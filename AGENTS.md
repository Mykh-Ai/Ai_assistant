# AGENTS.md

## Призначення

Цей репозиторій використовується для розробки практичних Telegram-ботів під задачі малого бізнесу.

Перший основний кейс: **FakturaBot**.

## Головне правило

Не вигадувати стан проєкту.

Якщо чогось немає в коді, документації або журналі проєкту — вважати, що цього ще не існує.

## Джерела істини

Пріоритет джерел істини:

1. `docs/TZ_FakturaBot.md`
2. `PROJECT_LOG.md`
3. поточний код репозиторію
4. `CHANGELOG.md`

Якщо між ними є конфлікт:
- спочатку звіряти ТЗ,
- потім журнал рішень,
- потім уже робити висновки.

Спеціалізовані contract scopes мають додаткові джерела, які треба читати перед змінами у відповідній зоні:

### LLM / action / FSM / semantic routing

- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

### Confirmation-like decisions

- `docs/Canonical_Decision_Resolver_Contract.md`

### OfficeFlow / Document Intake

- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`

### User access / onboarding / authorization

- `docs/User_Access_Model_Roadmap.md`

## Mandatory pre-work contract-read step

Перед змінами в handlers, FSM flows, top-level actions, in-action decisions, confirmation flows, LLM prompts, document intake, attachment router, voice/text routing, user access або authorization агент повинен спочатку прочитати релевантні contract docs.

У відповіді або робочому підсумку перед зміною треба явно зафіксувати:
- contracts read;
- constraints extracted;
- whether the change touches confirmation, routing, LLM, FSM, storage, DB, or access.

If the agent did not list contracts read and extracted constraints, the task is not ready for implementation.

Якщо зміна торкається кількох scopes, читати всі відповідні contracts. Не покладатися лише на назву файлу або стару пам’ять про архітектуру.

## Canonical top-level action completion gate

Новий canonical top-level action не вважається `implemented`, доки не виконано весь runtime + docs + tests контур:

- action зареєстрований у `docs/llm/Canonical_Action_Registry.md`;
- Python має власника виконання: handler/FSM/service route;
- top-level resolver отримує action тільки через Python-provided `allowed_actions`;
- `action_hints`, якщо потрібні, описують semantic meaning, а не literal alias whitelist;
- text/command route працює або явно не застосовується;
- voice reachability працює і має тести, або є явна documented причина, чому voice для цього action не застосовується;
- active FSM states не падають назад у top-level routing;
- in-FSM controls/confirmations документовані в `docs/llm/In_Action_Response_Registry.md`;
- exact-value steps, де голос небезпечний, лишаються text/file-only;
- README architecture tree оновлений для user-facing top-level/subflow карти;
- `PROJECT_LOG.md` і `CHANGELOG.md` оновлені.

Voice rule:
- voice може запускати top-level actions і вибирати bounded actions/fields/options у FSM;
- voice не повинен заповнювати precision-sensitive exact values: IBAN, IČO, DIČ, IČ DPH, email, invoice number, item numeric values, prices, quantities, final item descriptions, service alias names, or exact destructive confirmations.

## Server-side operational context

Для будь-яких дій на сервері FakturaBot спочатку перевіряти приватний локальний файл:

- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Цей файл не призначений для публічного індексу Git і може бути проігнорований `.gitignore`.

Не використовувати `docs/local-only/*.example.md` як робочий server runbook.
Файли `*.example.md` у `docs/local-only/` — це лише безпечні публічні заглушки / шаблони без реальних серверних даних.

## Як працювати зі змінами

Будь-яка суттєва зміна повинна:
- або відповідати чинному ТЗ,
- або супроводжуватись оновленням ТЗ,
- або бути явно зафіксована в `PROJECT_LOG.md`.

Не робити прихованих концептуальних змін.

Before making file changes, the agent must present a concise action plan and wait for the user's approval. Read-only investigation can be done without approval. If the user explicitly requests a narrow file edit, that request counts as approval for that scoped edit only.

Агент повинен питати дозвіл лише перед важливими змінами, зміною концепції, ризиковими діями або видаленням файлів / логіки.
Не засипати користувача постійними погодженнями для дрібних, очевидних або безпечних змін.

## Read-only і Sandbox

Read-only дії в межах репозиторію не потребують окремого дозволу користувача:
- читання файлів;
- пошук по коду або документації;
- перегляд `git status`, `git diff`, `git log`, `git branch`;
- інші команди, які не змінюють файли, git history, runtime state або зовнішні сервіси.

The agent must not ask for permission before running read-only commands. If a command does not modify files, git history, runtime state, DB/storage, or external services, run it directly without a separate approval request.

Якщо read-only команда падає через sandbox / environment setup, агент не повинен перетворювати це на цикл погоджень.
Правильна поведінка:
- повторити або спростити read-only команду, якщо це має сенс;
- використати уже доступний контекст;
- коротко зафіксувати технічне обмеження, якщо частину даних неможливо прочитати;
- продовжити роботу без запиту дозволу, якщо задача все ще може бути виконана коректно.

Запит дозволу потрібен для:
- запису за межами дозволеної робочої директорії;
- network / server дій;
- встановлення залежностей;
- commit / merge / push, якщо користувач прямо цього не просив;
- destructive або risky дій;
- runtime / DB / storage змін, якщо вони не були явно замовлені.

## Test commands

For this repository, run tests with `python -m pytest -q` from `D:\AI_Model\Ai_assistant`.
Avoid bare `pytest -q` because it may not include the project root on `sys.path` and can fail to import `bot`.

## Формат результату

Після виконання запиту на зміни в проєкті агент повинен за замовчуванням повертати результат у форматі:
1. Короткий summary, що саме змінено.
2. Unified diff.
3. Без зайвих покращень поза цими пунктами.

Якщо користувач явно задав інший формат відповіді, треба дотримуватись формату користувача.

## Як працювати з AI-функціональністю

AI не повинен трактуватись як автономний виконавець.

Правильна модель:
- Python orchestrates
- AI extracts / drafts
- Python validates
- user confirms
- system saves

Це правило особливо обов’язкове для:
- invoice draft
- contract customer extraction
- будь-яких реквізитів контрагентів
- email / PDF сценаріїв

## Canonical DecisionResolver rule

Усі confirmation-like replies повинні проходити через `bot/services/decision_resolver.py`.

Не додавати локальні парсери для:
- `ano` / `nie`
- `ok` / `tak`
- `schvalit` / `upravit` / `zrusit`
- Slovak diacritics variants
- Cyrillic або multilingual variants

Кожен новий confirmation-like flow повинен:
- вибрати decision family: `yes_no` або `approve_edit_cancel`;
- зареєструвати `context_name` у `tests/test_decision_resolver.py`;
- додати handler-level tests, які доводять використання shared resolver, а не локального parser/branching.

Це правило обов’язкове для invoice preview/post-PDF, contact confirmation, onboarding confirmation, accounting document preview, duplicate confirmation, delete/cancel flows та будь-яких майбутніх OfficeFlow confirmations.

## User access / security boundary

Unknown або unauthorized Telegram users must not create:
- supplier profiles;
- contacts;
- invoices;
- invoice PDFs;
- accounting documents;
- document metadata;
- temporary upload files;
- tenant storage directories;
- workspaces.

Unknown або unauthorized Telegram users must not trigger:
- LLM calls;
- STT calls;
- LMM / Vision calls;
- document classification/extraction calls.

Pending access requests are not tenants, not supplier profiles, and not business onboarding. Approval is required before `/supplier` and before any business flow.

Phase 1 controlled dry run uses one shared Telegram bot token, one backend, one SQLite DB, and allowlisted Telegram IDs. Per-client Telegram bot tokens / VPS / container / DB / API-key deployment is future commercial / installation-as-a-service only unless `docs/TZ_FakturaBot.md` and `PROJECT_LOG.md` explicitly say otherwise.

## OfficeFlow attachment / document intake boundary

Idle photo/PDF classification must only happen after authorization.

Active FSM state wins over idle classifier. Якщо користувач перебуває в active FSM flow, attachment routing must respect that state before any idle OfficeFlow classifier.

No automatic contact creation from receipts, incoming invoices, PDFs, photos, or idle attachments.

No automatic expense/accounting document save before user approval. AI/LMM may extract or draft; Python validates; user confirms; only then system saves.

## Як працювати з документами

Після кожної змістовної сесії треба оновлювати `PROJECT_LOG.md`.

Якщо зміни впливають на продуктову логіку, MVP або архітектуру — треба оновити і ТЗ.

## Що вважати завершеним завданням

Завдання не вважається завершеним, якщо:
- змінено код, але не зафіксовано важливе рішення;
- змінено концепцію, але не оновлено ТЗ;
- зроблено новий flow, але його немає в документації;
- змінено MVP scope, але це ніде не записано.

## Стиль роботи

Перевага надається:
- простим рішенням,
- мінімальній залежності від зовнішніх сервісів,
- стабільності,
- прозорій логіці,
- валідації після AI,
- локальному збереженню перевірених даних.

## Що не робити без окремого рішення

Не додавати самостійно:
- multi-tenant SaaS логіку
- зовнішній lookup контрагентів як критичну залежність
- автоматичне збереження AI-результатів без підтвердження
- складну рольову систему
- нові модулі, які роздувають MVP
