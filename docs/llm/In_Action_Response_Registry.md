# In-Action Response Registry (Audit Repair)

Purpose: evidence-based registry of bounded in-workflow responses and state-scoped clarifications.

## A) Bounded canonical response groups

| Response group | Category | Status | Entry mode | Canonical tokens / values | Source evidence | Notes |
|---|---|---|---|---|---|---|
| `invoice_preview_confirmation` | in-action response group | implemented | mixed (text + voice) | `ano`, `nie`, `unknown` | `process_invoice_preview_confirmation()` resolves with context `invoice_preview_confirmation`; voice routes to this handler from `waiting_confirm`. | Used before invoice persistence/PDF branching. |
| `invoice_postpdf_decision` | in-action response group | implemented | mixed (text + voice) | `schvalit`, `upravit`, `zrusit`, `unknown` | `process_invoice_postpdf_decision()` resolves with context `invoice_postpdf_decision`; voice routes from `waiting_pdf_decision`. | `upravit` currently performs cleanup + informs that edit function is not yet available. |
| `contact_confirm` (semantic intake) | in-action response group | implemented | mixed (text + voice) | `ano`, `nie`, `unknown` | `process_contact_intake_confirm()` resolves with context `contact_confirm`; voice routes from `ContactStates.intake_confirm`. | Used for AI-assisted contact intake path. |

## B) Deterministic (non-LLM) in-action confirmations

| Response group | Category | Status | Entry mode | Allowed values | Source evidence | Notes |
|---|---|---|---|---|---|---|
| `contact_manual_confirm` | in-action response group | implemented | text | `ano`, `nie` | `contact_confirm()` parses lowercased text directly. | Manual contact wizard path. |
| `supplier_onboarding_confirm` | in-action response group | implemented | text | `ano`, `nie` | `onboarding_confirm()` parses lowercased text directly. | Bootstrap/setup flow confirmation. |

## C) Slot clarification and bounded value groups

| Value/slot group | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| Invoice unresolved slot clarification (`service_term`, `customer_name`, `delivery_date`, `due_days`, `quantity`, `unit_price`, `quantity_unit_price_pair`) | in-action response group | implemented | mixed (text + voice) | Invoice FSM clarification handlers and prompts; quantity×price pair uses dedicated bounded resolver `resolve_quantity_unit_price_pair(...)`; voice routes for `waiting_service_clarification` and `waiting_slot_clarification`. | State-bounded only; not global free-form extraction. |
| Contact intake missing field responses (`name`, `ico`, `dic`, `address`, `email`) | in-action response group | implemented | mixed (text + voice, in specific states) | `process_contact_missing_fields()` updates one missing field at a time; voice routes for `ContactStates.intake_missing`. | Validation is deterministic in Python (ICO/DIC/email checks). |

## D) Audit correction focus

The previously reported in-action set did not connect service-alias functionality because `/service` is a separate command flow and does not currently define semantic canonical in-action tokens.
This is expected and should be documented as a manual command flow, not as a missing in-action resolver group.
