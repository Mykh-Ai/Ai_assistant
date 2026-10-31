# ZEVS — маршрути документів, виписка без пароля та сповіщення про збій
# Architecture Design Proof

Verdict: `ready_for_handoff`
Погодження користувача: **погоджено 2026-10-31**, включно з автоматичним вибором річних/місячних папок і failure notices. Підстава: «В принципі дизайн приймаю», із уточненням, що надані Drive URLs є прикладом дерева, без жорсткої прив’язки до 2026.
Статус реалізації цього дизайну: **не реалізовано, не розгорнуто**.
Цей документ є погодженим дизайном; implementation task зберігається окремо в docs/tasks.

Публічна копія: installation-specific Drive IDs замінено явними placeholders. Реальні значення належать приватній конфігурації; placeholders не можна використовувати як runtime IDs.

Ревізія 3, 2026-10-31: дизайн погоджено; Drive URLs визначають приклад і перевірені початкові папки, а не фіксований рік чи обов’язкові hardcoded child IDs. Стабільний корінь компанії налаштовується один раз, рік і місяць беруться з чинної validated document/statement логіки. Річні папки, зокрема Zevs_2027, перевикористовуються або створюються on demand. Погодження не є дозволом на merge, deployment чи production data writes.

## 1. Task Identity And Product Need

- Task: `ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1`.
- Дата: 2026-10-31, Europe/Berlin.
- Архітектор: Codex.
- Репозиторій: Mykh-Ai/Ai_assistant.
- Перевірений main: `d25a4431c7b923d055b225229e0c563953600bca`.
- Потреба: архівувати виписки ZEVS s.r.o. без пароля у вказану папку; блочки ZEVS — у другу папку; повідомляти власника документа в Telegram, якщо архівація остаточно не вдалася.
- Поточний Product Truth: Gmail collection і Google Drive archive мають `partial`, залежать від setup/admin/external credentials.
- Цільовий статус: ті самі класифікації; додатково чесно описаний конкретний налаштований маршрут, незашифрована архівна копія підтримуваного PDF і повідомлення про збій.
- Ризик: високий для зовнішнього сховища, банківських документів і tenant isolation. Зміна збереження даних є migration-sensitive.
- AI maturity: новий AI-рівень не додається; зміна детермінована. Чинний InfoHelp залишається capability-aware, partial.

### Факти та межі перевірки

Через GitHub прочитано AGENTS.md, чинний контракт Architecture Design Proof, релевантні код, тести, документи й записи PROJECT_LOG. Через підключений Google Drive прочитано лише метадані та прямі списки вказаних папок.

Підтверджено:

| Об’єкт | Поточний факт |
|---|---|
| Vypisy | ID `<ZEVS_2026_VYPISY_FOLDER_ID>`; пряма дочірня папка Zevs_2026 |
| blocky | ID `<ZEVS_2026_BLOCKY_FOLDER_ID>`; пряма дочірня папка Zevs_2026 |
| Спільний батько | `<ZEVS_2026_YEAR_FOLDER_ID>`, назва Zevs_2026 |
| Стабільний корінь компанії | `<ZEVS_COMPANY_ROOT_FOLDER_ID>`, назва Zevs s.ro; містить Zevs_2026 та Zevs_2025. На момент read-only перевірки Zevs_2027 у прямому списку немає |
| Поточна організація виписок | Чотири видимі PDF безпосередньо у Vypisy; назви містять ZEVS_Tatra та період |
| Поточна організація блочків | У blocky є підпапки 2026-07, 2026-08, 2026-10 |
| Пароль виписок | PROJECT_LOG, запис 2026-08-04, містить історичний доказ встановлення file-backed opening-password secret |
| Повторні спроби | ArchiveJobService: default max_attempts=5; ArchiveWorker: delay=15 хв |
| Поточне зняття пароля | detect_gmail_statement_period відкриває PDF лише в пам’яті; GmailStatementCollector зберігає початкові bytes |
| Повідомлення про остаточний Drive failure | У перевіреному archive scheduler відсутнє; його сигнатура не приймає Bot |

**Не перевірено в цій сесії:** поточний commit на VPS, фактичний workspace_id ZEVS, стан серверного secret-файла, OAuth-гранту та прав саме runtime-акаунта бота на папки. Доступ підключеного тут Google Drive не доводить доступу серверного бота. Вміст реальних банківських PDF не завантажувався.

На сервері не виконувалися команди. Документи, папки, права, SQLite й runtime не змінювалися. Тести не запускалися: це read-only дослідження і дизайн, а не перевірка зміненого коду.

## 2. Architecture Classification

Обраний клас: **5 — deterministic internal strategy**, розширення чинного архівування.

Це не новий top-level intent, не нова Telegram-команда, не новий FSM/subflow і не LLM-slot. Бізнес-події вже існують:
- новий дозволений Gmail statement import;
- підтверджене збереження receipt;
- terminal archive failure.

Поточні власники:
- Gmail: GmailStatementCollector.run_once; gmail_statement_scheduler._run_tick;
- receipt: accounting_document_intake._save_accounting_document_from_state і _enqueue_archive_after_confirmed_save;
- queue: AccountingDocumentArchiveService та ArchiveJobService;
- upload: ArchiveWorker і GoogleDriveOwnerOAuthArchiveProvider;
- lifecycle: google_drive_archive_scheduler та bot/main.py.

Новий спільний archive-routing helper не може стати окремим AI-router. Нові helper/service owners, описані далі, є **запроєктованими**, а не наявними функціями.

Повний proof підготовлено через зміну меж side effects і user-visible failure behavior, хоча нових розмовних станів немає.

### Обов’язкова зміна чинного контракту

GMAIL_PROTECTED_STATEMENT_PERIOD_ROUTING_V1 прямо каже, що розшифрована копія не створюється. Цей дизайн після погодження вводить вузький виняток: дозволена окрема архівна копія без пароля; encrypted original залишається незмінним. Заборона зберігати пароль і розкривати його в логах залишається.

## 3. Canonical Action Contract

Новий canonical_token: **не застосовується**.

Не додавати:
- публічну дію «розшифрувати PDF»;
- нову команду для маршрутизації папок;
- керування retry через довільний текст;
- автоматичний вибір папки моделлю.

Чинні receipt intake, InfoHelp, Gmail settings і правила confirmation лишаються власниками своїх маршрутів.

## 4. Semantic Boundary Matrix

