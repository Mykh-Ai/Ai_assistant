# OfficeFlow Android Read-Only Shell V1 — Architecture Design Proof

Verdict: `ready_for_handoff`

Approval date: 2026-08-19  
Repository baseline reviewed: `Mykh-Ai/Ai_assistant` `main` after Stage A merge commit `0182221a5b3afa48939afcc4642575a69069b597`  
Architect: ChatGPT with product-owner approval

Approved product decisions:

1. Stage B creates the first first-party Android client, but it does not create a second FakturaBot/OfficeFlow business implementation.
2. Android is a thin client over the already-implemented Stage A API and existing Python business/read owners.
3. Stage B is read-only for business data. No invoice/contact/document/work-time mutation is introduced.
4. Android local workspace selection is a client-side read scope only. It must never mutate Telegram `active_workspace_selection`.
5. Stage B introduces no OfficeFlow business FSM, no canonical Android business actions, no LLM/STT/LMM route, no upload path, and no generic action endpoint.
6. The Android client may use only the Stage A routes that already exist in `bot/officeflow_api_app.py`.
7. Accounting-document screens are deferred because Stage A exposes no accounting-document HTTP read route. The earlier Stage A rollout table was directional context, not authorization to expand Stage B backend scope.
8. Credentials are server-issued opaque tokens. Android stores them only in app-private, non-backed-up encrypted storage using Android Keystore-backed key material.
9. Release/pilot network traffic is HTTPS-only. Cleartext is not an allowed release fallback.
10. A definitive revoked/expired/unauthorized session returns the user to enrollment. A transient network error does not silently destroy a potentially valid session.
11. Logout revokes the current session when possible and always erases local credentials. Offline logout must truthfully state that server revocation could not be confirmed.
12. Stage B may be implemented and accepted against a local/synthetic Stage A API. Production API deployment/public exposure is a separate rollout gate.
13. Product Truth after Stage B may claim only a controlled read-only Android pilot, not full Android OfficeFlow support.

---

## 1. Task Identity And Product Need

Task id / name: `OFFICEFLOW_ANDROID_READ_ONLY_SHELL_V1`

Business need:

Stage A established a platform-neutral principal/session boundary and a membership-validated read-only HTTP API. The next safe product step is to prove that OfficeFlow can be used from a first-party Android application without duplicating business logic, bypassing tenant boundaries, or interfering with Telegram-owned business FSM state.

User-visible Stage B outcome:

```text
install/start Android app
        ↓
enter one-time administrator enrollment code
        ↓
secure local API session
        ↓
load accessible business profiles
        ↓
select local read scope
        ↓
Invoices | Contacts
        ↓
Invoice detail -> PDF
```

The Android user can:

- enroll a controlled device using an administrator-issued one-time code;
- restore a previously valid local API session after app restart;
- view accessible workspaces/business profiles;
- choose the current Android read scope;
- view outgoing invoice lists;
- view invoice details and items;
- render an existing invoice PDF;
- view contacts;
- sign out.

The Android user cannot in Stage B:

- create, edit, delete, send, or mark invoices paid;
- create or edit contacts;
- upload or classify accounting documents;
- run text/voice assistant flows;
- mutate persistent business-profile selection;
- run work-time, analytics, Google Drive, Gmail, or other mutating workflows.

Current Product Truth status: Android client remains `planned/not implemented`; Stage A provides only backend foundation.

Target Product Truth after successful Stage B implementation and acceptance: `partial` Android support for a controlled, read-only first-party client. Full Android business-workflow support remains `planned`.

Risk level: `high` for credential/privacy/network handling, `medium` for client state/workspace correctness, `low business-side-effect surface` because business routes remain read-only.

---

## 2. Architecture Classification

Primary class: **reserved/planned capability promoted to a partial client runtime**.

This is not a new top-level business action because:

- no new business operation is created;
- Android screens project already-existing server data;
- existing canonical actions remain owned by current Python business/conversation owners;
- the Android client does not execute `create_invoice`, edit/delete/paid, contact mutations, document intake, work time, or analytics.

