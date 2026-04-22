# FakturaBot Server Rollout Roadmap

## 1) Мета документа

Цей документ фіксує **практичний план розгортання** FakturaBot від поточного стану
`локальний репозиторій + GitHub` до першого зовнішнього тест-клієнта, який натискає `/start` у server-hosted інстансі.

Документ описує **цільовий напрямок та етапи впровадження**, а не твердження, що вся інфраструктура вже завершена.

## 2) Стартова точка (поточний стан)

На момент цього roadmap стартова точка:
- код і документація в локальному репозиторії;
- репозиторій у GitHub;
- є MVP runtime-функціональність FakturaBot;
- повний клієнт-ready server/onboarding workflow як стабільний продуктний процес ще формується.

## 3) Цільова near-term deployment концепція

Near-term напрямок розгортання:
- **один shared backend service**;
- **один codebase**;
- **одна спільна інфраструктурна база**;
- **tenant isolation** на рівні клієнта/бота/конфігурації/даних;
- per-client ізоляція:
  - окремий Telegram bot token,
  - окремий OpenAI API key,
  - окремий supplier/business config,
  - окремі дані та контексти сесій;
- Telegram-first rollout;
- setup page/self-service onboarding — **пізніше** (не required для першого серверного milestone);
- Android/UI шар — також пізніше.

## 4) Явне архітектурне рішення для rollout

На найближчий production-like rollout рекомендовано:
- **shared backend + tenant isolation** як основний шлях.

Що НЕ є основною стратегією першого production-like кроку:
- multi-Docker-per-client як дефолтна модель для кожного нового клієнта.

Примітка:
- пер-клієнтна контейнеризація може лишатися опцією пізнішого етапу (специфічна ізоляція/масштаб),
  але не як базова рекомендація для першого server rollout milestone.

## 5) Staged roadmap до першого клієнтського `/start`

### Stage 1 — Server foundation

Практичні кроки:
- вибрати VPS/сервер;
- підготувати базові директорії (код, storage, backups, logs);
- підготувати Docker/deploy baseline;
- налаштувати clone/pull/update процес з GitHub;
- підготувати production env/secrets policy (без hardcode у репозиторії).

Результат етапу:
- сервер готовий прийняти керований deploy і перезапуски.

### Stage 2 — First self-hosted production-like run (owner)

Практичні кроки:
- розгорнути один робочий інстанс для автора/внутрішнього тесту;
- перевірити `/start`;
- пройти базовий invoice flow end-to-end;
- перевірити persistence, логи, restart-поведінку.

Результат етапу:
- стабільний owner-run baseline, придатний для контрольованого зовнішнього dry run.

### Stage 3 — Tenant model definition

Практичні кроки:
- зафіксувати tenant identifier модель;
- визначити ізоляцію per-client config;
- визначити ізоляцію per-client data storage;
- визначити ізоляцію per-client FSM/session context;
- визначити policy ізоляції per-client secrets.

Результат етапу:
- формалізований tenant contract без cross-tenant змішування.

### Stage 4 — Multi-bot routing

Практичні кроки:
- мапити вхідні Telegram updates до правильного tenant;
- завантажувати коректні tenant config/secrets/data;
- додати технічні guardrails проти cross-tenant leakage;
- додати операційні перевірки, що маршрутизація детермінована.

Результат етапу:
- один backend коректно маршрутизує декілька ботів/тенантів.

### Stage 5 — Manual onboarding v1

Практичні кроки:
- зробити admin/manual onboarding runbook для перших клієнтів;
- створювати tenant config вручну;
- безпечно вносити/зберігати bot token та API ключі;
- створювати tenant-isolated storage;
- активувати конкретний tenant bot і виконувати smoke-check.

Результат етапу:
- керований ручний onboarding першого зовнішнього тест-клієнта без self-service UI.

### Stage 6 — First external client dry run

Практичні кроки:
- зареєструвати клієнтський Telegram bot/token;
- застосувати tenant config;
- дати клієнту інструкцію натиснути `/start`;
- пройти перший onboarding у боті;
- створити першу тестову фактуру;
- перевірити логи, ізоляцію і відсутність cross-tenant витоків.

Результат етапу:
- підтверджений перший зовнішній production-like сценарій «клієнт натиснув `/start` і пройшов базовий flow».

### Stage 7 — Later improvements

Після першого успішного зовнішнього dry run:
- self-service setup page;
- hardening секретів (vault/KMS-подібні практики за потреби);
- admin/analytics tooling;
- optional Google Drive інтеграція для storage документів;
- пізніше — Android/app шар.

## 6) Принципи зберігання даних і секретів

- Bot tokens / API keys не повинні передаватися через звичайний chat-flow.
- Секрети мають зберігатися на backend-стороні в керованому secure storage підході.
- Google Drive може бути опційним пізнім шаром для storage документів,
  але не є primary secret manager.
- Setup page — це future convenience layer, а не передумова першого server milestone.

## 7) Ризики і non-goals на ранньому rollout етапі

Основні ризики:
- помилки tenant isolation;
- витік секретів;
- помилки multi-bot routing;
- передчасне ускладнення через per-client containerization як дефолт.

Non-goals раннього етапу:
- не будувати одразу повний self-service кабінет;
- не заявляти fully automated onboarding до появи реального, перевіреного процесу;
- не ускладнювати інфраструктуру раніше, ніж це потрібно для першого зовнішнього клієнта.

## 8) Definition of first success milestone

Перший milestone вважається досягнутим, коли одночасно виконано:
- є перший зовнішній тест-клієнт з власним bot token і конфігурацією;
- tenant routing спрямовує апдейти в правильний tenant context;
- клієнт натискає `/start` у своєму боті;
- onboarding проходить у межах очікуваного flow;
- створюється перша тестова фактура;
- підтверджено відсутність cross-tenant data leakage.

## 9) Зв’язок з іншими документами

- `docs/TZ_FakturaBot.md` — продуктове ТЗ і межі MVP.
- `docs/Info_Help_Guidance_Layer.md` — окремий docs-first spec для `info_help` guidance layer.

Цей roadmap не дублює `info_help` spec, а фокусується на server rollout/onboarding інфраструктурному шляху.
