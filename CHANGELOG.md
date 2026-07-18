# Changelog

- Fixed owner OAuth Google Drive setup commands to read and disconnect the shared configured owner connection instead of a legacy Telegram-derived connection key; re-auth status no longer claims the interactive connect command is always available.
- Improved official RPO contact search with deterministic exact-name collapse, bounded typo/spacing suggestions that always require selection, and weak internal-substring rejection. Added disabled-by-default Financial Administration tax-enrichment configuration, a fail-closed async provider/aggregation boundary, no-network fake coverage, and exact key-authenticated production mappings for `ds_dsrdp`/`ds_dphs`; deployment and feature activation remain separately gated.

## Unreleased
- Added and deployed immutable workspace-specific Google Drive targets for newly confirmed receipts and incoming invoices, shared deterministic path validation, fail-closed enqueue behavior, and a redacted read-only deployment blocker audit for active legacy jobs; existing owner OAuth, worker, invoice-PDF behavior, retention, and historical remote files remain unchanged. Production audit and row-count preservation passed; the owner connection has since been reauthorized, while real two-profile upload smoke remains pending.
- Fixed access approval for one unambiguous migration-created inactive owner membership: approval now atomically validates supplier/workspace ownership, reactivates the membership, restores active selection, creates no business profile data, and rolls back fully on multiple or contradictory ownership. Configured admins may use argument-free `/approve` for safe self-targeting without exposing their Telegram ID.
- Fixed generic multi-workspace audit/dry-run readiness so public_profile_switch_ready is derived from required workspace columns, complete ownership backfill, zero migration blockers, and valid workspace/membership/selection foundation state. Already migrated databases now report database_already_migrated instead of a false ownership blocker.
- Added production-safe legacy multi-workspace migration tooling with redacted read-only planning, deterministic ownership mapping, logical fingerprint pinning, exclusive-lock refusal, verified SQLite and content-hashed storage backup, separately audited target construction, atomic apply, manifest-bound rollback, emergency restore, CLI modes, and fixture coverage. The production migration and exact-SHA deploy completed on 2026-07-13; the verified host rollback backup remains retained.
- Completed and deployed the target-schema multi-workspace runtime across profiles, contacts/service aliases, invoices/numbering/PDF/follow-up/analytics, accounting document intake/categories/storage/archive/analytics, work-time/settings/reports, and account-level deletion. Added `/profily`, canonical `switch_business_profile`, additional-profile onboarding, active-FSM switch blocking, voice confirmation, active-profile `/start`/`menu` context, Product Truth/InfoHelp, and isolation tests. Same-user two-profile Telegram acceptance remains pending.
- Added bounded LLM period slots for OfficeFlow work-time report generation so phrases such as `покажи табель рабочего времени за May` can route to the selected month while Python only validates/defaults missing year or month using the Bratislava business date.
- Moved OfficeFlow work-time report timesheet wording from Python fast-path variants into bounded LLM `positive_examples` for `generate_work_time_report`, keeping examples contextual rather than a whitelist.
- Fixed OfficeFlow work-time report routing so Ukrainian timesheet wording such as `Покажи мені табель працівного часу.` resolves to `generate_work_time_report` instead of `unknown`.
- Added a shared active-FSM navigation/stale-state guard for text and voice transcripts, plus stale callback protection for shared decision buttons and invoice follow-up buttons; fresh active-FSM safe switch confirmation remains deferred until FSM restore can be proven by tests.
- Fixed OfficeFlow work-time close recovery after ambiguous close commands such as zakry den 16.07: the bot now stays in close-time input state and accepts a plain HH:MM reply such as 16:07 instead of falling back to idle top-level routing.
- Strengthened top-level routing hints for OfficeFlow work-time deletion so mixed text such as `vidali dochadzku` routes to `delete_work_time_month` instead of invoice deletion, while invoice-specific delete requests still route to `delete_existing_invoice`.
- Changed OfficeFlow work-time Telegram preview/saved/month summaries from decimal-hour labels such as `8,4 hod.` to `h:mm` labels such as `8:24`, keeping stored minutes and lunch math unchanged.
- Changed OfficeFlow work-time monthly Excel report duration cells from decimal-hour text to Excel duration values formatted as `[h]:mm`, with header `Hodiny (h:mm)` and totals that can exceed 24 hours.
- Fixed OfficeFlow work-time runtime clock to use `OFFICEFLOW_TIMEZONE` with default `Europe/Bratislava` for open/close-now, today/yesterday, default report month, and bounded slot `today_iso`; invalid timezone values log a warning and fall back to Bratislava instead of silently using UTC.
- Fixed OfficeFlow work-time close-now safety: unclear close input no longer closes an open day, bounded slot extraction now requires explicit mode values, range endpoints beat duration-only interpretation, and strict parser fallback remains limited to numeric HH:MM/HH.MM ranges.
- Moved OfficeFlow work-time manual/close slot extraction to bounded LLM-first normalization for natural multilingual text such as explicit dates, verbal time ranges, and duration-only entries; Python still validates, previews, confirms, and saves, with parser fallback only for non-LLM/dev paths.
- Polished OfficeFlow work-time manual/close preview recovery: edit now re-renders previews safely, unknown preview replies repeat full context with buttons, active voice/text preview states no longer fall through to report routing, duration-only rows have clearer wording, and UTF-8 yesterday variants are parsed without changing lunch net/gross math.
- Added partial OfficeFlow work-time / dochadzka MVP with top-level actions `open_work_day`, `close_work_day`, `add_work_time_entry`, `generate_work_time_report`, `update_work_time_lunch_break`, and `delete_work_time_month`, additive user-scoped SQLite tables/settings, preview-confirmed time/lunch/delete writes, shared DecisionResolver route choices, Product Truth/InfoHelp coverage, monthly Excel report generation with net hours after configured lunch deduction, and confirmed deletion of selected-month DB records. Payroll, legal HR compliance, multi-employee attendance, export, and automatic time detection remain unsupported.

