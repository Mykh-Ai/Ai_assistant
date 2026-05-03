# Технічне завдання: FakturaBot

## Telegram-бот для створення фактур з голосу, тексту та договору

**Версія:** 2.0 Concept Update  
**Дата:** 30.03.2026  
**Автор:** Mykhailo Alieksieienko

---

## 2026-05-03 Addendum: supplier onboarding invoice-number baseline

Controlled user onboarding must collect one additional invoice setting before the default due-days question:
- first invoice number FakturaBot should generate for the current calendar year;
- format stays canonical `RRRRNNNN`, for example `20260025`;
- the setting is tenant-scoped by `supplier_telegram_id` and `issue_year`.

Runtime numbering rule:
- if the supplier has no bot-created invoice in that year, the next generated number is the configured first number;
- if bot-created invoices already exist, the next generated number is the larger of the configured first number and the next number after the supplier's latest invoice;
- the setting does not import historical external invoices and does not create placeholder invoice rows.

Supplier email sending remains optional in the controlled dry run. Legacy local/server SQLite databases with `supplier.smtp_host`, `supplier.smtp_user`, or `supplier.smtp_pass` as `NOT NULL` must be migrated by application bootstrap to the current nullable schema so supplier onboarding can save without SMTP credentials.

## 2026-05-03 Addendum: contact address and optional customer email

Customer/contact onboarding must not require the customer's email address. If the user does not provide it, the contact may still be saved and the local SQLite `contact.email` value may remain an empty string for compatibility with the current schema.

The contact address must include a house/building number. City-only or street-only values are not sufficient for invoice contact data and must be clarified before contact confirmation.

When a contact email is empty, the generated invoice PDF must omit the customer `Email:` line entirely instead of rendering an empty value or placeholder. Supplier email remains part of the supplier profile block.

## 2026-05-03 Addendum: voice delete intent and known STT `ano` noise

Explicit voice/text requests to delete an existing invoice must route to the bounded top-level action `delete_existing_invoice`, not to generic `create_invoice`, whenever the user input contains a clear delete/remove verb together with an invoice/faktura target. The rule is independent of the invoice number value; numbers such as `7`, `10`, `11`, or full canonical invoice numbers are all references to be resolved later by supplier-scoped Python lookup.

Deletion must remain outside the `create_invoice` flow. `delete_existing_invoice` still requires a separate shared `yes_no` DecisionResolver confirmation before Python deletes invoice rows or PDF files.

The observed STT phrase `Ah, nao` / `Ah, nao!` is treated narrowly as Slovak `ano` in confirmation contexts because the current STT repeatedly produces that phrase for spoken `ano`. This is an STT-noise compatibility rule, not broad Portuguese language support.

## 2026-05-03 Addendum: confirmed semantic aliases for invoice customer lookup

When `create_invoice` cannot directly resolve the extracted customer candidate but the existing supplier-scoped contact lookup finds exactly one safe close candidate, the bot may ask a bounded confirmation question such as `Mysleli ste odberateľa REALTIME TECHNOLOGIES SK, s.r.o.? áno / nie`.

Only after an explicit shared `yes_no` DecisionResolver confirmation may the bot save a supplier-scoped confirmed alias from the cleaned extracted customer candidate to that contact. The raw full STT transcript must not be stored as an alias. If the user rejects the suggestion, the flow returns to customer clarification without saving an alias.

Country suffix tokens are safety-sensitive. A candidate without a country suffix may be matched to one unique stored country-suffixed contact only after confirmation. A user candidate with an explicit country token such as `CZ` must not silently match an `SK` contact.

## 1. Опис продукту

FakturaBot — це Telegram-бот, який допомагає створювати фактури зі смартфона через голосові повідомлення, текстові команди та витяг реквізитів із договору.

На старті це **не масовий SaaS**, а **практична демонстраційна вітрина та робочий інструмент для самого автора**. Перший інстанс розгортається на власному сервері автора, де автор є першим реальним користувачем.

Проєкт розглядається як **перша вітрина для ширшої моделі**: розробка та розгортання Telegram-ботів під конкретні бізнес-процеси клієнта.

Перший конкретний кейс — **бот для фактур**. У майбутньому на тому ж підході можуть будуватись боти для:
- прийому замовлень,
- резервацій,
- заявок,
- запису клієнтів,
- сервісних повідомлень.

Docs-first архітектурний напрямок для цієї ширшої моделі зафіксовано як **OfficeFlow**: umbrella-система для документних workflows малого бізнесу. У цій моделі FakturaBot залишається модулем outgoing invoices. Поточне ТЗ не змінює runtime invoice flow, supplier SZČO profile, `pdf_path`, DB schema або поточну структуру `storage/invoices/`.

### 1.1 Стартова бізнес-модель

На першому етапі FakturaBot продається не як універсальна SaaS-платформа, а як:
- розгортання бота,
- налаштування під конкретний процес,
- підтримка,
- подальші доопрацювання,
- кастомізація під клієнта.

Формат позиціонування:

**«Роблю та розгортаю Telegram-ботів під задачі малого бізнесу»**

FakturaBot є першим демонстраційним продуктом у цій лінійці.

### 1.2 Чому не класичний SaaS

Масовий multi-tenant SaaS для цього продукту на старті не є пріоритетом, тому що:
- у різних користувачів різна мова і манера диктування,
- різні скорочення назв робіт,
- різні шаблони документів,
- різні бізнес-процеси,
- висока відповідальність за дані та інфраструктуру,
- занадто велика складність для першої версії.

Замість цього обирається **гібридна модель**:
- спільне технічне ядро,
- індивідуальні налаштування,
- окреме розгортання,
- кастомізація під потреби конкретного користувача.

### 1.3 Головна цінність MVP

Головна цінність першої версії:
- надиктувати фактуру голосом,
- отримати структуровану чернетку,
- підтвердити,
- згенерувати PDF з QR-кодом Pay by Square,
- відправити контрагенту на email,
- зберегти історію та контрагентів.

Ключовий wow-ефект MVP — **голосовий сценарій + PDF з QR + відправка одним натиском**.

