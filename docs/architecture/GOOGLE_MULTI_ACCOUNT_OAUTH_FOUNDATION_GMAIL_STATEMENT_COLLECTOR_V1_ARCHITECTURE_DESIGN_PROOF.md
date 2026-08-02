# Google Multi-Account OAuth Foundation And Gmail Statement Collector V1

Verdict: `ready_for_handoff`

Runtime implementation status: `partial` locally; `runtime_not_proven` externally

Current Product Truth after local implementation: `partial`,
`requires_setup`, `requires_admin`, `requires_external_credentials`

Implementation verification: focused backend and gateway tests passed; full website suite and real Google/deployment smoke remain pending

This is an architecture and implementation-handoff proof. It does not prove
that Gmail is connected, Google verification is complete, the callback is
deployed, credentials exist, or a real statement has been collected.

## 1. Task Identity And Product Need

Task id:
`GOOGLE_MULTI_ACCOUNT_OAUTH_FOUNDATION_AND_GMAIL_STATEMENT_COLLECTOR_V1`.

Business need: allow an authorized workspace administrator to bind one
configured Google account to one business workspace and allow OfficeFlow to
collect configured Gmail bank-statement attachments automatically without
parsing statements or mutating the mailbox.

User-visible outcome:

- an administrator can prepare, inspect, and disconnect the pilot Gmail
  binding through `/gmail_connect`, `/gmail_status`, and `/gmail_disconnect`;
- after successful OAuth and deployment setup, a background collector searches
  using one trusted deployment query;
- valid attachments are stored as immutable workspace-owned originals with
  bounded metadata and deterministic deduplication;
- an original may be queued through the existing Google Drive archive worker;
- the workspace owner receives one redacted notification for a new statement;
- Product Truth states that parsing and accounting are not supported.

Current Product Truth:

- owner-run Google Drive archive: `partial`;
- generic multi-account Google OAuth: `partial` local foundation;
- Gmail statement collection: `partial`, disabled until external setup;
- parsing, transaction import, reconciliation, and Tatra banka API:
  `unsupported`.

Target Product Truth after code, tests, policy synchronization, and required
runtime evidence:

- generic Google identity and service-specific OAuth-grant foundation:
  `partial`;
- configured Gmail statement collection: `partial`, `requires_setup`,
  `requires_admin`, `requires_external_credentials`;
- parsing, transaction import, reconciliation, and bank API: `unsupported`;
- Tatra banka API: `planned` only if an active roadmap source records it.

Risk: `high` because this handles restricted Gmail data, refresh tokens, a
public callback, tenant isolation, DB/files, recurring external activity, and
optional Drive archival.

Date: 2026-07-30. Architecture owner: user-approved product architecture,
clarified and materialized by Codex.

AI maturity: no new AI execution layer. The collector is deterministic Python.
Product Truth/InfoHelp may provide Level 2 answers, but no LLM, STT, LMM, OCR,
or learning hook participates in OAuth, selection, validation, or storage.

## 2. Architecture Classification

Primary class: `deterministic internal strategy / background integration`.

The setup commands are admin-only settings operations. They are not a
canonical top-level action, LLM or voice action, Telegram FSM,
DecisionResolver flow, accounting intake subflow, parser, reconciliation, or
bank accounting.

No Canonical Action Registry token or `allowed_actions` entry is added.
Capability/how-to questions belong to Product Truth/InfoHelp and must not
create OAuth state or call Google.

Executable V1 values:

```text
service = gmail
grant_purpose = gmail
capability = mailbox_bank_statement_collection
```

The schema can represent future services, but service execution must reject
Drive, Sheets, and Docs until separately approved. Existing owner Drive OAuth
remains separate.

## 3. Canonical Action Contract

Not applicable. Public setup uses only exact deterministic admin commands:

```text
/gmail_connect
/gmail_status
/gmail_disconnect
```

The settings handler and integration services own them. Voice is excluded.

## 4. Semantic Boundary Matrix

