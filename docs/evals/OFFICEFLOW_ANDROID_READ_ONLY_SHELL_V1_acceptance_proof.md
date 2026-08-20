# OfficeFlow Android Read-Only Shell V1 — Stage B Acceptance Proof

Date: 2026-08-19

Approved design: `docs/architecture/OFFICEFLOW_ANDROID_READ_ONLY_SHELL_V1_ARCHITECTURE_DESIGN_PROOF.md`

Overall verdict: `runtime_not_proven`

## Real-phone pilot APK preparation — 2026-08-20

- A debug APK was installed and started successfully on an authorized Samsung
  pilot phone. Administrator enrollment was consumed successfully, the
  authenticated session reached multiple workspace choices, and invoice-list
  and contact-list reads were observed on that device.
- The dedicated public Stage A HTTPS boundary was proven separately at
  `https://officeflow-pilot-api.zevsflow.sk`, including valid TLS, HTTP-to-HTTPS
  redirection, and unauthenticated `401`/`405`/`404` boundaries. That rollout did
  not issue an enrollment or mutate business data.
- The bounded GitHub Actions pilot build uses workflow configuration rather
  than an application-source hostname. The manual pilot job passes the exact
  verified HTTPS URL as `OFFICEFLOW_DEBUG_API_BASE_URL`, runs JVM tests, lint,
  and debug assembly, and verifies the generated debug `BuildConfig` contains
  the pilot URL and not the emulator default before publishing the pilot-named
  APK artifact.
- The manual pilot job is isolated behind the required-reviewer
  `android-pilot-signing` environment and the exact pilot branch. Pull-request
  builds cannot reference its secrets. The protected keystore is restored only
  under runner-temporary storage, removed on every exit, and its public
  certificate SHA-256 is pinned to
  `3835035c2df22b22406a00c359cc1a03e54f61852c302ed7c6392702a9d8e6fe`.
  A local forced assembly and `apksigner` verification matched that pin.
- GitHub Actions run `32385806345` on exact code/workflow SHA
  `a19b45f7aa01d288410580b94a88202a09545c03` passed the protected-environment
  approval, Android tests/lint/build, endpoint proof, PEM/DER signer pin,
  checksum, artifact upload, and always-run key cleanup. Downloaded artifact id
  `9412994306` matched APK SHA-256
  `52c8fd682d6f6696637df58937a0dc05c5e2a742f7db68249260e733699f818a`
  and the pinned signer under independent local verification.
- The resulting pilot artifact is a debug APK for controlled real-phone
  acceptance. It is not a release, production-signed, Play Store, or general
  distribution build.
- The real-device invoice-list tap exposed a concrete protocol defect before the
  detail could render: production-shaped legacy invoice items may return
  `unit: null`, while the Stage B Android model required a non-null string. C1
  makes only that response field nullable and keeps the server contract/schema
  unchanged. The repaired detail, PDF rendering, restart/session restoration,
  profile switch, and logout still require the new C1 APK on-device check.
- Crossing from the earlier ephemeral GitHub debug signer requires one final
  uninstall/install/enrollment. Later pilot APKs with the same application id
  and pinned signer can update in place and preserve app-private data and the
  AndroidKeyStore session. Uninstall, clear-data, a different device, revocation,
  or session-policy expiry still requires enrollment.

The acceptance verdict therefore remains `runtime_not_proven`: enrollment,
session use, multiple profiles, invoice listing, and contacts now have bounded
single-device evidence, but the repaired detail/PDF and remaining lifecycle
journeys do not. The public endpoint and build configuration do not prove those
missing paths.

## Scope and evidence boundary

Stage B is a first-party, administrator-enrolled Android **read-only** client
over the existing Stage A API. It creates no new OfficeFlow business action,
conversation flow, Telegram FSM, or business mutation. A traditional
Conversation Acceptance Proof is therefore not applicable and no synthetic
Telegram conversation trace is invented.