### 1.4 Ключовий принцип продукту

AI не є джерелом істини. У v2.0 контракт AI базується на **Bounded Semantic Canonicalization**: Python задає контекст і дозволені канонічні виходи, LLM повертає один дозволений канонічний вихід або `unknown`, Python валідовує і виконує дії.

Додатковий project-level принцип для confirmation-like відповідей зафіксовано в `docs/Canonical_Decision_Resolver_Contract.md`: усі рішення типу approve/edit/cancel або yes/no мають проходити через спільний Canonical DecisionResolver. Поточні локальні парсери `ano/nie` або `schvalit/upravit/zrusit` вважаються технічним боргом і мають мігрувати після тестів; це не означає, що спільний resolver уже повністю впроваджений у runtime.

Phase 1 migration частково впроваджує цей принцип у runtime: поточні invoice preview/post-PDF, contact confirmation, onboarding confirmation і existing-invoice delete confirmation flows проходять через `bot/services/decision_resolver.py`. Це не додає OfficeFlow Document Intake runtime, Telegram button callbacks, DB schema changes, storage migration або зміну `pdf_path`.

---

## 2. Архітектурна концепція

### 2.1 Current controlled dry-run deployment model

Це активна поточна модель для контрольованого dry run і безпечного onboarding другого реального користувача:
- один shared Telegram bot token (`BOT_TOKEN`);
- один backend process / deployable service;
- одна SQLite DB;
- кілька allowlisted Telegram users через `ALLOWED_TELEGRAM_USER_IDS`;
- strict tenant isolation by `telegram_id` / `supplier_telegram_id`;
- без per-user Telegram bot tokens;
- без public SaaS;
- без public self-service onboarding;
- без automatic signup;
- без збору per-user SMTP credentials.

Unknown Telegram users must be blocked neutrally before onboarding or business data mutation. Unknown users must not create supplier profiles, contacts, invoices, invoice PDFs, accounting documents, metadata, temporary upload files, tenant storage directories, or any other business/runtime artifacts, and must not trigger LLM, STT, or LMM calls.

This controlled shared-bot model is the current runtime model for safely onboarding the second user. It does not replace the future commercial / installation-as-a-service deployment model.

Ціль цієї версії:
- отримати живий продукт;
- пройти повний user flow на реальних даних власника;
- безпечно додати другого контрольованого користувача;
- перевірити tenant isolation перед будь-яким ширшим onboarding;
- на цій основі приймати окреме рішення про майбутнє комерційне розгортання та кастомізацію.

### 2.2 Future commercial / installation-as-a-service deployment model

Після успішного MVP базове ядро може підтримувати future commercial / installation-as-a-service model. Це не поточний runtime:
- один клієнт = один інстанс або інша окрема deployment/workspace одиниця;
- possible separate Telegram bot token per client;
- possible per-client VPS/container/workspace;
- possible separate DB/storage/API keys/secrets per client;
- окремі налаштування;
- окремі реквізити;
- окремий prompt/context;
- окремий словник скорочень;
- окремі сценарії;
- possible SaaS/admin UI, billing, support tooling, and stronger secrets management.

Ця future commercial / installation-as-a-service model не є поточним dry-run runtime і не є Phase 2 access-request automation. Її не можна трактувати як уже реалізовану або як вимогу для контрольованого другого користувача. Per-client Telegram bot tokens, per-client VPS/container, and per-client API keys are future/commercial options only.

OfficeFlow framing додає майбутні поняття `workspace` і `supplier profile` як документаційну модель, але не реалізує multi-workspace або multi-supplier runtime у межах поточного FakturaBot MVP. Поточний робочий supplier profile для SZČO Mykhailo Alieksieienko залишається чинним.

### 2.3 Стек технологій

| Компонент | Технологія |
|-----------|-----------|
| Мова | Python 3.11+ |
| Telegram | aiogram 3.x |
| STT | Whisper API |
| LLM-парсинг | OpenAI API / Claude API |
| PDF | reportlab |
| QR-код (Pay by Square) | internal PAY by square encoder + qrcode |
| Email | smtplib (SMTP/TLS) |
| База даних | SQLite |
| Деплой | Docker |

### 2.4 Що НЕ входить у першу версію

У v1.0 не входить:
- класичний SaaS,
- multi-tenant архітектура,
- lookup контрагентів з інтернету,
- FinStat,
- ORSR інтеграція,
- OCR як окремий складний модуль,
- автоматичне підтягування даних з реєстрів,
- Google Drive,
- складні звіти,
- billing,
- кабінет користувача.

---

## 3. Концепція MVP v1.0

### 3.1 Що входить у першу версію

Обов’язково:
- Telegram-бот,
- голосові повідомлення,
- текстові повідомлення,
- розпізнавання голосу в текст,
- AI-побудова invoice draft,
- ручне додавання постачальника,
- ручне додавання контрагента,
- додавання контрагента з договору через AI,
- локальна адресна книга,
- збереження оригіналу договору в локальне сховище,
- генерація PDF з QR-кодом Pay by Square,
- прев’ю перед підтвердженням,
- відправка PDF на email контрагента,
- історія фактур,
- статуси фактур,
- автонумерація фактур (RRRRNNNN, послідовна číselná rada).

### 3.2 Що свідомо відкладено

У v1.0 не робиться:
- підтягування компаній з інтернету,
- пошук через ORSR / ŽRSR / FinStat,
- повний OCR-конвеєр,
- універсальний парсинг будь-яких документів,
- Google Drive,
- складна бухгалтерська аналітика,
- повноцінна багатокористувацька рольова система.

---

## 4. Основні сценарії користувача

### 4.1 Онбординг постачальника

Перший запуск бота повинен зібрати реквізити постачальника.

На v1.0 основний сценарій — **вручну**.

Поля:
- ім’я / obchodné meno,
- IČO,
- DIČ,
- IČ DPH,
- адреса,
- IBAN,
- SWIFT/BIC,
- email,
- стандартна splatnosť у днях.

Зберігається один профіль постачальника.