This is not a subflow/FSM extension because:

- Android does not join Telegram aiogram FSM state in Stage B;
- no shared cross-channel flow identity exists yet;
- all business mutations remain deferred until a later Stage C proof defines shared flow ownership.

Client architecture is new because the repository contains no existing Android/Gradle/Kotlin application module. Business architecture is not new: Android consumes the Stage A API rather than implementing OfficeFlow logic locally.

---

## 3. Canonical Action Contract

No new canonical business token is introduced.

Forbidden Stage B action tokens include, but are not limited to:

```text
android_invoice
android_contacts
android_pdf
android_workspace
android_logout
```

Android UI navigation is not a business action.

Examples:

- tapping `Invoices` means navigate to a read-only screen and call `GET /v1/invoices`;
- tapping an invoice row means call `GET /v1/invoices/{id}`;
- tapping `PDF` means call `GET /v1/invoices/{id}/pdf`;
- choosing a business profile means set a local read-scope preference, not execute `switch_business_profile`.

Existing business action ownership remains unchanged from `docs/llm/Canonical_Action_Registry.md` and current Product Truth.

---

## 4. Semantic Boundary Matrix

| Android/client meaning | Expected Stage B behavior | Why | Must not become |
|---|---|---|---|
| enter enrollment code | exchange one-time server enrollment | auth setup | public signup or caller-chosen principal |
| reopen app | restore/validate local session | session continuity | silent new enrollment |
| choose business profile | local read scope | UI navigation | server `active_workspace_selection` write |
| tap invoice | read detail | object projection | edit invoice flow |
| open PDF | fetch/render existing persisted PDF | read artifact | PDF generation or arbitrary file access |
| open contacts | read contact projection | master-data read | add/edit contact |
| sign out | revoke current API session when possible and erase local credentials | access lifecycle | `/vymazat_databazu` or business-data deletion |
| Android Back | local navigation | client UX | Telegram FSM cancel |
| HTTP 401 | bounded refresh or terminal session | auth lifecycle | infinite retry or auth bypass |
| HTTP 404 invoice/PDF | bounded unavailable state | fail closed | alternate-workspace fallback |
| network failure | retryable client state | transport failure | automatic account reset |
| ask a business/capability question | no Stage B assistant route | assistant deferred | hidden Telegram/InfoHelp execution |

Critical identity distinction:

```text
Android selectedWorkspaceId
!=
Telegram active_workspace_selection
```

The Android value is a local read preference only.

---

## 5. Structured Client Context Contract

Stage B has no LLM-supplied slots. Client state is deterministic.

| Field | Source | Required | Owner/default | Invalid behavior | Precision/security boundary |
|---|---|---|---|---|---|
| enrollment secret | typed/pasted by user | enrollment only | server-issued | bounded enrollment failure | never logged; never persisted after exchange |
| access token | Stage A server | authenticated requests | SessionRepository | refresh/terminal auth path | encrypted app-private storage only |
| refresh token | Stage A server | refresh | SessionRepository | fail closed | encrypted app-private storage only |
| access/refresh expiry | Stage A server | local auth state | SessionRepository | revalidate/refresh | metadata only |
| API base URL | build configuration | yes | build/release config | app cannot connect | release user cannot override it |
| workspace id | `/v1/workspaces` | business reads | WorkspaceRepository | clear stale selection | never hand-entered as authority |
| selected workspace | local app state | required when multiple | WorkspaceStateStore | picker required | never persisted server-side |
| invoice id | server invoice list | detail/PDF | navigation argument | bounded not-found | server still validates workspace ownership |
| invoice limit/offset | client constant/state | invoice list | deterministic | bounded client error | must stay inside Stage A limits |
| PDF bytes | server PDF route | PDF viewer only | PdfRepository | bounded unavailable | app-private temporary material only |

Rules:

- the Android client never sends `principal_id` or Telegram ID as authority;
- the Android client does not invent a workspace id;
- remembered workspace selection is valid only after it is re-confirmed in the latest `/v1/workspaces` response;
- Stage B does not persist invoice/contact business records into a local canonical/offline database.

