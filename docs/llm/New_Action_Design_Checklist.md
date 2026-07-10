# New Canonical Action Implementation Guide

Purpose: practical implementation gate before adding or upgrading a canonical top-level action or related in-FSM control in FakturaBot / OfficeFlow.

This guide is evidence-based. It exists because project history repeatedly showed the same failure modes:
- treating the LLM as a Python command dictionary instead of a bounded semantic canonicalizer;
- requiring literal alias/example matching instead of resolving product meaning;
- adding phrase dictionaries in `voice.py` instead of shared resolver/state-aware handlers;
- exposing a canonical token before a Python handler/service exists;
- marking an action implemented before text, command, voice, tests, and docs are synchronized;
- confusing `edit_invoice` draft/in-FSM editing with `edit_existing_invoice` persisted invoice editing;
- accepting voice in exact-value states such as IBAN, ICO, DIC, email, invoice number, prices, quantities, item descriptions, or final destructive confirmation;
- treating a blocek/accounting document as if it were an editable generated outgoing invoice;
- parsing confirmations locally instead of using the Canonical DecisionResolver;
- calling STT/LLM/LMM before authorization;
- letting callbacks or voice handlers own business logic instead of converging into state-aware Python handlers;
- forgetting registry, tests, README, `PROJECT_LOG.md`, and TZ synchronization.

Do not use this guide to invent architecture. If the runtime, registry, TZ, and project log do not prove that a behavior exists, treat it as not implemented.

---

## 0. Capability truth gate

Every new top-level action, alias, command, or user-visible workflow must first
answer:

- Is this an executable action or an informational capability?
- Does it require a Product Truth record or update?
- What should InfoHelp say when the user asks whether the bot can do this?
- What should InfoHelp say when the user asks how to use it?
- What unsupported, partial, setup-required, or credential-required questions
  may users ask about it?
- Which claims are forbidden?
- What happens if the user asks about it before setup is complete?
- Is voice/STT allowed to start it, control it, or fill values?
- Which active FSM states must win over this top-level action?
- Which tests and eval/smoke cases prove runtime behavior and truthful
  explanation?

Do not add top-level aliases that only route an action while leaving the bot
unable to explain the capability. If the user can execute it, the user can ask
about it, and Product Truth / InfoHelp must answer within current evidence.

---

## 1. Source-of-truth reading order

Before touching code for top-level actions, in-action decisions, LLM routing, voice/text routing, FSM controls, confirmations, OfficeFlow intake, storage, DB, or access, read the relevant contracts first.

Required baseline:
1. `AGENTS.md`
2. `docs/Product_Doctrine_2030.md`
3. `docs/AI_Layer_Implementation_Standards.md`
4. `docs/Product_Truth_Layer.md`
5. `docs/Info_Help_Guidance_Layer.md`
6. `docs/Evaluation_and_Smoke_Test_Standards.md`
7. `docs/TZ_FakturaBot.md`
8. `PROJECT_LOG.md`
9. `docs/FakturaBot_LLM_Orchestrator_Contract.md`
10. `docs/Canonical_Decision_Resolver_Contract.md`
11. `docs/llm/Canonical_Action_Registry.md`
12. `docs/llm/In_Action_Response_Registry.md`
13. `docs/llm/Bounded_Resolver_Prompt_Template.md`
14. this guide

Extra scopes:
- OfficeFlow / Document Intake: read OfficeFlow and Document Intake contracts before changing attachment routing, accounting intake, LMM prompts, storage, duplicate checks, or document previews.
- Access / authorization: read `docs/User_Access_Model_Roadmap.md` before changing `/start`, middleware, admin approval, unknown users, or user deletion.
- Migration-sensitive work: read the data migration/runbook docs and prepare audit, backup, rollback, and dry-run plans before any DB/storage/path/schema change.

Implementation summary must explicitly state:
- contracts read;
- constraints extracted;
- touched scopes: confirmation, routing, LLM/STT/LMM, FSM, storage, DB, access, server.

---

## 2. Definition of Done for a new top-level action

A top-level action is not done when a token is added to a registry. It is done only when every applicable item below is true.

