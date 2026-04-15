# Технічне завдання: FakturaBot

## Telegram-бот для створення фактур з голосу, тексту та договору

**Версія:** 2.0 Concept Update  
**Дата:** 30.03.2026  
**Автор:** Mykhailo Alieksieienko

---

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

---

## 2. Архітектурна концепція

### 2.1 Модель стартового розгортання

На першому етапі:
- один сервер,
- один deployable instance / один Docker stack,
- один Telegram-бот,
- один реальний користувач (автор),
- одна локальна база даних.

Реалізаційно це може бути один Docker-контейнер або невеликий Docker stack, але концептуально це один інстанс для одного реального користувача на старті.

Ціль цієї версії:
- отримати живий продукт,
- самому пройти повний user flow,
- показувати демо людям,
- на цій основі продавати розгортання та кастомізацію.

### 2.2 Перспективна модель

Після успішного MVP базове ядро має підтримувати модель:
- один клієнт = один інстанс,
- окремі налаштування,
- окремі реквізити,
- окремий prompt/context,
- окремий словник скорочень,
- окремі сценарії.

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

**Python orchestrates → AI extracts → Python validates → user confirms**

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
7. Показати чернетку користувачу.
8. Після підтвердження створити PDF.

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

### 4.5 Створення фактури текстом

Користувач може писати короткі інструкції вручну. Логіка така сама:

**text/voice → action resolution + content/value canonicalization (Bounded Semantic Canonicalization) → Python validation/execution → preview/PDF**

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

Runtime-модель для цього токена: тільки bounded in-action/subflow edits в межах invoice flow (зазвичай через post-PDF `upraviť`), а не окремий top-level executor.

Це важливо:
- це **не** нова top-level action;
- це **не** add item flow;
- add item свідомо винесений за межі цього docs patch.

#### 4.7.1 A) Invoice-level edit operations

Canonical machine-facing operations:
- `edit_invoice_number`
- `edit_invoice_date`
- `edit_invoice_contact`
- `unknown`

Статус:
- `edit_invoice_number` — implemented;
- `edit_invoice_date` — planned (not yet implemented);
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
- `edit_item_unit`
- `edit_item_unit_price`
- `unknown`

Статус:
- implemented: `replace_service`, `edit_item_description`;
- planned (not yet implemented): `edit_item_quantity`, `edit_item_unit`, `edit_item_unit_price`.

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

**C) `edit_item_quantity` / `edit_item_unit` / `edit_item_unit_price`**
- змінюють тільки відповідне поле item;
- не повинні руйнувати arithmetic/business invariants;
- при нерозв’язному конфлікті — fail loud + bounded clarification.

#### 4.7.4 Precision-sensitive policy + item targeting

Precision-sensitive item fields:
- `item_description_raw`
- `edit_item_quantity`
- `edit_item_unit`
- `edit_item_unit_price`

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
- `operation` ∈ {`edit_invoice_number`, `edit_invoice_date`, `edit_invoice_contact`, `replace_service`, `edit_item_description`, `edit_item_quantity`, `edit_item_unit`, `edit_item_unit_price`, `unknown`};
- `target_item_index` обов’язковий для item-level операцій (для invoice-level ігнорується/`unknown`);
- `value` завжди candidate-only; Python робить final validation/execution або fail loud.

#### 4.7.7 Explicit implementation boundary for this docs map

- Цей docs patch фіксує єдину карту повного `edit_invoice` scope для майбутніх runtime патчів.
- Newly mapped operations (`edit_invoice_date`, `edit_invoice_contact`, `edit_item_quantity`, `edit_item_unit`, `edit_item_unit_price`) у цьому контексті **ще не реалізовані в runtime**.
- Поточний runtime coverage у межах `upraviť`: `edit_invoice_number`, `replace_service`, `edit_item_description`.

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

SMTP налаштовується при онбордингу (Gmail App Password або власний SMTP).

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

### 9.2 Відкладені модулі

Модулі, які не є обов’язковими для v1.0:
- Google Drive,
- external company lookup,
- OCR pipeline,
- e-faktura 2027,
- extended reports.

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