### 4.2 Додавання контрагента вручну

Користувач вручну вводить:
- назву компанії,
- адресу,
- IČO,
- DIČ,
- IČ DPH,
- email,
- контактну особу.

Після підтвердження бот зберігає картку у локальній БД.

### 4.3 Додавання контрагента з договору

Це один із ключових сценаріїв оновленої концепції.

Flow:
1. Користувач надсилає PDF або фото договору.
2. Python зберігає оригінал у `storage/contracts/` (для архіву).
3. Python витягує текст із документа (для text-based PDF — PDF text extraction; для фото або scan-PDF — vision/OCR fallback).
4. Python викликає AI з чітким промптом.
5. AI повинен знайти саме **замовника / objednávateľ**, а не виконавця / zhotoviteľ.
6. AI повертає строго структурований JSON.
7. Python валідовує поля (IČO = 8 цифр, DIČ = 10 цифр, назва не порожня).
8. Бот показує картку контрагента.
9. Користувач підтверджує або редагує.
10. Контрагент зберігається в локальній БД з посиланням на оригінал договору.

#### 4.3.1 Критичний принцип

Дані з договору **ніколи не зберігаються автоматично без підтвердження користувача**.

#### 4.3.2 Модель роботи

Не робити «OCR все вирішив».

Правильна модель:

**Python orchestrates → AI extracts → Python validates → user reviews/edits draft → user approves final generation**

### 4.4 Створення фактури голосом

Це центральний wow-сценарій продукту.

Приклад диктування:

> «Тесла Словакія за оправи один кус там 2000 євр, датум виставлення 30 марта 2026, сплатност 30 днів»

#### 4.4.1 Що повинен зробити бот

1. Прийняти голосове повідомлення.
2. Віддати його в Whisper.
3. Отримати текст.
4. Передати текст у LLM.
5. Побудувати чернетку фактури.
6. Нормалізувати значення.
7. Показати чернетку користувачу як `Náhľad faktúry`.
8. У preview показати proposed номер фактури у форматі `Číslo faktúry: <number> (návrh)`.
9. Прийняти preview-stage рішення: `schváliť`, `upraviť` або `zrušiť`.
10. Якщо користувач обирає `upraviť`, редагувати FSM draft і знову показати оновлений `Náhľad faktúry`.
11. Якщо користувач обирає `zrušiť`, скасувати draft без створення invoice row і без PDF.
12. Якщо користувач обирає `schváliť`, перевірити номер, створити final invoice row, присвоїти final number і згенерувати PDF.

Backward compatibility:
- `ano` у preview трактується як `schváliť`;
- `nie` у preview трактується як `zrušiť`.

Decision normalization for preview/post-PDF states:
- Python first applies local deterministic markers before trusting LLM output.
- Clear save/approve markers (`zachovať`, `uložiť`, `uloz`, `save`, `save changes`, `зберегти`, `збережи`, `сохрани`, `сохранить изменения`) map to `schvalit`.
- Clear edit markers (`upraviť`, `opravit`, `edit`, `change`, `редагувати`, `відредагувати`, `исправить`, `изменить`) map to `upravit`.
- Clear cancel markers (`zrušiť`, `cancel`, `скасувати`, `отменить`, `nie`, `ні`, `нет`) map to `zrusit`.
- Nouns like `zmeny` / `зміни` / `изменения` must not by themselves override an explicit save marker.
- If local markers conflict, Python must return `unknown` and ask the user to clarify instead of guessing.

До `schváliť` invoice row, final invoice number і PDF не створюються. Preview number є тільки proposed number, збереженим у FSM `invoice_draft`.

Правило proposed invoice number у draft stage:
- proposed number не резервується в DB;
- якщо користувач вручну редагує `číslo faktúry`, draft отримує `invoice_number_manual_override = true`;
- якщо користувач редагує `Dátum vystavenia` і `invoice_number_manual_override = false`, proposed number перераховується відповідно до нового року `Dátum vystavenia`;
- якщо `invoice_number_manual_override = true`, редагування `Dátum vystavenia` не перераховує proposed number автоматично;
- на `schváliť` Python перевіряє, що proposed/final number досі вільний.

#### 4.4.2 Які поля повинні витягуватись

- контрагент,
- назва роботи / позиції,
- кількість,
- одиниця,
- сума,
- валюта,
- дата dodania / виконання,
- кількість днів до сплатності,
- обчислена дата сплатності.

#### 4.4.3 Правила інтерпретації дат

- `Dátum vystavenia` = дата створення фактури; бот ставить її автоматично завжди.
- Якщо в повідомленні користувача є дата, вона трактується як `Dátum dodania`.
- Якщо дата в повідомленні не вказана, тоді `Dátum dodania = Dátum vystavenia`.
- `Dátum splatnosti = Dátum vystavenia + splatnosť XX dní`.
- Якщо AI повернув `Dátum dodania`, який старший за `Dátum vystavenia` більше ніж приблизно на 2 місяці, Python не приймає такий рік без явного підтвердження у raw/STT-тексті; у разі сумніву бот просить уточнити дату.
- Якщо `Dátum dodania` виходить більше ніж приблизно на 3 місяці в майбутньому від `Dátum vystavenia`, Python також вимагає явне підтвердження року у raw/STT-тексті; інакше бот просить уточнити дату.

### 4.5 Створення фактури текстом

Користувач може писати короткі інструкції вручну. Логіка така сама:

**text/voice → action resolution + content/value canonicalization (Bounded Semantic Canonicalization) → Python validation/execution → draft preview/edit → final approval → PDF**

`Semantic Action Resolver` покриває лише вибір дії; структуровані поля фактури окремо проходять semantic value/content canonicalization перед Python validation та execution.

### 4.6 Робота тільки з локально збереженими контрагентами

У v1.0 бот не шукає контрагентів у реєстрах щоразу.

Правильна модель:
- контрагент додається один раз,
- підтверджується,
- зберігається локально,
- далі використовується тільки локальна картка.

Зовнішні джерела в першій версії не є частиною критичного flow.