The repository contains deterministic Android JVM tests, AndroidKeyStore and
entry-surface instrumentation tests, Python backend/security regressions, a
reproducible Gradle wrapper, and a GitHub Actions debug-APK workflow. GitHub
Actions run `32309125355` passed `:app:testDebugUnitTest`,
`:app:lintDebug`, and `:app:assembleDebug`, then uploaded the APK and
checksum as artifact
`officeflow-android-debug-b03b2812eba89f5395bfd35851be5f55b0894052`
(artifact id `9385867828`). The downloaded APK matched its published SHA-256:
`aded96b7cbf7db88c29b9ba771dec112699dd328ffe46478050df5d4561dcc0a`.
The implementation host still has no emulator/device, so the checked-in
instrumentation tests and real app entry journey were not executed. The full
Python suite also has the unchanged clock-sensitive failure recorded below.
This artifact therefore remains `runtime_not_proven` for device runtime and a
fully green repository regression. No production API deployment is required or
claimed.

## Architecture and negative-space evidence

- Android package/application id: `sk.zevsflow.officeflow`; one `:app` module;
  Kotlin, Compose Material 3, ViewModel, Navigation Compose, coroutines,
  kotlinx.serialization, OkHttp, AndroidKeyStore AES/GCM, and `PdfRenderer`.
- `OfficeFlowApiClient` owns all HTTP and contains only the nine approved Stage
  A routes. It sends no principal/Telegram identity claim and has no logging
  interceptor, automatic transport retry, authenticated response cache, or
  business mutation route.
- `SessionCoordinator` serializes refresh with a `Mutex`, adopts an already
  rotated pair, retries a safe original request once, terminalizes definitive
  401, preserves credentials for temporary 423 block, and persists a
  `refreshUncertain` stop state after ambiguous transport failure so the refresh
  credential is never blindly replayed after restart.
- `SecureSessionStore` writes only AES/GCM IV+ciphertext under
  `noBackupFilesDir`, atomically replaces the file, and deletes unusable
  ciphertext/key material. Manifest backup is disabled and extraction rules
  exclude all app domains.
- Workspace selection is a nonsecret local preference and is accepted only
  after the latest `/v1/workspaces` response. Invoice/contact records remain
  memory-only. PDFs are bounded to the Stage A 25 MB ceiling, signature/type
  checked, rendered from app-private cache, and deleted on viewer release/startup.
- The only Python behavior change distinguishes temporary account block as
  bounded HTTP 423 from terminal 401. No Stage A route or schema changed.

## Acceptance scenario matrix

