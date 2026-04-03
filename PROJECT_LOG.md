# PROJECT_LOG

Журнал ходу проєкту.
Фіксує не лише зміну коду, а й зміну рішень, логіки, scope та концепції.

---

## 2026-04-03 — Session 007 — Phase 4: invoice draft → confirm → PDF preview

### Ціль

Реалізувати перший повний invoice flow для text/voice input:
draft → local contact resolution → preview → confirm → save → PDF preview.

### Що реалізовано

- додано persistence для faktúr:
  - таблиця `invoice`,
  - таблиця `invoice_item`,
  - fail-loud schema compatibility checks без auto-drop;
- додано `bot/services/invoice_service.py`:
  - генерація номеру `RRRRNNNN`,
  - save faktúry з одним рядком позиції,
  - get by id/number,
  - save `pdf_path`;
- додано `bot/services/pdf_generator.py` (reportlab + qrcode):
  - one-page business invoice layout,
  - Dodávateľ/Odberateľ block,
  - meta/dates block,
  - payment block,
  - items table,
  - strong `Na úhradu` block,
  - QR block;
- реалізовано `bot/handlers/invoice.py`:
  - `/invoice` text entry point,
  - preview словацькою,
  - confirm (`ano`/`nie`),
  - PDF decision step (`schváliť`/`upraviť`);
- voice flow інтегровано у той самий invoice path:
  - STT text далі обробляється через спільний Phase 4 flow;
- реалізовано local contact-only resolution:
  - exact match,
  - case-insensitive exact match;
- зафіксовано date semantics в коді:
  - `issue_date` = auto today,
  - дата з input трактується як `delivery_date`,
  - якщо відсутня — `delivery_date = issue_date`,
  - `due_date = issue_date + due_days`.

### Що свідомо не робилось

- email send;
- external lookup / FinStat;
- contract extraction;
- fuzzy matching;
- multi-item UI;
- advanced edit workflow;
- migration framework.

### Follow-up note (QR scope honesty)

- Phase 4 merge не блокується через QR subsystem.
- Поточний QR block у PDF вважається тимчасовим placeholder-рішенням для payment QR.
- Окремий наступний технічний крок:
  - дослідити/інтегрувати справжній Pay by Square payload generator;
  - перевірити сумісність payload із реальним скануванням.

---


## 2026-04-03 — Session 006 — PDF Layout Spec (docs-only)

### Ціль

Підготувати окрему docs-only специфікацію візуальної структури PDF-фактури для наступної фази реалізації генератора.

### Що реалізовано

- створено новий документ `docs/FakturaBot_PDF_Layout_Spec.md`;
- зафіксовано purpose PDF як частини wow-ефекту продукту;
- описано design principles (clean, restrained, readability-first);
- зафіксовано color principles з вимогою двох приємних фонових тонів без перевантаження;
- формалізовано порядок обов’язкових layout-блоків:
  header, Dodávateľ/Odberateľ, meta/dates, payment, items table, total, QR, footer;
- додано date semantics для `Dátum vystavenia`, `Dátum dodania`, `Dátum splatnosti`;
- зафіксовано preview/approval rule (`schváliť` / `upraviť`);
- додано typography/spacing guidelines та секцію “Do not”.

### Що свідомо не робилось

- не реалізовувався PDF generator;
- не змінювалося ТЗ;
- не додавалися нові продуктові фічі поза межами layout specification.

---

## 2026-03-31 — Session 004 — Phase 2: supplier onboarding (chat-based)

### Ціль

Реалізувати мінімальний supplier onboarding без fancy UI, без складної FSM-архітектури,
як базу для наступних invoice phases.

### Що реалізовано

- розширено SQLite schema `supplier` під повний профіль постачальника;
- додано `bot/services/supplier_service.py` з операціями:
  - create or replace profile,
  - get by `telegram_id`,
  - update profile (через upsert);
- реалізовано `bot/handlers/onboarding.py` як простий послідовний chat flow:
  12 полів → summary → confirm (`yes/no`) → save;
- додано MVP-рівень валідації для IČO/DIČ/IČ DPH/email/IBAN/days_due;
- додано UX-повідомлення, якщо профіль уже існує, з пропозицією пройти flow повторно.

### Безпека / обмеження фази