### 4.7 Full `edit_invoice` / `upraviť` edit surface map (docs-first contract)

`edit_invoice` залишається **reserved top-level action token**.

Runtime-модель для цього токена: тільки bounded in-action/subflow edits в межах invoice flow, а не окремий top-level executor. Основний happy path тепер редагує draft на етапі preview / `Náhľad faktúry`; post-PDF edit-flow лишається compatibility/fallback шляхом.

Це важливо:
- це **не** нова top-level action;
- це **не** add item flow;
- add item свідомо винесений за межі цього docs patch.

#### 4.7.1 A) Invoice-level edit operations

Canonical machine-facing operations:
- `edit_invoice_number`
- `edit_invoice_issue_date`
- `edit_invoice_delivery_date`
- `edit_invoice_due_date`
- `edit_invoice_date` (clarification-only umbrella intent)
- `edit_invoice_contact`
- `unknown`

Статус:
- `edit_invoice_number` — implemented;
- `edit_invoice_issue_date` — implemented;
- `edit_invoice_delivery_date` — implemented;
- `edit_invoice_due_date` — implemented;
- `edit_invoice_date` — implemented as clarification trigger (`Ktorý dátum chcete upraviť...`);
- `edit_invoice_contact` — planned (not yet implemented).

Fail-safe рішення для invoice-level полів:
- ці операції є integrity-sensitive;
- при неоднозначності/конфлікті Python має fail loud (з bounded clarification), без silent auto-fix;
- інваріанти нумерації, дат і contact linkage не можна “тихо виправляти”.

#### 4.7.2 B) Item-level edit operations

Canonical machine-facing operations:
- `replace_service`
- `edit_item_description`
- `edit_item_quantity`
- `edit_item_unit_price`
- `edit_item_total_amount`
- `unknown`

Статус:
- implemented: `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`.

#### 4.7.3 Операційна семантика item-level

**A) `replace_service` (replace service alias / canonical service)**
- змінює service identity позиції;
- оновлює canonical service term для item;
- може оновити short service name (де застосовно);
- повний display title має резолвитись із service alias / service dictionary.

**B) `edit_item_description` (edit free-text item detail)**
- змінює тільки optional manual detail field `item_description_raw`;
- це manual free-text;
- це не canonical alias;
- це не зміна service dictionary.

Для `edit_item_description` обов’язкові mutation modes:
- `set`,
- `replace`,
- `clear`.

**C) `edit_item_quantity` / `edit_item_unit_price` / `edit_item_total_amount`**
- змінюють тільки відповідне поле item;
- не повинні руйнувати arithmetic/business invariants;
- при нерозв’язному конфлікті — fail loud + bounded clarification.

#### 4.7.4 Precision-sensitive policy + item targeting

Precision-sensitive item fields:
- `item_description_raw`
- `edit_item_quantity`
- `edit_item_unit_price`
- `edit_item_total_amount`

Правила:
- precision-sensitive поля — text-first там, де voice може спотворити значення;
- voice не повинен “вгадувати” фінальні значення для precision-sensitive полів;
- для ambiguous voice input бот переходить на bounded Slovak prompt і просить текст.

Item targeting контракт:
- precision-sensitive item-level edits вимагають item targeting;
- single-item invoices можуть за замовчуванням таргетити перший item;
- multi-item invoices вимагають explicit item selection або bounded clarification.

#### 4.7.5 Data/model + render contract

- canonical service/title семантика зберігається без підміни;
- `item_description_raw` лишається окремим optional detail полем;
- головний service title береться з service alias/service DB;
- optional `item_description_raw` рендериться під головним title;
- detail text обмежений максимум 2 rendered lines;
- silent truncation заборонений; якщо не вміщується — bounded prompt на скорочення тексту.

#### 4.7.6 Minimal canonical contract block for `edit_invoice:subflow`

Machine-facing мінімальний bounded contract:
- `target_item_index`
- `operation`
- `value`

Де:
- `operation` ∈ {`edit_invoice_number`, `edit_invoice_issue_date`, `edit_invoice_delivery_date`, `edit_invoice_due_date`, `edit_invoice_date`, `edit_invoice_contact`, `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`, `unknown`};
- `target_item_index` обов’язковий для item-level операцій (для invoice-level ігнорується/`unknown`);
- `value` завжди candidate-only; Python робить final validation/execution або fail loud.

#### 4.7.7 Explicit implementation boundary for this docs map

- Цей docs patch фіксує єдину карту повного `edit_invoice` scope для майбутніх runtime патчів.
- У runtime досі не реалізована: `edit_invoice_contact`.
- Поточний runtime coverage у межах `upraviť`: `edit_invoice_number`, `edit_invoice_issue_date`, `edit_invoice_delivery_date`, `edit_invoice_due_date`, `edit_invoice_date` (clarification), `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`.
- Для invoice-level date edits застосовується bounded LLM normalization contract:
  - input: natural-language/text/STT date phrase;
  - output: тільки `DD.MM.RRRR` або `unknown`;
  - Python виконує тільки strict validate/parse та persistence/reject (без Python semantic date guessing).
- Guardrail: `dátum splatnosti` не може бути раніше за `dátum vystavenia` (fail-loud reject).
- Поточна поведінка для номеру фактури при зміні дати: номер **не змінюється автоматично** (без hidden auto-renumbering).

---

## 5. Роль AI у системі

### 5.1 Технічний контракт використання AI

У FakturaBot AI працює як **Semantic Action Resolver** в моделі **Bounded Semantic Canonicalization**:
- Python передає поточний state/context,
- Python передає дозволені канонічні дії або значення,
- LLM повертає тільки один дозволений канонічний вихід або `unknown`,
- Python виконує перевірку, state-check і side effects.

### 5.2 Єдиний семантичний шар (цільовий напрям)

Один і той самий підхід має уніфікувати:
- top-level action resolution (`create_invoice`, `add_contact`, `send_invoice`, `edit_invoice`),
- top-level action resolution (`create_invoice`, `add_contact`, `send_invoice`, `edit_invoice`, `edit_existing_invoice`),
- reply-state resolution (`ano`/`nie`, `schvalit`/`upravit`/`zrusit`),
- value/slot canonicalization (наприклад: `oprava`, `revizia`, `servis`).

