# Ai_assistant

Практичний репозиторій для розробки Telegram-ботів під задачі малого бізнесу.

Основний runtime-кейс зараз: **FakturaBot / OfficeFlow**.

FakturaBot створює словацькі outgoing invoices з голосу/тексту, веде локальні контакти, профіль постачальника, service aliases, базовий облік отриманих bločky/prijaté faktúry через Document Intake, і працює в контрольованому multi-user dry run з admin approval.

## Sources Of Truth

Для продуктових і runtime-рішень використовувати такий порядок:

1. `docs/TZ_FakturaBot.md`
2. `PROJECT_LOG.md`
3. поточний код
4. `CHANGELOG.md`

README є навігаційним оглядом. Якщо README конфліктує з ТЗ, журналом або кодом, пріоритет мають ТЗ/журнал/код.

## Current Runtime Map

Стан: runtime baseline 2026-05-06, with product/doctrine documentation updates through `PROJECT_LOG.md` sessions 077-085 on 2026-05-16/17.

### Access And Start

```text
/start
  unknown user
    create/refresh pending access request
    no STT / LLM / LMM / business data
  approved user
    clears active FSM state
    setup/status router
      missing supplier profile -> /moj_profil
      profile exists, no service alias -> /sluzbu
      profile + service, no contacts -> /contact
      ready state -> main operational menu

/menu
  full user-facing capabilities list
  includes create/show/edit/delete invoice wording
  does not expose internal canonical tokens as slash commands

Admin commands
  /access_requests
  /approve
  /reject
  /block
  /users
```

Admin/access commands are deterministic Python commands. They are not LLM-routed.

Global state control:

```text
/cancel
  clear active FSM state
  clean temporary intake staging when applicable
  exit persisted invoice edit mode without deleting the stored invoice

Text/voice cancel aliases
  zrušiť
  скасувати
  відмінити / відминити
  отменить
  почни з початку
```

### Supplier Profile

```text
/moj_profil
  show supplier/company/billing profile
  if profile is missing -> starts supplier onboarding

/upravit_profil
  choose field
    name
    ICO
    DIC
    IC DPH
    address
    IBAN
    SWIFT/BIC
    email
    default due days
  enter new value
  save/cancel confirmation
  after save, return the same staged/main navigation as /start
```

Voice support:
- top-level profile view/edit intent: yes;
- field choice inside `/upravit_profil`: yes;
- exact new field value: text-only.

### Services

```text
/sluzbu
  short service/item alias
  full invoice/PDF display title

legacy aliases
  /service
  /alias
```

Voice support:
- top-level add-service intent: yes;
- exact alias/display-name values: text-only.

### Contacts

```text
/contact
/contact_add
  manual contact flow
    company name
    ICO
    DIC
    IC DPH
    address
    email
    contact person
    save/cancel

AI-assisted contact intake
  text or document/contact-source input
  AI drafts candidate
  Python validates
  missing fields
  save/cancel
```

Voice support:
- top-level add-contact intent: yes;
- contact save/cancel decisions: yes;
- missing business-data values: text-only.

No automatic contact creation from receipts, incoming invoices, idle photos, or arbitrary attachments.

### Invoices

```text
/invoice
voice/text create_invoice
  natural-language invoice request
  bounded draft extraction
  missing slot clarification
    service/customer/date/quantity/price where recoverable
  preview
    approve
      create invoice row
      assign invoice number
      generate PDF
    edit
      invoice-level edit
        invoice number
        dates
          issue date
          delivery date
          due date
        customer/contact
          planned/partial, not a broad automatic contact rewrite
      item-level edit
        choose item
        replace service
        replace main description
        add item details
        clear item details
        quantity
        unit price
        total amount
    cancel
      clear draft without DB invoice/PDF side effects

post-PDF / post-edit decision
  approve
  edit
  cancel

existing invoice management
  show_existing_invoice by invoice number/reference
    show summary/PDF
    clear state
    no edit mode
  edit_existing_invoice by invoice number/reference
    same bounded edit subflow
  delete_existing_invoice by invoice number/reference
    yes/no confirmation
```

Important distinction:
- `show_existing_invoice` = read-only view of an already created invoice;
- `edit_invoice` = in-action/FSM draft/current invoice editing semantics;
- `edit_existing_invoice` = persisted invoice editing by number/reference.

Voice support:
- top-level create invoice: yes;
- `/invoice` waiting input: yes;
- preview/post-PDF decisions: yes;
- edit action/scope/item/field choices: yes;
- exact invoice number value: text-only;
- exact item numeric values/prices/quantities: text-only;
- final item description: text-only.

### Accounting Documents / Bločky

```text
/add_blocek
/dodat_blocek
  upload photo/PDF
  LMM classification/extraction
  duplicate warning if matched
  preview
    save
    edit unavailable in current runtime
    cancel

/blocek
/blocky
  show recent confirmed accounting documents
```