- SMTP пароль не логується;
- у summary пароль маскується (`********`);
- зберігання SMTP пароля в цій фазі лишається plain-text у SQLite (тимчасово, для MVP);
- production-grade secure credential storage ще не завершено.

### Що свідомо не робилось

- contact onboarding;
- invoice save flow;
- PDF/email send;
- contract extraction;
- lookup API;
- окремий settings center.

### Рішення

Phase 2 стартувала та реалізована в межах simple chat-based supplier onboarding.
Fancy UI свідомо відкладено.
Supplier profile став базовим persistence-шаром для наступних invoice phases.

---

## 2026-03-31 — Session 003 — Phase 1: voice-to-draft preview flow

### Ціль

Реалізувати перший живий wow-flow: голос → STT → AI draft preview в чаті.
Без save в БД, без PDF, без email, без supplier/contact persistence.

### Що реалізовано

- `bot/services/speech_to_text.py` — STT через OpenAI Audio API (Whisper)
- `bot/services/llm_invoice_parser.py` — LLM draft parsing через OpenAI Chat API
- `bot/handlers/voice.py` — voice message handler: download → STT → parse → preview
- `prompts/invoice_draft_prompt.txt` — системний промпт для витягу invoice draft
- `bot/config.py` — додано `openai_stt_model`, `openai_llm_model`
- `bot/main.py` — config передається в polling workflow data
- `requirements.txt` — додано `openai>=1.30`

### Архітектурні рішення

- STT і LLM parsing — два окремі сервіси, не злиті в один
- тимчасові файли видаляються одразу після обробки (try/finally)
- якщо `OPENAI_API_KEY` відсутній — app стартує нормально, voice handler
  повертає зрозуміле повідомлення без падіння
- graceful error handling для STT і LLM failure окремо

### Що свідомо не робилось

- save draft у БД
- PDF генерація
- email
- supplier/contact persistence
- contract extraction
- FSM / multi-step dialog

### Що далі

- Phase 2: мінімальний supplier onboarding (chat-based, sequential)

---

## 2026-03-31 — Session 002 — Phase 0 implementation skeleton

### Що вирішено

- docs bootstrap вважається завершеним;
- стартував Phase 0 implementation skeleton;
- серверний deploy свідомо відкладено;
- поточна ціль — підготувати локальний runnable каркас без feature-логіки.

### Що змінено