| Вхід / значення | Правильна поведінка | Не повинно перетворитися на |
|---|---|---|
| Новий statement import перевіреного джерела ZEVS | Оригінал локально; архівна копія PDF без пароля у Vypisy | Нову фактуру, транзакційний парсер, зміну оригіналу |
| Підтверджений receipt ZEVS | blocky/YYYY-MM | Архів виписок або outgoing invoice |
| Receipt іншого workspace | Чинний його маршрут | Папку ZEVS |
| Incoming invoice | Чинний prijate_faktury | Блочок лише через однакове слово «документ» |
| Outgoing invoice PDF | Чинний annual faktury route | Vypisy/blocky |
| «Чи вмієш зберігати виписки?» | InfoHelp без enqueue/upload | Виконання завантаження |
| Невідомий document_type або непідтверджене джерело | Fail closed, без upload | Receipt за замовчуванням |
| Активний профіль змінено після enqueue | Виконати незмінний snapshot початкового workspace | Перенаправити старий job |
| Документ 2026 року надійшов у 2027 | Архів 2026 року за датою/періодом документа | Автоматично поточний календарний рік |
| Перший документ 2027 року | Перевірити/створити Zevs_2027 у затвердженому корені компанії | Використати ID папок 2026 або шукати будь-де в Drive |
| Текст/голос із URL папки або паролем | Не змінює admin routing/secret | Конфігурацію зі слів користувача |

Meaning «блочки» у погодженому дизайні: `receipt` у workspace ZEVS, із збереженням місячних підпапок. Це approved scope, а не твердження про невідомі server settings. Чинне локальне збереження за роками/місяцями не перепроєктовується.

## 5. Structured Slot Contract

Нових bounded-LLM slots немає.

| Значення | Джерело | Валідація / invalid behavior |
|---|---|---|
| workspace_id | Persisted immutable workspace context | Точна membership/authorization; без пошуку за схожою назвою |
| storage_key | Persisted workspace | Канонічний local path лише цього workspace |
| document_type | Чинна підтверджена intake metadata / Gmail pipeline | Відомий тип; unknown без upload |
| route year | Receipt canonical issue-date path / validated statement period | Валідований рік документа; не рік отримання, запуску worker або retry |
| receipt month | Чинний validated YYYY-MM | 01–12; не місяць запуску worker |
| statement period | Чинний detect_gmail_statement_period | Неоднозначний період не вгадується |
| target folder IDs | Admin-owned company root + verified annual cache; optional verified existing-folder hints | Не з LLM, голосу, filename або callback; lineage перевіряється; child IDs не hardcode |
| opening password | Чинний GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE | Лише secret file; не Telegram, не DB, не metadata |
| output filename | Детермінований Python formatter | Safe filename, без traversal і control characters |
| max_attempts | Чинний job field | Позитивне число; для нових jobs default 5 |
| recipient | Збережений job actor / підтверджений Gmail workspace owner | Revalidate membership перед повідомленням |

### Точна пропозиція маршрутів

| Scope | Тип | Destination |
|---|---|---|
| Точний ZEVS workspace, archive year 2026 | bank_statement_original | Безпосередньо `<ZEVS_2026_VYPISY_FOLDER_ID>` |
| Точний ZEVS workspace, issue year 2026 | receipt | `<ZEVS_2026_BLOCKY_FOLDER_ID>` / YYYY-MM |
| Точний ZEVS workspace, інший валідований рік, зокрема 2027 | bank_statement_original | approved company root / Zevs_YYYY / Vypisy; PDF безпосередньо у Vypisy |
| Точний ZEVS workspace, інший валідований рік, зокрема 2027 | receipt | approved company root / Zevs_YYYY / blocky / YYYY-MM |
| Інші workspace/type | Усі | Чинна поведінка без retargeting |

Для всіх років, включно з 2026, діє однаковий bounded direct-child lookup за затвердженим шаблоном нижче exact company root. Надані 2026 IDs — перевірені evidence/bootstrap hints: їх можна кешувати після lineage verification, але не hardcode в Python і не вимагати окремої конфігурації для кожного року. Пошук довільної однойменної папки по всьому Drive заборонено. Не змінювати глобальний GOOGLE_DRIVE_ROOT_FOLDER_ID.

### Автоматичний перехід між роками

Рік визначається один раз при створенні job: для receipt — підтверджена дата документа; для виписки — чинний validated statement period (рік і місяць із greatest-covered-days правила). Дата отримання документа, Новий рік під час retry та пізніший active profile не змінюють його рік.

При першому дозволеному документі 2027 року worker перевіряє approved company root і його прямих дітей: Zevs_2027, далі Vypisy або blocky, а для receipt ще YYYY-MM. Якщо точна потрібна папка є — повторно використовує її. Якщо відсутня — створює в межах цього дерева; зайві підпапки без потреби не створюються. Окремий календарний cron на 1 січня не потрібен. Те саме правило діє для 2028 і наступних років.

Document від 2026-12-31, отриманий у січні 2027, лишається у Zevs_2026. Виписка з визначеним періодом 2026-12, доставлена в 2027, теж лишається у Zevs_2026/Vypisy. Для інтервалу через межу року зберігається чинне правило найбільшої кількості покритих днів, а не довільний вибір за датою листа.

Читання переліку дітей має враховувати pagination. Дублікати точних річних/type/month names, неправильний parent, shortcut замість справжньої папки, trashed folder або відсутність прав → fail closed і повідомлення за failure contract. Не обирати перший збіг і не fallback у минулий рік.

Routes читаються з нового admin-managed read-only JSON-файла, шлях до якого задає `GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE`. Це **нове запроєктоване налаштування**. Ключ: exact workspace_id + document_type. Поля: schema_version, route_revision, company_root_folder_id, annual_folder_template (лише Zevs_{YYYY}), document_folder_name (Vypisy / blocky), relative_suffix_mode (none / year_month), payload_mode (original / pdf_without_password). Optional existing_year_anchors є лише verified bootstrap hints, їх відсутність для нового року не блокує generic route. Рік не є захардкодженим глобальним налаштуванням. Файл має бути absolute regular file без symlink, з обмеженим розміром до 64 KiB, без дублікатів ключів. Реальні installation mappings не комітити в публічний репозиторій.

Якщо конфігурацію явно ввімкнено, але вона пошкоджена, не вдавати, що override відсутній. Нові jobs відповідного rollout не можуть непомітно піти старим маршрутом. Без налаштованого route-файла залишається legacy mode, що має бути явно відображено в setup status.

