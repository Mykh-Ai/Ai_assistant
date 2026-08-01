# Invoice Edit Reference Continuation - Architecture Design Proof

Task ID: `INVOICE_EDIT_REFERENCE_CONTINUATION`

Date: 2026-08-01

Architect: Codex under owner-supervised OfficeFlow repair

Verdict: `ready_for_handoff`

Implementation status: `not_implemented_waiting_owner_approval`

## 1. Task identity and product need

Business need: when `edit_existing_invoice` is resolved without an invoice
reference, the bot must remember that it asked for the reference and consume
the next typed value inside the same edit flow.

Current failure: the handler sends `Napíšte číslo faktúry, ktorú chcete
upraviť.` and returns to idle without setting an FSM state. A following `05`
is classified as a fresh top-level message and receives unrelated InfoHelp
noise guidance.

User-visible outcome: the next typed invoice reference continues invoice
selection, or receives state-aware not-found/ambiguity recovery.

Current and target Product Truth status: `edit_existing_invoice` remains
`partial`; this repair completes one missing continuation but does not expand
the supported edit operations.

Risk: medium. No schema, migration, external integration, or new canonical
top-level action is required, but this is a material FSM-route change.

## 2. Architecture classification

Primary class: extension of the existing top-level action
`edit_existing_invoice` with a missing-slot continuation subflow.

It is not a new top-level intent because the business meaning and canonical
token already exist. It is not an InfoHelp-only change because the failure is
lost execution context. It is not a deterministic fast-path because the bot
must own a pending conversational state across messages.

## 3. Canonical action contract

- Token: `edit_existing_invoice`.
- Status: partial and implemented.
- Meaning: find one tenant-scoped persisted outgoing invoice and enter the
  existing bounded edit subflow.
- Runtime owner: `bot/handlers/invoice.py::process_invoice_text`, scoped
  invoice runtime, and `start_invoice_edit_flow`.
- Allowed context: authorized idle top-level routing.
- Entry: natural-language text or voice/STT may start the action; the missing
  exact invoice reference continuation is text-only.

No canonical token or allowed-actions list changes.

## 4. Semantic boundary matrix

| User meaning | Expected action/status | Why | Must not become |
|---|---|---|---|
| Edit an already saved outgoing invoice | `edit_existing_invoice` | Existing owner | create invoice or invoice analytics |
| Ask how invoice editing works | InfoHelp/Product Truth | Informational question | execute edit flow |
| Add/manage a reusable service alias | `add_service_alias` | Supplier mapping owner | invoice edit |
| Add details to an item of a selected invoice | existing item edit subflow | Child operation after invoice selection | global service-alias write |
| Bare `05` while waiting for invoice reference | pending reference value | Active FSM owns it | idle InfoHelp/noise triage |
| Bare `05` while idle | current top-level safe handling | No pending owner | implicit invoice edit |

The repair does not change how the first message is semantically classified.
Unknown or ambiguous initial meaning remains clarification/InfoHelp, never a
write default.

## 5. Structured slot contract

| Slot | Type | Source | Required | Default | Invalid behavior | Voice boundary |
|---|---|---|---|---|---|---|
| `invoice_reference` | bounded text reference accepted by existing extractor | first message or typed continuation | yes before lookup | none | remain in state and explain not found/ambiguous/invalid | continuation is text-only |

Python extracts and validates the reference with the existing
`_extract_invoice_reference` and tenant-scoped lookup. LLM does not fill,
validate, or execute the slot. No value is silently selected.

## 6. Public route and convergence

| Entry | Public owner | Guards | Shared owner | Result |
|---|---|---|---|---|
| Text with reference | top-level invoice route | authorization, idle state | existing edit lookup | existing edit flow |
| Text without reference | top-level invoice route | authorization, idle state | new pending-reference state | ask for typed reference |
| Typed continuation | state handler | authorization, active FSM | same scoped lookup | existing edit flow or recovery |
| Voice without reference | voice -> STT -> top-level route | authorization before STT | same pending state | ask for typed reference |
| Voice while pending | voice state guard | authorization, active FSM | no business parsing | request exact text, retain state |

No button or command path is added.

## 7. FSM graph and state ownership

```text
idle + edit_existing_invoice without reference
-> waiting_existing_invoice_reference

waiting_existing_invoice_reference + one exact tenant match
-> existing start_invoice_edit_flow
-> waiting_edit_scope

waiting_existing_invoice_reference + invalid/not found/ambiguous
-> waiting_existing_invoice_reference

waiting_existing_invoice_reference + cancel
-> idle
```