- [ ] Canonical action identity is defined: name, product meaning, status, and nearby-action separation.
- [ ] `docs/llm/Canonical_Action_Registry.md` has an evidence-backed row with real source evidence.
- [ ] For `implemented` status, a real Python runtime owner exists: command handler, text route, FSM entry, or service call.
- [ ] Reserved/planned actions are not treated as runtime owners and cannot be marked `implemented`.
- [ ] `allowed_actions` includes the token only in contexts where Python has a real state-aware route to execute it or fail safely.
- [ ] Reserved/planned tokens are not added to runtime `allowed_actions` as if they were implemented.
- [ ] `action_hints` are added if plain token names are not enough to separate nearby meanings.
- [ ] Text route is wired and tested.
- [ ] Command route exists if the action is command-backed.
- [ ] Voice route is wired and tested, or the registry explicitly documents why voice is intentionally not applicable.
- [ ] Active FSM state wins over idle/top-level routing.
- [ ] In-FSM controls are documented in `docs/llm/In_Action_Response_Registry.md` where applicable.
- [ ] Exact-value boundaries are documented and enforced.
- [ ] Confirmation-like steps use `bot/services/decision_resolver.py`.
- [ ] Buttons, text, and voice converge into the same state-aware execution path where buttons exist.
- [ ] Unauthorized users cannot trigger STT, LLM, LMM, temp files, storage folders, DB rows, invoices, contacts, supplier profiles, or documents.
- [ ] Handler/service tests prove route, side effects, wrong-state behavior, and unauthorized behavior.
- [ ] Voice reachability tests exist, or intentional voice exclusion is documented and tested.
- [ ] Exact-value voice rejection tests exist for precision/destructive states.
- [ ] Product Truth is synchronized: new capability status, limitations, setup/admin/external-credential flags, forbidden claims, and safe next steps are documented or updated in the runtime registry when it exists.
- [ ] InfoHelp/support truth is synchronized: capability/how-to questions for the new action have a truthful answer path or a documented pending gap if runtime InfoHelp is not yet implemented.
- [ ] Product UX evals include at least one capability/how-to question for the new action and one unsupported/unknown nearby-action case where relevant.
- [ ] Docs are synchronized: TZ if product behavior changed, project log, Product Truth, InfoHelp guidance, registries, changelog when appropriate, and README architecture tree/navigation when action surfaces change.

If any item is intentionally out of scope, document that explicitly as `reserved`, `partial`, or `not voice-applicable`. Do not mark the action `implemented`.

---

## 3. Top-level action implementation checklist

### 3.1 Action identity

- [ ] Choose one canonical machine token.
- [ ] Define whether this is `implemented`, `reserved`, `partial`, or `unclear`.
- [ ] State the user-facing product meaning in plain language.
- [ ] Identify the existing command/manual flow, if one already exists.
- [ ] If no real Python runtime owner exists, keep the action `reserved` or `planned`; do not expose it as runtime-implemented.
- [ ] A reserved fallback may be documented in registries, but it is not implementation evidence.

### 3.2 Nearby-action separation

- [ ] List neighboring actions that users may confuse with this action.
- [ ] Add `not_this` guidance where confusion is likely.
- [ ] Verify known project separations:
  - `create_invoice` creates an outgoing invoice draft.
  - `add_receipt` starts upload for an external receipt/incoming invoice; it does not create an outgoing invoice from voice text.
  - `show_recent_accounting_documents` is read-only recent accounting metadata; it is not a broad document browser.
  - `edit_invoice` is reserved for current draft/in-FSM invoice editing semantics.
  - `edit_existing_invoice` edits an already persisted invoice after supplier-scoped Python lookup.
  - `delete_existing_invoice` deletes one invoice after confirmation.
  - `delete_user_database` starts a whole-user destructive warning flow and then requires exact typed confirmation.
  - `add_service_alias` creates a reusable service naming mapping; it does not create a concrete invoice.

### 3.3 Runtime route

- [ ] Identify the exact handler function that receives the canonical token.
- [ ] Ensure the handler validates `message.from_user`.
- [ ] Ensure supplier/contact/invoice/accounting lookups are scoped to the current Telegram user.
- [ ] Ensure Python validates all preconditions before side effects.
- [ ] Ensure `unknown` returns bounded Slovak guidance and does not clear useful state unless the state is unrecoverable.
- [ ] Ensure callbacks and voice handlers call the same state-aware helper instead of duplicating business logic.

### 3.4 Side effects

- [ ] List DB writes, file writes, storage moves, cleanup, access changes, external calls, and FSM transitions.
- [ ] For every side effect, identify the Python service that owns it.
- [ ] Confirm LLM/STT/LMM never performs or claims the side effect.
- [ ] If DB/storage/path/schema behavior changes, stop and run the migration-sensitive pre-work before implementation.

