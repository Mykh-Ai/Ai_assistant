# OfficeFlow / FakturaBot — Architecture Design Proof: підготовка й розрахунок вихідної фактури

**Task ID:** `invoice-preparation-v1`  
**Дата архітектурного рішення:** 2026-11-16  
**Проєкт / база:** `Mykh-Ai/Ai_assistant`, `main` (read-only inspection; deployed VPS revision не перевірено)  
**Статус документа:** узгоджений опис **першого етапу** для implementation agent; це **не доказ реалізації**.  
**Design verdict:** `ready_for_handoff` **після архітектурної поправки 2026-11-16** щодо прив'язки кнопок до версії прев'ю, інвалідації bundle після ручного редагування та сумісного відкату схеми. Попередній агентський вердикт `material_design_variance` був обґрунтований на попередній редакції документа; нову редакцію агент має знову read-only звірити з runtime. Якщо виявлено іншу матеріальну розбіжність — зупинитися.
**Amendment / owner decisions:** 2026-11-16. Нові кнопки invoice-preview прив'язані до ідентичності/версії; ручна правка збереженої фактури не переписує історичну калькуляцію й не вважає її актуальною.  
**Ризик:** medium/high через зміну розрахункових сум і збережених бухгалтерських даних.  
**Нормативні документи:** `AGENTS.md`, `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`, `docs/llm/New_Action_Design_Checklist.md`, `docs/Code_Agent_Handoff_Contract.md`, `docs/Implementation_Agent_Checklist.md`, `docs/Evaluation_and_Smoke_Test_Standards.md`, `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/Canonical_Decision_Resolver_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md` та relevant Product Truth/InfoHelp/PDF/migration docs.

## 1. Бізнес-потреба та видимий результат

Власник зараз надсилає природну текстову або голосову команду й хоче, щоб наявний FakturaBot **підготував розрахунок** перед стандартною генерацією PDF: знайшов пропущену назву послуги з останньої фактури саме цього клієнта, узяв збережену годинну ставку або уточнив її, визначив календарні тижні й дати від **фактичної поточної дати на VPS**, порахував роботу, проживання та чисту суму, заповнив окремий розрахунковий bundle, показав його разом із **непереробленим** старим прев'ю. Лише після чинного підтвердження створити фактуру **тим самим** `generate_invoice_pdf` з **однією кінцевою ціною послуги**.

Current Product Truth: старий `create_invoice` — implemented; новий preparation/calculation — not implemented. Target після тестів — supported для явно описаного підмножини сценаріїв, інакше partial з чесними обмеженнями. **Gmail draft/send та after-send Drive trigger поза цим етапом**; згадки в життєвому документі V2 є перспективними.

## 2. Класифікація архітектури

**Основна класифікація: (2) extension of existing top-level action `create_invoice`.** Допоміжні структуровані Phase-2 slots, enrichment і clarification — піддії всередині чинного маршруту. **Не створювати** `prepare_invoice` або новий canonical top-level action; `send_invoice` залишається зарезервованою, неактивною дією в цьому етапі. Не робити нового PDF-генератора, окремого клієнтського профілю чи паралельного бота. Не розробляти `edit_contact` як самостійний top-level у цьому етапі — це інший approval/handoff.

## 3. Канонічна дія

- Токен: `create_invoice` (існуючий, implemented), runtime owner `bot/handlers/invoice.py::process_invoice_text` і чинна FSM.
- Public entry: idle semantic text/voice, `/invoice` → waiting_input → та сама бізнес-логіка; існуючі callbacks → чинний DecisionResolver.
- Значення: підготувати чернетку вихідної фактури й за підтвердженням зберегти PDF; не надсилати email, не маркувати paid, не архівувати автоматично.
- Питання «як виставити фактуру» або «чи можеш рахувати KW?» — InfoHelp, **не виконання**.

## 4. Semantic Boundary Matrix

