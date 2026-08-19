# OfficeFlow Platform-Neutral Android Foundation V1 — Architecture Design Proof

Verdict: `ready_for_handoff`

Approved product decisions:

1. OfficeFlow/FakturaBot is the business product; Telegram is the current interface/transport, not the product boundary.
2. The target architecture supports multiple clients over one OfficeFlow business core. Telegram remains supported during migration; Android is the first planned first-party client.
3. `workspace_id` remains the canonical business-data and tenant-isolation boundary.
4. A new platform-neutral internal user identity (`principal_id`) is introduced above external identities. Telegram identity becomes one external identity mapping rather than the permanent canonical product identity.
5. Existing `telegram_id` / `supplier_telegram_id` columns are not bulk-renamed or mass-migrated in Stage A. They remain transitional actor/notification/audit compatibility fields where current runtime still requires them.
6. Stage A is deliberately narrow: identity, enrollment/session foundation, and read-only OfficeFlow HTTP API. It does not move business FSM ownership out of aiogram and does not expose business mutations.
7. The controlled Android pilot uses an administrator-issued, single-use, expiring enrollment secret exchanged for opaque server-issued API session credentials. No Google/Firebase/Telegram login provider is required for this pilot.
8. Enrollment secrets and API access/refresh tokens are stored only as hashes server-side. The client never chooses or asserts its principal or authorization state.
9. Stage A business reads are workspace-scoped and membership-validated. An explicitly requested read workspace never mutates `active_workspace_selection`.
10. Stage A does not claim that Android is supported. Product Truth may say only that a platform-neutral API/authentication foundation exists after implementation and proof.
11. The HTTP API should reuse the repository's existing `aiohttp` dependency and run as a separate process from Telegram polling.
12. No implementation prompt may change these decisions unless a design contradiction is first returned to the user for review.

Approval date: 2026-08-19  
Repository baseline reviewed: `Mykh-Ai/Ai_assistant` `main` at `f1a56119da9b0ba5068f4e9060753f55c7de4afe`  
Architect: ChatGPT with user approval

---

## 1. Task Identity And Product Need

Task id / name: `OFFICEFLOW_PLATFORM_NEUTRAL_ANDROID_FOUNDATION_V1`

Business need:

OfficeFlow currently exposes its business workflows through Telegram. That was a useful first interface, but it constrains product UX and routes user messages, voice, documents, and callbacks through a third-party messaging platform. The product direction is a first-party Android application with purpose-built screens for business profiles, invoices, accounting documents, contacts, projects/reservations later, and the conversational assistant.

The current business implementation must not be rewritten or forked into an Android-specific second system. The safe first step is to create a platform-neutral identity and read API foundation so Telegram and a future Android client can become adapters around one OfficeFlow core.

User-visible target outcome across the broader migration:

```text
Android app / future clients
        │
        ├──────────────┐
        │              │
Telegram adapter       │
        │              │
        ▼              ▼
OfficeFlow application / conversation layer
        │
        ▼
OfficeFlow business services
        │
        ▼
workspace-scoped DB / files / Google / OpenAI integrations
```

Stage A user-visible outcome is intentionally smaller:

- an approved existing OfficeFlow user can be enrolled for first-party API access;
- an authenticated client can list the user's accessible business workspaces;
- an authenticated client can read workspace-scoped invoices, invoice PDF content, and contacts;
- no Stage A endpoint can create, edit, delete, pay, upload, switch persistent business context, or run a conversational business workflow.

Current Product Truth status: `planned` for Android / platform-neutral user API; Telegram remains the current runtime interface.

Target Product Truth status after Stage A implementation and acceptance: `partial` foundation only. Android application support remains `planned` until an actual Android client and per-capability acceptance proofs exist.

Risk level: `high` for identity/authorization/tenant isolation; `migration-sensitive`; deliberately `low business-side-effect surface` because Stage A business endpoints are read-only.

---

## 2. Architecture Classification

Chosen class: infrastructure/application-boundary extension plus access/identity extension. This is **not a new top-level business action**.

Why this is not a new top-level action:

- the user is not starting a new standalone business operation;
- existing business actions such as `create_invoice`, `show_existing_invoice`, `edit_existing_invoice`, `add_contact`, `add_receipt`, `switch_business_profile`, analytics, and work-time remain the canonical business operations;
- Android UI navigation and HTTP reads are transport/read projections, not new canonical business actions;
- Stage A contains no new business FSM, no new confirmation flow, and no executable semantic action.