---

## 6. Public Route And Convergence Map

Stage B may call only the Stage A route set below.

| Android entry | HTTP route | Guards | Client owner | Result |
|---|---|---|---|---|
| enrollment screen | `POST /v1/enrollment/exchange` | bounded code input | SessionRepository | authenticated session or bounded failure |
| app start/session validation | `GET /v1/session` | stored access token | SessionRepository | valid session metadata or auth path |
| refresh | `POST /v1/session/refresh` | one serialized refresh attempt | SessionRepository | rotated credentials or terminal/retry state |
| sign out | `DELETE /v1/session` | usable access token where possible | SessionRepository | server revoke + local sign-out |
| workspace list | `GET /v1/workspaces` | authenticated session | WorkspaceRepository | accessible workspaces only |
| invoice list | `GET /v1/invoices` | authenticated + workspace scope | InvoiceRepository | sanitized invoice list |
| invoice detail | `GET /v1/invoices/{id}` | authenticated + workspace scope | InvoiceRepository | sanitized detail |
| invoice PDF | `GET /v1/invoices/{id}/pdf` | authenticated + workspace + invoice ownership | PdfRepository | app-private PDF material |
| contacts | `GET /v1/contacts` | authenticated + workspace scope | ContactRepository | sanitized contact list |

Forbidden Stage B network calls:

- generic `/v1/action`;
- invoice/contact mutation routes;
- mark-paid/delete/send routes;
- workspace-switch mutation;
- upload/document routes;
- text/voice/LLM routes;
- any endpoint not present in Stage A.

---

## 7. Client State Graph And FSM Ownership

Stage B introduces **no OfficeFlow business FSM**.

Telegram aiogram FSM remains fully independent and is never read, mirrored, cleared, or updated by Android.

Android has a local application/session state machine:

```text
APP_START
   |
   +-- no credentials -> ENROLLMENT_REQUIRED
   |                       |
   |                       +-- valid exchange -> store session -> LOAD_WORKSPACES
   |                       +-- invalid/used/expired -> remain ENROLLMENT_REQUIRED
   |                       +-- network uncertain -> RETRYABLE_ENROLLMENT_ERROR
   |
   +-- credentials exist -> SESSION_VALIDATION
                            |
                            +-- access valid -> LOAD_WORKSPACES
                            +-- definitive auth failure -> REFRESHING
                            |       +-- success -> atomically replace credentials -> LOAD_WORKSPACES
                            |       +-- definitive 401/revoked -> SESSION_TERMINAL
                            |       +-- network unknown -> RETRYABLE_NETWORK_ERROR
                            |
                            +-- transport failure -> RETRYABLE_NETWORK_ERROR

LOAD_WORKSPACES
   +-- zero -> NO_WORKSPACE
   +-- one -> READY_SCOPED
   +-- multiple + valid remembered local scope -> READY_SCOPED
   +-- multiple + no/stale scope -> WORKSPACE_PICKER

READY_SCOPED
   +-- invoices
   +-- invoice detail/PDF
   +-- contacts
   +-- local workspace change
   +-- sign out
```

No Stage B UI event may set/clear Telegram FSM state.

---

## 8. Decision And Callback Contract

Stage B introduces no business confirmation and does not use DecisionResolver.

One client-only confirmation exists: **sign out**.

Canonical local outputs:

```text
confirm_sign_out
cancel
```

Cancel:

- zero server effect;
- zero local credential effect;
- remain in current screen/state.

Confirm:

1. attempt to obtain a usable access session when safe;
2. call `DELETE /v1/session` when server revocation can be attempted safely;
3. erase local access/refresh credentials;
4. clear local workspace preference;
5. return to enrollment-required state.

If server revocation cannot be confirmed because the network is unavailable:

- local credentials are still erased;
- the UI must state that sign-out on this device is complete but server-side revocation was not confirmed;
- administrator lost-device/session revocation remains the safe recovery path.