| Намір користувача | Правильний маршрут | Не можна |
|---|---|---|
| «Вистав фактуру Techcompany, монтаж, 3000 €» | `create_invoice`; старий повний сценарій без зайвих пошуків | Вигадати години, KW або проживання |
| «Вистав Techcompany за попередні два тижні, 120 год» | `create_invoice` + Phase-2 preparation | Запустити новий top-level, вимагати ручний KW |
| «Не називаю послугу» | Після ідентифікації контакту — взяти одну однозначну послугу з останньої **його** фактури в тому ж workspace | Брати послугу глобально останньої фактури, копіювати старі числа |
| У контакта немає попередніх фактур або там неоднозначні різні послуги | Уточнити назву в поточній FSM, не створюючи PDF | Пропонувати навмання аліаси або вигадати послугу |
| «KW 45/2026» | Явна ISO-пара має найвищий пріоритет і валідується календарем | Заборонити KW як «старіший за останню фактуру» |
| «За попередні два тижні» | Python рахує два останні завершені ISO-тижні з business_today | Взяти рік з пам'яті/дата навчання LLM |
| «Dátum dodania — позавчора / минула п'ятниця» | LLM розпізнає semantics, Python обчислює від business_today | Приймати необґрунтований рік, придуманий LLM |
| «Покажи останню фактуру» | `show_existing_invoice` | Створити нову |
| «Відправ фактуру» | `send_invoice` reserved/unsupported в етапі 1 | Імітувати відправку або створити нову фактуру |
| «Оплачено / зміни фактуру / видали фактуру» | Свої існуючі top-level дії та підтвердження | Підмінити preparation |

Якщо текст допускає кілька істотно різних значень, LLM повертає ambiguity/unknown, Python ставить конкретне запитання. `unknown` не спричиняє записів.

## 5. Structured Slots — Phase 2 + розрахунковий bundle

Схему Phase 2 розширити **additively**, з backward compatibility старого `vstup`, `zamer`, `biznis_sk`, `stopa`, singleton/item shape. Назви нижче — канонічна **пропозиція контракту даних** для implementation agent, а не claim про поточні runtime поля. Агент може без зміни бізнес-семантики підібрати сумісне місце вкладення (наприклад `biznis_sk.calculation`), зафіксувати в технічному контракті й тестах. Заборонено просити LLM напряму рахувати фінальні суми й довіряти їм.

| Slot | Джерело і пріоритет | Python validation/derived value | Якщо немає/суперечність |
|---|---|---|---|
| `business_now_utc`, `business_today`, `business_timezone` | Тільки довірений runtime UTC, локалізація `Europe/Bratislava`; поточний timestamp зчитується **один раз на запит** | Python `datetime.now(UTC).astimezone(ZoneInfo('Europe/Bratislava'))`, `date`, ISO weekday; NTP-синхронізація часу ОС перевіряється під час deployment/smoke | Якщо серверний час недостовірний — fail closed, не вгадувати рік |
| `customer_id`, `workspace_id`, `supplier_id` | Від чинних Python services; не з LLM | Scope і membership, ідентифікація активного профілю | Уточнити/відмовити, не обрати інший профіль |
| `service_name`, `service_source` | (1) явна послуга користувача; (2) остання фактура **цього contact_id** у **цьому workspace** | Python знаходить фактуру за датою + ID, читає її items; застосовує лише якщо послуга однозначна; фіксує номер джерела | Немає попередньої або кілька різних — запитати назву; не показувати автоматичний список аліасів |
| `period_intent` | LLM: `none`, `previous_week`, `this_week`, `previous_two_completed_weeks`, `explicit_iso_week(s)`, `explicit_dates` та bounded інші перевірені інтервали | Python матеріалізує дати з `business_today`; ISO календар | Запитати при невизначеності |
| `iso_weeks[]` (`iso_year`, `kw`, `start`, `end`) | Явні KW+рік користувача пріоритетні, інакше Python виводить з period_intent | `date.fromisocalendar`, `date.isocalendar`; валідні 1–52/53, rollover ISO year ≠ Gregorian year | Якщо явно названо KW без року й біля Нового року неоднозначно — уточнити; не використовувати «рік останньої фактури» як guard |
| `issue_date`, `delivery_date`, `due_date`, `delivery_date_source` | Явна дата користувача > explicit relative phrase > погоджене специфічне правило періоду/контрагента > старі legacy defaults | LLM витягує relative/absolute intent, Python фіксує конкретний YYYY-MM-DD за business_today, перевіряє точність, рік і due logic | Невірне/двозначне — уточнити; `delivery_date=issue_date` у старому повному сценарії без інших правил |
| `hours_total`, `hours_by_kw` | Явний користувач (або перевірене джерело); `hours_by_kw` необов'язкові | Додатні Decimal; якщо розбивка повна, сума дорівнює total | Якщо є 120 год за 2 KW без розбивки — залишити `hours_by_kw=null`, не вигадувати 60+60; для PDF це не блокер |
| `hourly_rate`, `rate_source` | Явне значення > `default_hourly_rate_eur` наявного контакту, scoped | Decimal позитивна EUR/h, canonical currency | Немає — уточнити в FSM; одноразове значення **не змінює** картку контакту мовчки |
| `gross_amount` | Явна безсумнівна сума роботи користувача **або** hours_total × hourly_rate | Decimal 2 decimals; звірка з explicit fields | Якщо явні total і hours×rate конфліктують — запитати |
| `lodging_groups[]` (`nights`, `price_per_night`, `subtotal`) | Лише явно сказані групи, LLM витягує; Python рахує | Додатні/невід'ємні цілі nights і Decimal price; окремі групи | Якщо житло не вказано → []; якщо вказані ночі без тарифу і заявлено відрахування → уточнити |
| `lodging_total`, `net_amount` | Python: sum nights×rate, gross−lodging | Decimal EUR, 2 decimals; cross-check, сума більша нуля для звичайної фактури | Конфлікт або нетто ≤0 → fail safe/clarify; не створювати кредит-ноту |
| `amount_kind` | Визначений зміст явно заданої суми: gross або net | Запобігає подвійному відрахуванню проживання | Якщо сума й житло без ясності gross/net — уточнити |
| `pdf_final_item` | Тільки Python з валідованого `net_amount` | Для нового hourly/lodging сценарію: **одна позиція, quantity=1, unit_price=net, total=net**, назва з service_name | Не змінювати чинну формулу й item shape для старих повних команд, legacy multi-item лишається |

