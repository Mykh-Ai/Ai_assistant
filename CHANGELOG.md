# CHANGELOG

## [Unreleased]

### Added
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

### Changed
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
- accounting Document Intake now extracts raw `purchase_subject` / `Predmet nákupu` instead of premature accounting category candidates.
- temporary OfficeFlow/accounting intake sessions now expire after 5 minutes and safely clean only upload staging paths.
- accounting Document Intake now warns about deterministic metadata duplicates before preview while still requiring explicit preview approval before save.

### Notes
- Controlled multi-user dry run remains one backend, one bot token, and one SQLite DB; access is limited to bootstrap allowlisted or admin-approved Telegram users, and this is not full SaaS multi-tenancy.
- Public automatic signup remains out of scope; unknown users can only request access and must be approved by an admin before onboarding, LLM/STT/LMM, invoices, contacts, or document intake.
- Legacy supplier SMTP values should be purged after backup with `UPDATE supplier SET smtp_host = NULL, smtp_user = NULL, smtp_pass = NULL;`.
- Document Intake remains incremental: no bank matching, Telegram button callbacks, Google Drive sync, Zevs runtime profile, standalone contract save, bank-statement matching, or expense categorization.

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
