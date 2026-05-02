# Ai_assistant

Практичний репозиторій для розробки Telegram-ботів під задачі малого бізнесу.

Перший основний кейс - **FakturaBot**: Telegram-бот для створення словацьких фактур з голосу, тексту та даних контрагента.

## Джерела істини

Для рішень по продукту і коду використовувати такий порядок:

1. `docs/TZ_FakturaBot.md`
2. `PROJECT_LOG.md`
3. поточний код репозиторію
4. `CHANGELOG.md`

README є навігаційним оглядом. Якщо README конфліктує з ТЗ, журналом або кодом, пріоритет має ТЗ/журнал/код.

## Поточний стан

Стан на 2026-05-02: FakturaBot має робочий інкрементальний MVP runtime для outgoing invoices і окремий перший runtime-slice для accounting Document Intake.

Реально реалізовано:

- `/start` - базова перевірка бота.
- `/supplier`, `/onboarding` - ручний onboarding постачальника з SQLite persistence; SMTP-поля зберігаються як optional.
- `/service` - локальні alias-назви послуг для нормалізації позицій у фактурі.
- `/contact`, `/contact_add` - ручне створення контрагента.
- AI-assisted contact intake з текстового PDF/contract-like документа: Python зберігає/читає документ, AI пропонує draft, Python валідовує, користувач підтверджує перед save.
- `/invoice` і вільний invoice-intent текст/voice - створення invoice draft з тексту або STT, preview, edit/confirm/cancel, persistence, PDF generation.
- PDF generation з internal Pay by Square encoder і QR-кодом.
- Sequential invoice numbering, `invoice`/`invoice_item` persistence, `pdf_path`, edit existing invoice by number reference, delete existing invoice with confirmation.
- Canonical `DecisionResolver` для confirmation-like рішень у поточних invoice/contact/onboarding/delete/accounting flows.
- `/doklad`, `/expense`, `/intake` - accounting Document Intake Phase 1 для receipt / incoming invoice photo або PDF: LMM classification/extraction, Python validation, preview, confirm/cancel, confirmed JSON-sidecar storage.
- Idle attachment router для photo/PDF без активного FSM state: класифікує attachment як receipt, incoming invoice, contract, contact source або unknown і лише пропонує наступний bounded flow.
- 5-minute timeout для temporary OfficeFlow/accounting intake staging.

Не вважати реалізованим:

- real SMTP/email send flow для фактури;
- standalone `save_contract` archive flow;
- full OfficeFlow workspace runtime;
- Google Drive sync;
- bank matching;
- OCR pipeline для довільних scanned documents;
- multi-tenant SaaS runtime;
- setup page, billing, складна рольова система.

## Run

1. Створити `.env` на основі `.env.example`.
2. Заповнити мінімум:
   - `BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `OPENAI_STT_MODEL` або залишити default
   - `OPENAI_LLM_MODEL` або залишити default
3. Встановити залежності:
   - `pip install -r requirements.txt`
4. Запустити локально:
   - `python -m bot.main`
5. Або через Docker:
   - `docker compose up --build`

Production-like owner-run baseline:

- `.env.server.example` - стартовий env template;
- `docker-compose.prod.yml` - server/container baseline;
- `scripts/update_repo.sh` - контрольоване оновлення repo на сервері;
- `scripts/deploy_owner_run.sh` - rebuild/restart owner-run instance.

Перед server-side діями агент має перевірити приватний local-only context:

- `docs/local-only/FakturaBot_Server_Agent_Context.md`

## Test

Основна команда тестів для цього repo:

```powershell
python -m pytest -q
```

Не використовувати bare `pytest -q` як default, бо він може не додати project root у `sys.path`.

## Основні команди бота

- `/start` - health/intro.
- `/supplier`, `/onboarding` - supplier profile.
- `/service` - додати коротку назву послуги та її повний invoice/PDF display title.
- `/contact`, `/contact_add` - ручний контакт або контакт із document source.
- `/invoice` - invoice draft -> preview -> edit/confirm/cancel -> PDF.
- `/doklad`, `/expense`, `/intake` - receipt/incoming invoice intake.
- Voice message - STT і routing у поточний active flow або top-level invoice/contact/service intent.

## Документація

Активні source-of-truth / contract docs:

- `docs/TZ_FakturaBot.md` - головне ТЗ.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md` - AI/orchestrator contract для FakturaBot.
- `docs/Canonical_Decision_Resolver_Contract.md` - shared confirmation/decision contract.
- `docs/llm/Canonical_Action_Registry.md` - registry top-level actions/flows.
- `docs/llm/In_Action_Response_Registry.md` - registry in-flow responses and slot decisions.
- `docs/llm/Bounded_Resolver_Prompt_Template.md` - bounded resolver payload template.
- `docs/llm/New_Action_Design_Checklist.md` - checklist для нових canonical actions.

Поточні design / planning / proposal docs:

- `docs/OfficeFlow_Architecture_Framing.md` - OfficeFlow framing; явно відділяє current runtime від future modules.
- `docs/OfficeFlow_Storage_Model_Proposal.md` - future storage/workspace proposal; не мігрує invoice PDFs.
- `docs/Document_Intake_Module_Proposal.md` - broader Document Intake proposal і current layer boundaries.
- `docs/Document_Intake_MVP_Implementation_Plan.md` - Phase 1 accounting intake plan; runtime вже частково реалізований і журнал оновлено пізнішими сесіями.
- `docs/Invoice_Draft_Review_Lifecycle_Design.md` - audit/design для preview-stage invoice lifecycle; містить implementation status.
- `docs/Info_Help_Guidance_Layer.md` - planned info/help guidance layer, docs-first.
- `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` - rollout/planning document; детальний актуальний AI contract дивитись у LLM orchestrator contract.
- `docs/FakturaBot_Server_Rollout_Roadmap.md` - server rollout/onboarding roadmap.
- `docs/FakturaBot_PDF_Layout_Spec.md` - PDF layout requirements/history.

Pay by Square / QR verification references:

- runtime source: `bot/services/pay_by_square.py` and PDF integration in `bot/services/pdf_generator.py`;
- archived rationale: `docs/archive/PayBySquare_Research_Spike.md`;
- archived manual scan checklist: `docs/archive/PayBySquare_Manual_Verification_Checklist.md`.

Archive:

- `docs/archive/` - історичні документи, які більше не є поточними джерелами істини.

Local-only ops:

- `docs/local-only/README.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.example.md` - safe public template.
- `docs/local-only/FakturaBot_Server_Agent_Context.md` - private ignored live server context, якщо існує локально.

## AI принцип

AI не є автономним виконавцем.

Правильна модель:

- Python orchestrates.
- AI extracts / drafts / canonicalizes only inside bounded contracts.
- Python validates.
- User confirms.
- Python saves or performs side effects.

Це обов'язково для invoice draft, contact extraction, accounting document intake, email/PDF сценаріїв і будь-яких реквізитів контрагентів.
