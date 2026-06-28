# Google Drive Invoice Archive After Due Date Spec

Status: Phase 1 runtime slice plus future Phase 2 integration boundary.

## Current Phase 1 Runtime

Phase 1 implements overdue outgoing-invoice follow-up in Telegram with a local
Google Drive archive stub only.

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

`invoice_due_date_reminders`: `partial`

Reason: overdue detection, automatic in-process Telegram notification,
decisions, and persisted state exist. The scheduler runs inside the bot
process once per day by default, not as a separate external worker/cron
deployment.

`google_drive_invoice_archive_after_due_date`: `unsupported`

Reason: Phase 1 has only a local stub. It records and explains that no Google
Drive upload happened. It must not be described as Drive archive support.

Existing `google_drive_invoice_storage` remains `unsupported`.

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

`mark_existing_invoice_paid` reuses the same local follow-up state effect as the reminder card's "mark as paid" decision after supplier-scoped invoice lookup and explicit confirmation. It is a manual top-level entry point, not a bank integration. It may record the local archive stub after marking paid, but it must not claim that a real Google Drive upload/archive happened.

## Future Phase 2 Requirements

Before real Google Drive upload can be called supported:

- real OAuth token exchange and production token crypto must be enabled;
- Drive upload adapter must exist;
- folder policy and tenant/workspace scope must be defined;
- upload failure must keep local invoice PDFs valid;
- retry and observability behavior must be implemented;
- Product Truth, InfoHelp, tests, evals, `PROJECT_LOG.md`, and this spec must
  be updated;
- no local PDF deletion may be added without a separate migration/retention
  decision.
