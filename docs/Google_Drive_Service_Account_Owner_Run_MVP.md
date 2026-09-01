# Google Drive Owner OAuth MVP

Status: partial runtime integration, owner-run only.

## Scope

This MVP is not per-client OAuth and not SaaS Drive sync. One owner Google
account authorizes the bot once through a manual/local OAuth bootstrap. The bot
stores an encrypted refresh token and uploads archive files into one configured
personal My Drive root folder. Uploads consume the owner Google account quota.

Implemented runtime paths:

- confirmed receipts (`receipt`) upload to `FakturaBot/<workspace.drive_folder_name>/<year>/blocky/<year-month>/`;
- confirmed incoming invoices (`incoming_invoice`) upload to `FakturaBot/<workspace.drive_folder_name>/<year>/prijate_faktury/<year-month>/`;
- workspace-scoped outgoing invoice PDFs (`invoice_pdf`) are enqueued only after a control event such as marking the invoice paid, then upload to `FakturaBot/<workspace.drive_folder_name>/<year>/faktury/<year-month>/`; legacy null-workspace invoice jobs retain their compatibility target;
- before recording an outgoing invoice upload result, workspace-scoped jobs
  must match the invoice's persisted actor and immutable `workspace_id` and
  must update follow-up state through `WorkspaceInvoiceFollowupService`; only
  legacy invoices with a null persisted `workspace_id` use the legacy service;
- invoice PDFs remain local in `storage/invoices/...` in this MVP;
- receipt and incoming-invoice originals may be deleted only after upload success and DB state has been updated to `uploaded`; metadata JSON remains local.

Not implemented:

- per-client Drive OAuth or SaaS multi-client Drive provisioning;
- domain/web callback production UX for Drive archive setup;
- deleting local outgoing invoice PDFs;
- bank-confirmed settlement or bank matching;
- service-account personal My Drive archive. Service-account mode is unsupported for personal My Drive unless a future Google Workspace/Shared Drive setup is explicitly configured.

## Environment

Use empty placeholders in committed examples only:

```env
GOOGLE_DRIVE_ENABLED=0
GOOGLE_DRIVE_MODE=owner_oauth
GOOGLE_OAUTH_CLIENT_ID=
GOOGLE_OAUTH_CLIENT_SECRET=
GOOGLE_TOKEN_CRYPTO_SECRET=
GOOGLE_DRIVE_ROOT_FOLDER_ID=
GOOGLE_DRIVE_ROOT_FOLDER_NAME=FakturaBot
GOOGLE_DRIVE_OWNER_WORKSPACE_ID=owner
GOOGLE_DRIVE_DELETE_LOCAL_RECEIPT_ORIGINAL_AFTER_UPLOAD=1
GOOGLE_DRIVE_DELETE_LOCAL_INCOMING_INVOICE_ORIGINAL_AFTER_UPLOAD=1
GOOGLE_DRIVE_DELETE_LOCAL_INVOICE_PDF_AFTER_UPLOAD=0
GOOGLE_DRIVE_ARCHIVE_WORKER_INTERVAL_SECONDS=60
GOOGLE_DRIVE_ARCHIVE_WORKER_BATCH_SIZE=5
```

Never commit OAuth client secrets, token crypto secrets, authorization codes,
access tokens, refresh tokens, or stored encrypted token blobs in logs, docs,
Telegram replies, or Git.

## Owner Setup

1. Create or choose the owner personal My Drive folder, for example `FakturaBot`.
2. Copy the folder id into `GOOGLE_DRIVE_ROOT_FOLDER_ID`.
3. Configure `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, and `GOOGLE_TOKEN_CRYPTO_SECRET` outside Git.
4. Run `python -m bot.google_drive_owner_oauth_bootstrap authorize --telegram-id <admin_telegram_id>`.
5. Open the printed authorization URL as the owner Google account and copy the returned authorization code.
6. Run `python -m bot.google_drive_owner_oauth_bootstrap exchange --state-token <state> --code <code> --root-folder-id <folder_id>`.
7. Set `GOOGLE_DRIVE_ENABLED=1`, `GOOGLE_DRIVE_MODE=owner_oauth`, and restart the bot runtime.
8. Run a manual smoke upload only with real owner credentials.

`/google_drive_status` and `/google_drive_disconnect` resolve this shared owner
connection through `GOOGLE_DRIVE_OWNER_WORKSPACE_ID`; they do not derive a
separate connection key from the administrator's Telegram id. The interactive
`/google_drive_connect` command requires a configured production callback
redirect. Where that callback UX is not configured, use the manual owner
bootstrap above.

The bot creates/finds the year/type/month folders under the configured root
folder. If OAuth credentials, encrypted token, folder id, dependency, quota, or
access is missing, jobs stay retryable/failed boundedly; local files are not
deleted on failed upload.

## Runtime Owner

- `bot/google_drive_owner_oauth_bootstrap.py` owns manual owner authorization and encrypted token storage.
- `bot/services/google_drive_owner_oauth_client.py` isolates owner OAuth Google API calls.
- `bot/services/google_drive_connection_service.py` stores the encrypted owner token bundle.
- `bot/services/archive_worker.py` owns job claiming, retry/failure transitions, state updates, and post-upload retention.
- `bot/services/google_drive_archive_scheduler.py` starts the in-process worker only when `GOOGLE_DRIVE_ENABLED=1`.
- `bot/services/invoice_drive_archive_service.py` enqueues invoice PDFs after mark-paid/control events or falls back to the honest local stub when Drive is disabled.

## Test Evidence

Focused no-network coverage lives in
`tests/test_google_drive_service_account_archive.py`,
`tests/test_archive_worker.py`,
`tests/test_workspace_invoice_followup_service.py`, `tests/test_product_truth.py`,
and `tests/test_info_help.py`. Unit tests use fake Drive services and must not
call real Google APIs.
