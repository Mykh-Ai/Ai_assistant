# Google Gmail Statement Collector V1 — setup runbook

Status: `requires_setup`, `requires_admin`, `requires_external_credentials`.

Last verified: 2026-07-30.

This runbook activates the bounded Gmail OAuth and bank-statement attachment
collector implemented in OfficeFlow/FakturaBot. It does not activate Google
Drive access, email sending, statement parsing, transaction matching, cashflow,
VAT, tax, or accounting conclusions.

## Runtime boundaries

- `PUBLIC_INDEXING_ENABLED=true` remains unchanged on `zevsflow-site`.
- Gmail launch is controlled separately by `GOOGLE_GMAIL_ENABLED`.
- The only allowed Google API scope is
  `https://www.googleapis.com/auth/gmail.readonly`, plus OIDC identity scopes
  `openid email profile`.
- The expected Google email and target workspace are exact configuration.
- OAuth state and OIDC nonce are random, short-lived, single-use, and persisted
  only as SHA-256 hashes.
- Refresh/access tokens are encrypted at rest with
  `GOOGLE_TOKEN_CRYPTO_SECRET`.
- The public callback forwards only `state`, `code`, or `error` to the internal
  callback. Business context never comes from browser query parameters.
- Imported files remain workspace-scoped and have `parse_status=deferred`.

## 1. Google Cloud Console

Use a dedicated Google Cloud project or an explicitly approved existing
project.

1. Enable the Gmail API.
2. Configure the OAuth consent screen and required application identity.
3. Create a Web application OAuth client.
4. Register this exact redirect URI:
   `https://zevsflow.sk/oauth/google/integration/callback`.
5. Request only:
   - `openid`
   - `email`
   - `profile`
   - `https://www.googleapis.com/auth/gmail.readonly`
6. Complete Google's required verification for the restricted Gmail scope
   before production use. Keep the integration disabled until verification and
   the public callback deployment are both complete.

Official references:

- <https://developers.google.com/identity/protocols/oauth2/web-server>
- <https://developers.google.com/identity/openid-connect/openid-connect>
- <https://developers.google.com/workspace/gmail/api/auth/scopes>

## 2. Public callback gateway (`zevsflow-site`)

The repository contains the callback route in
`worker/google-oauth-gateway.ts`. Configure these runtime variables in the
hosting environment:

- `GOOGLE_INTEGRATION_CALLBACK_UPSTREAM_URL`: HTTPS URL of the private callback
  service endpoint.
- `GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET`: random value of at least 32 characters,
  identical to the backend value.

The callback must:

- accept only `GET /oauth/google/integration/callback`;
- reject duplicate, unknown, oversized, or malformed query parameters;
- send a bounded JSON `POST` to the internal callback;
- never render provider diagnostics, authorization codes, tokens, state, email,
  workspace IDs, or internal URLs;
- return `Cache-Control: no-store`, a restrictive CSP, no-referrer policy, and
  `X-Robots-Tag: noindex, nofollow`.

Deployment is intentionally outside this implementation session.

## 3. Backend configuration

Keep `GOOGLE_GMAIL_ENABLED=0` until all values have been installed and checked.
When ready, provide:

```dotenv
GOOGLE_GMAIL_ENABLED=1
GOOGLE_INTEGRATION_CALLBACK_ENABLED=1
GOOGLE_OAUTH_CLIENT_ID=<secret>
GOOGLE_OAUTH_CLIENT_SECRET=<secret>
GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI=https://zevsflow.sk/oauth/google/integration/callback
GOOGLE_GMAIL_EXPECTED_EMAIL=<exact-google-account-email>
GOOGLE_GMAIL_TARGET_WORKSPACE_ID=<canonical-workspace-id>
GOOGLE_GMAIL_STATEMENT_QUERY=<trusted-admin-query>
GOOGLE_TOKEN_CRYPTO_SECRET=<fernet-compatible-secret>
GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET=<same-random-proxy-secret>
GOOGLE_INTEGRATION_CALLBACK_HOST=127.0.0.1
GOOGLE_INTEGRATION_CALLBACK_PORT=8081
```

Optional bounded controls:

```dotenv
GOOGLE_GMAIL_CHECK_INTERVAL_SECONDS=86400
GOOGLE_GMAIL_INITIAL_LOOKBACK_DAYS=30
GOOGLE_GMAIL_OVERLAP_HOURS=24
GOOGLE_GMAIL_BATCH_SIZE=25
GOOGLE_GMAIL_MAX_ATTACHMENT_BYTES=15728640
GOOGLE_GMAIL_ALLOWED_MIME_TYPES=application/pdf,text/csv,application/csv
GOOGLE_GMAIL_ALLOWED_EXTENSIONS=.pdf,.csv
GOOGLE_GMAIL_NOTIFICATION_COOLDOWN_SECONDS=86400
```

Do not put secrets in git, logs, screenshots, task documents, browser URLs, or
Telegram messages.

## 4. Activation and verification

1. Back up the current SQLite database and storage root.
2. Start the backend with Gmail still disabled and run the test suite.
3. Install the complete environment configuration.
4. Start the backend. Enabled-but-incomplete configuration must fail closed
   before Telegram polling.
5. From an authorized administrator account that belongs to the exact target
   workspace, run `/gmail_connect`.
6. Complete Google consent using the expected Gmail address.
7. Run `/gmail_status`. It may report identity and lifecycle status, but must
   not show tokens, scopes as secrets, paths, message IDs, or attachment IDs.
8. Place one allowlisted test statement attachment in a message matching the
   trusted Gmail query.
9. Let one scheduler tick run and verify:
   - one `gmail_statement_imports` record;
   - one tenant-scoped `original.<ext>` and `metadata.json`;
   - `parse_status=deferred`;
   - no duplicate original on a repeated tick;
   - no Drive permission or upload;
   - no parsing or LLM call.
10. Test `/gmail_disconnect`. Local imported files must remain; the active grant
    must no longer be usable.

## 5. Failure and recovery

- `401`/`403` from Gmail transitions the binding and grant to
  `needs_reauth`; collection stops until a new `/gmail_connect` succeeds.
- Retryable provider failures do not delete or rewrite stored files.
- A source duplicate is skipped before attachment download where possible.
- A content duplicate gets its own metadata record but reuses the canonical
  workspace-local original.
- A crash before atomic directory promotion leaves no authoritative stored
  import. Temporary artifacts can be audited and removed only after backup and
  explicit approval.

## 6. Rollback

1. Set `GOOGLE_GMAIL_ENABLED=0` and
   `GOOGLE_INTEGRATION_CALLBACK_ENABLED=0`.
2. Restart the backend.
3. Remove or disable the public callback route only as a separate deployment
   action.
4. Revoke the Google grant in the Google Account security page if required.
5. Preserve SQLite rows and stored originals for audit. Do not delete them as
   part of rollback.

Local `/gmail_disconnect` and provider-side revocation are separate operations.
Neither operation deletes already collected business documents.