## 6. Public Route And Convergence Map

| Entry | Guards | Convergence | Result |
|---|---|---|---|
| /add_blocek → фото/PDF → preview | Authorization до AI/temp; bound workspace; підтвердження | _save_accounting_document_from_state → archive service | Локальне збереження, потім async archive |
| Idle attachment | Чинний attachment router; active FSM має пріоритет | Чинний intake, потім той самий save helper | Та сама queue |
| Text / voice / reply button у preview | Чинний state-aware decision helper | Спільний confirmed save | Один job, без parallel voice logic |
| Gmail background | Точний bound workspace, active grant, approved readonly query | _run_tick → archive service | Той самий worker |
| Остаточний збій | Persisted job + authorization для recipient | Notification outbox → scheduler Bot.send_message | Окреме інформаційне повідомлення |
| Capability question | Чинний InfoHelp | Product Truth | Без upload, route mutation і secret read |

Маршрут джерела Gmail має бути read-only-аудитом підтверджений як джерело саме ZEVS. Якщо mailbox/query допускає сторонні рахунки без достатньої ідентифікації, rollout блокується до уточнення конфігурації. Не вгадувати компанію за sender, назвою PDF або LLM.

## 7. FSM Graph And State Ownership

### Розмовний FSM

Нових станів немає. На ділянці, якої стосується зміна:

```text
existing intake waiting_upload
  -> existing extraction/category/duplicate branches
  -> waiting_preview_decision
     -> approved existing save decision -> local confirmed save -> enqueue -> IDLE
     -> unknown -> same preview; no save/enqueue
     -> edit/back -> existing recoverable intake state
     -> cancel/stale -> existing temp cleanup and terminal exit
```

Наявні category/duplicate subflows не перепроєктовуються. Збереження виконується тільки після чинного підтвердження. Fresh unrelated active-FSM switching не додається.

Gmail і archive worker не читають і не очищають Telegram FSM. Failure notice не повинно змінювати активну розмову.

### Внутрішній lifecycle архівації

```text
confirmed local document / stored Gmail original
  -> validate immutable owner + route
  -> pending
  -> uploading (existing lease)
     -> prepare/reuse verified payload
     -> reserve/reuse persisted remote file ID
     -> upload or reconcile same remote ID
     -> verify remote parent + bytes
        -> uploaded -> existing permitted retention
        -> transient failure -> retry_wait -> uploading
        -> attempt limit / permanent failure -> failed -> durable notice
```

| State | Дозволені ефекти | Success / error / recovery |
|---|---|---|
| pending | Лише запис/читання валідованого delivery context | Existing lease → uploading |
| uploading | Payload preparation, scoped Drive calls | Uploaded після readback; transient → retry_wait; permanent → failed |
| retry_wait | Збереження source і payload; до due немає upload | Due → uploading |
| uploaded | Тільки підтверджений success cleanup | Terminal; не створювати повторний файл |
| failed | Source зберігається; outbox notification | Terminal; автоматично не скидати ліміт |
| notice pending/retry | Лише delivery сповіщення після перевірки recipient | Sent / delayed retry / blocked |
| notice sent | Жодного нового send при штатному повторному tick | Terminal delivery record |

Чинні 5 спроб означають **5 загальних невдалих виконань**, а не 1+5. Перша — одразу, наступні — не раніше ніж через 15 хвилин після попередньої; приблизно 0/15/30/45/60 хв за відсутності інших затримок. Не обіцяти точний wall-clock SLA.

## 8. Decision, Confirmation, And Callback Contract

Нових підтверджень, кнопок і callback tokens немає.

Чинний receipt preview використовує `accounting_document_category_preview_decision` і shared DecisionResolver wrappers. Duplicate confirmation використовує `resolve_yes_no`, context `accounting_document_duplicate_save_decision`. Нові локальні yes/no parsers заборонені.

Text, voice transcript і наявні reply buttons повинні сходитися в чинний state-aware helper; upload запускається лише через результат confirmed local save. Secret і folder ID не можуть заповнюватися голосом.

Failure notice — інформаційне, без inline/reply keyboard, без retry button і без ReplyKeyboardRemove. Це захищає клавіатуру стороннього активного FSM. Після звичайного receipt success/cancel чинний handler продовжує власний keyboard cleanup.

Stale/forged/wrong-state callback не може створювати archive job або змінювати route. TTL/nonce і ownership чинних callbacks не послаблюються.

Ідемпотентність business event: чинний workspace/document/provider enqueue не повинен породжувати другий job або оновлювати target вже наявного job.

## 9. Side-Effect And Ownership Map

### Frozen delivery context

Для нових override jobs проєктується окрема additive таблиця `archive_delivery_context`, один рядок на job_id. Вона не замінює archive_jobs:

- job_id, workspace_id, route_revision;
- company_root_folder_id, archive_year, annual_folder_template, document_folder_name, exact_year_anchor (nullable);
- target_parent_folder_id (nullable до resolution), relative_suffix, resolved_target_folder_id;
- payload_mode, output_filename;
- source_sha256;
- payload_path, payload_sha256, payload_md5, payload_size, payload_mime_type;
- reserved_drive_file_id, created_at.

Scope і базовий route snapshot записуються **в одній транзакції з новим job**. Шлях джерела й існуюча accounting metadata лишаються незмінними. Пізніша зміна активного профілю або route-файла не змінює snapshot.

Snapshot відразу містить exact company root, валідований рік і bounded шаблон дерева; resolved IDs додаються одноразово після lineage verification. Для ідемпотентного річного/type/month folder resolution використовується чинна google_drive_folder_cache з новим окремим namespace, що включає route revision, root ID, рік і path; existing cache rows не переписуються. Якщо потрібно створити папку, її pre-generated ID резервується в цій таблиці до files.create, з unique key/CAS і повторним читанням переможного ID. Reservation не є доказом існування папки: перед використанням обов’язковий files.get/readback правильного name/parent/mimeType/trashed. Після crash/timeout повторюється той самий ID; duplicate-name ambiguity блокує resolution. Нової третьої таблиці для folder cache не потрібно.

Legacy jobs без context продовжують legacy шлях. До ввімкнення override потрібно інвентаризувати outstanding ZEVS jobs; вони не мають непомітно завантажитися за старим route під час cutover. Їх drain/hold/requeue план погоджується окремо за результатами аудиту, без автоматичного переписування.