### Added
- Owner OAuth Google Drive archive MVP: manual/local owner authorization bootstrap, encrypted refresh-token storage, lazy owner OAuth Drive provider, confirmed receipt/incoming-invoice uploads, and invoice-PDF enqueue after mark-paid/control events.
- Environment placeholders for `GOOGLE_DRIVE_ENABLED`, `GOOGLE_DRIVE_MODE=owner_oauth`, owner OAuth credentials, root folder id/name, owner workspace id, retention flags, and worker interval/batch size.
- Product Truth, InfoHelp, docs, and no-network tests for partial Google Drive archive support.

### Changed
- Contact intake prompts now include a `/menu` escape hint, and contact FSM sessions expire after five minutes of inactivity before processing the next contact-state input.
- Google Drive invoice storage/archive Product Truth is now `partial` owner OAuth with setup/admin/external-credential requirements, not unsupported and not fully supported.
- Mark-paid invoice flow falls back to the old local Drive stub when Drive is disabled, and enqueues a Drive archive job only when owner-run Drive mode is enabled and the PDF exists.
- Service-account mode is marked unsupported for personal My Drive unless Google Workspace/Shared Drive is explicitly configured later.

### Notes
- This is single-owner OAuth only, not per-client OAuth or SaaS Drive sync.
- Local invoice PDFs are not deleted in this MVP.
- Receipt/incoming originals are deleted only after upload success plus DB state `uploaded`; metadata JSON is kept.
- Manual Google Drive smoke is allowed only with real owner credentials.

# CHANGELOG

## [Unreleased]
- Fixed canonical multi-workspace dry-run ownership validation for already migrated actors with multiple supplier profiles: persisted workspace ownership is now authoritative, while unknown workspaces and cross-workspace relations remain deployment blockers.

- Added and deployed a disabled-by-default, workspace-pilot-gated official Slovak RPO lookup strategy inside the existing add_contact flow, including bounded candidate callbacks, typed missing DIČ and optional contact email/IBAN/person, additive nullable contact.iban migration, conflict-safe transactional merge, manual/PDF fallback, Product Truth/InfoHelp guidance, fake-only acceptance coverage, and a bounded live RPO provider smoke. Production code/schema are live; registry lookup remains disabled until explicit pilot workspace configuration.

### Added
- `mark_existing_invoice_paid` top-level text/voice action for manually marking one saved outgoing invoice as paid/uhradena after supplier-scoped lookup and confirmation buttons, storing only bot-local payment state.
- `accounting_document_analytics` top-level read-only runtime pilot for natural
  text/voice questions over confirmed receipts/bloceky and incoming
  invoices/prijate faktury, with workspace-scoped sanitized metadata dataframe
  reads, legacy uncategorized metadata compatibility, current-date injection,
  process-isolated validated analysis code execution, and Product Truth/InfoHelp
  status as partial rather than full accounting analytics.

