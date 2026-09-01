# Google Drive Invoice Archive After Due Date Spec

Status: partial owner OAuth runtime integration plus historical Phase 1 stub boundary.

## Historical Phase 1 Runtime

Phase 1 originally implemented overdue outgoing-invoice follow-up in Telegram with a local
Google Drive archive stub only. Configured owner OAuth deployments now use the
owner OAuth runtime update documented below.

Implemented:

- automatic in-process overdue check through the aiogram runtime scheduler,
  with default daily interval (`86400` seconds);
- tenant-scoped detection of saved outgoing invoices whose `invoice.due_date`
  is before today's date;
- Telegram reminder cards for the authorized invoice owner;
- three user decisions on the reminder card:
  - mark invoice as paid;
  - remind later;
  - do not remind again;
- persisted follow-up state in `invoice_followup_state`;
- local deterministic Google Drive archive stub after marking an invoice paid.

Not implemented in Phase 1:

- external cron/worker deployment;
- real Google Drive OAuth upload;
- real Drive folder creation;
- real Drive file upload;
- deleting local invoice PDFs after archive;
- email or SMS reminders;
- bank/payment matching;
- accounting export.

## Product Truth Status

Current Product Truth status after owner OAuth integration:

`invoice_due_date_reminders`: `partial`

Reason: overdue detection, automatic in-process Telegram notification,
decisions, and persisted state exist. The scheduler runs inside the bot
process once per day by default, not as a separate external worker/cron
deployment.

`google_drive_invoice_archive_after_due_date`: `partial`

Reason: configured owner OAuth deployments enqueue and upload invoice PDFs after
mark-paid/control events. Unconfigured deployments still fall back to the local
stub. It must not be described as full SaaS/per-client Drive sync.

`google_drive_invoice_storage`: `partial` owner OAuth archive integration.

## Data Model

Additive table:

```sql
invoice_followup_state (
    invoice_id INTEGER PRIMARY KEY,
    supplier_telegram_id INTEGER NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'unpaid',
    reminder_status TEXT NOT NULL DEFAULT 'active',
    remind_after TEXT,
    paid_at TEXT,
    muted_at TEXT,
    drive_archive_status TEXT NOT NULL DEFAULT 'stub_not_uploaded',
    drive_archive_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
)
```

Allowed values:

- `payment_status`: `unpaid`, `paid`;
- `reminder_status`: `active`, `snoozed`, `muted`;
- `drive_archive_status`: `stub_not_uploaded`,
  `stub_requested_after_paid`, `stub_skipped_no_drive_runtime`.

Legacy invoices without a follow-up row are treated as:

- `payment_status = unpaid`;
- `reminder_status = active`;
- `remind_after = NULL`.

No existing invoice rows, invoice numbers, PDF paths, or local PDF files are
rewritten by this phase.

## Detection Rules

An invoice is selected for a reminder when:

- `invoice.due_date < today`;
- effective `payment_status != paid`;
- effective `reminder_status != muted`;
- `remind_after IS NULL OR remind_after <= now`;
- `invoice.supplier_telegram_id` belongs to an authorized recipient;
- the invoice row still exists.

Do not notify for:

- paid invoices;
- muted invoices;
- snoozed invoices before `remind_after`;
- invoices outside the recipient supplier scope;
- blocked, deleted, or unauthorized Telegram users;
- deleted invoice rows;
- orphan follow-up rows without an invoice.

After a reminder card is sent successfully, Phase 1 records `remind_after` to
delay the next automatic notification. This prevents repeated sends on every
scheduler tick while keeping the invoice unpaid and active until the user
chooses a decision.

## Decision Effects

Mark as paid:

- sets `payment_status = paid`;
- sets `paid_at`;
- sets `reminder_status = muted`;
- clears `remind_after`;
- records Drive archive stub status
  `stub_requested_after_paid`;
- tells the user that Drive archive is not active and the invoice remains
  stored locally.

Remind later:

- sets `payment_status = unpaid`;
- sets `reminder_status = snoozed`;
- sets `remind_after` to a deterministic default of `now + 24h`;
- does not show Drive-ready copy.