Existing flows extended:

- authorization gains a platform-neutral principal/session entry above the existing Telegram access model;
- workspace membership becomes reusable from a non-Telegram transport;
- invoice/contact domain services gain only the read projections needed by the API where a current read method is missing.

Existing runtime owners:

- `bot/services/access_control.py::AccessControlService`
- `bot/services/workspace_context.py::WorkspaceContextService`
- `bot/services/scoped_invoice_runtime.py::ScopedInvoiceRuntime`
- `bot/services/workspace_invoice_service.py::WorkspaceInvoiceService`
- `bot/services/workspace_contact_service.py::WorkspaceContactService`
- `bot/services/db.py`

Evidence:

- `AGENTS.md` states that Telegram is the current runtime surface but only the interface, while OfficeFlow/FakturaBot is the business operating layer.
- `docs/Product_Doctrine_2030.md` states that product identity is larger than Telegram.
- `docs/architecture/MULTI_WORKSPACE_BUSINESS_PROFILES_ARCHITECTURE_DESIGN_PROOF.md` makes `workspace_id` the canonical business tenant and explicitly separates business workspace identity from Telegram actor identity.
- `bot/services/workspace_context.py` currently still represents the actor as `actor_telegram_id`, proving the external-person identity remains coupled to Telegram.
- `bot/services/scoped_invoice_runtime.py` already provides an explicit workspace-aware facade over invoice/contact services.

---

## 3. Canonical Action Contract

No new canonical top-level or in-FSM business token is introduced by Stage A.

Existing canonical business action registry remains authoritative. Android must eventually invoke the same owners; it must not create parallel tokens such as `android_invoice`, `android_contact`, `android_receipt`, or `android_delete_invoice`.

Stage A API endpoints are transport/read capabilities, not semantic business actions.

Relevant existing action boundaries that must remain unchanged:

- `create_invoice`
- `show_existing_invoice`
- `edit_existing_invoice`
- `delete_existing_invoice`
- `mark_existing_invoice_paid`
- `invoice_analytics`
- `add_contact`
- `show_recent_accounting_documents`
- `accounting_document_analytics`
- `add_receipt`
- `switch_business_profile`
- work-time actions

Status of those actions: unchanged from `docs/llm/Canonical_Action_Registry.md` and current Product Truth.

Future rule for Android:

```text
Telegram text ─┐
Telegram voice ├─> canonical action owner
Android text  ─┤
Android voice ─┤
Android button ┘
```

Stage A does not implement the lower three Android execution paths yet.

---

## 4. Semantic Boundary Matrix

| User/client meaning | Expected Stage A behavior | Why | Must not become |
|---|---|---|---|
| list my accessible business profiles | read-only workspace list | navigation/read projection | persistent workspace switch |
| read invoices in workspace A | validated workspace-scoped read | existing stored business data | invoice analytics or cross-workspace aggregation |
| read invoice 123 in workspace A | read-only invoice detail if owned | object projection | edit/delete/pay action |
| fetch PDF for invoice 123 | stream validated existing PDF | read artifact | exposing `pdf_path` or arbitrary filesystem read |
| read contacts in workspace A | workspace-scoped contact list | existing master data | add/edit contact |
| create an invoice | Stage A unsupported / no route | mutating canonical action deferred | direct DB write or hidden `create_invoice` execution |
| delete invoice 123 | Stage A unsupported / no route | destructive canonical action requires shared confirmation architecture | HTTP `DELETE` shortcut |
| mark invoice paid | Stage A unsupported / no route | existing confirmation-gated mutation | direct follow-up-state write |
| switch active workspace | Stage A does not mutate persistent active selection | Telegram FSM still owns live workflow state | changing `active_workspace_selection` from API |
| ask a capability/how-to question | no Stage A conversational route | InfoHelp/conversation API deferred | capability answer that executes a business action |
| request another member's/workspace's id | fail closed | tenant boundary | object existence leak or fallback read |
| unknown/invalid workspace id | 404/403-style bounded failure without data | no closest-match write/read | default to current/first workspace silently |

Ambiguous read scope definition:

```text
meaning:
  client requests a business-data read but there is more than one accessible workspace
positive_examples:
  explicit validated workspace_id from GET /v1/workspaces
not_this:
  changing the persisted active workspace, guessing from mutable labels, choosing a closest workspace
```

