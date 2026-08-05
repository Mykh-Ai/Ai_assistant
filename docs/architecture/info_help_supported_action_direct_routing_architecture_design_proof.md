# Supported Canonical Actions Route Directly To Existing Owners

> Superseded for current routing by the 2026-08-05 primary-bundle ownership
> amendment in
> `docs/architecture/INFOHELP_CONTEXTUAL_AI_ASSISTANT_V2_ARCHITECTURE_DESIGN_PROOF.md`.
> This file remains historical evidence of the narrower 2026-08-04 repair.

Verdict: `ready_for_handoff`

Date: 2026-08-04

## 1. Task Identity And Product Need

The supported request `Видалити фактуру 10` already resolves to
`delete_existing_invoice`, but the current Contextual InfoHelp predicate invokes
a second LLM solely because the action is destructive. That call can veto the
existing runtime owner through a confidence threshold. The target is direct
convergence on the existing lookup and confirmation flow, with no deletion
before the existing affirmative confirmation.

Product Truth status is `supported`; the runtime owner and confirmation-gated
deletion already exist. Risk is high at the routing boundary, while the
destructive side-effect boundary is intentionally unchanged.

## 2. Architecture Classification

Class 5: deterministic internal routing correction for an existing action.
This is not a new action, alias, slot, subflow, FSM, confirmation, button,
callback, or deletion implementation.

Verified current symbols:

- `bot/services/info_help_assistant.py::should_run_contextual_info_help`
- `bot/handlers/invoice.py::process_invoice_text`
- `bot/handlers/invoice.py::_apply_contextual_info_help_v2`
- `bot/handlers/invoice.py::_extract_invoice_reference`
- `bot/handlers/invoice.py::_execute_invoice_reference_action`
- `InvoiceReferenceContinuationStates.waiting_reference`
- `InvoiceStates.waiting_delete_existing_invoice_confirm`

## 3. Canonical Action Contract

- canonical token: `delete_existing_invoice`
- status: `implemented` / Product Truth `supported`
- meaning: delete one already persisted outgoing invoice
- owner: existing invoice-reference action owner
- entry: authorized idle text and voice-transcript routes
- protection: existing deterministic `yes_no` confirmation

No token is added or renamed.

## 4. Semantic Boundary

| Input/meaning | Expected | Forbidden result |
|---|---|---|
| `Видалити фактуру 10` | existing delete owner, reference `10`, confirmation state | InfoHelp clarification |
| `Видалити фактуру` | existing reference continuation | generic InfoHelp |
| supported Slovak equivalent | same owner | literal-only shortcut |
| edit invoice `10` | existing edit action | invoice deletion |
| delete contact | existing contact behavior | invoice deletion |
| delete receipt `10` | existing truthful receipt behavior | invoice deletion |
| `Чи можеш видалити фактуру?` | InfoHelp/Product Truth | deletion FSM |
| unclear `Видали 10` | existing clarification | assumed deletion |

## 5. Structured Slot Contract

`invoice_reference` comes only from the existing Python extractor and existing
resolver diagnostics. It is optional at entry. When present, Python passes it
to the existing owner; when absent, the owner starts the existing continuation
FSM. Persisted identity is established only by the existing tenant-scoped
lookup. The existing DecisionResolver supplies the confirmation decision.

No additional LLM extraction, phrase dictionary, invented reference, or slot
default is allowed. Missing reference is an owner-handled missing slot.

## 6. Public Route And Convergence

```text
authorized idle text or authorized STT transcript
-> active-FSM guard
-> primary bounded resolver
-> supported canonical action + registered runtime owner
-> existing Python owner
```

Questions, `unknown`, unsupported, corrective/negative, and genuinely
ambiguous input retain Contextual InfoHelp. Public routing happens once; voice
uses the same business route as text.

## 7. FSM Graph And Ownership

```text
IDLE
-> delete_existing_invoice + reference
   -> tenant lookup
   -> InvoiceStates.waiting_delete_existing_invoice_confirm
      -> yes -> existing deletion owner
      -> no/cancel -> safe exit, no deletion

IDLE
-> delete_existing_invoice without reference
   -> InvoiceReferenceContinuationStates.waiting_reference
      -> valid reference -> tenant lookup -> existing confirmation state
      -> invalid/ambiguous -> remain and clarify
      -> cancel -> existing safe exit
```

