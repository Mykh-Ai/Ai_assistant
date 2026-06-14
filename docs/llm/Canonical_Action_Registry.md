# Canonical / Working Action Registry (Audit Repair)

Purpose: evidence-based inventory of currently existing user-facing actions/flows as of 2026-05-06.

## Legend
- **Category**: `top-level user-facing action` | `bootstrap/admin/setup flow`
- **Status**: `implemented` | `reserved` | `partial` | `unclear`
- **Entry mode**: `text` | `command` | `voice` | `mixed`

## A) Top-level user-facing actions

| Action (canonical/working name) | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| `start` (working: `/start`) | top-level/system action | implemented | mixed (command + semantic text/voice) | `/start` command response exists in `cmd_start()`; semantic top-level routing now maps bounded `start` intent to the same existing `/start` flow. | Starts/resumes the approved-user setup/status router. Unknown-user access request remains command/middleware-only through `/start`; voice/text semantic `start` is available only after authorization middleware has allowed the user. |
| `create_invoice` | top-level user-facing action | implemented | mixed (text + command + voice) | `process_invoice_text()` resolves `top_level_action` and continues invoice creation; `/invoice` command starts invoice flow; free-text prereouter enabled when no FSM state. | Voice goes through STT in `handle_voice()` then into `process_invoice_text()` from idle state and from `InvoiceStates.waiting_input` after `/invoice`. |
| `show_existing_invoice` | top-level user-facing action | implemented | mixed (semantic text/voice) | `process_invoice_text()` maps bounded `show_existing_invoice` intent to supplier-scoped invoice lookup and `_send_existing_invoice_view(...)`; tests cover text and voice reachability. | Read-only display of an already created outgoing invoice by number/suffix/reference. It sends summary/PDF when available, clears FSM state, and does not enter edit mode, mutate invoice rows, delete PDFs, or create a new invoice. Nearby actions: `edit_existing_invoice` for editing, `delete_existing_invoice` for deletion. |
| `invoice_period_summary` | top-level user-facing action | implemented | mixed (semantic text/voice) | `process_invoice_text()` maps bounded `invoice_period_summary` intent to Python-owned year-period parsing and `InvoiceService.summarize_invoices_for_supplier_period(...)`; tests cover text, voice, tenant scope, missing DB, and no PDF/storage side effects. | Read-only yearly summary of already saved outgoing invoices for the current supplier scope. It currently supports current year, previous year, or an explicit calendar year such as 2026, groups totals by currency, clears FSM state, and does not create/edit/delete invoices, generate PDFs, summarize receipts/incoming invoices, or provide arbitrary accounting analytics. |
| `edit_existing_invoice` | top-level user-facing action | implemented | mixed (semantic text/voice) | `process_invoice_text()` maps bounded `edit_existing_invoice` intent to supplier-scoped invoice lookup and enters the existing invoice edit FSM; tests cover short-number lookup, ambiguity, supplier scope, missing PDF handling, and voice reachability through top-level routing. | Edits an already persisted outgoing invoice by number/suffix/reference after Python lookup. This is separate from reserved `edit_invoice`, which is the in-action/current-draft edit token. Exact invoice number/reference values remain precision-sensitive; Python resolves and handles ambiguity. |
| `delete_existing_invoice` | top-level user-facing action | implemented | mixed (semantic text/voice entry + confirmation; destructive side effect after confirmation only) | `process_invoice_text()` maps bounded `delete_existing_invoice` intent to supplier-scoped invoice lookup and `InvoiceStates.waiting_delete_existing_invoice_confirm`; confirmation uses shared DecisionResolver context `delete_existing_invoice_confirm`; tests cover ambiguity, yes/no confirmation, deletion, cancellation, and voice state routing. | Deletes one persisted outgoing invoice only after explicit confirmation. This is not create invoice, not edit invoice, and not whole-user database deletion. Voice may start the warning/confirmation flow, but destructive deletion remains Python-owned and confirmation-gated. |
| `add_contact` | top-level user-facing action | implemented | mixed (text + command + voice) | `process_invoice_text()` can route to `start_add_contact_intake()` when resolver returns `add_contact`; `/contact` and `/contact_add` command entry exists; document-caption prereouter for add-contact exists. | Voice top-level supported through STT → `process_invoice_text()`. Contact save/cancel confirmations support voice; missing business-data values are text-first. |
| `show_supplier_profile` (working: `/moj_profil`) | top-level user-facing action | implemented | mixed (command + semantic text/voice) | `cmd_moj_profil()` starts supplier profile creation when missing, or shows the current supplier profile summary when present; semantic top-level routing maps `show_supplier_profile` to the same handler. | User-facing profile/rekvizity action for viewing supplier/company/billing details used on invoices. `/supplier` remains legacy/technical onboarding alias. |
| `edit_supplier` (working: `/upravit_profil`) | top-level user-facing action | implemented | mixed (command + semantic text/voice + voice field choice + text value entry) | `cmd_upravit_profil()` starts a targeted one-field supplier profile edit; semantic top-level routing maps `edit_supplier` to the same handler; `supplier_profile_edit_field()` selects a field; `supplier_profile_edit_confirm()` saves through `SupplierService.update_profile(...)`. | User-facing action for changing supplier/company/billing details used on invoices. Field choice is voice-reachable through Python fast-path + bounded resolver fallback. Exact field values remain text-first. Save/cancel uses shared `yes_no` DecisionResolver context `supplier_profile_edit_confirm`. |
| `add_service_alias` (working: `/sluzbu`, legacy `/service` and `/alias`) | top-level user-facing action | implemented | mixed (text semantic + command + voice top-level; text-only precision steps in-flow) | `/sluzbu`, `/service`, `/alias`, and top-level semantic/voice invoke route to the same supplier handler flow; writes mapping via `ServiceAliasService.create_mapping(...)`. | **Implemented and canonicalized.** Top-level text semantic invoke: yes. Top-level voice invoke: yes (via STT -> top-level resolver). Ambiguous action: yes; compact optional action hints are used. Precision-sensitive fields remain text-only: short alias + full service title. Canonical Slovak-facing wording: `pridaj novú položku`, `pridaj novú službu`; primary command wording is `/sluzbu`. |
| `delete_user_database` (working: `/vymazat_databazu`, voice/text examples such as `Chcem vymazať moju databázu`) | top-level user-facing action | implemented | mixed (command + semantic text/voice entry; typed final confirmation only) | `/vymazat_databazu` command and semantic top-level routing start `DeleteUserDatabaseStates.waiting_exact_confirmation`; `UserDataDeletionService` deletes scoped business DB rows/files and marks access as `deleted_database`. | Entry points only start the warning flow. Final deletion requires exact typed phrase `vymazať databázu`; voice is rejected in the final state before STT. After deletion the user loses access and future `/start` creates a new pending access request. |
| `show_recent_accounting_documents` (working: `/blocek`, legacy `/blocky`) | top-level user-facing action | implemented | mixed (command + deterministic text aliases + semantic voice/text) | Dedicated accounting documents router reads confirmed accounting metadata through `accounting_document_registry`; semantic top-level routing maps `show_recent_accounting_documents` to the same read-only view. | Read-only recent receipts/incoming accounting documents view. It lists only confirmed Document Intake metadata and is not a broad document browser, contract archive, invoice PDF view, temp upload view, search, edit, delete, or Google Drive sync action. |
| `add_receipt` (working: `/add_blocek`, `/dodat_blocek`) | top-level user-facing action | implemented | mixed (command + semantic voice/text) | Existing accounting document intake command handler starts `AccountingDocumentIntakeStates.waiting_upload`; semantic top-level routing maps `add_receipt` to that same upload-waiting FSM. | User-facing entry for adding a new receipt/blocek or incoming invoice. Voice/text intent starts upload waiting only and asks for photo/PDF; it does not create an invoice or save an accounting document from voice content. `/doklad` remains a broader legacy/reserved document-intake entry and is not promoted in `/start`. |
| `send_invoice` | top-level user-facing action | reserved / unsupported runtime capability | semantic token may be recognized only for safe refusal/Product Truth handling | Resolver can recognize `send_invoice`, but no real outbound email/send execution owner exists in current runtime. Current generic fallback behavior is Level 1 only and must not be called support. | Future behavior should answer through Product Truth/InfoHelp: real outbound email sending is unsupported or requires external credentials until runtime integration, setup, tests, and approval exist. Do not expose this as implemented or as a hidden send action. |
| `edit_invoice` | top-level user-facing action | reserved | semantic token may be recognized only for safe refusal or in-action/FSM clarification | `edit_invoice` remains the reserved token for current draft/in-action invoice editing semantics; actual persisted invoice editing is `edit_existing_invoice`. Current generic fallback behavior is Level 1 only and must not be called support. | Do not mark as implemented standalone top-level action unless a real Python owner, entry route, Product Truth entry, InfoHelp answer, tests, and docs exist. Existing invoice edit operations live under in-FSM edit subflows and `edit_existing_invoice`. |