**Час/рік (головний захист):** рік навчання або версії LLM не є джерелом часу. Python передає моделі `business_today`, timezone й ISO-week reference; LLM **не має права** тихо повертати `2023` чи `2026` з власної пам'яті, якщо користувач цього року не назвав. Python перевіряє прив'язку результату до authoritative anchor; explicit **історичний рік** користувача допустимий і не блокується старими фактурами. Якщо часовий якір не зійшовся — відкинути модельний вихід/уточнити. Не вводити перевірку «новий KW не старіший останньої фактури». Це правило власник **скасував** 16.11.2026, оскільки мета була захистом від неправильної дати моделі.

**Робоча дата приклади:** якщо `business_today=2026-11-16` (понеділок), два попередні завершені тижні — `2026-W45` (02–08.11) і `2026-W46` (09–15.11), для TECH COMPANY погоджена дата dodania останньої п'ятниці останнього тижня — `2026-11-13`. Якщо `business_today=2027-01-04`, два попередні завершені — `2026-W52` і `2026-W53`, а не `2027-W00`. Явна дата `2023-11-18` з боку користувача має лишатися допустимою за чинними legal/validity перевірками, без автоматичного виправлення року.

**Примітка про часовий вираз «остання п'ятниця»:** LLM визначає, чи дата відносно сьогодні чи відносно прямо названого періоду, Python матеріалізує. Якщо обидва значення правдоподібні й дають різні дні — запитання. За правилом TECH COMPANY «попередні два завершені тижні» без явно вказаної дати dodania — п'ятниця останнього сервісного тижня; це не глобальний default для інших клієнтів.

## 6. Public Route & Convergence Map

| Вхід | Guard | Спільний owner | Результат |
|---|---|---|---|
| Вільний текст | Authorization → active-FSM first → top-level `create_invoice` | `process_invoice_text()` → Phase-2 extract/enrich → `_build_and_store_preview()` | Стан очікування підтвердження або уточнення |
| `/invoice` → текст | Authorization → `InvoiceStates.waiting_input` | Той самий shared owner | Ідентична чернетка |
| Голос | Authorization before STT; FSM guard; `voice.py` лише транспорт/transcription | Той самий owner через transcript | Ті самі семантичні слоти й перевірки; exact numeric edits лишаються text-only згідно чинних правил |
| Кнопки, тексти рішення | Invoice-preview callback: actor + chat/message + workspace + exact `preview_token`/version + state + expiry; free text: only current active draft, explicit reply-to-old-preview rejected | Shared `process_invoice_preview_confirmation()` / DecisionResolver after verification | approve/edit/cancel; previous preview buttons never act on a later draft |