| Scenario | Precondition / exact entry | Authorization and owner | Effect / workspace scope | Response / final state | Evidence | Result |
|---|---|---|---|---|---|---|
| S1 fresh install | no credential blob; launch `MainActivity` | local `SecureSessionStore` -> `OfficeFlowViewModel` | no HTTP/business effect | enrollment UI | `SessionCoordinatorTest.freshInstallRequiresEnrollment`; `EnrollmentScreenSmokeTest` authored, not executed | runtime not proven |
| S2 valid enrollment | valid one-time secret; Connect -> `POST /v1/enrollment/exchange` | Stage A enrollment authority; `SessionRepository` | server auth session only; encrypted pair stored; UI secret cleared | workspace load | `RepositoriesTest.validEnrollmentPersistsOnlyIssuedCredentialPair`; API-client enrollment test | pass (JVM) |
| S3 invalid/expired/replayed enrollment | invalid/consumed code; same POST | Stage A rejects boundedly | no local authenticated state; no secret persistence | Slovak invalid/used/expired state | `OfficeFlowApiClientTest.invalidAndConsumedEnrollmentRemainBoundedFailures`; Stage A HTTP tests | pass |
| S4 restart | valid encrypted blob; app launch -> `GET /v1/session` | `SecureSessionStore`, coordinator, Stage A current auth | no business write | restore/validate then workspace load | secure-store instrumentation authored; JVM persisted-state coordinator coverage | runtime not proven |
| S5 access expiry | safe GET receives 401 | one `SessionCoordinator` -> `POST /v1/session/refresh` | auth-only atomic credential replacement; same scope GET retried once | original read succeeds | `SessionCoordinatorTest.successfulRefreshAtomicallyReplacesCredentialsAndRetriesOnce` | pass |
| S6 concurrent 401 | eight concurrent protected reads | coordinator `Mutex` | exactly one refresh; callers adopt rotated pair | all callers succeed with new token | `concurrent401RequestsHaveOneRefreshOwner`; `requestWaitingForOwnerUsesAlreadyRefreshedToken` | pass |
| S7 definitive revoke | refresh returns terminal 401 | coordinator | local credentials cleared; no stale business cache retained | enrollment required | `definitiveRefresh401ErasesCredentials`; Stage A admin revoke tests | pass |
| S8 transient network | protected transport failure | coordinator | credentials preserved; no loop | bounded retryable failure | coordinator network mapping and `retryOnConnectionFailure(false)` boundary | pass (structural/JVM) |
| S9 ambiguous refresh | refresh request disconnect/lost response | coordinator persisted uncertainty owner | original pair retained with encrypted uncertainty marker; refresh not replayed | recovery guidance/fresh enrollment when access rejected | `ambiguousRefreshIsPersistedAndNeverBlindlyReplayed` | pass |
| S10 one workspace | `/v1/workspaces` returns one | `WorkspaceSelectionPolicy` | local selection only; no server selection call/write | home with selected profile | `WorkspaceSelectionPolicyTest.exactlyOneWorkspaceIsSelectedWithoutRememberedState`; Stage A no-selection-write tests | pass |
| S11 multiple first use | two workspaces, no preference | policy | no read until explicit local choice | picker | `multipleWorkspacesRequireExplicitSelection` | pass |
| S12 remembered valid | remembered id appears in latest list | `WorkspaceRepository` | local reuse only | profile visible on shell/list screens | `rememberedWorkspaceIsAcceptedOnlyAfterLatestListValidation`; UI source boundary | pass |
| S13 stale remembered | remembered id absent | repository/policy | preference cleared; no foreign fallback | explicit picker | `RepositoriesTest.staleRememberedWorkspaceIsClearedAfterAuthoritativeServerList` | pass |
| S14 local workspace change | choose another returned workspace | `WorkspaceRepository.select` | only subsequent GET query `workspace_id` changes; server/Telegram selection untouched | shell shows new profile | workspace policy/API query tests; Python `active_workspace_selection` regression | pass |
| S15 invoice list/pagination | selected workspace; `GET /v1/invoices?limit=50&offset=n` | coordinator -> API client -> Stage A scoped service | read only; pages deduplicate by id; reset on scope change | server facts displayed | protected-route API test; `PAGE_SIZE=50`; ViewModel `distinctBy` boundary | pass (JVM/structural) |
| S16 invoice detail | tap owned invoice; `GET /v1/invoices/{id}` | same auth/scope chain | read only | facts/items, PDF navigation only; no edit/pay/send/delete | API parse/route test; UI negative-space test | pass |
| S17 missing/foreign invoice | scoped detail returns 404 | Stage A tenant boundary | no fallback/alternate search | bounded unavailable state | Stage A isolation tests; `DetailState.Error`; route boundary | pass |
| S18 PDF success | owned invoice; approved PDF GET | coordinator/API client/Stage A PDF owner | app-private temporary file only; no path/share/export | bounded in-app `PdfRenderer`, page navigation, release cleanup | `pdfRequiresCorrectTypeSignatureAndPrivateCallerTarget`; PDF repository/UI source | pass (JVM); renderer runtime not proven |
| S19 PDF invalid/missing | 404, wrong type/signature, >25 MB | API client | partial temp deleted; no regeneration/path guess | bounded unavailable state | `pdfRejectsMissingWrongTypeBadSignatureAndDeclaredOversize`; Stage A PDF tests | pass |
| S20 contacts | selected scope; `GET /v1/contacts` | coordinator/API/Stage A contact projection | memory-only read; exact workspace | Slovak read-only list, no controls | protected-read API test; static UI/route boundary | pass |
| S21 online logout | confirm dialog; `DELETE /v1/session` 204 | `SessionRepository.signOut` | current server session revoked; credential/key and local scope erased | enrollment state | `RepositoriesTest.logoutRevokesWhenPossibleAndAlwaysErasesLocalState`; dialog source | pass (JVM); UI click runtime not proven |
| S22 offline logout | confirm; DELETE disconnects | repository | local erase still completes; no business effect | truthful unconfirmed-server-revoke copy | `offlineLogoutErasesLocallyAndReportsUnconfirmedServerRevoke` | pass |
| S23 lost-device admin revoke | CLI `revoke-session --telegram-id --session-id`; next Android GET/refresh | Stage A CLI/session owner -> terminal 401 | selected auth session only; no business write | Android erases and returns enrollment | Stage A admin-session tests + coordinator definitive-401 test | pass |
| S24 `/vymazat_databazu` | existing confirmed Telegram reset | existing Stage A transactional reset/session owner | old access/refresh/enrollment permanently invalid; business semantics unchanged | fresh enrollment required after later approval | Stage A reset/addendum regression referenced by Stage A acceptance proof | pass (existing Python) |
| S25 block/unblock | administrator temporarily blocks active user | Stage A returns 423 `access_temporarily_unavailable` | credentials/session preserved; reads denied while blocked | blocked UI; same session resumes after approval if otherwise valid | new HTTP 423/401 regression; `temporaryBlockPreservesCredentialPairAndDoesNotRefresh`; existing block/unblock service test | pass |
| S26 app-data reset/uninstall | app storage removed/backup restore attempted | Android OS + manifest/store | no backup-restored credentials | enrollment required | manifest/data-extraction static test; secure-store instrumentation authored | runtime not proven |
| S27 mutation negative space | inspect/call guessed business mutation | Android client has no method/route; Stage A keeps route unavailable | zero business effect | no UI control or network call | `test_android_api_client_contains_only_approved_stage_a_routes`; Android source negative-space; Stage A guessed-route tests | pass |
| S28 accounting-doc negative space | inspect app/navigation/network | no owner exists in Stage B | no route/screen/cache | unavailable/deferred | Android static boundary and exact-route test | pass |
| S29 Telegram regression | API/app absent or stopped; existing bot tests | existing Telegram owners | unchanged FSM/actions/selection/business effects | current Telegram journeys remain | full suite: 2612 passed + 7 subtests; one unchanged clock-sensitive work-time test failed because environment time was earlier than its fixed 07:00 open time | runtime not proven (unrelated full-suite failure) |
| S30 Product Truth/InfoHelp | ask Android capability/how-to | Product Truth + Slovak deterministic renderer | answer only; zero auth/business writes | partial/read-only/admin/setup; live endpoint not deployed | Product Truth/InfoHelp tests and DB no-effect test | pass |