Sign out must never call `/vymazat_databazu` or delete business data.

---

## 9. Side-Effect And Ownership Map

| Side effect | Trigger | Owner | Validation before effect | Failure/rollback | Idempotency |
|---|---|---|---|---|---|
| save token pair | successful enrollment/refresh | SecureSessionStore | response shape/expiry validated | no partial plaintext persistence | replace atomically |
| rotate stored token pair | successful refresh | SessionRepository + SecureSessionStore | one coordinated refresh owner | keep prior local state until replacement is committed | single replacement |
| erase local credentials | logout/terminal session/local app-data reset | SecureSessionStore | none beyond local state | fail closed to enrollment | repeatable |
| store local workspace preference | explicit/automatic valid local selection | WorkspaceStateStore | id exists in latest accessible workspace list | stale selection cleared | repeatable |
| revoke current server session | confirmed sign out where network permits | Stage A `DELETE /v1/session` | authenticated session | offline -> local sign-out plus unconfirmed-server warning | server route semantics apply |
| download PDF | user opens owned invoice PDF | PdfRepository | authenticated + server ownership | bounded unavailable state | safe read |
| create temporary PDF file | successful PDF fetch | PdfRepository | PDF response validated | app-private cleanup | replace/delete safely |
| business DB mutation | none | forbidden | n/a | n/a | n/a |
| Telegram/FSM mutation | none | forbidden | n/a | n/a | n/a |

No Android component owns OfficeFlow business side effects.

---

## 10. Authorization, Tenant, Network, And Precision Boundaries

Authorization remains server-owned:

```text
access token
-> Stage A session
-> principal
-> active Telegram external identity bridge
-> AccessControlService
-> accessible membership
-> requested workspace
-> workspace-scoped business read
```

Android never treats possession of a workspace id or local UI state as authorization.

Tenant rules:

- only workspaces returned by `/v1/workspaces` may be presented/remembered;
- every business read sends an explicit workspace id when multiple workspaces exist;
- a server 404/409/401 is authoritative; Android must not guess another tenant or silently fall back.

Network rules:

- release/pilot configuration is HTTPS-only;
- no silent cleartext HTTP fallback;
- a debug-only, explicitly scoped local-development exception may exist for emulator/synthetic testing, but must not ship in release configuration;
- credentials are never placed in URL query strings.

Credential secrecy:

Do not expose access/refresh/enrollment credentials through logs, crash text, UI diagnostics, analytics payloads, screenshots/debug dumps, clipboard after enrollment completion, or backup/restore.

Retry rules:

- safe GET reads may retry once after one successful coordinated refresh;
- multiple simultaneous 401 responses must converge on one refresh owner;
- refresh/enrollment POST requests must not be blindly replayed after an ambiguous timeout;
- transient network failure must not automatically erase a potentially valid refresh token;
- definitive 401/revoked/invalid refresh returns to enrollment-required state.

Known Stage A reliability limit:

Stage A rotates refresh credentials atomically and stores only hashes. If rotation succeeds server-side but the network response containing the new pair is lost, the old refresh credential is already invalid. Stage B must fail closed and guide the user toward fresh administrator enrollment rather than inventing an unsafe replay/recovery protocol.

---

## 11. Android Client Architecture And Ownership

Approved initial repository shape:

```text
android/
  app/
```

Stage B uses one Android application module. A premature multi-module mobile platform is out of scope.

Approved ownership:

```text
Compose UI
   ↓ UI events / immutable UI state
ViewModel
   ↓
Repository layer
   ├─ SessionRepository
   ├─ WorkspaceRepository
   ├─ InvoiceRepository
   ├─ ContactRepository
   └─ PdfRepository
          ↓
OfficeFlowApiClient
          ↓
Stage A HTTP API
```

Separate local owner:

```text
SecureSessionStore
WorkspaceStateStore
```

UI must not:

- construct Authorization headers directly;
- store/read refresh tokens directly;
- implement refresh concurrency;
- parse raw server exceptions independently in every screen;
- implement workspace membership/tenant rules;
- duplicate invoice/contact business models beyond read-only DTO/UI projection needs.