Не створювати мовні словники `вчера/позавчера/минулої п'ятниці` на Python як primary path. Python отримує канонізований date intent і **детерміновано обчислює дату**.

## 7. FSM Graph & Ownership

```text
idle / /invoice
  -> process_invoice_text: create_invoice
  -> Phase-2 parse (anchor business_today)
  -> scoped contact lookup -> service fallback -> calendar -> price/lodging calc
      -> missing customer/service/hours/rate/lodging value/date: waiting_slot_clarification
           -> user reply -> re-evaluate same partial draft and return to preview
      -> ambiguous contact: existing customer clarification/alias confirmation
      -> complete: waiting_confirm
           -> [new calculation summary] + [existing _format_preview]
           -> each rendered preview: fresh nonce/version + owner/workspace + Telegram chat/message id + expiry stored in FSM
           -> edit: existing edit FSM; change calculation inputs -> recompute bundle -> both previews again, fresh nonce; direct manual override -> invalidate calculation, clearly show manual amount, fresh nonce
           -> cancel: invalidate token, clear state, no invoice, remove owned keyboard
           -> approve: validate exact preview binding; claim single-use token; existing _finalize_invoice_draft -> DB invoice + PDF + valid bundle (or explicitly invalidated manual snapshot)
                      -> Telegram PDF -> clear FSM, cleanup owned keyboard
saved invoice -> old edit FSM -> material edit with valid bundle: mark snapshot invalidated atomically with DB financial change; rebuild PDF with validated new total; warn user; no silent historical recalc
```

- Продовження уточнення **не** йде на idle top-level.
- Не копіювати попередній invoice number, години, ставку, дати, житло, суму, статус або платіжну інформацію при fallback послуги.
- Нове відображення прев'ю **завжди** змінює `preview_token`/version. Кнопка з прев'ю №101 не може схвалити чернетку, показану як №102, навіть коли FSM стан `waiting_confirm` той самий. Зняти стару клавіатуру, якщо повідомлення належить користувачу/боту й cleanup дозволений; помилка очищення не дає права виконати стару дію.
- Правка **первинних параметрів калькуляції** всередині чернетки (hours/rate/lodging) викликає детермінований перерахунок. Чинний generic invoice editor змінює PDF item amount/quantity/price, а не ці первинні параметри. Якщо користувач прямо змінює **готову кінцеву суму**, не намагатися виводити з неї нові години чи ставку: bundle стає `invalidated`, а чернетка переходить до **ручного** результату з попередженням у новому preview. Погодити вручну можна, але він не має чинного розрахункового bundle для майбутнього листа.
- Для **вже збереженої** фактури material edit (кінцева сума, qty, price, назва послуги, дати, KW та інші поля, які згадує bundle) не переписує історичні години/ставку/ночі. Старий snapshot у `calculation_bundle_json` зберігається як `status=invalidated`, з `effective_invoice_total`, `invalidated_at`, `invalidation_reason=manual_invoice_edit`. Цей JSON — **історія, а не актуальний розрахунок**. Перерахунок до `valid` можливий тільки з перевірених первинних значень і нового підтвердження користувача, не за здогадом із нового net.
- Для `valid` bundle інваріант `bundle.net == invoice.total_amount == PDF.total` обов'язковий. Для `invalidated` bundle старий `net` має бути позначений `historical_net` (або лежати в `historical_calculation`) і **не має** вважатися чинним; чинні DB/PDF totals мають збігатися з `effective_invoice_total`. Stage 2 email не може використовувати `invalidated` bundle для деталізації KW/hours/lodging без повторної підготовки та підтвердження.
- Чинний `last_pdf_decision`/редагування історичних фактур без bundle не ламаються; `calculation_bundle_json=NULL` лишається допустимим для legacy і не повинно інвалідуватися/вигадуватися.
- При помилці PDF/DB rollback/cleanup залишити чинний шлях; частково створений bundle не повинен виживати без invoice.
- Для UI callback/lifecycle залишити одного owner, задокументувати terminal/timeout/stale/forbidden cleanup та тести, не покладатися на `one_time_keyboard`.

## 8. Decision & Callback Contract — поправка після `material_design_variance`