The state stores only the pending canonical action/context necessary for safe
recovery; it does not store a raw voice transcript. Active FSM owns ordinary
input. Unrelated text receives state-aware guidance and remains pending.
Global cancel clears the state. Stale/missing user or tenant context fails
closed and clears or safely exits according to existing access/runtime owners.

No keyboard is introduced.

## 8. Decision and callback contract

Not applicable. Invoice selection is not confirmation and adds no callback or
keyboard. Later edit confirmations remain owned by existing states and the
Canonical DecisionResolver contract.

## 9. Side-effect and ownership map

| Effect | Trigger | Owner | Gate | Failure/rollback |
|---|---|---|---|---|
| FSM metadata only | missing reference | aiogram state owner | authorized route | cancel/exit clears |
| Tenant-scoped invoice read | typed reference | scoped invoice runtime | authorized actor/workspace | no match stays pending |
| Business mutation | later existing edit flow only | existing edit services | existing validation/confirmation | unchanged |

Selection and clarification do not mutate invoices, contacts, service aliases,
files, or Product Truth.

## 10. Authorization, tenant, and precision boundaries

Authorization remains before STT/LLM and business access. Lookup uses the
current actor/workspace-scoped runtime. Cross-tenant fallback is forbidden.
Invoice reference is precision-sensitive: pending-state voice must not fill it
and must ask for typed text. No destructive confirmation changes.

## 11. User-facing response and exits

- Missing reference: explain that an existing invoice is being selected and
  request the number textually, including cancel guidance.
- Invalid/not found: explain the failure, retain the same state, and request a
  more complete exact reference.
- Ambiguous: request more trailing digits or the full number and retain state.
- Success: show the current existing invoice preview and enter the established
  edit-scope prompt.
- Cancel: clear state and return to idle with the shared cancellation response.
- Voice while pending: state remains; ask for the number as text.

## 12. Product Truth and InfoHelp

Capability ID remains `edit_existing_invoice`, status `partial`. Truthful
claim: an authorized user can select one saved outgoing invoice and use the
bounded existing edit flow. Limitation: invoice numbers and exact edited values
are text/precision-sensitive. Informational questions must continue to
Product Truth/InfoHelp and must not open the FSM.

## 13. Negative space and regressions

The change must not alter:

- initial semantic selection among edit, create, analytics, show, delete,
  paid-status, service alias, and InfoHelp;
- idle numeric input when no pending state exists;
- draft invoice editing;
- incoming/accounting-document behavior;
- tenant scoping;
- existing direct action-plus-reference path;
- existing item/invoice edit operations and confirmations;
- unauthorized behavior or STT/LLM access gates.

## 14. Acceptance scenarios

1. Text `upraviť faktúru` -> pending state -> typed `05` -> one scoped match ->
   existing preview and `waiting_edit_scope`.
2. Same first turn, then unknown reference -> no side effect, state retained.
3. Ambiguous short reference -> clarification, state retained.
4. Cancel from pending state -> idle, no lookup mutation.
5. Voice starts edit without a reference -> pending state; subsequent voice is
   rejected for precision and typed continuation succeeds.
6. Idle `05` without pending state does not enter invoice edit.
7. Capability question about adding service information stays InfoHelp and does
   not execute `edit_existing_invoice`.
8. Direct text action plus valid reference keeps the existing journey.
9. Unauthorized user cannot trigger STT/LLM, state, lookup, or storage.
10. Cross-tenant reference cannot select another workspace's invoice.
11. No-match, exception, and stale-context paths leave no business mutation.

Conversation Acceptance Proof must start from the public text/voice routes and
record state, resolver action, scoped owner, final response, and no-side-effect
facts under `docs/Evaluation_and_Smoke_Test_Standards.md`.

## 15. Out of scope and known gaps

- changing semantic hints for the unavailable preceding STT;
- adding a generic pending-slot framework for show/delete/paid actions;
- voice entry of invoice numbers;
- new buttons, callbacks, edit operations, aliases, or learning;
- schema/data migration, production data correction, merge, or deployment;
- recovering logs removed with the prior container recreation.

## 16. Evidence index and verdict

Evidence:

- runtime source issue `IR-20260801-78B6680F2D16` and Workshop log;
- `bot/handlers/invoice.py::process_invoice_text` missing-reference branch;
- `bot/handlers/invoice.py::InvoiceStates` and existing edit handlers;
- `bot/handlers/voice.py` active-state routing and precision exclusions;
- `bot/services/info_help.py::classify_info_help_triage`;
- deterministic local reproduction: `05` -> `spam_or_abuse` -> the reported
  concrete-business-task guidance;
- canonical action and in-action registries;
- Top-Level/Subflow Architecture Design Proof Contract;
- Evaluation and Smoke Test Standards.

Verdict: `ready_for_handoff`. Implementation may begin only after explicit
owner approval of this design.