---

## 5. Structured Slot Contract

Stage A has no LLM-supplied business slots. API request fields are deterministic transport/access inputs.

| Slot / field | Type / allowed values | Source | Required | Default owner | Invalid behavior | Precision boundary |
|---|---|---|---|---|---|---|
| authenticated principal | internal opaque `principal_id` | server session lookup only | yes | server | 401/fail closed | client may never supply/override it |
| external identity | provider + subject | server identity mapping | yes for current bridge | server | no principal resolution | Telegram subject is compatibility identity, not tenant key |
| requested workspace | stable `workspace_id` from accessible candidates | client read request | required when multiple memberships; optional when exactly one | Python membership service | fail closed; no guessed workspace | no LLM; labels are presentation only |
| enrollment secret | cryptographically random one-time secret | administrator-controlled enrollment delivery | exchange only | server generator | reject expired/used/invalid | secret stored only as hash |
| access token | opaque random token | server-issued | API requests | server | 401 | stored only as hash |
| refresh token | opaque random token | server-issued | refresh | server | 401/re-auth needed | stored only as hash; rotate on refresh |
| invoice id | integer/object identifier | URL path | object read | no default | return not-found without cross-workspace leak | server verifies workspace ownership |
| contact id if later exposed | integer/object identifier | URL path | object read | no default | same fail-closed rule | server verifies workspace ownership |

Rules:

- no LLM/STT/LMM participates in these values;
- no client-provided Telegram id is trusted for authorization;
- no client-provided `principal_id` is trusted;
- a requested workspace is a read scope, not an authorization claim; Python always validates membership;
- missing workspace with multiple memberships returns a bounded selection-required response rather than silently selecting or mutating state;
- missing workspace with exactly one active membership may be resolved deterministically without changing `active_workspace_selection`.

---

## 6. Public Route And Convergence Map

### Stage A routes

| Entry mode | Public entry | Guards before business data | Resolver/helper | Shared Python owner | Result |
|---|---|---|---|---|---|
| enrollment | `POST /v1/enrollment/exchange` | bounded body; enrollment hash/expiry/single-use; mapped authorized user | deterministic auth only | `ApiEnrollmentService` + `PrincipalIdentityService` + `ApiSessionService` | session credentials or fail closed |
| refresh | `POST /v1/session/refresh` | refresh hash, expiry, revoke state, user active state | deterministic auth only | `ApiSessionService` | rotated credentials or 401 |
| session read | `GET /v1/session` | bearer token, principal resolution, current access status | deterministic | `OfficeFlowApiContextService` | sanitized current session/principal status |
| workspace list | `GET /v1/workspaces` | bearer token; current access status | deterministic | principal-to-legacy identity bridge + `WorkspaceContextService` | accessible sanitized workspaces |
| invoice list | `GET /v1/invoices?workspace_id=...` | bearer token; workspace membership | deterministic | workspace invoice/scoped read service | sanitized invoice list |
| invoice detail | `GET /v1/invoices/{id}?workspace_id=...` | bearer token; workspace membership; object ownership | deterministic | workspace invoice/scoped read service | sanitized detail or not-found |
| invoice PDF | `GET /v1/invoices/{id}/pdf?workspace_id=...` | bearer token; membership; object ownership; persisted file validation | deterministic | workspace invoice/PDF owner | streamed PDF; no path exposure |
| contacts | `GET /v1/contacts?workspace_id=...` | bearer token; workspace membership | deterministic | workspace contact/scoped read service | sanitized contact list |
| revoke | `DELETE /v1/session` | current bearer token | deterministic | `ApiSessionService` | current session revoked |

There is no Stage A text/voice/button business route.

Transport rule:

- use the existing `aiohttp` dependency;
- run the API as a separate process, proposed entrypoint `python -m bot.officeflow_api_app`;
- do not insert the HTTP server into `bot/main.py` polling lifecycle;
- deployment/public exposure is a later rollout gate, not an automatic implementation consequence.

Existing evidence: `bot/google_integration_callback_app.py` already demonstrates bounded `aiohttp.web.Application` construction and safe HTTP request handling inside the repository.

---

## 7. FSM Graph And State Ownership

Stage A introduces **no business FSM** and does not alter aiogram `FSMContext` ownership.

Current live business FSM remains Telegram-owned. This is a deliberate boundary because `bot/services/active_fsm_guard.py` and `bot/handlers/voice.py` use aiogram `FSMContext`, Telegram `Message`, callback/message ownership, and state-specific handlers.