| Meaning/input or event | Expected owner/result | Must not become |
|---|---|---|
| `/gmail_connect` from configured admin | Prepare one workspace-bound OAuth request | LLM action, Gmail call, connection write, or workspace switch |
| “Can you read statements from Gmail?” | Product Truth/InfoHelp answer | OAuth state, Gmail search, or file write |
| “Send this invoice through Gmail” | Unsupported outbound-email truth | Gmail send, SMTP, or collector |
| “Import transactions from this statement” | Unsupported parsing/accounting truth | Parser, OCR, reconciliation, paid-state mutation |
| Idle Telegram PDF/photo | Existing attachment/intake route | Gmail import |
| Gmail scheduler tick | Background integration owner | Active-workspace lookup or FSM |
| Existing owner Drive archive | Existing Drive owner/worker | Generic Gmail grant or Drive-token migration |
| Matching query/sender/subject | Discovery candidate only | Authenticity claim |
| `/gmail_disconnect` | Stop the selected local binding | Delete imports, Gmail messages, or Drive files |

Ambiguity and `unknown` never default to OAuth, Gmail, DB, file, archive, or
notification effects.

## 5. Structured Slot And Configuration Contract

There are no LLM slots. Values come from deployment config, canonical
workspace state, verified Google identity, or bounded transport metadata.

| Value | Source | Python validation/failure |
|---|---|---|
| target workspace | `GOOGLE_GMAIL_TARGET_WORKSPACE_ID` | Resolve with `resolve_for_background_workspace`; fail before Google/files |
| expected account | `GOOGLE_GMAIL_EXPECTED_EMAIL` | Normalize and compare after verified ID token |
| query | `GOOGLE_GMAIL_STATEMENT_QUERY` | Trusted config only; blank/oversized disables collection |
| scopes | Python constant | Exact V1 set; missing scope fails |
| redirect URI | config plus persisted state | Exact registered HTTPS URI |
| allowlists | deployment config | Bounded normalized MIME/extension sets; blank disables downloads |
| batch/page/size limits | positive bounded config | Invalid config prevents false-ready startup |
| paths | persisted `WorkspaceContext` | Safe canonical values only |
| identity | verified ID-token claims | Signature/issuer/expiry/audience/nonce/subject/email verification |
| message metadata | Gmail DTOs | Length/type/control-character bounds; body discarded |

Required configuration surface:

```text
GOOGLE_GMAIL_ENABLED=0
GOOGLE_GMAIL_TARGET_WORKSPACE_ID=
GOOGLE_GMAIL_EXPECTED_EMAIL=
GOOGLE_GMAIL_STATEMENT_QUERY=
GOOGLE_GMAIL_CHECK_INTERVAL_SECONDS=86400
GOOGLE_GMAIL_INITIAL_LOOKBACK_DAYS=
GOOGLE_GMAIL_OVERLAP_HOURS=
GOOGLE_GMAIL_BATCH_SIZE=
GOOGLE_GMAIL_MAX_PAGES=
GOOGLE_GMAIL_MAX_ATTACHMENT_BYTES=
GOOGLE_GMAIL_ALLOWED_MIME_TYPES=
GOOGLE_GMAIL_ALLOWED_EXTENSIONS=
GOOGLE_GMAIL_NOTIFICATION_COOLDOWN_SECONDS=

GOOGLE_INTEGRATION_CALLBACK_ENABLED=0
GOOGLE_INTEGRATION_CALLBACK_HOST=
GOOGLE_INTEGRATION_CALLBACK_PORT=
GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET=
GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI=
GOOGLE_GMAIL_OAUTH_CLIENT_ID=
GOOGLE_GMAIL_OAUTH_CLIENT_SECRET=
GOOGLE_TOKEN_CRYPTO_SECRET=
```

The pilot email belongs in deployment config, never source code.
The Gmail OAuth client variables are separate from the existing owner Drive
OAuth client variables; neither integration may overwrite the other's client
credentials.

## 6. Public Route And Convergence Map

| Entry | Guards | Python owner | Result |
|---|---|---|---|
| `/gmail_connect` | authorized configured admin, feature/config, canonical workspace | settings -> generic state service | one URL; no Gmail/binding effect |
| `/gmail_status` | authorized admin and target workspace | settings -> status services | redacted read-only status |
| `/gmail_disconnect` | authorized admin and target workspace | settings -> binding/grant service | local binding disabled |
| public callback GET | bounded query and gateway config | ZevsFlow Worker route | short-lived HMAC-signed browser relay |
| callback relay GET / legacy internal POST | HMAC or proxy secret, then state/auth/workspace/identity/scopes | generic callback service | transactional account/grant/binding or failure |
| scheduler tick | feature/workspace/binding/grant/lease | Gmail collector | readonly discovery/import |
| capability question | normal Product Truth routing | Product Truth/InfoHelp | honest no-effect answer |