| Side effect | Власник | Gate | Fail-safe |
|---|---|---|---|
| Local source + metadata | Чинні GmailStatementStore / save_confirmed_accounting_document | Existing validation, authorization, confirmation там, де потрібно | Оригінал не змінювати |
| Queue + route snapshot | ArchiveJobService / archive service extension | Exact workspace, type, year, safe source path | Без generic/cross-tenant fallback |
| PDF archive payload | Новий детермінований helper, викликаний ArchiveWorker | Known opening secret, supported PDF, verified source hash | Не upload encrypted source замість потрібної копії |
| Folder/read/upload | Чинний owner OAuth provider extension | Frozen IDs, той самий runtime grant | Без broad folder search / permission changes |
| Create missing annual/type/month folder | Scoped route resolver у чинному provider | Exact approved company root, validated document year, zero exact children після повного bounded lookup, reserved ID | No cross-root/current-year fallback; verify persisted folder ID |
| Mark uploaded | Чинний archive lifecycle | Remote verification successful | Не приймати лише непорожній ID за повний доказ |
| Failure notice persistence | Новий notification service | Terminal job або явний prequeue failure | Unique event key; джерело збережене |
| Telegram send | Archive scheduler з ін’єкцією Bot | Перевірений recipient, outbox lease | Retry delivery незалежно від upload |
| Cleanup | Scoped payload helper + чинний retention owner | Verified terminal state і scope | Не видаляти encrypted source при failure |

### Копія PDF без пароля

1. Gmail original зберігається byte-for-byte як зараз; SHA-256 є доказом незмінності.
2. Worker працює лише з новим snapshot `payload_mode=pdf_without_password`.
3. PDF відкривається з відомим opening password із secret-файла. Password recovery/bruteforce не додається.
4. Усі сторінки клонуються PDF-бібліотекою в окремий документ без encryption. Не OCR, не скриншоти і не реконструкція сум/транзакцій.
5. Якщо PDF містить цифровий підпис, автоматичне перепакування зупиняється з `signed_pdf_requires_review`: не створювати копію з оманливою валідністю підпису.
6. Копія перевідкривається без пароля; `is_encrypted=False`, page count збігається, підтримуваний header/period і контрольні текстові значення не втрачені.
7. Payload атомарно зберігається у приватному `storage/workspaces/{storage_key}/archive_payloads/{job_id}/statement.pdf`: директорії 0700, файл 0600. Це новий службовий артефакт, не новий accounting original.
8. Точні bytes, hash, size і filename фіксуються перед першим upload і повторно використовуються. Змінені/відсутні payload після вже зарезервованого remote ID не можуть тихо породити іншу версію bytes: потрібен explicit failure/review.
9. Після verified uploaded або terminal failure службовий decrypted payload видаляється; encrypted source залишається. Аварійні tmp прибираються лише в точному scoped payload tree й без активного lease.
10. Підтримуваний unencrypted PDF проходить той самий readback і може копіюватися без повторної перебудови. Непідтримуваний/пошкоджений PDF не зберігається як «розшифрований».

Для виписок пропонується детермінована назва `ZEVS_Tatra_YYYY-MM_<opaque_import_ref>.pdf`; не перезаписувати наявний PDF лише через однаковий місяць. Receipt filename лишається чинним safe filename.

### Upload і retry без повторного створення файла

Для нових context jobs:
- Google files.generateIds резервує ID; його треба persist атомарно до files.create.
- Після reservation усі retries використовують тільки цей ID, те саме destination і ті самі payload bytes.
- Timeout після успішного remote create → files.get того самого ID; 409 при повторному create → readback, а не новий ID.
- До uploaded перевірити id, parents, mimeType, size, md5Checksum, trashed=false та opaque delivery reference в appProperties.
- Reserved ID з чужим parent/content/reference → terminal mismatch, без overwrite/move.
- Для receipts exact base ID → YYYY-MM. Існуючу місячну папку використовувати; якщо знайдено кілька однойменних дітей, не обирати першу навмання. Final child ID фіксується в context.
- Прямий Vypisy target не доповнюється ще раз workspace/year/bankove_vypisy.

Google офіційно описує pre-generated IDs як механізм безпечного повторення create/upload після невизначеного server result; повторне створення повертає 409 замість дубліката:
https://developers.google.com/workspace/drive/api/guides/manage-uploads
https://developers.google.com/workspace/drive/api/guides/create-file

### Класифікація помилок

- Timeout/network/429/5xx і bounded provider-unavailable при enabled archive → existing retry policy.
- Відсутній runtime grant/reauth або тимчасова недоступність provider не можуть вічно приховувати runnable jobs за scheduler noop: enabled mode має дати worker обмежений failure lifecycle.
- Invalid password, corrupt/signed unsupported PDF, forbidden target, unknown year, revoked authorization, unsafe source/route → fail closed; не витрачати 5 однакових upload attempts на завідомо нездійсненну операцію.
- Якщо доступна автоматична credential refresh, лишається чинним owner OAuth boundary; новий consent/переписування scopes не додається.
- Явно disabled Drive не дорівнює success: документ лишається local-only, response/setup notice це пояснює.
- Після failed не скидати attempts і не re-enqueue автоматично.

Якщо після останнього timeout неможливо встановити, чи remote create відбувся, статус є failure перевірки, а текст повідомлення — «не вдалося підтвердити збереження на Google Drive». Не стверджувати, що файла точно немає. Reserved ID і очікувані hashes зберігаються для подальшого read-only reconciliation.

Unreadable/missing secret-файл не має обривати весь Gmail tick до збереження дозволеного source: це bounded setup failure, для якого після перевірки workspace потрібно зберегти доступний original і створити review notice, без upload і без виведення exception/secret.

### Durable failure notice

Новий delivery service має additive таблицю `archive_failure_notices`:
event_key UNIQUE, job_id nullable, document_id, workspace_id, recipient_telegram_id, failure_kind, safe_error_code, safe_display_name, upload_attempts, max_attempts, status, delivery_attempts, next_attempt_at, locked_by, lease_until, sent_at, telegram_message_id, created_at, updated_at.

Для terminal job event_key є детермінованим від job_id і archive_failed. Для prequeue failure — від workspace/document і bounded failure_kind. Не записувати raw exception, password, банківський текст, OAuth token, sender/subject.

