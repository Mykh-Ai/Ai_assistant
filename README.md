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
- `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` — rollout/implementation план (що/коли/в якій фазі)
- `docs/FakturaBot_LLM_Orchestrator_Contract.md` — детальний LLM/orchestrator контракт (як саме AI шар взаємодіє з Python)
- `docs/llm/Canonical_Action_Registry.md` — актуальний аудит top-level дій (включно з manual command flows)
- `docs/llm/In_Action_Response_Registry.md` — реєстр bounded in-action responses і slot-clarification груп
- `docs/llm/Bounded_Resolver_Prompt_Template.md` — шаблон bounded resolver payload + optional action hints
- `docs/llm/New_Action_Design_Checklist.md` — чекліст додавання/формалізації нових canonical actions
- `AGENTS.md` — правила роботи агентів і помічників
- `PROJECT_LOG.md` — журнал ходу проєкту
- `CHANGELOG.md` — зміни по продукту / коду

## Принцип роботи з AI

AI не є джерелом істини.

FakturaBot використовує **Bounded Semantic Canonicalization** через **Semantic Action Resolver**:
- Python задає поточний контекст і дозволені канонічні виходи,
- LLM зводить шумний ввід до одного дозволеного канонічного значення або `unknown`,
- Python валідовує результат і тільки Python виконує дії.

Це однаково застосовується для:
- top-level action selection,
- in-state reply resolution,
- structured value canonicalization.

Додатковий runtime принцип для structured flows:
- якщо неясне лише одне поле, бот переходить у slot clarification, зберігає partial draft і просить тільки це поле (без повного reset workflow).

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
   - `/service` — správa názvov služieb (krátky názov služby → plný názov služby)
   - `/contact` or `/contact_add` - Phase 3 manual customer contact onboarding
   - `/invoice` — Phase 4 draft → confirm → PDF preview flow

Poznámka pre onboarding dodávateľa:
- SMTP host/user/pass sú v MVP voliteľné (môžete preskočiť cez `-` alebo `/skip`);
- email sending sa má používať iba pri kompletnej SMTP konfigurácii.

Примітка по Phase 4: QR block у PDF використовує реальний PAY by square payload encoder (internal Python implementation) з валідацією полів платежу.
Є щонайменше один успішний локальний manual scan-тест у реальній банківській апці для поточного PAY by square flow.
Додаткові перевірки в інших банківських апках усе ще бажані перед повним production sign-off.