### 5.3 Невідмінне правило безпеки

Навіть якщо LLM повернув канонічну дію (`zrusit`, `schvalit`, `send_invoice`),
виконання дозволене тільки Python після валідації контексту.

LLM не має права:
- виконувати side effects,
- змінювати DB/FSM напряму,
- позначати операцію як завершену.

### 5.4 Мовна політика

- Вхід користувача може бути multilingual/mixed/noisy/STT-distorted.
- Відповіді бота користувачу — словацькою.
- Сирий transcript може зберігатися окремо як trace/debug.
- Внутрішні канонічні виходи — тільки project-defined canonical tokens.

### 5.5 Обов’язкова вимога для structured workflows: slot-level clarification

Для кожного structured workflow (invoice, contact intake, create contract, майбутні structured assistant actions) обов’язково визначати:
- required slots;
- recoverable slot failures;
- fatal failures;
- partial draft retention behavior;
- clarification continuation behavior.

Обов’язковий контракт:
- якщо unresolved лише один slot і решта draft придатна — workflow не скидається повністю;
- Python зберігає partial draft/state;
- бот просить тільки unresolved slot;
- після уточнення workflow продовжується з поточного кроку;
- full reset дозволений тільки для fatal помилок.

### 5.6 Неоднозначні top-level actions: optional semantic hints

Для top-level bounded action resolution дозволяється використовувати компактні semantic action hints, якщо дія семантично неоднозначна в шумному multilingual вводі.

Правила:
- це **опційний** інструмент, не обов’язковий для кожної дії;
- застосовується вибірково, коли plain allowed-actions недостатньо для стабільного bounded розпізнавання;
- canonical bot wording і noisy user examples повинні бути чітко розділені в документації.

### 5.7 Planned `info_help` guidance/navigation/recovery layer (high-level TZ alignment)

`info_help` у плані продукту — це bounded guidance/navigation/recovery шар, а не free-form chat mode і не дубль direct top-level actions.

Routing precedence (обов’язково):
- top-level action resolution виконується першим;
- форма питання не блокує прямий action-routing (`"How do I create..."` може резолвитись у direct action);
- `info_help` використовується тільки коли top-level resolver повернув `unknown`;
- direct actions лишаються direct, без штучного перенесення в info-layer.

Поведінка planned `info_help` на рівні TZ:
- відповіді на informational usage/capability питання;
- навігація до linked actions/subtargets (лише через safe handoff правила);
- truthful planned-feature/unsupported notices;
- guidance для recovery/reset/start-over сценаріїв.

Contract precedence:
- усі `info_help` взаємодії залишаються підпорядкованими bounded Python→LLM контракту (`docs/llm`);
- цей шар не послаблює і не обходить існуючі contract rules.

Capability status для guidance topics:
- `implemented`
- `planned`
- `unsupported`

Вимога truthfulness:
- user-facing відповідь повинна відповідати фактичному status;
- не можна представляти planned/unsupported як implemented.

Logging requirement (product signal):
- кожен вхід у `info_help` має логуватись як structured product signal для подальшого аналізу UX/roadmap.

Phase 2/3 future direction (high-level):
- state-aware guidance + reset/new-task допомога;
- bounded runtime explainability через sanitized Python-prepared facts;
- explicit заборона на arbitrary source-code reading або arbitrary raw-log reading з боку LLM у цьому шарі.

Caution for unconfirmed runtime coverage in info/guidance answers:
- dedicated end-to-end edit existing contact details flow;
- historical old-invoice deletion as user-facing feature;
- send-invoice/send-email style capability;
- support/ticket escalation workflow.
Поки runtime-реалізація не підтверджена — ці пункти мають відповідатися як planned/unsupported, без overstatement.

Детальна архітектура і behavioral contract для planned `info_help` визначені в:
- `docs/Info_Help_Guidance_Layer.md`
TZ фіксує high-level product/requirements alignment і не дублює повний детальний spec.

---

## 6. Структура чернетки фактури

### 6.1 Мінімальна модель invoice draft

```json
{
  "customer_name": "TECH COMPANY, s. r. o.",
  "item_name_raw": "оправи",
  "item_name_normalized": "Opravy vyhradených technických zariadení elektrických",
  "quantity": 1,
  "unit": "ks",
  "amount": 2000.0,
  "currency": "EUR",
  "delivery_date": "2026-03-30",
  "issue_date": "2026-03-30",
  "due_days": 30,
  "due_date": "2026-04-29"
}
```

### 6.1.1 Dual-shape multi-item intake (Phase 1, bounded)

Поточний runtime для create/invoice intake підтримує backward-compatible dual-shape:
- singleton shape залишається валідним;
- optional bounded `biznis_sk.items[]` підтримується для candidate multi-item intake.

Contract decisions:
- Backward compatibility обов’язкова:
  - існуючий singleton shape лишається валідним;
  - додається опційний bounded `biznis_sk.items[]` для candidate multi-item extraction;
  - list-only hard cutover не входить у цей етап.
- Python лишається execution/workflow owner:
  - LLM може повертати лише bounded candidate item segmentation;
  - LLM не приймає рішення про persistence/side effects;
  - Python валідовує boundaries, numeric coherence, totals, max item count, render safety.
- Safe outcomes:
  - accept + continue,
  - bounded clarification,
  - safe fallback (без silent merge/guess).

Phase 1 bounds:
- `items[]` max size = 3;
- без open-ended extraction довільної кількості позицій;
- при перевищенні bounds або неоднозначності — bounded clarification/fallback.

Candidate item shape (conceptual, machine-safe):
- `polozka_povodna`,
- `termin_sluzby_sk`,
- `mnozstvo`,
- `jednotka`,
- `cena_za_jednotku`,
- `suma`,
- optional future-compatible `item_description_raw`.