### Authentication/enrollment lifecycle

```text
NO API ACCESS
  -> admin issues one-time enrollment
      -> ENROLLMENT_PENDING
          -> valid exchange before expiry
              -> enrollment consumed
              -> API_SESSION_ACTIVE
                  -> access request -> read-only business API
                  -> refresh -> rotate credentials -> API_SESSION_ACTIVE
                  -> revoke -> API_SESSION_REVOKED
                  -> access/refresh expiry -> API_SESSION_EXPIRED
          -> invalid / expired / already used
              -> fail closed; no session
```

No Stage A read request changes Telegram FSM state.

### Active Telegram FSM coexistence

```text
Telegram active business FSM
        +
Android/API read request
        -> allowed only as read-only workspace/object projection
        -> no FSM clear
        -> no active workspace mutation
        -> no callback/confirmation execution
        -> no business write
```

This is why persistent `switch_business_profile` and all mutations are deferred until a later shared cross-channel flow-ownership design is implemented.

State table:

| State | Entry condition | Accepted inputs | Unknown behavior | Side effects allowed | Success state | Cancel/revoke | Stale behavior |
|---|---|---|---|---|---|---|---|
| enrollment pending | admin issued enrollment | exact secret exchange | reject | session creation only after validation | session active | enrollment can expire/administratively invalidate | expiry rejects |
| API session active | successful exchange/refresh | bearer reads, refresh, revoke | 401/404 bounded failures | session metadata/last-seen/rotation only; no business writes | active/revoked/expired | revoke supported | expiry rejects |
| API session revoked | explicit revoke/admin revoke | none except new enrollment | 401 | none | revoked | n/a | n/a |

---

## 8. Decision, Confirmation, And Callback Contract

No business confirmation-like decision or callback is introduced in Stage A.

Explicitly deferred:

- `approve/edit/cancel` business decisions;
- `yes/no` business confirmations;
- invoice paid confirmation;
- invoice delete confirmation;
- receipt/category confirmation;
- persistent workspace switch confirmation;
- Android decision callbacks.

Therefore Stage A must not create a generic `POST /v1/action` or `DELETE /v1/invoices/{id}` shortcut that bypasses existing confirmation contracts.

Authentication lifecycle controls:

```text
enrollment exchange:
  state/context required: valid pending enrollment
  expiry: mandatory
  replay: consumed enrollment is rejected
  wrong principal: client cannot select principal

session refresh:
  state/context required: valid active refresh token
  expiry: mandatory
  rotation: successful refresh invalidates the prior refresh credential
  replay: old/rotated/revoked token rejected

session revoke:
  state/context required: active session
  idempotency: repeated use of the now-revoked token returns unauthorized/no additional side effect
```

No local multilingual confirmation parser is introduced.

---

## 9. Side-Effect And Ownership Map

| Side effect | Trigger | Python owner | Validation before effect | Rollback / fail-safe | Idempotency |
|---|---|---|---|---|---|
| create principal | first approved enrollment where mapping absent | `PrincipalIdentityService` | existing authorized user, no conflicting provider+subject mapping | transaction rollback | unique provider+subject prevents duplicates |
| create external identity mapping | same | `PrincipalIdentityService` | verified existing identity and uniqueness | transaction rollback | unique constraint |
| create enrollment row | admin CLI/API-access tooling | `ApiEnrollmentService` | admin-controlled target, existing authorized user | no secret persisted in clear | one pending secret can be separately revoked/expired |
| consume enrollment + create session | valid exchange | `ApiEnrollmentService` + `ApiSessionService` | hash, expiry, unused, active access state | single transaction preferred; fail closed | enrollment one-time |
| refresh/rotate session | valid refresh | `ApiSessionService` | token hash, expiry, revoke, active user | atomic rotation | prior credential invalidated |
| revoke session | authenticated revoke/admin revoke | `ApiSessionService` | session ownership/status | no business data touched | repeated revoked token cannot re-execute |
| update session last-seen metadata | authenticated request | `ApiSessionService` | valid session | failure must not open business access | safe repeated metadata update |
| read workspaces | GET | existing workspace context service via API adapter | principal + active authorization | no write | naturally repeatable |
| read invoices | GET | workspace invoice/scoped read owner | membership + workspace scope | no write | naturally repeatable |
| stream PDF | GET | existing invoice/PDF owner | membership + invoice ownership + safe persisted path/file check | 404/fail closed | naturally repeatable |
| read contacts | GET | workspace contact/scoped read owner | membership + workspace scope | no write | naturally repeatable |