- Чинна decision-family `approve_edit_cancel` і `bot/services/decision_resolver.py` залишаються. Не створювати інший бізнес-обробник підтверджень і не додавати локальних мовних парсерів. Visible labels `Schváliť / Upraviť / Zrušiť` незмінні; нової кнопки «Відправити» немає.
- **Лише для `InvoiceStates.waiting_confirm`** генерувати per-preview непередбачуваний короткий `preview_token` і монотонну версію (або новий opaque token на кожне відображення), зберігати в FSM `actor_id`, `workspace_id`, `chat_id`, `preview_message_id`, `created_at`/expiry та version. Використовувати окремий namespaced callback payload, наприклад `invprev:v1:<nonce>:approve|edit|cancel` (кожне фактичне значення <=64 байти Telegram); це **той самий** canonical decision після валідації, а не новий top-level action. Не міняти generic `decision:approve` інших продуктних FSM.
- Callback resolver/dispatcher перед викликом бізнес-owner перевіряє **все**: авторизований actor, той самий чат і message ID, той самий workspace та діюча membership, current `waiting_confirm`, exact nonce/version і TTL, відсутність already-consumed claim. При будь-якому mismatch/старому nonce — fail closed **до** виклику `_finalize_invoice_draft()` та до будь-якого edit/cancel нового чернеткового стану. Чужі/неперевірені повідомлення не чіпати. Власні застарілі markup прибирати, якщо ownership доведений.
- Legacy generic `decision:approve|edit|cancel` у `waiting_confirm` **не має** права схвалювати/редагувати/скасовувати актуальну чернетку. Його потрібно відхиляти як `stale_unbound_invoice_preview`; але зберегти цілком роботу такого payload для **інших** станів/екранів. Цей захист однаково застосовується до старого повного invoice creation та нового hourly-flow.
- Простий текст/voice decision (без callback) означає відповідь **на актуальне** preview в поточному FSM. Якщо користувач зробив explicit Telegram reply-to до старого preview_message_id — reject stale. Він не може відновити невідповідну версію чи обійти precision/authorization. Текстові рішення проходять існуючий DecisionResolver.
- `approve` виконується один раз на preview: atomic/single-flight Python claim для `(actor_id, workspace_id, preview_token)` плюс уже чинна DB-унікальність invoice number; повторний/одночасний callback не генерує інший PDF або другий invoice. Перед виконанням claim перевірити ідентичність, номер і валідність чернетки. Після success/cancel/timeout — token consumed/invalid, FSM очищений, власна клавіатура прибрана; cleanup failure логувати, не відкочуючи успішне збереження. Не перетворювати 'unknown' на approve.
- Якщо пропонувати зберегти змінений тариф у картці контакту, це окремий explicit confirmation з відповідним persistent edit, який не блокує виставлення фактури; без цієї UX-гілки дозволено лишити тариф лише разовим у Stage 1.

## 9. Side Effects Map

| Дія | Тригер | Owner | Перевірка / failure | Idempotency |
|---|---|---|---|---|
| Read active supplier/contact | Authorized create | ScopedInvoiceRuntime | membership + workspace | Read-only |
| Read latest invoice **for contact** | Відсутня назва послуги | Новий/розширений scoped read service | same contact/workspace; one unambiguous service | Read-only |
| Calculate period/amount | Перед preview | Python calendar/Decimal helper | anchored date, ISO validity, completeness | Pure |
| Optionally save default rate | **Лише окреме підтвердження** | ContactService/WorkspaceContactService | one scoped field, no upsert/rewrite | conditional update |
| Save invoice + calculation bundle + PDF | **Bound/current single-use** preview approve | Existing InvoiceService/WorkspaceInvoiceService and PDF owner | active valid numeric net matches DB/PDF; rejected stale/duplicate; rollback on failure | preview token claim + same invoice ID/numbering rules |
| Manual edit saved invoice with bundle | Existing scoped edit handler after user input | InvoiceService / WorkspaceInvoiceService scoped update + PDF rebuild, not LLM | apply new DB values and `status=invalidated`/effective total consistently; preserve old snapshot; no PDF overwrite on invalid math; failures recover without presenting mismatched PDF as successful | no-op/duplicate edit must not create new invoice; safe retry |
| Google Drive after paid | Existing mark_paid only | Existing InvoiceDriveArchiveService | Existing queue | unaffected |
| Gmail / email-send / new archive trigger | No effect in Stage 1 | out of scope | no permission | n/a |

