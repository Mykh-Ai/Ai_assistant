# Ai_assistant

Практичне ядро для Telegram-ботів під задачі малого бізнесу.

Перший реалізований кейс у цьому репозиторії — **FakturaBot**:
бот для створення фактур з голосу, тексту та договору.

## Ідея

Це не масовий SaaS на старті.

Підхід такий:
- є спільне технічне ядро,
- є окремий сценарій під конкретну задачу,
- є кастомізація під конкретного користувача або клієнта,
- є розгортання, підтримка і подальші доопрацювання.

FakturaBot — перша вітрина цього підходу.

## Поточний статус

Проєкт у фазі ранньої MVP-реалізації (Phase 4).

Поточна ціль:
- розгорнути перший інстанс для автора,
- реалізувати живий user flow,
- отримати продукт, який можна показати і дати “помацати”.

## MVP FakturaBot v1.0

У першу версію входить:
- Telegram-бот
- голосові повідомлення
- текстові повідомлення
- STT (Whisper)
- AI-побудова invoice draft
- ручний онбординг постачальника
- ручне додавання контрагента
- додавання контрагента з договору через AI
- локальна адресна книга
- збереження оригіналу договору
- генерація PDF-фактури
- QR-код Pay by Square
- email-відправка фактури
- історія фактур
- статуси фактур
- SQLite
- Docker deploy

## Що не входить у v1.0

- multi-tenant SaaS
- lookup контрагентів з інтернету
- FinStat / ORSR інтеграція
- окремий повний OCR pipeline
- Google Drive
- billing
- кабінет користувача
- складна рольова система

## Структура документації

- `docs/TZ_FakturaBot.md` — головне ТЗ
- `AGENTS.md` — правила роботи агентів і помічників
- `PROJECT_LOG.md` — журнал ходу проєкту
- `CHANGELOG.md` — зміни по продукту / коду

## Принцип роботи з AI

AI не є джерелом істини.

Усі критичні сценарії працюють так:

**AI / parser → draft → validation → user confirmation → save**

## Довгострокова ідея

Після FakturaBot на цьому ж підході можуть будуватись:
- боти для замовлень,
- боти для резервацій,
- боти для запису клієнтів,
- боти для заявок,
- інші Telegram-боти під конкретні бізнес-процеси.
## Run

1. Copy `.env.example` to `.env` and fill in:
   - `BOT_TOKEN` — Telegram bot token (required)
   - `OPENAI_API_KEY` — required for voice-to-draft flow (Phase 1+)
   - `OPENAI_STT_MODEL` — default: `whisper-1`
   - `OPENAI_LLM_MODEL` — default: `gpt-4o`
2. Install dependencies: `pip install -r requirements.txt`
3. Start locally: `python -m bot.main`
4. Or start with Docker: `docker compose up --build`
5. In Telegram use:
   - `/start` — health check
   - voice message — Phase 1 draft preview
   - `/supplier` або `/onboarding` — Phase 2 supplier onboarding
   - `/contact` or `/contact_add` - Phase 3 manual customer contact onboarding
   - `/invoice` — Phase 4 draft → confirm → PDF preview flow

Примітка по Phase 4: QR block у PDF зараз є тимчасовим payment QR placeholder.
Окрема задача — підтвердити та інтегрувати сумісний із реальним скануванням Pay by Square payload.
