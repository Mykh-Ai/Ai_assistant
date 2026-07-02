# Canonical DecisionResolver Contract

**Document role:** project-level architecture contract for confirmation-like user decisions.

This contract started as a docs-only policy and migration target.
Phase 1 runtime migration now exists for the current FakturaBot confirmation surfaces listed in section 7.1, but this document still does not claim that future modules or Telegram button callbacks are implemented.

---

## 1. Purpose

FakturaBot and future OfficeFlow modules need one canonical path for user replies that approve, reject, edit, cancel, or confirm an action.

Runtime audit found several confirmation paths:
- invoice preview approval/edit/cancel,
- post-PDF invoice decision,
- contact save/cancel,
- supplier onboarding save/cancel,
- hard-delete confirmation,
- future Document Intake preview/confirm.

Some paths already use bounded semantic confirmation resolution. Some older paths still use local literal parsers. Those local parsers are technical debt and must be migrated after tests.

---

## 2. Policy

All confirmation-like user replies must go through one shared **Canonical DecisionResolver**.

No new per-module local parsers for forms such as `ano`, `nie`, `ok`, `schvalit`, `upravit`, or `zrusit` are allowed.

The resolver normalizes user input into canonical decision tokens only. The active FSM flow remains the only place that executes the business action.

This is a runtime contract, not guidance. Future agents must treat this document as an implementation gate for any flow that asks the user to confirm, reject, approve, edit, cancel, save, delete, route, or choose between bounded next steps.

Forbidden patterns for new work:
- adding `if text.lower() in {...}` or equivalent confirmation parsing in handlers;
- adding a per-flow list of words such as `ano`, `nie`, `ok`, `так`, `да`, `save`, `delete`, or `cancel`;
- adding context-specific yes/no or approve/cancel word lists in a lower resolver layer when the behavior belongs to an existing decision family;
- letting an LLM return a final business action for a confirmation step.

Required pattern:
- the handler calls `bot/services/decision_resolver.py`;
- Python receives only family-level canonical outputs;
- the handler branches only on canonical tokens such as `yes`, `no`, `approve`, `edit`, `cancel`, or `unknown`;
- the confirmation context is registered in the central test matrix in `tests/test_decision_resolver.py`;
- user-facing wording can mention Slovak examples, but parsing those examples belongs to the shared resolver family, not to the flow.

Every new confirmation-like flow must add its `context_name` to one of the central test registries:
- `YES_NO_CONTEXTS`;
- `APPROVE_EDIT_CANCEL_CONTEXTS`;
- or a new explicitly named DecisionResolver family matrix added with the new family.

If the context is not in one of these matrices, the runtime flow is not considered covered by the Canonical DecisionResolver contract.

---

## 3. Decision Families

### 3.1 `approve_edit_cancel`

Used when the user can approve, edit, cancel, or produce an unresolved answer.

Canonical outputs:
- `approve`
- `edit`
- `cancel`
- `unknown`

Existing Slovak-facing invoice tokens such as `schvalit`, `upravit`, and `zrusit` may remain runtime/UI compatibility vocabulary, but new shared architecture should normalize to the family-level meaning above or provide an explicit adapter.

### 3.2 `yes_no`

Used when the user can confirm yes, reject no, or produce an unresolved answer.

Canonical outputs:
- `yes`
- `no`
- `unknown`

Existing Slovak-facing tokens such as `ano` and `nie` may remain runtime/UI compatibility vocabulary, but new shared architecture should normalize to the family-level meaning above or provide an explicit adapter.

### 3.3 New decision family gate

Before adding a new action, router, document intake step, delete flow, save flow, or approval step, the implementer must decide whether the user's reply is one of:
- an existing decision family (`yes_no`, `approve_edit_cancel`, etc.),
- a new bounded decision family that belongs in `bot/services/decision_resolver.py`,
- not a confirmation-like decision at all.

If it is confirmation-like, route-like, or destructive-action-like, it must be represented as a DecisionResolver family before runtime handler code is added.

New families must define:
- family name,
- canonical outputs,
- `unknown` behavior,
- which handlers are allowed to consume those outputs,
- tests for noisy/multilingual/STT-like input,
- a central context registry in `tests/test_decision_resolver.py`,
- tests that handlers branch only on canonical outputs.