No state is added or renamed. Existing active FSM ownership remains prior to
idle routing.

## 8. Decision And Confirmation Contract

The existing `yes_no` DecisionResolver context and
`InvoiceStates.waiting_delete_existing_invoice_confirm` remain authoritative.
Affirmative confirmation owns the existing delete side effect; negative,
cancel, ambiguous, stale, or wrong-state input performs no deletion according
to the existing fail-closed behavior. No new parser, prompt, message, or button
is introduced.

## 9. Side-Effect Ownership

| Effect | Existing owner | Gate |
|---|---|---|
| FSM transition | invoice-reference owner | supported direct route |
| invoice lookup | tenant-scoped invoice service | current workspace/supplier |
| invoice deletion | existing deletion service | affirmative existing confirmation |

Routing adds no DB, file, network, or API write.

## 10. Authorization, Tenant, And Precision Boundaries

Authorization, active-FSM ownership, workspace selection, tenant-scoped lookup,
cross-tenant failure, and confirmation remain unchanged. Invoice identity is
never disclosed or selected across tenants. The patch does not alter precision
rules.

## 11. User-Facing Outcome

With a resolvable reference, the current production wording is retained:

`Naozaj chcete vymazať faktúru 20260010? Odpovedzte: áno / nie`

Without a reference, the current request for an invoice number and its
continuation state are retained. Generic InfoHelp is not acceptable for either
supported executable request.

## 12. Product Truth And InfoHelp Contract

`delete_existing_invoice` remains `supported`. InfoHelp may explain the
confirmation-gated capability and continues to own questions, usage/help,
unknown, unsupported, corrective/negative, and genuinely ambiguous input. It
must not reclassify or veto an already resolved supported action with a real
owner.

## 13. Negative Space And Regression Contract

Invoice create/edit/view/analytics, contacts, receipts/accounting documents,
active FSM navigation, authorization, tenant isolation, stale protection,
confirmation, actual deletion, recent InfoHelp context, and unresolved-input
behavior remain unchanged. The fix is registry/Product-Truth driven and does
not match one literal sentence.

## 14. Acceptance Scenarios

Required evidence covers:

1. complete text route: InfoHelp `0`, owner `1`, confirmation state, deletion `0`;
2. missing reference: InfoHelp `0`, existing continuation state;
3. secondary confidence `0.97` cannot gate because no secondary call occurs;
4. capability question: InfoHelp, no owner/state/effect;
5. ambiguous input: clarification, no deletion;
6. neighboring edit/contact/receipt routes do not become deletion;
7. voice transcript converges on the same owner;
8. active FSM remains authoritative;
9. yes/no/ambiguous confirmation regression remains fail-closed;
10. unauthorized and cross-tenant attempts disclose and mutate nothing.

## 15. Out Of Scope

New states, buttons, confirmation UX, persistent InfoHelp history, raw LLM
payload storage, general InfoHelp redesign, deletion semantics, tenant changes,
migrations, `.env` changes, and unrelated refactoring are excluded.

## 16. Evidence Index

- action registry: `docs/llm/Canonical_Action_Registry.md`
- Product Truth: `bot/services/product_truth.py`
- shared semantic registry: `bot/services/info_help_action_registry.py`
- routing predicate: `bot/services/info_help_assistant.py`
- public route and owner: `bot/handlers/invoice.py`
- confirmation: `bot/services/decision_resolver.py`
- routing tests: `tests/test_info_help_contextual_v2.py`
- public journey tests: `tests/test_info_help_contextual_journeys_v2.py`
- continuation tests: `tests/test_invoice_reference_continuation_v2.py`
- confirmation tests: `tests/test_invoice_state_decisions.py`

Forensic baseline: mutation/destructive class and missing reference each
unconditionally caused a second Contextual InfoHelp call. Its destructive
confidence threshold was `0.98`, so an otherwise correct `0.97` result blocked
the owner and native continuation. The approved correction removes the second
call from the supported direct-action path; it does not lower the threshold.