Scheduler:
- після worker batch і після restart підбирає failed jobs та через INSERT OR IGNORE відновлює відсутні notice rows;
- сканує тільки failure transitions після явно зафіксованого rollout cutoff, щоб не засипати чат старими історичними збоями;
- охоплює common archive_jobs document types (receipt, incoming_invoice, invoice_pdf, bank_statement_original), кожен лише у власний authorized chat;
- забирає notice під lease, revalidate current membership для original job actor, надсилає без FSM/keyboard mutation;
- sent_at записує тільки після успішного Bot.send_message;
- temporary Telegram errors → delayed notice retry; retry_after поважається;
- bot blocked/invalid recipient → delivery_blocked, safe log; upload не повторюється через помилку Telegram.

Нові prequeue failures також не можуть бути лише warning:
- receipt enqueue error: confirmed-save response явно каже, що документ локально збережений, але Drive enqueue не вдалося; за доступної DB створюється durable event;
- Gmail archive-withheld / password/period/enqueue error: local original збережений, scheduler ставить окремий safe notice, без вигаданого upload success.

За справного процесу одна business failure дає один notice. **Exactly-once Telegram delivery не обіцяється**: crash після send і до sent_at може дати повтор того самого повідомлення. Однаковий короткий reference дозволяє його впізнати. Повністю заблокований чат, недоступна DB або зупинений процес унеможливлюють гарантію негайної доставки; збої не можна видавати за успіх.

## 10. Authorization, Tenant, And Precision Boundaries

- Чинні authorization guards перед STT/LLM/LMM/temp files лишаються.
- Receipt workspace фіксується в існуючому FSM і revalidate перед save.
- Background source використовує resolve_for_background_workspace; user active selection не є authority.
- Override строго за exact workspace_id/type; рік береться з валідованого документа і frozen job snapshot. Реальний workspace_id не вгадується з Zevs_2026. Усе річне дерево обмежене exact company root.
- Перед зовнішнім side effect перевіряються source containment, original ownership, frozen destination і active authority. Для нового notice повторно require_membership(original_actor, original_workspace).
- Route payload не береться з Telegram callback, голосу, LLM або metadata документа, що користувач може підмінити.
- Known opening password не виводиться, не передається моделям, не зберігається в SQLite/sidecar і не включається в user-facing diagnostics.
- Поточний owner OAuth залишається спільним налаштованим connection; нові scopes/accounts/token orchestration не створюються.
- Права на Drive не змінюються. Якщо runtime account не може писати у target, rollout не дозволяється.
- Серверний контекст не переносить FakturaBot у trader/research; операції лише /bot і /bot/repo. У наданому server context старий опис tenant token відрізняється від чинного AGENTS shared-token baseline; token model цей task не змінює.

## 11. User-Facing Response And Exit Contract

| Outcome | Відповідь | FSM / keyboard / наступна дія |
|---|---|---|
| Receipt local save + enqueue | «Doklad bol uložený lokálne. Archivácia na Google Drive prebieha na pozadí.» | Existing IDLE і ReplyKeyboardRemove |
| Gmail local import | Явно local save; period known/withheld; жодного твердження «вже в Drive» | Чужий FSM і keyboard без змін |
| Verified uploaded | Статус можна читати як archived; додатковий success chat spam не потрібний | Без нової дії |
| Retry wait | Не сповіщати на кожну спробу; status pending/retry | Без FSM mutation |
| 5 failures | Terminal notice з назвою, 5 attempts, local original retained, safe reason/reference | Без кнопок; звернутися до admin |
| Permanent failure до 5 | Явно неможливо архівувати; причина; не заявляти, що використано всі спроби | Без кнопок; admin review |
| Enqueue failed | Local success окремо від Drive failure | Receipt exit як після save; не просити повторно вводити документ |
| Wrong password / period unknown | Source retained; archive withheld; admin має перевірити secret/period | Не просити пароль у Telegram |
| Cancel/back/unknown у preview | Чинні response/state/cleanup | Не enqueue |
| Notice delivery failed | Жодного fake «повідомлено» | Durable retry або delivery_blocked |

Пропонований terminal template мовою чинного бота:

> Dokument „{safe_name}“ sa nepodarilo uložiť na Google Drive po {attempts} pokusoch. Lokálny originál zostal zachovaný. Obráťte sa na správcu. Dôvod: {safe_reason}. Referencia: {short_ref}.

Permanent-failure template не містить «po 5 pokusoch», якщо їх не було. Filename екранується для чинного parse mode. Повідомлення йде original actor/owner, а не глобальному admin замість користувача.

Фразу «Lokálny originál zostal zachovaný» дозволено використовувати лише після scoped перевірки наявності source. Якщо original відсутній/нечитається, повідомлення прямо каже про цю проблему; воно не обіцяє збережену локальну копію. Для невизначеного результату remote upload використовується формулювання «Uloženie na Google Drive sa nepodarilo potvrdiť».

## 12. Product Truth And InfoHelp Contract

Capability IDs: існуючі `gmail_statement_collection`, `google_drive_invoice_storage`.
Статус лишається partial/requires_setup/requires_admin/requires_external_credentials.

Після реалізації та verified setup бот може чесно сказати:
- для налаштованого ZEVS архівна копія підтримуваної виписки зберігається без пароля у Vypisy відповідного року;
- річні папки Zevs_YYYY і потрібні підпапки перевикористовуються або автоматично створюються при першому документі цього року, якщо runtime має права в затвердженому company root;
- блочки ZEVS зберігаються в blocky за місяцями;
- encrypted source лишається локально;
- Drive upload асинхронний, із bounded retry;
- при остаточному збої створюється повідомлення у Telegram;
- «надіслано» означає підтверджений Telegram API result, а не лише запис outbox.

Не може казати:
- усі PDF/усі банки/будь-які паролі підтримуються;
- виписку розпарсено чи платежі звірено;
- local save доводить Drive upload;
- історичні файли перенесені/розшифровані;
- папка 2027 вже фізично створена або доступна runtime до verified create/readback;
- будь-який документ, отриманий після 1 січня, належить новому року;
- Telegram гарантовано отримає exactly one message за будь-якого збою;
- реальний сервер підключений, якщо відомий тільки статичний registry.

Відповідь на «Чи можеш?» — Product Truth з live setup context або чесним unknown/requires_setup; без execution.
Відповідь на «Як користуватися?» — чинний receipt upload+confirmation або налаштований Gmail collector, без передачі пароля у чат.
Safe next steps — чинні /gmail_status, /google_drive_status та admin review.