New families must be documented in `docs/llm/In_Action_Response_Registry.md` before or together with runtime implementation.

### 3.4 `work_time_open_conflict_choice`

Used when the user tries to open a work day while a previous work day is still open.

Canonical outputs:
- `close_day`
- `fill_time`
- `skip_day`
- `cancel`
- `unknown`

### 3.5 `work_time_missing_days_choice`

Used for bounded work-time missing-day prompts when the runtime asks whether to fill, skip, or cancel.

Canonical outputs:
- `fill`
- `skip`
- `cancel`
- `unknown`
### 3.6 Exact typed destructive exception

`delete_user_database` final confirmation is an explicit exception to the yes/no confirmation pattern. The top-level entry intent may be resolved by the bounded Semantic Action Resolver, but final deletion must not use a yes/no DecisionResolver family and must not be accepted from voice. Runtime requires the exact typed phrase `vymazať databázu`; any other text keeps the confirmation state, and voice in that state is rejected before STT with a typed-text instruction.

---

## 4. Input Channels

The same decision path must handle:
- text message input,
- voice transcript input,
- future Telegram button/callback input.

Channel-specific handlers may adapt transport details, but they must converge into the same canonical decision family and token set before business logic runs.

---

## 5. Authority Split

LMM/semantic resolver responsibility:
- map noisy/multilingual/STT-distorted input to one allowed canonical decision token,
- return `unknown` when unclear,
- never execute the business action.

Python/FSM responsibility:
- define the active decision family and allowed outputs,
- validate that the canonical token is allowed in the current state,
- execute the business branch,
- fail safe on `unknown` or invalid context.

Business action execution must stay in the active FSM flow, not in the resolver.

### 5.1 Shared STT `áno` artifact fallback

Known deterministic STT artifacts of spoken Slovak `áno` are normalized only inside the shared resolver/lexicon layer before any LLM fallback:
- `Ah, não`
- `Ah no`
- `Ah ňao`
- `Ахняо`

These artifacts mean:
- `yes` in the `yes_no` family;
- `approve` in `approve_edit_cancel` contexts where `áno` already means approve, such as invoice preview approval.

This fallback does not add standalone Slovak-looking `no`, `nó`, `noo`, or `nou` as affirmative tokens. Handlers must not add local dictionaries for these artifacts, and callbacks are unaffected because they already emit canonical `decision:*` tokens.

---

## 6. Scope

This policy applies to:
- invoice preview confirmation,
- post-PDF invoice decision,
- existing invoice delete confirmation,
- contact save/cancel confirmation,
- supplier onboarding save/cancel confirmation,
- service/module confirmation flows added later,
- future OfficeFlow Document Intake preview/confirm lifecycle.

---

## 7. Migration Target

Existing local confirmation parsers are technical debt.

Migration must be tests-first:
1. Add regression tests around current accepted replies and branch outcomes.
2. Introduce the shared Canonical DecisionResolver adapter.
3. Migrate one low-risk flow at a time.
4. Keep behavior-compatible aliases until explicit cleanup is approved.
5. Confirm voice/text parity for every migrated FSM state.

Until migration is complete, docs and code must not claim the shared resolver is fully implemented everywhere.

For new flows, migration status is not an excuse to add new local parsers. Legacy local parsers may exist only as documented technical debt. New work must use the Canonical DecisionResolver from the first implementation slice.

### 7.1 Current Runtime Status

Implemented in `bot/services/decision_resolver.py`:
- `resolve_approve_edit_cancel(...)` returns `approve`, `edit`, `cancel`, or `unknown`.
- `resolve_yes_no(...)` returns `yes`, `no`, or `unknown`.
- `resolve_attachment_route_choice(...)` returns `create_contact`, `save_contract`, `cancel`, or `unknown`.
- `resolve_attachment_document_type_choice(...)` returns `receipt`, `incoming_invoice`, `contract`, `contact_source`, `cancel`, or `unknown`.
- `resolve_global_cancel(...)` returns `cancel` or `unknown` for global state-control escape wording.

