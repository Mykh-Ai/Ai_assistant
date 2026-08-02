# Google Gmail Statement Collector V1 — setup runbook

Status: `requires_setup`, `requires_admin`, `requires_external_credentials`.

Last verified: 2026-08-02.

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
- The public callback keeps only state plus code or error, signs a five-minute
  relay with HMAC-SHA256, and redirects through the browser to the Tunnel
  endpoint. Business context never comes from browser query parameters.
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

## 2. Public callback gateway (zevsflow-site)

The Worker route is implemented in worker/google-oauth-gateway.ts. Configure
the HTTPS Tunnel relay URL and the same random callback proxy secret in Worker
and backend secret storage.

The callback must:

- accept only GET /oauth/google/integration/callback;
- reject duplicate, unknown, oversized, or malformed Google parameters;
- keep only state plus exactly one of code or error;
- add an issuance timestamp, base64url-encode the bounded payload, and
  authenticate it with HMAC-SHA256;
- return a no-store 302 to the configured Tunnel relay endpoint;
- never render or log provider diagnostics, authorization codes, tokens, state,
  email, workspace IDs, secret values, or relay URLs.

For the controlled Zevs production deployment:

- the remotely managed Tunnel publishes gmail-callback.zevsflow.eu;
- the Tunnel origin is http://bot:8081 on the private Compose network;
- Docker runs the pinned cloudflared image with no published VPS port;
- the file-backed Tunnel token is mounted read-only;
- Worker upstream is the relay route at
  https://gmail-callback.zevsflow.eu/internal/oauth/google/integration/callback;
- the Worker signs the payload and the backend verifies that signature in
  constant time before OAuth state or database work;
- relay age is limited to five minutes with bounded future clock skew;
- one-time OAuth state and nonce still prevent callback replay.

The Tunnel hostname is not a public business API. Requests without a valid
signed, short-lived relay fail closed. Do not publish port 8081 or configure a
direct VPS DNS record.

## 3. Backend configuration

Keep `GOOGLE_GMAIL_ENABLED=0` until all values have been installed and checked.
When ready, provide:

```dotenv
GOOGLE_GMAIL_ENABLED=1
GOOGLE_INTEGRATION_CALLBACK_ENABLED=1
GOOGLE_GMAIL_OAUTH_CLIENT_ID=<secret>
GOOGLE_GMAIL_OAUTH_CLIENT_SECRET=<secret>
GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI=https://zevsflow.sk/oauth/google/integration/callback
GOOGLE_GMAIL_EXPECTED_EMAIL=<exact-google-account-email>
GOOGLE_GMAIL_TARGET_WORKSPACE_ID=<canonical-workspace-id>
GOOGLE_GMAIL_STATEMENT_QUERY=<trusted-admin-query>
GOOGLE_TOKEN_CRYPTO_SECRET=<fernet-compatible-secret>
GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET=<same-random-proxy-secret>
GOOGLE_INTEGRATION_CALLBACK_HOST=0.0.0.0
GOOGLE_INTEGRATION_CALLBACK_PORT=8081
```

Optional bounded controls:

```dotenv
GOOGLE_GMAIL_CHECK_INTERVAL_SECONDS=86400
GOOGLE_GMAIL_INITIAL_LOOKBACK_DAYS=30
GOOGLE_GMAIL_OVERLAP_HOURS=24
GOOGLE_GMAIL_BATCH_SIZE=25
GOOGLE_GMAIL_MAX_ATTACHMENT_BYTES=15728640
GOOGLE_GMAIL_ALLOWED_MIME_TYPES=application/pdf,application/octet-stream
GOOGLE_GMAIL_ALLOWED_EXTENSIONS=.pdf
GOOGLE_GMAIL_NOTIFICATION_COOLDOWN_SECONDS=86400
```

Tatra banka currently labels its statement PDF as `application/octet-stream`.
That MIME type is accepted only for a `.pdf` filename whose downloaded bytes
start with the PDF signature `%PDF-`; other octet-stream files fail closed.

Do not put secrets in git, logs, screenshots, task documents, browser URLs, or
Telegram messages.

The Gmail client variables are intentionally separate from
`GOOGLE_OAUTH_CLIENT_ID` and `GOOGLE_OAUTH_CLIENT_SECRET`, which remain owned by
the existing Google Drive owner OAuth integration. Never replace the Drive
credentials while configuring Gmail.

## 4. Activation and verification

1. Back up the current SQLite database and storage root.
2. Start the backend with Gmail still disabled and run the test suite.
3. Install the complete environment configuration.
4. Create the remotely managed Tunnel, install its token file with mode
   `0600`, configure its public hostname and the Worker upstream/secret, then
   validate `docker compose -f docker-compose.prod.yml config`.
5. Start the backend and Tunnel. Enabled-but-incomplete configuration must fail
   closed before Telegram polling.
6. Verify that the callback port is not published by Docker and that a direct
   tunnel request without the proxy header is rejected.
7. From an authorized administrator account that belongs to the exact target
   workspace, run `/gmail_connect`.
8. Complete Google consent using the expected Gmail address.
9. Run `/gmail_status`. It may report identity and lifecycle status, but must
   not show tokens, scopes as secrets, paths, message IDs, or attachment IDs.
10. Place one allowlisted test statement attachment in a message matching the
    trusted Gmail query.
11. Let one scheduler tick run and verify:
   - one `gmail_statement_imports` record;
   - one tenant-scoped `original.<ext>` and `metadata.json`;
   - `parse_status=deferred`;
   - no duplicate original on a repeated tick;
   - if the separately configured Drive archive is enabled, one idempotent archive job; Drive failure must not fail or delete the local import;
   - no parsing or LLM call.
12. Test `/gmail_disconnect`. Local imported files must remain; the active grant
    must no longer be usable.

### Controlled production evidence — 2026-08-02

- Public signed callback relay and backend callback are deployed.
- Real configured-admin consent produced one encrypted connected Gmail grant
  and one active workspace binding.
- One manual first tick used the configured bounded query, saw one message,
  stored one workspace-local original/metadata pair, set
  `parse_status=deferred`, and reported zero rejected and zero failed.
- A second tick created no additional import. This does not replace an explicit
  overlap test that re-sees the same Gmail source.
- The separate owner Google Drive connection was reauthorized through the
  existing manual owner OAuth bootstrap. The queued bank-statement job and its
  archive state reached `uploaded`; the local Gmail import remained stored with
  `parse_status=deferred`.

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
3. Stop the `cloudflared` service and disable the Tunnel route. Remove or
   disable the public callback route only as a separate deployment action.
4. Revoke the Google grant in the Google Account security page if required.
5. Preserve SQLite rows and stored originals for audit. Do not delete them as
   part of rollback.

Local `/gmail_disconnect` and provider-side revocation are separate operations.
Neither operation deletes already collected business documents.
