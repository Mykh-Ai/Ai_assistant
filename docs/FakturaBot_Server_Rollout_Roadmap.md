# FakturaBot Server Rollout Roadmap

## 1) Мета документа

Цей документ фіксує практичний стан і наступні кроки server rollout для FakturaBot:
від поточного production-like owner-run baseline до першого зовнішнього dry run.

Документ не є джерелом продуктової істини для MVP. Якщо є конфлікт, пріоритет мають:
1. `docs/TZ_FakturaBot.md`
2. `PROJECT_LOG.md`
3. поточний код
4. `CHANGELOG.md`

Для будь-яких реальних серверних дій спочатку перевіряти приватний локальний runbook:
`docs/local-only/FakturaBot_Server_Agent_Context.md`.

## 2) Audit стану на 2026-05-02

Статуси:
- `DONE` - є в коді/документації/журналі і не потребує додаткового підтвердження для поточного рівня.
- `PARTIAL` - частина вже зроблена, але етап ще не можна вважати завершеним.
- `NOT STARTED` - є лише план або концепція, runtime/операційного процесу ще немає.
- `FUTURE` - свідомо винесено за межі найближчого rollout.

| Етап | Статус | Що підтверджено | Що ще не завершено |
| --- | --- | --- | --- |
| Stage 1 - Server foundation | `PARTIAL` | Є `docker-compose.prod.yml`, `.env.server.example`, `scripts/update_repo.sh`, `scripts/deploy_owner_run.sh`, локальний server context/runbook, правило не публікувати секрети. | Формально не закрито backup/restore smoke-check, немає зафіксованого production secrets policy вище test-stage рівня, немає завершеного deployment checklist з результатами останньої перевірки. |
| Stage 2 - First self-hosted production-like run (owner) | `PARTIAL` | У `PROJECT_LOG.md` є записи про server deploy, server invoice cleanup/correction, Linux PDF font fix; README описує production-like owner-run baseline. | Немає останнього підписаного checklist: `/start`, повний invoice flow, PDF/QR, persistence після restart, logs, backup/restore. |
| Stage 3 - Tenant model definition | `NOT STARTED` | Концепція shared backend + tenant isolation описана в roadmap/local context. | Немає формального tenant contract і runtime-моделі tenant id/config/data/session/secrets isolation. |
| Stage 4 - Multi-bot routing | `NOT STARTED` | Бажаний напрямок визначений: один backend для кількох ботів/тенантів. | Немає runtime routing для кількох Telegram bot tokens, guardrails проти cross-tenant leakage і тестів маршрутизації. |
| Stage 5 - Manual onboarding v1 | `NOT STARTED` | Є локальний server context для ручних операцій без секретів у публічних файлах. | Немає завершеного manual onboarding runbook для першого tenant/client, smoke-check процедури і checklist без секретів. |
| Stage 6 - First external client dry run | `NOT STARTED` | Цільовий сценарій визначений. | Немає запису, що зовнішній клієнт пройшов `/start` і базовий invoice flow на server-hosted tenant. |
| Stage 7 - Later improvements | `FUTURE` | Теми визначені як після першого dry run. | Self-service setup page, vault/KMS-подібне hardening, admin tooling, Google Drive sync, Android/app layer не є поточним milestone. |

## 3) Поточна rollout концепція

Near-term напрямок:
- один shared backend service;
- один codebase;
- одна керована server/runtime база;
- tenant isolation на рівні клієнта/бота/конфігурації/даних/сесій;
- Telegram-first rollout;
- ручний onboarding перших клієнтів;
- setup page/self-service onboarding - пізніше;
- Android/UI шар - пізніше.

Що не є базовою стратегією першого rollout:
- multi-Docker-per-client як дефолт для кожного нового клієнта;
- повністю автоматичний SaaS onboarding до перевіреного ручного процесу;
- передчасна рольова система або admin panel.

## 4) Пріоритети

### P0 - закрити owner-run baseline

Задачі:
- перевірити `/start` на server-hosted owner instance;
- пройти повний invoice flow end-to-end;
- перевірити PDF generation і Pay by Square QR;
- перевірити, що `pdf_path` і створені файли зберігаються після restart;
- перевірити логи і відсутність критичних runtime errors;
- виконати backup/restore smoke-check або явно зафіксувати, що він ще не виконаний.

Definition of done:
- у `PROJECT_LOG.md` є запис з датою, командами/діями перевірки і результатом;
- відомо, як відновити runtime дані перед будь-якою DB/storage міграцією.

### P0 - зафіксувати DB/storage migration discipline

Поточний стан:
- повної системи міграцій БД у проєкті немає;
- `bot/services/db.py` виконує bootstrap через `init_db()`;
- є fail-loud перевірки очікуваних колонок через `PRAGMA table_info`;
- сумісне додавання `invoice_item.item_description_raw` робиться автоматичним `ALTER TABLE`;
- інші зміни схеми не можна вважати автоматично мігрованими.