Persist structured calculation per saved invoice, not only FSM. **Design decision:** nullable `invoice.calculation_bundle_json TEXT` (versioned JSON, `schema_version=1`) and nullable `contact.default_hourly_rate_eur` (exact decimal-compatible TEXT). Existing invoice row owns `invoice_id`, supplier/workspace. Historical rows stay `NULL`. A newly approved calculation is `status=valid`, with `net` invariant to DB/PDF. A manual edit invalidates its calculation without losing historical inputs: `status=invalidated`, historic snapshot retained and clearly labeled, `effective_invoice_total` equals current DB/PDF; email/AI must not present historical inputs as current. A later new valid calculation requires explicit re-preparation and approval.

**Schema compatibility / rollback is part of Stage 1 acceptance, not a deployment afterthought.** Current source in `bot/services/db.py::_bootstrap_contact_table/_bootstrap_invoice_table` compares table column-name sets for exact equality. An ALTER ADD COLUMN would make the previous unmodified revision fail on restart. Therefore:
1. Prepare and test a **compatibility baseline** that accepts both the pre-migration and the additive post-migration `contact`/`invoice` shapes, including legacy tables, without dropping data or implicitly backfilling fake bundles. The compatibility baseline must run existing invoice create/edit/read and archive without requiring the new fields to have non-null values.
2. Freeze writes/arrange backup and run a **read-only** local dry-run of real schema shape and version first. Explicitly approved migration expands nullable columns and verifies `init_db`, constraints, existing invoice reads, legacy profile and workspace paths, plus mixed old/new invoice records; no destructive table rewrite.
3. Keep a tested **rollback runtime** based on the compatibility baseline, capable of starting against the expanded DB while not exposing incomplete preparation. Never claim that the unmodified pre-migration executable itself can be rolled back against expanded DB. A full restore of the pre-migration SQLite backup is a separate recovery operation with explicit assessment of transactions made since backup; never silently discard newer invoices.
4. Before any live deployment, show owner the exact migration, backup, rollback binary/image and runbook, dry-run and tests, then request separate approval. No live DB change under the code-only task.

If schema/write/PDF coherence cannot be proven for the selected implementation, report new `material_design_variance`; do not invent an alternate table or skip validation.

## 10. Authorization / Tenant / Precision

Authorization before LLM/STT/storage; actor and workspace from Python, **не LLM**. Contact and prior invoice retrieval bound to `contact_id` + `workspace_id` (or verified legacy owner). Currency EUR and account field types validated. Do not let one workspace borrow another's last invoice or rate. Exact-value edits of invoice amount/rate/quantities/identifiers/text fields follow existing text-only precision rules; initial voice transcript remains only a *draft* requiring visual approval. Do not make a precision-sensitive value auto-save from uncertain STT.

## 11. User-Facing Response & Exit

- Complete draft → **separate calculation summary** (supplier, customer, service/source, KW incl ISO year/date range, hours/split if known, rate/source, lodging groups, gross/net, issue/delivery/due dates) **followed by unchanged `_format_preview`** and approval keyboard.
- Missing slot → one focused question, preserve partial data + correct FSM continuation, no write.
- Explicit historical/future date → display real date, not silent correction; if contradictions, ask.
- Edit calculation **inputs** → newly computed valid calculation summary + original preview with fresh bound version. Generic edit of final amount/price/quantity → clearly `manual override; previous calculation invalidated`, current manual total in original preview, fresh bound version; no false hours/rate inference.
- Existing invoice material edit → updated PDF/DB with user-visible warning that stored calculation is historical/invalidated; old invoice can still be viewed and marked paid; no erroneous future email breakdown.
- Old/unbound/other-profile/wrong-message callback → stale warning, no business side effect, no edit/cancel of current draft; owned markup cleanup only.
- Cancel/timeout/unknown → safe state, appropriate keyboard cleanup, no side effect.
- Approved → existing PDF returned in Telegram and persisted on VPS; **no email**.

## 12. Product Truth / InfoHelp

- Initial status: preparation logic unsupported; do not claim already deployed.
- After implementation/tests, truthfully describe only the supported relative periods, last-service fallback, rate/gross/net and lodging fields.
- Do not claim Work, GitHub Actions, Gmail send, direct Google Drive archive upon send, bank confirmation, or automatic ongoing client learning.
- Capability questions answered without launching the invoice flow.

## 13. Negative Space / Regression