Public route:

```text
GET https://zevsflow.sk/oauth/google/integration/callback
```

Backend relay route:

GET /internal/oauth/google/integration/callback?payload=...&signature=...

The existing secret-header JSON POST route remains fail-closed for internal
compatibility, but the production Worker uses the signed GET relay.

The ZevsFlow gateway remains server-side and never exchanges Google tokens.
Production evidence showed a material Cloudflare routing variance: a normal
Worker subrequest to the public Tunnel hostname failed even though the Tunnel
and backend were healthy. The approved transport therefore signs the bounded
relay payload with HMAC-SHA256 and returns a no-store browser redirect to the
outbound-only Tunnel hostname. The proxy secret never enters the URL or browser
JavaScript. The backend verifies the signature and five-minute issuance window
before OAuth state, database, or provider work.

The gateway accepts at most one `state`, `code`, and `error`. Repeated allowed
parameters, missing state, oversized values, or oversized total query fail
closed. `scope`, `authuser`, `prompt`, and `error_description` are not business
authority and are not forwarded. Granted scopes come from the token response.

## 7. State Graph And Ownership

No Telegram FSM exists.

OAuth graph:

```text
none -> pending -> consumed -> connection_saved
pending -> expired | rejected | invalid
pending -> consumed -> callback_failed
```

Forbidden:

```text
consumed -> consumed
expired/rejected -> connection_saved
identity/nonce/scope/authority mismatch -> connection_saved
```

State and nonce are independent:

- random `state` is returned once; only its hash is persisted;
- random OIDC `nonce` is sent to Google; only its hash is persisted;
- after official ID-token verification, Python hashes the returned nonce claim
  and compares it in constant time;
- missing, reused, or mismatched nonce is terminal.

State is atomically consumed before exchange. Failure after consumption never
allows replay; the admin starts a new `/gmail_connect`.

Import graph:

```text
discovered -> downloading -> stored -> archive_pending -> archive_uploaded
discovered -> ignored_filter_mismatch | rejected_unsupported | duplicate_source
downloading -> retry_wait -> downloading
downloading -> failed | duplicate_content
stored -> archive_not_configured | archive_retry_wait | archive_failed
```

Every stored/content-duplicate row has `parse_status=deferred`.

## 8. Decision, Callback, And Disconnect Contract

DecisionResolver is not applicable.

Before connect state creation: active authorization, configured admin, complete
Gmail/callback config, canonical target workspace, current setup authority,
expected email, exact redirect URI, and enabled callback runtime are required.
Connect creates state/nonce only and never switches active workspace.

The gateway enforces bounded input, a short-lived HMAC-SHA256 relay, no-store
browser redirect, and sanitized failure HTML. It never forwards browser
cookies or intentionally logs raw query, state, code, provider description,
secret, or relay URL.

The backend:

1. verifies the relay HMAC or legacy proxy secret in constant time before DB work;
2. accepts only a bounded structured payload within the relay TTL;
3. recovers all authority only from persisted OAuth state;
4. atomically consumes one pending unexpired state;
5. revalidates actor/admin/workspace/membership/service;
6. exchanges the code with bounded timeout and response size;
7. verifies ID token using the official installed Google auth library;
8. validates signature, issuer, expiry, audience, subject, email,
   `email_verified=true`, and nonce;
9. compares the verified email to configured expected email;
10. validates required scopes and first-connection refresh token;
11. encrypts the bounded token envelope;
12. transactionally saves account, grant, and binding;
13. sends a redacted Telegram result best-effort after commit.

The current unsigned JWT metadata decoder is never identity authority.

An omitted refresh token can reuse an existing one only after official proof
of the same subject, valid nonce/audience, the same OAuth client key and
service-specific grant, current workspace authority, successful token
decryption, and no substitution. First connection without refresh token fails
as `needs_reauth`. `invalid_grant` also becomes `needs_reauth`.

`/gmail_disconnect` is local in V1:

- disable the workspace Gmail binding immediately;
- preserve imports, files, metadata, and audit;
- never delete/mutate Gmail messages or Drive files;
- if no active binding uses the grant, clear encrypted token payload and access
  expiry, then mark it `disconnected`;
- if another authorized binding uses that exact grant, retain the token and
  report only that this binding stopped;
