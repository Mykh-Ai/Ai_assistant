# CHANGELOG

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