- `invoice_analytics` top-level read-only runtime pilot for natural text/voice
  questions over saved outgoing invoices, with supplier-scoped sanitized
  dataframe reads, normalized bot payment-status fields, current-date
  injection, process-isolated validated analysis code execution, and Product
  Truth/InfoHelp status as partial rather than full accounting analytics.
- automatic Phase 1 overdue invoice follow-up flow:
  in-process aiogram scheduler with default daily check, tenant-scoped overdue
  invoice detection, Telegram reminder cards, persisted mark-paid/remind-later
  /mute state, and an honest Google Drive archive stub after marking a
  reminder invoice as paid.
- `invoice_period_summary` top-level read-only action for natural text/voice
  questions about saved outgoing invoice count and totals for a supported
  calendar-year period, scoped to the authorized supplier account.
- deterministic Phase 1 top-level `info_help` fallback guidance for idle text/voice inputs when the semantic action resolver returns `unknown`.
- `show_existing_invoice` top-level read-only action: natural text/voice such as “show/open invoice/faktura 04” now shows the existing outgoing invoice summary/PDF and returns to idle instead of entering edit mode.
- global state cancellation through `/cancel` and shared DecisionResolver-backed text/voice cancel wording (`zrušiť`, `скасувати`, `відмінити`, `отменить`, “почни з початку”), with state-aware cleanup for temporary intake and safe persisted-invoice-edit exit.
- `delete_user_database` runtime flow: `/vymazat_databazu` and bounded top-level text/voice intent now start a destructive warning FSM, with exact typed final confirmation required before scoped deletion.
- voice/text reachability for existing canonical top-level/system actions `start`, `show_supplier_profile`, `edit_supplier`, `show_recent_accounting_documents`, and `add_receipt` through the shared Semantic Action Resolver and existing Python route handlers.
- Decision UI Layer Phase 1 for stable confirmation flows: reusable Telegram inline decision keyboards, canonical `decision:*` callback tokens, and a shared callback dispatcher for invoice preview, invoice alias confirmation, invoice delete confirmation, contact confirmations, supplier onboarding, and supplier profile edit confirmation.
- authorization middleware coverage for Telegram `CallbackQuery` updates so unknown or blocked users cannot trigger decision callback side effects.
- deterministic admin text aliases for `/users` (`користувачі`) and `/access_requests` (`запит`, `запрос`) without LLM routing.
- controlled access-request onboarding for unknown Telegram users: `/start` records a pending request only, admins can review with `/access_requests`, and admins can approve/reject/block users with deterministic admin commands.
- `ADMIN_TELEGRAM_USER_IDS` config for bootstrap administrators plus persistent `access_requests` and `authorized_users` tables.
- `ALLOWED_TELEGRAM_USER_IDS` config and centralized Telegram user authorization middleware for the controlled two-user dry run.
- docs-only Canonical DecisionResolver policy for confirmation-like replies across invoice, contact, onboarding, delete confirmation, and future Document Intake flows.
- shared runtime `bot/services/decision_resolver.py` adapter for canonical `approve_edit_cancel` and `yes_no` decision families.
- accounting Document Intake Phase 1 foundation for receipts and incoming invoices:
  - pure candidate models, validation, deterministic storage helpers, classifier/extraction parsers, and isolated LMM wrapper;
  - explicit `/doklad`, `/expense`, and `/intake` FSM flow for state-scoped photo/PDF uploads, Slovak preview, shared decision resolution, and confirmed JSON-sidecar storage.
- shared OfficeFlow idle attachment router foundation:
  - neutral temp staging under `storage/uploads/attachment_intake/`;
  - bounded LMM document-type classifier for `receipt`, `incoming_invoice`, `contract`, `contact_source`, and `unknown`;
  - idle-only `StateFilter(None)` router above accounting/contact intake;
  - bounded accounting/contact-route proposals before any save/create side effects.