- retain minimal identity/audit metadata subject to data-deletion rules.

Local disconnect does not claim Google-side revocation. V1 explains how the
user can revoke access in Google Account settings. Provider revocation is a
future separately approved operation.

## 9. Side Effects, Data Model, And Ownership

| Effect | Owner | Gate | Failure/idempotency |
|---|---|---|---|
| state/nonce row | generic OAuth state service | auth/admin/config/workspace | no Google call; fresh bounded request |
| token exchange | generic exchanger | claimed state/current authority | no token write; state prevents replay |
| account/grant/binding | callback service | verified identity/nonce/email/scopes/encryption | one transaction and unique constraints |
| Gmail list/get | readonly adapter | canonical active binding/grant and lease | bounded retry and source dedup |
| import reservation | import service | source identity/allowlists | source uniqueness |
| original/metadata | storage service | path/MIME/size/hash | atomic promotion and reconciliation |
| Drive enqueue | existing outbox | stored import and immutable target | local success preserved; idempotent |
| notification | collector notifier | committed nonduplicate storage | best effort; `notified_at`/cooldown |
| disconnect/token clearing | binding/grant service | auth/admin/binding | transactional and idempotent |

### Generic identity and service-specific grant

Identity and token grant are separate so future services cannot silently
replace one token envelope with a different scope set.

`google_accounts`:

```text
account_id
google_subject UNIQUE
google_email
created_by_telegram_id
created_at
updated_at
```

`google_subject` comes only from verified identity. Email is descriptive;
subject is stable. `created_by_telegram_id` is audit, not tenant authority.
Reuse requires a fresh verified callback and current target-workspace authority.

`google_oauth_grants`:

```text
grant_id
account_id
oauth_client_key
grant_purpose
status
granted_scopes_json
encrypted_token_payload
token_key_id
token_version
access_token_expires_at
connected_at
disconnected_at
revoked_at
last_error_code
created_at
updated_at
```

Constraint:

```text
UNIQUE(account_id, oauth_client_key, grant_purpose)
```

`oauth_client_key` is a non-secret config alias. V1 purpose is `gmail`. Future
services receive separate grants; no hidden Drive/Sheets/Docs scope upgrade.
Token payload is authenticated encryption, versioned, excluded from repr, and
never logged. Status allowlist: `connected`, `disconnected`, `needs_reauth`,
`revoked`, `error`.

`google_workspace_service_bindings`:

```text
binding_id
workspace_id
grant_id
service
status
created_by_telegram_id
last_successful_check_at
last_attempt_at
last_error_code
created_at
updated_at
UNIQUE(workspace_id, service)
```

V1 service is `gmail`, referencing a compatible active Gmail grant.

`google_integration_oauth_states`:

```text
state_id
workspace_id
telegram_id
requested_service
oauth_client_key
expected_google_email
requested_scopes_json
redirect_uri
state_token_hash
oidc_nonce_hash
status
created_at
expires_at
consumed_at
last_error_code
```

State and nonce are independently random, hashed at rest, approximately
ten-minute TTL, and single use.

`gmail_statement_imports`:

```text
import_id
workspace_id
grant_id
binding_id
source_type
gmail_message_id
gmail_thread_id
source_attachment_key
gmail_attachment_id
mime_part_id
sender
subject
gmail_internal_date
original_filename
safe_display_filename
mime_type
size_bytes
sha256
local_original_path
local_metadata_path
collection_status
parse_status
duplicate_of_import_id
archive_status
archive_job_id
attempt_count
next_attempt_at
claim_token
claim_expires_at
last_error_code
created_at
updated_at
stored_at
notified_at
UNIQUE(workspace_id, gmail_message_id, source_attachment_key)
```

Source key is Gmail attachment id or `inline:<part_id>`. A non-unique
workspace/SHA index supports content dedup while retaining each source.

V1 does not add an unbounded collector-run log. The single in-process scheduler
is sequential, the collector has a local overlap guard, and bounded
`last_attempt_at`, `last_successful_check_at`, and `last_error_code` fields live
on the workspace/service binding. A separate bounded
`google_integration_notification_state` table stores only the last sent time for
cooldown-protected lifecycle notifications. Multi-process scheduler deployment
is not proven and would require a DB lease before enabling more than one
collector process.