---

## 4. Bounded resolver checklist

The bounded resolver is a semantic canonicalizer, not a command executor and not an alias dictionary.

- [ ] Python provides `context_name`, `allowed_actions` or `allowed_values`, user text, optional `auxiliary_context`, and optional `action_hints`.
- [ ] Runtime `allowed_actions` contains only tokens with a state-aware Python route for execution or safe refusal.
- [ ] Reserved/planned tokens may appear in docs as future or fallback contract markers, but must not be advertised through runtime `allowed_actions` as implemented behavior.
- [ ] The resolver may return only one allowed token or `unknown`.
- [ ] The model cannot invent action names.
- [ ] `unknown` is always allowed and handled by Python.
- [ ] `action_hints` describe product meaning. They are not a whitelist of phrases.
- [ ] Examples in `action_hints` are illustrative only; tests must not require literal example matching.
- [ ] Deterministic Python fast-paths are allowed only when they are actually used and tested as narrow shortcuts.
- [ ] Variable natural-language slots are extracted by bounded LLM into structured values before Python validation; Python must not become the primary multilingual dictionary/parser for months, dates, periods, customer/service wording, or other business slots.
- [ ] Python slot parsers are limited to strict structural syntax, no-LLM compatibility fallback, or explicitly documented narrow deterministic ownership; any fallback parser must be named non-primary in docs/tests.
- [ ] Missing structured slot values use Python-owned business defaults only when the rule is explicit; invalid structured slot values fail loud or ask clarification instead of falling back to broad text guessing.
- [ ] LLM fallback remains available when fast-path aliases fail and an API key is configured.
- [ ] Resolver tests include semantic paraphrases, multilingual/noisy input, and nearby-action separation.
- [ ] Runtime tests prove Python validates the returned token before execution.

Bad pattern:
```text
If text contains one of these phrases, execute the action.
```

Required pattern:
```text
Python supplies allowed outputs -> resolver returns one token or unknown -> Python validates context -> Python executes existing handler/service.
```

### 4.1 InfoHelp Unknown / Discovery / Triage

InfoHelp bounded resolution is not a top-level action resolver. It must not
return executable action tokens. It may return a known Product Truth
`capability_id` / topic or, when no known capability fits, one Python-owned
triage class:

```text
known_product_capability
new_business_feature_request
customization_request_candidate
admin_review_candidate
out_of_domain
spam_or_abuse
smalltalk
unclear_needs_clarification
possible_product_truth_candidate
unknown
```

Rules:

- [ ] `unknown capability_id` triggers safe triage only after auth/state/routing
  gates allow it.
- [ ] Triage classes never mark a feature as supported.
- [ ] Triage classes never create canonical actions.
- [ ] Triage classes never save customization requests or notify admins.
- [ ] Out-of-domain, spam/noise, smalltalk, and unclear input are separated
  from business/customization candidates.
- [ ] Direct executable actions still win before InfoHelp/triage.
- [ ] Active FSM state still wins before InfoHelp/triage.
- [ ] Voice transcripts follow the same state-aware path.
- [ ] Tests cover Slovak, Ukrainian, Russian, mixed/surzhyk, and noisy-STT
  examples.

---

## 5. Voice coverage gate

Voice support is part of the user-facing FakturaBot MVP, but it is bounded.

- [ ] A new top-level action is not `implemented` unless voice reachability is implemented and tested, or explicitly documented as intentionally not voice-applicable.
- [ ] `voice.py` stays transport/STT/state router only.
- [ ] Do not add business phrase dictionaries to `voice.py`.
- [ ] Active FSM state wins over idle top-level routing.
- [ ] Voice may choose actions, fields, bounded options, item targets, routes, and confirmation options when Python supplies allowed outputs.
- [ ] Voice may provide the natural-language invoice request in idle state or in `InvoiceStates.waiting_input`.
- [ ] Voice must not fill precision-sensitive exact values.
- [ ] Unhandled active FSM voice input must ask for text and must not fall through to top-level action routing.

Text/file-only or typed-only examples:
- IBAN, ICO, DIC, IC DPH, email;
- invoice number and exact invoice references when precision matters;
- prices, quantities, totals, due-days when ambiguity is unsafe;
- final item descriptions and service alias names/titles;
- contact missing-field intake values;
- supplier profile new field values;
- destructive exact confirmation for `delete_user_database`.