- DecisionResolver families for idle attachment route and document-type clarification.
- `/blocky` read-only recent accounting documents view for the last 5 confirmed receipts/incoming invoices from confirmed metadata only.
- controlled receipt/incoming-invoice category MVP inside the existing accounting Document Intake preview flow:
  - system and workspace-scoped category registry with allowed-category payloads;
  - LMM candidate-only document and line-item category suggestions bounded by Python-provided categories or `unknown_review`;
  - unknown-category UX for choosing existing, confirmation-gated workspace category creation, save-as-unknown, or cancel;
  - confirmed metadata category snapshots with no DB/schema migration or file moves;
  - reply-button UX for category preview choices, unknown-category recovery, duplicate/new-category yes-no confirmations, similar-category decisions, and reasonable category selection lists.

### Changed
- Accounting document analytics now supplies Python-owned `allowed_categories` and
  `category_filter_hints` to the planner, and rejects category plans that do not
  use the hinted `category_id`, preventing invented translated category-label
  filters such as `pohonné látky` when confirmed metadata uses `vehicle_fuel` /
  `Palivo`.
- `invoice_period_summary` is no longer offered as a competing top-level
  user-facing resolver action. Simple calendar-year invoice count/total
  questions now route through `invoice_analytics`, which may use the existing
  deterministic yearly summary as an internal read-only fast path.
- Invoice analytics now redirects receipt/expense/incoming-invoice analytics to `accounting_document_analytics` and still guards bank/cashflow
  /VAT/tax wording before calculation and refuses to answer those domains from
  outgoing invoice data. Safe unsupported business analytics requests enter the
  existing confirmation-gated customization/admin-review preview flow instead
  of implying a request was created from plain text.
- Product Truth, InfoHelp, README, and technical docs now distinguish partial
  read-only invoice analytics from partial accounting-document/receipt analytics and
  unsupported bank/cashflow/VAT/tax/full accounting analytics; this is a truth
  sync, not a new analytics runtime.
- `invoice_analytics` final LLM-written answers now use Python-controlled
  Slovak business language by default instead of mirroring the user's input
  language; a reusable Safe Data Analyst Runtime checklist documents the
  read-only analytics sandbox, status-semantics, timeout, normalization, and
  language-policy rules for future analytics domains.
- Top-level unknown InfoHelp guidance now explicitly mentions that the bot can
  count saved outgoing invoices for a calendar-year summary.
- InfoHelp/Product Truth handling now distinguishes supported read-only yearly
  invoice summaries from broader unsupported analytics/reporting requests;
  Product Truth rendering also falls back to registry payload fields when
  localized Slovak copy is missing, avoiding generic `Táto schopnosť:
  podporované` output.
