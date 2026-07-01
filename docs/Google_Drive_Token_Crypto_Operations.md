# Google Drive Token Crypto Operations

Status: production operations policy for current owner OAuth token storage.

This document covers `GOOGLE_TOKEN_CRYPTO_SECRET`, the local secret used by
the token crypto provider foundation. It does not enable Google OAuth, Google
API calls, Drive uploads, or cleanup by itself, but the current owner OAuth
runtime depends on this secret to decrypt stored refresh-token bundles.

## Purpose

Google refresh token bundles must be stored encrypted before any real Google
Drive token exchange is enabled. `GOOGLE_TOKEN_CRYPTO_SECRET` is the local
Fernet-compatible secret used to encrypt and decrypt those token bundles.

Important boundaries:

- `GOOGLE_TOKEN_CRYPTO_SECRET` is a production secret.
- It is not a Google access token, refresh token, OAuth code, or client secret.
- It must not be committed to git.
- It must not be logged, printed into application logs, sent to users, pasted
  into tickets, or shared in chat.
- Only placeholders belong in `.env.example` and `.env.server.example`.

## If The Secret Is Lost

If `GOOGLE_TOKEN_CRYPTO_SECRET` is lost, existing encrypted Google refresh
token bundles cannot be decrypted.

Operational impact:

- Google Drive connections become unusable until the affected workspace
  reconnects Google Drive.
- Files already stored on Google Drive are not deleted by this failure.
- Pending archive jobs may remain blocked until reconnection, according to the
  worker policy available at that time.
- A SQLite/database backup alone is not enough to recover Google Drive
  connections without the matching secret.

## Common Loss Scenarios

The secret can be lost or invalidated by:

- deleting or replacing the production `.env` / server environment value;
- migrating to a new VPS/container/host without copying the secret;
- restoring only DB/storage backups without the secret backup;
- clearing Docker, hosting, or CI/CD environment variables;
- accidentally regenerating the secret in production;
- attempting key rotation without a migration plan;
- missing password manager or secret-vault backups.

## Storage Policy

Store `GOOGLE_TOKEN_CRYPTO_SECRET` only in approved production secret storage:

- production environment variables;
- a deployment secret manager;
- a restricted password manager or operations vault.

Access rules:

- restrict access to server operators/admins who need deployment recovery
  responsibility;
- never store the real value in git, docs, screenshots, chat, issue trackers,
  or support tickets;
- never include the value in application logs or exception messages;
- keep `.env.example` and `.env.server.example` as placeholders only.

## Backup Policy

Production backup must include enough material to recover the Google Drive
connection state:

- SQLite database;
- required `storage/` metadata and files;
- `GOOGLE_TOKEN_CRYPTO_SECRET`, backed up separately and securely;
- Google OAuth client configuration if used by the deployment;
- deployment environment variables needed to recreate the runtime.

Critical rule:

```text
A database backup without GOOGLE_TOKEN_CRYPTO_SECRET cannot recover encrypted
Google Drive refresh token bundles.
```

The secret backup should be stored separately from the database backup, but it
must be recoverable by the same authorized operations process.

## Rotation Policy

Runtime key rotation is not implemented yet.

Do not change `GOOGLE_TOKEN_CRYPTO_SECRET` in production after real token
storage is enabled unless there is an approved migration plan.

Future rotation must include at least:

1. Load old key.
2. Decrypt each stored token bundle.
3. Encrypt each bundle with the new key.
4. Update `token_key_id` and `token_version`.
5. Verify decrypt/read behavior with the new key.
6. Keep rollback material until verification is complete.

Changing the secret without migration makes existing encrypted token bundles
undecryptable.

## Recovery If The Secret Is Lost

If the secret is lost:

1. Do not try random replacement secrets.
2. Do not edit encrypted token ciphertext manually.
3. If runtime supports it, mark affected Google Drive connections as
   `needs_reauth` with a bounded error code.
4. Ask the workspace admin/user to reconnect Google Drive.
5. Let pending jobs wait or retry after reconnection according to the worker
   policy.
6. Do not delete existing Google Drive files as part of this recovery.

Existing files already uploaded to Google Drive remain on Google Drive. The
local system has simply lost the ability to refresh OAuth access for the
affected encrypted connection records.

## Generation Guidance

`FernetTokenCryptoProvider` expects a Fernet-compatible key.

Generate the value outside git on a trusted admin machine or server shell:

```powershell
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Then store the generated value in the production secret store or deployment
environment as:

```text
GOOGLE_TOKEN_CRYPTO_SECRET=<generated-fernet-key>
```

Do not commit the generated value. Do not paste it into logs, chats, tickets,
or documentation.

## Checklist Before Enabling Owner OAuth On A Deployment

Before enabling real Google OAuth token exchange:

- `GOOGLE_TOKEN_CRYPTO_SECRET` is configured in production.
- The secret backup is confirmed.
- The deployment `.env` or secret-store value is not tracked by git.
- Callback runtime fail-closed behavior is understood.
- Real token exchanger is implemented and tested.
- Token persistence uses production crypto, not deterministic fake crypto.
- Tests prove no plaintext access/refresh/id tokens appear in DB, repr,
  logs, or user-facing output.
- Product Truth/InfoHelp must remain `partial` and setup-gated unless the deployment
  has owner OAuth credentials, token crypto, encrypted refresh token, root folder id,
  archive worker, and smoke evidence.

## Non-Goals

This document does not implement:

- real Google token exchange;
- Google API calls;
- Drive upload or folder creation;
- callback runtime enablement;
- key rotation;
- cleanup or delete behavior;
- Product Truth/InfoHelp status upgrade.
