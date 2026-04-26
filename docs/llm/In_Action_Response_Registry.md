# In-Action Response Registry (Audit Repair)

Purpose: evidence-based registry of bounded in-workflow responses and state-scoped clarifications.

## A) Bounded canonical response groups

| Response group | Category | Status | Entry mode | Canonical tokens / values | Source evidence | Notes |
|---|---|---|---|---|---|---|
| `invoice_preview_confirmation` | in-action response group | implemented | mixed (text + voice) | `schvalit`, `upravit`, `zrusit`, `unknown` | `process_invoice_preview_confirmation()` resolves with context `invoice_preview_confirmation`; voice routes to this handler from `waiting_confirm`. | Preview is now draft-review decision. Backward-compatible aliases: `ano` -> `schvalit`, `nie` -> `zrusit`. `upravit` enters draft edit backend without DB/PDF side effects. |
| `invoice_postpdf_decision` | in-action response group | implemented | mixed (text + voice) | `schvalit`, `upravit`, `zrusit`, `unknown` | `process_invoice_postpdf_decision()` resolves with context `invoice_postpdf_decision`; voice routes from `waiting_pdf_decision`. | `upravit` enters bounded edit subflow; full `edit_invoice` operation map is still partial in runtime. |
| `contact_confirm` (semantic intake) | in-action response group | implemented | mixed (text + voice) | `ano`, `nie`, `unknown` | `process_contact_intake_confirm()` resolves with context `contact_confirm`; voice routes from `ContactStates.intake_confirm`. | Used for AI-assisted contact intake path. |
| `edit_invoice:invoice_level` | in-action response group | partial (2 implemented, 1 planned) | mixed entry with bounded clarification | `edit_invoice_number`, `edit_invoice_date`, `edit_invoice_contact`, `unknown` | Product + contract docs map these as invoice-level subflow ops under `edit_invoice`; runtime currently implements `edit_invoice_number` + `edit_invoice_date` (strict Phase 1 `DD.MM.RRRR`). | `edit_invoice` remains top-level reserved token; runtime must execute via bounded subflow only. Integrity-sensitive fields fail safe on ambiguity/conflict. |
| `edit_invoice:item_level` | in-action response group | partial (2 implemented, 3 planned) | mixed entry; precision-sensitive steps are text-first | `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit`, `edit_item_unit_price`, `unknown` | Product + contract docs define full item-level map; runtime currently implements `replace_service` + `edit_item_description` only. | Item targeting required for precision-sensitive item edits. Single-item can default to first item; multi-item requires explicit selection or bounded clarification. |

## B) Deterministic (non-LLM) in-action confirmations

| Response group | Category | Status | Entry mode | Allowed values | Source evidence | Notes |
|---|---|---|---|---|---|---|
| `contact_manual_confirm` | in-action response group | implemented | text | `ano`, `nie` | `contact_confirm()` parses lowercased text directly. | Manual contact wizard path. |
| `supplier_onboarding_confirm` | in-action response group | implemented | text | `ano`, `nie` | `onboarding_confirm()` parses lowercased text directly. | Bootstrap/setup flow confirmation. |

## C) Slot clarification and bounded value groups

| Value/slot group | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| Invoice unresolved slot clarification (`service_term`, `customer_name`, `delivery_date`, `due_days`, `quantity`, `unit_price`, `quantity_unit_price_pair`) | in-action response group | implemented | mixed (text + voice) | Invoice FSM clarification handlers and prompts; quantity×price pair uses dedicated bounded resolver `resolve_quantity_unit_price_pair(...)`; voice routes for `waiting_service_clarification` and `waiting_slot_clarification`. | State-bounded only; not global free-form extraction. |
| `create_invoice` Phase 2 intake shape (`singleton` + optional bounded `items[]`) | in-action response/value contract group | partial (Phase 1 implemented) | mixed intake (text + voice via STT) | Runtime supports backward-compatible dual-shape intake: singleton item fields remain valid; optional `biznis_sk.items[]` (max 3) is accepted as candidate segmentation shape; parser and preview/save paths normalize to internal list shape with bounded clarification/fail-safe behavior. | Implemented Phase 1: bounded multi-item intake + persistence. Legacy single-item path remains compatible. |
| Contact intake missing field responses (`name`, `ico`, `dic`, `address`, `email`) | in-action response group | implemented | mixed (text + voice, in specific states) | `process_contact_missing_fields()` updates one missing field at a time; voice routes for `ContactStates.intake_missing`. | Validation is deterministic in Python (ICO/DIC/email checks). |

## D) Audit correction focus

The previously reported in-action set did not connect service-alias functionality because `/service` is a separate command flow and does not currently define semantic canonical in-action tokens.
This is expected and should be documented as a manual command flow, not as a missing in-action resolver group.

## E) Reserved/partial contract notes for `edit_invoice` map

- `edit_invoice` is a reserved top-level token; runtime behavior is bounded in-action/subflow edits.
- Invoice-level operations are documented separately from item-level operations.
- Invoice-level mapped operations:
  - implemented: `edit_invoice_number`
  - implemented: `edit_invoice_date`
  - planned: `edit_invoice_contact`
- Item-level mapped operations:
  - implemented: `replace_service`, `edit_item_description`
  - planned: `edit_item_quantity`, `edit_item_unit`, `edit_item_unit_price`
- `edit_item_description` mutation semantics remain explicit:
  - `set`
  - `replace`
  - `clear`
- Precision-sensitive item operations require item targeting.
- Single-item invoices may default to first item; multi-item invoices require explicit selection or bounded clarification.
- Destructive/integrity-sensitive edits must fail safe (halt current edit step + bounded clarification), never silent auto-fix.
- Minimal bounded output shape for this response family:
  - `target_item_index`
  - `operation`
  - `value`
- Newly mapped operations listed as planned above are docs-only and not runtime-implemented yet.

## F) Runtime note for `create_invoice` dual-shape intake

- Phase 1 runtime dual-shape support is implemented:
  - singleton remains valid,
  - optional bounded `items[]` (max 3) is supported,
  - Python remains final validator/workflow owner.
- Unclear item boundaries, quantity semantics, service resolution ambiguity, total mismatch, or render-safety overflow must trigger bounded clarification/fallback, not silent acceptance.