- invoice edit invalid-date and invalid numeric item-value fallbacks now include field-specific examples while preserving the existing `zrušiť` recovery hint.
- accounting Document Intake and OfficeFlow attachment-routing invalid-input fallbacks now include Slovak cancel recovery hints for temp-staged flows without changing storage, cleanup, or classification behavior.
- business/contact/service/invoice exact-value FSM invalid-input fallbacks now include Slovak cancel recovery hints without changing successful paths or side effects.
- destructive delete fallbacks now include Slovak safe-exit recovery hints without mentioning `/start`, and onboarding invalid-value fallbacks now explain `zrušiť` plus `/start` restart recovery.
- exact global cancel text shortcuts now bypass the LLM resolver and run shared Python state cancellation directly; voice transcripts that exactly match global cancel shortcuts do the same after STT.
- invoice edit FSM menu fallbacks now include Slovak recovery hints for `zrušiť` and `/start`, while still keeping active FSM state from falling through to top-level action routing.
- `/menu` now shows the broader user-facing capability list, including create/show/edit/delete existing invoice flows, without exposing internal canonical tokens as slash commands.
- after `/upravit_profil` save, the bot now returns the same staged/main navigation as `/start`; ready users see invoice/view/document options instead of the first-service onboarding prompt.
- `/start`, `/menu`, `/moj_profil` profile display, and `/blocek` now behave as stateless interruptions by clearing active FSM state where applicable.
- invoice draft extraction now preserves optional raw/source customer and service mention fields from original text/STT; safe customer raw mentions can become confirmed contact aliases after approved preview, and safe service raw mentions can become confirmed semantic service aliases pointing to existing manual `/sluzbu` mappings after approved preview.
- documentation now treats FakturaBot / OfficeFlow as the current Phase 2 voice-capable runtime: `README.md` exposes the top-level/action tree, and `AGENTS.md` plus `docs/llm/New_Action_Design_Checklist.md` define that a new top-level action is implemented only after text/command, resolver, Python route, tests, and voice reachability or an explicit voice exclusion are covered.
- in-FSM voice handling now distinguishes control selection from exact value entry: `/invoice` waiting input and supplier profile field selection are voice-reachable, while contact missing-field values and invoice-number edit values ask for typed text.
- STT transcription now sends a compact multilingual FakturaBot / OfficeFlow context prompt so voice input is biased toward Slovak/Ukrainian/Russian/English mixed business speech without turning STT into a command router.
- top-level Semantic Action Resolver prompt/context now requires SK/UK/RU/mixed user input to be interpreted into Slovak FakturaBot product semantics before choosing an allowed action; supplier profile hints describe company/billing profile semantics rather than command aliases.
- users who complete `delete_user_database` now lose active access and remain visible to admins as `authorized_users.status=deleted_database`; future `/start` creates a fresh pending access request, and `/approve` reactivates the user with a clean business database.
- voice handling now refuses unhandled active FSM states with a Slovak text-required prompt instead of falling through to top-level routing and potentially clearing or overriding state.
- Canonical DecisionResolver now handles known spoken `áno` STT artifacts (`Ah, não`, `Ah no`, `Ah ňao`, `Ахняо`) in the shared resolver layer before LLM fallback, without treating standalone `no` variants as affirmative.
- text/voice confirmation replies continue through the Canonical DecisionResolver, while inline decision buttons now converge into the same state-aware execution paths by passing pre-canonicalized tokens without LLM/STT/LMM calls.
- authorization now accepts either bootstrap `ALLOWED_TELEGRAM_USER_IDS` membership or an active `authorized_users` row; blocked users are denied before normal handlers run.
- invoice numbering and uniqueness are now tenant-aware by `supplier_telegram_id`; invoice PDFs now use tenant-scoped paths under `storage/invoices/{supplier_telegram_id}/`.
- accounting document temp storage, confirmed storage, duplicate detection, and recent-document views are now scoped to the requesting Telegram user workspace.
- supplier onboarding no longer collects per-user SMTP host/user/password and saves those legacy fields as `NULL`/`None`.
- invoice preview/post-PDF decisions, contact confirmations, onboarding confirmation, and existing-invoice delete confirmation now route through the shared DecisionResolver.
- voice confirm-state transcripts now route to the active confirmation handler instead of falling through to top-level invoice routing.
- accounting Document Intake now passes real Telegram photo/PDF bytes into the LMM boundary as image/PDF payloads, with temp staging cleanup for cancel/error/confirmed-save paths.
- accounting Document Intake exposes a staged-file processing entrypoint so the idle router can continue into the existing accounting preview/confirmation flow without changing invoice storage or DB schema.
- idle attachment accounting proposal confirmation now uses the shared `yes_no` decision family without a flow-specific yes/no fallback.
- OfficeFlow idle attachment voice confirmations now route STT text back into the OfficeFlow continuation handlers instead of falling through to top-level invoice routing.
- accounting document preview voice confirmations now route through the same Canonical DecisionResolver path as text, with safe edit-unavailable handling.
- docs-only OfficeFlow architecture framing now reflects Document Intake Phase 1 runtime storage and explicitly preserves outgoing invoice `storage/invoices` + `pdf_path` behavior.
- docs-only OfficeFlow storage proposal now records future Google Drive sync path rules: storage-relative confirmed accounting paths are canonical, while temp uploads and host-only paths are not.
- accounting Document Intake now keeps raw `purchase_subject` / `Predmet nákupu` as factual purchase description while separately handling controlled category candidates and confirmed category snapshots.
- temporary OfficeFlow/accounting intake sessions now expire after 5 minutes and safely clean only upload staging paths.
- accounting Document Intake now warns about deterministic metadata duplicates before preview while still requiring explicit preview approval before save.
- confirmed accounting document saves now show clean Slovak next steps (`/add_blocek`, `/blocek`, `/menu`) instead of exposing the internal metadata path to ordinary users.
- accounting Document Intake duplicate warnings now use loud `POZOR! Tento doklad už je uložený!!!!` wording with explicit `Pridať iný bloček` / `Uložiť aj tak` / `/menu` buttons instead of looking like the ordinary yes/no path.
- idle photo/PDF receipt proposals now show explicit `Áno` / `Nie` reply buttons before entering accounting document preview processing.

