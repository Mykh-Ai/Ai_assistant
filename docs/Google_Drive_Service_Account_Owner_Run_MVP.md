# Google Drive Service Account Owner-Run MVP

Status: partial runtime integration, owner-run only.

## Scope

This MVP is not per-client Google OAuth and not SaaS Drive sync. One owner-managed
Google service account uploads files from the bot runtime into one Google Drive
root folder that the owner manually shares with the service-account email.

Implemented runtime paths:

- confirmed receipts (`receipt`) upload to `FakturaBot/<year>/blocky/<year-month>/`;
- confirmed incoming invoices (`incoming_invoice`) upload to `FakturaBot/<year>/prijate_faktury/<year-month>/`;
- outgoing invoice PDFs (`invoice_pdf`) are enqueued only after a control event such as marking the invoice paid, then upload to `FakturaBot/<year>/faktury/<year-month>/`;
- invoice PDFs remain local in `storage/invoices/...` in this MVP;
- receipt and incoming-invoice originals may be deleted only after upload success and DB state has been updated to `uploaded`; metadata JSON remains local.

Not implemented:

- per-user OAuth connection and per-client Drive ownership;
- SaaS multi-client Drive provisioning;
- deleting local outgoing invoice PDFs;
- bank-confirmed settlement or bank matching;
- real manual smoke without service-account credentials.

## Environment

Use empty placeholders in committed examples only:

```env
GOOGLE_DRIVE_ENABLED=0
GOOGLE_DRIVE_MODE=service_account
GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_PATH=/bot/secrets/fakturabot-google-drive-service-account.json
GOOGLE_DRIVE_ROOT_FOLDER_ID=
GOOGLE_DRIVE_ROOT_FOLDER_NAME=FakturaBot
GOOGLE_DRIVE_DELETE_LOCAL_RECEIPT_ORIGINAL_AFTER_UPLOAD=1
GOOGLE_DRIVE_DELETE_LOCAL_INCOMING_INVOICE_ORIGINAL_AFTER_UPLOAD=1
GOOGLE_DRIVE_DELETE_LOCAL_INVOICE_PDF_AFTER_UPLOAD=0
GOOGLE_DRIVE_ARCHIVE_WORKER_INTERVAL_SECONDS=60
GOOGLE_DRIVE_ARCHIVE_WORKER_BATCH_SIZE=5
```

Never commit the service-account JSON file. Keep it outside the repository. In
the production Docker setup, store it on the VPS under `/bot/secrets/` and use
the same absolute path inside the container; `docker-compose.prod.yml` mounts
that directory read-only.

## Owner Setup

1. Create a Google Cloud service account and download its JSON key outside Git.
2. Create or choose the owner Drive folder, for example `FakturaBot`.
3. Share that Drive folder with the service-account email as editor.
4. Copy the folder id into `GOOGLE_DRIVE_ROOT_FOLDER_ID`.
5. Set `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_PATH` to the container-visible JSON
   path, for example `/bot/secrets/fakturabot-google-drive-service-account.json`.
6. Set `GOOGLE_DRIVE_ENABLED=1` and restart the bot runtime.

The bot creates/finds the year/type/month folders under the shared root folder.
If credentials, folder id, dependency, or access is missing, jobs stay retryable
or fail boundedly; local files are not deleted on failed upload.

## Runtime Owner

- `bot/services/google_drive_service_account_client.py` isolates Google API calls.
- `bot/services/archive_worker.py` owns job claiming, retry/failure transitions,
  state updates, and post-upload retention.
- `bot/services/google_drive_archive_scheduler.py` starts the in-process worker
  only when `GOOGLE_DRIVE_ENABLED=1`.
- `bot/services/invoice_drive_archive_service.py` enqueues invoice PDFs after
  mark-paid/control events or falls back to the honest local stub when Drive is
  disabled.

## Test Evidence

Focused no-network coverage lives in `tests/test_google_drive_service_account_archive.py`,
`tests/test_archive_worker.py`, `tests/test_product_truth.py`, and
`tests/test_info_help.py`. Unit tests use fake Drive services and must not call
real Google APIs.
