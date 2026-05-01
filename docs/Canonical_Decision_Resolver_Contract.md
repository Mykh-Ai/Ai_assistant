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

### 7.1 Phase 1 Runtime Status

Implemented in `bot/services/decision_resolver.py`:
- `resolve_approve_edit_cancel(...)` returns `approve`, `edit`, `cancel`, or `unknown`.
- `resolve_yes_no(...)` returns `yes`, `no`, or `unknown`.

Migrated runtime paths:
- invoice preview confirmation;
- invoice post-PDF decision;
- contact semantic intake confirmation;
- manual contact confirmation;
- supplier onboarding confirmation;
- existing invoice delete confirmation.

Voice routing now sends confirm-state transcripts to the active confirmation handler for:
- invoice preview confirmation;
- invoice post-PDF decision;
- existing invoice delete confirmation;
- contact semantic intake confirmation;
- manual contact confirmation;
- supplier onboarding confirmation.

Not implemented by this migration:
- OfficeFlow Document Intake runtime;
- Telegram button/callback handling;
- DB schema changes;
- storage path changes;
- invoice PDF path behavior changes.

---

## 8. Non-Goals

This contract does not implement:
- runtime refactor,
- DB changes,
- storage changes,
- Document Intake runtime,
- Telegram button UI,
- changes to invoice numbering, PDF generation, or `pdf_path`.