- No new top-level token, no separate PDF generator, no PDF layout change, no removal/reformat of `_format_preview`.
- Legacy full command and multi-item creation without hourly/lodging must remain unchanged.
- Reading latest **client** invoice does not mutate prior data and only copies service name if unique.
- No implicit rate learning or copying rate/hours/lodging/dates from last invoice.
- No check that KW/year is newer than last invoice; no last-invoice-year guard.
- Explicit past dates remain legal input; validate consistency, don't replace with business_today.
- No automatic KW/hours split; no extra nights if lodging absent.
- No accidental top-level theft from show/edit/delete/paid/send or InfoHelp.
- No unauthorized calls, cross-workspace leakage, new Gmail permission, or archive trigger change.

## 14. Acceptance Scenario Contract (end-to-end through public entry)

Each scenario must assert: input; canonical intent/slots; current FSM; calculator results; next state/keyboard; DB/PDF/no-write consequences; voice path where relevant.

1. **Legacy full:** «Вистав фактуру Techcompany, montáž, 3000 €, dodania 12.11.2026» → create_invoice, same legacy PDF/preview and one addition summary, no rate search.
2. **Missing service with last client invoice:** contact's latest unique service `elektroinštalačné práce` → use only service; verify no old amount, rate, date, lodging copied; source displays invoice number.
3. **Missing service, first invoice:** ask user for exact service and continue same invoice draft; no alias guessing.
4. **Missing service, last multi-service:** ask clarification; no arbitrary first item choice.
5. **Hours × rate:** 120 h, 32 €/h → gross 3840 EUR; 14×29 lodging → 406 EUR; net/PDF item=3434 EUR; PDF exactly one priced service.
6. **Rate from contact vs one-time explicit rate:** explicit 40 overrides contact 32 only for this invoice; no contact update without consent.
7. **Multi-night rates:** 7×15 + 8×30 = 345 EUR; do not drop groups.
8. **No lodging:** amount not deducted; display none/absent, do not inherit last invoice's lodging.
9. **No period:** legacy `delivery_date=issue_date`, no invented KW.
10. **Anchor business_today=2026-11-16:** previous two completed weeks 2026-W45 and W46, `delivery_date=2026-11-13` under TECH COMPANY last-Friday rule.
11. **Anchor business_today=2027-01-04:** previous two completed weeks 2026-W52 and W53; no 2027-W00, date rollover correct.
12. **LLM returns 2023 despite runtime 2026 with no user year:** reject/reanchor, never produce 2023 invoice/dodania.
13. **User explicitly says 2023 or KW45/2023:** use exactly validated historical reference; don't forbid due to newer saved invoice.
14. **Explicit KW45/2026:** priority over derived previous week; valid `date.fromisocalendar` and visible year.
15. **Explicit KW53 in 2027:** invalid ISO week, clarify rather than guess.
16. **Relative dates:** «вчора», «позавчора», «минулої п'ятниці», «цей тиждень», «попередній тиждень», «попередні два тижні» with frozen anchor; text and voice transcript converge.
17. **120 h over two weeks without hours_by_kw:** gross/net valid, `hours_by_kw=null`, never 60+60 or 100+100.
18. **Explicit gross and lodging conflict with supplied net:** ask clarification, prevent double deduction.
19. **After edit of calculation inputs:** change hours or lodging, both previews agree with final PDF, new bound preview token; old approval invalidated. Direct edit of finished amount does **not** silently rewrite hours/rate/lodging: turns the calculation historical/invalidated and displays manual total.
20. **Duplicate/overlap:** when authoritative existing bundles show overlap, warn; historical records without bundle cannot be used to assert no overlap; user explicit override handled only with normal confirmation.
21. **Cross-workspace:** identical contact names in SZČO/ZEVS never cross-read; wrong-workspace membership blocked.
22. **Cancelled / unknown / stale callback / double approve:** no extra invoice, preserved number, correct terminal keyboard cleanup. Explicit replay: preview message #101 callback `approve` when new preview #102 is current → zero finalize calls / no DB/PDF write; current #102 remains awaiting decision.
23. **Old persisted invoices:** no bundle parses as null and still supports show/edit/mark paid; existing after-paid archive unchanged. New bundle-backed persisted invoice edited from 3434 to 3500: SQLite/PDF=3500, historical calculation=3434 marked `invalidated`, active current amount=3500, no fabricated new hours/rate/lodging, subsequent mail cannot claim 3434 breakdown.
24. **InfoHelp vs action:** “як бот рахує KW?” does not open invoice FSM.
25. **Authorized before STT/LLM:** unauthorized request causes no cost or side effect; voice route follows same owner and rejects exact numeric correction when contract requires typed text.
26. **Technical delivery:** focused unit + public-route + smoke + old journey, schema migration dry-run and tested compatibility rollback, full `Conversation Acceptance Proof` verdict, Product Truth/InfoHelp and PROJECT_LOG updated.
27. **Legacy/unbound invoice callback:** old `decision:approve` targeting current `waiting_confirm` → rejected, new current draft unchanged; same generic decision callback in an unrelated legitimate FSM remains supported.
28. **Callback isolation & idempotency:** wrong user/workspace/chat/message/nonce, expired token, duplicate and simultaneous approve → no cross-workspace mutation, at most one invoice/PDF. Fresh text/voice decision acts only on current active preview; reply-to-old-preview rejected.
29. **Material saved-invoice edits:** quantity, unit price, net total, service label and relevant dates each invalidate valid bundle and preserve an explicitly historical snapshot, atomically with effective invoice state; PDF success/failure and retries maintain consistent reported status.
30. **Schema rollback:** pre-migration and expanded schemas both boot under the compatibility runtime; unchanged old runtime boot against expanded schema is explicitly unsafe; backup, dry-run, compatibility rollback image and post-migration-write recovery cases are tested and documented.