## Current final state

- Implemented: Android source, secure session owner, local workspace policy,
  read-only screens/repositories, tests, wrapper, CI workflow, Product Truth and
  Slovak InfoHelp synchronization.
- Not implemented: any Android business mutation, assistant/voice/FSM,
  accounting-document screen, upload, background sync, offline canonical
  business mirror, public signup, or new backend business route.
- Production migration: **NO**. Deployment/public API exposure/server changes:
  **NO**. Play Store/release signing: **NO**.
- Telegram remains the current production end-user runtime.

Final acceptance remains `runtime_not_proven` until at least the real
entry/AndroidKeyStore instrumentation journey executes in an Android-capable
environment and the repository full-suite evidence is green or the unchanged
clock-sensitive baseline test is separately resolved. The debug build, JVM
suite, lint, APK checksum, and artifact path are proven by GitHub Actions run
`32309125355`; device behavior must not be inferred from those host-side
checks alone.

Python evidence on this checkpoint: focused Stage B/shared-boundary suite
`95 passed`; full repository suite `2612 passed, 7 subtests passed, 1 failed`.
The sole failure is unchanged
`tests/test_work_time_routing.py::test_explicit_close_now_closes_open_day`: it
opens a fixed 2026-07-03 day at 07:00 and invokes the real clock's "close now"
while the execution environment is earlier than 07:00, so the existing work-time
owner correctly refuses an end-before-start. It reproduced in isolation and no
work-time/FSM file was modified. `python -m compileall -q bot` and
`git diff --check` passed.