Split semantics rules:
- `montáž dva razy po 1000` => одна позиція (`mnozstvo=2`, `cena_za_jednotku=1000`);
- `oprava 3000 a montáž 1000` => дві candidate позиції;
- `oprava 3000, montáž 2x1000` => дві candidate позиції (друга з multiplier semantics);
- якщо межі позицій або quantity semantics неясні — Python запитує bounded clarification.

Fail-safe triggers (no silent auto-accept):
- ambiguous boundaries;
- ambiguous quantity semantics;
- ambiguous service resolution по будь-якій позиції;
- total incoherence (per-item або aggregate);
- render/page safety exceeded.

Runtime follow-up areas (future patches):
- richer bounded clarification for complex multi-item boundary ambiguity,
- stricter render/page-fit guards for larger real-world item text,
- optional per-item detail extraction policy hardening.

Правила дат для invoice draft:
- `issue_date` відповідає `Dátum vystavenia` і завжди ставиться ботом автоматично в момент створення фактури.
- Дата, яку користувач продиктував або написав у повідомленні, інтерпретується як `delivery_date` (`Dátum dodania`).
- Якщо користувач не вказав дату, `delivery_date` дорівнює `issue_date`.
- `due_date` обчислюється як `issue_date + due_days`.

### 6.2 Принцип preview

Будь-яка фактура проходить flow:

**draft → PDF preview → schváliť / upraviť**

Після генерації faktúry і PDF бот обов’язково дає її користувачу на перевірку.

На етапі preview користувач повинен бачити:
- контрагент,
- позиція,
- кількість,
- сума,
- дата dodania,
- дата виставлення,
- дата сплатності.

Доступні дії:
- `schváliť`
- `upraviť`

### 6.3 Explicit edit of existing persisted invoice by number

- Existing/finalized invoice edit is entered only by explicit command semantics (`upraviť faktúru 15`, `uprav faktúru číslo 20260015`, etc.).
- LLM responsibility is bounded to intent detection + extracting number reference text; LLM must not query DB.
- Python normalizes reference and searches supplier-scoped invoices by numeric suffix (`15` -> `...0015`) or full number.
- If 0 matches: `Faktúru s týmto číslom som nenašiel.`
- If >1 matches: `Našiel som viac faktúr. Napíšte celé číslo faktúry.`
- If exactly 1 match:
  1) load current persisted invoice data;
  2) show current invoice summary before edit menu;
  3) optionally send current PDF preview when stored `pdf_path` file is available;
  4) then open persisted edit-flow (`start_invoice_edit_flow`) without creating new draft.
- Current invoice summary must include:
  - invoice number,
  - customer/contact,
  - dates (issue/delivery/due),
  - item lines,
  - quantities,
  - unit prices,
  - item totals,
  - invoice total.
- Missing `pdf_path` or missing PDF file must not block entering persisted edit-flow.
- This does not restore post-PDF menu after each new invoice; explicit entrypoint only.

---

## 6.3 QR-код Pay by Square

Кожна PDF-фактура містить QR-код стандарту Pay by Square (Slovenská banková asociácia).

QR-код генерується автоматично з полів:
- IBAN постачальника (з профілю),
- suma k úhrade,
- variabilný symbol = číslo faktúry,
- dátum splatnosti,
- mena (EUR).

Реалізація: internal Python encoder (`bot/services/pay_by_square.py`) + `qrcode`.

Мінімальні required поля для payload у FakturaBot:
- IBAN,
- Amount (> 0),
- Currency (`^[A-Z]{3}$`),
- Variable symbol (numeric, max 10),
- Due date (`YYYY-MM-DD` → payload date),
- Beneficiary name (non-empty).

Якщо валідація не проходить — генерація payload зупиняється з явним exception (fail-loud), без fallback-placeholder.

Клієнт контрагента сканує QR у банківській аплікації → платіжний príkaz заповнений автоматично.

---

## 6.4 Відправка на email

Після підтвердження чернетки бот показує:

```
📄 Faktúra č. 20260015
Odberateľ: TECH COMPANY, s. r. o.
Suma: 2 000,00 €
Splatnosť: 29.04.2026

[✅ Odoslať na email] [💾 Len uložiť] [❌ Zrušiť]
```

При натисканні "Odoslať na email":
1. Бот відправляє email на адресу контрагента з БД.
2. Тема: `Faktúra č. 20260015 — [Názov dodávateľa]`
3. Тіло (словацькою): привітання + сума + splatnosť + подяка.
4. Вкладення: PDF фактура.
5. Бот підтверджує: "✅ Faktúra odoslaná na novak@firma.sk"

Per-user SMTP host/user/password collection is deprecated. Supplier onboarding collects only the business email; future sending should use a centralized transactional provider such as Postmark or equivalent.

---

## 6.5 Автонумерація фактур

Формат: `RRRRNNNN` (рік + послідовний номер).

Приклад: `20260001`, `20260002`, ... `20260099`.

Номер автоматично інкрементується. Скид лічильника — 1 січня кожного року.
Номер фактури присвоюється тільки в момент фінального підтвердження і збереження, а не на етапі draft.
Číselná rada послідовна, без пропусків — відповідно до вимог словацького законодавства.

---

## 6.6 Збереження договору

При додаванні контрагента з договору оригінальний файл (PDF або фото) зберігається в `storage/contracts/`.

Формат імені: `{ICO}_{date}_{original_filename}`

Приклад: `47983973_20260330_zmluva_tech_company.pdf`

Шлях записується в таблицю `contact.contract_path`. Це дає:
- архів договорів для účtovníka,
- можливість перевірити витягнуті дані пізніше,
- юридичне підтвердження реквізитів.

OfficeFlow storage proposal розглядає договори як long-living workspace/master-data documents, а не як документи, обов’язково прив’язані до одного року. Це поки лише proposal; поточний runtime і надалі використовує `storage/contracts/`.

---

## 7. Витяг контрагента з договору

### 7.1 Контракт взаємодії з AI

Для сценарію витягу з договору діє той самий bounded-контракт:
- Python передає AI поточний контекст задачі та дозволені канонічні значення полів/ролей,
- LLM повертає лише одне канонічне значення на поле або `unknown`,
- Python виконує валідацію, рольову перевірку (`objednavatel`), і тільки потім дозволяє user confirmation/save.