All schema creation is additive/idempotent. Do not modify or reinterpret
`google_drive_connections`, `google_drive_oauth_states`,
`google_drive_folder_cache`, existing Drive tokens, archive jobs, or files.
There is no startup backfill.

Production enablement requires read-only audit, verified DB/storage/environment
backup, dry-run, explicit approval, and rollback point. Rollback disables flags
and preserves new tables/files; it does not auto-drop/delete them.

## 10. Authorization, Tenant, And External-Data Boundaries

Background owner:

```text
WorkspaceContextService.resolve_for_background_workspace(workspace_id)
```

Never use active selection, last profile, `telegram-<id>`,
`GOOGLE_DRIVE_OWNER_WORKSPACE_ID`, or email as Gmail tenant identity. Invalid
workspace/owner/membership/authorization/binding/grant fails before Gmail/files.

One configured account is bound only to the configured workspace in V1. Future
workspace bindings require fresh verified OAuth and current admin authority;
an existing Google subject alone is not authorization.

Allowed Gmail adapter operations: refresh, list IDs with trusted query, bounded
pagination, bounded metadata/MIME tree, selected attachment download, bounded
filename-bearing inline data, and DTO return.

Forbidden: modify, trash, delete, send, draft, labels, mark read/unread, history
mutation, arbitrary Telegram search, body retention, or LLM use. Ordinary
text/HTML, snippets, and unrelated inline content are discarded.

Attachments are untrusted opaque bytes. V1 performs no execution, extraction,
OCR, parsing, macro/archive handling, or authenticity claim.

`gmail.readonly` is a restricted scope that technically permits viewing
messages and settings. The trusted query limits application behavior, not the
OAuth permission. Policy/consent material must say this accurately. A matching
query/sender/subject does not authenticate an email or attachment.

## 11. Storage, Deduplication, Recovery, Archive, And Responses

Approved local path:

```text
storage/workspaces/<workspace.storage_key>/
  bank_statement_imports/gmail/<year>/<month>/<import_id>/
    original.<ext>
    metadata.json
```

Year/month comes from validated Gmail internal date, not attachment contents.
Validate workspace, source ids, filename, MIME/extension mapping, non-empty
bytes, maximum size, SHA-256, containment, control characters, traversal, and
symlink escape. An `application/octet-stream` candidate is accepted only for a
`.pdf` filename whose downloaded bytes begin with the `%PDF-` signature.

Atomic procedure:

1. reserve the unique source row;
2. claim it with an expiring token;
3. create only its workspace-owned temp directory;
4. write/flush/close original and compute SHA-256;
5. validate/write metadata using safe replacement;
6. atomically promote to final import directory;
7. verify both files and hashes;
8. then mark DB `stored`.

Crash reconciliation:

- expired `downloading` claim plus valid final files: verify and finalize;
- expired claim with only owned temp files: clean only that temp directory and
  retry boundedly;
- unreferenced final directory: audit/report, never auto-delete;
- stored local import without archive job: enqueue idempotently on reconciliation.

Source duplicate returns the existing row with no second download/file/job/
notification. Content duplicate in the same workspace retains a second source
metadata row, sets `duplicate_of_import_id`, references the canonical original
without symlink/hardlink, and creates no second original/job/notification.
Never deduplicate across workspaces.

Optional Drive target:

```text
<workspace.drive_folder_name>/<YYYY>/bankove_vypisy/<YYYY-MM>
document_type = bank_statement_original
```

Reuse the existing archive outbox/worker. Persist the immutable target; retries
never consult active selection or redownload Gmail. Drive failure/unconfigured
does not fail local storage. Bank-statement originals are never automatically
deleted after Drive upload; other retention stays unchanged.

`/gmail_status` shows workspace, Google email, binding/grant status, last
successful check, bounded error, parser deferred, and separate Drive status.
It never shows tokens, scopes, IDs, paths, query, provider data, or secrets.

Notification includes only workspace name, safe filename, received date,
parsing unsupported, and Drive uploaded/pending/not-configured. No notification
for no result, duplicates, ignored messages, or repeated error in cooldown.

## 12. Product Truth And InfoHelp Contract

Capability id: `mailbox_bank_statement_collection`.

Docs-only status remains `unsupported`. After proven implementation:

```text
partial
requires_setup = true
requires_admin = true
requires_external_credentials = true
```