- existing-category selection during receipt categorization now ends with create-new/back controls so users can recover when no listed category fits.

### Fixed
- Invoice analytics now treats unpaid/not-paid outgoing invoice questions as both `pending_payment` and `overdue`, including muted reminders that are still not marked paid; the planner receives Python-owned payment-status filter hints and rejects plans that drop `overdue`.
- Analytics action-boundary smoke coverage now guards `invoice_analytics`,
  `accounting_document_analytics`, add/show receipt routes, InfoHelp capability
  questions, and unsupported bank/DPH/tax/export wording so those requests do
  not reach the wrong planner.- Ukrainian current-year invoice summary wording such as `цього року` now
  resolves through bounded period-value canonicalization to the yearly invoice
  summary instead of the generic supported-year guidance message.
- Invoice draft creation now honors an explicitly stated issue date (`Dátum
  vystavenia`, including voice-like Cyrillic forms such as `датом
  вытворения`) before validating delivery-date windows and computing due date.
  This fixes the case where `14 лютого` delivery was rejected against today's
  date even though the user also said the invoice issue date was `17 лютого`.
- Singleton invoice item parsing now fills missing item-level quantity, unit,
  and unit price from validated top-level draft values. This fixes the case
  where logs showed `unit_price` recognized at draft level while
  `items[0].unit_price` stayed empty and the bot kept asking for the price.

### Notes
- Real Google Drive invoice archive/upload after due-date follow-up remains
  unsupported. The Phase 1 stub records only local state, does not call Google
  APIs, does not create Drive folders, does not upload files, and does not
  delete local invoice PDFs.
- Tenant-scope rollout exposed a migration/repair gap for existing server data: confirmed accounting documents can exist under the legacy `mykhailo-szco` workspace while `/blocek` reads the requesting tenant workspace, and some historical invoice `pdf_path` values can point to local Windows paths. Data repair must use audit, backup, dry-run, and explicit apply approval rather than cross-tenant fallback reads.
- Controlled multi-user dry run remains one backend, one bot token, and one SQLite DB; access is limited to bootstrap allowlisted or admin-approved Telegram users, and this is not full SaaS multi-tenancy.
- Public automatic signup remains out of scope; unknown users can only request access and must be approved by an admin before onboarding, LLM/STT/LMM, invoices, contacts, or document intake.
- Legacy supplier SMTP values should be purged after backup with `UPDATE supplier SET smtp_host = NULL, smtp_user = NULL, smtp_pass = NULL;`.
- Document Intake remains incremental: no bank matching, Telegram button callbacks, Google Drive sync, Zevs runtime profile, standalone contract save, bank-statement matching, tax advice, accounting export, or full accounting analytics. Narrow receipt/incoming-invoice analytics is handled only by the separate partial read-only `accounting_document_analytics` runtime.

## [0.6.1] - 2026-04-12

### Changed
- invoice flow generalized from service-slot-only clarification to broader slot-level clarification (customer, delivery date, due days, quantity/unit price)
- partial draft retention is now enforced as a project-level structured workflow principle (not invoice-only)

## [0.6.0] - 2026-04-12

### Changed
- AI orchestration contract updated to **Bounded Semantic Canonicalization** via **Semantic Action Resolver**
- architecture moved away from narrow “LLM drafts payload + deterministic token routing” toward unified canonical action/value resolution
- Python explicitly remains the only execution authority (validation, state checks, side effects)

## [0.5.0] - 2026-04-03

### Added
- internal spec-driven PAY by square encoder service (`bot/services/pay_by_square.py`) for invoice `paymentorder` payload generation
- strict payload validation for IBAN, currency, amount, variable symbol, due date and beneficiary name
- unit tests for deterministic payload generation, validation failures, and PDF integration smoke

### Changed
- PDF generator now uses real PAY by square payload encoding instead of temporary text placeholder
- README/TZ/PROJECT_LOG updated to reflect real QR payload integration and current manual scan verification status