Forbidden Stage A side effects:

- invoice/contact/accounting/work-time business DB writes;
- PDF generation;
- file upload/staging;
- file delete/move;
- Google/Gmail mutation or OAuth changes;
- STT/LLM/LMM calls;
- Telegram messages/callbacks;
- `active_workspace_selection` writes from API;
- FSM set/clear/update;
- Product Truth registry mutation.

---

## 10. Authorization, Tenant, And Precision Boundaries

Authorization chain:

```text
Bearer token
-> session hash lookup
-> principal_id
-> principal external identity mapping
-> existing AccessControlService status
-> accessible workspace membership
-> requested workspace validation
-> workspace-scoped domain read
```

Rules:

1. Authentication/authorization occurs before any business-data read.
2. Stage A performs no STT/LLM/LMM/temp-file work, so those pre-authorization risks do not exist on the API path.
3. `workspace_id` remains the canonical business isolation key.
4. Client-provided workspace id is a requested scope only; membership is validated on every request.
5. Client-provided Telegram id/principal id is never an authority signal.
6. Blocked or `deleted_database` users fail API authorization even if an access/refresh token has not reached time expiry.
7. Removing active authorization must prevent subsequent API business reads.
8. Foreign invoice/contact ids return not-found/bounded denial without revealing cross-tenant object existence.
9. API responses must not expose Telegram IDs, `pdf_path`, storage roots, absolute server paths, token hashes, OAuth secrets, or other internal tenant keys not needed by the client.
10. No voice precision boundary is introduced because Stage A has no voice path.

Identity migration rule:

- create `principal` and `principal_external_identity` additively;
- do not rebuild current business tables in this slice;
- do not bulk backfill principals on deploy;
- create principal mappings lazily only through explicit approved enrollment;
- keep current `authorized_users` as the access-status authority for the controlled pilot.

---

## 11. User-Facing Response And Exit Contract

The Stage A API is machine-facing JSON/file transport, not a conversational UI.

Expected response purposes:

- enrollment success: return session credentials once, never the stored hashes;
- enrollment failure: generic invalid/expired/used result without disclosing other principals;
- session read: sanitized session/account status only;
- workspace list: opaque `workspace_id` plus presentation label and permitted non-sensitive metadata;
- multi-workspace data read with missing workspace: bounded `workspace_selection_required` response with no automatic persistent selection;
- invoice list/detail: sanitized business fields; no local paths;
- PDF: correct content type/file stream; no path disclosure;
- contacts: sanitized contact business fields only;
- unauthorized/blocked/revoked: 401-style response; no business payload;
- foreign object: 404-style response; no ownership disclosure;
- internal error: bounded server error; no secret/path/raw DB/provider exception text.

No Telegram keyboard is added/removed. Telegram FSM state is unchanged after every Stage A API request.

---

## 12. Product Truth And InfoHelp Contract

Proposed capability id for future Product Truth synchronization: `first_party_android_client` or a similarly approved registry identifier. This proof does **not** add a runtime Product Truth row itself.

Current status before implementation: `planned`.

Status after Stage A implementation: still **not `supported` Android**. The truthful state is `partial` foundation / Android client still planned.

What OfficeFlow may truthfully say after Stage A implementation:

> The system has a protected first-party API/authentication foundation that can be used by a future Android client. The Android application and full business workflows through Android are not implemented yet.

Limitations:

- no Android app in Stage A;
- no public self-registration;
- controlled admin-issued enrollment only;
- business API is read-only;
- no Android conversation/FSM/actions;
- no persistent workspace switch from API;
- no push notifications;
- no Android voice/document upload;
- Telegram remains the current user-facing runtime.

Forbidden claims:

- “OfficeFlow supports Android”;
- “Telegram is no longer used/needed”;
- “all Telegram functions work in Android”;
- “Android can create/edit/delete invoices”;
- “Android has end-to-end encrypted business messaging” unless separately implemented and proven;
- “public signup is available”.

Safe next step after Stage A: build the Android shell against the read API, then design shared cross-channel flow ownership before mutating actions.

Answer to “Can you use Android?” after Stage A:

> The Android client is still planned. The backend foundation for secure first-party access exists, but the Android app and its business workflows are not yet available.