Supported subset: one admin-bound configured Gmail/workspace, scheduled trusted
query, bounded immutable attachment storage/dedup, optional async owner-Drive
archive, status, and local disconnect.

Limitations: restricted mailbox-wide readonly permission; no mutation/sending,
authenticity guarantee, parsing, transactions, reconciliation, accounting,
invoice matching/paid update, cashflow/tax, Tatra API, push, multiple mailboxes,
or self-service. Google Cloud/callback/deployment setup is required.

Forbidden claims include technical access only to matching emails, parsed or
reconciled transactions, authenticity, Gmail send/modify, active Tatra/
Sheets/Docs, universal self-connect, Drive success while pending, and Google
verification/security assessment without evidence.

“Can you do this?” answer intent:

```text
After an administrator connects the configured Gmail account to the selected
business profile, ZevsFlow can periodically find configured attachments and
store them for that profile. It does not read or account for statement
contents. The permission is read-only but technically covers mailbox messages
and settings; ZevsFlow limits collector behavior to the configured filter.
```

“How do I use this?” answer intent:

```text
An administrator connects Gmail once for the configured profile. After
successful Google authorization and server setup, collection runs
automatically. /gmail_status shows the last check and /gmail_disconnect stops
local collection.
```

Questions create no OAuth/Gmail/import/file/archive/notification effect.

## 13. Negative-Space And Regression Contract

Preserve existing owner Drive connection/scopes/tokens/commands/callback,
folder cache/worker, invoice/receipt/incoming-invoice paths and retention,
workspace Drive targets, invoice/payment/analytics/contact/registry/intake/
work-time/access/voice/routing/FSM/DecisionResolver flows, active workspace
selection, unsupported outbound email truth, and unrelated Product Truth.

Do not add other Google scopes to the Gmail grant, use the owner Drive
workspace id as tenant, migrate Drive tokens, parse statements, send data to
AI, store bodies, mutate Gmail, create accounting rows, mark invoices paid,
claim authenticity, or broaden public onboarding.

## 14. Acceptance Scenario Contract

Create:
`docs/evals/GOOGLE_MULTI_ACCOUNT_OAUTH_FOUNDATION_GMAIL_STATEMENT_COLLECTOR_V1_conversation_acceptance_proof.md`.

Required scenario groups:

1. unauthorized/non-admin/invalid-workspace connect with no effect;
2. valid state plus nonce hashes and authorization URL;
3. signed-relay success, missing/duplicate/oversized input, invalid HMAC,
   output, and no secret exposure;
4. invalid relay signature or legacy proxy secret before DB work;
5. valid callback and wrong email, unverified email, invalid signature/issuer,
   wrong audience, expired token, missing subject, nonce mismatch, missing
   scope, first missing refresh token, safe same-subject refresh reuse,
   expired/rejected/reused state, revoked current authority, and DB rollback;
6. redacted status and idempotent disconnect, token clearing, import
   preservation, and no false provider-revocation claim;
7. no-result tick and invalid background scope before Gmail/files;
8. pagination, trusted query, nested MIME, attachment-id and inline attachment,
   body ignored, empty/oversized/unsafe/unsupported rejection;
9. valid atomic storage, source/content duplicate, cross-workspace isolation,
   retry, revoked token, no overlap, crash/temp reconciliation, and no parser/
   OCR/LLM with `parse_status=deferred`;
10. idempotent archive target, Drive failure/success local preservation, one
    notification, and duplicate no-notification;
11. Product Truth no-effect question and absence of Gmail mutation methods;
12. unchanged owner Drive, receipt/incoming retention, and invoice PDF journeys;
13. no voice/FSM/DecisionResolver/canonical-action change;
14. website policy truth, preserved enabled public indexing with an independent OAuth launch gate, and build/tests;
15. separate real OAuth/public HTTPS/test attachment/repeat tick/disconnect/
    integrity smoke.

Every scenario records precondition, exact event, authorization/workspace,
Python owner, state sequence, DB/file/network effect or no-effect,
idempotency/rollback, response, real/mocked boundary, and result.

Without real OAuth, public gateway, and Gmail attachment smoke, the verdict is
`runtime_not_proven` even when automated tests pass.

## 15. Out Of Scope, External Gates, And Known Gaps