## 15. Out of Scope / Known Gaps

- Stage 2: Gmail OAuth send/drafts, email composition, recipient-specific templates, after-send Drive archive — **not in this implementation task**.
- Generic `edit_contact` new top-level — separate architecture/approval. A scoped confirmation for saving rate, if implemented, is an in-FSM field update only; otherwise leave one-time rate and be honest.
- OCR documents, Gmail reading of client rules, automatic timesheets, unlimited invoice item count, inventing hourly breakdown from totals — unsupported.
- Potential ambiguity around local/exact date phrases, explicit KW without ISO year around New Year → ask when genuinely ambiguous.
- The selected persistence implementation and any server DB migration require read-only schema verification, explicit owner approval for migration/deploy, backup and the **tested compatibility-runtime rollback** before applying. Unmodified pre-migration runtime is incompatible with additive columns under current exact-set checks. Target repo source was read; live VPS and SQLite were not inspected.
- Stage 1 changes only invoice preview-bound callbacks, not global DecisionResolver semantics for other FSM; no new top-level action. Stage 2 Gmail must refuse to use invalidated calculation history as current.

## 16. Evidence Index & Verdict

- `bot/handlers/invoice.py`: `process_invoice_text`, `_build_and_store_preview`, `_format_preview`, `_finalize_invoice_draft`, `process_invoice_preview_confirmation`, `_resolve_issue_date`, `_resolve_delivery_date`; existing implementation seen in GitHub read-only.
- `bot/services/llm_invoice_parser.py`: `parse_invoice_phase2_payload` / `validate_invoice_phase2_payload` currently enforce non-empty service and limited structured items; missing-service enrichment must adjust the contract, not bypass validation silently.
- `bot/services/scoped_invoice_runtime.py`: supports scoped contacts, invoices and last invoice by workspace but no current confirmed **latest invoice by contact** facade method.
- `bot/services/contact_service.py`: current ContactProfile does not have optional default hourly rate; additive migration required.
- `bot/services/pdf_generator.py::generate_invoice_pdf`: existing canonical renderer; keep unchanged.
- `bot/services/invoice_drive_archive_service.py`: after-paid job owner; not in first-stage edit scope.
- `bot/services/google_integration_service.py`: Gmail OAuth `gmail.readonly`, send remains unsupported.
- `prompts/invoice_draft_prompt.txt`: current Phase-2 schema, no KW/lodging fields.
- `AGENTS.md` architecture, approval, voice, state/keyboard rules and mandatory `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`.

**Verdict: `ready_for_handoff` (amended architecture only; owner decision on both blockers 2026-11-16).** This revision explicitly resolves preview-binding, persisted-manual-edit and additive-schema rollback policy. Implementation agent must redo read-only verification against actual `main` and report design_matches_runtime / minor_nonsemantic_variance / material_design_variance. The previously reported variance is not itself permission to code around other contradictions. No source-code modification, migration, merge, push, deployment, or live test was performed in amending this artifact.