Обов’язкова синхронізація під час майбутньої реалізації:
- product_truth.py;
- Product_Truth_Layer.md / Info_Help_Guidance_Layer.md;
- Gmail runbook і protected-PDF architecture contract;
- Google_Drive_Faktury_Bloceky_Storage_Policy.md;
- TZ/README там, де змінилася обіцянка продукту;
- PROJECT_LOG.md, CHANGELOG.md;
- новий Conversation Acceptance Proof.
Не лишати стару абсолютну фразу «decrypted content is not stored» без опису вузького archive-payload exception.

## 13. Negative-Space And Regression Contract

Не змінювати:
- invoice creation, mark-paid, annual outgoing faktury routes;
- incoming invoice destination;
- receipts інших workspace;
- classification/extraction/category decisions;
- підтвердження перед accounting save;
- canonical action/resolver dictionaries;
- voice precision boundaries;
- access approval/onboarding;
- active-FSM routing, stale callback rejection і keyboard ownership;
- local originals/metadata paths, hash/dedup semantics;
- Gmail readonly scopes і mailbox content;
- connection/OAuth settings, shared bot-token model;
- retention інших типів документів.

Новий payload не повинен з’явитися у /blocek як другий accounting document.
Зміна route після enqueue не змінює queued job.
Failure notice не виконує upload, не запускає rollback successful local save і не очищає чужий FSM.
InfoHelp queries не створюють jobs, notices або credentials reads.

## 14. Acceptance Scenario Contract

У таблиці `Q` = existing job lifecycle; `N` = notice delivery lifecycle. Для кожного сценарію у майбутньому acceptance proof потрібні observed trace, final state, side-effect counts і keyboard assertions, де застосовно. Нижче — **очікування**, не вже отримані результати.

| # | Preconditions + точний input/event | Action / data | State sequence / effects | Final state / user outcome |
|---|---|---|---|---|
| 1 | Authorized ZEVS; /add_blocek; receipt.jpg; «✅ Uložiť s kategóriou» у чинному preview | Existing intake; receipt; validated 2026-10 | Existing upload→preview→save→IDLE; Q pending→uploaded; один файл у blocky/2026-10 | Local saved, verified Drive parent; keyboard removed |
| 2 | Те саме preview; voice transcript «uložiť s kategóriou» | Existing same decision helper | Рівно один save/enqueue; не parallel voice flow | Той самий result/cleanup, що #1 |
| 3 | Те саме preview; equivalent typed choice і reply button окремими тестами | Existing preview decision | Converge to same confirmed save | Однакова queue та exit |
| 4 | Idle authorized attachment receipt.jpg; чинний router розпізнав receipt | Existing attachment→intake | Classification не upload; тільки confirmation запускає save/job | Target як #1; no premature side effect |
| 5 | Background tick; новий approved-source encrypted statement з header 2026-09 | No new canonical; bank_statement_original; period=2026-09 | Source bytes unchanged; private payload без encryption; Q→uploaded | PDF без пароля безпосередньо Vypisy; source retained |
| 6 | Supported вже unencrypted statement | Same existing Gmail event | Validated bytes; без зайвої втрати content; direct target | Opens without password |
| 7 | Known encrypted input; secret відсутній/неправильний | bounded password_required/password_invalid | Local source retained; no encrypted substitute upload; N pending→sent | Явне failure notice; secret не в logs/DB/chat |
| 8 | PDF із conflicting period або no text | period_ambiguous/text_unavailable | No guessed year/month, no upload; one review notice | Source retained; non-FSM user informed |
| 9 | Підписаний PDF / corrupt PDF / unsupported encryption | signed_pdf_requires_review / bounded format error | No misleading transformed upload; source retained | Immediate safe review notice |
| 10 | Transient provider errors на всіх виконаннях; max_attempts=5 | Same job/context | Q: pending→retry_wait ×4→failed на 5-й; no early notice, no sixth attempt | N sent once in ordinary ticks; source retained |
| 11 | Transient error двічі; третє виконання успішне | Same reserved ID/bytes | Один remote file; Q uploaded; failed event відсутній | Немає false failure notice |
| 12 | enabled archive; provider build повернув None | bounded provider unavailable | Не нескінченний scheduler noop; bounded retry lifecycle | Після limit — notice |
| 13 | Drive create відбувся; response timeout; повторний tick | Same persisted reserved file ID | get/409 reconciliation, verified parent/hash; no new ID | Один файл; Q uploaded |
| 14 | Reserved ID існує з іншим parent/hash/reference | mismatch | No overwrite/move; fail closed | Failed + notice; original preserved |
| 15 | Упав процес після failed до enqueue notice | Persisted failed post-cutoff job | Restart scanner INSERT OR IGNORE → N pending | Повідомлення не втрачено через restart |
| 16 | Telegram temporary error; наступний send успішний | Same event_key | N retry_wait→sent; sent_at лише після success; no upload retry | Safe eventual delivery; штатно один notice |
| 17 | Crash після Telegram send до sent_at | Same event_key/reference | Можливий повтор notice; remote upload не повторюється | At-least-once limitation явно documented/tested |
| 18 | User blocked bot або membership revoked | Same scoped recipient | No send to another chat; delivery_blocked / forbidden | No privacy leak; bounded diagnostics |
| 19 | Receipt local save succeeds, enqueue raises | Same workspace/document | Local success preserved; truthful immediate response; durable event за available DB | IDLE; keyboard removed; no fake Drive success |
| 20 | Switch active workspace після enqueue | Original snapshot | Worker не consult new active selection | Original target/recipient authority preserved |
| 21 | Source path іншого workspace; forged route ID; unauthorized input | No valid authorized action | No temp/AI/storage/upload for unauthorized; mismatched job rejected | No cross-tenant effect |
| 22 | Preview text «не знаю»; missing/invalid confirmation | Existing unknown decision | Remain preview; no save/job | Clarification, existing keyboard retained |
| 23 | Preview cancel / category back / expired preview | Existing controls | Existing safe state/cleanup; no archive effect | Correct terminal/return state and keyboard |
| 24 | Notice arrives while user у work-time/invoice FSM | Existing background event | Send без reply markup/keyboard removal; no FSM write | User continues existing flow |
| 25 | Incoming invoice ZEVS / outgoing invoice / receipt іншого workspace | Existing respective actions | Existing targets unchanged | Regression behavior intact |
| 26 | «Vieš ukladať výpisy bez hesla?» text і voice | Existing info_help | Product Truth answer only; jobs/notices/files delta=0 | Honest partial/setup answer |
| 27 | Clock=2027; нові receipt 2027-01 та statement period 2027-01; Zevs_2027 відсутня; approved company root доступний | Existing business actions; frozen archive_year=2027 | Create/reuse Zevs_2027; Vypisy для statement; blocky/2027-01 для receipt; verify IDs | Правильне дерево 2027, no files under 2026; no failure notice |
| 28 | Duplicate Gmail source/content / repeated approved-save enqueue | Existing dedup + queue idempotency | No second job/context/file; old target not rewritten | Stable original/archive identity |
| 29 | Additive schema initialization на legacy DB двічі | Internal schema only | Legacy rows/paths/statuses unchanged; contexts не fabricated | Integrity ok; rollback compatible |
| 30 | Rollout audit знайшов pending ZEVS legacy jobs | No automatic repair action | Activation blocked до reviewed disposition | No hidden historical retarget |
| 31 | Readback remote size/checksum/parent не збігається | verification failure | No uploaded/no source cleanup | Bounded retry/failure notice |
| 32 | Existing local-original deletion option enabled; failed upload | Existing retention policy | Не видаляти source/metadata при pending/failed | Документ доступний для recovery |
| 33 | Persisted job посилається на відсутній original | bounded local_file_missing | No upload; no claim source retained; safe notice | User явно знає про відсутню локальну копію |
| 34 | Receipt дата 2026-12-31 / statement period 2026-12; received_at=2027-01-10 | archive_year=2026, month=12 | Reuse exact 2026 anchors; не create/use 2027 для цих jobs | Документи у правильному старому році |
| 35 | Job enqueue 2026-12-31, retry 2027-01-01 | Frozen year і IDs | Retry не переобчислює рік із now | Той самий destination і один файл |
| 36 | Zevs_2027/Vypisy/blocky/2027-01 створені раніше | Same bounded templates | Reuse verified direct-child IDs; zero duplicate folder create | Правильний 2027 archive |
| 37 | Crash/timeout під час annual/type/month folder create; повторний worker | Same persisted folder reservation | get/409 reconciliation того самого ID; verify lineage | Один bot-created folder на cache key |
| 38 | Два Zevs_2027 під approved root / no permission / wrong parent cached ID | bounded route ambiguity/forbidden/mismatch | No first-match, no fallback to 2026, no upload | Retry/permanent policy і safe notice; original retained |
| 39 | Clock=2028; документ 2028; approved annual route | Same generic year contract | Zevs_2028 використовується/створюється on demand | Немає hardcoded 2027 або щорічного code edit |
| 40 | Невалідована/відсутня дата receipt або неоднозначний statement period біля 1 січня | Unknown period/year | No guessed current year, no folder create/upload | Existing clarification/review і safe notice |