- створено базову структуру `bot/`, `prompts/`, `storage/`;
- додано мінімальний `config.py` з читанням `.env`;
- додано SQLite bootstrap з початковою таблицею `supplier`;
- додано мінімальний `/start` handler і запуск aiogram polling;
- додано `.env.example`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`.

### Що свідомо не робилось

- не реалізовувались voice / Whisper / LLM draft / PDF / email / contract extraction;
- не виконувався серверний deploy;
- не додавались internet lookup, SaaS/multi-tenant або інші модулі поза Phase 0.

### Що далі

- наступна ціль — ранній voice/draft flow;
- після цього — мінімальний onboarding та contacts у chat-based стилі.

---

## 2026-03-30 — Session 001 — Концептуальне перепозиціонування проєкту

### Що вирішено

- Повноцінний масовий SaaS на старті відкинуто.
- Перший інстанс розгортається для самого автора.
- FakturaBot розглядається як жива демонстраційна вітрина.
- Продукт позиціонується як частина ширшої моделі:
  розгортання Telegram-ботів під задачі малого бізнесу.

### Що входить у MVP v1.0

- Telegram-бот
- голосовий сценарій
- текстовий сценарій
- Whisper STT
- AI invoice draft
- ручний supplier onboarding
- ручне додавання контрагента
- додавання контрагента з договору через AI
- локальна адресна книга
- збереження оригіналу договору
- PDF-фактура
- QR Pay by Square
- email-відправка
- історія фактур
- статуси
- SQLite
- Docker deploy

### Що відкладено

- lookup контрагентів з інтернету
- FinStat
- ORSR інтеграція
- повний OCR pipeline
- Google Drive
- billing
- multi-tenant архітектура
- кабінет користувача

### Ключові рішення по AI

- AI не є джерелом істини.
- Усі критичні сценарії працюють через draft + validation + confirmation.
- Для договорів обрана модель:
  Python orchestrates → AI extracts → Python validates → user confirms.
- AI використовується для нормалізації живого диктування та коротких назв робіт.

### Приклад важливого сценарію

Голосовий input типу:
“Тесла Словакія за оправи один кус там 2000 євр, датум виставлення 30 марта 2026, сплатност 30 днів”

повинен перетворюватись у структуровану invoice draft-чернетку.

### Важлива продуктова ідея

FakturaBot — не просто бот для фактур.
Це перший приклад кастомного Telegram-бота під реальний бізнес-процес.

### Документи

Актуальне ТЗ:
`docs/TZ_FakturaBot.md`

### Наступні кроки

- створити стартову структуру репозиторію
- додати README
- додати AGENTS
- додати CHANGELOG
- перенести актуальне ТЗ у docs
- почати каркас MVP

## 2026-03-31 — Session 003 — Phase 1 voice-to-draft preview

### Що вирішено

- Phase 1 реалізується не як простий voice → text smoke test, а як перший wow-flow:
  **voice → STT → AI draft preview**
- На цій фазі свідомо не робимо:
  - save у БД
  - PDF
  - email
  - supplier/contact persistence
- STT і LLM parsing розділені на окремі сервіси.
- Реальні API ключі не зберігаються в repo; використовується `.env`.

### Що змінено

- додано підтримку `OPENAI_STT_MODEL` і `OPENAI_LLM_MODEL` у config;
- додано `bot/services/speech_to_text.py`;
- додано `bot/services/llm_invoice_parser.py`;
- додано prompt `prompts/invoice_draft_prompt.txt`;
- додано `bot/handlers/voice.py`;
- підключено voice router;
- Phase 1 flow тепер:
  Telegram voice → local temp file → OpenAI transcription → OpenAI draft parsing → preview in chat.

### Важливі дрібниці / уроки

- На старті проєкту треба перевіряти, що `.env` внесений у `.gitignore`.
- Один `OPENAI_API_KEY` використовується і для STT, і для LLM parsing.
- Перший voice-flow повинен показувати не просто розпізнаний текст, а спробу зрозуміти намір користувача.
- Preview не повинен показувати криві значення типу `— —`; форматування треба одразу чистити.
- Якщо STT повернув порожній текст, не можна відправляти його в LLM — треба зупиняти flow і просити повторити голосове.

### Що свідомо не робилось

- не реалізовувались supplier onboarding, contacts, PDF, email, contract extraction;
- не додавалась логіка save draft;
- не було серверного deploy;
- internet lookup / FinStat не входять у поточний flow.

### Статус фази

Phase 1 завершена на рівні коду.
Живий runtime test з реальним `BOT_TOKEN` і `OPENAI_API_KEY` ще потрібен.

### Що далі

- Phase 2 — мінімальний supplier onboarding у chat-based стилі;
- без fancy UI;
- ціль: створити і зберегти профіль постачальника, потрібний для майбутніх invoice flows.
## 2026-04-01 - Session 005 - Phase 3: manual contact creation

### Goal
Implement minimal manual customer contact creation required for next invoice phases.

### Implemented
- SQLite bootstrap extended with `contact` table (fail-loud compatibility check, no auto-drop/migrations).
- Added `bot/services/contact_service.py` with repository-style operations:
  - `ContactProfile`
  - `get_all_by_supplier(telegram_id)`
  - `get_by_name(telegram_id, name)`
  - `create_contact(...)`
  - `create_or_replace(...)`
- Implemented `bot/handlers/contacts.py` as a simple chat-based flow:
  1. company name
  2. ICO
  3. DIC
  4. optional IC DPH (`-`)
  5. address
  6. email
  7. optional contact person (`-`)
  8. summary
  9. confirm `yes`/`no`
  10. save
- Added exact-name duplicate check per supplier; existing name is warned and confirmed overwrite saves via upsert.
- Added supplier-profile guard: contact flow is blocked until `/supplier` onboarding is completed.

### Explicitly not included in this phase
- contract-based contact extraction
- contact search UI
- invoice save flow
- PDF generation
- email send
- external lookup API / FinStat
- complex dedup/fuzzy matching

### Decision
Phase 3 remains intentionally simple and chat-based; contract extraction and external lookup stay deferred to later phases.

### Follow-up note (language consistency)
- Text confirmation in supplier onboarding aligned to Slovak: `ano / nie` instead of `yes / no`.
- Text confirmation in manual contact flow aligned to Slovak: `ano / nie` instead of `yes / no`.
- User-facing language consistency improved across `/start`, voice preview, supplier onboarding, and manual contact flow.
- Why this matters:
  - bot is oriented to a Slovak interface;
  - mixed-language confirmations create product inconsistency;
  - language consistency is better fixed early while flows are still small.
## 2026-04-03 - Session 006 - Research spike: real PAY by square integration path

### Goal
Провести technical research spike для реальної інтеграції PAY by square QR у FakturaBot без blind implementation.

### Implemented
- Підготовлено окремий research artifact: `docs/PayBySquare_Research_Spike.md`.
- Зібрано та порівняно джерела:
  - офіційна специфікація PAY by square 1.2.0,
  - by square API docs,
  - Python package `pay-by-square`,
  - активні non-Python implementation repos (TS/Go/PHP) як референси.
- Зафіксовано практичний технічний вердикт для repo:
  - рекомендований шлях: власна мінімальна Python-реалізація payload encoder (spec-driven),
  - без введення зовнішнього SaaS як критичної залежності,
  - без cross-runtime адаптера як базового шляху.
- Зафіксовано мінімальний required payload і field constraints для першої інтеграції.
- Підготовлено implementation recommendation для майбутнього окремого PR (без змін runtime логіки у цій сесії).

### Explicitly not included in this session
- Немає змін у `bot/services/pdf_generator.py`.
- Немає production integration patch для PAY by square.
- Немає розширення scope на email / external bank API / інші модулі.

### Decision
Спочатку завершуємо research + decision record, після чого окремим PR робимо мінімальну production інтеграцію реального PAY by square payload у PDF flow.


## 2026-04-03 - Session 007 - Implementation: real PAY by square payload in PDF flow

### Goal
Замінити QR placeholder у Phase 4 на реальний PAY by square payload generator для invoice payment use case.

### Implemented
- Додано `bot/services/pay_by_square.py` з internal spec-driven encoder pipeline:
  1) mapping paymentorder даних,
  2) CRC32,
  3) LZMA raw compression (LZMA1),
  4) header/length prepend,
  5) Base32hex payload output.
- Додано strict validation: IBAN, amount, currency, VS, due date, beneficiary name (fail-loud через `PayBySquareValidationError`).
- `bot/services/pdf_generator.py` переведено з placeholder рядка `PAYBYSQUARE|...` на виклик `build_pay_by_square_payload(...)`.
- Додано unit tests:
  - deterministic payload vector,
  - validation failures,
  - PDF integration smoke (QR payload looks encoded and PDF still written).
- Оновлено `README.md`, `docs/TZ_FakturaBot.md`, `CHANGELOG.md` для чесного відображення статусу інтеграції.

### Explicitly not included
- Немає external SaaS generation path.
- Немає Node/Go/PHP sidecar adaptation.
- Немає email/bank API scope expansion.

### Manual verification status
- У цьому середовищі не виконувалась реальна перевірка сканування QR банківськими мобільними апками.
- Після deploy потрібна manual verification на реальних SK banking clients.
### Follow-up note (семантика дат у faktúre)
- Плутанину між `Dátum vystavenia` і `Dátum dodania` у специфікації усунуто.
- Дата, вказана користувачем у voice/text input, тепер інтерпретується як `Dátum dodania`.
- `Dátum vystavenia` завжди встановлюється ботом автоматично в момент створення фактури.

## 2026-04-03 - Session 008 - Verification support: PAY by square manual scan checklist

### Goal
Prepare a local verification-task plan for manual validation of the real PAY by square QR after merge, without runtime code changes.

### Implemented
- Added a short verification artifact: `docs/PayBySquare_Manual_Verification_Checklist.md`.
- Documented the local verification flow:
  - how to generate a PDF invoice locally;
  - where to find the generated PDF;
  - which fields must be checked after scanning in a banking app.
- Added expected outcomes:
  - success,
  - partial success,
  - fail.
- Added a short record checklist for the post-test note so follow-up patch decisions are explicit.

### Explicitly not included
- No runtime code changes.
- No new feature work.
- No email flow changes.
- No Phase 5 work.

### Decision
Before PAY by square production sign-off, a separate manual scan verification in a real banking mobile app must be completed and recorded in `PROJECT_LOG.md`.

