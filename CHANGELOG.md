# CHANGELOG

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