### 7.2 Очікуваний JSON

```json
{
  "company_name": "TECH COMPANY, s. r. o.",
  "address": "Oravské Veselé 966, 029 62 Oravské Veselé",
  "ico": "47983973",
  "dic": "2024169488",
  "ic_dph": "SK2024169488",
  "statutory_person": "Tomáš Sameliak",
  "email": "",
  "role_detected": "objednavatel"
}
```

### 7.3 Валідація після AI

Python повинен перевіряти:
- чи знайдено саме замовника,
- чи не порожня назва,
- чи IČO має валідний формат,
- чи IČ DPH не схоже на випадковий текст,
- чи не витягнуті реквізити виконавця замість замовника.

### 7.4 Остаточна логіка

Навіть при високому confidence дані лише пропонуються, а не зберігаються автоматично.

---

## 8. База даних

### 8.1 Таблиця supplier

Містить профіль постачальника.

Мінімальні поля:
- id,
- telegram_id,
- name,
- ico,
- dic,
- ic_dph,
- address,
- iban,
- swift,
- email,
- smtp_host,
- smtp_user,
- smtp_pass (шифровано; ключ шифрування не зберігається в БД і передається через безпечну конфігурацію середовища),
- days_due,
- created_at,
- updated_at.

### 8.2 Таблиця contact

Містить локальні картки контрагентів.

Мінімальні поля:
- id,
- supplier_id,
- name,
- ico,
- dic,
- ic_dph,
- address,
- email,
- contact_person,
- source_type,
- source_note,
- contract_path (шлях до оригіналу договору, nullable),
- created_at,
- updated_at.

`source_type` може мати значення:
- `manual`,
- `contract_ai`.

### 8.3 Таблиця invoice

Мінімальні поля:
- id,
- supplier_id,
- contact_id,
- invoice_number,
- issue_date,
- due_date,
- total_amount,
- currency,
- status,
- pdf_path,
- created_at,
- updated_at.

### 8.4 Таблиця invoice_item

У першій версії достатньо підтримати **одну позицію на фактуру**, але технічна структура може вже бути табличною.

Мінімальні поля:
- id,
- invoice_id,
- description_raw,
- description_normalized,
- item_description_raw (optional manual free-text detail below canonical service title; не alias і не dictionary-term),
- quantity,
- unit,
- unit_price,
- total_price.

Примітка для Phase 1 item edit contract:
- поточний single-item draft може дефолтно редагувати перший item;
- модель зберігається future-ready для multi-item через item-targeted edits.

---

## 9. Модулі системи

### 9.1 Обов’язкові модулі v1.0

- bot core,
- speech-to-text,
- LLM draft parser,
- contract extractor (AI витяг реквізитів + збереження оригіналу),
- contacts,
- supplier profile,
- invoices,
- PDF generator з QR-кодом Pay by Square,
- email sender,
- validation layer,
- SQLite storage.

У майбутньому OfficeFlow framing цей набір відповідає модулю **FakturaBot / Outgoing Invoices**.

Для всіх модулів, які приймають confirmation-like відповіді користувача, цільова архітектура вимагає shared Canonical DecisionResolver. Нові модулі не повинні додавати власні локальні парсери підтверджень.

### 9.2 Відкладені модулі

Модулі, які не є обов’язковими для v1.0:
- Google Drive,
- external company lookup,
- OCR pipeline,
- Document Intake / expenses,
- bank statement intake,
- document categories,
- e-faktura 2027,
- extended reports.

Document Intake описується окремо як docs-first future module для bločkov, prijatých faktúr, zmlúv і bankových výpisov. Він не реалізований у поточному runtime.

---

## 10. Структура проекту