One session-aware network owner serializes refresh and performs at most one authenticated retry after successful rotation.

Credential storage requirements:

- encrypted with Android Keystore-backed key material;
- stored only in app-private storage excluded from backup/restore;
- no raw token persistence in ordinary preferences, logs, database, or shared/external storage.

---

## 12. User-Facing Response And Exit Contract

### Enrollment screen

Purpose:

- explain that access is administrator-controlled;
- accept one-time enrollment secret;
- establish the first API session.

Outcomes:

- valid: store session and continue to workspace loading;
- invalid/expired/used: bounded error, remain on enrollment screen;
- network uncertain: explicit retry state; no infinite auto-submit;
- success: raw enrollment secret is discarded from UI/local state.

### Workspace selection

- zero accessible workspaces: safe empty state with retry/sign-out;
- exactly one: locally select automatically;
- multiple, first use: explicit picker;
- remembered workspace: use only if it remains in latest accessible list;
- stale remembered workspace: clear and show picker.

The current workspace name must remain visibly present in invoice/contact screens to reduce cross-business confusion.

### Invoice list

Display only Stage A projection fields such as invoice number, customer, dates, amount/currency, and status.

Pagination uses Stage A `limit/offset`; default Stage B page size is 50.

### Invoice detail

Read-only invoice data/items.

No edit/delete/pay/send controls.

### PDF viewer

- fetch through the Stage A PDF endpoint only;
- materialize only in app-private temporary storage if a file is required for rendering;
- render inside the app by default;
- do not treat the temporary copy as canonical storage;
- delete temporary material when it is no longer needed;
- do not expose arbitrary server/filesystem paths.

### Contacts

Read-only contact projection only.

No add/edit/delete controls.

### Sign out

- confirmation required at client UX level;
- server revoke when possible;
- local credentials always erased after confirmation;
- return to enrollment screen;
- never delete business data.

---

## 13. Product Truth And InfoHelp Contract

Capability id: `first_party_android_client`

Current status before Stage B implementation: `planned/not implemented`.

Target status after successful implementation and acceptance: `partial`.

Required flags after implementation:

```text
requires_admin = true
requires_setup = true
```

Truthful supported behavior after Stage B implementation:

> OfficeFlow has a first-party Android read-only client for a controlled pilot. After administrator enrollment it can show accessible business profiles, outgoing invoices, invoice PDFs, and contacts.

Limitations:

- administrator-issued enrollment is required;
- no public self-registration;
- business functionality is read-only;
- no Android invoice/contact mutations;
- no accounting-document screens;
- no Android text/voice assistant;
- no document upload;
- no work-time mutation;
- no push notifications;
- no full offline business database;
- Telegram remains an active interface for current business workflows;
- live remote pilot requires separate API deployment/public exposure.

Forbidden claims:

- "All OfficeFlow functions work on Android.";
- "Telegram is no longer needed.";
- "Android can create/edit/delete invoices.";
- "Android supports accounting-document intake.";
- "Anyone can register in the Android app.";
- "Android works fully offline.";
- "The Android pilot is live in production" unless API deployment/pilot activation is separately completed and proven.

Safe next step after Stage B: separately design Stage C shared cross-channel flow ownership before the first Android business mutation.

Capability/how-to questions through existing InfoHelp must not create enrollment, session, workspace selection, or business effects.

---

## 14. Negative-Space And Regression Contract

Stage B must not add/change:

### Backend

- Stage A HTTP route set;
- Stage A DB schema;
- principal/external-identity model;
- AccessControlService authority;
- workspace-membership rules;
- session/enrollment server semantics;
- PDF tenant isolation;
- account-reset credential revocation semantics.

### Telegram/business runtime

- Telegram `active_workspace_selection`;
- `bot/main.py` polling lifecycle;
- aiogram FSM;
- active-FSM guard;
- voice routing;
- confirmations/callbacks/keyboards;
- canonical business actions.

### Business functionality