Потрібні focus suites після реалізації: gmail statement period/collector/archive/scheduler/config, accounting_document intake/workspace isolation, archive job/worker/provider, notification service/scheduler, Product Truth/InfoHelp, tenant/access, schema/dry-run, існуючі voice/state/keyboard regressions. Далі — required repository checks за AGENTS і focused smoke.

Live smoke після окремого deployment approval:
- один погоджений новий ZEVS statement і один confirmed receipt;
- незалежний Drive API readback exact parents/hash;
- PDF download/reopen без пароля; порівняння сторінок оригіналу й копії в приватному QA;
- synthetic failure exercise без навмисного ламання реальних OAuth credentials;
- справжнє повідомлення у власний authorized Telegram chat;
- post-smoke DB/storage integrity.

Component tests без цього evidence не дають права стверджувати «працює на сервері».

## 15. Out Of Scope And Known Architecture Gaps

Не включено:
- implementation prompt до погодження;
- код, commit, push, PR, merge, deployment у цій сесії;
- читання/виведення реального password value;
- bank transaction parsing, payment matching, accounting conclusions;
- owner-password recovery, універсальне редагування PDF;
- зміна OAuth scopes/accounts/permissions;
- автоматичне переміщення старих Drive files;
- batch decrypt/reupload already archived statements;
- переписування старих jobs/import metadata;
- UI route editor, новий retry command, retry callback/FSM;
- календарне завчасне створення порожніх річних дерев, копіювання всіх старих підпапок або перейменування legacy Zevs 2024; нові річні Vypisy/blocky створюються лише on demand у погодженому scope;
- новий SaaS/tenant/token architecture;
- нові AI/self-learning features.

Відомі поточні gaps:
1. gmail_statement_imports.archive_status може лишатися enqueue-era archive_pending, коли authoritative job/state already uploaded. Це прямо записано в PROJECT_LOG 2026-08-02. Нові status/readback/notice рішення мають дивитися на archive_jobs і archive state, а не довіряти цьому summary field. Історичний repair не входить.
2. Поточний provider не має remote idempotency/readback contract для нового режиму; його треба додати лише в погодженій delivery-context гілці.
3. Права runtime бота і точний workspace не підтверджені live; це deployment blockers, а не доведений server failure.
4. Telegram не дає transactional exactly-once разом із local DB.

### Migration / backup / rollback plan для майбутньої реалізації

Поточні дані: archive_jobs/accounting_document_archive_state, Gmail immutable originals+sidecars, accounting originals+metadata, owner OAuth connection, google_drive_folder_cache. Пропозиція: дві нові additive таблиці, окремі private payload dirs, routes file і нові scoped reservation/cache rows лише для потрібних річних/type/month folders. Чинні paths/rows не переписуються.

До production writes:
1. Read-only exact workspace/membership/source-binding audit.
2. Runtime secret existence/readability перевіряється без виведення вмісту.
3. Read-only runtime-credential folder metadata check для exact company root, 2026 lineage/anchors і available create permissions; inventory pending/retry/uploading ZEVS jobs. Відсутня Zevs_2027 не є setup failure, якщо дозволено її scoped create.
4. Dry-run mapping: source document → existing period/date → proposed exact destination/payload mode. Existing uploaded files лише інвентаризувати.
5. Погоджений backup: online SQLite backup з quick_check, storage, config/env і image/commit rollback anchor; secrets у закритих правах.
6. Короткий writer freeze для застосування additive schema й activation cutover; fingerprint перед apply має збігатися з reviewed audit.
7. Idempotent schema apply, unchanged-legacy-row verification, cutover timestamp і activation routes.
8. Controlled smoke та independent readback.

Окреме погодження operational writes потрібне після конкретного audit/dry-run результату. Не змішувати його з погодженням цього дизайну.

