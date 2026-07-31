# Gmail OAuth and statement collector V1 — conversation acceptance proof

Date: 2026-07-30

Verdict: `runtime_not_proven`.

Reason: local deterministic implementation and focused tests exist, but no
production callback deployment, real Google OAuth consent, restricted-scope
verification, or real Gmail collection smoke has been performed.

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
| Correct admin starts connection | Short-lived state and nonce; only hashes persisted; Gmail readonly scope only | integration service tests | passed |
| Callback has wrong/expired/reused state | No token persistence or binding activation | callback/service tests | passed |
| Callback identity or email does not match | No binding activation | OAuth/service tests | passed |
| Callback includes Drive or other scope | Flow rejected | allowed-scope validation test | passed |
| Provider returns 401/403 while collecting | Binding/grant become `needs_reauth`; no file deletion | service/runtime implementation | focused persistence test added; scheduler integration smoke pending |
| Message contains ordinary text body | Body ignored; only filename-bearing allowlisted candidates | adapter tests | passed |
| First valid statement attachment | Workspace-local atomic original + metadata, `parse_status=deferred` | collector tests | passed |
| Same Gmail source repeats | No second download/store | collector/service source dedup | passed locally |
| Same bytes arrive from another source | No second original; separate metadata references canonical original | collector tests | passed |
| One malformed attachment among valid messages | Failure isolated; scheduler continues | collector implementation | local unit coverage partial |
| `/gmail_status` | Bounded lifecycle summary; no token/path/message identifiers | handler implementation | handler smoke pending |
| `/gmail_disconnect` | Grant unusable; collected files preserved | integration service test | passed |
| User asks whether Gmail statements are parsed | Product Truth says collection is partial and parsing/reconciliation is absent | Product Truth/InfoHelp tests | added |
| Existing Google Drive archive | No schema, token, scope, or runtime reuse | additive schema test and separate config/services | passed locally |
| Public site indexing | Remains enabled; OAuth has independent launch gate | user decision and site config unchanged | verified by diff review |

## Required real-environment smoke before launch

1. Deploy both callback surfaces with secrets supplied outside git.
2. Confirm the callback headers and browser response contain no OAuth secrets.
3. Complete Google verification for `gmail.readonly`.
4. Connect the exact configured account in the exact workspace.
5. Run first-lookback, overlap, retry, duplicate, revoked-token, and restart
   scenarios against a controlled mailbox.
6. Confirm no Gmail send/modify/delete endpoint and no Drive scope is
   authorized.
7. Confirm backup, disconnect, provider revocation, and rollback procedures.

Until all seven checks pass, capability status remains `partial`,
`requires_setup`, `requires_admin`, and `requires_external_credentials`.
