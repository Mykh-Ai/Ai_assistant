# In-Action Response Registry (Audit Repair)

Purpose: evidence-based registry of bounded in-workflow responses and state-scoped clarifications.

## A) Bounded canonical response groups

Design rule:
- New confirmation-like or route-like response groups must be implemented through `bot/services/decision_resolver.py`.
- This registry records canonical outputs, not per-flow synonym lists.
- Handlers must consume canonical outputs only and must not parse raw `ano` / `nie` / `ok` / `schvalit` / `zrusit` / multilingual variants locally.
- If an existing decision family fits, reuse it. If none fits, add a bounded family to the DecisionResolver before adding handler branches.

| Response group | Category | Status | Entry mode | Canonical tokens / values | Source evidence | Notes |
|---|---|---|---|---|---|---|
| `invoice_preview_confirmation` | in-action response group | implemented | mixed (text + voice) | `schvalit`, `upravit`, `zrusit`, `unknown` | `process_invoice_preview_confirmation()` resolves with context `invoice_preview_confirmation`; voice routes to this handler from `waiting_confirm`. | Preview is now draft-review decision. Backward-compatible aliases: `ano` -> `schvalit`, `nie` -> `zrusit`. `upravit` enters draft edit backend without DB/PDF side effects. |
| `invoice_postpdf_decision` | in-action response group | implemented | mixed (text + voice) | `schvalit`, `upravit`, `zrusit`, `unknown` | `process_invoice_postpdf_decision()` resolves with context `invoice_postpdf_decision`; voice routes from `waiting_pdf_decision`. | `upravit` enters bounded edit subflow; full `edit_invoice` operation map is still partial in runtime. |
| `invoice_customer_alias_confirm` | in-action response group | implemented | mixed (text + voice) | `yes`, `no`, `unknown` | `process_invoice_customer_alias_confirm()` resolves with context `invoice_customer_alias_confirm`; voice routes from `waiting_customer_alias_confirm`. | Legacy/explicit alias confirmation path for one close supplier-scoped customer candidate. `yes` stores the cleaned extracted customer candidate as a supplier-scoped confirmed alias for that contact; it must not store the full STT transcript. High-confidence fuzzy or bounded LLM contact resolution may now skip this separate prompt and store the cleaned candidate only after invoice preview approval. `no` returns to customer clarification without saving. |
| `supplier_profile_edit_field` | in-action field selection | implemented | mixed (text + voice) | one supplier-profile field token or `unknown` | `supplier_profile_edit_field()` first uses shared Python field aliases/fast-path, then bounded resolver context `supplier_profile_edit_field`; voice routes from `SupplierProfileEditStates.field` to the same handler. | This selects which field to edit only. The new field value remains text-first in `SupplierProfileEditStates.value`. |
| `supplier_profile_edit_confirm` | in-action response group | implemented | mixed (text + voice) | `yes`, `no`, `unknown` | `supplier_profile_edit_confirm()` resolves with context `supplier_profile_edit_confirm` before saving one targeted supplier-profile field; voice routes from `SupplierProfileEditStates.confirm` to the same handler. | Python validates the field value before confirmation and updates only the selected supplier-profile field after `yes`. Exact field-value entry remains text-first. |
| `contact_confirm` (semantic intake) | in-action response group | implemented | mixed (text + voice) | `ano`, `nie`, `unknown` | `process_contact_intake_confirm()` resolves with context `contact_confirm`; voice routes from `ContactStates.intake_confirm`. | Used for AI-assisted contact intake path. |
| `edit_invoice:invoice_level` | in-action response group | partial (2 implemented, 1 planned) | mixed entry with bounded clarification | `edit_invoice_number`, `edit_invoice_date`, `edit_invoice_contact`, `unknown` | Product + contract docs map these as invoice-level subflow ops under `edit_invoice`; runtime currently implements `edit_invoice_number` + `edit_invoice_date` (strict Phase 1 `DD.MM.RRRR`). | `edit_invoice` remains top-level reserved token; runtime must execute via bounded subflow only. Integrity-sensitive fields fail safe on ambiguity/conflict. |
| `edit_invoice:item_level` | in-action response group | implemented | mixed entry; precision-sensitive steps are text-first | `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`, `unknown` | Product + contract docs define full item-level map; runtime implements service/description and numeric item edit operations with bounded value capture. | Item targeting required for precision-sensitive item edits. Single-item can default to first item; multi-item requires explicit selection or bounded clarification. |
| `idle_attachment_accounting_proposal` | in-action response group | partial | text after idle attachment classification | `yes`, `no`, `unknown` | Shared idle attachment router uses `decision_resolver.resolve_yes_no(...)` before entering accounting document preview processing. | Used only after LMM classified an idle attachment as `receipt` or `incoming_invoice`. `yes` starts candidate extraction/preview; `no` cleans temp staging. |
| `attachment_route_choice` | in-action response group | partial | text after idle contract/contact-source classification | `create_contact`, `save_contract`, `cancel`, `unknown` | Shared idle attachment router resolves contact/contract route choice through the DecisionResolver family. | Slice 1 runtime supports `create_contact` and `cancel`. `save_contract` is reserved and fails explicitly without standalone contract save. |
| `attachment_document_type_choice` | in-action response group | partial | text after unknown idle attachment classification | `receipt`, `incoming_invoice`, `contract`, `contact_source`, `cancel`, `unknown` | Shared idle attachment router uses a bounded clarification family when the classifier returns `unknown`. | This clarification only selects a document type candidate. Python still maps it to a proposal and asks before save/create side effects. |

