# Invoice Edit Direct Action Architecture Design Proof

## 1. Task Identity And Product Need

- Task: direct invoice-edit action routing with Telegram buttons.
- Business need: a user who says a concrete edit such as `dátum dodania` must not be forced through a separate `faktúra alebo položka` turn or loop.
- User-visible outcome: one edit menu exposes the supported invoice fields and item branch as inline buttons; concrete text/voice input skips already-resolved levels.
- Current/target Product Truth: `edit_existing_invoice` remains `supported`; this repairs its bounded subflow and discoverability.
- Risk: medium FSM/callback UX risk; no new business mutation, schema, storage, or PDF semantics.
- Date/approval: 2026-08-18; user approved the hybrid button + live LLM design in this thread.

## 2. Architecture Classification

Primary class: **sub-action / canonical in-FSM control** under existing draft and persisted invoice editing. No new top-level action or capability is introduced.

## 3. Canonical Action Contract

Existing bounded operations remain the only executable outputs:

- `edit_invoice_number`
- `edit_invoice_issue_date`
- `edit_invoice_delivery_date`
- `edit_invoice_due_date`
- `replace_service`
- `edit_item_description`
- `edit_item_quantity`
- `edit_item_unit_price`
- `edit_item_total_amount`
- `item_level` only when an item target/action still needs selection
- `unknown`

Runtime owner remains `bot/handlers/invoice.py`. Buttons and LLM output select only from Python-provided values.

## 4. Semantic Boundary Matrix

| Meaning | Expected result | Must not become |
|---|---|---|
| change delivery date | `edit_invoice_delivery_date` | generic scope loop or issue/due date |
| change invoice number | `edit_invoice_number` | item number selection |
| change item quantity/price/total | matching item operation | invoice total/date edit |
| generic invoice-level wording | invoice-level menu/clarification | guessed write |
| generic item wording | item target/action selection | guessed item mutation |
| unclear input | `unknown`, same menu/state | any value/write default |

## 5. Structured Slot Contract

- `operation`: bounded LLM output or canonical callback token; required before value entry.
- `target_item_index`: Python default `1` only for a single-item invoice; otherwise explicit bounded selection.
- date value: bounded LLM normalization followed by strict Python validation.
- invoice number, item numeric values, service value, and final description: existing precision boundaries remain unchanged.
- Buttons never carry business values, invoice ids, or tenant data; they carry only canonical operation tokens.

## 6. Public Route And Convergence Map

| Mode | Entry | Resolver | Shared owner |
|---|---|---|---|
| text | active invoice edit FSM | unified bounded edit resolver | invoice edit operation dispatcher |
| voice | authorized STT, then active FSM | same unified bounded edit resolver | same dispatcher |
| button | authorized callback + expected state/message ownership | pre-canonicalized token | same dispatcher |

`voice.py` remains transport/state routing only.

## 7. FSM Graph And State Ownership

```text
preview edit / persisted edit
  -> waiting_edit_scope (unified edit menu)
     -> concrete invoice operation -> matching value state
     -> concrete item operation + one item -> matching value state
     -> item_level + one item -> waiting_edit_item_action
     -> item_level + many items -> waiting_edit_item_target -> waiting_edit_item_action
     -> generic invoice_level -> waiting_edit_invoice_action (compatibility clarification)
     -> unknown -> waiting_edit_scope with same menu
  -> successful draft edit -> waiting_confirm + updated preview
  -> successful persisted edit -> waiting_pdf_decision
```

Existing value handlers, validation, draft persistence boundary, persisted tenant scoping, and cancel/navigation behavior remain unchanged.

## 8. Decision And Callback Contract

- Keyboard type: inline.
- Callback prefix is invoice-edit-specific and accepts only the canonical tokens listed above.
- Expected state is `waiting_edit_scope` or the applicable item-action state.
- Python validates callback actor through FSM ownership, stored prompt message/chat ids, current state, and active-FSM expiry.
- Handled callbacks remove the old markup. Owned stale/expired callbacks remove obsolete markup; malformed, wrong-state, wrong-message, or unproven-ownership callbacks fail closed without altering the message.
- Cleanup failure is logged and does not undo an already-valid FSM transition.
- Buttons perform no DB/file mutation; final values continue through existing validators/confirmation boundaries.

## 9. Side Effects And Ownership

The changed selection step mutates FSM state only. Existing Python value handlers own draft mutation or supplier-scoped persisted invoice/PDF updates. No LLM or callback executes those effects directly.

## 10. Authorization, Tenant, And Precision Boundaries

Existing authorization middleware precedes STT/LLM/callback handling. Persisted invoice lookup remains supplier-scoped. Exact-value voice restrictions remain unchanged. No data migration is required.

## 11. User-Facing Response And Exit Contract

The first edit prompt shows direct supported actions. A concrete text/voice/button choice asks only for the missing exact value. Generic item selection opens the existing item branch. Unknown input repeats the actionable menu. Successful edits return to the existing preview/approval owner.

## 12. Product Truth And InfoHelp Contract

- Capability: `edit_existing_invoice`.
- Status: `supported`, requires setup/authorization.
- Supported behavior: edit bounded invoice fields and existing item fields through direct buttons or natural text/voice selection.
- Limitation: exact references and precision-sensitive edited values retain existing text-first/validation rules.
- Forbidden: claiming arbitrary invoice fields, contact replacement, add-item, cross-tenant edits, or unconfirmed writes.

## 13. Negative Space And Regression Contract

Preserve invoice creation, preview approve/cancel, existing-invoice lookup, item targeting, precision checks, active-FSM ownership, authorization, tenant scoping, PDF rebuild semantics, and Product Truth capability-question routing.

## 14. Acceptance Scenarios

- Draft preview -> edit -> text/STT `dátum dodania` -> date -> updated preview.
- The same direct route for issue date, due date, and invoice number.
- Direct item operation for one item; explicit target for multiple items.
- Button and text/voice converge on the same dispatcher.
- Unknown input has no write and retains the menu/state.
- Wrong-state/message/actor and stale callbacks fail closed; owned stale markup is removed.
- Existing two-step generic scope/action wording remains a compatibility path.
- Persisted invoice edit remains tenant-scoped and returns to its approval state.

## 15. Out Of Scope

New editable fields, contact replacement, adding/removing items, schema/storage changes, PDF layout changes, deployment, and self-learning are out of scope.

## 16. Evidence And Verdict

Evidence: `bot/handlers/invoice.py`, `bot/handlers/voice.py`, `bot/services/semantic_action_resolver.py`, `bot/handlers/decision_callbacks.py`, existing invoice state/voice tests, Sessions 036/037/042/054 in `PROJECT_LOG.md`, and the active LLM/FSM/keyboard contracts.

Verdict: **ready_for_handoff**. Current runtime matches the identified owners; the approved change removes the false mandatory scope hop without changing mutation authority.