Supported document types:
- receipt / bloček;
- incoming invoice / prijatá faktúra.

Accounting documents are external source documents. They are not edited like generated invoices. If recognition is wrong, the correction path is better photo/PDF re-upload; arbitrary manual accounting-document editing is not implemented.

Voice support:
- top-level show recent documents: yes;
- top-level add/upload receipt intent: yes, starts upload waiting only;
- upload itself: photo/PDF only;
- duplicate/preview decisions: yes.

### OfficeFlow Idle Attachment Router

```text
idle photo/PDF
  authorization first
  LMM document type classification
    receipt
    incoming_invoice
    contract
    contact_source
    unknown
  Python proposes bounded next step
  user confirms route before save/create side effects
```

Active FSM state wins over idle attachment routing.

Standalone contract save/archive is not implemented.

### User Database Deletion

```text
/vymazat_databazu
semantic text/voice delete_user_database intent
  warning
  exact typed confirmation only: vymazať databázu
  scoped business DB/file deletion
  authorized_users.status = deleted_database
  access_requests.status = deleted_database
  future /start requires new admin approval
```

Voice may start the warning flow. Voice must never pass final deletion confirmation.

## Voice Boundary

Voice is supported for:
- top-level canonical actions with runtime routes;
- bounded in-FSM action/field/item/route choices;
- confirmation-like decisions through the shared DecisionResolver;
- natural-language invoice request text.

Voice is intentionally not used for precision-sensitive exact values:
- IBAN;
- ICO / DIC / IC DPH;
- email;
- invoice number values;
- item quantities, unit prices, total amounts;
- final item descriptions;
- service alias names/display titles;
- exact destructive confirmations;
- upload steps that require photo/PDF.

## AI Architecture Principle

AI is not an autonomous executor.

```text
Python orchestrates
AI extracts / drafts / canonicalizes inside bounded contracts
Python validates
User confirms
Python saves or performs side effects
```

Authorization and tenant scoping happen before STT, LLM, LMM, temp files, DB writes, or storage writes.

## Run

1. Create `.env` from `.env.example`.
2. Fill at least:
   - `BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `OPENAI_STT_MODEL` or leave default
   - `OPENAI_LLM_MODEL` or leave default
3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Run locally:

```powershell
python -m bot.main
```

Or with Docker:

```powershell
docker compose up --build
```

Production-like owner-run baseline:
- `.env.server.example`
- `docker-compose.prod.yml`
- `scripts/update_repo.sh`
- `scripts/deploy_owner_run.sh`

Google Drive OAuth callback skeleton:
- separate process, not `bot/main.py` polling;
- fake exchanger only through injected test services in the current slice;
- production token exchanger foundation exists, but it is not wired into this
  callback runtime yet;
- no Drive upload, archive worker, or active Google Drive archive runtime;
- command: `python -m bot.google_drive_oauth_callback_app`;
- the config/runtime entrypoint intentionally fails closed until production
  token exchange and production token crypto are implemented.
- `GOOGLE_OAUTH_CLIENT_SECRET` is a placeholder for future token exchange;
  do not commit a real value.
- `GOOGLE_TOKEN_CRYPTO_SECRET` is a placeholder for future encrypted token
  storage; do not commit a real value.
- Token crypto operations are documented in
  `docs/Google_Drive_Token_Crypto_Operations.md`.

Before server-side work, read the private local runbook if present:

```text
docs/local-only/FakturaBot_Server_Agent_Context.md
```

## Tests

Use:

```powershell
python -m pytest -q
```

Do not use bare `pytest -q` as default because it may not include the project root on `sys.path`.

## Documentation

Active source-of-truth / contract docs:

- `docs/Product_Doctrine_2030.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Customization_Request_Layer.md`
- `docs/Self_Learning_Layer.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/Implementation_Agent_Checklist.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/FakturaBot_Data_Migration_Runbook.md`
- `docs/evals/README.md`

Planning / proposal docs:

- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/FakturaBot_Server_Rollout_Roadmap.md`
- `docs/FakturaBot_PDF_Layout_Spec.md`

Archive:

- `docs/archive/`
- `docs/archive/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md`
- `docs/archive/Invoice_Draft_Review_Lifecycle_Design.md`
- `docs/archive/llm/Confirmation_Decision_Audit_2026-04-14.md`
- `docs/archive/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`

Archive documents are historical context only. They are not active source of
truth and do not prove current runtime capability.

Local-only ops:

- `docs/local-only/README.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.example.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.md`

## Not Implemented

Do not treat these as current runtime:

- public automatic signup;
- full SaaS multi-tenancy;
- per-client bot/VPS/container/DB provisioning;
- standalone contract archive/save runtime;
- Google Drive sync;
- bank matching;
- broad OCR pipeline for arbitrary scanned documents;
- full OfficeFlow workspace runtime;
- real SMTP/email sending flow for invoices;
- complex role system;
- setup/billing UI.