### Notes
- one real local banking-app PAY by square scan has since been recorded as passed for the currently tested FakturaBot flow
- broader banking-app compatibility still requires additional manual confirmation outside CI/runtime environment

## [0.4.0] - 2026-04-03

### Added
- Phase 4 invoice persistence: new `invoice` and `invoice_item` bootstrap schema with fail-loud compatibility checks
- `InvoiceService` with sequential invoice numbering format `RRRRNNNN`, save/get operations, and `pdf_path` assignment
- `/invoice` text flow: draft parse, local contact resolution, preview, confirm (`ano`/`nie`), save, PDF generation, and PDF preview
- shared voice-to-invoice integration so STT output can continue through the same Phase 4 invoice flow
- PDF generation service (ReportLab + initial QR block scaffold) with one-page business layout and Slovak labels

### Changed
- invoice draft prompt/schema now expects `delivery_date` (user-mentioned date) and not `issue_date` from LLM
- due date is computed in code from issue date plus due days

### Not in scope
- email sending
- external contact lookup
- contract extraction
- fuzzy contact matching
- multi-item UI/edit workflow
- production-ready Pay by Square payload compatibility (completed in 0.5.0)

## [0.2.0] - 2026-03-31

### Added
- supplier onboarding flow (`/supplier`, `/onboarding`) with sequential chat questions, summary and confirm step
- supplier persistence layer with SQLite upsert/get operations by `telegram_id`
- supplier validation for IČO, DIČ, optional IČ DPH, email, IBAN, and `days_due`

### Changed
- onboarding phase introduced after Phase 1 voice-to-draft preview

## [0.1.0] - 2026-03-30

### Added
- стартова документаційна структура репозиторію
- README
- AGENTS
- PROJECT_LOG
- базове ТЗ FakturaBot

### Changed
- концепція проєкту зміщена з ідеї масового SaaS у бік демонстраційного продукту та кастомного розгортання

### Decided
- голос є обов’язковою частиною MVP
- email-відправка входить у MVP
- QR Pay by Square входить у MVP
- lookup з інтернету не входить у v1.0
- контрагент з договору додається через AI + validation + confirmation

## [0.2.0] - 2026-03-31

### Added
- voice handler for Telegram voice messages
- speech-to-text service using OpenAI Audio API
- LLM invoice draft parser service
- invoice draft extraction prompt
- config support for `OPENAI_STT_MODEL` and `OPENAI_LLM_MODEL`

### Changed
- Phase 1 redefined from simple voice-to-text smoke test to voice-to-draft preview flow
- bot polling startup updated to pass config into runtime handlers

### Fixed
- preview formatting for quantity/unit and amount/currency no longer shows `— —`
- empty STT result no longer goes into LLM parsing
## [0.3.0] - 2026-04-01

### Added
- contact persistence in SQLite (`contact` table bootstrap with schema compatibility checks)
- manual contact onboarding flow via `/contact` and `/contact_add`
- contact validation and summary/confirm (`yes`/`no`) step before save

### Changed
- contact save path now stores per-supplier records (`supplier_telegram_id`) with exact-name upsert behavior
- follow-up: supplier onboarding confirm flow now uses Slovak `ano`/`nie` instead of `yes`/`no`
- follow-up: manual contact confirm flow now uses Slovak `ano`/`nie` instead of `yes`/`no`
- follow-up: user-facing wording in relevant confirm flows aligned closer to Slovak consistency

## [0.6.0] - 2026-04-12

### Added
- unified bounded semantic resolver service for canonical action/value mapping (`bot/services/semantic_action_resolver.py`)
- contact intake extraction service for structured draft parsing (`bot/services/llm_contact_parser.py`)
- document intake pipeline for contract attachments with text-PDF extraction and scan-PDF detection (`bot/services/document_intake.py`)
- contact intake states for missing-field clarification + confirmation and save through existing contact service
- tests for semantic resolver, contact intake flow, voice state routing into contact clarification, and document intake branches

### Changed
- invoice runtime now uses bounded semantic resolution for:
  - top-level action routing,
  - preview confirmation (`ano`/`nie`),
  - post-PDF decision (`schvalit`/`upravit`/`zrusit`)
- voice handler now routes into contact-intake clarification/confirmation states

### Notes
- scan-PDF OCR branch currently fail-loud and pluggable; full OCR provider is not yet wired in runtime