Answer to “How do I use it?” after Stage A:

> There is no general Android user flow yet. Controlled API access is an administrator-managed pilot foundation only.

Capability questions must never create enrollment/session/business writes unless the user/admin is explicitly executing the corresponding access-management operation.

---

## 13. Negative-Space And Regression Contract

Stage A must not steal or alter:

### Existing business actions

- `create_invoice`, show/edit/delete/paid invoice flows;
- contacts and registry intake;
- receipt/incoming-invoice intake;
- invoice/accounting analytics;
- work-time actions;
- profile onboarding/edit;
- `switch_business_profile`;
- Gmail/Drive setup and schedulers;
- InfoHelp/customization/runtime issue flows.

### Telegram and FSM behavior

- `bot/main.py` remains the Telegram polling owner;
- aiogram FSM states continue to own current business conversations;
- active-FSM guard behavior remains unchanged;
- voice router remains unchanged in Stage A;
- Telegram callbacks and keyboards remain unchanged;
- Telegram active workspace selection is never mutated by Stage A reads.

### Read versus write

- no business mutation endpoint;
- no “helpful” generic action dispatcher;
- no direct database SQL from HTTP handlers as a bypass of domain owners;
- no cross-workspace fallback reads;
- no PDF path exposure;
- no file browser endpoint.

### Identity and migration

- no destructive rewrite of existing IDs;
- no mass principal backfill;
- no implicit merge of two external identities;
- no external provider becomes canonical product identity;
- no existing business row changes merely because API access is enrolled.

### Product claims

- no Android support claim until Android implementation is proven;
- no public SaaS/signup claim;
- no claim that data has been removed from all third parties while Telegram remains an active interface.

---

## 14. Acceptance Scenario Contract

### Scenario 1 — controlled enrollment happy path

Precondition: existing active authorized Telegram user; no principal mapping yet; admin issues enrollment.  
Exact input: valid one-time enrollment secret before expiry.  
Expected canonical action/slots: no business action; secret maps server-side to approved principal target.  
Expected state sequence: pending enrollment -> consumed -> active API session.  
Expected side effect: create principal/mapping if absent, consume enrollment, create hashed session credentials.  
Expected final state: active API session.  
Expected outcome: access/refresh credentials returned once; no business data changed.

### Scenario 2 — enrollment replay

Precondition: Scenario 1 completed.  
Input: same enrollment secret again.  
Expected effect: none.  
Final state: original session remains; no second session from replay.  
Outcome: bounded invalid/used enrollment response.

### Scenario 3 — expired enrollment

Precondition: pending enrollment past expiry.  
Input: enrollment secret.  
Expected effect: none; no principal/session created solely from expired exchange.  
Outcome: fail closed.

### Scenario 4 — session refresh rotation

Precondition: active session with valid refresh token.  
Input: refresh request.  
Expected effect: rotate credentials atomically; prior refresh credential invalid.  
Final state: one active rotated session lineage.  
Outcome: new credentials; replay of old refresh fails.

### Scenario 5 — blocked/deleted user after token issuance

Precondition: valid session; legacy access state becomes blocked or `deleted_database`.  
Input: any business GET.  
Expected effect: no business read.  
Outcome: unauthorized; session token does not override current access authority.

### Scenario 6 — list accessible workspaces

Precondition: active session, active authorization.  
Input: `GET /v1/workspaces`.  
Expected effect: none.  
Outcome: only membership-valid workspaces, sanitized ids/labels.

### Scenario 7 — single-workspace deterministic read default

Precondition: principal bridges to exactly one accessible active workspace.  
Input: invoice list without explicit workspace.  
Expected effect: none; no active-selection write.  
Outcome: read scoped to that one membership.

### Scenario 8 — multi-workspace missing read scope

Precondition: principal has two accessible workspaces.  
Input: invoice/contact read without workspace id.  
Expected effect: none.  
Outcome: `workspace_selection_required`; no silent selection and no `active_workspace_selection` change.

### Scenario 9 — valid explicit workspace invoice list

Precondition: active session; membership in requested workspace.  
Input: invoice list with validated workspace id.  
Expected effect: none.  
Outcome: only invoice rows from that workspace; no Telegram id/path fields.

### Scenario 10 — foreign workspace request

Precondition: active session without membership in target workspace.  
Input: invoice/contact read using that workspace id.  
Expected effect: none.  
Outcome: fail closed; no rows and no object-existence disclosure.

