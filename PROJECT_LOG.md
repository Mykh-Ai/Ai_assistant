# PROJECT_LOG

Журнал ходу проєкту.
Фіксує не лише зміну коду, а й зміну рішень, логіки, scope та концепції.

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