Рішення для найближчого етапу:
- не впроваджувати складну migration framework без конкретної schema/storage зміни;
- перед наступною реальною зміною схеми додати явний migration plan:
  - backup перед міграцією;
  - reversible або принаймні repeatable migration script;
  - `schema_migrations` або інший простий журнал застосованих міграцій;
  - smoke-check після міграції;
  - заборона тихого переміщення/перегенерації invoice PDF без збереження `pdf_path`.

### P1 - dependency management decision (`requirements.txt` vs `uv`)

Поточний стан:
- проєкт використовує `requirements.txt`;
- `Dockerfile` встановлює залежності через `pip install -r requirements.txt`;
- у roadmap/TZ немає зафіксованої вимоги переходу на `uv`.

Рішення:
- перехід на `uv` не є блокером для owner-run або першого dry run;
- `uv` варто розглянути окремою P1-задачею перед CI/server hardening, якщо потрібні:
  - lockfile;
  - швидше і відтворюване встановлення залежностей;
  - `pyproject.toml` як єдина точка dependency metadata;
  - окремі dev/test dependency groups.

Не змішувати перехід на `uv` з DB migration. Це різні ризики і різні rollback-плани.

### P1 - tenant contract

Задачі:
- визначити tenant identifier;
- описати per-tenant config;
- описати per-tenant secrets ownership і storage policy;
- описати ізоляцію data/session context;
- визначити, які таблиці/файли стають tenant-aware;
- додати guardrails проти cross-tenant leakage.

Definition of done:
- є окремий документ або секція в цьому roadmap з tenant contract;
- зміни узгоджені з `docs/TZ_FakturaBot.md` або явно зафіксовані в `PROJECT_LOG.md`.

### P1 - manual onboarding v1

Задачі:
- створити public checklist без секретів;
- створити/оновити local-only runbook для реальних token/API key дій;
- описати створення tenant config/storage;
- описати smoke-check після активації tenant bot;
- визначити rollback/deactivation steps для тестового клієнта.

### P2 - multi-bot routing

Задачі:
- мапити Telegram updates до правильного tenant;
- завантажувати коректні tenant config/secrets/data;
- додати тести маршрутизації;
- додати runtime guardrails проти cross-tenant leakage.

Передумова:
- P1 tenant contract має бути закритий до реалізації routing.

### P2 - first external client dry run

Задачі:
- підготувати клієнтський bot token/config;
- активувати tenant;
- дати клієнту інструкцію натиснути `/start`;
- пройти onboarding і створити першу тестову фактуру;
- перевірити логи, ізоляцію і rollback/deactivation procedure.

Передумова:
- P0 owner-run baseline закритий;
- P1 manual onboarding v1 готовий;
- якщо dry run іде через shared backend з кількома ботами, P2 multi-bot routing має бути готовий.

### P3 - later improvements

Після першого зовнішнього dry run:
- self-service setup page;
- vault/KMS-подібне hardening секретів за потреби;
- admin/analytics tooling;
- optional Google Drive інтеграція для storage документів;
- Android/app layer.

## 5) Найближчий порядок виконання

1. Закрити P0 owner-run checklist на сервері.
2. Перевірити backup/restore і зафіксувати поточну DB/storage migration discipline.
3. Описати tenant contract до будь-якого multi-bot runtime.
4. Підготувати manual onboarding v1.
5. Реалізувати multi-bot routing тільки після tenant contract.
6. Провести first external client dry run.
7. Після dry run приймати рішення про `uv`, CI/server hardening і self-service/admin tooling.

## 6) Definition of first success milestone

Перший зовнішній milestone вважається досягнутим, коли одночасно виконано:
- є зовнішній тест-клієнт з власним bot token і конфігурацією;
- tenant routing спрямовує updates у правильний tenant context;
- клієнт натискає `/start` у своєму боті;
- onboarding проходить у межах очікуваного flow;
- створюється перша тестова фактура;
- підтверджено відсутність cross-tenant data leakage;
- є запис у `PROJECT_LOG.md` з результатами dry run.

## 7) Non-goals раннього rollout

- Не будувати повний self-service кабінет до перевіреного ручного onboarding.
- Не заявляти fully automated onboarding до появи реального процесу.
- Не переводити кожного клієнта в окремий контейнер як дефолт без окремого рішення.
- Не додавати multi-tenant SaaS логіку без оновлення ТЗ або явного запису в `PROJECT_LOG.md`.
- Не робити DB migration без backup/restore плану.
- Не змішувати dependency tooling migration (`uv`) зі schema/storage migration.

## 8) Пов'язані документи

- `docs/TZ_FakturaBot.md` - продуктове ТЗ і межі MVP.
- `PROJECT_LOG.md` - журнал рішень і виконаних змін.
- `README.md` - поточна навігація по проєкту і статус реалізації.
- `docs/local-only/FakturaBot_Server_Agent_Context.md` - приватний server runbook для реальних server дій.
- `docs/Info_Help_Guidance_Layer.md` - окремий docs-first spec для `info_help` guidance layer.