## A.1) Shared idle attachment pre-router

| Capability (working name) | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| `officeflow_idle_attachment_router` | idle attachment pre-router | partial | photo/PDF while FSM state is idle | Shared OfficeFlow attachment router foundation. | This is not a top-level business action like `create_invoice` or `add_contact`. It classifies an idle attachment before Python proposes a bounded next step. Active FSM state wins; the router runs only when no FSM state is active. |

Supported LMM `document_type` classification values:
- `receipt`
- `incoming_invoice`
- `contract`
- `contact_source`
- `unknown`

Important distinction:
- LMM returns only `document_type`, `confidence`, and `reason`.
- `document_type` is not a business action.
- Python maps `document_type` to a proposed workflow step and asks the user before any confirmed save or contact creation.
- No confirmed accounting storage, contact save, contract save, DB mutation, Google Drive sync, or bank matching may happen from classification alone.

## B) Bootstrap/admin/setup flows

| Flow (working name) | Category | Status | Entry mode | Source evidence | Notes |
|---|---|---|---|---|---|
| `supplier_onboarding` (`/moj_profil`, legacy `/supplier`, `/onboarding`) | bootstrap/admin/setup flow | implemented | command + text in-flow | `cmd_moj_profil()` starts onboarding when the profile is missing; `cmd_onboarding()` remains legacy/technical direct onboarding entry and persists via `SupplierService.create_or_replace(...)`. | Final save confirmation uses the shared `yes_no` DecisionResolver context `onboarding_confirm`. |
| `start` (`/start`) | bootstrap/admin/setup flow | implemented | mixed (command + semantic text/voice for authorized users) | `cmd_start()` command response exists; authorization middleware handles unknown users before the start handler; semantic top-level `start` routes to `cmd_start()` after authorization. | Health/intro command for authorized users; unknown users create a minimal pending access request only through `/start` middleware handling. |
| `access_request` (`/start` from unknown user) | bootstrap/admin/setup flow | implemented | command | Authorization middleware writes `access_requests` when an unknown user sends `/start`. | Deterministic Python only; no supplier profile, tenant workspace, invoice/contact/document mutation, STT, LLM, or LMM call. |
| `access_admin` (`/access_requests`, `/approve`, `/reject`, `/block`, `/users`) | bootstrap/admin/setup flow | implemented | command | `bot/handlers/access_admin.py`; admin status comes from `ADMIN_TELEGRAM_USER_IDS` or active `authorized_users` admin/owner role. | Admin-only deterministic Python commands; not semantic actions and not LLM-routed. |

## C) Canonical wording vs noisy input examples

For `add_service_alias`:
- canonical bot-facing wording is Slovak UI wording (e.g. `pridaj novú položku`, `pridaj novú službu`);
- noisy multilingual/misspelled forms are runtime input examples only and must not be treated as canonical wording.

## D) Explicit correction note (for prior audit)

Previous audit was incomplete because it omitted an already implemented manual user-facing flow:
- `add_service_alias` via `/sluzbu` (two-step alias setup; `/service` and `/alias` remain legacy aliases) is implemented and persisted in DB.

This flow is command-driven rather than semantic top-level resolver-driven, so it must be classified as **implemented-manual top-level user action**, not as absent.
