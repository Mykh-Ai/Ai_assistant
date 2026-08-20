# OfficeFlow Android Home Top-Level Navigation V2 — C1 Acceptance Proof

Date: 2026-08-20

Approved design:
`docs/architecture/OFFICEFLOW_ANDROID_HOME_TOP_LEVEL_NAVIGATION_V2_ARCHITECTURE_DESIGN_PROOF.md`

Overall verdict: `runtime_not_proven`

## Scope and evidence boundary

C1 is a bounded Android shell/navigation, responsive-layout, invoice-detail,
and existing-PDF compatibility repair. It adds no API route, schema change,
business mutation, Telegram/FSM behavior, STT/LLM/LMM call, production server
deployment, Cloudflare change, or enrollment issuance. The Stage A session and
`workspace_id` tenant boundary remain authoritative.

The current code evidence proves the navigation model, response decoding,
bounded error classification, workspace-scoped retry URL, and Android source
compilation. Authored Compose instrumentation covers 2.0 font scale, long profile
text, scrolling to the final Home control, and a production-shaped detail with a
nullable item unit. Those device tests are not claimed as executed locally
without an attached emulator/device.

## Concrete invoice-detail diagnosis

Production storage and the Stage A projection permit `invoice_item.unit` to be
null for legacy rows. The Android Stage B `InvoiceItem.unit: String` decoder
rejected a valid production-shaped response before UI rendering. C1 changes the
Android field to `String? = null`, renders a bounded `jednotka neuvedená`
fallback, and adds a sanitized `unit: null` API fixture. No server response,
database row, route, or fallback tenant lookup is changed.

Detail failures are now separated into not-available, network, protocol, and
unexpected classes with safe Slovak text. Retry repeats the same explicit
`workspace_id`; it does not search another profile or clear the session.

## Concrete real-device PDF diagnosis

The authorized Samsung reached invoice detail and then sent the expected
workspace-scoped `GET /v1/invoices/{id}/pdf` request. The production API access
log records an actual `404` for that request. Read-only server inspection proved
that the persisted file exists, is visible inside both the Telegram and API
containers through the same storage mount, is within the 25 MB bound, and has a
valid `%PDF-` signature. Database integrity is `ok`.

The failing row uses the historical numeric owner directory. The actor now has
two workspaces, so the Stage A resolver rejected every numeric-owner PDF even
though the tested invoice number and persisted pointer each occur exactly once
and belong to the requested workspace. The repair narrows the compatibility
rule to that specific file: unique persisted row + workspace + invoice number +
filename + pointer may stream; a duplicate invoice number, shared pointer,
flat/arbitrary path, or foreign workspace still fails closed. No PDF is moved,
rewritten, regenerated, or exposed.

Android keeps the 25 MB, `application/pdf`, `%PDF-`, app-private temporary-file,
and cleanup gates. Its PDF UI now distinguishes not available, network failure,
invalid PDF response, and local rendering failure with sanitized messages.

## Acceptance scenario matrix

| # | Scenario | Evidence | Result |
|---|---|---|---|
| 1 | Valid stored session resolves to Home instead of invoice list | `NavHost.startDestination = HOME_ROUTE`; navigation unit test; Samsung observation | pass (code/JVM/device) |
| 2 | Multiple workspaces require choice, then Home | existing workspace policy plus `RootState.Ready` shell start; Samsung profile switch | pass (existing JVM/code/device) |
| 3 | Home has exactly six approved domains | `C1_BUSINESS_DOMAINS`; exact-order unit test | pass (JVM) |
| 4 | `Hlas / Chat` is separate and has zero functional channel effect | separate local unavailable route; no permission/STT/LLM owner | pass (code/structural) |
| 5 | No Android `Doklady` or `Bločky/Doklady` domain | exact-label unit/structural assertion | pass (JVM/structural) |
| 6 | Faktúry has the five frozen sublevels; only existing reads execute | navigation model availability assertion | pass (JVM) |
| 7 | Home -> Faktúry -> list -> detail -> PDF and natural back chain | Compose Navigation routes/back callbacks; Samsung; production API log | list/detail pass on device; PDF returned 404; repaired build/deploy/re-test pending |
| 8 | Production-shaped nullable-unit detail decodes and renders safely | sanitized MockWebServer fixture; nullable model; Samsung observation | pass (JVM/code/device) |
| 9 | Kontakty has exactly two frozen sublevels; only existing list executes | navigation model/availability assertion; Samsung observation | pass (JVM/device) |
| 10 | Both Bločky actions are local unavailable states | `C1Availability.UNAVAILABLE`; no API binding; Samsung observation | pass (JVM/structural/device) |
| 11 | All six work-time actions are local unavailable states | exact-label test; no API binding; Samsung observation | pass (JVM/structural/device) |
| 12 | Both analytics actions are local unavailable states | navigation model; no analytics owner call; Samsung observation | pass (structural/device) |
| 13 | InfoHelp is present but conversation execution is unavailable | empty sublevel model -> bounded local screen; Samsung observation | pass (code/device) |
| 14 | Profile switch clears business state and returns through fresh Home shell | existing `chooseWorkspace -> clearBusinessState`; fresh `ReadShell` Home start; Samsung observation | pass (code/device) |
| 15 | Restart validates session/workspace then opens Home | existing initialize path plus Home start destination | pass (code); device pending |
| 16 | Large font/long profile remains scrollable and final controls reachable | `ResponsiveC1SmokeTest` at 1.3, 1.5, and 2.0 font scale | authored; device runtime pending |
| 17 | Long invoice/contact/value text does not use competing fixed row columns | column-based label/value/contact layouts; scroll containers | pass (code); device runtime pending |
| 18 | Existing contact read route and explicit workspace scope remain unchanged | API-client protected-read test | pass (JVM) |
| 19 | Sign-out confirmation/repository semantics remain unchanged | existing dialog and repository tests | pass (existing JVM); UI click pending |
| 20 | Telegram journeys remain unchanged | no Telegram handler/FSM/runtime source touched; full Python regression | pass |
| 21 | Product Truth stays `partial` and distinguishes proven/pending paths | registry, Slovak InfoHelp, no-effect tests, focused/full Python regression | pass |
| 22 | No new route/schema/production/Cloudflare/enrollment/AI/mutation effect | exact-route boundary; read-only resolver regression; production unchanged | pass (structural); backend deployment required before PDF re-test |