Rollback:
- вимкнути нові override/notification execution flags і призупинити workers із новими context jobs перед старим image;
- старий worker не повинен підхопити new override jobs без context support;
- encrypted originals і business metadata зберігаються;
- не drop нові таблиці та не restore full DB поверх нової бізнес-активності;
- нові вже uploaded Drive files не видаляти/не move автоматично;
- rollback pause з reported pending state кращий за upload у неправильний legacy target.

## 16. Evidence Index And Handoff Readiness

### Нормативні документи

- AGENTS.md — sources of truth, approvals, tenant isolation, migration-sensitive writes, confirmation and keyboard lifecycle.
- docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md — proof requirements і prohibition handoff до complete design.
- Наданий Top_Level_Subflow_Architecture_Design_Proof_Contract.md — прочитаний перед проєктуванням.
- Наданий 02-FakturaBot_Server_Agent_Context.md — /bot isolation, secrets policy, server update boundary.
- docs/Code_Agent_Handoff_Contract.md; docs/Implementation_Agent_Checklist.md — scoped implementation і completion evidence.
- docs/FakturaBot_Data_Migration_Runbook.md — audit/backup/dry-run/rollback.
- docs/Evaluation_and_Smoke_Test_Standards.md — conversation acceptance і реальний smoke.
- docs/architecture/GMAIL_PROTECTED_STATEMENT_PERIOD_ROUTING_V1_ARCHITECTURE_DESIGN_PROOF.md — immutable original, secret, period, no-decrypted-copy baseline.
- docs/architecture/ACCOUNTING_DOCUMENT_GOOGLE_DRIVE_WORKSPACE_FOLDER_ISOLATION_V1_ARCHITECTURE_DESIGN_PROOF.md — bound workspace і async archive ownership.
- docs/Google_Gmail_Statement_Collector_Setup_Runbook.md; docs/Google_Drive_Faktury_Bloceky_Storage_Policy.md — current setup/storage semantics.
- docs/Product_Truth_Layer.md, docs/Info_Help_Guidance_Layer.md, docs/TZ_FakturaBot.md — guidance і capability scope.

### Код: поточні власники

| Claim | File / symbol |
|---|---|
| Відкриття лише для header/period | bot/services/gmail_statement_period.py::detect_gmail_statement_period |
| Незмінні downloaded bytes у storage | bot/services/gmail_statement_collector.py::GmailStatementCollector.run_once; GmailStatementStore._write_original_atomically |
| File-backed secret | bot/services/google_gmail_config.py::load_statement_pdf_open_password |
| Period gate і enqueue | bot/services/gmail_statement_scheduler.py::_run_tick |
| Local-import notification, не Drive completion | bot/services/gmail_statement_scheduler.py::_notification_text |
| Receipt confirmed save і log-only enqueue exception | bot/handlers/accounting_document_intake.py::_save_accounting_document_from_state; _enqueue_archive_after_confirmed_save |
| Workspace-specific route validation | bot/services/accounting_document_archive_service.py::enqueue_confirmed_document |
| Existing path contracts | bot/services/accounting_document_archive_path.py; gmail_statement_archive_path.py |
| Max attempts, transitions, lease, dedup | bot/services/archive_job_service.py::enqueue_job; claim_next_runnable_job; mark_retry_wait |
| 15-minute retry, retained source | bot/services/archive_worker.py::ArchiveWorker; DEFAULT_ARCHIVE_RETRY_DELAY |
| Provider None early noop і відсутність Bot | bot/services/google_drive_archive_scheduler.py::process_google_drive_archive_once; run_google_drive_archive_scheduler |
| Глобальний root/path resolution, non-idempotent create | bot/services/google_drive_owner_oauth_client.py::upload_file; _root_folder_id; _upload_to_folder |
| Background workspace authority | bot/services/workspace_context.py::resolve_for_background_workspace; require_membership |
| Existing schema | bot/services/db.py::ARCHIVE_JOBS_SCHEMA; ACCOUNTING_DOCUMENT_ARCHIVE_STATE_SCHEMA |
| Existing folder reservation/cache schema | bot/services/db.py::GOOGLE_DRIVE_FOLDER_CACHE_SCHEMA; unique workspace/provider/folder_path |
| Capability restrictions | bot/services/product_truth.py — gmail_statement_collection; google_drive_invoice_storage |
| Scheduler wiring | bot/main.py::main |

### Поточні тести як контракти, не результати цієї сесії

- tests/test_gmail_statement_period.py::test_encrypted_statement_uses_opening_password_without_owner_password
- tests/test_gmail_statement_period.py::test_encrypted_statement_fails_closed_for_missing_or_wrong_password
- tests/test_gmail_statement_collector.py::test_period_metadata_keeps_original_bytes_and_never_writes_password
- tests/test_gmail_statement_collector.py::test_atomic_store_source_and_content_dedup
- tests/test_gmail_statement_scheduler.py::test_notification_is_bounded_and_does_not_claim_parsing
- tests/test_archive_worker.py::test_max_attempts_transient_failure_becomes_failed
- tests/test_archive_worker.py::test_permanent_failure_sets_failed_and_preserves_local_file
- tests/test_archive_job_service.py::test_enqueue_after_terminal_job_returns_existing_without_duplicate
- tests/test_accounting_document_drive_workspace_isolation.py — scope/path isolation.

### Project log

- 2026-08-04 — Protected Gmail statement period routing V1: secret deployment, encrypted source preservation, supported period smoke, historical repair boundary.
- 2026-08-02 — Owner Google Drive reauthorized and Gmail statement archived; Gmail/Drive Product Truth synchronized: authoritative job/state і stale import summary.
- 2026-08-31 — Google Drive reauthorization and workspace archive-worker repair: реальна важливість provider failure, retention і controlled requeue.
- 2026-09-02 — Annual outgoing-invoice Drive folders: outgoing invoices не мають потрапити в новий receipt/statement route.

### Висновок readiness

`ready_for_handoff` означає: запропоновані архітектурні рішення, side-effect межі, failure/recovery, parity, Product Truth, migration safeguards і acceptance сценарії визначені.

**Дизайн погоджено користувачем; реалізацію, merge/deploy approval і перевірений live доступ це не доводить.**

Gate для підготовки implementation prompt пройдено явним погодженням користувача 2026-10-31. Агент реалізації не має дозволу самостійно змінювати scope, FSM, routing strategy, destinations, retry policy, secret handling або retention; design/runtime contradiction повертається на узгодження.