Out of scope: statement/PDF/CSV/XML parsing, OCR, bank transactions,
reconciliation, accounting, invoice paid state, tax/cashflow, Tatra API/
webhook, Gmail push/mutation/send, self-service/dashboard, multiple Gmail
mailboxes, user-owned Drive/Sheets/Docs, Drive token migration, antivirus,
ZIP/macros/password-protected files, production credentials, Google/Cloudflare
changes, deployment, production migration, and implicit git delivery.

Implementation gates:

- verify current `zevsflow-site` server-route capability;
- verify current Google consent, restricted-scope verification, security
  assessment, testing audience, domain, branding, and data-policy requirements;
- set operational query/MIME/extension/size values without inventing a sender;
- request approval before dependency installation if official verification
  cannot use approved dependencies;
- obtain separate production backup/migration/deployment approval.

Official requirements checked 2026-07-30:

- web-server code flow, exact redirect, state, offline refresh, incremental
  authorization:
  <https://developers.google.com/identity/protocols/oauth2/web-server>
- signed ID token and OIDC nonce:
  <https://developers.google.com/identity/openid-connect/reference>
- `gmail.readonly` restricted classification and server-data security boundary:
  <https://developers.google.com/workspace/gmail/api/auth/scopes>
- minimum scopes/verification and current exemptions:
  <https://support.google.com/cloud/answer/13464321> and
  <https://support.google.com/cloud/answer/13464323>.

These are design evidence, not proof ZevsFlow passed verification.

## 16. Evidence Index, Handoff, And Verdict

Verified 2026-07-30 at local HEAD
`715c5941076f9f952f000daeae19a119bf4679d5`:

- `WorkspaceContextService.resolve_for_background_workspace` is the canonical
  background owner;
- `FernetTokenCryptoProvider` is the versioned encryption seam;
- `GoogleOAuthTokenExchanger` exists but is Drive-coupled and only decodes
  unsigned ID-token metadata;
- Drive hashed state/callback/connection patterns exist but no independent
  nonce or generic identity/grant model exists;
- archive outbox/worker owners exist;
- outbound email Product Truth remains unsupported;
- no Gmail schema, settings commands, adapter, collector, or scheduler exists.

Older task baselines are historical. Every implementation session records
current remote HEAD/status and preserves unrelated changes.

The companion website was cloned at approved current HEAD
`921f42047f9e1237fa1081b001b7d183166ce219`. Its Vinext/Cloudflare worker can
own the exact server-side callback route, and the bounded gateway implementation
has a passing direct Node test. The user explicitly approved preserving
`PUBLIC_INDEXING_ENABLED=true`; Gmail OAuth availability remains independently
gated by backend and gateway configuration. This is a
`minor_nonsemantic_variance` from the older task text, not an OAuth security
variance. No site deployment was performed.

Contracts read: `AGENTS.md`, Architecture Design Proof contract, New Action
checklist, Implementation Agent Checklist, Code-Agent Handoff Contract,
Evaluation standards, Product Doctrine, AI standards, Product Truth, InfoHelp,
Migration Runbook, multi-workspace and Drive workspace-isolation proofs,
Google Drive owner MVP, and current OAuth/crypto/workspace/archive/config/
settings/Product Truth code.

Implementation order:

1. record both repositories and run read-only design verification;
2. add additive schema/no-rewrite tests;
3. implement accounts, grants, bindings, state, official identity+nonce;
4. implement internal callback and public gateway;
5. add admin commands and readonly adapter;
6. add lease, collector, atomic storage, recovery, and dedup;
7. extend existing archive outbox narrowly and add notifications;
8. synchronize Product Truth, InfoHelp, TZ, policies, env/runbook, changelog,
   project log, tests, and acceptance proof;
9. run focused/full primary and website suites;
10. document, but do not perform, external/production steps without approval.

The implementation agent reports design variance, design-to-code/tests,
schema/storage no-rewrite evidence, redaction and isolation, Gmail readonly and
Drive regressions, exact tests/not-run boundaries, Product Truth/policies,
acceptance verdict, migration/rollback, external steps, and git status.

Final design-proof verdict: `ready_for_handoff`.

Implementation acceptance verdict: `runtime_not_proven` until external Google
verification, callback deployment, real mailbox smoke, and the blocked full
website suite are completed.

All material product, identity, grant, scope, callback, workspace, storage,
deduplication, disconnect, recovery, Product Truth, regression, acceptance,
and out-of-scope decisions are fixed. Material runtime contradiction blocks
implementation rather than authorizing silent redesign.