Do not remind again:

- sets `payment_status = unpaid`;
- sets `reminder_status = muted`;
- sets `muted_at`;
- does not call or imply Google Drive upload.

## Google Drive Stub Contract

`GoogleDriveArchiveStubService.request_invoice_archive_stub(...)`:

- does not import or call Google APIs;
- does not require credentials;
- does not create folders;
- does not upload files;
- does not delete local PDFs;
- records only local stub state;
- returns honest user-facing copy.

Required user-facing meaning:

```text
Archivacia na Google Drive este nie je aktivna. Faktura ostava ulozena
lokalne. Po zapnuti Drive integracie ju bude mozne archivovat podla pravidiel.
```

## Manual Mark-Paid Entry Point

`mark_existing_invoice_paid` reuses the same follow-up state effect as the reminder card's "mark as paid" decision after supplier-scoped invoice lookup and explicit confirmation. It is a manual top-level entry point, not a bank integration. In configured owner OAuth deployments it may enqueue the existing local invoice PDF for archive-worker upload. In unconfigured deployments it records the local archive stub and must not claim that a real Google Drive upload happened.

## Future Full-Support Requirements

Before Google Drive archive can be called fully supported beyond the current partial owner OAuth runtime:

- per-client or account-specific OAuth setup must be designed if the product moves beyond single-owner deployments;
- folder policy and tenant/workspace scope must be defined for that wider model;
- upload failure must keep local invoice PDFs valid;
- retry and observability behavior must remain bounded;
- Product Truth, InfoHelp, tests, evals, `PROJECT_LOG.md`, and this spec must
  be updated for the wider claim;
- no local PDF deletion may be added without a separate migration/retention
  decision.

## Owner OAuth Runtime Update - 2026-06-30/2026-07-01

The current runtime is no longer stub-only for configured owner-run deployments.
`google_drive_invoice_archive_after_due_date` is now `partial` owner OAuth runtime integration.

Implemented:

- `InvoiceDriveArchiveService` falls back to the old local stub when
  `GOOGLE_DRIVE_ENABLED=0` or Drive is not configured;
- with owner OAuth Drive enabled, mark-paid/control events enqueue the existing local invoice
  PDF as an `invoice_pdf` archive job;
- the in-process Google Drive archive scheduler runs only when Drive is enabled;
- the owner OAuth provider refreshes credentials, creates/finds Drive folders, and uploads through
  injected/lazy Google API clients;
- worker failures are bounded and local invoice PDFs remain available;
- local invoice PDFs are never deleted in this MVP.

Folder policy for invoice PDFs:

```text
FakturaBot/<workspace.drive_folder_name>/<issue-year>/faktury/<issue-year>-<issue-month>/
```

The folder name comes from the persisted `WorkspaceContext` bound to the
invoice. The enqueue target is immutable and must not consult a later active
profile selection. Legacy invoices whose persisted `workspace_id` is null keep
the pre-workspace compatibility target.

Still not implemented:

- per-client OAuth Drive archive;
- deleting local invoice PDFs;
- bank matching or bank-confirmed payment;
- external cron/worker deployment separate from the bot process.

Live smoke - 2026-07-01:

- invoice `20260006` was marked paid through `mark_existing_invoice_paid`;
- `invoice_followup_state.payment_status` became `paid`;
- one `invoice_pdf` `archive_jobs` row was created and uploaded;
- `drive_archive_status` became `uploaded`;
- Google Drive returned a file id and target folder id;
- local PDF stayed present in `/bot/data/storage/invoices/...`;
- no bank matching, bank confirmation, or local PDF deletion occurred.

Operational incident during receipt backfill:

- two receipt originals/metadata had been classified under 2023 because the model misread or over-inferred the year;
- the live repair moved metadata, DB archive rows, and Drive files/folders from 2023 to 2026;
- the current receipt intake validation rejects issue years before 2026 before confirmed save;
- before 2027, replace the fixed minimum-year guard with an explicit accepted-year/window policy so January can still accept legitimate prior-year receipt backfill while impossible old years fail closed.
