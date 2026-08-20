# OfficeFlow Android read-only shell (Stage B)

This directory contains the single-module Kotlin/Jetpack Compose Android client
approved by
`docs/architecture/OFFICEFLOW_ANDROID_READ_ONLY_SHELL_V1_ARCHITECTURE_DESIGN_PROOF.md`.
It is a thin, read-only client over the Stage A OfficeFlow API. It is not a
second FakturaBot implementation and contains no invoice/contact mutations,
assistant, voice, upload, background synchronization, or offline business
database.

## Toolchain

- JDK 17
- Android SDK Platform 35 and Build Tools 35.x
- Gradle 8.10.2 via the checked-in wrapper
- minSdk 26; compileSdk/targetSdk 35

The minSdk is a Stage B technical choice, not a final Product Truth support
matrix.

## Build and tests

Linux/macOS:

```bash
cd android
./gradlew :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

Windows PowerShell:

```powershell
cd android
.\gradlew.bat :app:testDebugUnitTest :app:lintDebug :app:assembleDebug
```

With an emulator/device connected, run the AndroidKeyStore and entry-surface
instrumentation tests:

```bash
./gradlew :app:connectedDebugAndroidTest
```

The debug APK is written to:

`app/build/outputs/apk/debug/app-debug.apk`

## API endpoint configuration

Debug builds default to the Android emulator loopback endpoint
`http://10.0.2.2:8081`. The only debug cleartext exception is that exact host.
An HTTPS development endpoint can be supplied without changing source:

```bash
./gradlew :app:assembleDebug \
  -POFFICEFLOW_DEBUG_API_BASE_URL=https://approved-test-api.example
```

The GitHub Actions `workflow_dispatch` input `api_base_url` is optional. When it
is supplied, the workflow accepts only the separately approved OfficeFlow pilot
HTTPS endpoint, passes it through `OFFICEFLOW_DEBUG_API_BASE_URL`, and verifies
the generated debug `BuildConfig` before uploading an
`officeflow-android-pilot-<GITHUB_SHA>` artifact. Pull-request builds retain the
emulator default.

Release builds have no source-controlled production hostname and fail unless an
HTTPS endpoint is explicitly supplied at build time:

```bash
./gradlew :app:assembleRelease \
  -POFFICEFLOW_API_BASE_URL=https://approved-pilot-api.example
```

The URL is public build configuration, never an API secret. Enrollment codes,
access tokens, refresh tokens, signing keys, production host secrets, and other
credentials must never be committed or passed as ordinary Gradle properties.

## Current rollout truth

A dedicated public HTTPS boundary for the controlled OfficeFlow Android pilot
has been deployed and proven separately from Stage B. No pilot hostname is
committed into Android application source. Administrator enrollment,
authenticated session use, multiple profiles, invoice listing, and contacts
were proven on one authorized Samsung pilot device. The C1 Home build and
nullable invoice-detail repair still require a new APK/device check; detail/PDF,
restart restoration, profile switching, and logout are not yet proven after C1.
Telegram remains the runtime for business actions not supported on Android.

C1 starts at `Domov`, shows exactly the six approved business domains, and keeps
`Hlas / Chat` separate. Only `Faktúry -> Existujúce faktúry` and
`Kontakty -> Existujúce kontakty` are network-capable. Other domain actions are
truthful local unavailable states with no hidden network or business effect.

The app calls only the nine approved Stage A routes for enrollment, session
refresh/revoke/status, workspace listing, outgoing invoice list/detail/PDF, and
contact listing. Workspace choice is local UI state only and never changes the
server or Telegram `active_workspace_selection`.