- invoice create/edit/delete/pay/send;
- contact create/edit/delete;
- accounting-document read/upload/intake;
- receipt intake;
- Google Drive/Gmail mutation/setup;
- work-time actions;
- invoice/accounting analytics;
- Android text assistant;
- Android voice/STT;
- generic action execution;
- background synchronization;
- offline canonical business DB / Room mirror;
- push notifications;
- public signup;
- QR/deep-link action execution.

Accounting documents are deliberately deferred. Stage A exposes no accounting-document API route, and the previous rollout table was directional context only.

---

## 15. Acceptance Scenario Contract

Implementation acceptance must prove the applicable scenarios below with named automated tests and explicit manual/emulator smoke where UI behavior cannot be proven at unit level.

### S1 — fresh install

Precondition: no local credentials.  
Input: launch app.  
Expected state: `ENROLLMENT_REQUIRED`.  
Effect: none.  
UI: enrollment screen.

### S2 — valid enrollment

Precondition: valid administrator-issued one-time secret.  
Input: submit secret once.  
Expected state: enrolling -> authenticated -> workspace load.  
Effect: server session created by Stage A; encrypted local token pair stored; enrollment secret discarded.  
UI: progress then workspace/home.

### S3 — invalid/expired/replayed enrollment

Expected: bounded error; no authenticated local state; secret not persisted.

### S4 — app restart with valid session

Expected: restore encrypted credentials, validate session, resume without re-enrollment.

### S5 — access expiry with successful refresh

Expected: exactly one refresh owner, atomic local token replacement, original GET retried once.

### S6 — concurrent 401s

Expected: multiple reads converge on one refresh request; no refresh storm; all successful callers reuse the rotated pair.

### S7 — definitive revoked/invalid refresh

Expected: local credentials cleared; session becomes terminal; enrollment screen shown; no business payload displayed from stale cache.

### S8 — transient refresh/network failure

Expected: retryable network state; potentially valid local credentials preserved; no infinite loop.

### S9 — ambiguous refresh rotation / lost response

Expected: no blind replay loop; fail closed; user is guided to fresh enrollment if session recovery is impossible.

### S10 — one accessible workspace

Expected: local automatic selection; no server `active_workspace_selection` write.

### S11 — multiple workspaces first use

Expected: explicit picker; no silent first/Telegram-active selection.

### S12 — remembered valid workspace

Expected: reuse only after latest `/v1/workspaces` confirms access; current workspace name visible.

### S13 — stale remembered workspace

Expected: local selection cleared; explicit picker/empty state; no foreign fallback.

### S14 — local Android workspace change

Expected: subsequent reads use new requested workspace id only; Telegram persistent active selection remains unchanged.

### S15 — invoice list

Expected: exact selected workspace only; pagination respects Stage A contract; no duplicated/cross-workspace rows.

### S16 — invoice detail

Expected: read-only detail/items; no mutation controls or calls.

### S17 — missing/foreign invoice

Expected: bounded unavailable state; no alternate-workspace search/fallback.

### S18 — PDF success

Expected: Stage A PDF endpoint only; app-private render; no path disclosure; temporary material cleaned up.

### S19 — PDF 404/missing

Expected: bounded unavailable state; no client-side filename/path guessing and no regeneration.

### S20 — contacts

Expected: exact workspace contacts only; read-only UI.

### S21 — logout online

Expected: confirm -> server current-session revoke -> local credential/workspace erase -> enrollment screen.

### S22 — logout offline

Expected: local credential erase and enrollment screen; truthful UI indicates server revoke unconfirmed; no hidden claim of server revocation.

### S23 — administrator lost-device revoke

Precondition: Android session exists; administrator revokes opaque session id through Stage A CLI.  
Expected: next protected/refresh attempt terminates local session and returns to enrollment.

### S24 — `/vymazat_databazu`

Expected: pre-reset Android access/refresh/enrollment credentials remain permanently invalid after later re-approval; fresh enrollment required.

### S25 — ordinary block/unblock

