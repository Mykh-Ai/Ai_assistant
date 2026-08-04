# Conversation Acceptance Proof: Supported Action Direct Routing

Verdict: `safe_to_commit`

Date: 2026-08-04

Approved design:
`docs/architecture/info_help_supported_action_direct_routing_architecture_design_proof.md`

Working state: branch `codex/supported-action-direct-routing`, based on
`9e9e9022c2fe274c01a0c46a1624a096c0d41e03`; commit SHA is assigned after this
proof is reviewed. Environment is local Windows/Python with isolated SQLite
fixtures. LLM, STT transport, Telegram transport, and deletion are mocked or
isolated as stated. Server deployment and human Telegram smoke are post-merge
evidence and are not claimed by this pre-commit verdict.

## Public-Entry Traces

### A — complete supported text command

- Preconditions: authorized actor `111`, idle, isolated supplier and invoice
  `20260010`.
- Entry/input: text, `Видалити фактуру 10`.
- Resolver/slot: `delete_existing_invoice`; Python reference `10`.
- Owner: `bot.handlers.invoice::_execute_invoice_reference_action`, exactly
  once.
- InfoHelp: zero calls; mocked secondary result would have confidence `0.97`.
- Transition: idle ->
  `InvoiceStates.waiting_delete_existing_invoice_confirm`.
- Side effect: zero deletion; the invoice row remains present.
- Response: `Naozaj chcete vymazať faktúru 20260010? Odpovedzte: áno / nie` with
  the unchanged existing decision keyboard.
- Evidence:
  `test_supported_invoice_delete_reaches_existing_owner_once_without_infohelp[text]`.
- Result: pass.

### B — missing invoice reference

- Preconditions: authorized actor, idle.
- Entry/input: text, `Vymazať faktúru`.
- Resolver/slot: `delete_existing_invoice`; no reference.
- InfoHelp: zero calls despite arranged secondary confidence `0.97`.
- Transition: idle ->
  `InvoiceReferenceContinuationStates.waiting_reference`; pending action is
  `delete_existing_invoice`.
- Side effect: none.
- Evidence:
  `test_supported_invoice_delete_without_reference_bypasses_infohelp_and_enters_continuation`
  and `tests/test_invoice_reference_continuation_v2.py`.
- Result: pass.

### C — voice convergence

- Preconditions: authorized idle voice route.
- STT transcript: `Видалити фактуру 10`.
- Observed handoff: shared `process_invoice_text`, channel `voice`; the public
  handler trace reaches the same owner once, same confirmation state, zero
  InfoHelp calls, and zero pre-confirm deletion.
- Evidence:
  `test_voice_delete_invoice_transcript_converges_on_shared_text_route` and
  `test_supported_invoice_delete_reaches_existing_owner_once_without_infohelp[voice]`.
- Result: pass.

### D — informational capability question

- Input: `Чи можу я видалити чек?` with an arranged false primary invoice-delete
  diagnostic.
- Result: Contextual InfoHelp/Product Truth answers the unsupported exact
  receipt operation; no invoice owner, state, or effect.
- Evidence:
  `test_receipt_delete_capability_question_blocks_false_invoice_delete`.
- Result: pass.

### E — correction and nearby object

- Input: `Я хочу чек видалити, а не фактуру!`.
- Result: correction/negation keeps the InfoHelp path; no invoice delete state.
- Unsupported contact edit begins with `unknown`, uses InfoHelp, and never calls
  supplier-profile edit.
- Evidence: `test_correction_negates_invoice_and_blocks_delete_flow` and
  `test_unsupported_contact_edit_uses_infohelp_without_supplier_profile_edit`.
- Result: pass.

### F — active FSM and confirmation

- Active FSM help remains owned by the active-state guard and does not change
  state. Existing negative confirmation exits without deletion, affirmative
  isolated confirmation deletes exactly once, and ambiguous confirmation
  remains fail-closed.
- Evidence: `test_active_fsm_help_keeps_state_and_calls_contextual_assistant_once`,
  `tests/test_invoice_state_decisions.py`, `tests/test_decision_resolver.py`, and
  `tests/test_voice_state_routing.py`.
- Result: pass.

### G — authorization and tenant isolation

- Authorization remains upstream of STT/LLM/business routing. Existing
  supplier/workspace-scoped lookup rejects ambiguous/inaccessible references;
  the shared owner and access tests remain green.
- Evidence: focused suite includes `tests/test_invoice_intent_prerouter.py`,
  `tests/test_voice_state_routing.py`, and current Product Truth tests; full
  repository regression is recorded below.
- Result: pass.

## Required Scenario Matrix

| # | Scenario | Result/evidence |
|---|---|---|
| 1 | Primary text happy path | pass, trace A |
| 2 | Action plus slot | pass, trace A |
| 3 | Missing slot continuation | pass, trace B |
| 4 | Invalid/ambiguous reference | pass, continuation and invoice lookup tests |
| 5 | Clarification consumed by state | pass, `test_next_reference_is_consumed_by_continuation_owner` |
| 6 | Command convergence | not applicable; no command added/changed |
| 7 | Voice convergence | pass, trace C |
| 8 | Button/text/voice decision convergence | unchanged; existing decision/voice suites pass |
| 9 | Active FSM priority | pass, trace F |
| 10 | Cancel/navigation/exit | unchanged; continuation and confirmation suites pass |
| 11 | Nearby action | pass, trace E and invoice prerouter suite |
| 12 | Unknown no effect | pass, contextual journey suite |
| 13 | Product Truth question no execution | pass, trace D |
| 14 | Stale/wrong callback | unchanged; no callback changed |
| 15 | Unauthorized no AI/effect | unchanged access boundary; full suite required before merge |
| 16 | Tenant isolation | pass, trace G |
| 17 | Persisted-data safety | pass: row remains before confirmation; actual delete owner unchanged |
| 18 | Old journeys through shared predicate | pass, focused suite |
| 19 | Keyboard lifecycle | unchanged existing keyboard and confirmation lifecycle; no new UI |

## Design-To-Code Map

| Design requirement | Code | Proof |
|---|---|---|
| mutation class alone does not invoke InfoHelp | `should_run_contextual_info_help` | predicate test |
| supported registered action with owner routes once | same predicate + `process_invoice_text` | trace A/C |
| missing reference stays owner-handled | `process_invoice_text` continuation branch | trace B |
| secondary confidence cannot veto | no secondary call on direct route | trace A/B |
| tenant lookup and confirmation unchanged | `_execute_invoice_reference_action` | trace A + existing suites |
| informational/correction input stays InfoHelp | predicate and existing V2 owner | trace D/E |

No material deviation from the approved design is recorded.

## Verification

- Regression-first old-code run: `4 failed, 22 passed`; the four failures were
  the intended direct/missing-slot veto assertions.
- Corrected narrow suite: `26 passed in 5.89s`.
- Expanded focused suite: `1086 passed in 87.99s`.
- Full `python -m pytest -q`: `2476 passed, 7 subtests passed in 457.79s`.
- Server deployment and live Telegram negative smoke: intentionally pending
  until merge; they must be appended before the overall task is called fully
  verified.

Decision: repository behavior is `safe_to_commit`; this is not merge,
deployment, or live-production acceptance.