### Scenario 11 — foreign invoice id inside owned workspace request

Precondition: invoice id exists only in another workspace.  
Input: detail/PDF request using owned workspace scope plus foreign invoice id.  
Expected effect: none.  
Outcome: not-found; no cross-workspace lookup fallback.

### Scenario 12 — PDF read

Precondition: owned invoice with persisted valid PDF.  
Input: PDF GET.  
Expected effect: file read/stream only.  
Outcome: PDF bytes; response does not expose persisted path/server path. Missing unsafe file fails boundedly.

### Scenario 13 — contacts read

Precondition: owned workspace.  
Input: contacts GET.  
Expected effect: none.  
Outcome: only workspace contacts; no contact creation/edit.

### Scenario 14 — attempted business mutation route

Precondition: active session.  
Input: guessed `POST /v1/invoices`, `DELETE /v1/invoices/{id}`, pay/switch/action route.  
Expected effect: none.  
Outcome: route unavailable/method denied; existing business side effects untouched.

### Scenario 15 — active Telegram FSM coexistence

Precondition: same user has a fresh active Telegram invoice/contact/work-time FSM.  
Input: Stage A API read.  
Expected effect: read only; no FSM data/set/clear and no persistent workspace switch.  
Outcome: Telegram flow remains intact.

### Scenario 16 — no AI invocation on API reads

Precondition: valid session.  
Input: every Stage A business GET.  
Expected effect: no STT/LLM/LMM call.  
Outcome: deterministic read path only.

### Scenario 17 — Telegram regression

Precondition: Stage A code present but API process may be stopped.  
Input: existing Telegram regression suite and representative start/profile/invoice/contact/document/work-time journeys.  
Expected effect: unchanged from baseline.  
Outcome: Telegram runtime remains functional; API availability is not required for bot polling.

### Scenario 18 — Product Truth capability question

Precondition: Stage A implemented.  
Input: “Do you support Android?” through existing InfoHelp route after Product Truth synchronization work is separately implemented.  
Expected effect: no enrollment/session/business action.  
Outcome: truthful partial-foundation/planned-client answer, not “supported Android”.

---

## 15. Out Of Scope And Known Architecture Gaps

Deferred deliberately beyond Stage A:

- Android application code/UI;
- public automatic signup;
- email/password login;
- Google Sign-In / Firebase Auth;
- Telegram login as the Android authentication dependency;
- first-party push-notification architecture;
- shared cross-channel business FSM/session ownership;
- Android conversational text routing;
- Android voice/STT routing;
- Android photo/PDF upload and intake;
- `create_invoice` through Android;
- edit/delete/mark-paid/send through Android;
- contact mutations through Android;
- accounting-document mutations through Android;
- work-time mutations through Android;
- persistent workspace switch through Android/API;
- generic action endpoint;
- decision callback/nonce architecture for business writes;
- migration of all `telegram_id` columns to `principal_id`;
- replacing `workspace_membership.telegram_id` in this slice;
- cross-workspace analytics;
- projects/reservations/new business modules;
- disabling/removing Telegram;
- server deploy/public Cloudflare route as an automatic part of code implementation;
- broad self-learning changes.

Known architecture gap after Stage A:

Business flow state remains aiogram/Telegram-owned. Before the first Android mutating canonical action, a separate approved design must define cross-channel flow identity, state ownership, decision nonce/expiry, text/voice/button convergence, and safe behavior when Telegram and Android are used concurrently.

---

## 16. Evidence Index

Current repository evidence reviewed:

- `AGENTS.md`
  - mission: OfficeFlow/FakturaBot is not a Telegram command bot; Telegram is the current interface;
  - current baseline: Python/aiogram, SQLite, bounded AI, tenant-scoped multi-user runtime;
  - mandatory preflight and deterministic side-effect authority.

- `docs/Product_Doctrine_2030.md`
  - product identity larger than Telegram;
  - Python orchestrates/validates/executes; AI remains bounded;
  - no fake capability claims.

- `docs/architecture/OfficeFlow_Architecture_Framing.md`
  - OfficeFlow umbrella/module direction;
  - existing outgoing invoice/document boundaries;
  - no runtime claim without code evidence.