Migrated runtime paths:
- invoice preview confirmation;
- invoice post-PDF decision;
- contact semantic intake confirmation;
- manual contact confirmation;
- supplier onboarding confirmation;
- targeted supplier profile edit confirmation;
- existing invoice delete confirmation.
- invoice customer alias confirmation.
- idle attachment accounting proposal confirmation;
- idle attachment route choice;
- idle attachment document-type clarification;
- accounting document duplicate save decision;
- accounting document preview decision.
- global state cancellation through `/cancel` and shared cancel wording such as `zrušiť`, `скасувати`, `відмінити`, `отменить`, and “почни з початку”.

Voice routing now sends confirm-state transcripts to the active confirmation handler for:
- invoice preview confirmation;
- invoice post-PDF decision;
- existing invoice delete confirmation;
- invoice customer alias confirmation;
- contact semantic intake confirmation;
- manual contact confirmation;
- supplier onboarding confirmation.
- targeted supplier profile edit confirmation.
- OfficeFlow idle attachment proposal/route/document-type decisions;
- accounting document duplicate and preview decisions.

Current Phase 2 boundary:
- voice can control bounded state actions/field choices when Python supplies allowed outputs;
- exact value entry remains text/file-only where STT guessing is unsafe;
- `delete_user_database` final confirmation remains exact typed text only and rejects voice before STT.

### 7.2 Decision UI Layer Phase 1

Decision UI Layer Phase 1 is the historical increment that introduced Telegram inline decision buttons for stable confirmation surfaces.

Implemented button surfaces:
- invoice draft preview confirmation;
- invoice customer alias confirmation;
- existing invoice delete confirmation;
- contact semantic intake confirmation;
- manual contact confirmation;
- supplier onboarding confirmation;
- targeted supplier profile edit confirmation.

Callback authorization rule:
- callback queries must pass the same Telegram user authorization boundary before any callback side effect;
- unknown or blocked users must not trigger decision callback execution;
- callbacks must not create access requests, tenants, supplier profiles, contacts, invoices, documents, temporary files, or storage paths for unauthorized users.

Decision UI contract:
- buttons emit only canonical callback tokens: `decision:yes`, `decision:no`, `decision:approve`, `decision:edit`, or `decision:cancel`;
- callbacks do not call LLM, STT, LMM, or per-flow local parsers;
- callbacks validate the active FSM state before executing;
- stale or wrong-state callbacks are rejected without business side effects;
- text and voice inputs continue through `bot/services/decision_resolver.py`;
- text/voice resolver output and button callback tokens converge into the same state-aware handler execution path.

Out of scope for Phase 1:
- `decision:reupload`;
- standalone contract save/archive buttons;
- OfficeFlow route/document-type buttons such as `create_contact`, `save_contract`, `receipt`, `incoming_invoice`, `contract`, or `contact_source`;
- accounting document preview edit button while runtime edit remains unavailable;
- DB schema, storage model, server, or LLM prompt changes.

---

## 8. Non-Goals

This contract does not implement:
- runtime refactor,
- DB changes,
- storage changes,
- Document Intake runtime,
- Telegram button UI,
- changes to invoice numbering, PDF generation, or `pdf_path`.


### 7.2 OfficeFlow Work-Time DecisionResolver Slice - 2026-07-01

Implemented in `bot/services/decision_resolver.py`:
- `resolve_work_time_open_conflict_choice(...)` returns `close_day`, `fill_time`, `skip_day`, `cancel`, or `unknown`.
- `resolve_work_time_missing_days_choice(...)` returns `fill`, `skip`, `cancel`, or `unknown`.

Migrated runtime paths:
- work-time manual range preview uses the shared `approve_edit_cancel` family;
- work-time close preview uses the shared `approve_edit_cancel` family;
- work-time monthly delete confirmation uses the shared `yes_no` family with context `work_time_delete_month_confirm`;
- open-day conflict choices use `work_time_open_conflict_choice`;
- missing-day choices use `work_time_missing_days_choice`.

Voice routing sends active work-time FSM transcripts to the same state handlers. Exact time values remain preview-confirmed and Python-validated before any write.