Expected: while blocked protected API reads fail; if the same server session has not expired/revoked it may resume after re-approval according to Stage A semantics; Android must not convert ordinary block into local permanent credential revocation unless the server returns terminal session evidence.

### S26 — local app-data reset/uninstall semantics

Expected: no credential recovery from backup; new enrollment required.

### S27 — business-mutation negative space

Expected: Android source/network contract contains no business POST/PATCH/DELETE route except auth/session endpoints; UI contains no hidden mutation controls.

### S28 — accounting-document negative space

Expected: no accounting-document screen/network route is implemented in Stage B.

### S29 — Telegram regression

Expected: existing Telegram full regression remains unchanged; Android/API availability is not required for bot polling.

### S30 — Product Truth / InfoHelp

Expected: Android described only as partial/read-only controlled client after implementation; capability/how-to questions cause zero auth/business effects.

Acceptance environment:

- automated Android unit/instrumented tests where appropriate;
- emulator/device UI smoke;
- integration against a locally started Stage A API with synthetic SQLite/filesystem fixtures;
- full existing Python regression for shared backend guarantees.

Production API deployment is not required to accept Stage B code, but production/live-pilot claims remain forbidden until a separate rollout gate is completed.

---

## 16. Out Of Scope, Known Gaps, Evidence Index, And Verdict

Explicitly deferred:

- production API deployment/public Cloudflare exposure;
- Play Store publication;
- production signing/release pipeline;
- public user registration;
- Google/Firebase identity provider;
- accounting-document API/screens;
- Android `create_invoice`;
- invoice edit/delete/paid/send;
- contact mutations;
- document photo/PDF upload and intake;
- Android conversational text routing;
- Android voice/STT;
- shared cross-channel FSM/session ownership;
- push notifications;
- background sync;
- offline canonical business database;
- device attestation;
- biometric app lock;
- final supported Android OS/device matrix.

Known architecture/reliability gap:

Stage A refresh rotation is intentionally fail-closed but is not idempotently recoverable if the server commits rotation and the response carrying the new credentials is lost. Stage B must not invent unsafe recovery. If pilot evidence shows this is operationally significant, a separate auth-recovery protocol design is required.

Known rollout gap:

Stage A remains merged but not deployed/publicly exposed. Therefore Stage B can be implemented and fully contract-tested locally, but a real-phone remote pilot requires a separate API deployment/pilot gate.

Evidence index:

- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`
  - mandatory architecture-proof sections, handoff rule, negative-space and acceptance requirements.
- `docs/architecture/OFFICEFLOW_PLATFORM_NEUTRAL_ANDROID_FOUNDATION_V1_ARCHITECTURE_DESIGN_PROOF.md`
  - Stage A identity/session/read API architecture and directional Stage B rollout context.
- `docs/evals/OFFICEFLOW_PLATFORM_NEUTRAL_ANDROID_FOUNDATION_V1_acceptance_proof.md`
  - Stage A post-implementation evidence, tenant isolation, session lifecycle, account reset, Product Truth negative space.
- `bot/officeflow_api_app.py`
  - exact Stage A HTTP route surface used by Stage B.
- `bot/services/api_session.py`
  - current opaque access/refresh lifecycle, rotation, revoke and session metadata owners.
- `bot/services/officeflow_api_context.py`
  - server authorization and workspace scope owner.
- `bot/services/officeflow_read_service.py`
  - sanitized invoice/contact/PDF read projections.
- `bot/services/workspace_invoice_pdf_storage.py`
  - exact workspace-root PDF tenant boundary.
- repository root at merged Stage A baseline
  - no Android/Gradle/Kotlin client exists yet; Stage B mobile client starts as a new first-party adapter.
- Stage A merge commit `0182221a5b3afa48939afcc4642575a69069b597`
  - canonical repository baseline for Stage B design.

Final verdict:

`ready_for_handoff`

The product owner approved this Stage B architecture. An implementation prompt may be written from this proof, but it must implement only the Android read-only shell and must not infer Stage C business mutations, shared FSM architecture, accounting-document backend routes, production deployment, or broader Android capability.