```text
faktura-bot/
├── bot/
│   ├── main.py
│   ├── handlers/
│   │   ├── onboarding.py
│   │   ├── contacts.py
│   │   ├── contracts.py
│   │   ├── invoice.py
│   │   └── settings.py
│   ├── services/
│   │   ├── whisper.py
│   │   ├── llm_invoice_parser.py
│   │   ├── llm_contract_extractor.py
│   │   ├── pdf_generator.py        # PDF + Pay by Square QR
│   │   ├── email_sender.py         # SMTP відправка з PDF-вкладенням
│   │   └── validation.py
│   ├── models/
│   │   ├── database.py
│   │   ├── supplier.py
│   │   ├── contact.py
│   │   └── invoice.py
│   └── config.py
├── storage/
│   ├── invoices/                    # Згенеровані PDF-фактури
│   ├── contracts/                   # Оригінали договорів (PDF/фото)
│   └── uploads/                     # Тимчасові файли
├── prompts/
│   ├── invoice_draft_prompt.txt
│   └── contract_customer_prompt.txt
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

Майбутня OfficeFlow storage model описана в `docs/OfficeFlow_Storage_Model_Proposal.md` як non-runtime proposal. Вона не переносить існуючі PDF, не змінює `pdf_path` і не створює yearly folders у поточному коді.

---

## 11. Безпека

### 11.1 Базовий принцип

Усі зовнішні дані вважаються недовіреними:
- голос,
- текст,
- PDF,
- фото договору,
- відповідь LLM.

### 11.2 Критичні правила

- AI ніколи не зберігає дані напряму в БД.
- Усі результати AI проходять Python-валідацію.
- Усі важливі дії потребують підтвердження користувача.
- Дані контрагентів беруться з локальної БД, а не з інтернету.
- Перша версія не залежить від зовнішніх lookup-сервісів.

### 11.3 Захист від помилкових витягів

Для договорів обов’язково перевіряється, щоб:
- не переплутати `objednávateľ` і `zhotoviteľ`,
- не зберегти власні реквізити користувача як контрагента,
- не створити контакт без назви та базових реквізитів.

---

## 12. Стратегічний висновок

FakturaBot v1.0 — це не спроба побудувати великий SaaS, а **живий демонстраційний продукт**, який:
- реально вирішує задачу автора,
- показує wow-ефект через голос,
- витягує контрагентів з договорів і зберігає оригінали,
- створює PDF-фактури з QR-кодом Pay by Square,
- відправляє фактуру на email одним натиском,
- демонструє підхід до кастомних Telegram-ботів для малого бізнесу.

Після цієї версії продукт може розвиватися двома напрямками:
1. як індивідуально налаштований FakturaBot для клієнтів,
2. як ядро для інших ботів під конкретні бізнес-процеси.

---

## 13. Документаційний супровід проєкту

У репозиторії обов'язково ведеться PROJECT_LOG.md.

Після кожної змістовної сесії фіксуються:
- прийняті рішення,
- зміни scope,
- відкладені модулі,
- уточнення архітектури,
- наступні кроки.

Зміни, що впливають на продуктову логіку або межі MVP, мають відображатися і в PROJECT_LOG.md, і в цьому ТЗ.

---

## 14. Підсумок рішень, зафіксованих у цьому оновленні

1. Повноцінний масовий SaaS на старті відкинуто.  
2. Перший інстанс розгортається для самого автора.  
3. Голосовий сценарій є обов’язковою частиною MVP.  
4. Lookup компаній з інтернету (FinStat, ORSR) у v1.0 не використовується — API платний, парсинг з договору достатній.  
5. Додавання контрагента з договору через AI + validation + confirmation. Оригінал договору зберігається.  
6. Дані контрагентів надалі беруться з локальної БД.  
7. AI використовується як інструмент побудови чернетки, а не як автономний виконавець.  
8. PDF-фактура обов’язково містить QR-код Pay by Square.  
9. Email-відправка є частиною MVP (не відкладений модуль).  
10. Продукт мислиться як частина ширшої моделі кастомних ботів для малого бізнесу.  
11. Для test/dev операцій додано явну дію `delete_existing_invoice` з обов’язковим підтвердженням `áno/nie` та supplier-scoped пошуком за суфіксом/повним номером.  

## 2026-05-02 Controlled Two-User Dry Run Addendum

Current controlled multi-user model for the next dry run:
- one shared backend/codebase;
- one Telegram bot token for now;
- one SQLite DB for now;
- Phase 1 access only for Telegram users listed in bootstrap `ALLOWED_TELEGRAM_USER_IDS`;
- Phase 2 may add admin-approved access without `.env` edits only when the current code and `PROJECT_LOG.md` confirm it is implemented/deployed;
- no public self-service onboarding;
- deterministic tenant isolation by `telegram_id` / `supplier_telegram_id`.

This is not full SaaS multi-tenancy. Out of scope for this step:
- multiple bot-token orchestration;
- workspace admin UI;
- billing;
- Postmark integration;
- encrypted secret vault for per-tenant secrets;
- bank-statement matching;
- expense categorization.

Python remains the source of truth for authorization, tenant identity, DB filters, invoice-number generation, file-path generation, duplicate checks, and persistence. LLM/STT may help with bounded extraction or action/value resolution only after the Telegram user is authorized, and must not decide authorization or tenant identity.

Tenant-sensitive runtime rules:
- invoice numbers are unique per supplier: `UNIQUE(supplier_telegram_id, invoice_number)`;
- the same invoice number may exist for different suppliers;
- invoice PDF files are stored under `storage/invoices/{supplier_telegram_id}/{invoice_number}.pdf`;
- accounting document confirmed storage uses a tenant workspace key such as `telegram-{supplier_telegram_id}`;
- accounting document temporary upload staging is tenant-scoped before any LMM call or confirmed save;
- contact and supplier profile operations are scoped to the current Telegram user.

Legacy per-user SMTP credential collection is deprecated for the dry run. Supplier onboarding collects only the business email. Existing DB columns `smtp_host`, `smtp_user`, and `smtp_pass` remain for compatibility but are unused by the dry-run flow and should be cleared if legacy values exist:

```sql
UPDATE supplier
SET smtp_host = NULL,
    smtp_user = NULL,
    smtp_pass = NULL;
```

Future email sending should use a centralized transactional email provider, for example Postmark or equivalent, with a project-owned sender domain and DKIM/DMARC/Return-Path configured later. Per-user SMTP credentials must not be collected in onboarding.

## 2026-05-02 Controlled Access-Request Onboarding Addendum

This section specifies Phase 2 controlled onboarding automation. Do not treat it as the current dry-run model unless the current code and `PROJECT_LOG.md` confirm it is implemented and deployed.

When Phase 2 is implemented, unknown Telegram users may request access through `/start`, but this is not public automatic signup:
- `/start` from an unknown user records or refreshes a minimal `access_requests` row with Telegram metadata only;
- no supplier profile, tenant workspace, contact, invoice, accounting document, temp intake workspace, LLM, STT, or LMM call is created for unknown users;
- the user receives a neutral Slovak message that administrator approval is required;
- configured admins may review pending requests with `/access_requests`;
- configured admins may use `/approve <telegram_id>`, `/reject <telegram_id>`, `/block <telegram_id>`, and `/users`;
- non-admin users cannot run access-management commands.

Authorization model:
- a user is authorized when their Telegram ID is in `ALLOWED_TELEGRAM_USER_IDS`, or when `authorized_users.status = 'active'`;
- a user is an admin when their Telegram ID is in `ADMIN_TELEGRAM_USER_IDS`, or when `authorized_users.role` is `admin`/`owner` and status is `active`;
- blocked users are denied before normal handlers run, even if they previously had access;
- approved users still must complete `/supplier` onboarding before invoice creation.

Operational config:
- `ALLOWED_TELEGRAM_USER_IDS` remains a bootstrap/static allowlist for compatibility and emergency access;
- `ADMIN_TELEGRAM_USER_IDS` is the bootstrap admin configuration;
- real Telegram IDs must be configured in environment variables only, not committed or documented with real values.

Out of scope remains public signup, email/password accounts, billing, payments, SaaS dashboard, multiple Telegram bot tokens, per-user bot-token orchestration, Postmark sending, and automatic tenant creation with full privileges.