## B) Deterministic (non-LLM) in-action confirmations

This section documents legacy/manual deterministic confirmations. It is not a template for new work.

No new confirmation-like response group should be added here unless explicitly approved as a deterministic non-semantic exception. New product/runtime flows must default to the Canonical DecisionResolver contract.

| Response group | Category | Status | Entry mode | Allowed values | Source evidence | Notes |
|---|---|---|---|---|---|---|
| `contact_manual_confirm` | in-action response group | implemented | text | `ano`, `nie` | `contact_confirm()` parses lowercased text directly. | Manual contact wizard path. |
| `supplier_onboarding_confirm` | in-action response group | implemented | text | `yes`, `no`, `unknown` | `onboarding_confirm()` resolves with shared `yes_no` DecisionResolver context `onboarding_confirm`. | Bootstrap/setup flow confirmation. |
| `delete_user_database_exact_confirmation` | destructive exact confirmation | implemented | text only | exact phrase `vymazať databázu` | `DeleteUserDatabaseStates.waiting_exact_confirmation`; `confirm_delete_user_database()` calls `UserDataDeletionService` only after exact typed match. | Explicit exception: no yes/no resolver and no voice confirmation. Voice in this state is rejected before STT and top-level routing. |

## C) Slot clarification and bounded value groups

| Value/slot group | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| Invoice unresolved slot clarification (`service_term`, `customer_name`, `delivery_date`, `due_days`, `quantity`, `unit_price`, `quantity_unit_price_pair`) | in-action response group | implemented | mixed (text + voice) | Invoice FSM clarification handlers and prompts; quantity×price pair uses dedicated bounded resolver `resolve_quantity_unit_price_pair(...)`; voice routes for `waiting_service_clarification` and `waiting_slot_clarification`. | State-bounded only; not global free-form extraction. |
| `create_invoice` Phase 2 intake shape (`singleton` + optional bounded `items[]`) | in-action response/value contract group | partial (Phase 1 implemented) | mixed intake (text + voice via STT) | Runtime supports backward-compatible dual-shape intake: singleton item fields remain valid; optional `biznis_sk.items[]` (max 3) is accepted as candidate segmentation shape; parser and preview/save paths normalize to internal list shape with bounded clarification/fail-safe behavior. Voice routes both from idle top-level input and from `InvoiceStates.waiting_input` after `/invoice`. | Implemented Phase 1: bounded multi-item intake + persistence. Legacy single-item path remains compatible. |
| Contact intake missing field responses (`name`, `ico`, `dic`, `address`, `email`) | in-action value capture group | implemented | text-first | `process_contact_missing_fields()` updates one missing field at a time from text input; voice in `ContactStates.intake_missing` asks for text and does not route to top-level actions. | Missing contact data is business data entry, not a command selection step. Validation is deterministic in Python (ICO/DIC/email/address checks). |
| Generic exact-value text fallback | in-action safety fallback | implemented | voice fallback only | none | `handle_voice()` refuses unhandled active FSM states with a Slovak text-required prompt instead of falling through to top-level routing. | Prevents voice from clearing or overriding active typed-value states. Business-specific phrase routing remains outside `voice.py`. |

## D) Audit correction focus

The previously reported in-action set did not connect service-alias functionality because `/service` was a separate command flow and did not define semantic canonical in-action tokens.
This is expected and should be documented as a manual command flow, not as a missing in-action resolver group.

## E) Reserved/partial contract notes for `edit_invoice` map

- `edit_invoice` is a reserved top-level token; runtime behavior is bounded in-action/subflow edits.
- `edit_existing_invoice` is explicit top-level action for persisted invoice edit by number reference; DB lookup and supplier scoping are Python-only.
- Invoice-level operations are documented separately from item-level operations.
- Invoice-level mapped operations:
  - implemented: `edit_invoice_number`
  - implemented: `edit_invoice_date`
  - planned: `edit_invoice_contact`
- Item-level mapped operations:
  - implemented: `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`
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
- Numeric item operations are runtime-implemented with deterministic validation/recalculation in Python.

## F) Runtime note for `create_invoice` dual-shape intake

- Phase 1 runtime dual-shape support is implemented:
  - singleton remains valid,
  - optional bounded `items[]` (max 3) is supported,
  - Python remains final validator/workflow owner.
- Unclear item boundaries, quantity semantics, service resolution ambiguity, total mismatch, or render-safety overflow must trigger bounded clarification/fallback, not silent acceptance.
- For explicit persisted invoice delete commands (SK/EN/UK/RU), canonical top-level action is `delete_existing_invoice`; runtime delete remains Python-guarded with explicit confirmation.

