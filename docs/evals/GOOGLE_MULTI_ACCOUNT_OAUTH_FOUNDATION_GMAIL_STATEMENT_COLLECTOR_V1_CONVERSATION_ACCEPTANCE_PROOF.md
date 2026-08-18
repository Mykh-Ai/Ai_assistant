# Gmail OAuth and statement collector V1 — conversation acceptance proof

Date: 2026-07-30

Verdict: `partial`; controlled OAuth/callback and first collection are
`runtime_proven` for the configured pilot.

Reason: the production callback, real Google consent, connected grant, one
bounded Gmail query, one atomic workspace-local statement import, and a second
tick with no new import have succeeded. Broader launch evidence remains
incomplete: Google restricted-scope verification evidence, source-repeat
redownload dedup under an overlapping query, and revoke/disconnect recovery.
The separate owner Drive reauthorization and queued statement upload succeeded.

## Maturity

- Product Truth / InfoHelp: Level 2, bounded capability-aware guidance.
- OAuth and collection side effects: deterministic Python services.
- Statement interpretation: not implemented (`parse_status=deferred`).
- Self-learning: not applicable; no email content or statement pattern is
  learned.

## Acceptance matrix

| Journey | Expected result | Evidence | Status |
|---|---|---|---|
| Unauthorized user sends `/gmail_connect` | No OAuth state, token, workspace data, file, or external call | existing authorization middleware plus admin/workspace checks | locally covered by architecture; handler smoke pending |
| Authorized non-admin sends `/gmail_connect` | Honest admin-only rejection; no OAuth state | `bot/handlers/gmail_settings.py` | locally implemented |
| Admin in wrong workspace sends `/gmail_connect` | Fail closed before OAuth state creation | exact workspace membership check | locally implemented |
| Correct admin starts connection | Short-lived state and nonce; only hashes persisted; Gmail readonly scope only | integration tests plus controlled production consent | passed |
| Callback has wrong/expired/reused state | No token persistence or binding activation | callback/service tests | passed |
| Callback identity or email does not match | No binding activation | OAuth/service tests | passed |
| Callback includes Drive or other scope | Flow rejected | allowed-scope validation test | passed |
| Provider returns Gmail 401/403 or refresh `invalid_grant` while collecting | Binding/grant become `needs_reauth`; one cooldown-protected admin notice; normal scheduler sleep; no file deletion, raw provider diagnostic, or tight loop | transport/service/runtime implementation | focused classification, tick-signal, notification and sleep tests passed; production status transition passed; post-reauthorization tick pending |
| Message contains ordinary text body | Body ignored; only filename-bearing allowlisted candidates | adapter tests | passed |
| First valid statement attachment | Workspace-local atomic original + metadata, `parse_status=deferred` | collector tests plus controlled production tick | passed |
| Same Gmail source repeats | No second download/store | collector/service source dedup | passed locally |
| Same bytes arrive from another source | No second original; separate metadata references canonical original | collector tests | passed |
| One malformed attachment among valid messages | Failure isolated; scheduler continues | collector implementation | local unit coverage partial |
| `/gmail_status` | Bounded lifecycle summary; no token/path/message identifiers | handler implementation plus controlled production output | passed |
| `/gmail_disconnect` | Grant unusable; collected files preserved | integration service test | passed |
| User asks whether Gmail statements are parsed | Product Truth says collection is partial and parsing/reconciliation is absent; static guidance does not invent live account state | Product Truth/InfoHelp regression tests | passed |
| User asks whether Drive archive is configured | Product Truth remains partial and directs to `/google_drive_status`; external-credential dependency is not rendered as a false unconfigured-account claim | Product Truth/InfoHelp regression tests | passed |
| Existing Google Drive archive | Separate grant/job path; Gmail local import survives Drive failure | production owner OAuth reauthorization plus bank-statement job/archive state `uploaded` | passed for controlled statement |
| Public site indexing | Remains enabled; OAuth has independent launch gate | user decision and site config unchanged | verified by diff review |

## Remaining real-environment smoke before wider launch

Completed in the controlled pilot:

1. deployed public callback and signed relay with no-store/no-referrer/noindex;
2. real configured-admin Google consent and encrypted connected grant;
3. one bounded Gmail query with one stored workspace-local original and
   metadata, `parse_status=deferred`, zero rejected, and zero failed;
4. a second tick with no additional import;
5. backup, owner Drive reauthorization, encrypted connected grant, and
   queued bank-statement job/archive state reaching `uploaded` while the local
   import remains preserved.

Still required:

1. retain evidence of Google restricted-scope verification/security review
   appropriate to the rollout;
2. exercise an overlapping repeated-source tick that re-sees the same Gmail
   source and proves no second download/store;
3. exercise revoked-token and `/gmail_disconnect` recovery while preserving
   the imported original;
4. verify restart/integrity and rollback procedures against the controlled
   imported record.

Capability status remains `partial`, `requires_setup`, `requires_admin`, and
`requires_external_credentials` outside the configured pilot.
