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

### Invoice Analytics

`invoice_analytics` is implemented as a partial read-only pilot for natural
language questions over saved outgoing invoices for the current authorized
supplier.

It can answer questions about:
- invoice counts and totals;
- simple calendar-year summaries through an internal deterministic fast path;
- periods and period comparisons;
- customers, months, currencies, and bounded matching lists;
- bot payment states such as pending payment, paid, and overdue.

Payment-state analytics use Python-normalized `payment_status_canonical`, not
raw invoice lifecycle `status`. The final business answer shown to the user is
Slovak by default. Analytics is read-only: it must not create, edit, delete,
send, archive, mark paid, generate PDFs, upload to Google Drive, or write any
invoice/accounting data. Receipt, expense, and incoming-invoice analytics are handled only by the separate partial `accounting_document_analytics` runtime; bank, cashflow, VAT, tax, and full accounting analytics remain unsupported and must not be answered from outgoing invoice data.

### Accounting Document Analytics

`accounting_document_analytics` is implemented as a partial read-only pilot for
natural-language questions over confirmed receipts/bloceky and incoming
invoices/prijate faktury in the current accounting workspace.

It can answer bounded questions about counts, sums, vendors, categories,
months/periods, document type, comparisons, limited lists, averages, and top
rankings from confirmed metadata only. Old metadata without category remains
readable as `uncategorized` / `Bez kategorie`.

It does not analyze outgoing invoices, bank movements, cashflow, VAT/tax
reports, accounting export, or full accounting conclusions. It does not create,
edit, delete, or persist documents, categories, files, registry entries, DB
rows, or any side effects.

### Accounting Documents / Bločky

```text
/add_blocek
/dodat_blocek
  upload photo/PDF
  LMM classification/extraction
  duplicate warning if matched
  category preview
    save with category
    change document category
    change line-item category when line items exist
    create workspace category only after typed label + confirmation
    save without category / save as review
    cancel

/blocek
/blocky
  show recent confirmed accounting documents
```

Supported document types:
- receipt / bloček;
- incoming invoice / prijatá faktúra.

Accounting documents are external source documents. They are not edited like generated invoices. Category handling is partial and controlled: Python provides allowed categories, LMM may suggest only bounded candidate category ids or `unknown_review`, the user confirms in preview, and final save stores category ids with label snapshots. Workspace categories are created only after explicit typed-label confirmation. If recognition is wrong, the correction path is better photo/PDF re-upload; arbitrary manual accounting-document editing is not implemented.

Current category metadata by itself is not analytics, tax/accounting judgement, bank matching, VAT reporting, accounting export, or a category totals report. Receipt/incoming-invoice analytics is available only through the separate partial read-only `accounting_document_analytics` runtime over confirmed metadata.

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

Google Drive owner OAuth archive:
- partial runtime integration for one owner Google account, not per-client OAuth and not SaaS Drive sync;
- enabled only with `GOOGLE_DRIVE_ENABLED=1` and `GOOGLE_DRIVE_MODE=owner_oauth`;
- requires `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_TOKEN_CRYPTO_SECRET`, `GOOGLE_DRIVE_ROOT_FOLDER_ID`, and a stored encrypted owner refresh token;
- one-time owner bootstrap command: `python -m bot.google_drive_owner_oauth_bootstrap authorize --telegram-id <admin_telegram_id>`, then `python -m bot.google_drive_owner_oauth_bootstrap exchange --state-token <state> --code <code> --root-folder-id <folder_id>`;
- uploads consume the owner Google account quota in personal My Drive;
- confirmed receipts upload under `FakturaBot/<year>/blocky/<year-month>/`;
- confirmed incoming invoices upload under `FakturaBot/<year>/prijate_faktury/<year-month>/`;
- outgoing invoice PDFs are enqueued after mark-paid/control events under `FakturaBot/<year>/faktury/<year-month>/`;
- local outgoing invoice PDFs are not deleted in this MVP;
- receipt/incoming originals may be deleted only after upload success and DB state `uploaded`; metadata JSON stays local;
- service-account mode is unsupported for personal My Drive unless a future Google Workspace/Shared Drive setup is explicitly configured;
- setup details are in `docs/Google_Drive_Service_Account_Owner_Run_MVP.md` (current owner OAuth MVP doc), `docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md`, and `docs/Google_Drive_Token_Crypto_Operations.md`;
- live smoke on 2026-07-01 confirmed invoice `20260006` mark-paid -> `invoice_pdf` archive job -> Google Drive `uploaded` state.

Google Drive OAuth callback skeleton:
- separate process, not `bot/main.py` polling;
- production token exchanger foundation exists;
- owner archive uses the manual/local bootstrap command today;
- domain/web callback UX remains a later production improvement;
- command: `python -m bot.google_drive_oauth_callback_app`;
- `GOOGLE_OAUTH_CLIENT_SECRET` is a placeholder for future token exchange; do not commit a real value.
- `GOOGLE_TOKEN_CRYPTO_SECRET` is a placeholder for future encrypted token storage; do not commit a real value.
- Token crypto operations are documented in `docs/Google_Drive_Token_Crypto_Operations.md`.

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
- full/per-client Google Drive sync; owner OAuth Drive archive is partial, single-owner, and requires setup;
- bank matching;
- bank/cashflow analytics;
- tax/VAT advice;
- full accounting analytics;
- broad OCR pipeline for arbitrary scanned documents;
- full OfficeFlow workspace runtime;
- real SMTP/email sending flow for invoices;
- complex role system;
- setup/billing UI.
