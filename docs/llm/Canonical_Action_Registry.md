# Canonical / Working Action Registry (Audit Repair)

Purpose: evidence-based inventory of currently existing user-facing actions/flows as of 2026-04-13.

## Legend
- **Category**: `top-level user-facing action` | `bootstrap/admin/setup flow`
- **Status**: `implemented` | `reserved` | `partial` | `unclear`
- **Entry mode**: `text` | `command` | `voice` | `mixed`

## A) Top-level user-facing actions

| Action (canonical/working name) | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| `create_invoice` | top-level user-facing action | implemented | mixed (text + command + voice) | `process_invoice_text()` resolves `top_level_action` and continues invoice creation; `/invoice` command starts invoice flow; free-text prereouter enabled when no FSM state. | Voice goes through STT in `handle_voice()` then into `process_invoice_text()` when not in state-specific branch. |
| `add_contact` | top-level user-facing action | implemented | mixed (text + command + voice) | `process_invoice_text()` can route to `start_add_contact_intake()` when resolver returns `add_contact`; `/contact` and `/contact_add` command entry exists; document-caption prereouter for add-contact exists. | Voice top-level supported through STT → `process_invoice_text()`; additional voice support exists in in-flow contact states (`intake_missing`, `intake_confirm`). |
| `add_service_alias` (working: `/service`) | top-level user-facing action | implemented | mixed (text semantic + command + voice top-level; text-only precision steps in-flow) | `/service` command and top-level semantic/voice invoke route to the same supplier handler flow; writes mapping via `ServiceAliasService.create_mapping(...)`. | **Implemented and canonicalized.** Top-level text semantic invoke: yes. Top-level voice invoke: yes (via STT -> top-level resolver). Ambiguous action: yes; compact optional action hints are used. Precision-sensitive fields remain text-only: short alias + full service title. Canonical Slovak-facing wording: `pridaj novú položku`, `pridaj novú službu`. |
| `send_invoice` | top-level user-facing action | reserved | text/voice token recognized, runtime fallback | Included in allowed top-level resolver actions and fallback tokenization; in runtime branch `process_invoice_text()` maps it to generic “Nerozumiem...” and clears state. | Resolver-recognized placeholder only; no standalone execution flow yet. |
| `edit_invoice` | top-level user-facing action | reserved | text/voice token recognized, runtime fallback | Included in allowed top-level resolver actions and fallback tokenization; runtime currently returns generic “Nerozumiem...” and clears state. | Resolver-recognized placeholder only; no standalone execution flow yet. |

## B) Bootstrap/admin/setup flows

| Flow (working name) | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| `supplier_onboarding` (`/supplier`, `/onboarding`) | bootstrap/admin/setup flow | implemented | command + text in-flow | Command handler `cmd_onboarding()` starts 12-step supplier profile flow and persists via `SupplierService.create_or_replace(...)`. | Includes bounded final confirm (`ano/nie`) but parsed deterministically in Python (no semantic resolver here). |
| `start` (`/start`) | bootstrap/admin/setup flow | implemented | command | `cmd_start()` command response exists. | Health/intro command, not business action. |

## C) Canonical wording vs noisy input examples

For `add_service_alias`:
- canonical bot-facing wording is Slovak UI wording (e.g. `pridaj novú položku`, `pridaj novú službu`);
- noisy multilingual/misspelled forms are runtime input examples only and must not be treated as canonical wording.

## D) Explicit correction note (for prior audit)

Previous audit was incomplete because it omitted an already implemented manual user-facing flow:
- `add_service_alias` via `/service` (two-step alias setup) is implemented and persisted in DB.

This flow is command-driven rather than semantic top-level resolver-driven, so it must be classified as **implemented-manual top-level user action**, not as absent.