- `docs/architecture/MULTI_WORKSPACE_BUSINESS_PROFILES_ARCHITECTURE_DESIGN_PROOF.md`
  - `workspace_id` is the canonical business isolation key;
  - Telegram actor identity is distinct from business workspace identity;
  - membership validation and active-workspace safety;
  - transitional Telegram-derived fields may remain compatibility/audit fields.

- `docs/FakturaBot_Data_Migration_Runbook.md`
  - schema/tenant/path changes are migration-sensitive;
  - audit/backup/dry-run/rollback discipline;
  - no cross-tenant fallback as a migration substitute;
  - production multi-workspace migration already completed with workspace ownership foundation.

- `bot/main.py`
  - current runtime entry creates aiogram `Bot`/`Dispatcher`, Telegram authorization and active-FSM middleware, routers, and bot-dependent schedulers.

- `bot/services/authorization.py`
  - current user authorization is Telegram-user based.

- `bot/services/access_control.py::AccessControlService`
  - current active/admin/blocked/deleted-database access authority keyed by Telegram id.

- `bot/services/workspace_context.py::WorkspaceContextService`
  - current membership/selection service is workspace-aware but actor is still `actor_telegram_id` and membership remains Telegram keyed.

- `bot/services/db.py`
  - workspace schema exists;
  - current access/membership and multiple compatibility tables still carry Telegram-derived identity fields.

- `bot/services/scoped_invoice_runtime.py::ScopedInvoiceRuntime`
  - existing transitional workspace-aware facade over invoices/contacts/analytics/PDF storage.

- `bot/services/workspace_invoice_service.py::WorkspaceInvoiceService`
  - invoice reads/writes validate `workspace_id` and contact/invoice ownership.

- `bot/handlers/business_profiles.py`
  - persistent workspace switching is currently Telegram/FSM-aware and blocks switching during unrelated active flows.

- `bot/services/active_fsm_guard.py`
  - active workflow state and navigation are coupled to aiogram `FSMContext` and Telegram `Message`.

- `bot/handlers/voice.py`
  - current voice state dispatcher is Telegram/aiogram specific, proving a parallel Android FSM must not be created.

- `bot/google_integration_callback_app.py`
  - repository already uses bounded `aiohttp.web.Application` HTTP handling.

- `requirements.txt`
  - `aiohttp` is already a runtime dependency; no new web framework is required for Stage A.

- `docker-compose.prod.yml`
  - production currently starts Telegram bot polling and Cloudflare tunnel only; no general OfficeFlow user API process exists.

- `tests/test_architecture_import_boundaries.py`
  - existing contract pattern for enforcing layer boundaries.

- `docs/llm/Canonical_Action_Registry.md`
  - current business actions remain canonical and must not be duplicated for Android transport.

- `/mnt/data/Top_Level_Subflow_Architecture_Design_Proof_Contract.md` / project canonical equivalent
  - required proof sections, convergence, FSM, confirmation, side-effect, Product Truth, negative-space and acceptance gates used by this artifact.

---

## 17. Target Rollout Sequence Beyond Stage A

This sequence is directional context, not authorization to implement later stages without their own required design proof where they materially change FSM/actions/confirmations.

| Stage | Target outcome |
|---|---|
| A — Foundation | internal principal, external identity mapping, controlled enrollment/session, read-only workspace/invoice/contact/PDF API |
| B — Android shell | first-party Android login/enrollment UX, business-profile presentation, read-only invoices/contacts/accounting-document screens |
| C — First vertical canonical action | shared cross-channel flow ownership, then `create_invoice` through Android text/voice/buttons using the same Python action owner |
| D — Documents | Android photo/PDF input converges on existing attachment/accounting intake owners |
| E — Existing invoice mutations | edit/paid/delete with shared confirmation, nonce/expiry, idempotency and stale/wrong-flow protection |
| F — Work time / analytics / settings | port remaining proven actions/read models without duplicating business logic |
| G — Notifications | transport-neutral notification owner plus Android push; Telegram becomes one delivery adapter |
| H — Telegram independence | a new approved user can complete the supported lifecycle without Telegram; Telegram can remain an optional adapter or be retired by separate product decision |

---

## 18. Handoff Readiness Verdict

`ready_for_handoff`

The product direction and Stage A scope are approved. The implementation agent may implement **only Stage A** as frozen here. It must not infer Android UI, public signup, business mutation endpoints, shared FSM design, or later rollout stages.

Any contradiction discovered between this proof and current runtime/data must be reported as a design blocker before the agent invents a different identity, tenant, FSM, or confirmation architecture.