## Current truth and next acceptance gate

Current bounded real-phone evidence proves Home, authenticated session use,
invoice listing, repaired invoice detail, profile switching, contacts, and the
expected unavailable behavior of unsupported domains on one authorized Samsung
device. It also proves that the current deployed backend returns `404` for the
tested existing legacy PDF. This evidence does not yet prove PDF success.

Final acceptance remains `runtime_not_proven` until the newly built C1 APK is
installed on the authorized pilot device after the separately approved backend
deployment and scenario 7 PDF success plus the still-pending restart, large
font/long text, complete back chain, and logout checks are exercised. Presence
of unavailable Home domains must not be interpreted as functional Android
parity.

The C1 pilot packaging now uses one pinned controlled-pilot signing certificate
instead of the GitHub runner's per-build debug certificate. The public
certificate SHA-256 is
`3835035c2df22b22406a00c359cc1a03e54f61852c302ed7c6392702a9d8e6fe`.
One final uninstall/install/enrollment is required to cross from the previous
ephemeral signer; subsequent same-signer APK updates preserve app-private data
and the AndroidKeyStore session. This fixes update continuity only and does not
prove any pending C1 device scenario.

## Validation checkpoint

- C1 PDF repair focused API suite: `20 passed`.
- C1 PDF repair full repository regression: `2617 passed, 7 subtests passed`.
- C1 PDF repair `python -m compileall -q bot` and `git diff --check`: pass.
- C1 PDF repair PR run `32395879671`: JDK 17 Android JVM tests, lint, and
  debug assembly pass.
- C1 PDF repair stable-pilot run `32396113507` on exact code/workflow SHA
  `4b4d249859865c6ab85344a31e7757bb6e7e28e7`: JVM tests, lint, stable-signed
  assembly, exact HTTPS endpoint proof, pinned-certificate proof, checksum,
  artifact upload, and signing-key cleanup pass. Artifact id `9416786993` has
  APK SHA-256
  `8c41ceef7fd9ee2e641433fca80be82400f6fa3957dc9de7ced16cdbab3717b8` and
  certificate SHA-256
  `3835035c2df22b22406a00c359cc1a03e54f61852c302ed7c6392702a9d8e6fe`.
- Android main, JVM-test, and instrumentation-test source compilation: pass.
- `:app:testDebugUnitTest :app:lintDebug :app:assembleDebug`: pass.
- Focused Product Truth/API/Android boundary regression: `45 passed`.
- Full repository regression: `2617 passed, 7 subtests passed`.
- `python -m compileall -q bot`: pass.
- `git diff --check`: pass.
- Stable-signed local pilot assembly and `apksigner` certificate pin: pass.
- GitHub stable-signed pilot run `32385806345` on exact code/workflow SHA
  `a19b45f7aa01d288410580b94a88202a09545c03`: pass. Downloaded artifact id
  `9412994306` matched APK SHA-256
  `52c8fd682d6f6696637df58937a0dc05c5e2a742f7db68249260e733699f818a`,
  the approved endpoint evidence, and the pinned signer under independent local
  verification.

The host-built debug APK is build evidence only. Compose instrumentation remains
authored for 1.3/1.5/2.0 font scale and long profile/contact/detail content, but
not executed because no emulator/device is attached to the local build host.