---

## 6. Decision and confirmation gate

All confirmation-like decisions must use `bot/services/decision_resolver.py` unless an explicit exact typed destructive exception is documented.

- [ ] Decide whether the user reply is `yes_no`, `approve_edit_cancel`, an existing route/document-type family, a new bounded family, or not a decision.
- [ ] Register every new confirmation context in the central resolver tests.
- [ ] Do not add local `ano` / `nie` / `ok` / `schvalit` / `upravit` / `zrusit` parsing in handlers.
- [ ] Do not add per-flow multilingual synonym dictionaries.
- [ ] Handlers branch only on canonical outputs such as `yes`, `no`, `approve`, `edit`, `cancel`, route tokens, document-type tokens, or `unknown`.
- [ ] Buttons emit canonical `decision:*` tokens only.
- [ ] Button callbacks must validate authorization and current FSM state before side effects.
- [ ] Stale or wrong-state callbacks fail without business side effects.
- [ ] Text, voice transcript, and button callback paths converge into the same state-aware handler/helper.
- [ ] Destructive actions must fail safe on ambiguity.

Exact typed destructive exception:
- `delete_user_database` final confirmation is not yes/no.
- It requires exact typed text `vymazať databázu`.
- Voice is rejected before STT in that final confirmation state.

---


### 6.1 Active FSM / stale-state / callback-confirmation gate

Any new top-level action, subflow, preview, confirmation, callback-driven flow,
or pending user decision must declare its active-state safety coverage before it
can be accepted.

- [ ] If the action starts or continues an FSM state, it is covered by the
  shared active-FSM navigation/stale-state layer in
  `bot/services/active_fsm_guard.py`.
- [ ] Active text input uses the shared guard before state-specific business
  parsing; `pass_through` must continue to the existing state handler and must
  not be swallowed by a catch-all router.
- [ ] Active voice transcripts use the same shared guard after STT and before
  state-specific voice routing; `voice.py` must not add navigation phrase
  dictionaries.
- [ ] Every active FSM state records shared activity metadata, and stale-state
  evaluation reads the old timestamp before any refresh.
- [ ] Stale or legacy approve/save/delete/pay/send/mark-paid-like replies fail
  closed and cannot execute business side effects.
- [ ] If stale recovery replays a fresh business request, it first clears or
  safely cleans the old FSM state and routes through the existing idle
  top-level entry path exactly once.
- [ ] Callback confirmations validate authorization, expected current FSM state
  or pending callback context, activity timestamp or callback timestamp where
  available, and expiration before side effects.
- [ ] Legacy, missing-state, mismatched-state, or expired callbacks fail closed.
- [ ] Callback payloads that mutate data should include a timestamp, nonce, or
  equivalent pending-decision context where the existing keyboard API allows it.
- [ ] Fresh active-FSM safe switch confirmation is implemented only if the
  previous FSM state/data and original user request can be preserved or restored
  with tests. If that cannot be proven, document the follow-up gap instead of
  implementing an unsafe approximation.
- [ ] A stateless/read-only action that does not create an FSM state, pending
  decision, callback confirmation, recoverable draft, or preview explicitly
  documents why this shared guard is not required.

## 7. Dangerous boundary checklist

Apply this checklist before exposing or changing actions that touch destructive behavior, authorization, tenant scope, DB/storage, or external document intake.

- [ ] Unknown or unauthorized Telegram users cannot pass into the action.
- [ ] Authorization runs before STT, LLM, LMM, upload staging, temp workspace creation, DB writes, or storage writes.
- [ ] Tenant/user scope is deterministic Python logic, not resolver/LLM output.
- [ ] DB queries filter by `telegram_id` / `supplier_telegram_id` where relevant.
- [ ] Storage paths use current tenant/workspace rules; no cross-tenant fallback reads.
- [ ] Delete database flow requires exact typed confirmation and scoped deletion only.
- [ ] Invoice deletion remains separate from invoice creation and requires confirmation.
- [ ] Receipt/accounting document intake treats blocek/incoming invoice as an external source document, not as an editable outgoing invoice.
- [ ] No automatic contact creation from receipts, PDFs, photos, or idle attachments.
- [ ] No automatic accounting document save before preview approval.
- [ ] No server/storage/schema/path changes unless explicitly in scope and migration-sensitive pre-work is approved.
- [ ] Cleanup code is restricted to known temp paths or explicitly scoped tenant-owned paths.

---

## 8. Required tests

Use focused tests for the changed surface, then run the full suite with:

```powershell
python -m pytest -q
```

Minimum test matrix for a new or upgraded action:

- [ ] Resolver tests for canonical token, `unknown`, multilingual/noisy/STT-like input, and nearby-action separation.
- [ ] Handler route tests for text and command entry.
- [ ] Voice reachability tests for top-level action or documented voice exclusion.
- [ ] Active-FSM tests proving state wins over top-level routing.
- [ ] In-FSM control tests for action/field/option selection.
- [ ] Exact-value voice rejection tests for typed-only states.
- [ ] DecisionResolver family tests for every confirmation-like context.
- [ ] Handler tests proving no local confirmation parser drives the branch.
- [ ] Callback tests if buttons are present: canonical token, authorization, stale/wrong state, and convergence into handler.
- [ ] Unauthorized tests proving no STT/LLM/LMM, temp files, DB rows, storage paths, invoices, contacts, supplier profiles, or documents are created.
- [ ] Side-effect tests for DB/storage writes, cleanup, and rollback/fail-safe behavior.
- [ ] Wrong-state/stale-state tests proving no accidental clear or side effect.
- [ ] Full suite run before marking complete.

If tests are not run, say exactly why and do not claim runtime completion.

---

## 9. Docs synchronization

Docs must match runtime evidence. Do not update one registry and leave the rest stale.

Update as applicable:
- `PROJECT_LOG.md`: every meaningful session, constraints read, touched scopes, verification.
- `CHANGELOG.md`: user-visible behavior or release-note-worthy changes.
- `docs/TZ_FakturaBot.md`: product logic, MVP scope, authorization, storage, or runtime behavior changes.
- `docs/Product_Truth_Layer.md` or the runtime Product Truth registry when it exists: capability status, limitations, setup/admin/external-credential flags, forbidden claims, safe next steps.
- `docs/Info_Help_Guidance_Layer.md` or the runtime InfoHelp registry when it exists: how users should learn about the capability and what answer they receive when they ask whether/how the bot can do it.
- `docs/Evaluation_and_Smoke_Test_Standards.md` or focused eval artifacts: product UX smoke scenarios for capability questions, unsupported nearby requests, active FSM confusion, and no hidden side effects.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`: bounded resolver contract changes.
- `docs/Canonical_Decision_Resolver_Contract.md`: decision family or confirmation policy changes.
- `docs/llm/Canonical_Action_Registry.md`: top-level action status, entry modes, source evidence.
- `docs/llm/In_Action_Response_Registry.md`: in-FSM controls, decision families, slot/value groups.
- README architecture tree/navigation: new files, handlers, services, commands, or public action surfaces.

Status wording rules:
- `implemented` means runtime exists, reachable modes are wired, tests cover it, and docs agree.
- `reserved` means token/name may exist but runtime does not execute a standalone business flow.
- `partial` means a bounded slice exists; document exactly what is and is not implemented.
- `unclear` means evidence is insufficient; investigate before coding.

---

## 10. Final implementation pre-flight

Before code changes, the implementation agent must be able to answer:

- [ ] What exact user problem does this action solve?
- [ ] Which existing flow owns execution?
- [ ] Which canonical token is returned by the resolver?
- [ ] Which `allowed_actions` context includes it?
- [ ] What happens on `unknown`?
- [ ] Does voice reach it, and if not, why?
- [ ] Which active FSM states must intercept voice/text before top-level routing?
- [ ] Which exact values are text/file-only?
- [ ] Which DecisionResolver family is used?
- [ ] What side effects occur, and which Python service owns them?
- [ ] What tenant/user scope is enforced?
- [ ] What is the Product Truth status after this change?
- [ ] How will InfoHelp answer "can you do this?" and "how do I use this?" for this action?
- [ ] Which unsupported or partial claims must InfoHelp refuse?
- [ ] Which setup/admin/external-credential state changes the answer?
- [ ] What tests prove the route, voice behavior, authorization, wrong-state safety, exact-value safety, and docs/runtime synchronization?
- [ ] What product UX eval proves the user can discover and understand the new capability?
- [ ] Which docs are updated in the same patch?

If any answer depends on guessing, the implementation is not ready.
