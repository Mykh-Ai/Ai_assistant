# 2026-08-04 - Exact unsupported InfoHelp admin-review buttons

- Preflight classified the existing behavior as `partial`: Contextual InfoHelp
  truthfully offered an administrator-review request and the confirmation-gated
  Level 3 customization flow already existed, but the offer exposed no action.
- Touched scopes: Contextual InfoHelp handoff, one bounded FSM choice, Telegram
  inline callbacks/cleanup, active-FSM navigation, tests, and active contracts.
  No canonical top-level action, Product Truth capability/status, STT/LMM
  business path, DB schema, persisted row, storage, access rule, invoice/receipt
  operation, PDF, `.env`, or server runtime changed.
- Exact unsupported results now show `Požiadať správcu` and `Hlavné menu`.
  Admin review opens the existing `Schváliť / Upraviť / Zrušiť` preview; no
  request is saved until that separate approval. Main menu reuses `cmd_menu()`
  and saves nothing.
- Callback identity remains `callback.from_user`, authorization remains in the
  shared outer middleware, and FSM draft ownership is revalidated before the
  preview. Wrong-state/foreign callbacks cannot edit unproven markup. Owned
  handled/stale/expired callbacks and active `/menu`, `/cancel`, `/start`, and
  timeout exits remove the offer keyboard; cleanup failure is logged without
  rolling back a safe route.
- AI maturity remains the existing partial Level 3 request-capture slice. No
  self-learning hook applies because no semantic alias or confirmed product
  behavior is learned.
- Focused routing/callback/FSM verification: `53 passed`. Expanded neighboring
  InfoHelp/voice/customization/confirmation verification: `291 passed, 7
  subtests passed`; after the final message-ownership assertion was added, the
  final code's complete repository regression passed: `2486 passed, 7 subtests
  passed in 465.19s`.
- Published runtime commit `feda8fb04290f050e8b6657c7397662e2041f011`
  through PR `#83`; GitHub reported no configured commit statuses and merged
  the exact tested head into `main` as
  `0ab1197fa90e3e24d63cee89dd57290a93f4d7c5`.
- Production `/bot/repo` was clean before deployment and fast-forwarded from
  `fd1e60a` to exact merge SHA `0ab1197`. The production compose image rebuilt
  successfully; `fakturabot` and `fakturabot-cloudflared` are `Up`, bot restart
  count is `0`, startup schedulers loaded, Telegram polling is active, no
  polling conflict was observed, and in-container `compileall` passed. `.env`,
  DB/storage, and unrelated server projects were not changed.
- Live Telegram button interaction remains pending; current status is
  `deployed_pending_live_smoke`.
- Conversation proof:
  `docs/evals/info_help_admin_offer_buttons_conversation_acceptance_2026_08_04.md`.

# 2026-08-04 - Supported canonical actions bypass the second InfoHelp veto

- Read-only audit on `origin/main` `9e9e9022c2fe274c01a0c46a1624a096c0d41e03`
  confirmed that `delete_existing_invoice` is implemented, Product Truth
  `supported`, registered with an existing runtime owner, tenant-scoped lookup,
  reference continuation, and shared `yes_no` confirmation. The only production
  call to `should_run_contextual_info_help()` was in `process_invoice_text`.
- Root causes were the shared predicate treating every `mutating`/`destructive`
  action as requiring a second LLM and separately treating a missing invoice
  reference as requiring that call. The secondary destructive confidence gate
  (`0.98`) could therefore block a correct primary action and its native
  continuation.
- The shared predicate now routes a registered Product-Truth-supported action
  with a real runtime owner directly after excluding questions,
  correction/negation, commands, `unknown`, unsupported/non-eligible, and
  unresolved cases. Mutation class alone is no longer a trigger. Owner-handled
  missing slots are not reclassified.
- `delete_existing_invoice` with reference `10` reaches the existing owner
  exactly once and enters
  `InvoiceStates.waiting_delete_existing_invoice_confirm`; without a reference
  it enters `InvoiceReferenceContinuationStates.waiting_reference`. Text and
  voice transcripts converge. The InfoHelp resolver is not called, so its
  `0.98`/other confidence thresholds are unreachable on this direct route.
- No canonical action, FSM state, confirmation, DecisionResolver family,
  callback, button, keyboard, deletion service, lookup rule, authorization,
  tenant scope, schema, storage, `.env`, or self-learning behavior changed. AI
  maturity remains partial Level 2; this is a Class 5 deterministic routing
  correction.
- Regression-first evidence on old code: `4 failed, 22 passed`. Corrected
  narrow suite: `26 passed in 5.89s`. Expanded invoice/InfoHelp/voice/FSM/
  Product Truth/DecisionResolver suite: `1086 passed in 87.99s`. Full
  repository regression: `2476 passed, 7 subtests passed in 457.79s`.
- Architecture proof:
  `docs/architecture/info_help_supported_action_direct_routing_architecture_design_proof.md`.
  Conversation proof:
  `docs/evals/info_help_supported_action_direct_routing_conversation_acceptance_proof.md`.
- Delivered as commit `2d5967b1036adb47f0089bc21351ee8d497c0dbb`
  through PR `#82`; merge/deployed main SHA is
  `fd1e60ac7e185733d0c01957e579ccae0e27b47a`. The production container was
  running with restart count `0`, active polling, and no polling conflict.
- Live Telegram `Видалити фактуру 10` reached the existing confirmation for
  `20260010`, proving the direct route. That invoice was subsequently deleted
  after an affirmative choice, so it is not negative-smoke evidence and is not
  claimed as such.
- Live missing-slot `Видалити фактуру` followed by `9` reached confirmation for
  `20260009`; the user chose the negative path, received
  `Vymazanie faktúry bolo zrušené.`, and a read-only production check proved
  invoice `20260009` remained present. This is the valid no-deletion smoke.

# 2026-08-02 - Gmail/Drive Product Truth and InfoHelp synchronized

- `README.md`, `docs/TZ_FakturaBot.md`, Product Truth, InfoHelp, the Gmail
  setup runbook, canonical architecture proof, and conversation acceptance
  proof now describe the controlled production pilot as connected/runtime
  proven while preserving the global `partial` owner-only classification.
- Fixed a Product Truth rendering mismatch: `requires_external_credentials`
  describes a capability dependency and no longer becomes the unsupported
  claim that the current Gmail/Drive account is unconfigured. Without observed
  account context, static Gmail/Drive InfoHelp omits live account status and
  directs users to `/gmail_status` or `/google_drive_status`.
- Runtime scope is read-only guidance only: no OAuth scopes, FSM, tokens, DB
  schema/data, archive jobs, files, or server configuration changed. AI
  maturity remains partial Level 2 InfoHelp; no self-learning hook applies.
- The authoritative Drive archive job/state already reports the controlled
  statement as `uploaded`. The enqueue-era Gmail import `archive_status`
  consistency gap remains explicitly out of scope and requires a separate
  migration-safe audit before any persisted-data repair.
- Before integrating concurrent main PR #77, focused Product Truth/InfoHelp:
  131 passed; full suite: 2469 passed, 7 subtests passed. After integration,
  Product Truth, InfoHelp, and Contextual InfoHelp V2: 145 passed.

# 2026-08-02 - Owner Google Drive reauthorized and Gmail statement archived

- After the deterministic `/google_drive_connect` route was restored, the
  configured administrator completed the existing manual owner OAuth bootstrap
  through the registered localhost callback on the desktop computer.
- Before the token write, an online SQLite backup passed `PRAGMA quick_check` and
  was retained with mode `0600`. The one-time OAuth state became `consumed`; the
  refresh token was encrypted with the configured token crypto provider, and the
  owner connection became `connected` with its configured root folder.
- The existing `bank_statement_original` job completed on its scheduled final
  retry. Both `archive_jobs` and `accounting_document_archive_state` report one
  `uploaded` bank-statement record; the workspace-local Gmail original remains
  authoritative with `parse_status=deferred`.
- The collector's enqueue-era `gmail_statement_imports.archive_status` remains
  `archive_pending`; completed Drive state is currently owned by the archive job
  and accounting archive-state tables. This stale summary field is an explicit
  follow-up consistency gap, not evidence that upload is still pending.
- OAuth code/state capture and all temporary audit/helper files were deleted from
  the desktop, VPS `/tmp`, and container after the successful exchange. No token,
  account address, provider identifier, Drive file id, or folder id was recorded
  in repository documentation.

# 2026-08-02 - Google settings commands restored ahead of slash fallback

- Production evidence showed exact `/google_drive_connect` was consumed by the
  invoice router's unknown-slash catch-all, which triggered the LLM/InfoHelp path
  instead of the existing deterministic admin command handler.
- Router order now places `gmail_settings` and `settings` before `invoice`, so
  known Google setup/status commands reach their Python owners while genuinely
  unknown slash commands still retain the bounded fallback.
- Added a regression assertion for both Google settings routers. Focused Drive
  and Gmail settings tests passed. No FSM, DB schema/data, OAuth scope, token,
  Product Truth, self-learning, or capability-maturity change was made.

# 2026-08-02 - Contextual InfoHelp V2 production fail-closed smoke repair

- PR #70 was merged at `e9b94b4`, deployed disabled-first, and then enabled
  only for the configured administrator with
  `INFOHELP_CONTEXTUAL_V2_ROLLOUT=admin_pilot`.
- Before deployment, the production SQLite database and environment file were
  backed up under a mode-0600 scoped backup. Database `PRAGMA quick_check`
  remained `ok`, with three suppliers and eleven invoices before and after the
  deploy and smoke attempt.
- The first live bounded-LLM smoke case, a Ukrainian receipt-deletion
  capability question, failed closed to `unknown`: the model copied prose from
  the output description into an enum and followed an incorrect primary
  invoice diagnostic. No Telegram action, business handler, database write,
  file write, callback, or other business side effect was executed.
- The rollout was immediately restored to `disabled` and the bot was recreated
  healthy. This is a smoke-detected contract defect, not accepted production
  behavior.
- The repair supplies literal allowed values for every bounded enum/list,
  labels the primary resolver result as untrusted diagnostic context, and adds
  receipt/invoice negative-space examples. Python validation, Product Truth,
  action eligibility, tenant/FSM/confirmation gates, and fail-closed behavior
  remain authoritative.
- The first repaired batch proved receipt capability/action/correction and the
  incomplete invoice-delete case, then failed closed because the model dropped
  an explicit numeric invoice reference (`10`). Each attempt restored rollout
  to `disabled`; database integrity and row counts remained unchanged.
- The follow-up contract makes exact reference-token copying explicit and adds
  paired missing-reference/present-reference examples. Python still validates
  and owns the continuation/action boundary; no reference is invented.
- The next throttled server batch proved cases 1-10, including the numeric
  invoice reference and canonical `/contact` create semantics, then failed
  closed because the LLM did not echo an already Python-proven Telegram reply
  relationship. Rollout again returned to `disabled`; DB integrity/counts were
  unchanged. Python now preserves proven same-bot reply ownership and a proven
  `active_fsm_help` descriptor in the validated result instead of asking the
  model to rediscover those transport/runtime facts.
- The combined final-SHA server batch then passed cases 1-20 with no DB write
  or Telegram business effect. A post-smoke qualitative audit found two weak
  assertions: a proven reply could still be hidden by the generic unclear
  branch, and a vague destructive word could inherit a different exact action
  from the model. The final safety repair handles proven quoted replies before
  generic unclear fallback and rejects a primary/exact action mismatch unless
  the bounded result explicitly marks a correction. The pilot was disabled
  again before this repair deployment.
- Final repair PR #79 merged at `4de87cb` and was deployed disabled-first as
  image `sha256:a50580724bd243d6a5fa9d2806fdef30a1474aebe7d11d0602da9977b385cfc6`.
  Startup/polling logs were healthy before `admin_pilot` was restored.
- Combined throttled server evidence covers all 20 planned bounded-LLM and
  deterministic cases. After the qualitative repairs, targeted real-handler
  smoke additionally proved that a quoted bot reply produces a useful no-effect
  explanation and vague `видалити` creates no invoice continuation or dispatch.
  The smoke executed no Telegram business effect and no DB write.
- Final repository verification was `162 passed` focused and `2473 passed, 7
  subtests passed` full, with compileall and diff checks green. Production DB
  remained `quick_check=ok`, with three suppliers and eleven invoices; the bot
  and cloudflared containers are running. Rollout remains scoped to
  `admin_pilot`, not general availability.
- Real Telegram transport/UI interaction by the configured administrator is
  still a separate acceptance item; server harness evidence must not be called
  a human Telegram journey.
- Touched scopes: Contextual InfoHelp LLM payload/prompt, focused tests,
  orchestration/InfoHelp/evaluation docs, project log, deployment rollout.
  No schema, migration, storage layout, access, PDF, STT/LMM, self-learning, or
  persisted business-data change.

# 2026-08-02 - Controlled Gmail consent and first statement import proven

- A real configured-admin `/gmail_connect` completed after PR #71 and the
  production backend accepted Google canonical OIDC scope aliases while still
  requiring exact `gmail.readonly`. One encrypted grant is `connected` and one
  workspace Gmail binding is `active`; no provider identifiers or secrets were
  recorded in docs.
- Before the first collection write, a SQLite online backup passed
  `PRAGMA quick_check` and was retained with mode `0600`.
- The controlled first manual scheduler tick used the configured bounded query,
  saw one message, stored one workspace-local original/metadata pair, set
  `parse_status=deferred`, and reported `rejected=0` and `failed=0`. A second
  tick produced no new import; explicit overlap-based source redownload dedup
  remains a separate acceptance gate.
- The Gmail binding now has a successful check timestamp and no error. No Gmail
  mutation, body retention, parsing, OCR, LLM call, reconciliation, accounting
  row, or automatic invoice state change occurred.
- The separate owner Google Drive connection is `needs_reauth`. The idempotent
  bank-statement archive job entered `retry_wait` with the safe
  `google_drive_not_configured` code; the local Gmail import remains stored and
  authoritative. Drive reauthorization and uploaded-state evidence remain open.
- Product status advances from external `runtime_not_proven` to controlled
  `partial_runtime_proven` for the configured pilot. It remains `partial`,
  `requires_setup`, `requires_admin`, and `requires_external_credentials`
  outside that pilot.

# 2026-08-02 - Gmail OAuth canonical OIDC scope alias repair

- A controlled real `/gmail_connect` callback reached the production backend,
  consumed its one-time state, and failed before grant persistence with the safe
  code `oauth_scope_missing`; no grant, binding, Gmail call, import, or mailbox
  mutation was created.
- Root cause: the Gmail integration required literal `email` and `profile`
  values even though Google may return their canonical `userinfo.email` and
  `userinfo.profile` scope aliases. The older Drive token boundary already
  handled these official equivalents.
- Scope validation now accepts only those two official OIDC aliases, persists
  the actual provider-returned scope values, still requires exact
  `gmail.readonly`, and continues to reject broader Google API scopes.
- Touched scopes: deterministic OAuth grant validation, focused regression
  tests, Gmail architecture proof, project log, and changelog. No schema,
  migration, storage layout, LLM/STT/LMM/FSM, Product Truth claim, collector,
  Gmail mutation, or existing persisted business data changes.
- Status remains `partial`, `requires_admin`, and
  `requires_external_credentials` until a new production consent completes and
  one bounded statement import is verified.
# 2026-08-02 - Gmail signed callback relay merged and production-smoked

- Backend PR #68 merged to main at 27d7367 and was fast-forwarded to
  /bot/repo. Companion zevsflow-site PR #9 merged at 9eba5f3; GitHub CI
  completed successfully.
- Before backend deployment, a SQLite online backup was created at the scoped
  production backup path with size matching the live database and mode 0600.
- Rebuilt/recreated only the FakturaBot backend. FakturaBot and the pinned
  cloudflared sidecar remained running with no published callback port.
- In-container transport smoke: a correctly signed dummy relay reached the
  callback and returned 400 only for invalid OAuth state; an invalid signature
  returned 401 before OAuth/DB work. Safe browser headers were present.
- Public end-to-end smoke on the registered zevsflow.sk callback followed
  exactly one 302 relay and returned 400 for the dummy state. Worker and
  backend responses both returned no-store, no-referrer, and noindex headers.
  The former production 502 is resolved.
- No real OAuth state, grant, Gmail call, mailbox mutation, imported document,
  Drive upload, parser, LLM call, or business-data write was created by the
  smoke.
- Infrastructure status is production-ready for controlled consent. Product
  status remains partial and requires_external_credentials until the configured
  Zevs s.r.o administrator completes /gmail_connect with the expected account
  and one deduplicated statement import is verified.
# 2026-08-02 - Gmail callback HMAC signed relay variance

- Docs/contracts read: active Gmail architecture proof, setup runbook, callback
  app/runner/service, current gateway contract, and focused callback tests.
- Production evidence: Worker server-to-server fetch returned 502 while direct
  Tunnel POST reached the private callback and correctly returned 401 without
  the proxy secret. Cloudflare compatibility flags did not make that
  subrequest path reliable.
- Approved variance: the Worker now keeps only bounded state plus code or
  error, adds an issuance timestamp, base64url-encodes the payload, and signs
  that exact value with HMAC-SHA256. The browser follows a no-store redirect to
  the outbound-only Tunnel; the secret is never placed in the URL.
- Backend verification is constant-time and occurs before OAuth state, DB, or
  Google work. Missing/invalid signatures, payload tampering, relays older than
  five minutes, excessive future skew, duplicate parameters, and invalid
  payload shapes fail closed.
- Existing one-time OAuth state/nonce, admin/workspace authority, exact redirect
  URI, Google identity/scopes, token encryption, DB schema, storage, collector,
  and Gmail read-only boundaries are unchanged.
- Touched scopes: callback transport, gateway, transport tests, architecture,
  runbook, project log, changelog. No LLM/STT/LMM/FSM, Product Truth behavior,
  self-learning, PDF/layout, DB migration, or business-data mutation.
- Status remains partial, requires_admin, and requires_external_credentials
  until a real configured administrator completes Google consent and a
  deduplicated statement import is proved.
- Rollback: disable both Gmail flags, stop the callback/Tunnel service, and
  redeploy the prior Worker/backend commits. Preserve DB/storage for audit.
# 2026-08-02 - Gmail callback private Tunnel deployment foundation

- Docs/contracts read: Gmail collector setup runbook and architecture proof,
  server agent context, current Compose definition, current callback runner,
  and callback/config tests.
- Constraints: no public VPS callback port; remotely managed outbound-only
  Cloudflare Tunnel; exact Zevs workspace; Gmail read-only; file-backed Tunnel
  token; separate Worker proxy secret; no secrets in git/logs/chat.
- Touched scopes: production Compose, server/callback deployment documentation,
  focused infrastructure regression. No Telegram routing, FSM, LLM/STT/LMM,
  DB schema, persisted business data, access model, or PDF/layout change.
- Status: callback transport `requires_setup` until the Cloudflare Tunnel,
  hostname and Worker variables are configured and runtime-smoked. Gmail
  collection remains disabled until that gate passes.
- Maturity: deterministic external-integration setup only; the Gmail product
  capability remains `partial` and `requires_external_credentials`.
- Added a pinned `cloudflare/cloudflared:2026.7.2` service. It connects to
  `http://bot:8081` over the private Compose network, mounts
  `/bot/secrets/cloudflared-token` read-only, and publishes no host port.
- Product proof: the public callback must traverse Worker -> authenticated
  Tunnel hostname -> private callback; an unauthenticated direct Tunnel request
  must fail closed. Real consent and one deduplicated statement import remain
  separate acceptance gates.
- Self-learning hooks: none; OAuth, callback transport and document collection
  must not learn semantic aliases or bypass deterministic validation.
- Rollback: disable both Gmail flags, restart the bot, stop the Tunnel service,
  and disable its route. Preserve DB/storage and imported originals for audit.

# 2026-08-02 - Separate Gmail OAuth credentials from owner Drive OAuth

- Production preflight found that the active owner Drive OAuth integration
  already uses GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET.
- Gmail configuration now requires dedicated GOOGLE_GMAIL_OAUTH_CLIENT_ID and
  GOOGLE_GMAIL_OAUTH_CLIENT_SECRET values.
- The approved mailbox sample identified Tatra banka statement PDFs with MIME
  `application/octet-stream`; the collector now requires `.pdf` plus `%PDF-`
  signature validation before storage.
- No production secret was written, rotated, logged, or committed. Gmail stays
  disabled pending callback deployment, exact query approval, and controlled
  runtime smoke.

# 2026-08-02 - Emergency rollback of Contextual InfoHelp Recovery V1

- Confirmed four production regression classes after PR `#63`: unrelated destructive suggestions for receipt deletion wording; recovery callbacks dispatching with the bot-authored `callback.message`; synthetic action-label dispatch into an invoice owner without continuation FSM state; and missing Telegram quoted-message context.
- Audited latest `origin/main` at `1bea21028ff41abd1848e6637b255914e9b85d90`; PR `#63` merge `ec7c5696ec6b73b6e0a90c38ce3a1a1a5f8bae89` is a two-parent merge and PR `#64` is docs-only.
- Applied a mainline-parent revert of PR `#63` on `hotfix/revert-contextual-infohelp-v1`, preserving all unrelated commits and retaining PR `#64` historical evidence as rolled-back/superseded.
- Removed the contextual recovery classifier/store, conversation-context middleware/capture, recovery router/callback dispatch, active-FSM contextual descriptors/outcomes, unknown-command recovery route, and feature-only voice/context hooks.
- Restored pre-PR63 unknown-input, InfoHelp, active-FSM navigation/stale recovery, DecisionResolver callback, Product Truth, and customization-request behavior.
- Added rollback containment tests that reject `infohelp:*`, `navigation:show_main_menu`, `dispatch_recovery_action`, feature middleware/capture, destructive recovery buttons, and callback-message actor dispatch.
- Verification: rollback-only `5 passed in 2.84s`; focused InfoHelp/routing/callback/FSM `400 passed in 53.83s`; adjacent voice/invoice/workspace/contact/state-control `264 passed in 118.99s`; full suite `2429 passed, 7 subtests passed in 488.94s (0:08:08)`; compileall and staged diff check passed.
- No database schema, migration, persisted context, storage path, or business-data write is introduced by the rollback.
- Product status: Contextual InfoHelp Recovery V1 is `rolled_back_after_interactive_regression`; the underlying pre-existing `info_help` capability remains `partial`.
- V2 is explicitly out of scope and requires a revised Architecture Design Proof plus owner approval before implementation.
- Production deployment, backup path, final merge SHA, post-deploy integrity/hash, and runtime smoke are recorded operationally after the rollback PR merges; they are not preclaimed here.

# 2026-08-02 - Contextual InfoHelp Recovery V1 merged, deployed, and runtime-smoked

- PR `#63` was made ready and merged to `main`; merge SHA: `ec7c5696ec6b73b6e0a90c38ce3a1a1a5f8bae89`.
- Production `/bot/repo` fast-forwarded from `465df389c1b0c6ad3281733fe7888f5b49122c1d` to the exact merge SHA and remained clean against `origin/main`.
- Production compose build/recreate succeeded. `fakturabot` started polling as `@officeflow_sk_bot`, remained `running`, and had restart count `0`; no polling conflict or startup exception was observed.
- Production-image compile smoke passed. Bounded in-container runtime smoke returned `infohelp_runtime_smoke=ok` and validated router priority, context limits/isolation, active-flow navigation, payload sanitization, and strict bounded parsing.
- A configured live OpenAI call with synthetic `/invoce` input returned `infohelp_live_llm_smoke=ok outcome=clarify_candidates`. It executed no business side effect and wrote no persisted business data.
- The slim production image has no `pytest`; complete regression evidence remains the pre-merge `2467 passed, 7 subtests passed` run, plus the deployed compile/runtime/live-LLM checks.
- Temporary host/container smoke files were removed. No DB/schema migration, storage rewrite, or production business-data mutation occurred.
- Capability maturity remains partial Level 2. Deployed runtime smoke passed, but interactive acceptance still requires a real authorized Telegram text message, voice/STT update, recovery-button click, and keyboard lifecycle observation; no user update was fabricated.
- Rollback anchor before this deployment: `465df389c1b0c6ad3281733fe7888f5b49122c1d`.

# 2026-08-01 - Runtime issue Agent Claim reuses the existing handoff schema

- Owner decision: the former V1 GitHub-verified acknowledgment method is
  obsolete. Receiving an issue must be recorded by the deterministic handoff
  service without waiting for a Workshop commit.
- Reused the existing `runtime_issue_handoffs` columns and persisted states.
  A successful `claim` validates the live stdin token and exact
  `manifest_digest`, then atomically writes existing
  `status='acknowledged'` and `acknowledged_at`.
- The CLI renders that terminal status as
  `delivery_state=accepted_by_agent`. New claims leave
  `workshop_branch` and `workshop_commit_sha` null.
- Removed the active `ack` command and remote Git commit verifier. Git
  publication remains a final repair-session step, not an intake gate.
- No table, column, CHECK constraint, Stage 1 issue row, business data,
  tenant/workspace boundary, Telegram route, LLM/STT/FSM behavior, or Product
  Truth capability changed. No database migration is required.
- Preserved historical acknowledged rows without rewrite or deletion.
- Archived the superseded V1 bridge documents under
  `docs/archive/runtime_issue_autorepair_v1/` with an explicit obsolete
  notice. Current contract and Workshop paths now live under
  `docs/features/runtime_issue_agent_claim/`.
- Repository status: implemented locally; not merged or deployed. Production
  still exposes the obsolete CLI until a separately approved deployment.
- Verification: the new CLI regression failed before implementation; 62 focused
  bridge/evidence/workshop tests and compileall passed after implementation;
  the full repository suite passed with 2424 tests and 7 subtests in
  398.95 seconds.

# 2026-07-31 - Repair skill gates and Agent Claim Bridge V2 design

- Updated the interactive repair skill so diagnosis begins with a candidate
  error class and the active canonical documents, registries, code owners, or
  tests that define the intended architecture and correct behavior.
- Required the exact canonical sources used for diagnosis to be recorded in
  the Workshop log; missing canonical truth blocks intuitive repair.
- Made `docs/Implementation_Agent_Checklist.md` conditional: it is mandatory
  before a code repair, but not for final no-code diagnostic outcomes such as
  expected behavior, external failure, or insufficient evidence.
- Clarified that repair/workshop commit and push are final publication steps
  after a complete local outcome, required tests, and final diff inspection;
  intermediate intake/progress artifacts must not be pushed.
- Added the `RUNTIME_ISSUE_AGENT_CLAIM_BRIDGE_V2` Architecture Design Proof.
  The proposed deterministic `claim` transition records
  `accepted_by_agent` after a bounded local receipt and does not wait for a
  GitHub commit, PR, merge, or deployment.
- V2 remains `planned_not_implemented` and migration-sensitive. Runtime code,
  SQLite schema/data, server state, and production were not changed in this
  documentation/design step.

# 2026-07-31 - Runtime Issue F02 Prefix Routing Repair

- Classified `IR-20260730-5FA71FDFFCDE-F02` as a confirmed low-risk routing
  defect: the complete STT problem report competed with invoice analytics in
  the generic top-level resolver.
- Added a deterministic first-token boundary for `проблема`, `помилка`, `баг`,
  `chyba`, `problem`, `bug`, and `error`.
- Authorized administrators now reach the existing shared runtime issue owner
  before business routing; the original report remains intact and active FSM
  state/data are preserved.
- Authorized non-admin idle users enter the existing confirmation-gated
  admin-review request preview. No request is saved before approval, and no
  administrator notification is claimed.
- Active non-admin FSM ownership remains unchanged; no nested/suspended FSM
  architecture was introduced.
- Unauthorized users remain blocked before STT/LLM and persistence.
- AI maturity remains partial Level 3 for non-admin human-review capture and
  the existing bounded runtime-issue layer for administrators.
- Self-learning was not added: explicit support prefixes are deterministic
  control markers, not learned business aliases.
- No DB schema, persisted data, tenant boundary, dependencies, or production
  data changed.
- Verification: 47 focused runtime issue/voice tests passed; 553 adjacent
  routing, InfoHelp, customization, and access tests plus 7 subtests passed;
  the final full repository suite passed with 2433 tests plus 7 subtests.
  `python -m compileall -q bot` and `git diff --check` passed.

## 2026-07-30 - Gmail OAuth foundation and statement collector V1 local implementation

### Status
- Implemented the bounded local foundation as `partial`, `requires_setup`, `requires_admin`, and `requires_external_credentials`.
- Acceptance remains `runtime_not_proven`: no production callback deployment, real Google consent, restricted-scope verification, or real mailbox/Drive smoke was performed.
- Explicit product decision: `PUBLIC_INDEXING_ENABLED=true` remains unchanged; Gmail OAuth has an independent fail-closed launch gate.

### Runtime and storage
- Added separate Google identity, service grant, workspace binding, OAuth state, and notification-cooldown tables without rewriting the existing owner Drive connection table.
- Added official OIDC token verification, nonce/audience/email checks, hashed short-lived single-use state/nonce persistence, encrypted token envelopes, same-subject refresh-token preservation, local disconnect, and `needs_reauth` transitions.
- Added an internal secret-bound callback service and a bounded server-side callback gateway in the companion `zevsflow-site` repository.
- Added admin-only `/gmail_connect`, `/gmail_status`, and `/gmail_disconnect`, a Gmail read-only adapter with no mutation methods, bounded historical overlap/pagination, attachment-only MIME traversal, atomic workspace storage, source/content deduplication, and parser-deferred metadata.
- Added one bounded Telegram notification per newly stored canonical statement, cooldown-protected reauthorization notifications, and optional idempotent `bank_statement_original` enqueue through the existing owner Drive archive path. Local originals are preserved.

### Truth, safety, and verification
- Updated Product Truth, InfoHelp, TZ, setup/rollback runbook, architecture proof, changelog, and conversation acceptance evidence. No canonical action, FSM, DecisionResolver, LLM/STT/LMM, invoice/PDF, or existing Drive credential behavior was changed.
- Focused Gmail/Product Truth/InfoHelp tests: 161 passed.
- Existing archive/Drive regression tests: 109 passed.
- Full backend suite after the final config guard: 2408 passed, 7 subtests passed in 469.16 seconds.
- Post-suite Telegram HTML-escaping/config focused smoke: 10 passed.
- Companion gateway direct Node tests: 4 passed earlier in the session.
- Full companion lint/test commands were not run because the environment approval reviewer reported its usage limit; no workaround or deployment was attempted.
## 2026-07-30 - Runtime repair correction - invoice analytics alias-first customer resolution

### Diagnosis and repair

- The first PR #54 implementation was tenant-scoped but incomplete: after the
  analytics dataframe was built, it asked a bounded LLM to choose a canonical
  contact directly from the full analytics question. That bypassed the
  confirmed contact-alias and deterministic resolution chain already used by
  invoice generation.
- Added a bounded analytics slot extractor that returns only the minimal
  explicitly stated `customer_reference` or `null`. It does not receive the
  contact list and cannot choose or persist an identity.
- Python now sends that reference through the existing tenant-scoped invoice
  contact path: exact -> normalized -> confirmed alias -> high-confidence
  fuzzy -> bounded LLM fallback over current-tenant candidates.
- A resolved contact becomes a trusted `contact_id` dataframe prefilter before
  planner execution. An explicit unresolved reference now fails safe with a
  clarification instead of silently analyzing all tenant invoices.
- Analytics remains read-only and does not learn/write an alias, edit a
  contact, rewrite an invoice, regenerate a PDF, or change DB/storage schema.

### Scope and product truth

- Existing canonical action: `invoice_analytics`; no new action, FSM, callback,
  confirmation family, storage layout, access rule, or migration.
- Current status and maturity remain `partial` bounded read-only analytics;
  Python owns tenant scope, identity validation, dataframe filtering,
  planner validation, execution, and all side-effect boundaries.
- Text and voice/STT share the same post-transcription path. STT still only
  supplies transcript text; it does not resolve the contact.
- Confirmed alias self-learning is reused read-only. No learning hook was added
  because an analytics answer is not user confirmation for a new alias.
- The separate runtime issue F02 concerning routing of messages beginning with
  “Проблема...” is explicitly deferred as `needs_more_diagnostics`; this repair
  does not change runtime-issue/top-level routing.

### Verification

- Failing-before proof: the confirmed-alias regression invoked the bounded
  analytics contact selector and failed before this correction.
- Focused post-repair acceptance: confirmed alias resolves before bounded
  fallback; explicit unresolved customer stops before planner execution.
- Focused and adjacent analytics/contact/tenant/voice/Product Truth suite:
  546 passed.
- Full 92-file test inventory was run in three groups after the monolithic
### Merge and controlled deployment

- Repair commit `7d6f43f603a2661ed6d50a8244b20284a680d30e` was pushed
  to the existing repair branch and PR #54 was updated through the connected
  GitHub app. GitHub exposed no status checks for the commit.
- PR #54 was marked ready and merged into `main` as
  `2379869c6f609624082fc36eb1e088174e554154`.
- Server `/bot/repo` was clean and fast-forwarded from `632e9b0` to the exact
  merged SHA. Docker image `repo-bot` was rebuilt and the existing
  `fakturabot` container recreated.
- Pre-deploy SQLite backup:
  `/var/backups/fakturabot/20260730T211228Z_pre_pr54_invoice_analytics_alias/`;
  active and backup SHA-256 values matched exactly after deployment and SQLite
  integrity check returned `ok`.
- Production container is `running`, restart count is zero, polling started,
  and filtered startup logs contain no error/critical/traceback marker.
- Production-image temporary-DB smoke passed for Cyrillic confirmed-alias
  lookup and strict customer-reference parsing. Real Telegram voice acceptance
  remains a manual follow-up.

  desktop command hit its output/time limit: 409 passed; 1540 passed plus
  7 subtests; 436 passed. Aggregate: 2385 passed, 7 subtests passed.
- `python -m compileall -q bot tests`: passed.
- `git diff --check`: passed.

## 2026-07-30 - Runtime repair - invoice analytics customer identity scope

Summary:
- Diagnosed a recorded production observation where a noisy/Cyrillic spoken
  customer reference reached invoice analytics but was not resolved to the
  existing canonical contact before planner filtering.
- Added a bounded internal customer identity step over unique contacts from the
  active tenant plus `unknown`; Python now prefilters the sanitized dataframe by
  trusted `contact_id` before planning.
- Added a planner contract that rejects a second `customer_name` or `contact_id`
  filter after Python has established the customer scope.

Preflight:
- Docs/contracts read: AGENTS, Product Doctrine 2030, AI Layer Implementation
  Standards, Product Truth Layer/Registry design, Self-Learning Layer,
  Confirmed Semantic Alias Learning Contract, Evaluation/UX standards, TZ,
  LLM orchestrator/action/in-action/resolver contracts, Invoice Analytics
  Runtime Contract, Safe Data Analyst checklist, runtime repair policy/runbook,
  repository audit, server context, current code/tests, and recent project log.
- Touched scopes: bounded LLM canonicalization, invoice analytics handler,
  sanitized dataset catalog, planner validation, Product Truth, contracts,
  eval artifact, tests, changelog, and project log.
- Current status: `partial` read-only invoice analytics; no status uplift.
- AI maturity: existing bounded partial Level 2 behavior; Python owns scope,
  validation, execution, and every side-effect boundary.
- Out of scope: new action/FSM/callback/confirmation, DB/schema/storage migration,
  contact or alias write, invoice/PDF rewrite, deployment, merge, or production
  configuration/data change.
- User journey proof: an authorized idle user asks by text or voice/STT for an
  invoice total for a noisy/Cyrillic customer name; bounded resolution selects
  only a current-tenant contact or `unknown`; Python computes only over matching
  trusted `contact_id` rows and returns a read-only answer.
- Self-learning considered: intentionally not added. Analytics alone is not
  user confirmation for a reusable contact alias.
- Product claim sources: runtime code/tests, Product Truth `invoice_analytics`,
  Invoice Analytics Runtime Contract, TZ, orchestrator/in-action contracts.

Verification:
- Focused invoice analytics suite: 54 passed, 195 deselected.
- Adjacent analytics/Product Truth/InfoHelp/voice suite: 469 passed.
- Full repository suite: 2376 passed, 7 subtests passed.
- `python -m compileall -q bot tests`: passed.
- `git diff --check`: passed with line-ending conversion warnings only.

## 2026-07-29 - Runtime issue workshop bridge Phase 1

### Implementation
- Added the dedicated additive `runtime_issue_handoffs` table with strict owned-schema validation, stable one-per-issue receipts, 60-minute atomic leases, safe expiry/redelivery, token rotation, verified acknowledgment, and no Stage 1 mutation.
- Added bounded JSON-only `take-next`, stdin-only `ack`, recorded-evidence collection, and idempotent workshop queue/log bootstrap CLIs. Raw lease tokens are never persisted or accepted through argv; remote receipt verification clones the fixed workshop branch into an automatically cleaned isolated temporary bare repository and performs the ancestor check there without mutating the project repository.
- Added fixed-window recorded STT/Docker/network/provider evidence from Docker stdout and stderr with exact labeled correlation, conflicting-identity rejection, a strict global Docker lifecycle/health allowlist, cross-tenant rejection, unavailable/source-error truth, combined input/item/excerpt caps, secret/path redaction, and no active probe.
- Review amendment: remote verification runs outside `BEGIN IMMEDIATE`; acknowledgment obtains a fresh timezone-aware UTC value after verification, reopens a write transaction, atomically revalidates every live lease/ack fact against that fresh time, and uses it for the conditional update and `acknowledged_at`. A lease expiring during verification fails without canonical mutation.
- Kept `reconciled` schema-reserved and unreachable. Telegram routing, FSM, callbacks, Product Truth, InfoHelp, nightly scheduling, diagnosis, repair, notifications, deploy, and production data remain unchanged.

### Verification
- Focused bridge suite after review amendments: 69 passed in 8.27s.
- Required adjacent runtime-issue/FSM/access/tenant/workspace/Product Truth/InfoHelp set after review amendments: 622 passed in 32.80s.
- Full repository suite after review amendments: 2356 passed, 7 subtests passed in 86.24s.
- Compileall, diff check, internal Markdown links, canonical/workshop JSON parsing, final scope audit, and secret/private-path scan passed.
- Temporary migration proof preserves all pre-existing table/index/trigger definitions and row values and rejects missing/type/default/check/unique/index incompatibility. Real Docker/GitHub/provider/server smoke and production migration were not run.
- Architecture verdict remains `ready_for_handoff`; implementation verification verdict is `safe_to_review`; design-to-code variance is `none_identified`.
## 2026-07-28 - Official contact registry production scope expanded globally

### Configuration and rollback
- User explicitly approved replacing the single-workspace registry pilot scope with availability for every authorized user who has an active workspace/profile.
- Read-only production audit found `CONTACT_REGISTRY_LOOKUP_ENABLED=1`, `CONTACT_TAX_LOOKUP_ENABLED=1`, a configured Financial Administration API key, five-second provider timeouts, a five-candidate maximum, and a non-empty `CONTACT_REGISTRY_PILOT_WORKSPACE_IDS`.
- Backed up the protected server `.env` to `/var/backups/fakturabot/20260728T192708Z_contact_registry_global/.env.before`; pre-change SHA-256 is `ed4936042bcc47bc5090c147303482cfffc6c016082b4a1e52ef0cc2144a212c`.
- Cleared only `CONTACT_REGISTRY_PILOT_WORKSPACE_IDS`, preserving the global RPO/tax enable flags, API key, timeouts, candidate bound, and all unrelated configuration. Post-change `.env` SHA-256 is `aac22b958d9ca5840774911b6dd0620736639ca214d90bebae4112ce80594f75`.

### Runtime verification
- Recreated only the existing FakturaBot container without build or code update. Effective container configuration reports registry and tax lookup enabled, an empty global pilot scope, configured tax credentials, five-second timeouts, and five maximum candidates.
- Container startup is healthy at the existing server commit `acb1c75`: status `running`, restart count zero, and aiogram polling started without matching `ERROR`, `CRITICAL`, `Traceback`, or Telegram polling conflict output.
- The change performs no DB/storage migration or business-data write. Authorization, active-workspace binding, bounded candidate selection, typed precision fields, provider fail-closed behavior, and explicit final confirmation remain mandatory.

## 2026-07-18 - Registry tax preview wording production repair

### Cause and repair
- Real Telegram acceptance proved that official income-tax ID enrichment worked, but the preview still appended a generic sentence saying tax IDs were not created or inferred. The sentence was misleading when the income-tax ID was already present.
- Replaced the unconditional note with deterministic, source-aware wording. An officially enriched income-tax ID is now acknowledged; a missing VAT ID is stated only as not found for the selected company ID and is never inferred. Manual-entry guidance remains only when the required income-tax ID is actually absent.
- Added focused FSM assertions for the enriched and unavailable-tax branches. Fake-only focused registry/tax/Product Truth tests passed: 58 passed in 11.76s; compileall and diff-check passed.

### Controlled deployment evidence
- Committed and pushed `92bcaa7` (`fix: make registry tax preview source aware`), created Docker rollback tag `fakturabot-rollback:pre-92bcaa7`, fast-forwarded the clean server tree, and rebuilt/recreated the existing production container.
- Production is running at exact SHA `92bcaa7e0ce4cd9ce42d2522ceaa7561ffdffe70`; startup and aiogram polling are healthy. A deterministic in-container smoke returned the expected source-aware wording for an official income-tax ID with no VAT ID.
- Tax enrichment remains enabled behind the existing parent registry/pilot gate; the API key is present without being printed and timeout remains 5 seconds. SQLite integrity is `ok`; counts remain 3 contacts, 9 invoices, and 3 workspaces. No schema migration or contact/invoice/storage write occurred.
## 2026-07-18 - Contact registry search/tax enrichment controlled deployment

### Release and rollback
- Created scoped commit `e63127b` (`feat: improve registry search and add tax enrichment`) from 21 task files and pushed `main`; pre-existing local work in `PROJECT_LOG.md` and `tests/test_access_workspace_reactivation.py` remained excluded.
- Server repo was clean at `692eebb` and fast-forwarded to exact SHA `e63127b6b080068f3012a26e51728d885d535f58`.
- Created rollback point `/var/backups/fakturabot/20260718T171457Z_contact_registry_tax_enrichment`: SQLite integrity `ok`, DB SHA-256 `9f0bd0df2be034f4f419b2200280048a19ca4e26483818206f99f8018ff1c1ef`, protected env copy, 71-file storage snapshot, and Docker tag `fakturabot-rollback:20260718t171457z`.

### Activation and bounded smoke
- Atomically set `CONTACT_TAX_LOOKUP_ENABLED=1` and `FINANCNA_SPRAVA_TIMEOUT_SECONDS=5` while preserving the exact key and `.env` mode `600`/owner `root:root`; the existing RPO pilot-workspace gate remains the parent boundary.
- Rebuilt/recreated the production container with image SHA `24807583f7a24c49f02175c34737ac8e279237d8c11ebafb31b9ac655af1c00a`; startup and aiogram polling were healthy.
- Container config reported tax enabled, key present, timeout 5, income mapping `ds_dsrdp:ico:dic`, and VAT mapping `ds_dphs:ico:ic_dph` without printing the secret.
- Live tax-provider smoke for IČO `56055552` returned an exact validated DIČ, no IČ DPH, unknown VAT status, and source `financna_sprava_income_tax`; no tax value was logged.
- The first 5-second RPO smoke timed out externally as `registry_unavailable`; one bounded 10-second retry/final check returned exactly one exact-name Zevs candidate, matching IČO/city, and valid RPO detail/address/source.
- Post-deploy audit: server tree clean at `e63127b`, container up, zero recent ERROR/Traceback/CRITICAL log matches, SQLite integrity `ok`, and unchanged counts of 3 contacts, 9 invoices, and 3 workspaces. No DB/storage migration or contact/invoice write occurred.

### Residual gate
- Controlled Telegram conversation acceptance is still pending; this deployment is not a general `safe_to_deploy` claim and does not broaden the configured pilot workspace scope.
## 2026-07-18 - FA_CONTACT_REGISTRY_SEARCH_QUALITY_AND_TAX_ENRICHMENT_V1 staged implementation

### Changes
- Added deterministic RPO full/core/legal-suffix normalization, exact-result collapse, active-first duplicate exact results, bounded whole-token/compact/one-edit suggestions, and weak internal-substring rejection.
- Suggestions such as `ZE VS` and `Empbau` require explicit selection; only exact name/IČO results may auto-open detail.
- Added disabled-by-default Financial Administration config and a separate async provider/aggregator with exact-IČO validation, bounded status/error handling, response limits, no retries/raw logging, conflict refusal, no `SK + DIČ` inference, and existing source metadata reuse.
- Integrated enrichment only in the selected-company detail owner. Valid DIČ skips typed DIČ; all tax failures retain RPO and use manual DIČ. No DB write occurs before final confirmation.
- Added fake-only provider/search/FSM/Product Truth tests and synchronized environment examples and canonical docs.


### Verification
- Final post-audit focused registry/contact/provider completion suite: 108 passed in 36.44s.
- Broad contact/workspace/invoice/callback/voice/state/migration/Product Truth regression: 803 passed.
- A later expanded 34-file broad rerun reached 858 passed plus one transient Windows `os.replace` access-denied failure in the existing migration rollback test; its immediate isolated rerun passed (1 passed), consistent with a temporary filesystem lock rather than a product regression.
- Final post-audit full regression: 2244 passed, 7 subtests passed in 338.16s.
- `python -m compileall -q bot` passed.
- All automated provider tests use fakes. A separate bounded authenticated FS metadata/schema smoke completed without logging the key or raw taxpayer values.
### Evidence boundary
- Authenticated evidence binds `ds_dsrdp` (`ico` -> `dic`) and `ds_dphs` (`ico` -> `ic_dph`) with lowercase row fields, documented pagination envelope, and 404 no-result semantics. `verified_financna_sprava_schema()` now returns only those audited mappings.
- Architecture verdict is `ready_for_handoff`; the implementation verdict is `safe_to_review`, not `safe_to_deploy` or a claim that production tax enrichment is active.

### Safety
- No commit, push, DB/storage migration, restart, code deployment, or feature activation occurred. A later user-authorized server write installed only the FS key in the existing env file. Pre-existing edits in this file and `tests/test_access_workspace_reactivation.py` were preserved.


### 2026-07-18 server key installation follow-up
- At the user's explicit request, installed the clipboard-provided Financial Administration key into the production compose env file `/bot/repo/.env` without printing or logging its value. An initial one-character corruption caused by Windows-to-SSH CR normalization was detected from 401 responses, corrected by exact-byte transfer, and verified without exposing the secret.
- Final verification reports the full 250-character value, exactly one non-empty key line, file mode `600`, owner `root:root`, and zero local/remote temp files. `CONTACT_TAX_LOOKUP_ENABLED` remains absent/off.
- Authenticated `/api/lists` and list-detail calls confirmed `ds_dsrdp` searchable by `ico` and `ds_dphs` searchable by `ic_dph,ico`; exact searches confirmed lowercase `dic`/`ico` and `ic_dph`/`ico` row mappings, page envelope behavior, direct official IČ DPH, and HTTP 404 for no exact result.
- A bounded DPH page audit observed 315 pages, 314204 items, 1000 distinct IČOs in the first 1000 rows, and no duplicate-IČO group in that sample. Conflicting/historical rows and documented failure statuses remain fake-tested/fail-closed.
- Bound the exact audited mapping in local code and added a regression assertion; the immediate focused provider/FSM/Product Truth suite passed (`58 passed in 12.63s`). No service restart, container rebuild, deployment, DB/storage write, or feature activation occurred.
## 2026-07-17 - Contact Registry Pilot Activation For SZČO Mykhailo Alieksieienko

### Production data operation
- User explicitly identified the test contact `Zevs s.r.o.` in workspace `SZČO Mykhailo Alieksieienko` for complete removal from the live contact registry before a controlled lookup recreation test.
- Read-only audit found exactly one matching contact, zero linked invoices, one confirmed contact alias, and a stored contract path whose target file did not exist.
- Verified rollback backup: `/var/backups/fakturabot/20260717T193839Z_zevs_delete_pilot`; SQLite integrity `ok`, target row present, backup SHA-256 `0872736299f9bf762bfe0bf2a7b357a66e3ff44ed30d00f367e4e2806d4fc486`, and the prior server `.env` retained server-side.
- One transaction deleted the contact and its one contact alias. Post-write verification reports zero target rows/aliases, DB integrity `ok`, three remaining contacts, and nine unchanged invoices.

### Pilot activation and verification
- Enabled `CONTACT_REGISTRY_LOOKUP_ENABLED=1` for exactly the selected workspace, with timeout 5 seconds and maximum 5 results; all other workspaces remain outside the pilot.
- Canonical multi-workspace dry-run remains ready with zero blockers and no writes. Accounting Drive audit remains deployment-ready with zero blockers and unchanged DB hash.
- Recreated the existing production image without rebuild to apply env configuration. Startup/polling logs are healthy.
- Live bounded RPO name search for `Zevs s.r.o.` normalized to `zevs`, returned at most five candidates, and included an exact normalized-name match. The real Telegram conversation remains pending user execution.
## 2026-07-17 - Multi-Profile Migration Audit Readiness Repair

### Cause and scope
- Production dry-run exposed a canonical audit defect after one authorized actor acquired two supplier profiles: the legacy by-telegram planner intentionally omitted non-unique actors and then misclassified already workspace-bound rows as owner_missing.
- Scope is read-only migration/deployment tooling. No business row, workspace selection, storage path, Telegram FSM, Product Truth, LLM/STT/LMM, or runtime capability behavior changes locally.

### Repair
- Legacy pre-migration databases retain the existing unambiguous Telegram ownership path.
- Already migrated databases validate direct ownership through persisted workspace_id plus actor and canonical supplier/workspace mapping.
- Workspace-aware relation checks now reject unknown workspaces and cross-workspace invoice/contact, follow-up, confirmed alias, work-time event, and customization relations.
- Added a real two-profile same-actor regression and a fail-closed cross-workspace/unknown-workspace regression.

### Verification and delivery state
- New targeted regressions: 2 passed.
- Full migration/readiness suite: 33 passed.
- Full project suite: 2206 passed, 7 subtests passed in 334.18s.
- Repair commit 997d3e7 was pushed and deployed. Fresh pre/post-deploy canonical dry-runs report public_profile_switch_ready=true, blocker_count=0, migration_required=false, and writes_performed=false.

## 2026-07-17 - FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1

### Preflight and architecture
- Audited baseline `main` HEAD `f4415cdf71bedf370aa5f141c7abee8efff80cb4`; preserved pre-existing local edits in `PROJECT_LOG.md` and `tests/test_access_workspace_reactivation.py`.
- Read the top-level/subflow proof, action design, handoff, implementation, evaluation, migration, DecisionResolver, Product Truth, InfoHelp, TZ, contact/workspace/DB/callback/voice code and focused tests before implementation.
- Created `docs/architecture/FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1_ARCHITECTURE_DESIGN_PROOF.md`; verdict `ready_for_handoff`.
- Classification: extension of existing `add_contact`; AI maturity remains Level 2 capability-aware guidance. Registry field mapping/ranking and every write are deterministic Python. No self-learning hook is appropriate for official identifiers.

### Implementation
- Added nullable contact `iban` across schema contracts, additive/idempotent legacy+workspace bootstrap, models/services/parser/manual/document previews, and a narrow MOD-97 contact validator without changing supplier IBAN behavior.
- Added official Slovak RPO async provider boundary with name/exact-IČO search, deterministic normalization/ranking, bounded results/timeout/response size, safe HTTP/JSON handling, and no LLM/scraping/retry/raw-response persistence.
- Extended the existing contact FSM with workspace/pilot-gated candidate/detail/fallback/typed DIČ/optional email-IBAN-person/final-confirm states. `/contact`, `/contact_add`, and `/add_kontakt` share one owner. Exact values remain text-only; final yes/no reuses DecisionResolver.
- Added nonce/index-only callbacks with actor/state/workspace/profile/feature/expiry/index/replay checks. No contact write occurs before final confirmation.
- Added transactional registry merge owner: same IČO updates one stable row while preserving unsupplied optional fields, contract path, and invoice references; name/IČO collisions and split/duplicate rows fail closed.
- Synchronized Product Truth (`partial`), InfoHelp, TZ, in-action response registry, README navigation, environment examples, changelog, and the Conversation Acceptance Proof.

### Official-source and variance boundary
- Official RPO docs and read-only live search/detail shape were verified on 2026-07-17. RPO supplies official name, IČO, address/municipality, and lifecycle data; it does not supply DIČ/IČ DPH for this implementation.
- Financial Administration information-list API requires separate credentials/setup and was not added. DIČ is typed; IČ DPH is never inferred. Cache remains deferred, so no no-op cache TTL setting is exposed.

### Post-review repairs
- Replaced mutating workspace resolution in registry callback validation with a read-only resolver; wrong-workspace stale callbacks no longer recreate active selection state.
- Synchronized registry-session expiry with the shared five-minute contact inactivity clock for accepted typed activity and fully validated buttons; malformed/stale callbacks do not refresh.
- Normalized valid AI/document-extracted contact IBAN before partial or complete draft persistence; invalid extracted IBAN remains behind the typed correction gate.
- Added regression evidence for no selection write, typed/button timeout refresh, and LLM-returned spaced lowercase IBAN.

### Verification and delivery state
- Post-review targeted regression: `33 passed in 19.01s`.
- Expanded focused registry/contact/workspace/migration/decision/state/voice/Product Truth regression: `139 passed in 36.37s`.
- Final full suite: `2204 passed, 7 subtests passed in 326.14s`.
- Conversation Acceptance Proof: `docs/evals/FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1_conversation_acceptance_proof.md`, verdict `safe_to_commit` (code-quality evidence only, not deployment authorization).
- Feature commit ba2d0dc and audit repair 997d3e7 were pushed and deployed. The initial readiness blocker was repaired without bypassing the gate.

### Deployment gate result
- Server repo remained clean at the prior commit and the FakturaBot container remained Up; no production checkout or runtime mutation occurred.
- Read-only accounting Drive audit passed with zero blockers and unchanged DB hash.
- Canonical multi-workspace dry-run performed no writes but failed readiness with 131 owner/target blockers while also reporting database_already_migrated.
- Root cause is a canonical planner limitation for the current two-profile actor: by_telegram excludes actors with more than one supplier, so already workspace-bound rows are reported as owner_missing.
- Contact schema currently has four preserved rows and no iban column; additive startup migration remains pending behind the audit repair and a fresh verified backup/rollback gate.

### Production delivery
- Repaired pre-deploy dry-run: public_profile_switch_ready true, blocker_count zero, migration_required false, database_already_migrated, and writes_performed false. Drive audit also passed with zero blockers and unchanged DB hash.
- Verified SQLite backup /var/backups/fakturabot/20260717T190725Z_997d3e7_contact_registry has source/backup integrity ok and SHA-256 587ccd95596bb5aad651d79f8df2d23435bb44be1274c08a532c2268625aeab4; pre-schema counts were four contacts and nine invoices.
- Docker rebuilt/recreated FakturaBot at 997d3e7. Startup/polling logs are healthy, recent error scan is empty, and host/container hashes match for the changed runtime owners.
- Post-deploy DB integrity is ok. Nullable contact.iban exists once; four existing contacts retain null IBAN; all table counts match backup; invoice count remains nine; orphan invoice-contact references are zero.
- Post-deploy migration and Drive audits remain green. Bounded official-RPO smoke passed without logging company data or raw response.
- Registry runtime remains disabled with no pilot workspaces configured. No real Telegram pilot conversation was performed; enabling requires explicit pilot workspace selection.

## 2026-07-16 - Production Enqueue Repair For Two Preserved Receipts

- After explicit user direction to archive the two existing receipts, a read-only storage/state audit found exactly two confirmed local receipt metadata files with preserved originals but no archive state/job; all 33 older accounting records remained tracked.
- Fail-closed dry-run validated one active canonical workspace, one matching supplier, active membership ownership, zero existing jobs, one original plus metadata per receipt, and exact safe targets `<workspace.drive_folder_name>/2026/blocky/2026-07`.
- Created verified rollback backup `/var/backups/fakturabot/20260716T181011Z_feba5a9_drive_enqueue_2_receipts`: SQLite integrity `ok`, two originals plus two metadata files retained, DB SHA-256 `15eb7ae14740f6012c3f11a952dcd89821b867b7cd20f9a84334b477bafc07d0`, archive SHA-256 `de99a6e0abcb5bcc3cc859d39924a60459d1a174175f547ff3b3eb2267e6612e`.
- Enqueued only those two documents through `AccountingDocumentArchiveService`; both jobs started `pending` with immutable workspace-specific targets and no pre-existing job collision.
- The existing scheduler processed exactly two jobs. Both completed `uploaded` with distinct Drive file ids and one shared correct target folder id; no retry or error code occurred.
- Existing retention executed only after successful upload: both local originals were removed, both local metadata files remain, and the dedicated backup is retained.
- Post-operation verification: DB integrity `ok`, one job per document, untracked metadata `0`, active accounting jobs `0`, blockers `0`, and read-only audit reported `database_unchanged=true`.
- No historical remote file was moved, no old job was rewritten, no invoice PDF was touched, and no second OAuth connection, worker, scheduler, schema change, Docker restart, or code deployment was performed for this repair.

## 2026-07-16 - Owner Google Drive Reauthorization And Status Lookup Repair

- Production owner OAuth reauthorization was completed after explicit user approval through the existing manual bootstrap. The first consent was rejected fail-closed as `drive_scope_missing`; a second consent with the required Drive permission completed successfully.
- Authoritative read-only verification reports the configured owner connection as `connected` with a stored root folder. No document upload, archive-job mutation, remote file move, or Drive folder creation was performed during reauthorization.
- Confirmed a Telegram integration defect: `/google_drive_status`, `/google_drive_disconnect`, and interactive state creation resolved a legacy `telegram-<id>` connection key while the active owner OAuth worker uses `GOOGLE_DRIVE_OWNER_WORKSPACE_ID`.
- Updated the three admin setup commands to resolve the shared configured owner connection. Reauthorization status now requires administrator action without falsely claiming `/google_drive_connect` is always available when production callback UX is not configured.
- Current capability status remains `partial`, owner-run only. No new canonical action, FSM, voice route, LLM/STT/LMM behavior, schema, workspace business ownership, archive path, retention behavior, or upload worker topology was added.
- Updated the owner OAuth operations document and changelog. Product Truth and InfoHelp capability status did not change because the repair makes the existing shared-owner connection status truthful without expanding support.
- Focused settings tests: `python -m pytest -q tests\\test_google_drive_setup_commands.py` -> `19 passed`.
- Expanded Drive/OAuth tests: `python -m pytest -q tests\\test_google_drive_setup_commands.py tests\\test_google_drive_oauth_state_service.py tests\\test_google_drive_connection_service.py tests\\test_google_drive_oauth_callback_service.py tests\\test_google_drive_service_account_archive.py` -> `107 passed`.
- Full suite: `python -m pytest -q` -> `2162 passed, 7 subtests passed`.

## 2026-07-16 - Accounting Document Drive Workspace Folder Isolation V1

### Preflight and scope
- Approved baseline verified at `a99528c2dcea4df98006b2a7e371ade84f524622` on `main`; initial unrelated dirty changes in this log and `tests/test_access_workspace_reactivation.py` were preserved.
- Read the approved task, architecture proof contract, multi-workspace proof, implementation/handoff/evaluation contracts, Product Doctrine, AI standards, Product Truth, InfoHelp, TZ, migration runbook, OfficeFlow storage proposal, current intake/archive/workspace/provider/retention code, and relevant tests.
- Read-only verdict: `design_matches_runtime`. The existing confirmed-save route, workspace-bound FSM, archive outbox, shared owner OAuth worker, retention, and idempotency matched the frozen architecture; the missing workspace-specific persisted target was the approved gap.
- Scope is deterministic Python storage/archive path selection. No LLM/STT/LMM, public route, FSM state, OAuth/token, scheduler, worker topology, invoice PDF, schema, production DB, server, or remote Drive mutation is included.

### Implementation
- Added one shared accounting-document archive path owner for canonical local path validation, `receipt -> blocky`, `incoming_invoice -> prijate_faktury`, Unicode-safe single workspace folder validation, and bounded relative target normalization.
- Confirmed workspace-bound intake now enqueues new receipt/incoming-invoice jobs with exact canonical `workspace_id`, local `storage_key`, persisted `drive_folder_name`, and immutable target `<drive_folder_name>/<YYYY>/<type>/<YYYY-MM>`.
- Missing/unsafe workspace folder or cross-workspace path fails before job creation; the handler keeps the existing successful local-save UX and preserves original plus metadata.
- Duplicate enqueue returns the existing job without overwriting its target; retry and worker execution use the persisted target and do not consult `active_workspace_selection`.
- Explicit provider targets are always relative below the configured root; a legitimate first workspace segment equal to the configured root name is no longer stripped accidentally. Existing invoice-PDF targets remain `YYYY/faktury/YYYY-MM`.
- Added `python -m bot.accounting_document_drive_audit --db-path <db>`: read-only aggregate audit with before/after DB SHA-256 and blocker exit code for active missing/unsafe/mismatched targets. No apply/backfill mode exists.

### Safety and verification
- No business schema or data migration; no local/remote file move; historical Drive files remain untouched.
- Existing retention remains: failed/pending uploads preserve original and metadata; configured post-`uploaded` cleanup may remove only accounting originals; metadata remains; invoice PDFs remain governed separately.
- Focused archive/intake suite: `114 passed`.
- Expanded worker/provider/workspace/Product Truth/InfoHelp suite: `292 passed`.
- Updated focused path/provider/Product Truth/InfoHelp suite: `162 passed`.
- Final full suite after retention assertions: `2162 passed, 7 subtests passed in 215.50s`.
- Real configured two-profile Google Drive smoke was documented but not run during local verification.

### Delivery
- Runtime commit `36090500e5a7ddeb05f405f5a8a287d3f5c4948f` was pushed to `origin/main`, fast-forwarded on `/bot/repo`, and built into the production container.
- Live and stopped-state read-only Drive target audits both reported `active_accounting_jobs=0`, `blocker_count=0`, `deployment_ready=true`, `writes_performed=false`, and unchanged DB SHA-256 `faa50d6a97a9ca0b3efa3cf677535b8f6d79b024bd62bef20bb3e67dec6a0309`.
- Verified backup `/var/backups/fakturabot/20260716T171216Z_3609050_drive_workspace` contains an exact raw DB copy plus storage archive; source and backup DB integrity both reported `ok` and raw DB SHA-256 values match.
- Post-deploy container state is `Up`; startup/polling and owner OAuth scheduler logs are present with zero recent error lines. Host/container SHA-256 values for the new path and audit modules match.
- Fifteen preservation tables have exact pre-deploy backup versus live row-count parity, including workspace, membership, supplier, contacts, invoices, accounting archive, and work-time rows; post-deploy DB integrity is `ok`.
- Redacted runtime inventory now has three workspaces, three active memberships, two active selections, and a maximum of two memberships for one actor. Actual Telegram switching and cross-profile object acceptance were not exercised by the agent.
- The single owner Google Drive connection is `needs_reauth`; real upload smoke remains externally blocked until the owner completes the existing reauthorization flow. No credentials, OAuth state, archive rows, local documents, or remote Drive files were changed by the agent.

## 2026-07-13 - Access Approval Workspace Reactivation Repair

### Status
- Fixed the integration gap between access approval and migration-created inactive workspace owner memberships.
- Current implementation status: implemented, fully regression-tested, and delivered through the production deployment chain in this session; manual Telegram self-approval and acceptance remain the user-driven gate.
- Scope is deterministic Python access/workspace persistence. AI maturity, LLM/STT/LMM authority, business-domain ownership, storage, PDF, and Google Drive behavior are unchanged.

### Behavior
- `approve_user` now runs authorization, access-request decision, optional migrated-membership reactivation, and active-selection restore in one `BEGIN IMMEDIATE` transaction.
- Automatic reactivation is allowed only for exactly one inactive owner membership with one active workspace, one supplier in that workspace, matching `supplier.telegram_id`, one supplier row for the actor, and no competing owner.
- A single existing active membership may have its missing/stale active selection restored.
- Multiple inactive memberships, unsupported membership status, unavailable workspace, supplier mismatch, multiple actor suppliers, or competing ownership fail closed and roll back every approval write.
- Clean approval without existing memberships still creates no workspace, supplier, membership, or selection.
- Public/admin workspace invitation, ownership transfer, claim, and actor merge remain unsupported.
- Configured admins can invoke argument-free `/approve` to self-target through `message.from_user.id`; explicit `/approve <telegram_id>` remains supported for other users, and invalid explicit targets retain the usage error.

### Verification
- `python -m pytest -q tests/test_access_workspace_reactivation.py tests/test_access_request_flow.py tests/test_workspace_context.py tests/test_workspace_profile_service.py` - 35 passed.
- `python -m pytest -q tests/test_access_workspace_reactivation.py tests/test_access_request_flow.py` - 26 passed after adding argument-free admin self-approval.
- Added explicit integration proofs that admin `/approve <telegram_id>` unlocks `/profily` for one verified migrated user and preserves an already registered user's active membership, selection, workspace, supplier, and `/profily` access.
- `python -m pytest -q` - 2137 passed, 7 subtests passed in 314.87s.

## 2026-07-13 - Generic Multi-Workspace Dry-Run Readiness Fix

### Status
- Fixed the stale generic audit/dry-run readiness flag after the successful production migration.
- Current implementation status: production migrated and deployed; public profile runtime ready; same-user two-profile Telegram acceptance still pending.
- Scope is deterministic read-only DB/schema reporting and active migration documentation. AI maturity, LLM/STT/LMM routing, FSM behavior, business writes, storage paths, and runtime handlers are unchanged.

### Changes
- Replaced the hard-coded public_profile_switch_ready=false with a shared readiness assessment derived from required workspace tables/columns, non-null workspace ownership, planner blockers, and workspace/membership/active-selection foundation validity.
- Reused the same assessment in authoritative post-apply validation so generic and apply reports cannot silently diverge.
- Changed already-migrated dry-run output to apply_block_reason=database_already_migrated.
- Closed the generic auditor SQLite read-only connection deterministically, preventing Windows file-handle retention from blocking an immediate tested rollback.
- Added migrated-ready and broken-foundation fail-closed regression coverage.
- Synchronized TZ, architecture proof, migration runbook, and changelog with the 2026-07-13 production migration/deploy evidence and retained backup.

### Production and acceptance boundary
- No server command, DB/storage write, Docker build/restart, Telegram message, or Google Drive call was performed in this fix session.
- The verified backup remains at /var/backups/fakturabot/20260713T173948Z_7408399 and must not be removed before real two-profile acceptance and a later explicit retention decision.
- Real acceptance still requires one authorized actor to create a second profile through /profily, exercise text and voice switching, verify lightweight object isolation, and remove temporary objects through normal product flows if no longer needed.

### Verification
- python -m pytest -q tests/test_multi_workspace_migration.py tests/test_multi_workspace_migration_apply.py - 16 passed.
- python -m pytest -q - 2129 passed, 7 subtests passed in 305.94s (final rerun).
## 2026-07-12 - Production-Safe Multi-Workspace Legacy Migration Apply

### Status
- Implemented local migration dry-run/apply/rollback tooling for the legacy production SQLite shape.
- Current implementation status: migration tooling implemented / locally fixture-proven; real server migration and Docker restart require explicit approval after the updated server read-only dry-run report.
- Scope is deterministic Python DB/storage migration safety. AI maturity and LLM behavior are unchanged.
- No real server DB/storage write, Docker restart, deploy, commit, or push was performed.

### Safety implementation
- Added a redacted read-only planner with deterministic legacy supplier-to-workspace mapping, logical database fingerprint, ownership counts, ambiguity/orphan blockers, no-op/already-migrated detection, and preserved invoice/accounting paths.
- Added apply gates for the exact confirmation token, stopped-writer assertion, unchanged fingerprint, exclusive SQLite lock, blocker-free plan, safe external backup location, and backup disk capacity.
- Added consistent SQLite backup with integrity/fingerprint verification, raw DB/WAL/SHM evidence, invoice/workspace snapshots, and content-hashed storage inventory verification.
- Added separate canonical target DB construction, legacy/unknown column and table preservation, workspace ownership backfill, foundation upsert, source row-count parity, null-ownership audit, and atomic same-directory replacement.
- Added manifest-bound rollback with current DB/storage drift refusal, backup SHA-256/integrity checks, and atomic restore.
- Added emergency restore from the verified pre-apply snapshot when post-swap fingerprint validation is fault-injected to fail.
- Extended the CLI with audit, dry-run, apply, and rollback modes and explicit fingerprint/backup/manifest/confirmation/service-stop arguments.

### Verification
- Focused migration apply/audit fixtures and CLI dry-run: 15 passed.
- Covered round-trip rollback, backup artifacts, path/storage preservation, orphan ownership, confirmation/fingerprint/service-stop gates, active SQLite writer lock, unsafe backup placement, storage drift, mixed foundation state, repeated apply, empty supplier data, and emergency restore.
- Broad migration/workspace regression: 52 passed.
- Full regression: 2128 passed, 7 subtests passed in 309.34s.
- Final whitespace verification passed.

### Operational gate
- The previous server dry-run was produced before this apply implementation and reported the migration gate closed.
- A new read-only server dry-run from the exact candidate code must be presented before requesting approval for server DB apply or Docker restart.
- Apply and restart are separate operational side effects; neither is authorized by this local implementation session.
## 2026-07-12 - Delivery Push And Server Migration Gate

### Status
- Committed and pushed the current multi-workspace runtime plus InfoHelp customization request preview package as `a806df3`.
- Server `/bot/repo` was fast-forwarded to `a806df3` for read-only migration audit, but Docker rebuild/restart was not performed.
- Server dry-run audit reported legacy persisted schemas with missing workspace columns for supplier, contact, service aliases, semantic aliases, invoice, invoice number settings, invoice follow-up, and work-time tables.
- Migration plan reported `apply_available=false` / `public_profile_switch_ready=false`, so production deploy remains blocked by the backup/migration apply/post-apply audit/server-smoke gate.

### Verification
- Local full regression before commit: `python -m pytest -q` - 2118 passed, 7 subtests passed.
- Local whitespace gate: `git diff --check` passed with CRLF warnings only.
- Server audit: `python -m bot.multi_workspace_migration --mode dry-run --db-path /bot/repo/data/storage/fakturabot.db --storage-root /bot/repo/data/storage` completed read-only and redacted tenant values.

## 2026-07-12 - Multi-Workspace Target Runtime Completion And Public Route

### Status
- Implemented the target-schema multi-workspace runtime across contact/service/invoice/accounting/work-time/profile/deletion domains.
- `/profily` and canonical `switch_business_profile` are now locally reachable and classified `partial / target-schema implemented`; production deployment remains blocked by the backup/migration/post-apply/server-smoke gate.
- AI maturity: deterministic Python orchestration with bounded workspace-reference selection and shared DecisionResolver confirmations; no autonomous side effects or cross-workspace model access.

### Implemented
- Bound contact, invoice, accounting-document, supplier-profile, service-alias, and work-time FSMs to their starting workspace with membership revalidation before writes.
- Added workspace-isolated invoice persistence/numbering/edit/delete/PDF/follow-up/analytics and accounting storage/categories/duplicates/archive/analytics.
- Added workspace ownership to target work-time schema/service/settings/events and storage-key-based report paths; legacy schemas remain readable and workspace mode fails closed until migration.
- Expanded account-level exact-confirmation deletion to remove every owned local workspace and related aliases/work-time/archive/customization/foundation rows and storage keys, while leaving remote Drive files/shared provider credentials untouched.
- Added `/profily`, exact membership-scoped selection, add-profile onboarding, idle text routing, voice confirmation, active-FSM switch blocking, active profile display in `/start` and `/menu`, Product Truth, InfoHelp, and registry/TZ updates.

### Verification
- Focused contact/service alias: 44 passed and 16 passed.
- Focused invoice/workspace/handler slices: 317 passed and 250 passed.
- Accounting intake/storage/categories: 69 passed; accounting read/analytics routing: 250 passed.
- Work-time routing/service/voice: 139 passed; workspace work-time proof slice: 75 passed.
- Full-database deletion/tenant safety: 16 passed.
- Profile onboarding/context/selector/router slices: 31 passed, 14 passed, 228 passed, and 4 passed.
- Product Truth and InfoHelp: 126 passed.
- `python -m pytest -q` -> 2118 passed, 7 subtests passed in 304.85s.
- No existing DB migration, storage rewrite, server write, deploy, commit, or push was performed.
## 2026-07-12 - InfoHelp Customization Request Preview Copy

### Status
- Reworked the partial Level 3 customization request preview so user-facing confirmation text is compact Slovak copy addressed to the user, while admin metadata remains in the saved/admin detail path.
- InfoHelp LLM triage prompt now requires Slovak business wording for `admin_review_draft` free-text fields.
- No request storage schema, admin review commands, Product Truth status, server state, or deployment changed.
- Fixed the multi-workspace migration dry-run test fixture so it explicitly simulates legacy `work_time_days` schema when expecting a workspace backfill plan.

### Verification
- `python -m py_compile bot\handlers\invoice.py bot\services\info_help_resolver.py`
- `python -m pytest -q` - 2118 passed, 7 subtests passed.

## 2026-07-12 - Multi-Workspace Invoice Follow-Up And Data Boundaries

### Status
- Continued the partial internal multi-workspace implementation; public /profily and switch_business_profile remain disabled.
- AI maturity is unchanged: this is deterministic Python persistence/routing safety, not a new AI capability.

### Implemented
- Added nullable invoice_followup_state.workspace_id to fresh schemas while accepting legacy schemas without automatic backfill.
- Added WorkspaceInvoiceFollowupService with workspace-isolated payment, snooze, mute, reminder-send, Drive-status, due-list, and background workspace scan operations.
- Restricted legacy follow-up and invoice analytics readers to workspace_id NULL invoice rows on transitional schemas.
- Added background WorkspaceContext resolution from persisted workspace/supplier/membership/authorization state without reading active_workspace_selection.
- Updated the invoice follow-up scheduler to process legacy and workspace rows separately and label workspace notifications with the business profile name.
- Updated follow-up callbacks to resolve the invoice workspace and require actor membership, so switching the active profile after notification cannot retarget the callback.
- Added workspace-aware Drive archive request handling with real workspace_id job ownership instead of telegram-derived workspace keys.
- Added workspace-scoped invoice analytics datasets and immutable storage_key-based PDF target paths; existing persisted invoice.pdf_path values remain unchanged.
- Invoice creation/edit Telegram FSM, contact handlers, accounting documents, work-time, deletion, and remaining archive/storage domains are still not workspace-safe.

### Verification
- workspace follow-up, legacy follow-up, analytics, tenant PDF boundary slice -> 25 passed.
- workspace analytics/PDF plus legacy tenant regression slice -> 20 passed.
- workspace/legacy follow-up handler and analytics regression slice -> 41 passed.
- legacy-schema scheduler compatibility slice -> 21 passed.
- workspace Drive enqueue and archive compatibility slice -> 62 passed.
- python -m pytest -q -> 2108 passed, 7 subtests passed.
- No real DB migration, storage rewrite, server write, deploy, commit, or push was performed.

## 2026-07-11 - Multi-Workspace Foundation Stage 1

### Status
- Corrected the Phase 0 verdict to design_matches_runtime: the Telegram-keyed runtime is the documented migration source shape, not a material contradiction with the approved target design.
- Multi-workspace business profiles remain planned / partial internal foundation; no public /profily route or switch_business_profile action is exposed.

### Implemented
- Added additive workspace, workspace_membership, and active_workspace_selection foundation tables to local DB bootstrap without backfilling or rewriting persisted business data.
- Added shared WorkspaceContextService with authorization-first resolution, active-membership validation, single-membership auto-selection, persisted multi-membership selection, and cross-workspace fail-closed behavior.
- Added read-only multi-workspace audit/dry-run tooling with redacted tenant references, schema/index/row-group inventory, invoice PDF path classification, accounting storage counts, and an explicit unavailable apply gate.
- Added transitional workspace-aware supplier persistence: new schemas use nullable UNIQUE(workspace_id) with non-unique telegram_id actor compatibility; legacy schemas remain readable and are not auto-migrated.
- Added atomic WorkspaceProfileService creation for first/additional modes: workspace, supplier, owner membership, and optional active selection commit together or fully roll back.
- Legacy get_by_telegram_id remains compatible for one profile and fails closed with ambiguous_supplier_profile_requires_workspace when multiple profiles exist.
- Added workspace-isolated contact CRUD with UNIQUE(workspace_id, name), cross-workspace ID/name isolation, actor/workspace mismatch rejection, and a legacy Telegram-scoped facade that fails closed when multiple supplier profiles exist.
- Added workspace-scoped confirmed contact aliases and contact resolution: the same alias may resolve to different contacts in separate workspaces, while foreign contact ids fail closed.
- Preserved legacy confirmed service-alias learning on the transitional alias schema through bounded manual upsert; no alias may silently retarget another service.
- Telegram contact handlers and FSM workspace binding remain Telegram-scoped and are not yet counted as workspace-safe.
- Added workspace-scoped invoice persistence and numbering with UNIQUE(workspace_id, invoice_number), independent first-number settings/sequences, workspace contact ownership validation, and cross-workspace invoice lookup rejection.
- Preserved legacy single-profile invoice creation/numbering, including explicit duplicate-number rejection when target rows still have workspace_id NULL.
- Invoice follow-up/payment/reminders, analytics datasets, PDF path builders, and Telegram handlers remain outside this completed service slice.
- Kept existing Telegram-scoped business services unchanged until migration tooling and every mandatory domain are workspace-safe.

### Verification
- python -m pytest -q tests/test_workspace_context.py -> 5 passed.
- python -m pytest -q tests/test_multi_workspace_migration.py tests/test_workspace_context.py -> 8 passed.
- python -m pytest -q tests/test_access_request_flow.py tests/test_archive_job_service.py tests/test_work_time_service.py -> 81 passed.
- python -m pytest -q tests/test_access_request_flow.py tests/test_archive_job_service.py tests/test_work_time_service.py tests/test_product_truth.py -> 106 passed.
- python -m pytest -q tests/test_workspace_profile_service.py tests/test_workspace_context.py tests/test_supplier_smtp_optional.py tests/test_onboarding_decisions.py -> 21 passed.
- broader tenant/invoice/delete/migration regression slice -> 83 passed.
- python -m pytest -q -> 2082 passed, 7 subtests passed.
- workspace contact + contact normalization/intake/onboarding/tenant slice -> 53 passed.
- python -m pytest -q after contact schema changes -> 2086 passed, 7 subtests passed.
- workspace contact aliases + legacy contact/service alias regression slice -> 102 passed.
- python -m pytest -q after confirmed alias schema changes -> 2088 passed, 7 subtests passed.
- workspace invoice/numbering + tenant focused gate -> 17 passed.
- broad invoice analytics/follow-up/edit/prerouter regression slice -> 396 passed.
- python -m pytest -q after invoice/numbering schema changes -> 2096 passed, 7 subtests passed.
- Product Truth and InfoHelp were not promoted because no public multi-profile capability is reachable; current user-facing status remains planned/unsupported until the readiness gate passes.
- Local real-data audit was not run because storage/fakturabot.db is absent in this workspace.
- No real DB migration, server write, deploy, commit, or push was performed.
## 2026-07-11 - Architecture And LLM Docs Reorganization

Summary:
- Created `docs/architecture/` as the active folder for architecture/design-proof documents.
- Moved OfficeFlow architecture/storage proposal docs under `docs/architecture/`.
- Added `docs/architecture/MULTI_WORKSPACE_BUSINESS_PROFILES_ARCHITECTURE_DESIGN_PROOF.md` from the handoff-ready design proof file.
- Moved the LLM orchestrator contract to `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`.
- Updated active README/AGENTS/current-doc/code references to the new paths.

Scope:
- Touched scopes: documentation organization, active documentation references, and Product Truth source-reference strings only.
- No runtime code behavior, DB/storage schema, migrations, LLM/STT/LMM routing, FSM flows, server state, tests, or deployment changed.
- Current implementation status for multi-workspace business profiles remains `planned / unsupported in current runtime` until implementation, migration, Product Truth/InfoHelp updates, tests, and acceptance proof are complete.

Verification:
- Documentation-only reorganization; no runtime tests required.
- Read-only path/reference audit performed with `rg`.

## 2026-07-10 - Agent Documentation Preflight Rule

Summary:
- Updated `AGENTS.md` to require relevant `docs/` preflight before non-trivial work, project-rule compliance, mismatch reporting, and repair proposals when docs/code/logs/runtime evidence disagree.
- Clarified that meaningful work sessions should update the relevant active `docs/` source of truth when behavior, architecture, capability truth, AI/LLM contracts, storage, access, deployment, or user-facing workflows change.
- Clarified that existing active docs should be updated before creating new docs, and that trivial read-only answers or commands do not require documentation churn.

Scope:
- Touched scopes: agent workflow documentation and project log only. No runtime code, tests, server, DB/storage, product behavior, parser, LLM routing, or deployment changed.

Verification:
- Documentation-only change; no runtime tests required.

## 2026-07-10 - OfficeFlow Work-Time Report Period Slots

Summary:
- Recorded the defect/root cause: the earlier work-time report month flow incorrectly trusted Python text parsing for natural-language month semantics after the top-level action was known. That violates the bounded LLM contract because Python should validate/default structured slots, not own multilingual month dictionaries as the primary path.
- Integrated bounded LLM period slots for `generate_work_time_report`: the top-level resolver can now return `slots.period` with `month` 1-12 and optional `year` for phrases such as `покажи табель рабочего времени за May`.
- Kept Python as validator/executor: it validates structured month/year, defaults missing year/month from the Europe/Bratislava business date, and only uses the older text month parser for no-LLM/legacy direct calls.
- Confirmed report files are generated on demand under `storage_dir/work_time_reports/<telegram_id>/dochadzka_YYYY_MM.xlsx`; DB rows remain canonical and an existing same-month file is overwritten by regeneration.

Scope:
- Touched scopes: top-level LLM routing payload/diagnostics, work-time report period validation, LLM contract/checklist governance, tests, canonical registry, changelog/project log. No DB schema, parser dictionary expansion, invoice/accounting side effects, lunch math, report Excel layout, STT prompt, or server state changed.
- Current implementation status: `partial` work-time MVP unchanged; selected report month routing is now bounded LLM-slot aware when an API key is configured.
- AI maturity level: bounded semantic canonicalization with Python-owned validation/defaults and deterministic report generation.

Verification:
- Focused tests cover LLM period slot capture, router-to-handler period passing, Python defaults for missing year/month, invalid month rejection, and existing report generation flow.
- Contract/checklist docs now explicitly forbid making Python broad human-language dictionaries the primary owner for bounded variable slot interpretation.

## 2026-07-10 - LLM Action Hint Boundary Contract

Summary:
- Tightened the LLM Orchestrator Contract for ambiguous top-level semantic actions: compact `action_hints` are now mandatory when allowed-action tokens alone cannot separate nearby meanings.
- Made `meaning`, `positive_examples`, and `not_this` required fields for hinted actions, with examples treated as illustrative semantic context rather than literal whitelists.
- Added boundary coverage requirements for overlapping verbs, shared business nouns, top-level vs in-action/subflow meanings, and read/write or destructive/read-only separation.

Scope:
- Touched scopes: AI orchestration contract and project log only. No runtime code, parser dictionaries, STT prompt, LLM routing implementation, DB/storage, invoice/accounting/work-time handlers, tests, deploy, or server state changed.
- Current implementation status: governance/documentation contract update for future bounded resolver bundle work.
- AI maturity level: contract-level bounded semantic canonicalization guidance; no new runtime capability or side effect.

Verification:
- Read-only diff review of `docs/FakturaBot_LLM_Orchestrator_Contract.md`.
## 2026-07-10 - OfficeFlow Work-Time Report Bundle Examples

Summary:
- Corrected the previous work-time report routing hotfix to follow the bounded resolver contract: removed Ukrainian/Russian timesheet variants from the Python report fast-path and moved the timesheet context into the LLM `positive_examples` for `generate_work_time_report`.
- Strengthened the `generate_work_time_report` semantic boundary with a broader `meaning` and explicit `not_this` separations from add/open/close/delete/lunch/payroll actions.
- Added tests proving the top-level bundle includes `Покажи табель рабочего времени` as a contextual positive example and that `Покажи мені табель працівного часу.` is resolved through the LLM bundle path, not by expanding Python phrase dictionaries.

Scope:
- Touched scopes: top-level semantic routing bundle, tests, changelog/project log. No voice.py phrase dictionary, parser dictionary, slot extraction, DB schema, invoice/accounting flow, timezone, lunch math, or report generation change.
- Current implementation status: `partial` work-time MVP unchanged; this is a routing-bundle quality repair for an existing top-level action.
- AI maturity level: bounded semantic canonicalization with Python-owned allowed actions and LLM contextual examples; no new side effects and no self-learning.

Verification:
- `python -m pytest -q tests\test_work_time_routing.py` - 33 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py` - 222 passed.
- `git diff --check` - clean (Git reported existing LF-to-CRLF normalization warnings only).
## 2026-07-10 - OfficeFlow Work-Time Report Timesheet Routing

Summary:
- Investigated live top-level routing miss where STT text `Покажи мені табель працівного часу.` returned `unknown` instead of `generate_work_time_report`.
- Strengthened the bounded top-level work-time report fast-path for Ukrainian/Russian timesheet/table wording such as `табель`, `табелю`, `робочого/працівного часу`, while preserving Python-owned allowed-action routing.
- Updated the `generate_work_time_report` action hint so the LLM understands show/generate timesheet/report wording as the same OfficeFlow work-time report intent.
- Kept voice.py free of work-time phrase dictionaries and did not touch parser dictionaries, slot extraction, DB schema, invoice/accounting flows, timezone, lunch math, or report generation.

Docs/contracts read:
- `AGENTS.md`, `docs/Product_Doctrine_2030.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`, `docs/Product_Truth_Registry_MVP_Design.md`, `docs/Self_Learning_Layer.md`, `docs/Evaluation_and_Smoke_Test_Standards.md`, `docs/Product_UX_Eval_Artifacts.md`, `docs/TZ_FakturaBot.md`, `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/llm/New_Action_Design_Checklist.md`, `docs/llm/Bounded_Resolver_Prompt_Template.md`, and `docs/local-only/FakturaBot_Server_Agent_Context.md`.

Preflight/status:
- Touched scopes: top-level semantic routing, LLM action hint, tests, changelog/project log, server deploy. No confirmation, FSM, STT prompt, LMM, storage, DB, access, PDF/layout, Product Truth status, InfoHelp capability, self-learning, or report-generation semantics changed.
- Current implementation status: `partial` work-time MVP unchanged; this is a routing-quality repair for an existing implemented canonical action.
- AI maturity level: bounded semantic canonicalization repair inside existing Python-owned action resolver; no new autonomous execution and no new product capability claim.
- Product/user journey proof: user can say `Покажи мені табель працівного часу.` and the resolver returns `generate_work_time_report` instead of `unknown`.
- Self-learning hooks considered: none; broad action-alias learning is not implemented and this fix remains registry/test-owned.

Verification:
- `python -m pytest -q tests\test_work_time_routing.py` - 33 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py` - 221 passed.
- `git diff --check` - clean (Git reported existing LF-to-CRLF normalization warnings only).
## 2026-07-09 - Active FSM Navigation and Stale-State Guard

Summary:
- Added a shared active-FSM navigation/stale-state guard in `bot/services/active_fsm_guard.py`, wired as message middleware after authorization and reused by `voice.py` after STT.
- Added bounded active-FSM navigation classification in `bot/services/decision_resolver.py` with only `cancel_current_flow`, `show_main_menu`, `resume_start_status`, and `pass_through` outputs.
- Reused existing Python behavior: `cancel_current_state()`, `cmd_menu()` / `MENU_MESSAGE`, `cmd_start()` / staged status, and existing idle `process_invoice_text()` only after stale-state clearing.
- Added shared FSM activity metadata and timeout policy: destructive exact confirmation 5 minutes, destructive confirmation 10 minutes, preview/decision/choice 15 minutes, data-entry 30 minutes.
- Added stale callback guards for shared `decision:*` callbacks and timestamped `invoice_followup:*` callbacks; legacy/missing/expired callbacks fail closed before save/delete/pay/send/mark-paid side effects.
- Deferred fresh active-FSM safe switch confirmation because the current idle top-level route executes actions directly and there is no proven dry-run probe plus previous-FSM restore contract.

Docs/contracts read:
- `AGENTS.md`, `docs/Product_Doctrine_2030.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`, `docs/Product_Truth_Registry_MVP_Design.md`, `docs/Self_Learning_Layer.md`, `docs/Evaluation_and_Smoke_Test_Standards.md`, `docs/Product_UX_Eval_Artifacts.md`, `docs/TZ_FakturaBot.md`, `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/llm/New_Action_Design_Checklist.md`, `docs/llm/Bounded_Resolver_Prompt_Template.md`, `docs/Canonical_Decision_Resolver_Contract.md`, OfficeFlow/Document Intake contracts, `docs/User_Access_Model_Roadmap.md`, and the affected handlers/tests.

Preflight/status:
- Touched scopes: routing, FSM, voice/STT post-processing, DecisionResolver-adjacent bounded navigation, callback safety, docs/tests/log. No DB schema, storage model, PDF/layout, access model, Product Truth capability, InfoHelp capability, server, deployment, or self-learning change.
- Current implementation status: `implemented` for explicit active-FSM navigation and stale-state recovery; `implemented` for covered stale callbacks; `deferred` for fresh active-FSM safe switch confirmation.
- AI maturity level: bounded Python-owned canonicalization inside an active FSM guard; no new autonomous execution or product capability claim.
- Product/user journey proof: active `/menu`, `/start`, `/cancel` and semantic navigation escape old FSM states; stale work-time/invoice/document states do not parse later requests as old state input; stale approve/delete/pay/save-like replies and callbacks fail closed.
- Self-learning hooks considered: none; navigation, stale recovery, and callback expiry must not learn aliases or mutate semantic memory.
- Source of truth for user-facing claims: runtime code and this log; Product Truth/InfoHelp not updated because this is a safety/runtime behavior, not a user-visible business capability.

Verification:
- `python -m pytest -q tests\test_active_fsm_guard.py tests\test_decision_resolver.py tests\test_decision_callbacks.py tests\test_invoice_followup_handler.py tests\test_voice_state_routing.py` - 749 passed.
- `python -m pytest -q tests\test_accounting_document_intake_flow.py tests\test_officeflow_attachment_router.py tests\test_active_fsm_guard.py tests\test_voice_state_routing.py` - 154 passed.
- `python -m pytest -q` - 2061 passed, 7 subtests passed.
- `git diff --check` - clean (Git reported existing LF-to-CRLF normalization warnings only).

Known follow-up gap:
- Fresh active FSM + clear new top-level business request still requires explicit navigation/cancel or future safe switch confirmation. Do not implement safe switch until a top-level dry-run/probe and exact previous FSM state/data restore are proven by tests.
## 2026-07-09 - OfficeFlow Work-Time Close Input Recovery

Summary:
- Investigated 2026-07-08 live logs for the failed close-day smoke: STT and top-level routing selected `close_work_day`, but the unresolved `16.07` input did not keep the user in close-time input state, so the follow-up `16:07` was routed as idle top-level `unknown`.
- Fixed `start_close_work_day()` to enter `WorkTimeStates.waiting_close_input` when the close action is recognized but the close time/duration is missing or ambiguous.
- Added close-candidate support for plain `HH:MM` replies such as `16:07` in the active close flow, while keeping dotted `16.07` from being treated as a time.
- Kept parser dictionaries, LLM intent routing, DB schema, invoice/accounting flows, timezone, and lunch math unchanged.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py` - 69 passed.
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py tests\test_voice_state_routing.py` - 132 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2042 passed, 7 subtests passed.

## 2026-07-04 - OfficeFlow Work-Time Delete Routing Disambiguation

Summary:
- Strengthened top-level action hints so mixed Ukrainian/Latin requests like `vidali dochadzku` are treated as OfficeFlow work-time month deletion, not outgoing invoice deletion.
- Added regression coverage for both local resolver priority and the full `process_invoice_text` path, while preserving invoice-specific deletion such as `vidaliti fakturu 02`.
- Kept parser dictionaries, work-time slot extraction, DB schema, invoice deletion execution, accounting flows, timezone, and lunch math unchanged.

Verification:
- `python -m pytest -q tests\test_work_time_routing.py tests\test_invoice_intent_prerouter.py::test_process_invoice_text_top_level_hints_disambiguate_work_time_delete_from_invoice_delete tests\test_invoice_intent_prerouter.py::test_process_invoice_text_mixed_dochadzka_delete_routes_to_work_time_not_invoice` - 33 passed.
- `python -m pytest -q tests\test_work_time_routing.py tests\test_invoice_intent_prerouter.py` - 252 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2041 passed, 7 subtests passed.

## 2026-07-03 - OfficeFlow Work-Time Preview h:mm Duration Display

Summary:
- Fixed Telegram work-time preview, saved-day summaries, and month/delete summaries to display durations as `h:mm` instead of decimal-hour labels such as `8,4 hod.`.
- Kept stored `total_minutes`, lunch math, duration-only semantics, Excel `[h]:mm` report values, parser/LLM/routing/timezone/DB/invoice/accounting flows unchanged.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py` - 67 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2038 passed, 7 subtests passed.

## 2026-07-03 - OfficeFlow Work-Time Excel h:mm Duration Display

Summary:
- Changed generated work-time Excel report duration cells from decimal-hour text to Excel duration values formatted as `[h]:mm`.
- Updated the report header from `Hodiny` to `Hodiny (h:mm)` and kept totals as full elapsed hours so values over 24 hours render as totals such as `100:30`.
- Kept Prichod/Odchod as `HH:MM`, lunch math semantics unchanged, duration-only rows unchanged semantically, and parser/LLM/routing/timezone/DB/invoice/accounting flows out of scope.

Verification:
- `python -m pytest -q tests\test_work_time_service.py` - 36 passed.
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py` - 67 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2038 passed, 7 subtests passed.
- `python -m pytest -q tests\test_voice_state_routing.py tests\test_decision_resolver.py` - 706 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2037 passed, 7 subtests passed.
- `git diff --check` - clean.
## 2026-07-03 - OfficeFlow Work-Time Bratislava Runtime Clock

Summary:
- Fixed OfficeFlow work-time runtime `now`/`today` semantics to use IANA timezone `Europe/Bratislava` by default through `OFFICEFLOW_TIMEZONE`.
- Added centralized work-time clock helpers in `bot/services/work_time.py` for local now/date and timezone resolution, with warning + fallback to Bratislava on invalid timezone values.
- Updated open-day, close-now, relative date parsing, default report month, and bounded work-time slot `today_iso` to use the work-time local date/time instead of server/container UTC.
- Preserved parser dictionaries, LLM intent routing, invoice/blocek/accounting flows, DB schema, close-now safety, and lunch math.

Docs/contracts read:
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/TZ_FakturaBot.md`, `bot/services/work_time.py`, `bot/handlers/work_time.py`, `bot/handlers/voice.py`, and focused work-time tests.

Preflight/status:
- Touched scopes: work-time runtime clock, bounded slot extraction payload date, strict parser default date, report month default, env examples, README, TZ, canonical registry, changelog, project log, tests.
- Current implementation status: `partial` OfficeFlow work-time MVP.
- AI maturity level: unchanged; Python-owned runtime clock feeding bounded LLM slot context, no new LLM authority.
- Persisted data impact: no schema migration and no existing data rewrite; new writes use Bratislava local clock going forward.
- Product/user journey proof: UTC `2026-07-03T09:37:00Z` opens as `11:37`, UTC `2026-07-03T15:45:00Z` close-now saves `17:45`, and UTC midnight boundary `2026-07-03T22:30:00Z` resolves to local date `2026-07-04`.
- Self-learning hooks considered: none; this is runtime clock configuration, not learned behavior.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` - 771 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_info_help.py tests\test_product_truth.py` - 344 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2036 passed, 7 subtests passed.
- `git diff --check` - clean.
## 2026-07-03 - OfficeFlow Work-Time Close-Now Safety Fix

Summary:
- Fixed the post-af03b94 close-day safety gap: unclear close input now returns a clarification prompt and never falls through to `close_now`.
- Added explicit `mode` support to bounded work-time slot extraction (`manual_range`, `manual_duration`, `close_at_time`, `close_with_duration`, `close_now`, `unknown`) and made missing/unknown/invalid modes fail safe.
- Kept broad natural-language interpretation in the bounded LLM layer; strict parser fallback now accepts numeric HH:MM/HH.MM ranges only and does not learn verbal/Cyrillic broad phrase dictionaries.
- Preserved preview-before-save, DecisionResolver approve/edit/cancel, lunch net/gross math, delete-month flow, Product Truth, InfoHelp, invoice, blocek/accounting, and voice routing boundaries.

Docs/contracts read:
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Bounded_Resolver_Prompt_Template.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `bot/handlers/work_time.py`, `bot/services/work_time.py`, `bot/handlers/voice.py`, and focused work-time/voice/decision tests.

Preflight/status:
- Touched scopes: LLM slot extraction, close-day FSM safety, strict parser fallback, work-time routing tests, service tests, canonical/in-action registry docs, changelog, project log.
- Current implementation status: `partial` OfficeFlow work-time MVP.
- AI maturity level: bounded Python-owned action execution with LLM slot canonicalization inside already-selected work-time actions; no new Product Truth capability, customization request, or self-learning behavior added.
- Persisted data impact: no schema migration and no existing data rewrite; the change prevents accidental close writes and preserves the existing confirmation-gated write path.
- Product/user journey proof: unclear close text keeps the day open, explicit `teraz` closes now, exact close time and close duration show preview until approve, and Cyrillic natural ranges from the bounded LLM stay manual ranges rather than duration-only entries.
- Self-learning hooks considered: none added; slot extraction is bounded per-request normalization, not learned aliases.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` - 765 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_info_help.py tests\test_product_truth.py` - 344 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2030 passed, 7 subtests passed.
- `git diff --check` - clean.
- `rg -n "work_time|dochadz|zatvor|teraz|od 6|do 11|manual_range|close_now" bot\handlers\voice.py` - only state dispatch references, no work-time phrase dictionary.

## 2026-07-03 - OfficeFlow Work-Time Bounded LLM Slot Extraction

Summary:
- Moved work-time manual-entry and close-day slot extraction to bounded LLM-first normalization after the top-level resolver has already selected the work-time action.
- The LLM may return only `work_time_entry` slots (`date`, `start_time`, `end_time`, `duration_minutes`) or `unknown`; Python validates the date/time/duration shape, previews the candidate, applies lunch/net rules where relevant, and saves only after approval.
- Added prompt guidance for explicit numeric dates (`1.07`, `1.07.2026`, `1 na 7`), multilingual/verbal ranges, duration-only requests, and capability-style questions that should return `unknown` instead of becoming executable entries.
- Kept deterministic parser support as fallback for missing API key, bounded-LLM errors, and focused local/dev tests, not as the primary natural-language interpretation layer.

Docs/contracts read:
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Bounded_Resolver_Prompt_Template.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `bot/handlers/work_time.py`, `bot/services/work_time.py`, and focused work-time tests.

Preflight/status:
- Touched scopes: LLM slot extraction, FSM work-time manual/close entry, fallback parser hardening, canonical/in-action registry docs, changelog, project log, tests.
- Current implementation status: `partial` OfficeFlow work-time MVP.
- AI maturity level: bounded Python-owned action execution with LLM slot canonicalization inside an already-selected work-time action; no new Product Truth capability, customization request, or self-learning behavior added.
- Persisted data impact: no schema migration and no existing data rewrite; only new candidate normalization before the existing preview/confirmation write path.
- Product/user journey proof: natural text like `1 na 7 z 6.00 do 11.00`, `1.07.2026 pracoval 6 hodin`, and Cyrillic-style natural ranges resolve to the intended date/time/duration candidate before preview instead of defaulting to today's duration entry.
- Self-learning hooks considered: none added; slot extraction is bounded per-request normalization, not learned aliases.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` - 754 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_info_help.py tests\test_product_truth.py` - 344 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2019 passed, 7 subtests passed.
- `git diff --check` - clean.
## 2026-07-03 - OfficeFlow Work-Time Preview/Edit UX Polish

Summary:
- Fixed manual work-time preview/edit recovery after the b45525d live smoke: `_preview_manual_candidate` now receives `config` explicitly and no longer crashes or goes silent after edit input.
- Unknown replies in manual and close preview states now repeat the full pending preview with date, arrival, departure, net hours, and approve/edit/cancel buttons instead of a naked confirmation prompt.
- Active preview FSM state still wins over text/voice top-level report requests; voice dispatch remains STT -> same state-aware handler path with no work-time phrase dictionary in `voice.py`.
- Added real UTF-8 yesterday parsing for `vcera`, `v?era`, `?????`, `?????`, and `?????`, plus clearer duration-only preview/saved-summary wording.
- Kept lunch-break net/gross semantics, delete-month behavior, global InfoHelp unknown fallback, invoice, blocek/accounting, and admin-request preview/buttons out of scope.

Docs/contracts read:
- `AGENTS.md`, `README.md`, `PROJECT_LOG.md`, `CHANGELOG.md`, `docs/Product_Doctrine_2030.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/Canonical_Decision_Resolver_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/llm/New_Action_Design_Checklist.md`, `bot/handlers/work_time.py`, `bot/services/work_time.py`, `bot/handlers/voice.py`, `bot/services/semantic_action_resolver.py`, `bot/services/decision_resolver.py`, and focused work-time/voice/decision tests.

Preflight/status:
- Touched scopes: FSM, confirmation recovery, voice state routing tests, work-time parsing/display, in-action registry, changelog, project log, tests.
- Current implementation status: `partial` OfficeFlow work-time MVP.
- AI maturity level: bounded state-aware in-FSM control under existing Level 2 Product Truth/InfoHelp truth; no new top-level capability, no customization request, and no self-learning behavior added.
- Persisted data impact: no schema migration and no data rewrite; display wording and parsing only.
- Product/user journey proof: edit -> corrected range returns preview/buttons, unknown text/voice in pending previews repeats full context, Cyrillic/Slovak yesterday resolves to the previous date, duration-only rows no longer display as `- - -`, and existing lunch/delete-month regressions stay covered.
- Self-learning hooks considered: none added; this is deterministic FSM recovery and parser support.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` - 750 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_info_help.py tests\test_product_truth.py` - 344 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2015 passed, 7 subtests passed.
- `git diff --check` - clean.

## 2026-07-02 - OfficeFlow Work-Time Lunch Break Settings And Net Report Hours

Summary:
- Added `update_work_time_lunch_break` for setting, changing, or disabling a fixed lunch-break deduction after preview confirmation.
- Added first-report lunch setup so an authorized user is asked once whether lunch should be deducted before the monthly report is generated.
- Corrected report semantics to show net hours: explicit start/end rows subtract the configured lunch break, while duration-only rows keep the user-confirmed net duration stable and store a lunch snapshot/audit mode.
- Kept payroll, salary, legal HR compliance, multi-employee attendance, export, automatic break detection, and generated-report deletion out of scope.

Docs/contracts read:
- `AGENTS.md`, `README.md`, `PROJECT_LOG.md`, `CHANGELOG.md`, `docs/Product_Doctrine_2030.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`, `docs/Product_Truth_Registry_MVP_Design.md`, `docs/Self_Learning_Layer.md`, `docs/Evaluation_and_Smoke_Test_Standards.md`, `docs/Product_UX_Eval_Artifacts.md`, `docs/TZ_FakturaBot.md`, `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/llm/New_Action_Design_Checklist.md`, `docs/llm/Bounded_Resolver_Prompt_Template.md`, `docs/Info_Help_Guidance_Layer.md`, `docs/Customization_Request_Layer.md`, `docs/Canonical_Decision_Resolver_Contract.md`, `docs/User_Access_Model_Roadmap.md`, `docs/FakturaBot_Data_Migration_Runbook.md`, and focused work-time/voice/decision/product truth/help code.

Preflight/status:
- Touched scopes: routing, FSM, confirmation/buttons, voice state routing, additive DB schema, work-time report generation, Product Truth, InfoHelp, docs, tests.
- Current implementation status: `partial` OfficeFlow work-time MVP.
- AI maturity level: bounded canonical top-level action routing plus Level 2 Product Truth/InfoHelp truth sync; no customization request or self-learning behavior added.
- Persisted data impact: additive nullable `work_time_days` columns and additive user-scoped `work_time_settings`; existing rows are not rewritten and legacy rows remain readable.
- Product/user journey proof: first report asks lunch yes/no, approval saves settings and sends report, later report skips setup, update/disable lunch is confirmation-gated, voice routes through state/top-level routing, report totals use net semantics, and delete-month still deletes only selected current-user DB rows after confirmation.
- Self-learning hooks considered: none added; lunch-break wording is canonical routing/settings behavior, not learned aliases.

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` - 743 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_info_help.py tests\test_product_truth.py` - 344 passed.
- `$env:PYTHONIOENCODING='utf-8'; python -m pytest -q` - 2008 passed, 7 subtests passed.
- `git diff --check` - clean.

## 2026-07-02 - OfficeFlow Work-Time Month Deletion Flow

Summary:
- Added `delete_work_time_month` for deleting stored OfficeFlow work-time / dochadzka DB records for one selected month after destructive preview confirmation.
- The flow resolves explicit month/year, asks for month/year when missing, exits without confirmation when no rows exist, previews row count and total hours, and deletes only current `telegram_id` scoped `work_time_days` plus related `work_time_events` for that month after confirmation.
- Documented that generated monthly Excel reports are on-demand artifacts, not canonical stored attendance data; deletion removes DB work-time records only.
- Kept global InfoHelp unknown-business fallback, invoice, blocek/accounting, payroll/legal HR, export, automatic detection, and generated-report file deletion out of scope.

Docs/contracts read:
- `AGENTS.md`, `README.md`, `PROJECT_LOG.md`, `CHANGELOG.md`, `docs/Product_Doctrine_2030.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`, `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/Canonical_Decision_Resolver_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/llm/New_Action_Design_Checklist.md`, work-time handler/service code, voice routing, semantic action resolver, and focused work-time/voice/decision tests.

Preflight/status:
- Touched scopes: routing, FSM, confirmation/buttons, voice state routing, work-time DB delete side effect, Product Truth, InfoHelp known work-time text, docs, tests.
- Current implementation status: `partial` OfficeFlow work-time MVP.
- AI maturity level: bounded canonical top-level action routing plus Level 2 Product Truth/InfoHelp truth sync; no new customization request or self-learning behavior.
- Side effects: confirmed deletion from existing user-scoped SQLite `work_time_days` and related `work_time_events`; no schema migration, no server writes, no external services.
- Product/user journey proof: text/voice can start monthly deletion, missing month asks clarification, empty month has no destructive confirmation, existing month previews count/hours, cancel preserves rows, approve deletes only the current user's selected-month rows.
- Self-learning hooks considered: none added; delete wording is a canonical resolver action, not learned aliases.

Verification:
- `python -m pytest -q tests\\test_work_time_service.py tests\\test_work_time_routing.py tests\\test_voice_state_routing.py tests\\test_decision_resolver.py` - 754 passed.
- `python -m pytest -q tests\\test_invoice_intent_prerouter.py tests\\test_info_help.py tests\\test_product_truth.py` - 344 passed.
- `='utf-8'; python -m pytest -q` - 2019 passed, 7 subtests passed.
- `git diff --check` - clean.

## 2026-07-01 - OfficeFlow Work-Time / Dochadzka MVP

Summary:
- Added partial OfficeFlow work-time tracking with top-level actions `open_work_day`, `close_work_day`, `add_work_time_entry`, and `generate_work_time_report`.
- Added additive SQLite tables `work_time_days` and `work_time_events`, scoped by `telegram_id`; no existing data rewrite or migration repair was performed.
- Added `/dochadzka`, work-time FSM handlers, preview-confirmed exact time writes, shared DecisionResolver-backed callbacks/voice/text paths, Product Truth and InfoHelp coverage, and monthly Excel report generation.
- Kept payroll, salary calculation, legal HR attendance compliance, multi-employee attendance, accounting/payroll export, automatic time detection, and official payroll document claims out of scope.

Docs/contracts read:
- `AGENTS.md`, `docs/Product_Doctrine_2030.md`, `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`, `docs/Product_Truth_Registry_MVP_Design.md`, `docs/Self_Learning_Layer.md`, `docs/Evaluation_and_Smoke_Test_Standards.md`, `docs/Product_UX_Eval_Artifacts.md`, `docs/TZ_FakturaBot.md`, `docs/FakturaBot_LLM_Orchestrator_Contract.md`, `docs/llm/Canonical_Action_Registry.md`, `docs/llm/In_Action_Response_Registry.md`, `docs/llm/New_Action_Design_Checklist.md`, `docs/llm/Bounded_Resolver_Prompt_Template.md`, `docs/Info_Help_Guidance_Layer.md`, `docs/Customization_Request_Layer.md`, `docs/Canonical_Decision_Resolver_Contract.md`, `docs/User_Access_Model_Roadmap.md`, OfficeFlow intake/storage docs, and `docs/FakturaBot_Data_Migration_Runbook.md` for additive schema safety.

Preflight/status:
- Touched scopes: routing, FSM, confirmation, voice, DB schema, storage/report file output, Product Truth, InfoHelp, docs, tests.
- Current implementation status: `partial`.
- AI maturity level: Level 2 capability-aware Product Truth/InfoHelp coverage plus deterministic Python-owned action execution; no Level 3 customization save and no Level 4 self-learning added.
- Product/user journey proof: user can start a day, close it, add a manual interval after preview, and generate a monthly report; Product Truth honestly answers work-time/payroll capability questions.
- Self-learning hooks considered: none added; work-time aliases are canonical actions, not learned aliases.
- User-facing claims are backed by runtime code, Product Truth registry, canonical action docs, InfoHelp docs, and focused tests.

Docs updated:
- `README.md`
- `docs/TZ_FakturaBot.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/evals/product_truth_infohelp_smoke.md`
- `CHANGELOG.md`

Verification:
- `python -m pytest -q tests\test_work_time_service.py tests\test_work_time_routing.py` -> 14 passed.
- `python -m pytest -q tests\test_decision_resolver.py` -> 581 passed.
- `python -m pytest -q tests\test_product_truth.py tests\test_info_help.py` -> 125 passed.
## 2026-07-01 - Contact wizard recovery hint and inactivity timeout

Summary:
- Added `/menu` to contact creation recovery hints, including the first company-name prompt, so users have a visible clickable escape from the text-first contact wizard.
- Added a five-minute inactivity timeout for contact FSM states; expired contact sessions clear on the next contact-state input before processing user data.
- Kept voice exact-value entry out of scope: company/contact identifiers remain text-first, and no new top-level action or DB/storage schema change was added.

Docs/contracts checked or updated:
- `docs/TZ_FakturaBot.md`
- `docs/llm/In_Action_Response_Registry.md`
- `CHANGELOG.md`

Verification:
- `python -m pytest -q tests\test_contact_intake_semantic_flow.py tests\test_voice_state_routing.py tests\test_state_control.py` -> 82 passed.
## 2026-07-01 - Google Drive documentation truth sync after live smoke

Summary:
- Reconciled Google Drive docs/registries after live owner OAuth smoke.
- Marked Drive as integrated `partial` owner OAuth runtime when configured, not unsupported/stub-only and not full SaaS/per-client sync.
- Updated stale mark-paid and due-date follow-up registry text that still claimed real Drive upload never occurs.
- Added live smoke evidence for invoice `20260006`: mark-paid created an `invoice_pdf` archive job, the archive worker uploaded it to Google Drive, DB status became `uploaded`, and the local PDF remained available.
- Recorded the receipt-year incident: two receipts were extracted under 2023 and repaired to 2026; current guard rejects receipt issue dates before 2026, but before 2027 this should become an explicit configurable accepted-year/window policy to allow legitimate January prior-year backfill.

Docs/source documents checked or updated:
- `README.md`
- `docs/TZ_FakturaBot.md`
- `docs/Google_Drive_Service_Account_Owner_Run_MVP.md`
- `docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md`
- `docs/Google_Drive_Faktury_Bloceky_Storage_Policy.md`
- `docs/Google_Drive_Token_Crypto_Operations.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `bot/services/product_truth.py` (registry already partial; `last_verified_at` updated to 2026-07-01)
- `bot/services/info_help.py`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/evals/product_truth_infohelp_smoke.md`
- `CHANGELOG.md`

Verification:
- Documentation-only sync; runtime smoke evidence came from live DB/log inspection after invoice `20260006` upload.

## 2026-07-01 - Receipt 2023 year repair and receipt date guard

Summary:
- Repaired two live confirmed receipt metadata/archive records that had been saved under year 2023 after LMM date extraction errors.
- Moved local metadata from `years/2023` to `years/2026`, updated DB `archive_jobs` and `accounting_document_archive_state`, and moved/renamed the corresponding owner OAuth Google Drive files into the 2026 receipt folders.
- Added a Python validation guard that rejects receipt issue dates before 2026 before confirmed save can derive storage paths, metadata JSON, archive jobs, or Drive upload state.
- Product Truth and TZ now state this receipt date boundary honestly.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_Data_Migration_Runbook.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/TZ_FakturaBot.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Touched scopes:
- storage/DB/server: yes, live metadata paths and archive rows repaired after backup; local receipt originals were already deleted by confirmed Drive upload retention.
- Google Drive: yes, two uploaded receipt files were renamed and moved to 2026 receipt folders through owner OAuth.
- runtime validation: yes, receipt date guard before confirmed save.
- LMM/STT/routing/FSM/confirmation/access/PDF layout: no behavior change.
- Product Truth/docs/tests/project log: updated.

Safety and rollback:
- Server backup created at `/bot/data/storage/migration_backups/receipt-2023-year-repair-20260701090216` before apply.
- No token, OAuth secret, service-account JSON, or Telegram ID was written to docs/logs.
- Post-repair audit found zero receipt archive rows or metadata files under `years/2023`.

Verification:
- Live DB/storage audit found the two repaired records under `years/2026` with issue dates `2026-03-26` and `2026-06-14`.
- Live Drive validation confirmed both files renamed and untrashed in the new 2026 folders.
- `python -m pytest tests/test_accounting_document_storage.py tests/test_accounting_document_extraction.py -q` -> 31 passed.

## 2026-06-30 - Google Drive owner OAuth archive MVP switch

Summary:
- Switched the Google Drive MVP direction from service-account personal My Drive upload to single-owner OAuth mode.
- Added manual/local owner OAuth bootstrap for authorization URL generation and code exchange into encrypted refresh-token storage.
- Added an owner OAuth archive provider that refreshes credentials and uploads through the existing archive worker contract.
- Preserved archive job/retention semantics: receipt and incoming originals are deleted only after confirmed upload plus DB state `uploaded`; metadata JSON and invoice PDFs remain local.
- Product Truth/InfoHelp/docs now classify Google Drive archive as `partial`, `requires_setup`, `requires_admin`, and `requires_external_credentials`, with service-account personal My Drive marked unsupported unless Workspace/Shared Drive is configured later.

Contracts read:
- `AGENTS.md`
- `docs/Product_Doctrine_2030.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Self_Learning_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/FakturaBot_Data_Migration_Runbook.md`
- `docs/Google_Drive_Token_Crypto_Operations.md`
- `docs/Google_Drive_Service_Account_Owner_Run_MVP.md`
- `docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md`

Touched scopes:
- runtime/config: yes, Drive mode default and owner OAuth provider/bootstrap;
- routing/top-action: no new top-level action;
- confirmation: no new confirmation family;
- LLM/STT/LMM: no model calls or prompt authority changes;
- FSM: no active FSM changes;
- storage/DB: existing `google_drive_connections` encrypted token row and existing `archive_jobs`; no schema migration;
- access: setup remains owner/admin controlled;
- PDF/layout: no PDF layout changes; local invoice PDFs remain local;
- Product Truth/InfoHelp/evals/docs: updated.

Implementation status:
- `partial`: single-owner Google Drive archive via owner OAuth for configured deployments.
- `unsupported`: service-account personal My Drive archive without Workspace/Shared Drive, per-client OAuth Drive, SaaS Drive sync, bank matching, bank-confirmed settlement, local invoice PDF deletion.
- AI maturity: Level 2 Product Truth/InfoHelp truth update for this capability; runtime integration remains deterministic Python-owned with no LLM execution authority.

Safety and retention:
- No OAuth secrets, authorization codes, access tokens, refresh tokens, encrypted token blobs, or service-account JSON are logged or documented as real values.
- Missing OAuth credentials/token/root folder/API dependency produces bounded not-configured/retry behavior without deleting local files.
- Manual smoke requires real owner credentials; unit tests must fake Google API calls.

Verification:
- `python -m compileall bot tests` -> passed.
- `python -m pytest -q tests\test_google_drive_service_account_archive.py tests\test_archive_worker.py tests\test_archive_job_service.py tests\test_accounting_document_archive_service.py tests\test_invoice_followup_handler.py tests\test_invoice_followup_service.py tests\test_google_oauth_token_exchanger.py tests\test_google_drive_connection_service.py tests\test_google_drive_oauth_state_service.py tests\test_google_drive_oauth_callback_service.py tests\test_google_drive_oauth_callback_app.py tests\test_google_drive_setup_commands.py tests\test_product_truth.py tests\test_info_help.py` -> 356 passed before adding explicit fail-closed owner OAuth tests.
- `python -m pytest -q tests\test_google_drive_service_account_archive.py` -> 12 passed after adding explicit owner OAuth missing connection/client-secret/folder-id fail-closed tests.
- `git diff --check` -> passed.
- Full `python -m pytest -q` -> passed locally before final audit; rerun after log update before commit.

## 2026-06-30 - Google Drive owner-run service-account archive MVP

Summary:
- Implemented partial owner-run Google Drive archive via service account, not per-client OAuth and not SaaS Drive sync.
- Added lazy Google Drive adapter, archive scheduler, invoice archive enqueue service, config/env placeholders, and retention policy for confirmed accounting originals.
- Existing accounting archive jobs now upload receipts/incoming invoices through the worker when Drive is enabled; invoice PDFs are enqueued after mark-paid/control events and remain local.
- Product Truth/InfoHelp now classify Google Drive invoice storage/archive as `partial` with setup/admin/external-credential requirements.

Contracts read:
- `AGENTS.md`
- `README.md`
- `PROJECT_LOG.md`
- `CHANGELOG.md`
- `docs/TZ_FakturaBot.md`
- `docs/Product_Doctrine_2030.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Self_Learning_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/Implementation_Agent_Checklist.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/FakturaBot_Data_Migration_Runbook.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/Google_Drive_Invoice_Archive_After_Due_Date_Spec.md`
- `docs/Google_Drive_Token_Crypto_Operations.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

Touched scopes:
- runtime/config: yes, Google Drive owner-run service-account archive config and scheduler;
- routing/top-action: no new top-level action;
- confirmation: no new confirmation family; mark-paid keeps existing confirmation gates;
- LLM/STT/LMM: no model calls or prompt changes;
- FSM: no active FSM fallthrough changes;
- storage/DB: additive archive-job document type behavior and follow-up Drive archive status values; no server data migration run;
- access: no authorization boundary change;
- PDF/layout: no PDF layout changes; local invoice PDFs remain local;
- Product Truth/InfoHelp/evals/docs: updated.

Implementation status:
- `partial`: owner-run Google Drive archive via service account for configured deployments.
- `unsupported`: per-client OAuth Drive, SaaS Drive sync, bank matching, bank-confirmed settlement, local invoice PDF deletion.
- AI maturity: Level 2 Product Truth/InfoHelp truth update for this capability; runtime integration remains deterministic Python-owned with no LLM execution authority.

Safety and retention:
- Service-account JSON must stay out of Git; `.gitignore` excludes common service-account JSON names.
- Missing credentials/root folder/API dependency produces bounded `google_drive_not_configured` retry state without deleting local files.
- Receipt/incoming originals are deleted only after upload success and DB state `uploaded`, controlled by env flags.
- Metadata JSON and invoice PDFs are not deleted by this MVP.

Verification:
- `python -m compileall bot tests` -> passed.
- `python -m pytest -q tests\test_google_drive_service_account_archive.py tests\test_archive_worker.py tests\test_archive_job_service.py tests\test_accounting_document_archive_service.py tests\test_invoice_followup_handler.py tests\test_invoice_followup_service.py tests\test_product_truth.py tests\test_info_help.py` -> 217 passed.
- Manual Google Drive smoke not run: no real service-account credentials or shared Drive root folder were provided in this workspace.

## 2026-06-28 - Session 161 - Invoice analytics unpaid filter semantics

### Goal
Fix the analytics-layer gap where a muted but still unpaid overdue outgoing invoice could disappear from user questions asking for unpaid/not-paid invoices.

### Preflight
- Docs/contracts read: AGENTS.md, Invoice Analytics Runtime Contract, Product Truth/InfoHelp references, eval smoke artifact, and prior follow-up/reminder specs from the current session.
- Touched scopes: read-only invoice analytics dataset catalog, planner prompt/validation, existing analytics handler catalog call, Product Truth/InfoHelp wording, eval/docs, tests, changelog.
- Current status: `partial` invoice analytics runtime, corrected semantic filter contract; no DB schema, storage, server, reminder callback, or paid-state write behavior changed.
- AI maturity: unchanged bounded analytics layer; Python owns status semantics and validates planner output.
- Out of scope: marking invoices paid, migrations, server deploy, bank reconciliation, real payment confirmation, and Google Drive upload.

### Changes
- Added Python-owned payment-status filter groups and multilingual filter hints to `build_invoice_analytics_data_catalog(user_question=...)`.
- Defined unpaid/not-paid/neuhradene/nezaplatene/neoplatene semantics as `payment_status_canonical` in `pending_payment` plus `overdue`; `overdue` wording remains overdue-only.
- Tightened the invoice analytics planner prompt and added validation that rejects hinted payment-status plans missing required canonical values, especially `overdue` for unpaid questions.
- Passed the user question into the invoice analytics data catalog from `_run_invoice_analytics(...)`.
- Documented that muted/snoozed reminders are not payment truth and updated Product Truth, InfoHelp, eval smoke, and changelog.

### Verification
- `python -m pytest -q tests/test_invoice_analytics_dataset.py tests/test_invoice_analytics_planner.py tests/test_safe_python_analytics_executor.py tests/test_product_truth.py tests/test_info_help.py` - 173 passed.
- `python -m pytest -q` - 1874 passed, 7 subtests passed.
- `git diff --check` - passed.

### Notes
- Live/server inspection before this patch showed invoice `20260006` had `payment_status=unpaid`, `reminder_status=muted`, and an overdue due date; the stored state was correct. The bug was the analytics filter semantics, not the reminder callback.

## 2026-06-22 - Session 160 - Manual mark existing invoice paid MVP

### Goal
Implement the MVP top-level action for marking one saved outgoing invoice as paid/uhradena after explicit confirmation.

### Preflight
- Docs/contracts read: AGENTS.md, Product Doctrine, AI Layer standards, Product Truth, InfoHelp, Evaluation/UX standards, LLM orchestrator contract, canonical/in-action registries, New Action checklist, bounded resolver template, DecisionResolver contract, TZ, Drive archive stub spec, and PROJECT_LOG.md.
- Touched scopes: routing, confirmation, voice/STT routing, FSM, existing DB write service, Product Truth, InfoHelp, docs, tests.
- Current status: supported MVP for manual bot-local paid state; no bank matching, no bank confirmation, no real Google Drive upload.
- AI maturity: bounded top-level action canonicalization plus Product Truth-backed guidance; deterministic Python owns all side effects.
- Out of scope: DB schema changes, PDF layout/content edits, invoice deletion/editing, bank integrations, server/deploy, migrations, external services.

### Changes
- Added canonical `mark_existing_invoice_paid` top-level action with supplier-scoped invoice lookup and `mark_existing_invoice_paid_confirm` DecisionResolver confirmation.
- Added confirmation buttons: `Ozna?i? ako uhraden?` and `Sp?? do hlavn?ho menu`.
- Routed text, voice, and decision callbacks to the same handler.
- Persisted only `invoice_followup_state.payment_status=paid` through `InvoiceFollowupService.mark_paid()` and recorded the existing local Drive archive stub.
- Updated Product Truth, InfoHelp, canonical/in-action docs, TZ, Drive stub spec, eval smoke, changelog, and tests.

### Verification
- `python -m compileall -q bot tests` - passed.
- Focused new mark-paid tests - 9 passed.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_invoice_state_decisions.py tests/test_decision_callbacks.py tests/test_decision_resolver.py tests/test_voice_state_routing.py tests/test_product_truth.py tests/test_info_help.py` - 1060 passed.
- `python -m pytest -q` - 1869 passed, 7 subtests passed.

### Notes
- No DB schema, storage layout, PDF path, or invoice content changes.
- No real Google Drive, bank matching, or bank-confirmed payment claim was added.

## 2026-06-21 - Session 159 - Accounting document analytics category contract hardening

### Goal
Fix the receipt/incoming-invoice analytics planner gap where category questions could be planned with model-invented translated `category_label` filters instead of Python-provided confirmed `category_id` values.

### Changes
- Added Python-provided `allowed_categories`, category aliases, and `category_filter_hints` to the accounting document analytics data catalog.
- Passed workspace storage, workspace key, and the user question into the planner catalog from the runtime handler.
- Tightened the planner prompt so category filters must use `category_id` from `data_catalog.allowed_categories` and obey `category_filter_hints` when present.
- Added planner validation that rejects plans missing the hinted `category_id` filter column/id before execution.
- Added multilingual regression tests for Ukrainian/Slovak category wording such as `пальне`, `palivo`, and `pohonné látky` resolving to `vehicle_fuel`.
- Updated `docs/llm/Accounting_Document_Analytics_Runtime_Contract.md` to make Python-owned category semantics explicit.

### Verification
- Focused analytics tests passed locally after the hardening patch.
- Live prompt smoke over representative category questions verified that the planner selected `vehicle_fuel`, `materials`, and `tools` category ids instead of invented labels.

### Notes
- This was a contract gap in the first accounting document analytics rollout: previous smoke coverage proved top-level routing/action separation, but did not prove semantic category normalization inside generated analytics plans.
- No DB schema changes.
- No storage writes or migrations.
- No analytics expansion beyond confirmed receipt/incoming-invoice metadata.

# PROJECT_LOG

## 2026-06-21 - Session 158 - Accounting analytics action-boundary smoke hardening

Summary:
- Added smoke/regression tests proving `accounting_document_analytics` does not
  steal existing outgoing invoice analytics, add-receipt, recent-document, or
  show-existing-invoice routes, and `invoice_analytics` does not answer
  bloček/incoming-invoice expense questions.
- Added handler-level smoke coverage proving unsupported bank/DPH/tax/export
  wording over bločky enters the customization preview and never reaches either
  analytics planner.
- Fixed guard vocabulary for Slovak `daňovo uznateľné`, `bankové/bankovými`,
  and `pohyby/pohybmi`, and made InfoHelp classify bank/DPH/tax analytics before
  receipt/accounting-document analytics.

Preflight:
- Contracts checked: Safe Data Analyst Runtime Checklist and Canonical Action
  Registry boundaries for analytics actions.
- Touched scopes: semantic routing tests, InfoHelp capability order,
  unsupported-domain guard terms, changelog, project log. Not touched: DB,
  storage, LMM extraction, migrations, server/deploy, category persistence, or
  analytics write behavior.
- Current implementation status remains `partial` for read-only accounting
  document analytics and `unsupported` for bank/cashflow/DPH/tax/export/full
  accounting analytics.
- AI maturity level unchanged: Level 2 bounded analytics with Python-owned
  scope, validation, and no side effects.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py::test_smoke_analytics_action_boundaries_do_not_steal_existing_routes tests/test_invoice_intent_prerouter.py::test_smoke_unsupported_accounting_document_analytics_never_reaches_planner tests/test_invoice_intent_prerouter.py::test_smoke_infohelp_distinguishes_analytics_capability_questions`
  - 21 passed.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_info_help.py tests/test_product_truth.py tests/test_voice_state_routing.py tests/test_accounting_document_analytics_dataset.py tests/test_accounting_document_analytics_planner.py tests/test_accounting_document_analytics_executor.py tests/test_accounting_document_analytics_answerer.py`
  - 407 passed.
- `git diff --check`
  - passed with Windows LF-to-CRLF warnings only.

## 2026-06-21 - Session 157 - Accounting document analytics runtime pilot

Summary:
- Added canonical top-level action `accounting_document_analytics` as a partial
  read-only runtime pilot for confirmed receipts/bloceky and incoming
  invoices/prijate faktury.
- Added workspace-scoped sanitized metadata dataframe construction, planner
  bounds, process-isolated AST-validated execution, and Slovak final-answer
  grounding for expense-side accounting document analytics.
- Synced Product Truth, InfoHelp, canonical registry, orchestrator contract,
  TZ, README, eval smoke artifact, tests, changelog, and project log.

Preflight:
- Docs/contracts read: AGENTS, Product Doctrine, AI Layer Standards, Safe Data
  Analyst Runtime Checklist, Product Truth Layer/Registry, Self-Learning,
  Evaluation and Smoke Test Standards, Product UX Eval Artifacts, TZ,
  Orchestrator Contract, Canonical Action Registry, In-Action Response Registry,
  New Action Checklist, Bounded Resolver Prompt, InfoHelp, Customization
  Request Layer, DecisionResolver, OfficeFlow/Document Intake docs, User Access,
  and the existing invoice analytics runtime contract.
- Touched scopes: routing, LLM planner prompt, analytics executor sandbox,
  final answerer, storage metadata reads, Product Truth, InfoHelp, docs,
  tests. Not touched: STT provider, LMM extraction, DB schema, migrations,
  server/deploy, runtime storage writes, PDF layout, bank/tax/export flows.
- Current implementation status: `partial` for read-only accounting document
  analytics; `partial` for receipt analytics as a Product Truth alias of that
  runtime; `unsupported` for bank/cashflow/VAT/tax/accounting export/full
  accounting analytics.
- AI maturity level: Level 2 bounded analytics interpretation/explanation with
  Python-owned data scope, validation, sandboxed execution, and no side effects.
- Explicitly out of scope: category creation/management from analytics,
  tax/accounting judgement, VAT reporting, bank matching, accounting export,
  DB/storage migrations, and automatic persistence of suggested labels.
- Product journey proof: an authorized idle user can ask a natural text/voice
  question such as `Koľko som minul v BAUHAUS?`, Python reads only confirmed
  current-workspace receipt/incoming-invoice metadata, executes a bounded
  read-only analysis, returns a Slovak answer, clears state, and creates no
  DB/file/category side effect.
- Self-learning hooks considered: no learning was added; analytics questions
  remain bounded by canonical action routing and Python-provided dataframe
  schema, not learned aliases or mutable registries.
- Product claim sources: current code/tests, Product Truth entries
  `accounting_document_analytics` and `receipt_analytics`,
  `docs/llm/Accounting_Document_Analytics_Runtime_Contract.md`, canonical
  registry, TZ, README, eval smoke artifact, and this log.

Verification:
- `python -m pytest -q tests/test_accounting_document_analytics_dataset.py tests/test_accounting_document_analytics_planner.py tests/test_accounting_document_analytics_executor.py tests/test_accounting_document_analytics_answerer.py`
  - 18 passed.
- `python -m pytest -q tests/test_product_truth.py`
  - 23 passed.
- `python -m pytest -q tests/test_info_help.py`
  - 98 passed.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py`
  - 192 passed.
- `python -m pytest -q tests/test_voice_state_routing.py::test_voice_idle_accounting_document_analytics_reaches_top_level_router tests/test_voice_state_routing.py::test_voice_idle_invoice_analytics_reaches_top_level_router tests/test_voice_state_routing.py::test_voice_idle_recent_accounting_documents_routes_to_existing_view`
  - 3 passed.

## 2026-06-21 - Session 156 - README receipt category truth sync

Summary:
- Synced README with the deployed receipt/incoming-invoice category MVP: category preview, bounded category changes, workspace category creation after typed-label confirmation, and category metadata snapshots.
- Removed the stale README claim that receipt/bloček categorization is not implemented; kept receipt analytics/category totals/reporting as not implemented.

Preflight:
- Docs/contracts checked: README, TZ, Document Intake Module Proposal, In-Action Response Registry, Product Truth/InfoHelp evidence from runtime tests.
- Touched scopes: docs only.
- Not touched: runtime code, tests, DB, server storage, Product Truth code, InfoHelp code, analytics, tax/accounting export, bank matching.
- Current implementation status: `partial` receipt/incoming-invoice categorization inside existing Document Intake preview flow; receipt analytics remains planned/unsupported.

Verification:
- `git diff --check`
  - passed.

## 2026-06-21 - Session 155 - Receipt category selection recovery controls

Summary:
- Added create-new/back controls at the end of existing-category selection during receipt/incoming-invoice categorization.
- `create_new_category` reuses the existing typed-label plus confirmation flow; no category is persisted from the list button alone.
- `back` returns an unknown-category document back to the previous unknown-category menu instead of trapping the user in the existing-category list.

Preflight:
- Docs/contracts read: AGENTS, Canonical DecisionResolver Contract, Document Intake Module Proposal, In-Action Response Registry.
- Touched scopes: accounting document category FSM, DecisionResolver category-selection family, docs, changelog, tests.
- Not touched: DB schema, migrations, storage paths, LMM extraction payload, top-level canonical actions, analytics, tax/accounting export, bank matching.
- Current implementation status: `partial` receipt/incoming-invoice category UX recovery inside existing preview flow only.
- AI maturity level: Level 1/2 UX hardening around existing Python-gated category selection; no new AI authority.
- Out of scope: standalone category management, analytics, automatic category creation, or persistence without typed label and explicit confirmation.

Verification:
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_decision_resolver.py`
  - 605 passed.
- `python -m compileall bot`
  - passed.
- `git diff --check`
  - passed.
- `PYTHONIOENCODING=utf-8 python -m pytest -q`
  - 1786 passed, 7 subtests passed.

## 2026-06-21 - Session 154 - Receipt intake button UX follow-up

Summary:
- Made the deterministic duplicate warning visually loud with `POZOR! Tento doklad už je uložený!!!!` and explicit `Pridať iný bloček`, `Uložiť aj tak`, and `/menu` reply buttons.
- Added explicit `Áno` / `Nie` reply buttons to the idle photo/PDF receipt proposal before entering accounting document preview processing.
- Kept both confirmation-like paths routed through `bot/services/decision_resolver.py`; buttons send visible bounded text into the active FSM and do not add a top-level action.

Preflight:
- Docs/contracts read: AGENTS, Canonical DecisionResolver Contract, Document Intake Module Proposal, OfficeFlow Storage Model Proposal, In-Action Response Registry, local server runbook before deployment.
- Touched scopes: accounting document FSM UX, idle attachment FSM UX, DecisionResolver button-label normalization, docs, changelog, focused tests.
- Not touched: DB schema, migrations, confirmed storage layout, LMM extraction payload, top-level canonical actions, Product Truth capability scope, analytics, tax/accounting export, bank matching.
- Current implementation status: `partial` for receipt/incoming-invoice document intake UX; no new analytics or accounting judgment capability.
- AI maturity level: Level 1/2 UX hardening around existing deterministic Python-gated flows.
- Out of scope: receipt analytics, category management top-level action, automatic duplicate deletion, automatic save, or server data migration.
- User journey proof: authorized user sends a receipt photo, sees explicit `Áno` / `Nie` proposal buttons, and duplicate receipts show a loud warning before any save-anyway path.

Verification:
- `python -m compileall bot`
  - passed.
- `python -m pytest -q tests/test_officeflow_attachment_router.py`
  - 29 passed.
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_decision_resolver.py tests/test_officeflow_attachment_router.py`
  - 632 passed.
- `PYTHONIOENCODING=utf-8 python -m pytest -q`
  - 1784 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-20 - Session 153 - Receipt Category MVP v1

Summary:
- Implemented controlled receipt/incoming-invoice categories inside the existing
  accounting Document Intake preview flow, not as a new top-level action.
- Added system categories plus workspace-scoped custom categories persisted
  under the workspace master-data category registry.
- Extended LMM extraction to receive Python-provided `allowed_categories` and
  return candidate-only document/line-item categories or `unknown_review`.
- Added category preview decisions, unknown-category handling, existing
  category selection, confirmation-gated new category creation, similar-label
  protection, and save-with/save-without-category paths through
  `bot/services/decision_resolver.py`.
- Persisted confirmed category metadata as category ids plus `label_snapshot`;
  old metadata without category remains readable and no storage paths are moved.
- Synced Product Truth, InfoHelp, TZ, Document Intake docs, in-action registry,
  eval smoke, changelog, and tests. Receipt analytics remains planned.

Preflight:
- Docs/contracts read: AGENTS, Product Doctrine 2030, AI Layer Implementation
  Standards, Product Truth Layer, Product Truth Registry MVP Design,
  Self-Learning Layer, Evaluation and Smoke Test Standards, Product UX Eval
  Artifacts, TZ, LLM Orchestrator Contract, Canonical Action Registry,
  In-Action Response Registry, New Action Design Checklist, Bounded Resolver
  Prompt Template, Info Help Guidance Layer, Customization Request Layer,
  Confirmed Semantic Alias Learning Contract, Code Agent Handoff Contract,
  Implementation Agent Checklist, Data Migration Runbook, Canonical
  DecisionResolver Contract, OfficeFlow Architecture Framing, OfficeFlow
  Storage Model Proposal, Document Intake Module Proposal, Document Intake MVP
  Implementation Plan, User Access Model Roadmap, PROJECT_LOG, CHANGELOG, and
  the accounting extraction prompt.
- Touched scopes: LMM extraction prompt/wrapper/parser, accounting document FSM,
  voice routing for active accounting states, DecisionResolver category
  families, confirmed metadata shape, workspace storage for category registry,
  Product Truth, InfoHelp, docs/evals/tests.
- Not touched: top-level canonical actions, STT implementation, LMM provider
  calls beyond payload/prompt shape, DB schema, existing confirmed file paths,
  server runtime, PDF layout, bank/tax/export/Drive integrations, or receipt
  analytics execution.
- Current implementation status: `partial` for receipt/incoming-invoice
  category capture; `planned` for receipt analytics; `unsupported` for tax
  advice, bank matching, accounting export, and VAT/category totals.
- AI maturity level: Level 2/4 boundary for bounded candidate extraction and
  controlled workspace category learning only after user confirmation. This is
  not analytics, accounting judgment, or adaptive workflow automation.
- Out of scope: standalone category management, `categorize_receipt` top-level
  action, broad document categories, data migration, category analytics,
  Google Drive sync, accounting export, tax/VAT conclusions, or automatic
  category creation by the model.
- User journey proof: authorized user starts `/add_blocek`, uploads a
  receipt/PDF, sees bounded category candidates, resolves unknown categories
  by choosing existing or confirming a new workspace category, previews changes,
  and only final save persists category snapshots.
- Self-learning hooks considered: workspace category creation is controlled,
  tenant-scoped, confirmation-gated, and reused only through future
  `allowed_categories` payloads. No action aliases or Product Truth learning
  were added.
- Product claim sources: current code/tests, Product Truth entry
  `accounting_document_categories`, Document Intake docs, TZ, in-action
  registry, eval smoke, and this log.

Verification:
- `python -m compileall bot`
  - passed.
- `python -m pytest -q tests/test_decision_resolver.py tests/test_accounting_document_extraction.py tests/test_accounting_document_intake_flow.py`
  - 601 passed.
- `python -m pytest -q tests/test_accounting_document_extraction.py tests/test_accounting_document_categories.py`
  - 26 passed.
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_accounting_document_lmm.py tests/test_accounting_document_storage.py tests/test_product_truth.py tests/test_info_help.py`
  - 182 passed.
- `python -m pytest -q`
  - 1776 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-20 - Session 152 - Safe analytics checklist failure register

Summary:
- Updated `docs/llm/Safe_Data_Analyst_Runtime_Checklist.md` with a mandatory
  failure register and repair playbook for LLM-generated read-only analytics
  runtimes.
- Recorded the 2026-06-20 invoice analytics failures and fixes: unsupported
  receipt/expense analytics preview state, overly broad yearly fast path,
  partial period dictionaries, planner repair/logging, explicit invoice-number
  show/edit routing, and Telegram-smoke-driven coverage.
- Documented the current analytics layer model: bounded top-level routing,
  unsupported-domain guard, bounded execution-strategy gate, narrow
  deterministic whole-year fast path, planner semantics/code workflow, Python
  validation/execution, repair loop, Slovak final answer policy, and read-only
  side-effect boundary.
- Integrated the same rules into the active checklist logic: authority split,
  temporal logic, planner prompt, handler tests, product UX smoke, implementation
  order, and pre-deploy checks now require the bounded strategy/guard/repair
  model instead of only recording it as a past failure.

Scope:
- Documentation only. No runtime code, DB/storage, server state, Product Truth,
  InfoHelp, or deployment changes.

Verification:
- Documentation-only update; tests not run.

## 2026-06-20 - Session 151 - Invoice analytics planner workflow and repair loop

Summary:
- Tightened the `invoice_analytics` planner prompt into a generic workflow:
  normalize the user request into Slovak FakturaBot business semantics, identify
  analysis kind, period, date column, row filters, required dataframe columns,
  sandbox-safe pandas code, and self-check that the computed result can answer
  the request.
- Added a bounded planner repair loop: if generated code fails planning,
  validation, or sandbox execution, Python logs the sanitized reason and sends
  structured repair feedback back to the planner before showing a user-facing
  fallback.
- Replaced the yearly fast-path gate with a bounded execution-strategy decision
  (`whole_calendar_year_summary` vs `safe_analytics_runtime`) when an LLM key is
  available, so month, quarter, date-range, customer/status/list/comparison,
  and ambiguous-period questions do not depend on partial month-name
  dictionaries before reaching the safe analytics runtime.
- Fixed the top-level resolver priority for explicit existing-invoice number
  references so `show/edit/delete invoice 04` style requests stay in the
  existing invoice flows instead of being captured by invoice analytics; plain
  four-digit years such as `2026` are not treated as invoice-number references.
- Kept final user-facing invoice analytics answers Python-controlled as Slovak
  business language; planner `answer_language` remains metadata only.

Preflight:
- Docs/contracts read: AGENTS, AI Layer Implementation Standards, Safe Data
  Analyst Runtime Checklist, Product Truth Layer, FakturaBot LLM Orchestrator
  Contract, Invoice Analytics Runtime Contract, current planner/handler/tests,
  and focused memory notes for invoice analytics/Slovak final answers.
- Touched scopes: invoice analytics planner prompt, handler retry/fallback
  behavior, yearly fast-path gate, runtime logging, contract docs, tests,
  project log. Not touched:
  DB schema, storage, PDF generation, authorization, STT/LMM, Product Truth
  status, receipt/bank/tax analytics support, server/deploy.
- Current implementation status: `partial` read-only invoice analytics pilot.
- AI maturity level: Level 2 bounded analytics interpretation/explanation with
  Python validation and no side effects; this is not full accounting analytics
  and not adaptive workflow.
- Out of scope: hardcoding March/May behavior, adding receipt analytics,
  changing tenant scoping, or promising a result after all safe repair attempts
  fail.
- User journey proof: a non-yearly invoice analytics request can recover from a
  rejected generated code plan through structured repair feedback and then
  return a Slovak business answer from Python-computed results; a quarter
  invoice analytics question is routed to safe analytics runtime instead of the
  deterministic yearly summary; smoke coverage now includes new invoice
  analytics phrasings, exact `покажи фактуру 04` / `upraviť fakturu 05` routes,
  and the unsupported `покажи видатки за цей рік` guard.

Verification:
- `python -m pytest -q tests\test_invoice_analytics_planner.py tests\test_invoice_intent_prerouter.py::test_invoice_analytics_validation_stop_logs_reason tests\test_invoice_intent_prerouter.py::test_invoice_analytics_repairs_invalid_generated_code_before_user_fallback tests\test_invoice_intent_prerouter.py::test_process_invoice_text_runs_invoice_analytics_without_side_effects tests\test_safe_python_analytics_executor.py tests\test_invoice_analytics_answerer.py`
  - 44 passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_product_truth.py tests\test_info_help.py tests\test_voice_state_routing.py`
  - 354 passed.
- `python -m pytest -q`
  - 1715 passed, 7 subtests passed.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py -k "smoke or unsupported_expense_domains or quarter_invoice_question"`
  - 17 passed, 169 deselected.
- `python -m pytest -q tests\test_invoice_intent_prerouter.py -k "show_existing_invoice or edit_existing_invoice or nearby_invoice_top_actions"`
  - 8 passed, 178 deselected.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-20 - Session 150 - Invoice analytics routing and InfoHelp honesty guards

Summary:
- Demoted `invoice_period_summary` from the public top-level routing surface;
  simple calendar-year invoice count/total wording now reaches
  `invoice_analytics` and can use the deterministic yearly summary only as an
  internal read-only fast path.
- Added Python-side unsupported-domain guards before invoice analytics
  calculation for receipt, expense, incoming-invoice, bank, cashflow, VAT, tax,
  and similar accounting analytics wording. Safe unsupported business analytics
  requests now start the existing confirmation-gated customization/admin-review
  preview flow; no request row is saved before approval.
- Updated Product Truth, InfoHelp, contracts, README/TZ, changelog, and focused
  tests so month/multi-month invoice questions route to invoice analytics while
  unsupported plausible analytics requests stay honest and offer an
  admin/customization-review path.

Preflight:
- Docs/contracts read: AGENTS, Product Doctrine 2030, AI Layer Implementation
  Standards, Product Truth Layer, Product Truth Registry MVP Design,
  Self-Learning Layer, Evaluation and Smoke Test Standards, Product UX Eval
  Artifacts, TZ, LLM Orchestrator Contract, Canonical Action Registry,
  In-Action Response Registry, New Action Design Checklist, Bounded Resolver
  Prompt Template, Info Help Guidance Layer, Customization Request Layer,
  Confirmed Semantic Alias Learning Contract, Invoice Analytics Runtime
  Contract, README, PROJECT_LOG, and CHANGELOG.
- Touched scopes: routing, LLM bounded resolver inputs, user-facing InfoHelp,
  Product Truth, docs/contracts, tests, project log, changelog. Not touched:
  STT/LMM behavior, storage layout, DB schema, authorization model,
  server/deploy, PDF layout, or persisted data migration.
- Current implementation status: `partial` for read-only invoice analytics;
  `unsupported` for receipt/expense/incoming-invoice/bank/cashflow/VAT/tax
  analytics; `planned` for future receipt/category analytics prerequisites.
- AI maturity level: partial Level 2 capability-aware honesty for analytics
  questions plus deterministic Python-gated read-only analytics routing. This
  is not Level 3 customization persistence and not Level 7 adaptive workflow.
- Explicitly out of scope: receipt or expense analytics, bank matching,
  VAT/tax advice, Google Drive analytics, new DB/storage writes, automatic
  category learning, or weakening authorization/confirmation gates.
- Product journey proof: an approved user asking a March/May invoice question
  reaches `invoice_analytics`; a simple current-year invoice summary reaches
  `invoice_analytics` and may use the yearly fast path; a receipt/check expense
  analytics question is refused before calculation, enters the customization
  request preview state with approve/edit/cancel controls, and does not save a
  request before confirmation.
- Self-learning hooks considered: no new learning was added because these
  requests are routing and truth-boundary behavior, not confirmed reusable
  aliases or user-approved account preferences.
- User-facing product claims are backed by current code, Product Truth,
  InfoHelp guidance, active LLM contracts, README/TZ, and tests.

Verification:
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_info_help.py tests\test_product_truth.py tests\test_voice_state_routing.py`
  - 344 passed.
- `python -m pytest -q`
  - 1704 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-18 - Session 149 - Product Truth and InfoHelp analytics truth sync

Summary:
- Synced README, TZ, Product Truth, and InfoHelp guidance after the Safe Data
  Analyst Runtime pilot.
- Made Product Truth/InfoHelp distinguish partial read-only invoice analytics
  from planned receipt/blocek analytics and unsupported bank/cashflow/VAT/tax
  /full accounting analytics.
- Kept this as a truth/documentation and self-knowledge update only: no new
  receipt analytics, receipt categories, incoming invoice analytics, bank
  analytics, or invoice analytics runtime behavior was implemented.

Preflight:
- Docs/contracts read: AGENTS, README, TZ, Product Truth Layer, InfoHelp
  Guidance Layer, Canonical Action Registry, Safe Data Analyst Runtime
  Checklist, Invoice Analytics Runtime Contract, Product Truth/InfoHelp code,
  focused tests, PROJECT_LOG, and CHANGELOG.
- Touched scopes: documentation, Product Truth registry, InfoHelp deterministic
  capability classification/rendering, tests, project log, changelog.
- Current implementation status: `partial` for invoice analytics, `planned`
  for receipt analytics prerequisites, `unsupported` for bank/cashflow/VAT/tax
  /full accounting analytics.
- Out of scope: new analytics domains, receipt categorization/storage,
  invoice analytics executor/planner/runtime changes, DB/storage writes,
  server/deploy changes.

Verification:
- `python -m pytest -q tests/test_product_truth.py`
  - 21 passed.
- `python -m pytest -q tests/test_info_help.py`
  - 93 passed.
- `python -m pytest -q tests/test_invoice_analytics_answerer.py`
  - 1 passed.
- `python -m pytest -q tests/test_invoice_analytics_planner.py`
  - 18 passed.
- `python -m pytest -q tests/test_safe_python_analytics_executor.py`
  - 21 passed.
- `python -m pytest -q`
  - 1695 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-18 - Session 148 - Safe data analyst checklist and analytics language policy

Summary:
- Added `docs/llm/Safe_Data_Analyst_Runtime_Checklist.md` as the reusable
  checklist for future read-only LLM-generated analytics runtimes.
- Recorded the invoice analytics pilot lessons: raw lifecycle status is not
  payment/business truth, LLM boilerplate imports need narrow normalization,
  Docker/Linux process timeout behavior must be verified in production, and
  final business answer language must be Python-controlled.
- Updated the invoice analytics runtime contract to reference the universal
  checklist while keeping invoice-specific dataset/payment semantics and
  unsupported boundaries in the invoice contract.
- Hardened `invoice_analytics` final-answer behavior so planner
  `answer_language` metadata cannot override the default Slovak business
  answer policy.

Preflight:
- Docs/contracts read: AGENTS, AI Layer Implementation Standards, FakturaBot
  LLM Orchestrator Contract, Product Truth Layer, Evaluation and Smoke Test
  Standards, Invoice Analytics Runtime Contract, PROJECT_LOG, and recent
  invoice analytics commits `b65e72a`, `da048f2`, `95d5419`, and `d812502`.
- Touched scopes: LLM planner prompt, final answerer prompt/payload, invoice
  analytics handler handoff, docs/contracts, tests, project log, changelog.
- Current implementation status: `partial` for invoice analytics; no new
  receipt, incoming invoice, bank, tax, accounting, or write analytics domain
  was implemented.
- AI maturity level: bounded read-only analytics pilot remains under the
  existing partial runtime model.
- Out of scope: executor policy changes, scheduler/deploy changes, new data
  domains, DB/storage writes, Google Drive upload, payment semantics changes.

Verification:
- `python -m pytest -q tests/test_invoice_analytics_answerer.py`
  - 1 passed.
- `python -m pytest -q tests/test_invoice_analytics_planner.py`
  - 18 passed.
- `python -m pytest -q tests/test_safe_python_analytics_executor.py`
  - 21 passed.
- `python -m pytest -q tests/test_invoice_analytics_dataset.py`
  - 4 passed.
- `python -m pytest -q`
  - 1681 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-17 - Session 147 - Invoice analytics planner import-boilerplate fix

Summary:
- Investigated live post-deploy smoke where `invoice_analytics` routed
  correctly but returned the safe validation-stop answer instead of executing.
- Server-side mock `message.answer` smoke showed the real generated planner
  code included forbidden `import pandas as pd` and
  `from datetime import datetime` boilerplate despite the prompt.
- Added planner-side normalization that strips only the known harmless
  `import pandas as pd` / `from datetime import datetime` boilerplate and
  redundant `current_date = datetime.strptime(...)` assignment before the
  existing AST safe executor validation. Other imports remain visible and are
  rejected by planner or executor validation.
- Kept executor authority unchanged: imports remain forbidden and any
  remaining unsafe code is still rejected before execution.
- Follow-up production smoke showed sanitized planner code passed validation
  but timed out in Docker because child-process spawn plus pandas startup did
  not fit the original 2-second default. Increased the default hard timeout to
  10 seconds while preserving terminate/kill isolation on timeout.
- A second server mock smoke still showed intermittent safe-stop responses from
  Linux container execution paths using `spawn`. Switched Linux/Unix execution
  context to `fork` while keeping Windows on `spawn`, preserving the separate
  process and timeout-kill boundary.

Verification:
- `python -m pytest -q tests/test_invoice_analytics_planner.py`
  - 7 passed.
- `python -m pytest -q tests/test_safe_python_analytics_executor.py`
  - 21 passed.
- `python -m pytest -q tests/test_invoice_analytics_dataset.py`
  - 4 passed.
- `python -m pytest -q`
  - 1669 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-16 - Session 146 - Invoice analytics runtime pilot

Summary:
- Added canonical top-level action `invoice_analytics` as a partial read-only
  runtime pilot for saved outgoing invoice analytics.
- The runtime builds a supplier-scoped sanitized pandas dataframe from saved
  outgoing invoices, injects the current runtime date, asks the LLM only for a
  bounded analysis code plan, validates the AST, executes in a timeout-killed
  child process without DB/file/network/write access, and answers from computed
  results.
- Added Python-side normalized bot payment status fields
  `payment_status_canonical`, `payment_status_label`, and
  `payment_status_source`; raw invoice lifecycle status is exposed only as
  `invoice_status_raw` and must not be treated as payment truth.
- Preserved the existing deterministic `invoice_period_summary` yearly summary
  path as separate implemented behavior.

Preflight:
- Docs/contracts read: AGENTS, Product Doctrine, AI Layer Implementation
  Standards, Product Truth Layer, Product Truth Registry MVP Design,
  Self-Learning Layer, Evaluation and Smoke Test Standards, Product UX Eval
  Artifacts, TZ FakturaBot, LLM Orchestrator Contract, Canonical Action
  Registry, In-Action Response Registry, New Action Design Checklist, Bounded
  Resolver Prompt Template, Canonical DecisionResolver Contract, InfoHelp
  Guidance Layer, Customization Request Layer, Confirmed Semantic Alias
  Learning Contract, PROJECT_LOG.
- Touched scopes: top-level routing, LLM planning boundary, read-only DB
  dataset service, safe analytics executor, final answer rendering, Product
  Truth, InfoHelp, canonical docs, TZ, eval smoke artifacts, tests.
- Not touched: invoice create/edit/delete persistence, status mutation,
  confirmation flows, STT implementation, LMM, accounting document intake,
  receipts/incoming invoices, bank statements, PDF layout/generation, external
  storage, email/SMS, server deployment, DB schema.
- Current implementation status: `partial` for invoice analytics; existing
  `invoice_period_summary` remains `implemented`; full accounting analytics,
  tax/VAT advice, receipt/incoming invoice analytics, bank matching, and write
  operations remain unsupported.
- AI maturity: bounded AI-assisted runtime pilot. Python owns data, scope,
  payment-status normalization, validation, process isolation, execution, and
  side-effect denial; LLM only drafts bounded code and wording from
  Python-provided facts.
- Self-learning hooks considered: none added. Analytics questions are not
  confirmed semantic aliases and must not expand canonical actions or Product
  Truth automatically.
- User journey proof: authorized idle user asks a text or voice invoice
  analytics question, sees a computed answer over only their saved outgoing
  invoices, and no invoice/PDF/storage/DB write occurs.
- Product claim sources: current code/tests, Product Truth entry
  `invoice_analytics`, `docs/llm/Invoice_Analytics_Runtime_Contract.md`, TZ
  addendum, canonical action registry, eval smoke artifacts, and this log.

Verification:
- `python -m pytest -q tests/test_safe_python_analytics_executor.py`
  - 21 passed.
- `python -m pytest -q tests/test_invoice_analytics_dataset.py`
  - 4 passed.
- `python -m pytest -q tests/test_invoice_analytics_planner.py`
  - 6 passed.
- `python -m pytest -q`
  - 1668 passed, 7 subtests passed.
- `git diff --check`
  - passed with line-ending conversion warnings only.

## 2026-06-16 - Session 145 - Invoice follow-up callback keyboard cleanup

Summary:
- Updated overdue invoice follow-up callback handling so a successful
  mark-paid, remind-later, or do-not-remind-again decision removes the inline
  keyboard from the original Telegram reminder card before sending the
  confirmation message.
- Keyboard cleanup happens only after the callback is parsed, ownership is
  validated, and the decision state is persisted. Stale/forbidden callbacks do
  not clear keyboards or claim success.
- Cleanup failure is logged and does not roll back the already persisted
  decision.

Scope and constraints:
- Touched scopes: invoice follow-up Telegram callback UX, focused handler
  tests, changelog, project log.
- Not touched: overdue detection rules, scheduler interval/cooldown,
  payment/reminder state semantics, real Google Drive upload, invoice PDF
  generation, local invoice storage.
- Current implementation status: UX fix for existing partial automatic
  due-date follow-up; Google Drive archive remains an unsupported stub only.

Verification:
- `python -m pytest -q tests/test_invoice_followup_handler.py`
  - 8 passed.
- `python -m pytest -q`
  - 1626 passed, 7 subtests passed.

## 2026-06-15 - Session 144 - Automatic overdue invoice follow-up correction

Summary:
- Reworked Phase 1 overdue outgoing-invoice follow-up from manual command
  trigger to automatic runtime control.
- Added an in-process aiogram background scheduler started from `bot/main.py`.
  The scheduler runs due-invoice checks automatically once per day by default,
  sends Telegram reminder cards to authorized supplier owners, and is
  cancelled when polling stops.
- Removed `/kontrola_splatnosti` from the user-facing runtime surface.
- Added access-boundary filtering inside the scheduler path because automatic
  jobs do not pass through Telegram middleware. Blocked, deleted, and
  unauthorized users are skipped before any reminder message is sent.
- Added successful-send cooldown persistence through `remind_after` so the
  same overdue invoice is not sent again on every scheduler tick.
- Corrected the default scheduler interval from the initial hourly setting to
  `86400` seconds because invoice due-date status changes at day granularity.
- Kept the three bounded callback decisions: mark paid, remind later, do not
  remind again. Kept the Google Drive behavior as a local honest stub only.
- Updated Product Truth, InfoHelp, TZ, canonical/in-action docs, changelog,
  product UX smoke scenarios, and tests to remove manual-command assumptions.

Preflight:
- Touched scopes: runtime scheduler, invoice follow-up service, callback-only
  handler surface, config, access filtering, Product Truth/InfoHelp, docs,
  evals, tests.
- Not touched: LLM, STT, LMM, PDF/layout generation, local invoice PDF saving
  behavior, server operations, real Google OAuth/Drive APIs, email/SMS,
  accounting export, bank matching.
- Current implementation status: `partial` for invoice due-date reminders
  because automatic Telegram reminders run in-process, while external
  cron/worker deployment and non-Telegram channels remain out of scope;
  `unsupported` for real Google Drive invoice archive/upload.
- AI maturity: no new AI maturity level; deterministic Python runtime with
  Product Truth/InfoHelp coverage.
- Self-learning hooks considered: none added; reminder outcomes are payment
  and notification state, not semantic learning signals.
- User journey proof: approved supplier with overdue invoice receives an
  automatic Telegram reminder card without running a command, chooses a
  callback decision, and state persists; blocked users are not notified.
- Persisted-data safety: still additive table only; this correction adds state
  updates to `remind_after` after successful sends but does not rewrite
  existing invoice rows, invoice numbers, PDF paths, or local PDFs.

Verification:
- `python -m pytest -q tests/test_invoice_followup_service.py tests/test_invoice_followup_handler.py tests/test_product_truth.py tests/test_info_help.py`
  - 119 passed.
- `python -m pytest -q`
  - 1625 passed, 7 subtests passed.
- Local file smoke with temporary SQLite DB and dummy Telegram bot:
  - created approved supplier/contact/overdue invoice locally;
  - automatic scheduler tick sent one reminder card;
  - card buttons were `Oznacit ako zaplatenu`, `Pripomenut neskor`,
    `Viac nepripominat`;
  - same-day duplicate tick sent 0 reminders because `remind_after` was set;
  - `Viac nepripominat` persisted `reminder_status=muted`;
  - next-day tick sent 0 reminders for the muted invoice;
  - no Telegram API, Google API, network, PDF rewrite, or external storage was
    used.
- Deployment:
  - committed as `b931e98` (`Add automatic invoice due-date follow-up`) and
    pushed to `origin/main`;
  - server env updated only in `/bot/repo/.env` for follow-up scheduler keys:
    scheduler enabled, default daily interval `86400`, notification cooldown
    `24` hours;
  - server backup created under `/bot/backups/deploy_20260615_184522/` before
    restart (`fakturabot.db.bak`, `storage.tgz`, `env.bak`);
  - server `/bot/repo` fast-forwarded to `b931e98`;
  - container rebuilt/restarted with `docker compose -f docker-compose.prod.yml
    up -d --build`;
  - post-deploy logs showed `FakturaBot starting`, `Start polling`,
    `Invoice follow-up scheduler started interval_seconds=86400`, and
    scheduler tick `eligible_suppliers=1`, `notified_suppliers=1`,
    `reminders_sent=5`, `failed_sends=0`;
  - container state stayed `running`, restart count `0`, and logs showed no
    `ERROR`, `Traceback`, `TelegramConflictError`, or polling conflict.

## 2026-06-15 - Session 143 - Manual overdue invoice follow-up Phase 1

Summary:
- Implemented Phase 1 overdue outgoing-invoice follow-up behind deterministic
  Python services and Telegram callbacks.
- Added additive `invoice_followup_state` bootstrap schema. Existing invoices
  without a follow-up row are interpreted as unpaid/active; no existing invoice
  rows, invoice numbers, PDF paths, or local PDF files are rewritten.
- Added `/kontrola_splatnosti` as the manual Phase 1 trigger. It lists only the
  current authorized supplier's overdue invoices and sends reminder cards with
  mark-paid, remind-later, and do-not-remind-again choices.
- Added persisted follow-up state transitions for `paid`, `snoozed`, and
  `muted`, plus tenant-scoped callback validation before every write.
- Added `GoogleDriveArchiveStubService` as a no-network local stub after
  mark-paid. It records only stub state and tells the user that Google Drive
  archive is not active and the invoice remains stored locally.
- Updated Product Truth, InfoHelp copy/classification, action/in-action
  registries, TZ, changelog, and product UX smoke scenarios.

Preflight:
- Docs/contracts read: AGENTS, PROJECT_LOG, TZ, Product Truth Layer, InfoHelp
  Guidance, Customization Request Layer, Implementation Agent Checklist,
  Code-Agent Handoff Contract, Google Drive Token Crypto Operations,
  OfficeFlow Storage Model Proposal, Canonical Action Registry,
  In-Action Response Registry, Bounded Resolver Prompt Template,
  Canonical DecisionResolver Contract, Product Doctrine, AI Layer Standards,
  Product Truth Registry MVP Design, Self-Learning Layer, Product UX Eval
  Artifacts, LLM Orchestrator Contract, New Action Checklist, Data Migration
  Runbook, CHANGELOG.
- Touched scopes: DB schema additive table, invoice follow-up service,
  Telegram command/callback routing, Product Truth/InfoHelp, docs/evals/tests,
  user-data deletion cleanup, invoice deletion cleanup.
- Not touched: LLM, STT, LMM, PDF/layout generation, local invoice PDF saving
  behavior, server operations, real Google OAuth/Drive APIs, email/SMS,
  accounting export, bank matching, automatic scheduler.
- Current implementation status: `partial` for invoice due-date reminders
  because the trigger is manual `/kontrola_splatnosti`; `unsupported` for real
  Google Drive invoice archive after due-date follow-up.
- AI maturity: no new AI maturity level; deterministic runtime and partial
  Product Truth/InfoHelp coverage only.
- Self-learning hooks considered: no learning added; reminder decisions are
  payment/reminder state, not semantic aliases.
- User journey proof: approved user runs `/kontrola_splatnosti`, sees only own
  overdue invoices, chooses one of three callback decisions, state persists,
  and Drive stub copy remains honest.
- Persisted-data safety: additive table only; legacy rows require no migration.
  Read-only audit for server apply would count invoice rows, follow-up rows,
  and orphan states before any production DB write. Backup/rollback for server
  apply would back up SQLite first; no server writes were performed in this
  session.
- Product claim sources: current code/tests plus Product Truth entries
  `invoice_due_date_reminders` and
  `google_drive_invoice_archive_after_due_date`, this log, TZ addendum, and
  focused spec.

Verification:
- `python -m pytest -q tests/test_invoice_followup_service.py tests/test_invoice_followup_handler.py tests/test_product_truth.py tests/test_info_help.py`
  - 116 passed.
- `python -m pytest -q`
  - 1622 passed, 7 subtests passed.

## 2026-06-14 - Session 142 - Ukrainian current-year invoice summary wording

Summary:
- Investigated the Telegram screenshot where the voice request `На яку суму я виставив фактур цього року?` returned the supported-year guidance instead of the invoice total.
- Confirmed server logs resolved the top-level action as `invoice_period_summary`; the failure was action-parameter canonicalization for the supported year period.
- Reworked the local fix to follow the LLM/orchestrator contract: after the top-level action token is selected, the handler asks bounded resolver context `invoice_summary_period_selection` for `current_year`, `previous_year`, or `unknown`; Python still parses explicit `YYYY` deterministically and owns date-range validation/execution.
- Added narrow deterministic fallback only inside the shared semantic resolver for no-key/offline operation, with LLM fallback available when configured.
- Added regression coverage so the screenshot wording answers with the yearly summary and proves the bounded period resolver is used.

Verification:
- Superseded earlier local phrase-parser patch before commit/deploy; verification rerun below after bounded resolver alignment.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py::test_invoice_period_summary_resolves_as_read_only_top_level_action tests/test_invoice_intent_prerouter.py::test_process_invoice_text_answers_invoice_period_summary_without_side_effects tests/test_invoice_intent_prerouter.py::test_invoice_period_summary_uses_bounded_period_value_resolver tests/test_voice_state_routing.py::test_voice_idle_invoice_period_summary_answers_from_top_level_router` -> `10 passed`.
- `python -m pytest -q` -> `1599 passed, 7 subtests passed`.

## 2026-06-14 - Session 141 - Invoice explicit issue-date intake guardrail

Summary:
- Investigated server logs for a failed invoice draft where the user said delivery date `14 лютого` and issue date `17 лютого`.
- Confirmed the runtime understood delivery date, but compared it against `date.today()` as `issue_date`, so the delivery-date guard rejected it as more than 62 days in the past.
- Added deterministic Python extraction of explicitly marked invoice issue date from the raw/STT text before delivery-date validation and due-date computation.
- Kept the stale-year delivery guardrail intact; the fix changes the anchor date when the user explicitly provides `Dátum vystavenia`.

Contracts/preflight:
- Contracts already read for this invoice/runtime task: Product Doctrine, AI Layer Implementation Standards, Product Truth Layer/Registry, Self-Learning Layer, Evaluation and Smoke Test Standards, Product UX Eval Artifacts, TZ, LLM Orchestrator Contract, Canonical/In-Action registries, New Action checklist, Bounded Resolver prompt, InfoHelp, Customization Request, Confirmed Semantic Alias Learning, DecisionResolver, and server runbook.
- Touched scopes: invoice FSM/runtime date normalization, tests, TZ, changelog, project log.
- No DB schema, persisted-data migration, storage rewrite, access change, Product Truth capability expansion, or confirmation parser change.
- Current status: implemented bug fix for create-invoice draft date anchoring; AI maturity unchanged.
- Out of scope: broad natural-language date grammar, numeric issue-date forms without month names, server deploy unless explicitly requested.

Verification:
- `python -m pytest -q tests/test_invoice_phase2_ai_layer.py` -> `68 passed`.

## 2026-06-14 - Session 140 - Fix singleton invoice price clarification loop

Summary:
- Inspected live server logs for a failed invoice price entry during invoice
  creation.
- Logs showed the LLM/parser had recognized `quantity=1.0` and
  `unit_price=3490.0` at the draft level, but `items[0].quantity` and
  `items[0].unit_price` stayed empty, so the invoice builder re-entered
  `quantity_unit_price_pair` clarification.
- Fixed singleton item normalization so a one-item draft fills missing item
  fields from the validated top-level draft values. Multi-item drafts are left
  unchanged to avoid applying one price to multiple items.

Constraints:
- No DB/schema/storage migration, no persisted data writes, no Product Truth
  status change, and no confirmation parser change.
- Runtime scope: invoice draft normalization before preview/save.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py::test_singleton_item_uses_top_level_quantity_and_price_from_llm_payload tests/test_invoice_intent_prerouter.py::test_slot_clarification_applies_unit_price_and_continues_to_preview tests/test_invoice_intent_prerouter.py::test_slot_clarification_applies_quantity_unit_price_pair_and_continues_to_preview tests/test_invoice_intent_prerouter.py::test_unknown_top_level_gets_info_help_guidance tests/test_invoice_intent_prerouter.py::test_info_help_guidance_builder_has_no_side_effects`
  - 15 passed.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py`
  - 158 passed.
- `python -m pytest -q tests/test_invoice_phase2_ai_layer.py`
  - 66 passed.
- `python -m pytest -q`
  - 1595 passed, 7 subtests passed.

## 2026-06-14 - Session 139 - InfoHelp invoice summary visibility

Summary:
- Updated the top-level unknown InfoHelp guidance so the general capability
  list explicitly says the bot can count a calendar-year summary of saved
  outgoing invoices.
- Added the `súhrn faktúr za 2026` example to the same guidance so users can
  discover the supported `invoice_period_summary` wording from fallback help.

Constraints:
- No runtime execution logic, DB/schema, storage, PDF, Product Truth status,
  resolver, or server configuration changes.
- This is a user-facing InfoHelp copy change only; the supported capability was
  already implemented as `invoice_period_summary`.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py::test_unknown_top_level_gets_info_help_guidance tests/test_invoice_intent_prerouter.py::test_info_help_guidance_builder_has_no_side_effects tests/test_info_help.py::test_invoice_period_summary_capability_question_renders_supported_product_truth`
  - 3 passed.

## 2026-06-13 - Session 138 - Invoice yearly summary top-level action

Summary:
- Implemented `invoice_period_summary` as a bounded top-level read-only action
  for text/voice questions such as `Na akú sumu som vystavil faktúry tento
  rok?` and `Súhrn faktúr za 2026`.
- Added a tenant-scoped invoice service summary query that counts and sums only
  saved outgoing invoices for the current supplier by `issue_date` and
  calendar-year bounds.
- Updated Product Truth, InfoHelp copy, canonical action registry,
  orchestrator contract, TZ notes, and UX smoke artifact so the narrow yearly
  summary is `supported` while broader invoice analytics/reporting remains out
  of scope.

Preflight:
- Contracts read: Product Doctrine, AI Layer Standards, Product Truth Layer and
  Registry design, Self-Learning Layer, Evaluation/Smoke standards, Product UX
  eval artifacts, TZ, LLM Orchestrator contract, Canonical Action Registry, New
  Action checklist, InfoHelp guidance, Customization Request layer, Confirmed
  Semantic Alias contract, In-Action Response registry, Bounded Resolver prompt
  template, and Canonical DecisionResolver contract.
- Touched scopes: top-level routing/resolver, invoice read service,
  user-facing invoice handler response, Product Truth, InfoHelp, docs, evals,
  tests, and project log.
- Current implementation status: `supported` for read-only calendar-year
  outgoing invoice totals; `unsupported` for receipts, incoming invoices, VAT
  reports, unpaid/cashflow analytics, arbitrary period analytics, and document
  intake summaries.
- AI maturity: runtime action with Product Truth/InfoHelp Level 2 coverage for
  this specific capability; no new self-learning behavior.
- Out of scope: DB schema changes, migrations, PDF/storage writes, invoice
  creation/edit/delete, confirmations, admin review storage, external lookup,
  and broad analytics.
- User journey proof: idle text or voice can ask for a yearly invoice summary;
  Python resolves the bounded action, parses a supported year, reads only the
  authorized supplier's saved invoices, returns count/totals, clears state, and
  creates no PDFs or storage files.
- Source of truth: current code, Product Truth entry
  `invoice_period_summary`, canonical action registry, orchestrator contract,
  TZ notes, tests, and eval artifact.

Verification:
- `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_product_truth.py`
  - 303 passed.
- `python -m pytest -q`
  - 1594 passed, 7 subtests passed.

## 2026-06-13 - Session 137 - InfoHelp invoice-summary honesty hardening

Summary:
- Audited a production voice failure where an unknown invoice-period summary
  question was answered as `Táto schopnosť: podporované.`
- Server logs showed STT transcript
  `На яку суму я вже виставив фактуру в цьому році?`, request id
  `433d328c-2491-4b2c-90a5-d75ba80b33a5`, Telegram message id `1168`,
  update id `384865418`, and top-level intent `unknown`; logs did not include
  InfoHelp triage output, selected capability id, Product Truth status, active
  FSM state value, or final response body.
- Hardened Product Truth rendering so missing localized Slovak copy falls back
  to Product Truth payload fields (`title`, `summary_for_user`,
  `current_limitations`, `safe_next_steps`) instead of generic
  `Táto schopnosť`.
- Added bounded deterministic triage for invoice/report/summary/total-by-period
  requests as a plausible unsupported/unverified business reporting need, with
  an answer-only response that states no calculation or mutation happened.

Constraints:
- No invoice yearly summary/report action was implemented.
- No DB schema, storage, Google Drive, receipt categorization, invoice
  analytics, destructive confirmation, or voice phrase dictionary changes.
- InfoHelp remains partial Level 2; this fixes a specific honesty and renderer
  gap but does not complete broad capability-aware Q&A.

Verification:
- `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_product_truth.py`
  - 293 passed.
- `python -m pytest -q`
  - 1584 passed, 7 subtests passed.

## 2026-05-31 - Session 136 - Google OAuth token exchanger regression hardening

Summary:
- Hardened Google OAuth token exchanger regression coverage before any
  callback wiring.
- Added tests that token bundle repr hides token plaintext, invalid
  `expires_in` fails with a bounded error, invalid `id_token` metadata is
  ignored without repr leakage, mocked `HTTPError`/`URLError` paths stay
  bounded, raw Google response bodies are not exposed, and callback runtime
  remains unwired to the real exchanger.
- Tightened exchanger behavior so invalid non-positive or non-integer
  `expires_in` raises bounded `drive_connection_error` instead of silently
  accepting the token response.

Constraints:
- No callback runtime wiring, real Google API/network call in tests, Drive
  adapter, upload, Telegram handler change, cleanup/delete, or Product
  Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_google_oauth_token_exchanger.py tests/test_google_drive_oauth_callback_app.py tests/test_token_crypto.py`
  - 58 passed.
- `python -m pytest -q`
  - 1574 passed, 7 subtests passed.

## 2026-05-31 - Session 135 - Google OAuth token exchanger foundation

Summary:
- Added `GoogleOAuthTokenExchanger` as a production-capable authorization-code
  token exchanger foundation for future Google Drive OAuth callback wiring.
- The exchanger posts form data to `https://oauth2.googleapis.com/token` via an
  injectable HTTP client, normalizes token responses into the existing
  `GoogleOAuthTokenBundle`, validates refresh-token and `drive.file` scope
  requirements, and extracts safe subject/email metadata from `id_token` when
  present.
- Added bounded provider error mapping for invalid grants, invalid clients,
  scope errors, malformed JSON, HTTP 5xx, timeouts, and unexpected client
  failures without exposing auth code, client secret, token values, or raw
  Google response text.
- Added `GOOGLE_OAUTH_CLIENT_SECRET` config/env placeholders only.

Constraints:
- Token exchanger service only.
- No callback runtime wiring, real Google API call in tests, Drive adapter,
  file upload, archive worker real-provider run, local cleanup/delete, archive
  job behavior change, real secret commit, or Product Truth/InfoHelp status
  change.

Verification:
- `python -m pytest -q tests/test_google_oauth_token_exchanger.py tests/test_google_drive_oauth_callback_service.py tests/test_google_drive_oauth_callback_app.py tests/test_token_crypto.py`
  - 67 passed.
- `python -m pytest -q`
  - 1565 passed, 7 subtests passed.

## 2026-05-31 - Session 134 - Google Drive token crypto operations docs

Summary:
- Added `docs/Google_Drive_Token_Crypto_Operations.md` to document production
  handling for `GOOGLE_TOKEN_CRYPTO_SECRET`.
- Covered purpose, loss impact, common loss scenarios, storage policy, backup
  policy, current no-rotation policy, recovery steps, Fernet-compatible
  generation guidance, and the checklist required before real Google OAuth
  token exchange.
- Linked the operations document from the Google Drive storage policy and
  README.

Constraints:
- Documentation-only session.
- No runtime code changes, real Google token exchange, Google API/network
  call, Drive adapter, upload, real secret commit, or Product Truth/InfoHelp
  status change.

Verification:
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-31 - Session 133 - Production token crypto provider foundation

Summary:
- Added `FernetTokenCryptoProvider` as a production-capable token crypto
  foundation using authenticated Fernet encryption from the `cryptography`
  dependency.
- Added `GOOGLE_TOKEN_CRYPTO_SECRET` config/env placeholders for future
  external secret wiring; no real secret value is committed.
- Kept `DeterministicFakeTokenCryptoProvider` test-only and left the Google
  OAuth callback runtime fail-closed without wiring production crypto into it.
- Added tests for missing/invalid secret fail-closed behavior, Fernet
  encrypt/decrypt roundtrip, ciphertext/plaintext separation, repr secrecy,
  wrong-secret rejection, key/version mismatch handling, DB plaintext
  protection through `GoogleDriveConnectionService`, env placeholder safety,
  and no Google/network imports.

Constraints:
- Token encryption provider foundation only.
- No real Google token exchange, Google API/network call, Drive adapter,
  upload, callback runtime enablement, real secret commit, or Product
  Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_token_crypto.py tests/test_google_drive_connection_service.py`
  - 46 passed.
- `python -m pytest -q`
  - 1546 passed, 7 subtests passed.

## 2026-05-31 - Session 132 - Google Drive OAuth callback runtime fail-close

Summary:
- Hardened the Google Drive OAuth callback skeleton so the injectable
  `create_callback_app(...)` test path still supports fake exchanger/crypto,
  but `create_callback_app_from_config(...)` fails closed until production
  token exchange and production token crypto are explicitly implemented.
- Removed the runtime config path's use of `DeterministicFakeTokenCryptoProvider`
  so `python -m bot.google_drive_oauth_callback_app` cannot start a service
  that persists fake connected Google Drive rows into a real DB.
- Added callback boundary tests for fake-mode rejection, no runtime DB
  creation, Google error handling with wrong state, ignoring raw
  `error_description`, ignoring query-provided `telegram_id`, and keeping
  `bot/main.py` free of callback app wiring.
- Updated README to describe the callback app as a test/integration foundation
  whose config/runtime entrypoint is intentionally disabled for production.

Constraints:
- Safety hardening and tests only.
- No real Google token exchange, Google API/network call, real Drive adapter,
  upload, Product Truth/InfoHelp status change, or push.

Verification:
- `python -m pytest -q tests/test_google_drive_oauth_callback_app.py tests/test_google_drive_oauth_callback_service.py tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py`
  - 89 passed.
- `python -m pytest -q`
  - 1536 passed, 7 subtests passed.

## 2026-05-31 - Session 131 - Google Drive OAuth callback HTTP skeleton

Summary:
- Added a separate `aiohttp` callback service entrypoint:
  `python -m bot.google_drive_oauth_callback_app`.
- The callback app exposes `GET /oauth/google/callback`, handles `state`,
  `code`, and `error` query parameters, calls the existing
  `GoogleDriveOAuthCallbackService`, and sends safe Telegram success/failure
  messages when a consumed/rejected OAuth state identifies the Telegram user.
- The slice uses `FakeGoogleOAuthTokenExchanger` only, guarded by explicit
  `GOOGLE_OAUTH_CALLBACK_USE_FAKE_EXCHANGER=1` for runtime startup.
- Added callback host/port/fake-mode config placeholders and documented the
  separate callback command in README.

Constraints:
- Separate callback HTTP service only; `bot/main.py` polling runtime remains
  unchanged.
- No real Google token exchange, Google API/network call, Drive adapter,
  upload, archive worker run, local cleanup/delete, or Product Truth/InfoHelp
  Google Drive capability upgrade.

Verification:
- `python -m pytest -q tests/test_google_drive_oauth_callback_app.py tests/test_google_drive_oauth_callback_service.py tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py`
  - 84 passed.
- `python -m pytest -q`
  - 1531 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-31 - Session 130 - Google Drive setup command boundary tests

Summary:
- Hardened Google Drive setup command boundary tests before any real callback
  endpoint or token exchange work.
- Added coverage for missing `GOOGLE_OAUTH_REDIRECT_URI`, non-admin status
  denial, middleware allowlist pass-through for the three Google Drive setup
  commands, disconnected/revoked/error status display, and status-output
  secrecy guards.

Constraints:
- Tests/log update only.
- No callback endpoint, token exchange, Google API/network call,
  upload/Drive adapter, or Product Truth/InfoHelp capability upgrade.

Verification:
- `python -m pytest -q tests/test_google_drive_setup_commands.py tests/test_google_drive_connection_service.py tests/test_google_drive_oauth_state_service.py`
  - 73 passed.
- `python -m pytest -q`
  - 1519 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warning only.

## 2026-05-31 - Session 129 - Google Drive setup commands foundation

Summary:
- Added admin-only Telegram setup commands for the future Google Drive
  Accounting Archive connection:
  `/google_drive_connect`, `/google_drive_status`, and
  `/google_drive_disconnect`.
- `/google_drive_connect` creates a single-use OAuth state and returns a
  Google authorization URL using configured `GOOGLE_OAUTH_CLIENT_ID` and
  `GOOGLE_OAUTH_REDIRECT_URI`; it does not exchange tokens or call Google.
- `/google_drive_status` reads only the local connection record and hides
  tokens, ciphertext, raw scopes, state tokens, and OAuth internals.
- `/google_drive_disconnect` marks the local connection disconnected only; it
  does not revoke Google tokens, delete Google Drive files, delete local files,
  run workers, or mutate archive jobs.
- Added config placeholders for the OAuth client id and redirect URI.

Constraints:
- Telegram setup command foundation only.
- No real callback endpoint, token exchange, Google API/network calls, real
  Drive adapter, upload, worker run, local cleanup/deletion, outgoing invoice
  PDF archive, or Product Truth/InfoHelp Google Drive capability upgrade.

Verification:
- `python -m pytest -q tests/test_google_drive_setup_commands.py tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py`
  - 65 passed.
- `python -m pytest -q`
  - 1511 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-31 - Session 128 - Google Drive OAuth callback failure hardening

Summary:
- Hardened `GoogleDriveOAuthCallbackService.handle_callback(...)` so generic
  token exchanger exceptions and token crypto failures return bounded
  `drive_connection_error` failures instead of escaping.
- Added `drive_oauth_code_missing` as a bounded OAuth state error code so
  missing-code callback diagnostics are consistent between callback result and
  stored OAuth state.
- Added tests for generic provider exception handling, token crypto failure,
  missing-code state diagnostics, existing-connection `invalid_grant`
  `needs_reauth` marking, and successful reconnect token rotation without
  plaintext persistence.

Constraints:
- Small callback service hardening and tests only.
- No real Google API, real callback endpoint, Telegram commands, upload/Drive
  adapter, raw provider-error logging, or Product Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_google_drive_oauth_callback_service.py tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py tests/test_token_crypto.py`
  - 76 passed.
- `python -m pytest -q`
  - 1500 passed, 7 subtests passed.

## 2026-05-31 - Session 127 - Fake Google Drive OAuth callback service

Summary:
- Added `GoogleDriveOAuthCallbackService` as a local/fake callback pipeline for
  future Google Drive setup.
- The service consumes a stored OAuth state once, calls an injected token
  exchanger protocol, validates refresh-token and required-scope presence,
  encrypts the token bundle through the existing crypto provider, and upserts a
  connected `google_drive_connections` record.
- Added bounded callback/token-exchange result handling for missing code,
  invalid/reused/expired/rejected state, missing refresh token, missing scope,
  invalid grant, provider error, and unknown connection persistence errors.
- Added tests proving fake-token success, one-time state consumption,
  no exchanger call for bad state/code, bounded provider errors, encrypted-only
  persistence, no raw code/state/token persistence or repr exposure, no
  Google/network imports, and no Product Truth/InfoHelp status upgrade.

Constraints:
- Fake/local OAuth callback token-exchange foundation only.
- No real Google API calls, real token endpoint, real Google client, upload,
  Drive adapter, Telegram settings UI, or Product Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_google_drive_oauth_callback_service.py tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py tests/test_token_crypto.py`
  - 72 passed.
- `python -m pytest -q`
  - 1496 passed, 7 subtests passed.

## 2026-05-31 - Session 126 - Google Drive OAuth state rejection hardening

Summary:
- Hardened `GoogleDriveOAuthStateService.mark_oauth_state_rejected(...)` so it
  only transitions pending OAuth states to rejected.
- Consumed and expired states now remain terminal and cannot be overwritten to
  rejected; already rejected states return a deterministic no-op result.
- Added tests for pending rejection, consumed/expired terminal guards,
  rejected no-op behavior, wrong/missing state safety, and exact SHA-256 state
  token hash persistence.

Constraints:
- Small OAuth state service hardening and tests only.
- No token exchange, Google API/network calls, callback handler, Telegram
  commands, or Product Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py tests/test_token_crypto.py`
  - 58 passed.
- `python -m pytest -q`
  - 1482 passed, 7 subtests passed.

## 2026-05-31 - Session 125 - Google Drive OAuth state foundation

Summary:
- Added additive SQLite storage for future Google Drive OAuth state records via
  `google_drive_oauth_states`.
- Added `GoogleDriveOAuthStateService` to create single-use OAuth state tokens,
  persist only SHA-256 state-token hashes, build Google authorization URLs with
  offline access parameters, consume pending states once, expire stale states,
  and mark states rejected with bounded error codes.
- Added tests proving schema bootstrap idempotency, raw state tokens are not
  stored or exposed in repr output, authorization URLs contain required OAuth
  parameters but no client secret, state consumption is single-use, expired and
  reused states are bounded, scopes/workspace/user metadata are preserved, and
  no Google/network imports were introduced.

Constraints:
- OAuth state foundation and URL builder only.
- No token exchange, Google API calls, callback endpoint, token storage, real
  Drive adapter, upload, Telegram handler/command change, or Product
  Truth/InfoHelp Google Drive status upgrade.

Verification:
- `python -m pytest -q tests/test_google_drive_oauth_state_service.py tests/test_google_drive_connection_service.py tests/test_token_crypto.py`
  - 52 passed.
- `python -m pytest -q`
  - 1476 passed, 7 subtests passed.

## 2026-05-30 - Session 124 - Google Drive connection error-code hardening

Summary:
- Hardened `GoogleDriveConnectionService.mark_needs_reauth(...)` so persisted
  connection error codes are bounded before OAuth wiring.
- Added the allowed Google Drive connection error-code set:
  `drive_auth_revoked`, `drive_needs_reauth`,
  `drive_insufficient_permissions`, `drive_token_refresh_failed`,
  `drive_connection_error`, `drive_unknown_error`,
  `drive_oauth_state_invalid`, `drive_scope_missing`, and
  `drive_not_configured`.
- Unknown/raw provider errors, token-like strings, OAuth auth-code-like
  strings, provider JSON, and OAuth/provider URLs are normalized to
  `drive_unknown_error` before DB persistence.
- Added tests proving allowed codes persist, raw sensitive-looking errors do
  not persist, `needs_reauth` and disconnect behavior remains intact, token
  plaintext still does not appear in DB/repr output, and no Google/network
  imports were introduced.

Constraints:
- Service hardening and tests only.
- No OAuth flow, Google API calls, real Drive adapter, Telegram handlers or
  commands, uploads, or Product Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_google_drive_connection_service.py tests/test_token_crypto.py`
  - 36 passed.

## 2026-05-30 - Session 123 - Google Drive connection schema and token crypto foundation

Summary:
- Added additive SQLite foundation tables for future per-workspace Google Drive
  connections and folder-id caching.
- Added `GoogleDriveConnectionService` primitives for schema bootstrap,
  encrypted connection upsert, metadata-only connection reads, explicit token
  decryption through an injected crypto provider, needs-reauth/disconnect
  status updates, and workspace-scoped folder cache read/update/clear.
- Added `TokenCryptoProvider` abstraction with a deterministic fake provider
  for tests and an unconfigured production placeholder that requires future
  explicit secret/KMS wiring before real credentials can be stored.
- Added tests proving ciphertext-only persistence, no plaintext token in DB or
  repr output, bounded validation/status handling, workspace-scoped folder
  cache isolation, no Google/network imports, and no Product Truth/InfoHelp
  status upgrade.

Constraints:
- Foundation only.
- No Google OAuth flow, Google API calls, real Drive adapter, upload, worker
  real-provider execution, Telegram handler changes, connect/status/disconnect
  commands, plaintext token storage, or Product Truth/InfoHelp Google Drive
  implementation claim.

Verification:
- `python -m pytest -q tests/test_google_drive_connection_service.py tests/test_token_crypto.py`
  - 21 passed.

## 2026-05-30 - Session 122 - Accounting original cleanup dry-run

Summary:
- Added a dry-run service for local retention planning of confirmed accounting
  document originals after successful archive upload.
- The dry-run reads archive state, validates strict confirmed-original paths,
  groups by `(workspace_id, document_type)`, keeps the latest 5 uploaded
  originals per group, and reports `keep`, `would_delete`, or `exclude` with a
  bounded reason.
- Added tests for grouping, tenant isolation, status exclusions, missing Drive
  IDs, missing upload timestamps, invalid/excluded paths, missing local files,
  deterministic ordering, summary counts, no file deletion calls, no DB
  mutation, and no Google/network imports.

Constraints:
- Dry-run only.
- No file deletion, apply-delete, scheduler, admin cleanup command, DB row
  mutation, Google API/network call, `/blocek` or document-save behavior change,
  or Product Truth/InfoHelp active cleanup claim.

Verification:
- `python -m pytest -q tests/test_accounting_original_cleanup_service.py tests/test_accounting_document_archive_service.py tests/test_archive_job_service.py`
  - 70 passed.
- `python -m pytest -q`
  - 1424 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warning only.

## 2026-05-30 - Session 121 - Archive status read-only boundary hardening

Summary:
- Hardened archive status read-only boundary tests before any cleanup or real
  Drive adapter work.
- Added coverage proving `get_state_read_only(...)` does not create a missing
  DB file, malformed archive statuses fall back to safe display, and archive
  state from another workspace is not shown in `/blocky` / `/blocek`.
- Reconfirmed read-view guards for no archive job creation and no archive state
  mutation.

Constraints:
- Tests/log update only unless a small bug is exposed.
- No Google OAuth/API, real Drive adapter, worker execution from handler,
  cleanup/deletion, user-facing wording change, or Product Truth/InfoHelp
  status change.

Verification:
- `python -m pytest -q tests/test_accounting_documents_handler.py tests/test_accounting_document_archive_service.py`
  - 39 passed.
- `python -m pytest -q`
  - 1398 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 120 - Recent accounting archive status display

Summary:
- Added read-only archive/outbox status display to the recent accounting
  documents view (`/blocky` / `/blocek`).
- The view derives `document_id` from the confirmed metadata filename stem and
  reads archive state by workspace/document id without creating archive jobs,
  running a worker, uploading files, or mutating archive state.
- Added Slovak user-safe labels for `not_configured`, `pending`, `uploading`,
  `uploaded`, `retry_wait`, `failed`, and `abandoned`.
- Added handler tests for every displayed archive status and read-only guards
  against job creation, state mutation, worker/provider usage, and
  Google/network imports.

Constraints:
- Recent-docs status display only.
- No Google OAuth/API, real Drive adapter, worker run from handler, upload,
  user notifications, accounting document save-flow change, local
  cleanup/deletion, or Product Truth/InfoHelp active Google Drive claim.

Verification:
- `python -m pytest -q tests/test_accounting_documents_handler.py tests/test_accounting_document_registry.py tests/test_accounting_document_archive_service.py`
  - 45 passed.
- `python -m pytest -q`
  - 1395 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 119 - Fake archive worker regression hardening

Summary:
- Hardened fake archive worker regression tests before recent-docs archive
  status display work.
- Added coverage for uploaded timestamps on both archive job and archive state,
  one-job-only worker processing, missing provider handling, permanent failure
  state consistency, and local deletion tripwires.

Constraints:
- Tests/log update only unless a small bug is exposed.
- No Google OAuth/API, real Drive adapter, external network integration,
  Telegram handler change, recent-docs status display, cleanup/deletion, or
  Product Truth/InfoHelp status change.

Verification:
- `python -m pytest -q tests/test_archive_worker.py tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 60 passed.
- `python -m pytest -q`
  - 1385 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 118 - Fake archive worker lifecycle

Summary:
- Added a provider-injected local archive worker for accounting document archive
  jobs.
- The worker claims one runnable job via the archive outbox lease API, returns
  a no-op result when nothing is runnable, and updates archive job/state rows on
  success, retryable failure, permanent failure, max attempts, and missing
  mirrored state.
- Added bounded provider failure classes and bounded worker error codes:
  `upload_transient_failed`, `upload_permanent_failed`,
  `provider_unavailable`, and `upload_unexpected_failed`.
- Added fake-provider tests for pending and due retry uploads, retry timing,
  active/expired leases, terminal job exclusion, max attempts, missing state,
  local file preservation, bounded logs, and no Google/network imports.

Constraints:
- Phase 1C fake/local worker lifecycle only.
- No Google OAuth, Google API calls, real Drive adapter, external network
  upload, user notifications, recent-docs UI change, local cleanup/deletion,
  invoice lifecycle/reminders, or outgoing invoice PDF archive.
- Product Truth/InfoHelp remain unchanged and must not claim active Google
  Drive archiving.

Verification:
- `python -m pytest -q tests/test_archive_worker.py tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 57 passed.
- `python -m pytest -q`
  - 1382 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warning only.

## 2026-05-30 - Session 117 - Archive enqueue failure logging hardening

Summary:
- Hardened the confirmed accounting document archive enqueue failure log to use
  bounded fields only.
- Replaced exception traceback logging at the handler boundary with a fixed
  `archive_enqueue_failed` category and hashed workspace/document references.
- Kept confirmed accounting document save success behavior unchanged when
  archive enqueue fails.
- Added tests proving enqueue failure still preserves the confirmed document,
  logs the bounded category, omits confirmed original/metadata paths, omits the
  full filename-derived document id, and does not include raw exception
  path/token-like text.
- Extended the Google Drive Product Truth/InfoHelp regression to keep Drive
  storage unsupported/not implemented.

Constraints:
- Logging hardening and tests only.
- No worker, Google OAuth/API, upload, extra handler wiring, confirmed local
  file deletion, cleanup implementation, or Product Truth/InfoHelp status
  change.

Verification:
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_accounting_document_archive_service.py tests/test_archive_job_service.py`
  - 80 passed.
- `python -m pytest -q`
  - 1368 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 116 - Confirmed accounting document archive enqueue

Summary:
- Wired the accounting document intake confirmation path to enqueue a local
  Google Drive archive outbox job after `save_confirmed_accounting_document(...)`
  succeeds.
- The hook derives `document_id` from the confirmed metadata filename stem and
  uses the confirmed original and metadata paths; no temporary upload path is
  archived.
- Archive enqueue failures are logged with a bounded diagnostic and do not roll
  back the already-confirmed local accounting document save.
- Added handler-flow tests for confirmed receipt and incoming-invoice enqueue,
  no enqueue before preview approval, no enqueue on cancel, no enqueue on save
  failure, idempotent duplicate enqueue, confirmed path/state mirroring, and
  archive enqueue failure preserving the confirmed original.

Constraints:
- Phase 1B only: enqueue archive state/job after confirmed accounting document
  save.
- No Google OAuth, Google API calls, real Drive adapter, worker run, upload,
  local cleanup/deletion of confirmed originals, invoice lifecycle/reminders,
  outgoing invoice PDF archive, or recent-docs UI change.
- Product Truth/InfoHelp remain unchanged and must not claim active Google
  Drive archiving.

Verification:
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_accounting_document_archive_service.py tests/test_archive_job_service.py`
  - 80 passed.
- `python -m pytest -q tests/test_accounting_document_registry.py tests/test_accounting_documents_handler.py`
  - 18 passed.
- `python -m pytest -q tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 43 passed.
- `python -m pytest -q`
  - 1368 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 115 - Google Drive archive outbox transition hardening

Summary:
- Hardened `ArchiveJobService` with explicit bounded transitions for
  `pending`, `uploading`, `uploaded`, `retry_wait`, `failed`, and `abandoned`.
- Added additive worker lease columns on `archive_jobs`: `locked_by` and
  `lease_until`.
- Added atomic runnable job claiming for pending jobs, due retry jobs, and
  expired uploading leases.
- Clarified terminal enqueue policy: an existing `uploaded`, `failed`, or
  `abandoned` job for the same workspace/document/provider blocks automatic
  duplicate enqueue and is returned as-is.
- Tightened archive input validation to accepted accounting document originals
  under `workspaces/<workspace>/years/<year>/expenses/<month>/<receipts|incoming_invoices>/originals/`.
- Hardened `AccountingDocumentArchiveService` so mark operations require an
  existing archive state and fail safely before mutating a direct job-service
  job without mirrored state.
- Added static handler-boundary coverage proving accounting handlers still do
  not import or call archive services in this slice.

Constraints:
- Service hardening and tests only.
- No Telegram handler wiring or archive job creation from accounting document
  confirmation.
- No Google OAuth, Google API calls, real Drive adapter, external credentials,
  upload, notification, local cleanup/deletion, invoice lifecycle/reminders, or
  outgoing invoice PDF archive.
- Product Truth/InfoHelp remain unchanged and must not claim active Google
  Drive archiving.

Verification:
- `python -m pytest -q tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 43 passed.
- `python -m pytest -q tests/test_accounting_document_registry.py tests/test_accounting_documents_handler.py`
  - 18 passed.
- `python -m pytest -q`
  - 1361 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 114 - Google Drive accounting archive outbox foundation

Summary:
- Added the tracked design source
  `docs/Google_Drive_Faktury_Bloceky_Storage_Policy.md` after checking it for
  obvious secrets/credentials.
- Added additive SQLite archive foundation tables:
  `archive_jobs` and `accounting_document_archive_state`.
- Added `bot/services/archive_job_service.py` for local outbox job creation,
  idempotent active-job enqueue, runnable job listing, and status transitions.
- Added `bot/services/accounting_document_archive_service.py` to mirror archive
  state for confirmed accounting documents by workspace/document id.
- Added service tests for schema bootstrap, enqueue idempotency, runnable jobs,
  upload/retry/failure/abandoned status updates, local-file retention, no
  Google/network imports, and Product Truth non-overclaim.

Constraints extracted:
- Phase 1A only: DB/outbox services and tests.
- No Google OAuth, Google API calls, external credentials, real upload, Drive
  delete/archive, notifications, local cleanup, invoice lifecycle/reminders, or
  outgoing invoice PDF archive.
- Existing accounting document naming/storage remains canonical; new archive
  state references existing `metadata_path` and `original_path`.
- Telegram handlers are not wired to enqueue or upload in this slice.
- Product Truth/InfoHelp still must not claim active Google Drive archive.

Touched scopes:
- DB schema: yes, additive tables only;
- storage: references only, no file moves/deletes;
- accounting document services: archive foundation only;
- Telegram handlers/FSM/routing/LLM/STT/LMM/access/server: no behavior changes.

Current implementation status:
- Google Drive accounting archive: partial foundation only, no runtime upload.
- Google Drive integration/OAuth: unsupported / requires external credentials.
- AI maturity: not an AI-layer change; Product Truth remains the source for user
  capability claims.

Verification:
- `python -m pytest -q tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 27 passed.
- `python -m pytest -q tests/test_accounting_document_registry.py tests/test_accounting_documents_handler.py`
  - 18 passed.
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py`
  - 84 passed.
- `python -m pytest -q`
  - 1345 passed, 7 subtests passed.

## 2026-05-24 - Session 113 - InfoHelp human-review offer wording

Summary:
- Cleaned InfoHelp human-review offer rendering so escalation copy is
  contextual rather than appended as global boilerplate.
- Replaced internal-sounding "samostatný potvrdený náhľad" wording with
  user-facing Slovak copy that says a request is saved only after confirmation.
- Improved unsupported invoice email guidance: automatic email sending remains
  unsupported, while users can manually forward the PDF in Telegram or
  share/download it and attach it in their own email app with recipient and
  message filled manually.

Scope:
- InfoHelp rendering, InfoHelp docs, and tests only.
- No email sending implementation.
- No human-review storage or delivery flow changes.
- No Product Truth status changes.

Verification:
- `python -m pytest -q tests/test_info_help.py tests/test_product_truth.py`
  - 84 passed.
- `python -m pytest -q`
  - 1318 passed, 7 subtests passed.

## 2026-05-24 - Session 112 - Capability completion documentation gate

Summary:
- Added a docs-only capability completion gate across agent instructions,
  implementation checklists, action design guidance, Product Truth, InfoHelp,
  eval standards, and product doctrine.
- Clarified that user-facing runtime changes are incomplete when Product Truth,
  InfoHelp, eval/smoke artifacts, tests, forbidden claims, or `PROJECT_LOG.md`
  are stale.
- Added a concrete future Google Drive invoice storage example: runtime
  integration must be accompanied by Product Truth status/limitations, InfoHelp
  answers for "Vieš ukladať faktúry na Google Drive?" and "Ako zapnem Google
  Drive?", eval smoke, tests, log entry, and forbidden claims.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No handler, DB/schema, Product Truth runtime data, integration, retry,
  backlog, code-agent, or self-learning changes.
- No complete InfoHelp Level 2 or complete Level 3 claim.

Verification:
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-24 - Session 111 - Align Product Truth with human review runtime

Summary:
- Updated Product Truth to describe `customization_requests` as partial
  human-review runtime support instead of unsupported storage.
- Added Product Truth records for admin status review, answer-only admin
  response-to-user, admin-facing response delivery observability, access
  request approval, and invoice draft edit flow.
- Expanded InfoHelp Slovak answers for request lifecycle, admin answer
  delivery, accepted/rejected status meaning, confirmed admin-review submission,
  admin-facing delivery observability, recent bločky, contacts, services,
  existing invoice edit/delete, and generic voice usage.
- Updated InfoHelp triage payload truth so confirmed request storage is marked
  available while admin notification remains unavailable.
- Updated Product Truth/InfoHelp/customization eval/doctrine docs to reflect
  answer-only admin response delivery and observability without overstating
  maturity.

Constraints:
- Truth/docs/tests alignment only.
- No new runtime feature, admin command, retry/recovery command, notification,
  backlog conversion, Product Truth candidate conversion, code-agent handoff, or
  self-learning.
- No dynamic runtime Product Truth mutation.
- Still a partial Level 3 human-review slice, not the complete Customization
  Request Layer.
- Still partial InfoHelp, not complete Level 2.

Verification:
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_customization_request_admin.py`
  - 135 passed.
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_customization_request_admin.py tests/test_invoice_intent_prerouter.py`
  - 282 passed.
- `python -m pytest -q`
  - 1317 passed, 7 subtests passed.

## 2026-05-23 - Session 110 - Admin response delivery observability

Summary:
- Added admin detail observability for the latest Admin Response delivery state.
- `/customization_request <id_or_prefix>` now shows computed `not_started`,
  `send_pending`, `send_succeeded`, and `send_failed` response delivery states
  using existing `customization_requests` fields.
- Added a stuck `send_pending` warning for pending responses older than 15
  minutes with attempts and no `response_sent_at`; this marks the result as
  unknown/manual-check-needed only.
- Detail output shows bounded response metadata and a redacted/truncated
  admin response preview without exposing `raw_text_hash`.
- Updated the Customization Request contract and MVP smoke eval catalog.

Constraints:
- Observability-only slice.
- No schema change.
- No retry or auto retry.
- No recovery command or `delivery_unknown` marking.
- No Product Truth mutation.
- No request review status mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No notifications.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py`
  - 87 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1308 passed, 7 subtests passed.

## 2026-05-23 - Session 109 - Admin Response delivery idempotency hardening

Summary:
- Hardened Admin Response to User MVP delivery idempotency before push.
- The service now atomically claims a response as `send_pending` before any
  Telegram delivery attempt.
- Duplicate confirms for the same `response_id` in `send_pending`,
  `send_succeeded`, or `send_failed` do not trigger another outbound send.
- The handler now sends to the persisted request row `telegram_id` returned by
  the service, not a final-send FSM draft target.
- Added handler/service tests for pending duplicate confirms, already-succeeded
  duplicate confirms, same-id failed response no-retry behavior, tampered FSM
  target safety, missing bot failure, Telegram exception failure, outbound
  redaction, persisted failed response text, attempts behavior, review status
  separation, and no downstream Product Truth/backlog/code-agent/self-learning
  effects.

Constraints:
- No new response kinds.
- No retry flow.
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No automatic accept/reject notifications.
- No broad routing changes.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_voice_state_routing.py`
  - 149 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1303 passed, 7 subtests passed.

## 2026-05-23 - Session 108 - Admin Response to User MVP

Summary:
- Implemented explicit admin response delivery for customization/human-review
  requests.
- Added admin-only `/customization_request_reply <id_or_prefix>`.
- Added a confirmation-gated admin response FSM: text entry, preview,
  send/edit/cancel, and shared DecisionResolver callback/voice preview routing.
- Added latest-response metadata fields on `customization_requests`:
  `admin_response_text`, `response_kind`, `response_sent_at`,
  `response_sent_by`, `response_delivery_status`, `response_attempts`,
  `response_failed_reason`, `responded_to_request_status`,
  `response_updated_at`, and `response_id`.
- Persisted confirmed response metadata/text before Telegram send attempt;
  delivery result then records `send_succeeded` or `send_failed`.
- Duplicate confirm for an already sent `response_id` does not send again.
- Failed send keeps the response persisted with a safe bounded failure reason
  and no automatic retry.
- Updated docs/evals to mark only default `answer` response delivery as
  implemented.

Constraints:
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No automatic notifications on accept/reject.
- No automatic retry.
- No threaded/multi-response conversation history.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_voice_state_routing.py`
  - 142 passed, 7 subtests passed.
- `python -m pytest -q tests/test_decision_resolver.py tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_voice_state_routing.py`
  - 658 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1296 passed, 7 subtests passed.

## 2026-05-23 - Session 107 - Refine admin response MVP delivery semantics

Summary:
- Refined the docs-only Admin Response MVP design before runtime
  implementation.
- Clarified that confirmed admin response text/metadata must persist before the
  Telegram send attempt, and delivery status/timestamps/failure reason are
  updated after the send result.
- Clarified that MVP stores only latest response metadata on
  `customization_requests`; multi-response or threaded conversation history is
  future scope.
- Defined `clarification_request` as one-way outbound communication if included
  in MVP; it does not reopen a structured workflow or automatically move the
  request to `needs_user_input`.
- Clarified failed-send recovery: failed responses remain persisted with
  `send_failed`, no automatic retry happens, and a future manual retry may
  reuse persisted response data.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No admin replies implemented.
- No user notifications implemented.
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- Still a partial Level 3 MVP design, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `git diff --check`

## 2026-05-23 - Session 106 - Document admin response loop for customization requests

Summary:
- Broadened Customization Request documentation into an Admin Response / Human
  Review Loop concept.
- Clarified that current `customization_requests` rows may conceptually cover
  feature/customization requests, unanswered product/support/troubleshooting
  questions, possible Product Truth gaps, and admin-review candidates.
- Documented the current runtime limitation: capture, confirmed save, admin
  list/detail, and status-only accept/reject review exist; admin response to
  user, answer text storage, response delivery metadata, user notifications,
  `needs_user_input` delivery, and Product Truth mutation are not implemented.
- Extended eval artifacts with future/next-slice scenarios for admin answers,
  rejection explanations, clarification requests, out-of-domain/spam safety,
  and Product Truth gap non-mutation.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No admin replies.
- No user notifications.
- No Product Truth mutation.
- No backlog conversion.
- No code-agent handoff.
- No self-learning.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or closed human-review loop.

Verification:
- `git diff --check`

## 2026-05-22 - Session 105 - Customization request MVP docs and eval checkpoint

Summary:
- Aligned Customization Request MVP documentation with the current partial
  Level 3 runtime slice.
- Clarified user preview/save behavior, tenant-scoped storage, redacted
  draft/save data, deterministic request IDs, admin list/detail commands, and
  status-only accept/reject review commands.
- Tightened runtime-supported status terminology versus reserved/future
  statuses.
- Added `docs/evals/customization_request_mvp_smoke.md` with user, admin,
  privacy, and forbidden-claim smoke scenarios.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No admin notes.
- No notifications.
- No Product Truth mutation.
- No Product Truth candidate conversion.
- No backlog conversion.
- No code-agent handoff.
- No self-learning.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `git diff --check`

## 2026-05-22 - Session 104 - Customization request review idempotency hardening

Summary:
- Hardened admin customization request review transitions for repeated or
  racing review attempts.
- The service now checks the guarded review `UPDATE` row count and refetches
  the current row if another review already changed the status.
- Repeat accept/reject attempts return safe already-processed results and do
  not overwrite the original `reviewed_by`, `reviewed_at`, or `updated_at`.
- Added focused regression tests for accept-accepted, reject-rejected,
  reject-accepted, accept-rejected, audit-field preservation, pending-list
  exclusion, detail visibility, and no downstream side effects.

Constraints:
- No new feature surface.
- No notifications.
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No admin notes.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py`
  - 61 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1250 passed, 7 subtests passed.

## 2026-05-22 - Session 103 - Admin customization request review statuses

Summary:
- Added admin-only `/customization_request_accept <request_id>` and
  `/customization_request_reject <request_id>` commands.
- Added a status-only review transition in `CustomizationRequestService`:
  `confirmed_pending_review` can become `reviewed_accepted` or
  `reviewed_rejected`.
- Review transitions set `reviewed_by`, `reviewed_at`, and `updated_at`.
- Re-reviewing an already processed request is safe and does not change the
  existing reviewed status.
- Existing pending list now naturally excludes reviewed requests, while detail
  remains able to show reviewed requests.

Constraints:
- No Product Truth mutation.
- No user/admin notification.
- No backlog conversion.
- No code-agent handoff.
- No Product Truth candidate conversion.
- No self-learning.
- No free-form LLM review.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_access_request_flow.py`
  - 77 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1248 passed, 7 subtests passed.

## 2026-05-21 - Session 102 - Admin-only customization request detail view

Summary:
- Added `/customization_request <request_id>` as an admin-only read-detail
  command for customization requests.
- The detail view is read-only, supports full `request_id` lookup and safe
  unique short-prefix lookup, and rejects ambiguous prefixes.
- Output uses conservative display redaction and omits `raw_text_hash`.
- Added tests for full ID lookup, unique-prefix lookup, ambiguous/missing
  lookup, non-admin denial, unauthorized middleware blocking, read-only
  behavior, and sensitive value redaction.

Constraints:
- No approve/reject status changes.
- No admin notifications.
- No Product Truth mutation.
- No code-agent handoff or backlog conversion.
- No self-learning.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_access_request_flow.py tests/test_customization_requests.py`
  - 61 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1232 passed, 7 subtests passed.

## 2026-05-21 - Session 101 - Admin-only customization request pending list

Summary:
- Added `/customization_requests` as an admin-only read/list command for
  pending confirmed customization requests.
- The list is read-only and shows a compact pending-review summary for the
  newest requests across tenants for administrators.
- Added a narrow limit/newest-first option to the existing admin/internal
  `CustomizationRequestService.list_pending_customization_requests_for_admin`.
- Added tests for admin access, non-admin denial, middleware blocking for
  unauthorized users, pending-only filtering, conservative output redaction,
  admin-wide visibility, read-only behavior, and list limiting.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Add a minimal read-only admin review surface only.
- Do not add approve/reject status changes.
- Do not add admin notifications.
- Do not mutate Product Truth.
- Do not implement code-agent handoff or backlog conversion.
- Do not add self-learning.
- Do not expose requests to non-admin users.
- Do not call the complete Level 3 customization layer.
- Do not change InfoHelp/Triage creation flow.

Touched scopes:
- Admin/access: added one admin command and middleware admin-command allowlist
  entry.
- Storage/DB: read-only admin list query only; no schema change and no status
  mutation.
- Product docs: synchronized Customization Request contract narrowly.
- LLM/STT/LMM/FSM/routing/voice/PDF/server: unchanged.

Current implementation status:
- Admin pending customization request list: implemented read-only MVP slice.
- Approve/reject/status review decisions: unsupported.
- Admin notification: unsupported.
- Product Truth mutation: unsupported and unchanged.
- Code-agent handoff/backlog conversion: unsupported.
- Complete Customization Request Layer / complete Level 3: not complete.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_access_request_flow.py tests/test_customization_request_admin.py`
  - 248 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1222 passed, 7 subtests passed.

## 2026-05-21 - Session 100 - Customization Request Phase 2 edge-case regression tests

Summary:
- Added Phase 2 edge-case regression coverage for customization request
  confirmation hardening.
- Covered cross-user duplicate `request_id` collision, non-pending duplicate
  `request_id`, full `decision_callback(...)` approve/edit/cancel routing,
  edit draft identity preservation, and same-draft duplicate approval.
- Tests-only change; no runtime bug was found during implementation.

Constraints:
- No admin list command.
- No admin notification.
- No Product Truth mutation.
- No code-agent handoff.
- No routing behavior change.
- No new canonical actions.
- No complete Level 3 claim.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py`
  - 233 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1212 passed, 7 subtests passed.

## 2026-05-21 - Session 099 - Customization Request Phase 2 ownership/idempotency hardening

Summary:
- Hardened the existing Phase 2 confirmation flow without adding new feature
  surface.
- Preview drafts now carry the original requester `telegram_id`, workspace
  context, and deterministic `request_id` generated at preview time.
- Approval uses the draft owner and stored `request_id`; mismatched users are
  rejected without saving.
- Duplicate approval attempts for the same `request_id` are handled
  idempotently and do not create duplicate rows.
- FSM draft storage now minimizes raw input by keeping redacted original text
  plus a raw text hash; save still re-applies service-level redaction.
- Added focused text/button/voice regression tests for ownership,
  idempotency, callback decisions, voice approve/cancel, text-first edit, and
  all four eligible triage classes.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Runtime hardening and tests only.
- No admin notification or admin list command.
- No Product Truth mutation.
- No code-agent handoff.
- No new canonical action.
- No InfoHelp heuristic/dictionary expansion.
- No broad routing change without a failing narrow test.
- Do not call Level 3 complete.

Touched scopes:
- Confirmation: kept shared DecisionResolver `approve_edit_cancel` context.
- FSM: hardened Customization Request preview draft ownership/idempotency data.
- Storage/DB: no schema change; save still goes only through
  `CustomizationRequestService.create_confirmed_customization_request(...)`
  after approval.
- Voice/STT: added coverage for voice approval/cancel and text-first edit
  boundary; no voice phrase dictionary expansion.
- Product docs: synchronized Customization Request contract only.

Current implementation status:
- Customization Request preview/save: partial Level 3 MVP slice, hardened.
- Admin notification/list: unsupported and unchanged.
- Product Truth mutation: unsupported and unchanged.
- Code-agent handoff: unsupported and unchanged.
- Complete Customization Request Layer / complete Level 3: not complete.

Self-learning hooks considered:
- None added. This hardening stores only confirmed request rows after explicit
  approval and does not learn aliases, topics, or workflow rules.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_info_help.py tests/test_voice_state_routing.py tests/test_invoice_intent_prerouter.py tests/test_decision_resolver.py tests/test_decision_callbacks.py`
  - 775 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1205 passed, 7 subtests passed.

## 2026-05-21 - Session 098 - Customization Request MVP Phase 2 preview/save flow

Summary:
- Added a confirmation-gated Customization Request preview/save flow for
  eligible idle InfoHelp/Triage candidates:
  `new_business_feature_request`, `customization_request_candidate`,
  `admin_review_candidate`, and `possible_product_truth_candidate`.
- Drafts live only in FSM/temp state until the user explicitly approves.
- Approval saves exactly one `confirmed_pending_review` row through
  `CustomizationRequestService.create_confirmed_customization_request(...)`.
- Edit lets the user revise a short title/summary before returning to the
  preview.
- Cancel clears the draft and saves nothing.
- Idle voice transcripts can start the same preview flow, while exact
  title/summary edits remain text-preferred.
- Button, text, and voice confirmation paths use the shared
  DecisionResolver `approve_edit_cancel` family with context
  `customization_request_preview`.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- No save before explicit confirmation.
- No admin notification or admin list command.
- No Product Truth mutation.
- No code-agent handoff.
- No new canonical business action.
- Active FSM state and direct executable actions keep precedence.
- Unauthorized/unknown users must not start or save request drafts.

Touched scopes:
- Confirmation: added `customization_request_preview` DecisionResolver context.
- Routing: idle unknown InfoHelp/Triage candidate path only.
- FSM: added `CustomizationRequestStates.waiting_preview_decision` and
  `CustomizationRequestStates.waiting_edit_text`.
- Storage/DB: uses existing `customization_requests` table/service only after
  approval; no schema change.
- Voice/STT: idle voice transcript can start preview; edit text remains
  text-preferred.
- LLM/LMM/server/PDF/layout/access model: no architecture expansion.
- Product docs: updated active Customization Request and InfoHelp contracts.

Current implementation status:
- Customization Request storage foundation: implemented partial foundation.
- Confirmation-gated preview/save: implemented partial MVP slice.
- Admin notification/list: unsupported.
- Product Truth mutation: unsupported and unchanged.
- Code-agent handoff: unsupported.
- Complete Level 3 customization layer: partial, not complete.

AI maturity:
- Partial Level 3 MVP slice. This does not complete the Customization Request
  Layer because admin/developer review, richer structured request objects,
  Product Truth candidate conversion, and code-agent handoff are still absent.

Out of scope:
- Admin notification/list command.
- Product Truth writes or status changes.
- Code-agent handoff/task creation.
- New canonical business actions.
- Timeout/cleanup scheduler beyond existing FSM clear/cancel behavior.

Product/user journey proving the change:
- An authorized idle user asks for a new business feature or customization.
- The bot shows a Slovak preview with title, summary, what will be saved, and
  what will not happen.
- Approve saves one pending-review row; cancel saves nothing; edit then approve
  saves the edited title/summary.

Self-learning hooks considered:
- None implemented. Request capture is explicit and confirmed, but no alias,
  topic, or workflow learning is stored.

Source of truth for user-facing claims:
- Runtime code and tests prove preview/save only after approval.
- `CustomizationRequestService` proves persisted status and tenant scope.
- Product Truth registry is not mutated and no support claim is upgraded.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_info_help.py tests/test_voice_state_routing.py tests/test_invoice_intent_prerouter.py`
  - 268 passed, 7 subtests passed.

## 2026-05-20 - Session 097 - Harden Customization Request service boundaries

Summary:
- Hardened the Customization Request Phase 1 storage/service API before any
  user-facing flow is wired.
- Added `get_customization_request_for_user()` as the tenant-scoped read API;
  it requires `telegram_id` and returns only rows matching both `request_id`
  and user scope.
- Renamed the unscoped lookup to
  `get_customization_request_by_id_for_admin()` and documented it as
  admin/internal only.
- Renamed pending-review listing to
  `list_pending_customization_requests_for_admin()` and documented it as an
  admin/internal primitive, not a tenant-user listing API.
- Re-redacts caller-provided `redacted_original_text` before persistence so a
  handler-side mistake cannot store obvious secrets as redacted text.
- Restricts request creation to request-starting triage classes:
  `new_business_feature_request`, `customization_request_candidate`,
  `admin_review_candidate`, and `possible_product_truth_candidate`.
- Added tests for scoped reads, cross-user read prevention, required
  `telegram_id`, admin/internal method naming, direct-redacted-text
  re-redaction, invalid triage classes, and invalid source channel.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`

Constraints extracted:
- Service/API hardening and tests only.
- No user-facing InfoHelp/Triage flow, handlers, routing changes, admin list
  command, admin notification, Product Truth mutation, code-agent handoff, or
  complete Level 3 claim.

Touched scopes:
- Customization Request storage service, tests, and project log.
- DB table shape, runtime routing, handlers, voice/STT, LLM behavior, admin
  notification, Product Truth registry, and code-agent handoff are unchanged.

Current implementation status:
- Customization Request storage/service foundation: hardened partial Phase 1
  runtime foundation for confirmed rows only.
- User-facing Customization Request flow: not implemented.
- Admin review/notification: not implemented.
- Code-agent handoff: not implemented.
- Customization Request Level 3: not complete.

AI maturity:
- Storage prerequisite hardening for future Level 3. This patch does not
  provide a confirmation-gated user journey.

Out of scope:
- Draft preview FSM, confirmation UI, InfoHelp integration, admin list,
  admin notification, Product Truth candidate conversion, and code-agent
  task creation.

Verification:
- Service tests:
  `python -m pytest -q tests/test_customization_requests.py`.
- Required focused suite:
  `python -m pytest -q tests/test_customization_requests.py tests/test_product_truth.py tests/test_info_help.py`.
- Full suite:
  `python -m pytest -q`.

## 2026-05-20 - Session 096 - Customization Request storage foundation

Summary:
- Added additive SQLite storage foundation for confirmed customization
  requests through the new `customization_requests` table.
- Added `bot/services/customization_requests.py` with a narrow service API for
  creating confirmed request rows, fetching by id, listing user-scoped
  requests, listing pending review rows, hashing raw text, and deterministic
  redaction.
- Persisted records require tenant/user scope, non-empty title and summary,
  allowed persisted status, and explicit confirmed storage semantics.
- `draft_unconfirmed` is rejected from long-term persistence in Phase 1.
- Duplicate `request_id` creation fails deterministically instead of silently
  upserting.
- Added redaction coverage for API keys / `sk-` tokens, password/secret/token
  fields, IBAN-like values, email addresses, and phone numbers.
- Added tests proving tenant-scoped listing, status filtering, timestamp
  population, redaction/hash behavior, Product Truth immutability, and absence
  of admin notification / code-agent hooks.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Storage/service foundation only.
- No user-facing InfoHelp/Triage flow, routing behavior change, admin
  notification, admin list command, code-agent handoff, Product Truth mutation,
  pre-confirmation request persistence, handler-local matching, or complete
  Level 3 claim.

Touched scopes:
- DB schema bootstrap, storage service, tests, and project log.
- Runtime routing, handlers, voice/STT, LLM behavior, admin notification,
  Product Truth registry, and code-agent handoff are unchanged.

Current implementation status:
- Customization Request storage/service foundation: partial Phase 1 runtime
  foundation for confirmed rows only.
- User-facing Customization Request flow: not implemented.
- Admin review/notification: not implemented.
- Code-agent handoff: not implemented.
- Customization Request Level 3: not complete.

AI maturity:
- Storage prerequisite for future Level 3. This patch does not itself provide
  a confirmation-gated user journey.

Out of scope:
- Draft preview FSM, confirmation UI, InfoHelp integration, admin list,
  admin notification, Product Truth candidate conversion, and code-agent
  task creation.

Verification:
- Focused service test:
  `python -m pytest -q tests/test_customization_requests.py`.
- Required focused suite:
  `python -m pytest -q tests/test_customization_requests.py tests/test_product_truth.py tests/test_info_help.py`.
- Full suite:
  `python -m pytest -q`.

## 2026-05-20 - Session 095 - Harden LLM InfoHelp triage fallback tests

Summary:
- Added regression tests for the LLM-backed InfoHelp / Unknown-Triage fallback
  path without changing runtime behavior.
- Covered absent and non-`sk-` API key no-call behavior so the OpenAI client is
  not instantiated when the LLM fallback is unavailable.
- Extended payload assertions to exclude both `safe_next` and
  `safe_next_steps`, plus request/admin/action side-effect fields.
- Added parser coverage proving an invalid topic for a known capability is not
  trusted and normalizes to the safe `product_capability` topic.
- Added service and top-level integration coverage for model `unknown`
  returning generic bounded fallback guidance.
- Added service and top-level integration coverage for
  `possible_product_truth_candidate` clarification without Product Truth
  mutation, DB/storage writes, admin notification, or request save.
- Added mocked multilingual/noisy LLM-path smoke inputs for SK, SK without
  diacritics, Ukrainian, Russian, mixed/surzhyk, and mild STT-like text.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Tests-only unless a failing test exposes a tiny safety bug.
- No new features, routing behavior changes, storage/admin/customization
  writes, canonical actions, heuristic/dictionary expansion, DecisionResolver
  changes, or complete Level 2 claims.

Touched scopes:
- Tests and project log only.
- Runtime routing, handlers, DB/storage/schema, admin notifications,
  customization storage, canonical actions, DecisionResolver, and Product
  Truth status are unchanged.

Current implementation status:
- LLM-backed bounded InfoHelp / Unknown-Triage resolver path: partial Level 2
  foundation.
- InfoHelp Level 2: still not complete.
- Customization Request storage/admin notification: still unsupported runtime.

AI maturity:
- Test hardening for a partial Level 2 foundation. No new runtime capability
  claims.

Out of scope:
- Runtime behavior changes.
- Request persistence, admin sends, new business actions, Product Truth status
  mutation, broad heuristic expansion, and self-learning.

Verification:
- Focused suite required:
  `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_product_truth.py`.
- Full suite required:
  `python -m pytest -q`.

## 2026-05-19 - Session 094 - LLM-backed InfoHelp triage resolver path

Summary:
- Added `bot/services/info_help_resolver.py` as the bounded LLM-backed
  InfoHelp / Unknown-Triage classifier path behind deterministic v1.
- Deterministic Product Truth / triage matching remains the first fast-path;
  LLM classification is used only when deterministic triage returns no
  renderable result and a plausible API key is configured.
- LLM input is classification-only: context name, input channel, user text,
  supported languages, known capability IDs with title/domain/classification
  summaries, allowed topic IDs, allowed triage classes, disabled request
  storage/admin notification flags, and the expected output schema.
- LLM output is validated back into Python-owned fields only:
  `capability_id`, `topic_id`, `triage_class`, `confidence`, and
  `needs_clarification`.
- Hardened validation so conflicting `capability_id` + `triage_class`
  combinations fail safe instead of forcing a known capability.
- Wired the unknown top-level text path and idle voice transcript path to use
  deterministic triage first, then the bounded LLM classifier fallback.
- Added mocked LLM payload, parser, fallback, rendering, text integration, and
  voice transcript regression tests.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- No Customization Request storage, admin notifications, DB/storage request
  records, new canonical business actions, DecisionResolver changes,
  handler-local keyword matching, or deterministic phrase dictionary expansion
  as the main solution.
- LLM output must not choose final `response_mode`, decide Product Truth
  `primary_status`, return answer text, return canonical actions, draft
  requests, or create admin messages.
- Product Truth remains the only source of primary status, flags/context,
  limitations, setup requirements, forbidden claims, and safe next steps.

Touched scopes:
- InfoHelp resolver/service, unknown top-level text routing, idle voice
  transcript channel wiring, tests, and project log.
- No DB/storage/schema, admin notification, DecisionResolver, canonical action,
  customization storage, or handler-local keyword matching changes.

Current implementation status:
- LLM-backed bounded InfoHelp / Unknown-Triage resolver path: implemented as
  partial Level 2 foundation.
- InfoHelp Level 2: still not complete.
- Customization Request storage/admin notification: still unsupported runtime.

AI maturity:
- Partial Level 2 foundation only. Broader Level 2 still requires evaluated
  resolver behavior, voice/STT parity coverage beyond smoke, multilingual/noisy
  evals, and account-context-aware Product Truth evidence.

Out of scope:
- Runtime support claims beyond Product Truth.
- Request persistence, admin sends, new business actions, Product Truth status
  mutation, and self-learning.

Verification:
- Focused suite required:
  `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_product_truth.py`.
- Full suite required:
  `python -m pytest -q`.

## 2026-05-19 - Session 093 - Harden bounded InfoHelp triage regressions

Summary:
- Added regression coverage for bounded InfoHelp / Unknown-Triage v1.
- Covered unsupported triage class rejection, confidence bounds, invalid
  `topic_id` fallback, ignored model `response_mode`, ignored model
  `primary_status`, and ignored free-form `answer_text`.
- Added idle voice transcript triage coverage for new business feature
  requests, out-of-domain questions, smalltalk, unclear requests, and
  admin/customization candidates.
- Added voice regression proving final delete-database confirmation remains
  typed-only and does not call STT.
- Extended multilingual/noisy smoke coverage and action separation tests.
- Added a minimal parser hardening fix so an unsupported triage class cannot
  keep a model-provided topic as trusted output.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Prefer tests-only.
- No Customization Request storage, admin notification, DB/storage request
  records, new canonical business actions, DecisionResolver changes,
  handler-local keyword matching, or phrase dictionaries as main
  understanding.
- LLM output must not choose final response mode or decide Product Truth
  support status.

Touched scopes:
- Tests, project log, and one narrow `bot/services/info_help.py` parser
  validation fix.
- Runtime routing, handlers, DB/storage/schema, DecisionResolver, STT/LMM
  implementation, and Product Truth status are unchanged.

Current implementation status:
- Bounded Unknown / Discovery / Triage: v1 foundation implemented.
- Bounded InfoHelp resolver: partial foundation only, not complete Level 2.
- Customization Request storage/admin notification: unsupported runtime.
- InfoHelp Level 2: not complete.

AI maturity:
- Test hardening for a partial Level 2 foundation. This does not complete
  arbitrary capability-aware Q&A, request storage, self-learning, or
  code-agent handoff.

Out of scope:
- Runtime feature expansion.
- Broader deterministic phrase dictionaries.
- Persistence, admin notifications, new actions, and Product Truth status
  changes.

Verification:
- Focused suite required:
  `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_product_truth.py tests/test_voice_state_routing.py`.
- Full suite required:
  `python -m pytest -q`.

## 2026-05-18 - Session 092 - Add bounded InfoHelp triage resolver foundation

Summary:
- Added bounded InfoHelp / Unknown / Discovery / Triage v1 classification.
- Resolver output is Python-owned structured data only:
  `capability_id`, `topic_id`, `triage_class`, `confidence`, and
  `needs_clarification`.
- Added validation that rejects invented capability IDs, invalid JSON, and
  free-form answer-only model output.
- Explicitly ignores model-provided support status and final `response_mode`;
  Python still derives answers from Product Truth primary status, flags/context,
  routing/FSM/account state, and safety policy.
- Wired triage only after active-state routing, direct top-level action
  resolution, and conservative Product Truth fast-paths.
- Added safe non-persistent responses for new business feature requests,
  customization/admin candidates, out-of-domain input, spam/noise, smalltalk,
  unclear text, and possible Product Truth candidates.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `bot/services/info_help.py`
- `bot/services/product_truth.py`
- `bot/services/semantic_action_resolver.py`
- `bot/handlers/invoice.py`
- `bot/handlers/voice.py`
- `tests/test_info_help.py`
- `tests/test_product_truth.py`
- `tests/test_invoice_intent_prerouter.py`
- `tests/test_voice_state_routing.py`

Constraints extracted:
- Classification only; no Customization Request storage, admin notification,
  DB/storage request records, new canonical business actions, DecisionResolver
  changes, handler-local keyword matching, or phrase dictionaries as the main
  understanding layer.
- LLM output must not choose final response mode or decide Product Truth
  support status.
- Product Truth remains authoritative for primary status, flags/context,
  limitations, setup requirements, forbidden claims, and safe next steps.

Touched scopes:
- InfoHelp service: yes.
- Product Truth `info_help` capability metadata: yes.
- Top-level routing: narrow integration after existing direct-action and
  Product Truth fast-path precedence.
- Shared semantic action resolver: tightened generic `urob/sprav` so it does
  not create invoices without an invoice target.
- Tests/docs/project log: yes.
- Confirmation, DecisionResolver, STT, LMM, FSM side effects, storage, DB,
  access, server, PDF/layout: unchanged.

Current implementation status:
- Product Truth MVP: implemented foundation.
- Deterministic Product Truth-backed InfoHelp fast-path: partial.
- Bounded Unknown / Discovery / Triage: v1 foundation implemented.
- Bounded InfoHelp resolver: partial foundation only, not complete Level 2.
- Customization Request storage/admin notification: unsupported runtime.
- InfoHelp Level 2: not complete.

AI maturity:
- Partial Level 2 foundation. This patch adds safe classification and
  rendering paths, but does not complete arbitrary capability-aware Q&A,
  request storage, self-learning, or code-agent handoff.

Out of scope:
- Customization Request persistence/admin send flow.
- New canonical actions.
- Product Truth status changes based on model output.
- Runtime storage/DB/schema changes.
- Broad multilingual production evaluation beyond focused tests.

Self-learning hooks considered:
- None implemented. Triage classifications are not learned or persisted.

Verification:
- Focused and full test commands required before commit:
  `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py`
  and `python -m pytest -q`.

## 2026-05-18 - Session 091 - Clarify InfoHelp response policy and Product Truth flags

Summary:
- Performed a docs-only consistency cleanup before bounded InfoHelp resolver
  implementation.
- Clarified that LLM output may classify into Python-provided
  capability/topic/triage options, but must not authoritatively choose the
  final `response_mode`.
- Documented that Python derives final response behavior from Product Truth
  `primary_status`, flags/context, account state, active FSM/routing state, and
  safety policy.
- Clarified Product Truth status model:
  `supported`, `partial`, `planned`, `unsupported`, and `unknown` are primary
  support statuses; `dangerous`, `requires_setup`, `requires_admin`, and
  `requires_external_credentials` are flags/context, not primary statuses.

Constraints:
- Documentation-only update.
- No runtime code, resolver, handlers, phrase dictionaries, DB/storage/schema,
  or customization request storage changes.
- InfoHelp Level 2 remains not complete.

Touched scopes:
- Product/AI/InfoHelp/LLM docs and project log only.
- Runtime code, routing, LLM execution, STT, FSM, storage, DB, access, server,
  and tests unchanged.

Verification:
- `git diff --check` is the required verification for this docs-only update.
- Runtime tests were not required because no code changed.

## 2026-05-17 - Session 090 - Document Unknown Discovery Triage layer

Summary:
- Added docs-only architecture guidance for the Unknown / Discovery / Triage
  layer before bounded InfoHelp resolver implementation.
- Clarified that `unknown capability_id` is not a final answer and must be
  triaged safely when auth/state/routing allow it.
- Defined the Python-owned triage classes:
  `known_product_capability`, `new_business_feature_request`,
  `customization_request_candidate`, `admin_review_candidate`,
  `out_of_domain`, `spam_or_abuse`, `smalltalk`,
  `unclear_needs_clarification`, `possible_product_truth_candidate`, and
  `unknown`.
- Documented the intended order: authorization, active FSM ownership, direct
  executable action resolver, known Product Truth capability/topic resolver,
  Unknown / Discovery / Triage resolver, then Python-controlled outcome.
- Added examples and eval expectations for known Product Truth, new business
  feature discovery, out-of-domain questions, spam/noise, smalltalk, unclear
  requests, and admin/developer candidates.

Reason:
- Prevent Product Truth from becoming only a search index over known
  capability IDs and preserve OfficeFlow/FakturaBot as a safe business
  discovery layer.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Product_Doctrine_2030.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Customization_Request_Layer.md`
- `docs/Self_Learning_Layer.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `bot/services/product_truth.py`
- `bot/services/info_help.py`
- `bot/services/semantic_action_resolver.py`
- `tests/test_info_help.py`
- `tests/test_product_truth.py`

Constraints extracted:
- Documentation-only update.
- No runtime code, resolver, handlers, phrase dictionaries, DB/storage/schema,
  or customization request storage changes.
- Unknown / Discovery / Triage may classify only into Python-owned classes and
  must not execute, save, notify, invent capability IDs, change Product Truth,
  or mark anything as supported.
- Direct executable actions and active FSM state remain higher priority than
  InfoHelp/triage.

Touched scopes:
- Product docs/contracts/eval artifact: yes.
- Runtime code, confirmation, routing, LLM, STT, LMM, FSM, storage, DB,
  access, server, PDF/layout: unchanged.

Current implementation status:
- Product Truth MVP: implemented foundation.
- Deterministic Product Truth-backed InfoHelp fast-path: partial.
- Unknown / Discovery / Triage layer: documented, not implemented.
- Bounded InfoHelp resolver: not complete.
- Customization Request storage: unsupported runtime.
- InfoHelp Level 2: not complete.

AI maturity:
- Design documentation only. No runtime maturity increase.

Out of scope:
- Bounded InfoHelp resolver implementation.
- Customization Request storage/admin notification flow.
- Self-learning triage patterns.
- Runtime telemetry.

Self-learning hooks considered:
- Documented as future only; no learning behavior added.

Verification:
- `git diff --check` is the required verification for this docs-only update.
- Runtime tests were not required because no code changed.

## 2026-05-17 - Session 089 - Align InfoHelp Product Truth status

Summary:
- Updated the `info_help` Product Truth capability record so it matches the
  current runtime after Sessions 087-088.
- Classified current InfoHelp as partial: selected conservative Product
  Truth-backed capability/safety topics plus Level 1 unknown-input guidance.
- Removed the stale forbidden claim that live Product Truth InfoHelp does not
  exist at all.
- Kept explicit forbidden claims against overstatement: complete Level 2,
  arbitrary capability Q&A, saved customization requests, and voice/STT parity.
- Added a focused registry regression test for the `info_help` record.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `bot/services/product_truth.py`
- `tests/test_product_truth.py`
- `tests/test_info_help.py`
- `tests/test_invoice_intent_prerouter.py`

Constraints extracted:
- Product Truth must not claim roadmap or future capability as implemented.
- InfoHelp may be described only as a partial Level 2 foundation with
  deterministic fast-path coverage for selected topics.
- Full Level 2 still requires bounded InfoHelp resolver coverage, voice/STT
  parity, multilingual/noisy tests, and account-context-aware runtime evidence.
- Customization request storage and code-agent handoff remain unsupported.
- No resolver, handler, phrase dictionary, prompt, LLM/STT/LMM, DB/storage,
  access, server, or PDF/layout change belongs in this patch.

Touched scopes:
- Product Truth registry: yes, `info_help` capability metadata only.
- Tests: yes, registry-level status regression.
- Project log: yes.
- Confirmation, routing, handlers, LLM, STT, LMM, FSM, storage, DB, access,
  server, PDF/layout: unchanged.

Current implementation status:
- InfoHelp: partial.
- AI maturity: Level 2 foundation only, not complete Level 2.
- Customization requests: unsupported runtime storage.
- Code-agent handoff: unsupported runtime behavior.

Out of scope:
- Bounded InfoHelp resolver implementation.
- Broad arbitrary capability question support.
- Phrase dictionaries or handler-local keyword matching.
- Customization Request Layer storage.
- Voice/STT parity work.

Self-learning hooks considered:
- None added. Product Truth status metadata does not create learning behavior.

Product/user journey proof:
- Product Truth payloads now describe current InfoHelp honestly: selected
  supported fast-path coverage exists, but complete Level 2 is still not
  claimed.

User-facing product claim sources:
- `bot/services/product_truth.py`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `PROJECT_LOG.md`

## 2026-05-17 - Session 088 - Product UX InfoHelp smoke fix-only patch

Summary:
- Implemented the approved fix-only service patch for six failed Level 2
  InfoHelp UX smoke phrases.
- Extended conservative InfoHelp topic matching for accounting export
  materials, PDF template customization, own/custom function requests,
  code-agent handoff wording, and delete-database safety questions.
- Tightened top-level edit intent fallback so persisted invoice editing
  requires invoice-edit semantics and no longer captures PDF template
  questions; `Uprav fakturu 15` resolves to existing `edit_existing_invoice`.
- Added focused service and prerouter regression tests proving Product Truth
  answers for the failed phrases and no invoice/edit/delete execution from
  informational questions.

Contracts read:
- `AGENTS.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `bot/services/product_truth.py`
- `bot/services/info_help.py`
- `bot/services/semantic_action_resolver.py`
- `bot/handlers/invoice.py`
- `tests/test_info_help.py`
- `tests/test_invoice_intent_prerouter.py`

Constraints extracted:
- Product Truth remains the source for capability status and user-facing
  capability claims.
- InfoHelp may classify only known topic/capability IDs and must not execute
  actions.
- No new canonical action names, LLM classifier, prompt changes, handler-local
  business phrase dictionaries, DecisionResolver changes, or DB/storage/config
  changes belong in this patch.
- Direct destructive execution remains behind existing deterministic gates;
  delete-user-database final typed confirmation is unchanged.

Touched scopes:
- InfoHelp service: yes, conservative topic-bound Product Truth matching.
- Semantic action resolver: yes, narrowed top-level persisted-invoice edit
  fallback.
- Tests and project log: yes.
- `invoice.py`, handlers, DecisionResolver, prompts, LLM/STT/LMM integration,
  DB/storage/config, invoice/contact/accounting/supplier flows: unchanged.

Current implementation status:
- InfoHelp Level 2: partial, limited to controlled Product Truth topics.
- Accounting export, custom PDF templates, customization request storage, and
  code-agent handoff: unsupported runtime capabilities.
- Delete user database: supported but dangerous and confirmation-gated.
- Existing invoice edit: supported through `edit_existing_invoice`.

AI maturity:
- Level 2 partial. This patch fixes specific capability/safety smoke coverage
  without broad free-form classification, learning, or customization storage.

Out of scope:
- Broad semantic guessing, new actions, new prompts, handler routing changes,
  request persistence, code-agent execution, data migration, server changes,
  and product scope expansion.

Self-learning hooks considered:
- None added. These smoke phrases are fixed through controlled Product Truth
  topic matching, not learned aliases.

Product/user journey proof:
- Capability/safety questions receive Slovak Product Truth guidance with no
  hidden invoice/edit/delete side effects.
- Direct persisted invoice edit phrase still enters the existing bounded
  `edit_existing_invoice` route.

User-facing product claim sources:
- `bot/services/product_truth.py`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/llm/Canonical_Action_Registry.md`
- current runtime tests

Verification:
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_invoice_intent_prerouter.py` - 143 passed.
- `python -m pytest -q` - 1031 passed.

## 2026-05-17 - Session 087 - InfoHelp Level 2 first Product Truth wiring

Summary:
- Added the first Product Truth-aware InfoHelp runtime slice in
  `bot/services/info_help.py`.
- Added a conservative whitelist classifier for clearly informational
  capability/help questions and reserved unsupported send-invoice intent.
- Added Slovak Product Truth response rendering from structured registry
  payloads for supported, partial, unsupported, dangerous, and
  external-credential cases.
- Wired the existing idle invoice top-level path to Product Truth guidance only
  for unknown/reserved informational messages and narrow how-to/safety
  questions before existing action execution.
- Kept direct invoice/contact/accounting/supplier behavior, active FSM
  ownership, DecisionResolver semantics, prompts, LLM/STT/LMM calls, DB schema,
  storage, config, and Product Truth statuses unchanged.
- Updated `docs/evals/product_truth_infohelp_smoke.md` from scenarios-only to
  first partial automated Level 2 wiring coverage.

Contracts read:
- `AGENTS.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/evals/README.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `bot/services/product_truth.py`
- `bot/services/info_help.py`
- `bot/handlers/invoice.py`
- `bot/services/semantic_action_resolver.py`
- focused idle routing tests in `tests/test_invoice_intent_prerouter.py`

Constraints extracted:
- Product Truth remains the only source for capability truth.
- InfoHelp answers must be Slovak, structured, and side-effect free.
- No LLM classifier, prompt change, new canonical action, customization request
  storage, code-agent handoff, email/SMS/Google Drive/accounting-export
  implementation, or Product Truth status change belongs in this patch.
- Direct actions must remain direct actions; active FSM state must not fall
  through to idle InfoHelp.
- Reserved unsupported send-invoice intent must not become executable.

Touched scopes:
- InfoHelp service: yes, first Level 2 Product Truth renderer/classifier.
- Idle top-level invoice routing: narrow guidance hook only.
- Tests/eval/log: yes.
- Semantic resolver, DecisionResolver, active FSM flows, invoice/contact/
  accounting/supplier execution, delete-user-database final typed confirmation,
  prompts, LLM/STT/LMM, DB/storage/config/access/server/PDF layout: unchanged.

Current implementation status:
- InfoHelp Level 2: partial first runtime slice for conservative whitelisted
  topics only.
- Product Truth Registry: existing MVP foundation consumed by InfoHelp.
- Customization requests and code-agent handoff: unsupported runtime.
- Email, SMS, Google Drive, accounting export, and custom PDF templates:
  unsupported runtime capabilities.

AI maturity:
- Level 2 partial. The bot can answer selected capability/how-to/reserved
  questions from Product Truth, but broad arbitrary InfoHelp, customization
  request creation, topic learning, and code-agent handoff remain out of scope.

Out of scope:
- Broad semantic guessing.
- LLM-backed InfoHelp classification.
- Mutation from informational questions.
- Account-context DB reads for setup-aware handler answers.
- Any persisted data, storage, tenant, or authorization model change.

Verification:
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_invoice_intent_prerouter.py` - 131 passed.
- `python -m pytest -q` - 1019 passed.

## 2026-05-17 - Session 086 - Product Truth Registry MVP foundation

Summary:
- Added `bot/services/product_truth.py` as the first Python-owned runtime
  Product Truth registry foundation.
- Added the required MVP capability ids with primary product statuses limited
  to `supported`, `partial`, `planned`, `unsupported`, and `unknown`.
- Represented dangerous/setup/admin/external-credential facts as boolean
  flags, not as primary product statuses.
- Added structured query payloads for future InfoHelp consumption:
  `get_capability(...)`, `search_capabilities(...)`, and
  `get_safe_answer_payload(...)`.
- Added in-memory account-context merging so `create_invoice` can remain
  product-supported while returning account-level `requires_setup` when setup
  facts such as supplier profile, service alias, or contact are missing.
- Added `tests/test_product_truth.py` for registry validation, required ids,
  status constraints, forbidden claims, dangerous/external flags, account setup
  overlay, unknown lookup behavior, and side-effect import guards.
- Added `docs/evals/product_truth_infohelp_smoke.md` as scenarios only. It is
  explicitly marked not wired to runtime InfoHelp and not a completed Level 2
  InfoHelp eval result.

Contracts read:
- `AGENTS.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/evals/README.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/TZ_FakturaBot.md`

Constraints extracted:
- Python remains the Product Truth source of truth.
- LLM output is not Product Truth and no LLM/STT/LMM call belongs in this
  foundation patch.
- Primary product status must describe availability only; dangerous,
  requires-setup, requires-admin, and requires-external-credentials are flags.
- InfoHelp must consume Product Truth later, but Level 2 InfoHelp is not
  implemented in this patch.
- Unsupported integrations such as email, SMS, Google Drive, accounting
  export, custom PDF templates, customization request storage, and code-agent
  handoff must not be claimed supported.
- Product Truth must not change invoice/contact/accounting/supplier runtime
  behavior or tenant/access boundaries.

Touched scopes:
- Product Truth registry foundation: yes;
- product UX eval scenarios: scenario artifact only;
- project log: yes;
- InfoHelp runtime, Telegram handlers, routing, semantic resolver, prompts,
  LLM/STT/LMM integration, FSM, DB, storage, config, invoice/contact/accounting
  behavior, supplier behavior, access, server, PDF/layout: no behavior changes.

Current implementation status:
- Product Truth Registry MVP foundation: partial runtime foundation
  implemented.
- InfoHelp: still Level 1 static fallback only; Level 2 capability-aware
  InfoHelp is not implemented.
- Customization requests and code-agent handoff: unsupported runtime.

AI maturity:
- This patch is below Level 2. It creates the controlled Product Truth source
  needed by future Level 2 InfoHelp but does not answer arbitrary capability
  questions in Telegram.

Out of scope:
- InfoHelp Level 2 routing/answers.
- Any LLM/STT/LMM calls or prompt changes.
- Any DB/storage/config/server changes.
- Any invoice/contact/accounting/supplier/runtime behavior changes.
- Any customization request storage or code-agent handoff.
- Any self-learning expansion. Existing confirmed alias learning remains
  partial and cannot change Product Truth.

Product/user journey proof:
- Unit tests prove registry load, schema/status rules, required capability ids,
  unsupported-feature honesty, dangerous/external flags, account setup overlay,
  unknown lookup, and no side-effect imports.
- Human-readable eval scenarios were recorded for future Product Truth +
  InfoHelp smoke checks, but they are not marked as run because InfoHelp is not
  wired to the registry yet.

Source-of-truth basis:
- Runtime-supported claims reference current code owners, active docs, and
  focused test files.
- Unsupported/partial/planned claims are backed by `docs/Product_Truth_Layer.md`,
  `docs/Product_Truth_Registry_MVP_Design.md`, `docs/TZ_FakturaBot.md`,
  `docs/llm/Canonical_Action_Registry.md`, and `PROJECT_LOG.md`.

Verification:
- `python -m pytest -q tests/test_product_truth.py` -> 12 passed.
- `python -m pytest -q` -> 1005 passed.

## 2026-05-17 - Session 085 - Documentation cleanup after architecture review

Summary:
- Accepted the external architecture review verdict as a cleanup backlog before
  runtime implementation.
- Updated `docs/TZ_FakturaBot.md` to remove stale active-truth claims around
  real outbound email support, align InfoHelp routing/status language with
  Product Truth, and split current accounting document intake Phase 1 from
  broader planned Document Intake.
- Updated `docs/llm/Canonical_Action_Registry.md` with explicit implemented
  rows for `edit_existing_invoice` and `delete_existing_invoice`, and clarified
  reserved `send_invoice` / `edit_invoice` behavior under Product Truth /
  InfoHelp rather than generic support.
- Updated `README.md` current-runtime date framing and added an explicit
  archive warning.
- Added `docs/Product_Truth_Registry_MVP_Design.md` and
  `docs/Product_UX_Eval_Artifacts.md` to define the first concrete registry and
  eval artifact conventions before runtime work.
- Added `docs/evals/README.md` as the placeholder/index for future eval
  artifacts.

Touched scopes:
- documentation/product truth cleanup: yes;
- action registry documentation: yes;
- Product Truth registry design and eval artifact convention: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only cleanup patch.

## 2026-05-17 - Session 084 - Top-level action Product Truth and InfoHelp sync gate

Summary:
- Updated `docs/llm/New_Action_Design_Checklist.md` so new or upgraded
  top-level canonical actions must synchronize Product Truth and InfoHelp /
  support guidance, not only action registries, TZ, README, and tests.
- Added explicit requirements for capability status, limitations,
  setup/admin/external-credential flags, forbidden claims, safe next steps,
  capability/how-to answer paths, and product UX evals for new actions.

Touched scopes:
- documentation/product direction: yes;
- top-level action implementation checklist: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 083 - General implementation agent checklist

Summary:
- Added `docs/Implementation_Agent_Checklist.md` as the general implementation
  gate for approved product/customization changes that are not necessarily new
  top-level canonical actions.
- The checklist requires agents to read governing docs, inspect current code
  ownership, decide whether to integrate into existing modules or create a new
  module, analyze Product Truth, data/migration, AI, FSM, access, PDF/layout,
  risks, tests, and product UX evals before coding.
- Updated `AGENTS.md`, `README.md`, `docs/Code_Agent_Handoff_Contract.md`,
  `docs/Customization_Request_Layer.md`, and
  `docs/Evaluation_and_Smoke_Test_Standards.md` to reference the new checklist.

Touched scopes:
- documentation/product direction: yes;
- implementation-agent checklist: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 082 - Evaluation and smoke test standards

Summary:
- Added `docs/Evaluation_and_Smoke_Test_Standards.md` as the mandatory
  evaluation contract for AI/product layers, Product Truth, InfoHelp,
  customization requests, self-learning, code-agent handoff, FSM recovery,
  access safety, document intake, PDF/layout, and migration/server checks.
- Clarified that unit tests are required but not sufficient for Level 2+
  AI/product layers; product UX evals and smoke scenarios must prove real user
  journeys, truthfulness, safety, state-awareness, and no hidden side effects.
- Updated `AGENTS.md`, `README.md`, `docs/Product_Doctrine_2030.md`,
  `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`,
  `docs/Info_Help_Guidance_Layer.md`, `docs/Customization_Request_Layer.md`,
  `docs/Self_Learning_Layer.md`, and `docs/Code_Agent_Handoff_Contract.md` to
  reference the new evaluation contract.

Touched scopes:
- documentation/product direction: yes;
- evaluation and smoke-test contract: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 081 - Self-learning and code-agent handoff contracts

Summary:
- Added `docs/Self_Learning_Layer.md` as the umbrella contract for controlled
  learning beyond current invoice customer/service aliases.
- Added `docs/Code_Agent_Handoff_Contract.md` as the contract for converting
  approved customization/product requests into bounded implementation tasks
  with docs, scope, tests, evals, no-go constraints, rollback notes, and human
  approval gates.
- Updated `docs/Confirmed_Semantic_Alias_Learning_Contract.md` to clarify that
  it remains the focused runtime contract for current confirmed aliases under
  the broader self-learning policy.
- Updated `AGENTS.md`, `README.md`, `docs/Product_Doctrine_2030.md`,
  `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`,
  `docs/Customization_Request_Layer.md`, and
  `docs/Info_Help_Guidance_Layer.md` to reference the new contracts.

Touched scopes:
- documentation/product direction: yes;
- self-learning and code-agent handoff contracts: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 080 - Product Truth and Customization Request contracts

Summary:
- Added `docs/Product_Truth_Layer.md` as the source-of-truth contract for
  supported/partial/planned/unsupported/unknown/dangerous/setup/admin/external
  credential capability answers.
- Added `docs/Customization_Request_Layer.md` as the contract for turning
  unsupported, partial, planned, unknown, or account-specific business needs
  into confirmed pending requests instead of fake promises or blind fallback.
- Updated `AGENTS.md`, `README.md`, `docs/Product_Doctrine_2030.md`,
  `docs/AI_Layer_Implementation_Standards.md`, and
  `docs/Info_Help_Guidance_Layer.md` to reference the new contracts.

Touched scopes:
- documentation/product direction: yes;
- Product Truth and customization request contracts: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 079 - AI layer standards and InfoHelp contract reset

Summary:
- Added `docs/AI_Layer_Implementation_Standards.md` as the mandatory maturity
  and acceptance contract for AI-facing product layers.
- Rewrote `docs/Info_Help_Guidance_Layer.md` from a Phase 1 fallback-oriented
  planning spec into a Level 2+ capability-aware support concierge contract.
- Clarified that current top-level InfoHelp fallback behavior remains Level 1
  only until Product Truth, capability-aware Q&A, customization request
  creation, controlled learning, and UX evals exist.
- Updated `AGENTS.md`, `README.md`, and `docs/Product_Doctrine_2030.md` so the
  new AI-layer standard is part of the active documentation set.

Touched scopes:
- documentation/product direction: yes;
- InfoHelp contract: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 078 - Archive superseded planning and audit docs

Summary:
- Moved superseded historical planning/audit/task docs out of the active documentation set:
  - `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` -> `docs/archive/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md`
  - `docs/Invoice_Draft_Review_Lifecycle_Design.md` -> `docs/archive/Invoice_Draft_Review_Lifecycle_Design.md`
  - `docs/llm/Confirmation_Decision_Audit_2026-04-14.md` -> `docs/archive/llm/Confirmation_Decision_Audit_2026-04-14.md`
  - `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md` -> `docs/archive/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`
- Updated `README.md` so active docs no longer list archived planning files as current planning docs.
- Updated `docs/archive/README.md` with the newly archived documents and their historical role.
- Updated `AGENTS.md` to state that `docs/archive/` is historical context only and must not be used as active source of truth.

Touched scopes:
- documentation organization: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access, server: no behavior changes.

Verification:
- Tests not run; documentation-only archive move.

## 2026-05-16 - Session 077 - Product doctrine and agent contract reset

Summary:
- Rewrote `AGENTS.md` as the main OfficeFlow/FakturaBot agent contract instead of a narrow Telegram-bot MVP instruction file.
- Added `docs/Product_Doctrine_2030.md` as the product north-star: OfficeFlow/FakturaBot is an AI-assisted business operating layer, not a command bot.
- Clarified the current runtime truth: controlled tenant-scoped multi-user runtime exists, while full SaaS, public signup, billing, per-client bot/runtime provisioning, and complex role/workspace administration remain not implemented.
- Preserved and strengthened existing safety rules: no invented project state, docs-first work, approval discipline, migration safety, Python-owned execution, DecisionResolver, access boundaries, OfficeFlow attachment boundaries, and project-log discipline.
- Added explicit AI-layer maturity language so static fallback/repair work cannot be called a completed AI product layer.
- Added Product Truth, customization request, self-learning, code-agent handoff, state-aware explanation, and product UX evaluation expectations as mandatory project direction.

Source material:
- `AGENTS.md`
- `PROJECT_LOG.md` read from first line to last line before the patch
- prior read-only audit context over the listed FakturaBot/OfficeFlow docs and runtime files

Touched scopes:
- documentation/product direction: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access, server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 076 - Invoice edit fallback examples

Summary:
- Added an example date to invoice edit invalid-date recovery copy: `DD.MM.RRRR, napr. 15.03.2026`.
- Made invoice item numeric edit invalid-value recovery copy field-specific: quantity examples for `edit_item_quantity`, price examples for `edit_item_unit_price` and `edit_item_total_amount`.
- Kept the existing cancel hint unchanged: `Ak nechcete pokračovať v úprave, napíšte „zrušiť“.`
- Did not change InfoHelp, routing, DB/storage/PDF paths, LLM behavior, delete flows, `/start`, `/menu`, accounting/contact/service flows, or action switching.

Contracts read:
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/Canonical_Decision_Resolver_Contract.md`

Constraints extracted:
- active FSM state owns invoice edit recovery and must not fall through to top-level routing;
- invoice item quantity, unit price, and total amount edits are precision-sensitive exact-value steps;
- Python validates exact values and state data, while LLM/routing behavior remains out of scope;
- fallback copy must stay Slovak and preserve the existing state-cancel hint.

Touched scopes:
- FSM: yes, invoice edit fallback copy only;
- confirmation/routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_invoice_state_decisions.py` -> `71 passed`.
- `python -m pytest -q` -> `993 passed`.

## 2026-05-15 - Session 075 - Phase 1 top-level info help fallback

Summary:
- Added deterministic Phase 1 top-level `info_help` guidance for idle unknown text input.
- Routed idle voice unknown transcripts through the same `process_invoice_text(...)` unknown fallback guidance.
- Kept active FSM handlers, FSM recovery hints, global cancel, `/start`, `/menu`, delete database flow, DB schema, storage paths, invoice PDF paths, Google Drive, LMM/accounting extraction, action switching, and buttons/callbacks unchanged.
- Did not implement Phase 2/3 runtime explainability or LLM-backed help-topic resolution.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/Info_Help_Guidance_Layer.md`

Constraints extracted:
- top-level action resolution runs first and `info_help` may run only after a top-level miss;
- Phase 1 guidance must be deterministic/template-based and must not add a new LLM call;
- known top-level actions must continue through existing Python-owned routes;
- active FSM state must not fall through to top-level action routing or `info_help`;
- user-facing guidance must stay Slovak and must not claim planned Phase 2/3 explainability runtime exists.

Touched scopes:
- top-level routing: yes, unknown-only fallback copy through `process_invoice_text(...)`;
- voice: yes, idle voice benefits through the existing `process_invoice_text(...)` path only;
- FSM/confirmation/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_state_control.py` -> `152 passed`.
- `python -m pytest -q` -> `993 passed`.

## 2026-05-15 - Session 074 - Accounting and OfficeFlow recovery hints

Summary:
- Added Slovak cancel recovery hints to invalid/wrong-input accounting document intake fallbacks for upload waiting, duplicate decision, and preview decision states.
- Added Slovak cancel recovery hints to OfficeFlow idle attachment accounting proposal, route choice, and document-type clarification fallbacks.
- Kept successful paths, state transitions, temp staging lifecycle, cleanup behavior, LMM classification/extraction, confirmed accounting storage, Google Drive, DB schema, storage paths, invoice PDF paths, top-level `info_help`, and FSM action switching unchanged.

Contracts read:
- `AGENTS.md`
- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Canonical_Decision_Resolver_Contract.md`

Constraints extracted:
- active OfficeFlow/accounting FSM state remains owned by its state handlers and must not fall through to top-level action routing;
- Python keeps ownership of validation, confirmation, cleanup, and save side effects;
- temporary attachment/accounting staging paths remain temporary only and confirmed accounting storage is not touched by fallback copy changes;
- LMM classification/extraction, accounting categorization, Google Drive sync, DB schema, storage paths, and invoice PDF paths are out of scope;
- confirmation-like replies continue through the shared DecisionResolver families;
- user-facing fallback text must stay Slovak and should use `zrušiť` instead of `/start` for temp-staged flows.

Touched scopes:
- FSM: yes, invalid/wrong-input fallback copy only in accounting intake and OfficeFlow attachment routing states;
- confirmation: no new decision family, existing DecisionResolver calls unchanged;
- routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_officeflow_attachment_router.py tests/test_state_control.py` -> `65 passed`.
- `python -m pytest -q` -> `989 passed`.

## 2026-05-15 - Session 073 - Business FSM recovery hints

Summary:
- Added Slovak cancel recovery hints to invalid contact intake/manual contact fallbacks.
- Added Slovak cancel recovery hints to service alias empty-value fallbacks.
- Added Slovak cancel recovery hints to invoice exact-value edit fallbacks for service, invoice number, date, numeric, and item description values.
- Kept successful paths, state transitions, DB writes, PDF generation, storage paths, delete database flow, top-level `info_help`, and FSM action switching unchanged.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Canonical_Action_Registry.md`

Constraints extracted:
- active FSM state remains owned by its handler and must not execute top-level actions from invalid input;
- LLM may only do bounded canonicalization where already designed and must not become a free-form fallback;
- confirmation-like decisions stay routed through the shared DecisionResolver;
- exact business values remain text-first and Python-validated;
- user-facing fallback text must stay Slovak;
- no DB schema, storage path, invoice PDF path, delete database final gate, top-level `info_help`, FSM action switching, buttons/callbacks, Google Drive, accounting intake, or OfficeFlow router changes belong in this patch.

Touched scopes:
- FSM: yes, invalid-value/wrong-input fallback copy only in contact, service alias, and invoice exact-value edit states;
- confirmation: no new decision family, existing confirmation paths unchanged except unknown fallback copy;
- routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_contact_intake_semantic_flow.py tests/test_service_alias_flow.py tests/test_invoice_state_decisions.py tests/test_state_control.py` -> `99 passed`.
- `python -m pytest -q` -> `985 passed`.

## 2026-05-15 - Session 072 - Destructive and onboarding recovery hints

Summary:
- Added Slovak safe-exit hints to wrong-input destructive confirmation fallbacks for scoped database deletion and existing invoice deletion.
- Added Slovak cancel/restart hints to invalid-value onboarding steps without changing successful onboarding paths.
- Kept the exact database deletion confirmation phrase unchanged and preserved global `zrušiť` / `назад` cancellation behavior.
- Did not add top-level `info_help`, FSM action switching, buttons/callbacks, DB schema changes, storage path changes, or invoice PDF path changes.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/Info_Help_Guidance_Layer.md`

Constraints extracted:
- active FSM state remains owned by its current handler and must not execute top-level actions from invalid input;
- destructive delete confirmations must not mention `/start` and must preserve the final exact typed confirmation gate;
- non-destructive onboarding recovery may mention `/start` because active `/start` clears FSM state and restarts setup/status guidance;
- user-facing recovery text must stay Slovak;
- no DB schema, storage path, invoice PDF path, Google Drive, accounting intake, contacts, service alias, or general voice routing changes belong in this patch.

Touched scopes:
- FSM: yes, invalid-value/wrong-input fallback copy only;
- confirmation: yes, existing shared decision flows keep their current yes/no/exact gates;
- routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_state_control.py tests/test_delete_user_database_flow.py tests/test_invoice_state_decisions.py tests/test_onboarding_decisions.py` -> `93 passed`.
- `python -m pytest -q` -> `982 passed`.

## 2026-05-15 - Session 071 - FSM recovery hints and deterministic exact cancel

Summary:
- Changed exact global cancel text shortcuts to run `cancel_current_state(...)` directly without entering the LLM-backed global cancel resolver.
- Kept `/cancel` and `/start` behavior unchanged: `/cancel` cancels active state, while `/start` clears active FSM state and shows the current start/status guidance.
- Added `назад` as a deterministic cancel/back-style shortcut because there is no separate back action in the current FSM architecture.
- Added Slovak recovery hints to invoice edit FSM menu/choice fallbacks so noisy input repeats the state-specific menu and explains `zrušiť` and `/start`.
- Did not add top-level `info_help`, FSM action switching, new buttons/callbacks, DB schema changes, storage path changes, or invoice PDF path changes.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/Info_Help_Guidance_Layer.md`

Constraints extracted:
- active FSM state remains owned by its state handlers and must not fall through to top-level routing;
- exact global cancel shortcuts are deterministic Python state control, not LLM interpretation;
- non-exact/bounded semantic interpretation may still use the existing resolver path where already designed;
- `info_help` remains planned/docs-only and is not implemented in this slice;
- user-facing recovery text must stay Slovak;
- `/start` is safe to mention as a restart because the active `/start` handler clears FSM state;
- final `delete_user_database` confirmation remains an exact typed-text gate and is unchanged;
- no DB schema, storage path, invoice PDF path, or persisted-data migration is involved.

Touched scopes:
- FSM: yes, invoice edit menu/choice fallback copy only;
- routing: yes, exact global cancel shortcut path and active-FSM top-level guard tests;
- LLM/STT: yes, exact text and exact STT transcript global cancel now bypass the LLM resolver;
- confirmation/state-control: yes, global state cancel behavior;
- storage/DB/access/server: no runtime behavior changes.

Verification:
- `python -m pytest -q tests/test_decision_resolver.py tests/test_state_control.py tests/test_voice_state_routing.py tests/test_invoice_intent_prerouter.py tests/test_invoice_state_decisions.py` -> `643 passed`.
- `python -m pytest -q` -> `982 passed`.

## 2026-05-09 - Session 070 - Profile edit return menu alignment

Summary:
- Reused the `/start` staged setup/status navigation after successful `/upravit_profil` saves.
- Ready users now see the main operational menu after profile edits, including create/view invoice options, instead of always being pointed back to `/sluzbu`.
- Added show/edit invoice wording to the advanced `/start` navigation.
- Expanded `/menu` into the broader user-facing capability list, including create/show/edit/delete existing invoice flows without exposing internal canonical tokens as slash commands.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `CHANGELOG.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- `/start` is the source of the staged setup/status menu for approved users;
- ready users should get the main operational menu, while incomplete users should see only the next missing setup step;
- `/menu` may list broader user-facing capabilities, but internal canonical tokens such as `edit_existing_invoice` must not be presented as Telegram slash commands;
- `/vymazat_databazu` menu wording must not imply a simple restart; the flow deletes scoped data and removes bot access until reapproval;
- profile edit exact values remain text-only and Python-validated;
- no new top-level action, DB schema, storage layout, access rule, or LLM prompt change is required.

Touched scopes:
- routing/FSM: yes, post-profile-edit response navigation only;
- access: no policy change, reused approved-user `/start` status logic;
- LLM/STT/confirmation/storage/DB/server: no.

Verification:
- `python -m pytest -q tests/test_access_request_flow.py tests/test_onboarding_decisions.py tests/test_delete_user_database_flow.py` -> `34 passed`.
- `python -m pytest -q` -> `983 passed`.

## 2026-05-09 - Session 069 - State reset and read-only invoice view

Summary:
- Added canonical top-level action `show_existing_invoice` for read-only viewing of an existing outgoing invoice by number/reference.
- Split “show/open invoice” from `edit_existing_invoice`: viewing sends the invoice summary/PDF and clears FSM state; editing still enters the bounded persisted invoice edit FSM.
- Added global state cancellation through `/cancel` and shared DecisionResolver-backed text/voice cancel wording (`zrušiť`, `скасувати`, `відмінити`, `відминити`, `отменить`, “почни з початку”).
- Made `/start`, `/menu`, existing `/moj_profil` display, and `/blocek` behave as stateless interruptions by clearing active FSM state where applicable.
- Kept persisted invoice edit cancellation safe: leaving `waiting_pdf_decision` after a persisted edit exits edit mode without deleting the stored invoice; newly generated unconfirmed invoice cancellation still uses existing cleanup.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `CHANGELOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Constraints extracted:
- new top-level actions require registry/docs/runtime/tests/voice reachability;
- active FSM state normally wins over idle routing, but explicit system/read-only commands may be state-clearing interruptions;
- confirmation/cancel-like wording must go through `bot/services/decision_resolver.py`;
- Python owns supplier-scoped invoice lookup, validation, FSM changes, DB/file side effects, and cleanup;
- voice may launch top-level actions but must not fill exact invoice numbers or destructive exact confirmations;
- temp Document Intake/OfficeFlow cleanup must remain restricted to approved temporary staging paths;
- no DB schema or storage layout migration is allowed in this slice.

Touched scopes:
- FSM: yes, global cancel and stateless read-only interruption behavior;
- routing: yes, new `show_existing_invoice` top-level route and `/start`/`/blocek` state reset behavior;
- LLM/STT: yes, bounded top-level action resolver, active-state voice cancellation, and voice reachability tests;
- confirmation/decision: yes, new `global_state_cancel` DecisionResolver family;
- storage: temporary intake cleanup only;
- DB: no schema changes, no migration; existing invoice read/delete behavior unchanged except safe persisted-edit cancel;
- access/server: no runtime server writes or access model changes; server logs were read-only inspected.

Verification:
- `python -m pytest -q tests\test_decision_resolver.py tests\test_invoice_intent_prerouter.py tests\test_voice_state_routing.py tests\test_access_request_flow.py tests\test_state_control.py` -> `579 passed`.
- `python -m pytest -q tests\test_voice_state_routing.py tests\test_state_control.py tests\test_decision_resolver.py` -> `463 passed`.
- `python -m pytest -q` -> `968 passed`.

## 2026-05-06 - Session 068 - Invoice service raw mention self-learning

Summary:
- Implemented confirmed semantic service alias learning for invoice service raw mentions extracted from text/STT.
- Added `ServiceAliasService` support for `confirmed_semantic_alias` domain `invoice_service`, target type `supplier_service_alias`, and a default cap of 10 aliases per service target per supplier/domain.
- Integrated confirmed service alias lookup into invoice service resolution after exact manual `/sluzbu` alias lookup and before bounded LLM fallback.
- Wired approved invoice previews to store safe `service_raw_mention` variants only when the service resolved to one existing manual service mapping.
- Kept `supplier_service_alias` as the manual `/sluzbu` table only; learned practical variants are not written there and do not rewrite service titles or invoice item descriptions.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`
- `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`

Constraints extracted:
- Python remains the only lookup, validation, persistence, and execution authority;
- LLM/STT may provide raw service mention candidates only;
- learned service aliases must target existing supplier-scoped manual service mappings;
- `supplier_service_alias` remains user-owned manual `/sluzbu` storage and must not receive learned variants;
- alias persistence requires approved invoice preview where the resolved service is visible;
- exact-value service alias creation remains text-only through `/sluzbu`;
- no DB schema, storage layout, access, server, or confirmation behavior change is required.

Touched scopes:
- invoice runtime/service lookup: yes;
- persisted DB rows: yes, existing `confirmed_semantic_alias` table only;
- LLM prompt/parser: no new prompt shape beyond existing `service_raw_mention`;
- confirmation: no behavior change, uses existing preview approval;
- FSM: no new states;
- DB schema/storage/access/server: no schema, storage, authorization, or server writes.

Verification:
- `python -m pytest -q tests/test_service_alias_service.py tests/test_invoice_phase2_ai_layer.py::test_preview_uses_service_raw_mention_as_alias_candidate tests/test_invoice_phase2_ai_layer.py::test_preview_rejects_full_command_as_service_alias_candidate tests/test_invoice_phase2_ai_layer.py::test_resolve_service_alias_bounded_uses_confirmed_semantic_alias tests/test_invoice_state_decisions.py::test_preview_approval_stores_confirmed_service_alias_from_raw_mention tests/test_invoice_state_decisions.py::test_preview_cancel_does_not_store_service_alias` -> `14 passed`.
- `python -m pytest -q` -> `948 passed`.

## 2026-05-06 - Session 067 - Invoice raw customer mention extraction

Summary:
- Added optional `biznis_sk.odberatel_raw_mention` to the invoice draft prompt as the source/STT phrase for the customer/company mention.
- Added optional `biznis_sk.service_raw_mention` and per-item `service_raw_mention` prompt/parser support as future-ready extraction fields only.
- Preserved normalized Python-facing fields: `odberatel_kandidat`, `polozka_povodna`, and `termin_sluzby_sk` remain the lookup/validation inputs.
- Allowed the invoice parser to keep the new optional raw mention fields without breaking older payloads.
- Wired only `odberatel_raw_mention` into existing contact alias learning as a safe candidate; alias persistence still happens only after preview approval or explicit alias confirmation.
- Added safety filtering so a full invoice command, amount/date/payment-like data, or command phrase is not stored as a contact alias candidate.
- Did not implement service confirmed-alias persistence; `/sluzbu` manual aliases and service runtime behavior remain unchanged.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`

Constraints extracted:
- Python remains the execution, lookup, validation, and persistence authority;
- LLM may extract raw/source mention candidates but must not create aliases or claim contact/service matches;
- raw aliases must come from isolated customer/service phrases, not full invoice commands;
- contact aliases may be stored only after preview approval or explicit confirmation;
- service semantic alias persistence is future work and must not write to `supplier_service_alias` in this slice;
- no DB schema, storage layout, access, or confirmation behavior change is required.

Touched scopes:
- LLM prompt: yes, invoice draft prompt shape;
- invoice parser/runtime: yes, optional fields and contact alias candidate selection;
- confirmation: no behavior change;
- FSM: no new states;
- DB/storage/access/server: no schema, storage, authorization, or server writes.

Verification:
- `python -m pytest -q tests/test_invoice_phase2_ai_layer.py tests/test_invoice_state_decisions.py::test_preview_approval_stores_confirmed_customer_alias tests/test_invoice_state_decisions.py::test_preview_approval_stores_confirmed_customer_alias_from_raw_mention tests/test_invoice_state_decisions.py::test_preview_cancel_does_not_store_customer_alias` -> `66 passed`.
- `python -m pytest -q` -> `940 passed`.

## 2026-05-06 - Session 066 - Runtime documentation tree and new-action checklist alignment

Summary:
- Updated the agent-facing top-level action completion gate: a new canonical top-level action is not considered implemented until the registry, Python route, resolver integration, text/command path, tests, and voice reachability or an explicit voice exclusion are covered.
- Reworked `docs/llm/New_Action_Design_Checklist.md` into a practical implementation guide for future top-level actions.
- Mined recurring project failure patterns from `PROJECT_LOG.md` into the checklist, including literal prompt matching, dead phrase dictionaries, voice gaps, FSM fallthrough, premature action exposure, `edit_invoice` vs `edit_existing_invoice` confusion, exact-value voice mistakes, and docs/runtime/test drift.
- Updated LLM/DecisionResolver contracts to reflect current Phase 2 runtime boundaries rather than treating Decision UI Phase 1 as the current endpoint.
- Updated the README into an architecture tree of runtime top-level actions, subflows, in-FSM controls, voice boundaries, and not-implemented areas.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

Constraints extracted:
- Python/FSM remains the execution authority; LLM may only canonicalize or draft within bounded allowed outputs;
- top-level voice coverage is part of implementation completeness unless the action is intentionally text/button/file-only;
- active FSM state wins over idle/top-level routing;
- exact values and destructive confirmations remain text-first;
- confirmation-like replies remain owned by the shared Canonical DecisionResolver;
- docs must not describe reserved or planned behavior as implemented runtime.

Touched scopes:
- routing/LLM/FSM/voice/confirmation docs: yes, documentation alignment only;
- runtime code, DB, storage, access, server: no changes.

## 2026-05-06 - Session 065 - Tenant storage migration gap and repair governance

Summary:
- Recorded the discovered tenant-scope data routing gap as a migration/repair issue, not as data loss.
- Server read-only inventory found existing confirmed accounting document originals and metadata JSON under legacy workspace `mykhailo-szco`.
- `/blocek` uses tenant-scoped recent-document routing, so it does not read legacy owner metadata from `mykhailo-szco`.
- Invoice DB rows exist, but some historical `invoice.pdf_path` values point to local Windows paths and are invalid on the Linux server.
- Server dry-run repair plan found 17 accounting metadata JSON files and 17 matching originals that can be copied from `mykhailo-szco` into the owner tenant workspace with metadata storage fields rewritten.
- Server dry-run found 3 invoice rows with Windows-local `pdf_path` values, but no unambiguous matching PDF files on the server for those invoice numbers, so invoice repair requires a separate decision or PDF regeneration.
- After explicit approval, the bloček repair was applied on the server: backup created under `/bot/repo/data/backups/tenant-storage-repair-20260506T111128Z`, 17 metadata JSON files and 17 originals copied into the owner tenant workspace, and 17 metadata storage blocks rewritten.
- Post-repair runtime registry validation returned 5 recent accounting documents for the owner tenant workspace; bad JSON and missing original references were 0.
- After explicit approval, invoice PDFs `20260003` and `20260004` were regenerated on the server from existing DB rows/items and their `invoice.pdf_path` values were updated to tenant-scoped server paths. Backup was created under `/bot/data/storage/backups/invoice-pdf-repair-20260506T134251Z`.
- Post-repair invoice path validation showed PDFs exist for `20260001`, `20260003`, `20260004`, `20260005`, and `20260006`; `20260002` remains a draft row with a historical Windows-local `pdf_path` and no matching server PDF.
- Added migration-sensitive data rules to `AGENTS.md`.
- Added `docs/FakturaBot_Data_Migration_Runbook.md` for audit, backup, dry-run, apply, and post-repair validation workflow.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Constraints extracted:
- supplier profile data is DB-backed and scoped by `telegram_id`;
- outgoing invoices are DB-backed by `supplier_telegram_id`, while PDFs are resolved through persisted `invoice.pdf_path`;
- accounting documents consist of confirmed originals plus metadata JSON sidecars;
- recent accounting document view reads only confirmed metadata under the requesting tenant workspace;
- legacy `mykhailo-szco` must not become a cross-tenant fallback source in multi-user dry run;
- server-side data repair requires backup, dry-run, and explicit apply approval.

Touched scopes:
- confirmation/routing/LLM/FSM/access: no runtime behavior change;
- storage/DB: documented migration-sensitive issue and governance only;
- server: read-only inventory only, no data writes.

## 2026-05-06 - Session 064 - In-action voice control cleanup

Summary:
- Added voice routing for supplier profile field selection inside `SupplierProfileEditStates.field`.
- Added voice routing from `InvoiceStates.waiting_input` into the same invoice text processing path used by `/invoice` text input.
- Kept supplier profile value entry text-first; voice in `SupplierProfileEditStates.value` still asks for typed text.
- Changed contact missing-field intake voice handling to ask for typed text because that state captures business data values, not command choices.
- Changed invoice-number edit value voice handling to ask for typed text; voice can still choose the edit-number action in the previous bounded action-selection state.
- Added supplier profile field selection fallback through the shared Semantic Action Resolver after Python fast-path aliases fail.

Contracts read:
- `AGENTS.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`

Constraints extracted:
- Active FSM state wins over top-level routing;
- voice can control bounded state actions/field choices when Python supplies allowed outputs;
- exact value capture remains text-first for invoice numbers, identifiers, bank/email fields, numeric values, descriptions, and destructive confirmations;
- `voice.py` must not contain business phrase dictionaries.

Touched scopes:
- confirmation: no new confirmation family;
- routing/voice routing: yes, in-FSM voice routing only;
- LLM prompt behavior: no;
- FSM/DB/storage/access/server: no.

## 2026-05-06 - Session 063 - Supplier profile edit confirmation wording

Summary:
- Updated the targeted supplier profile edit confirmation message.
- Removed the inline `ano` / `nie` instruction from the message because the confirmation buttons already provide the available actions.
- Kept the shared `yes_no` DecisionResolver flow, FSM behavior, callbacks, DB writes, and access checks unchanged.

Contracts read:
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`

Constraints extracted:
- confirmation-like replies must continue through `bot/services/decision_resolver.py`;
- button callbacks must converge into the same state-aware confirmation handler;
- UI wording can change without adding local confirmation parsing or changing canonical decision outputs.

Touched scopes:
- confirmation: yes, UI wording only;
- routing/LLM/FSM/storage/DB/access/server: no behavior change.

## 2026-05-06 - Session 062 - STT transcription context prompt

Summary:
- Added a compact multilingual FakturaBot / OfficeFlow context prompt to the STT transcription call.
- The prompt tells the transcription model to expect Slovak, Ukrainian, Russian, English, and mixed Surzhyk / mixed Slovak-Ukrainian-Russian-English speech.
- The prompt explicitly keeps STT as transcription only: no translation, no summary, no conversion into commands, and no canonical action routing.
- Kept `voice.py`, semantic action routing, confirmation logic, FSM execution, DB, and storage unchanged.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`

Constraints extracted:
- Python authorization and tenant scoping must happen before STT/LLM/LMM;
- STT may produce only a raw transcript candidate;
- Python/FSM/DecisionResolver/Semantic Action Resolver remain responsible for state, routing, validation, and side effects;
- voice transport code must not become a business-command router.

Touched scopes:
- confirmation: no;
- routing/voice routing: no `voice.py` change;
- LLM/STT prompt behavior: yes, STT transcription prompt only;
- FSM/DB/storage/access/server: no.

## 2026-05-06 - Session 061 - Top-level LLM action context repair

Summary:
- Repaired top-level Semantic Action Resolver guidance so SK/UK/RU/mixed user input is interpreted into Slovak FakturaBot product semantics before choosing one allowed canonical action.
- Expanded `show_supplier_profile` and `edit_supplier` action context as supplier/company/business/billing profile semantics instead of narrow "profile" wording or command aliases.
- Kept `voice.py` unchanged; voice remains STT/state routing only.
- Adjusted tests so natural/polite top-level phrases with an API key exercise the bounded resolver path instead of requiring Python alias coverage.

Contracts read:
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Python defines `allowed_actions`, validates output, and executes existing routes;
- LLM canonicalizes multilingual/noisy input by internally normalizing the user meaning into Slovak FakturaBot product semantics within those bounds;
- `action_hints` are compact domain context, not keyword-parser replacement;
- deterministic aliases must remain a narrow fast path, not the primary voice reachability mechanism.

Touched scopes:
- confirmation: no;
- routing/voice routing: no `voice.py` change, but top-level semantic routing behavior is affected;
- LLM prompt behavior: yes;
- FSM/DB/storage/access/server: no.

## 2026-05-05 - Session 060 - Delete user database runtime flow

Summary:
- Implemented `delete_user_database` as a destructive leave/reset flow.
- Added `/vymazat_databazu` and bounded top-level text/voice intent routing that only start a Slovak warning + exact-confirmation FSM.
- Required exact typed confirmation phrase `vymazať databázu`; voice in the final confirmation state is rejected before STT and cannot delete.
- Added scoped deletion service for current user's supplier profile, contacts, invoices/items, service aliases, invoice-number settings, confirmed semantic aliases, tenant invoice PDFs, tenant workspaces, tenant upload staging dirs, and only contract files referenced by that user's contacts.
- Added `deleted_database` access/request status behavior: active access is revoked without removing the `authorized_users` row, future `/start` creates a new pending request, and `/approve` reactivates the user with old business data gone.
- Preserved `blocked` as admin-blocked, kept existing invoice delete flow unchanged, and did not touch `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Python owns authorization, tenant scope, deletion, and side effects;
- resolver/LLM may only classify `delete_user_database` when Python includes it in `allowed_actions`;
- final deletion confirmation is an exact typed destructive exception, not a yes/no DecisionResolver flow;
- voice must not pass final confirmation;
- deleted users are not authorized, including static allowlist users, until admin reapproval.

Touched scopes:
- confirmation: yes, exact typed destructive exception;
- routing/voice routing: yes;
- FSM: yes;
- LLM prompt behavior: no prompt file changes; bounded resolver remains allowed-actions only;
- DB/storage/access: yes;
- server/Git history: no.

Verification:
- `python -m pytest -q tests/test_delete_user_database_flow.py tests/test_access_request_flow.py` -> `23 passed`.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_tenant_safety.py` -> `138 passed`.
- `python -m pytest -q tests/test_decision_resolver.py` -> `408 passed`.
- `python -m pytest -q` -> `926 passed`.

## 2026-05-05 - Session 059 - Top-level voice command reachability

Summary:
- Made existing canonical top-level/system actions voice-reachable through the shared Semantic Action Resolver and existing Python route handlers.
- Added bounded top-level routing for `start`, `show_supplier_profile`, `edit_supplier`, `show_recent_accounting_documents`, and `add_receipt`.
- Reused existing `/start`, `/moj_profil`, `/upravit_profil`, `/blocek`, and `/add_blocek`/`/dodat_blocek` flows instead of duplicating business logic.
- Kept `voice.py` as transport/STT/state routing only; it now refuses unhandled active FSM voice input with a text-required message instead of falling through to top-level routing.
- Kept `edit_invoice` as in-action/FSM invoice editing and preserved `edit_existing_invoice` for persisted invoice editing.
- Kept `add_receipt` as upload-waiting flow only: voice text does not create invoices, extract receipts, or save accounting documents.
- Did not expose or implement `delete_user_database`.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`

Constraints extracted:
- Python remains the execution and validation authority;
- resolver output must be one Python-allowed canonical token or `unknown`;
- `voice.py` must not contain business phrase dictionaries;
- confirmation-like replies must continue through `bot/services/decision_resolver.py`;
- exact/manual fields remain text-first;
- destructive/manual confirmation gates must not be weakened.

Touched scopes:
- confirmation: no new decision family;
- routing/voice routing: yes;
- FSM: yes, route reuse and active-state safety fallback only;
- LLM prompt behavior: no prompt file changes; bounded resolver payload remains strict;
- DB schema/storage model/server: no.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_accounting_documents_handler.py tests/test_accounting_document_intake_flow.py tests/test_onboarding_decisions.py tests/test_decision_resolver.py` -> `579 passed`.
- `python -m pytest -q` -> `918 passed`.

## 2026-05-05 - Session 058 - Shared STT ano artifact fallback

Summary:
- Consolidated known spoken `áno` STT artifacts in the shared Canonical DecisionResolver/semantic lexicon layer.
- Normalized `Ah, não`, `Ah no`, `Ah ňao`, and `Ахняо` to affirmative `yes` for the `yes_no` family before LLM fallback.
- Kept invoice preview approve/edit/cancel behavior aligned so the same artifacts resolve to `approve` where `áno` is already an approve alias.
- Preserved standalone `no`, `nó`, `noo`, and `nou` as non-affirmative inputs; no handler dictionaries or button callback changes were added.

Contracts read:
- `AGENTS.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`

Constraints extracted:
- confirmation-like text and voice replies must pass through `bot/services/decision_resolver.py`;
- deterministic known STT artifacts must be handled in one shared resolver/lexicon layer;
- handlers must branch only on canonical outputs and must not define local confirmation dictionaries;
- LLM prompts must not change, and deterministic artifacts must not be routed to LLM.

Touched scopes:
- confirmation: yes;
- routing/callback routing: no;
- FSM: no;
- LLM prompt behavior: no;
- DB schema/storage model/server: no.

Verification:
- `python -m pytest -q tests\test_decision_resolver.py` -> `408 passed`.
- `python -m pytest -q` -> `904 passed`.

## 2026-05-05 - Session 057 - Decision UI Layer Phase 1

Summary:
- Added Telegram inline decision buttons for stable confirmation flows: invoice preview, invoice customer alias confirmation, invoice delete confirmation, contact confirmations, supplier onboarding confirmation, and supplier profile edit confirmation.
- Added a shared decision callback dispatcher that accepts only canonical Phase 1 callback tokens: `decision:yes`, `decision:no`, `decision:approve`, `decision:edit`, and `decision:cancel`.
- Kept text and voice confirmation replies on the Canonical DecisionResolver path; button callbacks skip LLM/STT/LMM and pass pre-canonicalized tokens into the same state-aware handler execution paths.
- Added callback-query authorization middleware so unauthorized or blocked users cannot trigger decision callback side effects.
- Left standalone contract save/archive buttons, OfficeFlow route/document-type buttons, `reupload`, and accounting-document edit buttons out of Phase 1.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/User_Access_Model_Roadmap.md`

Constraints extracted:
- callbacks must emit canonical decision tokens only;
- callbacks must validate authorization and active FSM state before side effects;
- text/voice fallback must keep using `bot/services/decision_resolver.py`;
- LLM/STT/LMM must not run from button callbacks;
- unknown users must not create business data, temp files, storage paths, invoices, contacts, or documents.

Touched scopes:
- confirmation: yes;
- routing/callback routing: yes;
- FSM: yes;
- access: yes;
- LLM/STT/LMM prompts: no;
- DB schema/storage model/server: no.

Verification:
- `python -m pytest -q tests\test_decision_callbacks.py tests\test_access_request_flow.py tests\test_contact_intake_semantic_flow.py tests\test_onboarding_decisions.py tests\test_invoice_state_decisions.py -q` -> passed.
- `python -m pytest -q` -> `864 passed`.

## 2026-05-04 - Session 056 - Preview-approved contact alias learning

Summary:
- Changed supplier-scoped contact lookup so high-confidence customer-name variants such as missing-letter STT transcriptions can resolve to one safe local contact without a separate `áno / nie` alias prompt.
- Kept country-token guardrails: explicit `CZ` does not silently match `SK`, and multiple plausible country variants remain ambiguous.
- Added preview-approved alias learning: when fuzzy or bounded LLM customer resolution is used in the invoice preview, the cleaned customer candidate is stored as a confirmed alias only after the user approves the invoice preview.
- Kept raw full STT/request text out of alias storage and left unrelated low-similarity contacts from forcing clarification.

Contracts read:
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

Verification:
- `python -m compileall bot\services bot\handlers` -> passed.
- `python -m pytest -q tests\test_contact_lookup_normalization.py tests\test_invoice_phase2_ai_layer.py tests\test_invoice_state_decisions.py` -> `142 passed`.
- `python -m pytest -q` -> `858 passed`.

## 2026-05-04 - Session 055 - Alias confirmation STT retry guard

Summary:
- Treated ambiguous STT yes/no noise such as `Ah non !` narrowly as `unknown` in `invoice_customer_alias_confirm`, before LLM fallback can misread it as a real `no`.
- Kept real `nie` / `no` behavior unchanged for the alias confirmation flow.
- Changed alias confirmation `unknown` handling to keep the same FSM state: first unclear reply asks the user to try again with `áno / nie` or `yes / no`; repeated unclear reply asks for a text answer.
- Added structured `invoice_customer_alias_confirm_resolved` logging with decision and retry count.

Contracts read:
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`

Verification:
- `python -m compileall bot\services bot\handlers` -> passed.
- `python -m pytest -q tests\test_decision_resolver.py tests\test_invoice_phase2_ai_layer.py` -> `428 passed`.

## 2026-05-04 - Session 054 - Staged user onboarding profile commands

Summary:
- Updated admin approval notification so the approved user is told access was approved, their FakturaBot working database is ready, and the next action is `/start`.
- Changed `/start` into a staged setup/status router: `/moj_profil` for approved users without profile, `/sluzbu` after profile, `/contact` after service aliases, and an advanced menu after profile + service aliases + contacts.
- Added `/moj_profil` as the user-facing supplier profile surface: it starts profile creation when missing and shows a read-only profile summary when present.
- Added `/upravit_profil` for targeted one-field supplier profile edits with Python validation and shared `yes_no` DecisionResolver confirmation context `supplier_profile_edit_confirm`.
- Changed post-profile onboarding guidance to point only to `/sluzbu` as the next staged step, instead of showing service/contact/invoice commands together.
- Added `/sluzbu` as the primary user-facing service-alias command while preserving `/service` and `/alias`.
- Added `/blocek` as the user-facing recent receipts/accounting-documents view, while preserving legacy `/blocky`.
- Added `/add_blocek` and `/dodat_blocek` as user-facing commands for adding a new receipt/blocek through the existing accounting Document Intake flow; `/doklad` remains legacy/reserved and is not promoted in `/start`.
- Updated missing-profile guidance from `/supplier` to `/moj_profil` in invoice/contact/document-intake paths.
- Documented `delete_user_database` as the reserved destructive top-level action for a follow-up hard-delete implementation; no hard-delete runtime was implemented in this session.

Contracts read:
- `docs/TZ_FakturaBot.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`

Verification:
- `python -m pytest -q tests\test_access_request_flow.py tests\test_onboarding_decisions.py tests\test_service_alias_flow.py tests\test_decision_resolver.py tests\test_accounting_documents_handler.py tests\test_accounting_document_intake_flow.py` -> `425 passed`.
- `python -m pytest -q` -> `852 passed`.

## 2026-05-03 - Session 053 - Confirmed customer alias learning

Summary:
- Added a reusable confirmed semantic alias contract for bounded, user-confirmed alias learning.
- Added a supplier-scoped `confirmed_semantic_alias` table for aliases learned only after explicit confirmation.
- Integrated confirmed customer aliases into the existing `ContactService.resolve_contact_lookup(...)` path instead of adding a separate invoice lookup.
- Added invoice customer alias confirmation: when one safe close customer candidate is found, the bot asks a shared `yes_no` DecisionResolver question and saves only the cleaned extracted customer candidate after `yes`.
- Kept raw STT transcripts out of alias storage and preserved country-token safety: explicit `CZ` does not silently match stored `SK`.
- Added a service-layer supplier-scope guard so aliases cannot be created for another supplier's contact id.
- Added voice routing for the new alias-confirmation FSM state.

Contracts read:
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Verification:
- `python -m compileall bot\services bot\handlers` -> passed.
- `python -m pytest -q tests\test_contact_lookup_normalization.py tests\test_invoice_phase2_ai_layer.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` -> `448 passed`.
- `python -m pytest -q` -> `826 passed`.

## 2026-05-03 - Session 052 - Voice delete intent and STT confirmation noise

Summary:
- Hardened top-level invoice intent routing so explicit delete phrases such as `udalit fakturu 10`, `vidaly fakturu 11`, `vymaz fakturu 7`, or noisy STT variants are routed to `delete_existing_invoice` before generic invoice creation.
- Kept deletion outside `create_invoice`; delete remains a separate bounded top-level action and still requires explicit `yes_no` confirmation before any destructive DB/PDF action.
- Added a narrow confirmation fallback for the observed STT pattern `Ah, nao` / `Ah, nao!` as Slovak `ano`, without adding broad Portuguese-language support.
- Added `top_level_intent_resolved` logs so server diagnostics show the canonical top-level intent selected for voice/text inputs.

Verification:
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_decision_resolver.py tests\test_invoice_state_decisions.py tests\test_contact_intake_semantic_flow.py tests\test_accounting_document_intake_flow.py tests\test_officeflow_attachment_router.py` -> `561 passed`.
- `python -m pytest -q` -> `804 passed`.

## 2026-05-03 - Session 051 - Contact address validation and optional customer email

Summary:
- Made customer/contact email optional in manual and document/semantic contact intake.
- Kept DB schema unchanged by storing an omitted contact email as an empty string.
- Added contact address validation requiring a house/building number, so incomplete addresses such as city-only or street-only values do not pass confirmation.
- Updated contact intake missing-field behavior so missing email no longer blocks contact save, while incomplete address still requires clarification.
- Updated invoice PDF customer block rendering so the customer `Email:` line is omitted when contact email is empty.

Verification:
- `python -m pytest -q tests\test_contact_intake_semantic_flow.py tests\test_pdf_generator_layout_wrapping.py` -> `28 passed`.
- `python -m pytest -q` -> `801 passed`.

## 2026-05-03 - Session 050 - Supplier onboarding saved next-step guidance

Summary:
- Updated the successful `/supplier` completion message so the user is told what to do after the supplier profile is saved.
- The message now starts with `/alias`, then points the user to `/contact`, then `/invoice` or text/voice invoice creation.
- Added `/alias` as a command alias for the existing service-alias flow; `/service` remains supported.
- Updated `/start` for users with an existing supplier profile to show the same operational next steps.
- Clarified that `/alias` means short service name -> full invoice/PDF service title, for example `opravy` -> `Opravy vyhradených zariadení elektrických`.
- User-facing guidance now says these flows can be started by Slovak voice/text examples such as `dodaj novú službu` and `dodaj nový kontakt`.
- Kept the supplier save confirmation on the existing shared DecisionResolver path; no DB schema, access model, LLM, STT, LMM, storage, or invoice numbering changes.

Verification:
- `python -m pytest -q tests\test_onboarding_decisions.py tests\test_access_request_flow.py tests\test_service_alias_flow.py` -> `16 passed`.
- `python -m pytest -q` -> `796 passed`.

## 2026-05-03 - Session 049 - Supplier onboarding first invoice number and SMTP schema repair

Summary:
- Fixed the new-user supplier save failure seen on the server by migrating legacy `supplier.smtp_host`, `supplier.smtp_user`, and `supplier.smtp_pass` `NOT NULL` columns to nullable columns during `init_db()`.
- Added a tenant-scoped `invoice_number_settings` table for the first invoice number FakturaBot should generate per supplier/year.
- Extended `/supplier` onboarding: after email, the bot now asks for the first invoice number for the current year, then asks the default due-days question as the last step.
- Invoice numbering now starts from the configured first number for a supplier/year and then continues from the larger of existing bot invoices or that configured first number.
- No historical invoice import or automatic fake invoice creation was added.

Verification:
- `python -m pytest -q tests\test_onboarding_no_smtp.py tests\test_onboarding_decisions.py tests\test_tenant_safety.py tests\test_supplier_smtp_optional.py` -> `15 passed`.
- `python -m pytest -q` -> `794 passed`.

## 2026-05-03 - Session 048 - Access approval onboarding next step

Summary:
- Updated `/approve <telegram_id>` so the approved user receives a direct bot message after approval.
- Reused the same next-step text for `/approve` notification and `/start` when an approved user has no supplier profile yet.
- The approved-user message tells the user that access is approved and that `/supplier` is the next command when they are ready to enter supplier registration data.
- Kept supplier onboarding explicit: approval does not create a supplier profile, tenant business data, invoices, documents, temp files, or AI/STT/LMM calls.
- Added masked access approval notification logs for server diagnostics.

Verification:
- `python -m pytest -q tests\test_access_request_flow.py` -> `11 passed`.
- `python -m pytest -q` -> `791 passed`.

## 2026-05-02 - Session 047 - Admin command text aliases

Summary:
- Added deterministic text aliases for admin access commands:
  - `користувачі` for `/users`;
  - `запит` and `запрос` for `/access_requests`.
- Kept aliases admin-only by recognizing them in the authorization middleware as admin command equivalents before handler routing.
- Added tests for direct alias handlers and middleware pass-through for bootstrap admins.

Verification:
- `python -m pytest -q tests\test_access_request_flow.py` -> `9 passed`.

## 2026-05-02 - Session 046 - Controlled access-request onboarding

Audit summary:
- User-facing entry points remain centrally protected by Telegram authorization middleware before `/start`, `/supplier`, invoice, contact, accounting-document intake, OfficeFlow attachment routing, voice/STT, text pre-routing, and other mutating handlers can run.
- The previous static `ALLOWED_TELEGRAM_USER_IDS` model was safe for the two-user dry run but operationally inconvenient for additional access requests.
- Unknown users must not create supplier profiles, contacts, invoices, accounting documents, temp storage workspaces, or trigger LLM/STT/LMM calls.
- Admin access management must remain deterministic Python logic and must not be routed through LLM/STT/LMM.

Summary:
- Added `ADMIN_TELEGRAM_USER_IDS` config parsing while preserving `ALLOWED_TELEGRAM_USER_IDS` as bootstrap/static access.
- Added persistent `access_requests` and `authorized_users` tables through `init_db()` with fail-loud compatibility checks and no destructive migration.
- Added `AccessControlService` for pending requests, approvals, rejections, blocking, active-user checks, and admin checks.
- Updated authorization middleware so unknown `/start` creates or refreshes only a minimal pending access request, sends a neutral Slovak access message, and optionally notifies configured admins.
- Added admin-only `/access_requests`, `/approve <telegram_id>`, `/reject <telegram_id>`, `/block <telegram_id>`, and `/users` commands.
- Preserved local/test behavior when both `ALLOWED_TELEGRAM_USER_IDS` and `ADMIN_TELEGRAM_USER_IDS` are empty.
- Updated docs to describe controlled access requests, admin approval, bootstrap allowlists/admins, one-bot model, and the no-public-signup boundary.

Verification:
- `python -m pytest -q tests\test_access_request_flow.py tests\test_tenant_safety.py` -> `13 passed`.
- `python -m pytest -q` -> `787 passed`.

Notes:
- This is not public self-service signup and does not add billing, payments, SaaS dashboard, multiple bot tokens, Postmark, email/password accounts, or full tenant provisioning.
- Blocked users keep existing data but cannot pass the authorization guard.

## 2026-05-02 - Session 045 - User access rollout phases documented

Summary:
- Added `docs/User_Access_Model_Roadmap.md` to separate Phase 1 static allowlist dry run, Phase 2 admin-approved access request automation, and Phase 3 future commercial deployment.
- Updated the server rollout roadmap to state that the current second-user dry run uses one shared Telegram bot token, one backend, one SQLite DB, and `ALLOWED_TELEGRAM_USER_IDS`.
- Reframed the TZ deployment section so the current shared-bot controlled dry run is distinct from the future commercial/per-client installation model.
- Added a local-only safe `docs/local-only/New_User_Onboarding_Checklist.md` checklist with no real Telegram IDs, tokens, names, or private client data.
- Preserved the future per-client bot/VPS/container/DB/storage/API-key model as out of scope for the current dry run and Phase 2 access-request work.
- Strengthened the documentation-only wording so Phase 2 is treated as planned/not implemented unless current code, tests, and `PROJECT_LOG.md` separately confirm implementation.

Verification:
- Documentation-only change; tests not run.

## 2026-05-02 - Session 044 - Minimal tenant-safety hardening for controlled two-user dry run

Audit summary:
- User-facing Telegram entry points include `/start`, `/supplier`/onboarding, invoice creation and edit/delete/view flows, contact flows, accounting document intake, OfficeFlow idle attachment routing, voice routing, and generic text/document pre-routing.
- Supplier profile access was already keyed by `telegram_id`; contact list/name flows were supplier-scoped, while invoice PDF rebuild/display paths still used unscoped contact lookup and were changed to scoped lookup.
- Invoice number generation and DB uniqueness were global; this was changed to tenant-aware `UNIQUE(supplier_telegram_id, invoice_number)` with per-supplier generation and availability checks.
- Existing invoice edit/delete/view resolution already used supplier-scoped number reference matching in the main pre-router; persisted edit subflows were hardened to reload invoices by current `supplier_telegram_id` before mutations.
- Invoice PDF storage was flat by `invoice_number`; it is now tenant-scoped under `storage/invoices/{supplier_telegram_id}/{invoice_number}.pdf`.
- Accounting document confirmed storage, duplicate detection, recent-document views, and temp staging previously used a fixed workspace/default temp path; runtime paths now pass the current Telegram user and use tenant workspaces such as `telegram-{supplier_telegram_id}`.
- Legacy supplier SMTP fields (`smtp_host`, `smtp_user`, `smtp_pass`) existed and onboarding collected them historically; onboarding now collects only business email and saves SMTP fields as `None`.
- LLM/STT/LMM cost boundary is now protected by centralized Telegram user authorization middleware before handlers run.

Summary:
- Added `ALLOWED_TELEGRAM_USER_IDS` config parsing and centralized Telegram user authorization middleware with neutral unauthorized response.
- Registered authorization middleware in `bot/main.py` so unauthorized users are blocked before onboarding, contacts, invoices, accounting intake, OfficeFlow attachment routing, voice/STT, LLM, and LMM handler work.
- Changed invoice schema/bootstrap to migrate from global invoice-number uniqueness to tenant-aware uniqueness, retaining existing rows and documenting the need for DB backup before rollout.
- Updated invoice number generation, availability checks, invoice lookup-by-number, invoice PDF paths, contact lookups during invoice PDF rebuild, and persisted invoice edit/delete flows to respect the requesting Telegram user.
- Added tenant-scoped accounting document temp storage, confirmed storage metadata, duplicate checks, and recent-document views.
- Deprecated per-user SMTP credential collection in onboarding while keeping DB columns for compatibility.
- Updated docs with the controlled two-user model, allowlist requirement, tenant-scoped storage rules, SMTP purge SQL, and out-of-scope items.

Migration note:
- `init_db()` now rebuilds the `invoice` table when it detects the legacy global `UNIQUE(invoice_number)` shape and recreates it with `UNIQUE(supplier_telegram_id, invoice_number)`.
- Before server rollout, back up the SQLite DB and storage directory. Rollback risk is mainly schema rollback/manual restore if the live DB contains unexpected duplicate rows for the same supplier and invoice number.
- Existing legacy SMTP values should be purged after backup with:

```sql
UPDATE supplier
SET smtp_host = NULL,
    smtp_user = NULL,
    smtp_pass = NULL;
```

Verification:
- `python -m pytest -q tests\test_tenant_safety.py tests\test_accounting_document_storage.py tests\test_accounting_document_duplicates.py tests\test_accounting_document_registry.py tests\test_onboarding_decisions.py tests\test_onboarding_no_smtp.py` -> `37 passed`.
- `python -m pytest -q` -> `780 passed`.

Notes:
- This is not full SaaS multi-tenancy.
- Out of scope remains multiple bot-token orchestration, workspace admin UI, billing, Postmark integration, encrypted tenant secret vault, bank-statement matching, and expense categorization.
- Python remains the execution authority; LLM/STT/LMM does not decide authorization, tenant identity, DB scoping, invoice numbering, file paths, or persistence.

## 2026-05-02 - Session 043 - Canonical DecisionResolver matrix tests

Summary:
- Added central Canonical DecisionResolver test registries for yes/no and approve/edit/cancel confirmation contexts.
- Added exact multilingual/noisy/STT-like contract matrices covering existing FakturaBot and OfficeFlow confirmation contexts.
- Added a static handler guard against local confirmation token parsers in `bot/handlers/*.py`.
- Updated the shared resolver fallback to cover newly contracted Slovak/Cyrillic-compatible variants such as `potvrď`, `zmeniť`, and `zahodiť`.
- Updated `docs/Canonical_Decision_Resolver_Contract.md` to require new confirmation-like flows to register their `context_name` in the central test matrix.

Verification:
- `python -m pytest -q tests\test_decision_resolver.py` -> `340 passed`.
- `python -m pytest -q` -> `753 passed`.

Notes:
- No DB schema, storage behavior, invoice PDF path behavior, deployment scripts, or server state was changed.
- No handler-local confirmation parser was added.

## 2026-05-02 - Session 042 - Server rollout roadmap audit and priorities

Summary:
- Audited `docs/FakturaBot_Server_Rollout_Roadmap.md` against the current README, project log, repo deployment files, and local-only server context.
- Reworked the roadmap from a target-only plan into a current audit with stage statuses: done/partial/not started/future.
- Added prioritized rollout tasks for owner-run baseline, DB/storage migration discipline, dependency management, tenant contract, manual onboarding, multi-bot routing, and first external dry run.
- Clarified that the project currently has no full DB migration system; current behavior is bootstrap/fail-loud with one compatible `ALTER TABLE` path, and the next schema/storage change needs an explicit migration plan.
- Clarified that moving from `requirements.txt` to `uv` is a P1 dependency-management decision, not a blocker for owner-run or first dry run and not the same risk category as DB migration.

Verification:
- Documentation-only change; tests not run.

Notes:
- No runtime code, DB schema, storage behavior, deployment script, server state, or dependency file was changed.
- Real server actions still require checking `docs/local-only/FakturaBot_Server_Agent_Context.md` first.

## 2026-05-02 - Session 041 - Docs archive correction and README refresh

Summary:
- Audited markdown documents at repo root, `docs/`, `docs/llm/`, `docs/local-only/`, and `docs/archive/` for current role/status.
- Rewrote `README.md` as a current navigation/status document instead of the outdated Phase 4 snapshot.
- Added `docs/archive/README.md` to mark archived documents as historical context, not current sources of truth.
- Moved the old root `FakturaBot_Implementation_Phases_Spec.md` into `docs/archive/`.
- Moved `docs/PayBySquare_Research_Spike.md` and `docs/PayBySquare_Manual_Verification_Checklist.md` into `docs/archive/`.
- Kept active README references to archived Pay by Square rationale/manual QR scan verification materials.

Verification:
- Documentation/file organization only; tests not run.

Notes:
- Current source-of-truth order remains `docs/TZ_FakturaBot.md`, `PROJECT_LOG.md`, current code, then `CHANGELOG.md`.
- No runtime code, DB schema, storage behavior, invoice flow, or Pay by Square implementation was changed.
- README now explicitly says real SMTP/email sending, standalone `save_contract`, full OfficeFlow workspace runtime, Google Drive sync, bank matching, full OCR, and multi-tenant SaaS runtime are not implemented.

## 2026-05-01 - Session 070 - Local Codex Windows sandbox ACL fix documented

Summary:
- Documented the resolved local Windows Codex elevated sandbox setup failure that occurred before shell command execution with `windows sandbox: setup refresh failed with status exit code: 1`.
- Root cause was unsafe Windows ACL/world-writable paths on the local machine, not project code.
- Removed `C:\Users\Public\KROS`.
- Fixed the `D:\` root ACL by removing `Everyone:(OI)(CI)(F)` inheritance and keeping normal access for the current user, Administrators, SYSTEM, and Users read/execute.
- Cleaned unsafe ACLs on `C:\$360Section`.
- Reset old Codex sandbox state: `.codex\.sandbox`, `cap_sid`, and `sandbox.log`.
- The known local Windows ACL-related sandbox setup failure was resolved and verified.

Verification:
- `Get-Location` -> `D:\AI_Model\Ai_assistant`
- `python --version` -> `Python 3.12.0`
- `python -m pytest -q` -> `373 passed in 13.20s`

Conclusion:
- Sandbox/tooling issue resolved; project tests are green.
- For this repository, the confirmed test command is `python -m pytest -q` from `D:\AI_Model\Ai_assistant`.
- Avoid bare `pytest -q` because it may not include the project root on `sys.path` and can fail during collection with `ModuleNotFoundError: No module named 'bot'`.

## 2026-05-01 — Session 069 — Document Intake real Telegram file payload wiring

Summary:
- Hardened `/doklad` accounting intake so real Telegram photo/PDF downloads are passed into `accounting_document_lmm.py` as file bytes.
- Updated the LMM wrapper to send images as Chat Completions `image_url` data URLs and PDFs as `file` payloads with base64 `file_data`, while keeping strict JSON parser boundaries.
- Added size/mime guards before provider calls and kept provider behavior fully mockable in tests.
- Added user-facing handling for unknown classification, parser/provider errors, and poor readability/blurred documents.
- Added temp staging cleanup after unknown/poor/error paths, cancel, and confirmed save copy.
- No DB schema changes, invoice flow changes, bank matching, Google Drive sync, Zevs runtime profile, `storage/invoices` changes, or `pdf_path` behavior changes were made.

Tests:
- Focused accounting document suite: `52 passed`.
- Full suite: `373 passed`.

## 2026-05-01 — Session 068 — Document Intake Phase 1 Slice 4 explicit Telegram intake

Summary:
- Added an explicit accounting document intake FSM entered only by `/doklad`, `/expense`, or `/intake`.
- Added state-scoped photo/PDF upload handling for receipts and incoming invoices, with temp staging under `storage/uploads/accounting_intake/`.
- Wired Slice 4 to the existing accounting document LMM wrapper, Python validation, Slovak preview, shared `resolve_approve_edit_cancel(...)`, and confirmed JSON-sidecar storage.
- Registered the router without broad idle attachment interception; uploads outside the active intake state are not processed by this router.
- Kept edit as a bounded not-yet-implemented response for this slice.
- No bank matching, DB schema changes, Google Drive sync, Zevs runtime profile, supplier profile changes, invoice flow changes, `storage/invoices` changes, or `pdf_path` behavior changes were made.

Tests:
- Focused Document Intake Slice 1-4 suite: `44 passed`.
- Full suite: `365 passed`.

## 2026-05-01 — Session 067 — Document Intake Phase 1 Slice 3 LMM boundary

Summary:
- Added `bot/services/accounting_document_lmm.py` as an isolated, mockable LMM wrapper for accounting document classification and extraction.
- Added classification and extraction prompt files with strict JSON-only output contracts.
- The wrapper immediately parses provider output through the strict classifier/extraction parsers and returns candidate-only data.
- Added tests with fake provider clients for valid responses, non-JSON responses, forbidden side-effect fields, prompt content, provider isolation, and no file/DB writes.
- No Telegram handlers, preview/confirm flow, real Vision wiring, bank matching, DB schema changes, invoice flow changes, `storage/invoices` changes, `pdf_path` changes, or current contract `document_intake.py` behavior changes were made.

Risks / follow-up:
- Next slice should add preview/FSM handler integration behind explicit command/state routing, not broad idle attachment interception.
- Real photo/PDF Vision payload wiring should stay inside the LMM boundary and continue to feed strict parsers only.

## 2026-05-01 — Session 066 — Document Intake Phase 1 Slice 2 parsers

Summary:
- Added pure classifier parser for strict `receipt` / `incoming_invoice` / `unknown` classification JSON.
- Added pure extraction parser that converts approved candidate JSON into `AccountingDocumentCandidate`.
- Added parser guards against non-JSON, unsupported enums, unexpected top-level fields, and side-effect top-level fields such as `saved_path`, `status`, `confirmed`, and `final_category`.
- Added focused parser tests and compatibility coverage showing extraction output passes existing validation.
- No Telegram handlers, OpenAI/LMM/Vision calls, DB schema changes, file writes, invoice flow changes, `storage/invoices` changes, `pdf_path` changes, or current contract `document_intake.py` behavior changes were made.

Risks / follow-up:
- Next slice should add LMM call wrappers behind these parsers without letting model output create paths, IDs, save status, or final categories.
- Handler integration must remain explicit-command/state first to avoid intercepting existing contact contract uploads.

## 2026-05-01 — Session 065 — Document Intake Phase 1 Slice 1 foundation

Summary:
- Added pure accounting document data models for future receipt/incoming-invoice intake candidates.
- Added Python validation for required fields, positive Decimal amounts, ISO dates, currency handling, document type gating, and non-blocking IBAN/variable-symbol warnings.
- Added storage helpers for temp staging under `storage/uploads/accounting_intake/` and confirmed JSON-sidecar saves under the proposed OfficeFlow yearly/monthly expense tree.
- Added focused tests for validation failures, deterministic filenames, year/month path derivation, confirmed metadata sidecars, temp staging, and the guard against writing to `storage/invoices`.
- No Telegram handlers, LMM/OpenAI calls, DB schema changes, invoice flow changes, supplier profile changes, `storage/invoices` changes, or `pdf_path` changes were made.

Risks / follow-up:
- Next slice should add strict classifier/extraction parser tests before any LMM call.
- Handler integration must remain explicit-state or explicit-command first to avoid stealing existing contact contract uploads.

## 2026-05-01 — Session 064 — Canonical DecisionResolver runtime Phase 1

Summary:
- Added `bot/services/decision_resolver.py` as the shared Canonical DecisionResolver adapter for `approve_edit_cancel` and `yes_no` decision families.
- Migrated invoice preview, post-PDF invoice decision, contact semantic/manual confirmation, supplier onboarding confirmation, and existing-invoice delete confirmation to the shared resolver path.
- Fixed voice routing so confirm-state transcripts route to the active confirmation handler instead of falling through to top-level invoice routing.
- Added regression tests for canonical decisions, manual contact/onboarding confirmation aliases, delete confirmation context, and voice confirm routing.
- No OfficeFlow Document Intake runtime, DB schema, storage paths, supplier profile, invoice PDF path behavior, or `pdf_path` behavior changed.

Risks / follow-up:
- Telegram button/callback decisions are still future work.
- Future Document Intake must reuse the shared resolver and add its own preview/confirm tests before runtime implementation.

## 2026-05-01 — Session 063 — Canonical DecisionResolver docs policy

Summary:
- Added `docs/Canonical_Decision_Resolver_Contract.md` as the project-level policy for confirmation-like replies.
- Defined the required migration target: one shared Canonical DecisionResolver for `approve_edit_cancel` and `yes_no` decision families.
- Documented that LMM/semantic resolver returns only canonical decision tokens while the active FSM flow executes business actions.
- Marked existing local confirmation parsers as technical debt to migrate after tests.
- No runtime code, DB schema, storage paths, or Document Intake runtime were changed.

Risks / follow-up:
- Add tests around existing confirmation behavior before migrating local parsers.
- Migrate invoice/contact/onboarding/delete confirmation paths one at a time after tests.

## 2026-05-01 — Session 062 — Document Intake Phase 1 MVP implementation plan

Summary:
- Added `docs/Document_Intake_MVP_Implementation_Plan.md` as a docs-only Phase 1 plan for future receipt/incoming-invoice intake.
- Defined accepted inputs, classification, LMM JSON contract, Python validation, file naming, yearly/monthly storage target, Telegram preview/confirm flow, DB/storage options, and required tests.
- Explicitly kept bank matching, Google Drive sync, Zevs runtime profile, and multi-workspace runtime out of scope.
- No runtime code, DB schema, existing invoice storage, `pdf_path`, or supplier profile behavior was changed.

## 2026-05-01 — Session 061 — Docs-first OfficeFlow architecture foundation

Summary:
- Created docs-first OfficeFlow framing with FakturaBot defined as the current outgoing invoices module.
- Added a non-runtime OfficeFlow storage model proposal separating persistent master data from yearly accounting documents.
- Added a future Document Intake module proposal for receipts, incoming invoices, contracts, and bank statements.
- Minimally updated README, FakturaBot TZ, and LLM orchestrator contract with OfficeFlow cross-links and explicit non-runtime boundaries.
- No runtime code, DB schema, `pdf_path`, supplier SZČO profile, invoice flow, or existing storage files were changed.

Risks / follow-up:
- Future storage migration requires backup, DB/file compatibility plan, and invoice PDF path regression tests.
- Future Document Intake actions must be added docs-first to the action registry before runtime implementation.

## 2026-04-30 — Session 060 — Explicit hard-delete flow for persisted invoices

Summary:
- Added explicit top-level action `delete_existing_invoice` for persisted invoice deletion by short/full number reference.
- Added mandatory confirmation gate (`áno / nie`) before destructive delete.
- Implemented hard delete of invoice items + invoice row, plus best-effort PDF file deletion.
- Added ownership/invoice existence re-check right before destructive delete to fail loud safely.
- No soft delete, no storno logic, no DB schema migration.

Tests:
- `PYTHONPATH=. pytest -q tests/test_invoice_intent_prerouter.py`
- `PYTHONPATH=. pytest -q tests/test_invoice_state_decisions.py`
- `PYTHONPATH=. pytest -q`

## 2026-04-30 — Session 059 — Deterministic post-PDF save/edit/cancel decision guard

Summary:
- Hardened bounded decision normalization for preview/post-PDF invoice states with local Python marker detection before LLM fallback.
- Clear save markers such as `зберегти`, `сохрани`, `uložiť`, and `save changes` now map to `schvalit` deterministically.
- Removed reliance on ambiguous nouns like `зміни` / `изменения` as edit intent when an explicit save marker is present.
- Conflicting local markers now return `unknown` so the bot asks for clarification instead of guessing.
- Updated TZ with the decision-marker contract and added regression tests for the logged STT phrase.

Tests:
- `PYTHONPATH=. pytest -q tests/test_invoice_intent_prerouter.py` — 82 passed.
- `PYTHONPATH=. pytest -q` — 280 passed.

## 2026-04-30 — Session 058 — Item-level numeric edits inside `upraviť položku`

Summary:
- Extended bounded item action menu with numeric operations: `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`.
- Added stage-aware numeric value handler for both draft and persisted edit backends under existing `upraviť položku` flow.
- Added strict numeric parser for bounded value input (`1500`, `1500,50`, `1500.50`, `2`, `2,5`) with fail-loud fallback prompt.
- Added deterministic arithmetic semantics:
  - quantity edit recalculates total using existing unit price;
  - unit-price edit recalculates total using existing quantity;
  - total edit recalculates unit price with guard `quantity > 0`.
- Added persisted backend updates for invoice item financial fields + invoice total recomputation before PDF rebuild.
- Updated LLM/action-contract docs and in-action registry status for item-level numeric operations.

## 2026-04-30 — Session 057 — Existing invoice summary preview before persisted edit-flow

Summary:
- Follow-up hardening for explicit `edit_existing_invoice`: when exactly one persisted invoice is resolved, bot now sends a current Slovak invoice summary before entering edit menu.
- Summary includes invoice number, customer, dates, item lines (description/detail), quantity, unit price, item total, and invoice total.
- If persisted `pdf_path` exists and file is available, bot sends current PDF as optional document preview; missing file/path does not fail flow.
- After summary/PDF preview, runtime continues into existing `start_invoice_edit_flow(...)` backend without creating a new draft and without post-PDF menu restoration.

## 2026-04-30 — Session 056 — Explicit existing-invoice edit entrypoint by number reference

Summary:
- Added explicit top-level action `edit_existing_invoice` for persisted invoice editing by command like `upraviť faktúru 15`.
- Kept preview-stage draft `upraviť` flow unchanged; no restoration of post-PDF menu after each generation.
- Implemented supplier-scoped invoice reference resolution in Python/DB layer (LLM does not query DB): short numeric suffix and full number both supported, with deterministic ambiguity handling.

Runtime changes:
- `process_invoice_text(...)` now accepts and handles `edit_existing_invoice` as explicit entrypoint.
- Added extraction of numeric invoice reference from user text and supplier-scoped lookup:
  - 0 matches => `Faktúru s týmto číslom som nenašiel.`
  - >1 matches => `Našiel som viac faktúr. Napíšte celé číslo faktúry.`
  - 1 match => set `last_invoice_id`/`edit_invoice_id` and start persisted `start_invoice_edit_flow(...)`.
- Added `InvoiceService.find_invoices_for_supplier_by_number_reference(...)`.

Tests:
- Added intent routing assertion for `edit_existing_invoice`.
- Added persisted lookup happy-path test for short reference `15` -> invoice `20260015`.
- Added ambiguity and supplier-scope guard test.

## 2026-04-30 — Session 055 — Normalize electrical repair service display title

### Goal
Fix FakturaBot invoice text generation so the supplier service alias/canonical layer uses the correct Slovak display title for electrical reserved technical device repairs.

### Changes
- updated `ServiceAliasService` to normalize the known service display title to `Opravy vyhradených technických zariadení elektrických`;
- applied the normalization on `create_mapping(...)`, `list_mappings(...)`, and `resolve_service_display_name(...)` so both new saves and existing lower-case/no-diacritic records render through the corrected title;
- added focused regression coverage for storing and resolving the corrected Slovak variant.

### Decision
- No schema migration or new service-alias flow was added.
- Existing supplier alias mappings remain the source of truth; this is a narrow canonical-title normalization for one confirmed Slovak service phrase.

## 2026-04-26 — Session 054 — Preview-stage draft edit-flow implementation

### Goal
Move the invoice edit happy path from post-PDF approval to preview / `Náhľad faktúry`, while keeping post-PDF edit as compatibility/fallback and showing a proposed invoice number before final generation.

### Changes
- changed preview confirmation semantics from `ano` / `nie` to draft-review decision `schvalit` / `upravit` / `zrusit`, with `ano` and `nie` kept as aliases;
- added proposed invoice number to FSM `invoice_draft` and preview copy as `Číslo faktúry: <number> (návrh)`;
- changed final preview approval to create the invoice row, use the proposed/final number, generate PDF, set ready status, send PDF, and clear FSM;
- added draft edit backend for invoice number/date edits and item service/description/detail edits, mutating FSM draft only and returning updated preview;
- preserved post-PDF `waiting_pdf_decision` and persisted invoice edit backend as compatibility/fallback;
- updated LLM bounded confirmation contract and in-action registry for preview draft decisions;
- extended tests for preview decision aliases, proposed number behavior, draft edits, duplicate proposed number rejection, and post-PDF compatibility.

### Decision
- No DB schema migration was made.
- Invoice number remains non-null on persisted invoices.
- Proposed number is not reserved before final approval.
- Billing/quota logic remains out of scope.

### Manual verification checklist

Happy path:
- create invoice and verify preview shows `Číslo faktúry: <number> (návrh)`;
- reply `schváliť` or `ano`;
- verify invoice row is created with final number, PDF is generated, status is `pripravena`, bot does not ask post-PDF `schváliť/upraviť/zrušiť` again, and FSM is cleared.

Draft edit before finalization:
- create invoice and choose `upraviť` on preview;
- edit `Dátum dodania`;
- verify bot shows updated text preview, no PDF rebuild happens during draft edit, no final invoice row exists before `schváliť`, and review returns to `schváliť/upraviť/zrušiť`.

Proposed number conflict:
- set draft proposed invoice number to an already existing number;
- reply `schváliť`;
- verify finalization is rejected, no invoice/PDF is created, draft remains available, and bot asks for another invoice number.

## 2026-04-26 — Session 053 — Draft review edit-flow lifecycle design audit

### Goal
Audit current FakturaBot invoice lifecycle and design the migration path for moving `upraviť faktúru` from the post-PDF approval step to the draft review / `náhľad faktúry` step before final invoice/PDF generation.

### Changes
- added docs-only architecture document `docs/Invoice_Draft_Review_Lifecycle_Design.md` with:
  - current runtime lifecycle and confirmation semantics;
  - audit answers for FSM draft vs DB invoice row, invoice number timing, PDF timing, `last_invoice_id`, and edit-flow dependencies;
  - target draft lifecycle and state machine proposal;
  - data model impact for draft status, numbering, PDF storage, and abandoned drafts;
  - LLM contract impact for preview decision canonical outputs `schvalit` / `upravit` / `zrusit`;
  - phased migration plan and risks.

### Decision
- No runtime code, tests, DB schema, numbering logic, PDF generation logic, billing logic, or post-PDF edit behavior changed in this session.
- Current audit conclusion: pre-confirmation preview is FSM-only `invoice_draft`; current edit-flow requires persisted `invoice_id` and is coupled to PDF rebuild side effects, so draft review editing should be implemented through a stage-aware edit orchestrator rather than a narrow `waiting_confirm` patch.

## 2026-04-24 — Session 052 — Clarify implicit first item before explicit `polozka 2`

### Goal
Make the invoice draft prompt explicit that the first item may already start before the user says `polozka 2` / `pozicia 2`.

### Changes
- updated `prompts/invoice_draft_prompt.txt` so the split-semantics section now states:
  - if the user starts describing the first service without saying `polozka 1`,
  - and later says `polozka 2` / `pozicia 2` / `item number 2`,
  - the preceding service fragment should be treated as candidate item 1 and the marker opens candidate item 2.

### Decision
Numbered markers in voice input are not required to start from `1`; the model should infer an implicit first item when earlier service content is already present.

## 2026-04-24 — Session 051 — Align invoice draft prompt with multilingual Slovak-normalized LLM contract

### Goal
Make the invoice draft LLM layer explicitly responsible for normalizing mixed SK/UA/RU/noisy STT input into Slovak business semantics while preserving the exact Python-facing bounded JSON shape.

### Changes
- updated `docs/FakturaBot_LLM_Orchestrator_Contract.md` to state explicitly that:
  - LLM first normalizes multilingual/noisy invoice meaning into Slovak draft semantics;
  - LLM output must stay aligned to the exact Python intake shape (`vstup`, `zamer`, `biznis_sk`, `stopa`, bounded `items[]`);
  - numbered and ordinal item markers across mixed languages are valid candidate split signals at the LLM contract level;
- updated `prompts/invoice_draft_prompt.txt` so the runtime prompt now explicitly instructs the model to:
  - preserve raw transcript in `vstup.povodny_text`;
  - normalize business meaning into Slovak field-by-field in `biznis_sk`;
  - return only the machine-safe JSON shape expected by Python;
  - treat multilingual numbered/ordinal item markers as explicit bounded item separators.

### Decision
Invoice item segmentation and multilingual normalization should be driven primarily by the LLM contract/prompt, while Python remains a bounded validator and fail-safe layer rather than the main natural-language parser.

## 2026-04-24 — Session 050 — Improve numbered voice item boundary handling

### Goal
Reduce invoice-draft misses in multi-item voice input where the user separates positions with numbered markers such as `polozka 2`, `polozka cislo 3`, `pozicia 2`, or `item number 2`.

### Changes
- expanded invoice item-boundary heuristics in `bot/handlers/invoice.py` to treat numbered markers as explicit multi-item separators;
- covered both Latin/transliterated and Cyrillic/diacritic variants of `polozka/položka/pozicia/позиция/положка/item`;
- updated `prompts/invoice_draft_prompt.txt` with explicit examples for numbered multi-item speech up to three positions;
- added regression coverage in `tests/test_invoice_phase2_ai_layer.py` for `item 2` and `item 3` style voice boundaries.

### Decision
Numbered item markers are now treated as strong split signals even when the utterance has no commas and no reliable conjunction split, because this is a natural speech pattern in Telegram voice drafting.

## 2026-04-24 — Session 049 — Fix Linux PDF font resolution for server invoice generation

### Goal
Restore invoice PDF generation in the Linux Docker deployment after runtime failure on missing Slovak glyph-capable fonts.

### Changes
- updated `bot/services/pdf_generator.py` to probe Linux font locations in addition to Windows and ReportLab fallback fonts;
- added `fonts-dejavu-core` installation to `Dockerfile` so the container includes a Unicode-capable TTF font at runtime.

### Problem confirmed
- server logs showed PDF generation failure during invoice confirmation:
  - `RuntimeError: No available PDF font with required Slovak glyph support`

### Decision
Keep the existing Unicode font registration flow, but make it Linux-aware and ensure the Docker image ships with at least one known-good system font.

## 2026-04-24 — Session 048 — Add safe server update runbook to local-only agent context

### Goal
Document the exact safe update procedure for refreshing the server-hosted FakturaBot instance after GitHub changes, without exposing secrets in public repo docs.

### Changes
- updated `docs/local-only/FakturaBot_Server_Agent_Context.md` with a focused safe update runbook:
  - SSH entry point;
  - `/bot/repo` working directory;
  - `git fetch` / `checkout main` / `pull --ff-only`;
  - `docker compose -f docker-compose.prod.yml up -d --build`;
  - status/log verification steps;
  - explicit note for `TelegramConflictError` as a competing-runtime issue.

### Decision
Server update instructions belong in the local-only server agent context because they are operational guidance tied to the live host and should not be expanded in public repo docs.

## 2026-04-24 — Session 047 — Public repo prep for local-only operational materials

### Goal
Prepare the repository for a public GitHub state while keeping private operational/server materials available locally for agents and excluded from the public index.

### Changes
- audited the repo for server access details, absolute server paths, deploy/runtime commands, private runbooks, and local ops handoff materials;
- confirmed the main sensitive local operational file is `docs/local-only/FakturaBot_Server_Agent_Context.md`, which remains local-only and ignored;
- expanded `.gitignore` for a dedicated `docs/local-only/` area while keeping safe placeholders trackable;
- added a minimal production-like deployment baseline for Stage 1-2 rollout:
  - `.dockerignore`
  - `docker-compose.prod.yml`
  - `.env.server.example`
  - `scripts/update_repo.sh`
  - `scripts/deploy_owner_run.sh`
- added public-safe placeholders:
  - `docs/local-only/README.md`
  - `docs/local-only/FakturaBot_Server_Agent_Context.example.md`
- sanitized tracked public docs to avoid direct local artifact/path guidance where not needed:
  - `docs/FakturaBot_Server_Rollout_Roadmap.md`
  - `docs/PayBySquare_Manual_Verification_Checklist.md`
  - `PROJECT_LOG.md`

### Exposure assessment
- no tracked file with real SSH host/IP details was found in the current git index;
- `docs/local-only/FakturaBot_Server_Agent_Context.md` contains real server operational details locally, but is already ignored and not tracked in the current repository state;
- no history rewrite was performed.

## 2026-04-21 — Session 046 — Server rollout/onboarding roadmap + README deployment direction alignment

### Goal
Add a practical docs-first deployment/onboarding roadmap from current local+GitHub state to the first external client pressing `/start` on a server-hosted FakturaBot, and align README with the near-term shared-backend tenant-isolation direction.

### Changes
- added `docs/FakturaBot_Server_Rollout_Roadmap.md` with staged operational path:
  - start point and scope truthfulness notes (plan/target, not completed infrastructure claim);
  - explicit near-term architecture decision: shared backend + tenant isolation as primary rollout model;
  - staged roadmap (server foundation -> owner production-like run -> tenant model -> multi-bot routing -> manual onboarding v1 -> first external client dry run -> later improvements);
  - data/secret handling principles and first milestone definition for external `/start` success.
- updated `README.md` surgically to:
  - link the new rollout roadmap document;
  - state the near-term rollout direction (shared backend + tenant isolation, Telegram-first);
  - clarify self-service setup page is later and not required for first deployment milestone.

### Scope boundary
- Docs-only patch.
- No runtime code changes.
- No claim that multi-tenant runtime, setup page, or full production automation is already implemented.

## 2026-04-19 — Session 045 — TZ alignment with planned `info_help` guidance layer

### Goal
Align `docs/TZ_FakturaBot.md` with the newer docs-first `info_help` architecture at high-level product/requirements level, without duplicating the detailed focused spec.

### Changes
- updated `docs/TZ_FakturaBot.md` (section 5) with a surgical high-level `info_help` alignment block:
  - clarified `info_help` as bounded guidance/navigation/recovery layer (not free-form chat, not direct-action duplicate);
  - fixed routing precedence: top-level action first, question form does not block direct actions, `info_help` only on top-level `unknown`;
  - added concise contract-precedence note: `info_help` remains subordinate to existing bounded `docs/llm` rules;
  - added capability status model (`implemented` / `planned` / `unsupported`) and truthfulness requirement;
  - added structured logging requirement for all `info_help` entries as product signals;
  - added Phase 2/3 future-direction note (state-aware guidance, reset/new-task support, bounded runtime explainability);
  - explicitly prohibited arbitrary source-code/raw-log reading by LLM in this layer;
  - preserved caution for unconfirmed flows (contact edit, old-invoice deletion, send-invoice/send-email, support escalation);
  - added explicit reference to detailed spec `docs/Info_Help_Guidance_Layer.md`.

### Scope boundary
- Docs-only alignment patch.
- No runtime code changes.
- No upgrade of unsupported/planned behavior to implemented.

## 2026-04-19 — Session 044 — Refinement: Phase 2/3 runtime explainability for `info_help` spec

### Goal
Extend the docs-first `info_help` specification with forward-looking runtime explainability/debug-aware guidance rules for later phases, while preserving strict bounded `docs/llm` contract precedence.

### Changes
- updated `docs/Info_Help_Guidance_Layer.md` with targeted additions:
  - future-direction note: controlled runtime explainability in Phase 2/3;
  - new subsection for bounded Python-prepared runtime/debug context (`FSM state`, flow, next actions, reset availability, STT failure count, error category, fallback reason, API/quota status, sanitized summary);
  - explicit prohibitions against arbitrary source-code/raw-log reading by LLM and against leaking secrets/internal traces/paths;
  - added worked examples for repeated STT failure and model/API or quota/credits failure;
  - extended logging rationale with runtime-explainability signals;
  - extended Phase 2/3 rollout bullets with debug-aware guidance and optional admin reliability summaries.

### Scope boundary
- Docs-only refinement.
- No runtime code changes.
- No new implementation claims beyond planned behavior.

## 2026-04-19 — Session 043 — Docs-first spec for `info_help` guidance/navigation layer

### Goal
Add a dedicated docs-first architecture/spec for planned `info_help` capability, explicitly subordinate to existing bounded `docs/llm` contract, without runtime implementation changes.

### Changes
- added new spec document: `docs/Info_Help_Guidance_Layer.md`
  - defines purpose/scope/non-goals for controlled guidance/navigation/recovery layer;
  - fixes routing rule: top-level action resolution first, `info_help` only on top-level miss;
  - defines internal `info_help` submodes (`faq_topic`, `state_guidance`, `action_offer_or_handoff`, `restart_or_reset_request`, `support_escalation`);
  - defines capability status model (`implemented`, `planned`, `unsupported`) with truthful response rules;
  - defines bounded knowledge-registry shape and staged LLM interaction contract;
  - defines safety requirements (no hidden mutation, explicit confirmation for handoff/reset);
  - defines mandatory structured logging fields for all info-layer requests;
  - includes worked examples and explicit truthfulness boundaries for unconfirmed flows;
  - includes phased rollout and docs-alignment checklist.

### Scope boundary
- Docs-only change.
- No runtime code changes.
- No behavior claimed as implemented beyond confirmed current runtime.

## 2026-04-19 — Session 042 — Invoice date edit expansion (issue/delivery/due) with voice-first bounded LLM contract

### Goal
Expand `upraviť faktúru` invoice-level date editing from one narrow `edit_invoice_date` path to full three-date support (`vystavenia`, `dodania`, `splatnosti`) and make value capture voice/text parity via bounded LLM normalization contract.

### Changes
- invoice-level action surface (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - added canonical operations:
    - `edit_invoice_issue_date`
    - `edit_invoice_delivery_date`
    - `edit_invoice_due_date`
  - kept `edit_invoice_date` as clarification-only umbrella intent (`upraviť dátum` -> ask which date).
- user prompts/messages (`bot/handlers/invoice.py`):
  - updated invoice-level edit menu to list all three concrete date actions;
  - added clarification prompt:
    - `Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?`
  - added exact value prompts:
    - `Napíšte alebo nadiktujte nový dátum vystavenia... DD.MM.RRRR`
    - `Napíšte alebo nadiktujte nový dátum dodania... DD.MM.RRRR`
    - `Napíšte alebo nadiktujte nový dátum splatnosti... DD.MM.RRRR`
  - success messages split per field:
    - `Dátum vystavenia bol upravený.`
    - `Dátum dodania bol upravený.`
    - `Dátum splatnosti bol upravený.`
- bounded LLM date normalization contract (`bot/services/semantic_action_resolver.py`, `bot/handlers/invoice.py`):
  - added `resolve_invoice_date_normalization(...)` that enforces bounded output:
    - JSON `{ "normalized_date": "DD.MM.RRRR" }` or `{ "normalized_date": "unknown" }`;
  - invoice date value handler now uses this contract for both text and voice/STT input;
  - Python side only performs strict format/date validation and applies persistence/reject logic.
- validation and persistence (`bot/handlers/invoice.py`, `bot/services/invoice_service.py`):
  - added `update_invoice_delivery_date(...)` and `update_invoice_due_date(...)`;
  - enforced invariant reject:
    - `Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.`
  - also prevents issue-date update that would violate `due_date >= issue_date`.
- tests (`tests/test_invoice_state_decisions.py`):
  - updated issue-date success path to new explicit action;
  - added routing clarification test for generic `upraviť dátum`;
  - added success coverage for delivery-date edit;
  - added invariant reject coverage for due-date earlier than issue-date;
  - added voice-style natural-language date input test with mocked bounded normalization result.

### Scope boundary
- Item-level edit flow was not changed.
- No hidden auto-fix behavior added; all invariant conflicts remain fail-loud with explicit user-facing reject.
- No behavior claimed as implemented beyond confirmed current runtime.

## 2026-04-19 — Session 041 — Hardening `nový opis položky` isolation from alias mappings

### Goal
Close pre-merge risk check: ensure `nový opis položky` mutates only invoice item fields and has no side effects on supplier service-alias DB state.

### Changes
- invoice item mutation path isolation (`bot/services/invoice_service.py`, `bot/handlers/invoice.py`):
  - added explicit `update_item_main_description(...)` method in `InvoiceService`;
  - switched `replace_main_description` handler path from `update_item_service(...)` to `update_item_main_description(...)` to make intent/scope explicit (invoice item only).
- regression coverage (`tests/test_invoice_state_decisions.py`):
  - added test `test_novy_opis_updates_only_invoice_item_without_alias_db_side_effects` that verifies:
    - main item description is replaced exactly (no appended tail),
    - item details are untouched,
    - service-alias mappings remain identical before/after action.

### Scope boundary
- Minimal change only for isolation/clarity.
- No changes to `zmeniť službu` runtime branch.
- No confirmation-flow or FSM redesign changes.

## 2026-04-19 — Session 040 — UX wording cleanup for `upraviť faktúru` item-level edit flow

### Goal
Align item-level edit naming/messages with real runtime semantics without changing confirmation architecture or broad FSM design.

### Changes
- user-facing prompt cleanup (`bot/handlers/invoice.py`):
  - removed `kontakt` from top-level `upraviť faktúru` scope prompt (`faktúra` now shows only `číslo/dátum`);
  - replaced item-action menu wording with explicit four actions:
    - `zmeniť službu`
    - `nový opis položky`
    - `pridať detaily k položke`
    - `vymazať detaily položky`
- item edit action routing/messages (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - split bounded item-action semantics into:
    - `replace_service`
    - `replace_main_description`
    - `add_item_details`
    - `clear_item_details`
  - updated input prompts to match action semantics:
    - main description replacement prompt explicitly states replacement;
    - details prompt explicitly asks for details;
    - clear-details action executes immediately and returns clear-details-specific feedback.
- success-message precision (`bot/handlers/invoice.py`):
  - `Služba položky bola zmenená.`
  - `Opis položky bol nahradený novým textom.`
  - `Detaily položky boli doplnené.`
  - `Detaily položky boli vymazané.`
  - empty-clear case: `Položka nemá žiadne detaily na vymazanie.`
- tests (`tests/test_invoice_state_decisions.py`):
  - updated item-level flow assertions to new user-facing action names and success copy;
  - added state assertion for `nový opis položky` action mode;
  - updated detail-flow expectations to additive details semantics and new messages.

### Scope boundary
- No redesign of confirmation-flow.
- No breaking changes for working `zmeniť službu` branch semantics.
- No large FSM refactor; only minimal routing/message touch for item-level UX fidelity.

## 2026-04-19 — Session 039 — LLM contract rewrite for bounded confirmation/decision normalization

### Goal
Fix unstable `unknown` outcomes in bounded confirmation steps by rewriting only the LLM prompt/instruction contract (no Python routing/fallback expansion).

### Changes
- bounded resolver prompt rewrite (`bot/services/semantic_action_resolver.py`):
  - replaced overly literal/conservative system prompt with explicit intent-normalization policy;
  - added stepwise policy in system prompt: semantic intent inference -> canonical normalization -> `unknown` only for true ambiguity/non-decision/garbage;
  - explicitly documented `yes_no_confirmation` behavior (user not required to answer exact `ano`/`nie`);
  - explicitly documented `postpdf_decision` normalization (`approve/confirm/save` -> `schvalit`, `edit/change/correct` -> `upravit`, `delete/cancel/remove/discard` -> `zrusit`) with destructive-safety guard for unclear intent.
- bounded resolver user payload contract (`bot/services/semantic_action_resolver.py`):
  - added `normalization_contract` object to reinforce semantic-intent-first behavior and context-specific mapping expectations.
- tests (`tests/test_invoice_intent_prerouter.py`):
  - added LLM-path contract tests (mocked `AsyncOpenAI`) for multilingual/noisy confirmation inputs in `invoice_preview_confirmation`;
  - added LLM-path contract tests for multilingual delete/cancel/remove/discard intents in `invoice_postpdf_decision`;
  - assertions verify model path usage (`fallback_used=False`) and presence of new instruction contract fields in prompt/payload.

### Scope boundary
- No FSM/routing changes.
- No fallback keyword/synonym expansion in Python.
- Fix is implemented through LLM contract only.

## 2026-04-18 — Session 038 — Contract-correction pass for edit FSM (item target bounded resolver + runtime contact removal)

### Goal
Finalize previous clean FSM rewrite without redesigning again: align remaining gaps with docs/llm contract by moving multi-item target selection to bounded semantic resolution and removing `edit_invoice_contact` from runtime edit surface.

### Changes
- item-target contract correction (`bot/handlers/invoice.py`):
  - added bounded resolver helper `_resolve_item_target_index_bounded(...)` with dedicated context `invoice_edit_item_target_selection`;
  - `waiting_edit_item_target` no longer relies on local `isdigit()` gate as primary selector;
  - handler now resolves canonical target via bounded resolver first, then Python validates range (`1..N`) and performs fail-loud clarification with state preserved.
- runtime contact edit removal (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - removed `edit_invoice_contact` from invoice-level runtime allowed actions;
  - removed contact wording from invoice-level user prompts;
  - removed invoice-action runtime branch for contact edit;
  - removed fallback mapping for `edit_invoice_contact` in context `invoice_edit_invoice_action`.
- fallback support (`bot/services/semantic_action_resolver.py`):
  - added fallback context `invoice_edit_item_target_selection` for deterministic non-LLM fallback (`1/2/3`, basic ordinal/cardinal forms).
- tests (`tests/test_invoice_state_decisions.py`, `tests/test_voice_state_routing.py`):
  - added multi-item target coverage for numeric and spoken ordinal selection;
  - added ambiguous target + out-of-range fail-loud/state-preserved coverage;
  - added runtime-surface tests proving invoice action prompt no longer offers contact edit and contact text is treated as unknown;
  - added extra voice invoice-action routing check for date phrase.

### Scope boundary
- No new architecture redesign from scratch.
- Kept prior clean state split and value executors unchanged.
- Kept text-only policy for final description value state unchanged.

## 2026-04-18 — Session 037 — Clean FSM/orchestrator redesign for `upraviť faktúru` edit subflow

### Goal
Replace legacy mixed item/invoice edit routing with clean bounded orchestrator states and state-scoped semantic resolution, including voice parity for edit-flow control states.

### Changes
- invoice edit FSM/orchestrator rewrite (`bot/handlers/invoice.py`):
  - replaced mixed `waiting_edit_operation` contract with explicit state split:
    - `waiting_edit_scope`
    - `waiting_edit_invoice_action`
    - `waiting_edit_item_target`
    - `waiting_edit_item_action`
    - value states (`waiting_edit_service_value`, `waiting_edit_invoice_number_value`, `waiting_edit_invoice_date_value`, `waiting_edit_description_value`)
  - replaced heuristic `_detect_edit_operation(...)` primary routing with bounded state-scoped semantic resolvers:
    - scope resolver (`invoice_edit_scope_selection`)
    - invoice action resolver (`invoice_edit_invoice_action`)
    - item action resolver (`invoice_edit_item_action`)
  - removed invoice-level action handling from item-target state; item-target now handles only item index selection.
  - rewrote edit entrypoint from legacy `_start_invoice_item_edit_flow(...)` to clean `start_invoice_edit_flow(...)` with explicit scope selection first.
  - kept integrity rules and reuse of existing executors (`update_item_service`, `update_item_description`, `update_invoice_number`, `update_invoice_issue_date`, PDF rebuild/post-edit prompt helpers).
  - kept `waiting_edit_description_value` as text-only final precision state; number/date states now support voice/text with fail-loud exact-text fallback prompts on invalid/ambiguous input.
- semantic fallback support (`bot/services/semantic_action_resolver.py`):
  - added deterministic fallback contexts for new bounded edit states (`invoice_edit_scope_selection`, `invoice_edit_invoice_action`, `invoice_edit_item_action`) for non-LLM test/runtime fallback paths.
- voice routing parity (`bot/handlers/voice.py`):
  - removed text-only guards for edit-flow selection/control states; STT text now routes through the same edit handlers as text input for:
    - scope
    - invoice action
    - item target
    - item action
    - service value
    - invoice number/date value
  - retained text-only guard only for final item-description value state.
- tests (`tests/test_invoice_state_decisions.py`, `tests/test_voice_state_routing.py`):
  - updated edit-flow tests for clean state graph transitions (scope -> branch-specific states).
  - added explicit routing coverage for `upraviť opis položky` -> description branch and `zmeniť službu` -> service branch.
  - updated single-item and multi-item flow assertions to new orchestrator steps.
  - updated invoice-level branch tests to use `waiting_edit_invoice_action` before number/date value states.
  - expanded voice routing coverage for edit scope, invoice action, item target, item action, service value, and number/date value handler routing.
  - strengthened regression by asserting FSM transition to correct final input state before final handlers (removes prior false-green pattern).

### Scope boundary
- Clean redesign of bounded `upraviť` subflow only (post-PDF in-action model).
- No standalone top-level `edit_invoice` executor added.
- `edit_invoice_contact` remains planned/future-ready (not implemented value persistence).

## 2026-04-17 — Session 036 — Fix post-edit return for `edit_item_description` approval stage

### Goal
Fix narrow runtime bug where successful item description edit inside `upraviť` could return user into edit-loop context instead of reliably staying in post-PDF approval stage.

### Changes
- invoice edit success return hardening (`bot/handlers/invoice.py`):
  - added `_send_post_edit_approval_prompt(...)` helper for post-edit success responses;
  - helper explicitly enforces FSM state `waiting_pdf_decision` before sending approval prompt;
  - wired helper into all successful edit handlers (`replace_service`, `edit_item_description`, `edit_invoice_number`, `edit_invoice_date`) after successful PDF rebuild.
- regression coverage (`tests/test_invoice_state_decisions.py`):
  - extended `replace_service` test with explicit state + approval prompt assertions;
  - extended `edit_item_description` success path test with explicit state + approval prompt assertions;
  - existing invoice number/date tests continue asserting post-edit approval state/prompt behavior.

### Scope boundary
- Narrow runtime bugfix only.
- No edit architecture redesign.
- No expansion to unrelated actions/flows.

## 2026-04-16 — Session 035 — Semantic seam migration batch 1 (bounded service alias contract)

### Goal
Migrate remaining Python-first semantic service resolution seams (invoice parse + service clarification + invoice edit service change) to bounded LLM orchestration with DB-driven allowed sets, while keeping deterministic cleaning/validation unchanged.

### Changes
- invoice parser contract hardening (`bot/services/llm_invoice_parser.py`):
  - removed dictionary/normalizer-based service canonicalization from payload validation;
  - kept deterministic shape checks and safe string normalization only (`strip`, non-empty constraints);
  - service term is now treated as bounded semantic output to be resolved in runtime against allowed aliases.
- invoice runtime bounded resolution (`bot/handlers/invoice.py`):
  - added supplier-scoped bounded service alias resolver that:
    - fetches active alias options from DB,
    - keeps deterministic text cleaning for direct exact/normalized match,
    - otherwise calls bounded semantic resolver with allowed values + per-option description,
    - accepts only one alias from allowed set (or unknown).
  - migrated create-preview item service resolution to this bounded alias contract;
  - migrated service slot clarification (`waiting_service_clarification`) to bounded alias contract;
  - migrated invoice edit `replace_service` path to bounded alias contract;
  - removed old bridge-form/dictionary semantic fallback usage from these paths.
- focused tests (`tests/test_invoice_phase2_ai_layer.py`):
  - updated parser expectations to deterministic-only service-field repair behavior (no dictionary semantic rewrite),
  - added tests for bounded alias resolution (deterministic direct match + bounded LLM canonical selection),
  - adjusted multi-item preview fixture coverage to include alias set required by bounded contract.

### Scope boundary
- Deterministic cleaning/validation/FSM/persistence logic kept in Python.
- No giant synonym dictionaries introduced.
- No architecture expansion beyond bounded service-semantic seams targeted in this batch.

## 2026-04-16 — Session 034 — Pre-merge audit fixes for Phase 1 multi-item `create_invoice`

### Goal
Apply only merge-blocking safety fixes discovered during pre-merge audit of Phase 1 multi-item `create_invoice` runtime patch.

### Changes
- item-boundary ambiguity hardening (`bot/handlers/invoice.py`):
  - strengthened `_looks_like_item_boundary_split(...)` with numeric-token count check against expected item count;
  - prevents silent acceptance of two-item candidate splits when raw text contains only one amount token (e.g. conjunction phrase with one number).
- aggregate total invariant hardening:
  - in confirmation save path, added explicit guard that draft aggregate total equals sum of persisted item totals before DB insert;
  - in `InvoiceService.create_invoice_with_items(...)`, added fail-loud invariant check (`invoice total == sum(item totals)`).
- docs consistency:
  - removed contradictory `single-item` status line in orchestrator contract section 6.2 so runtime status markers are internally consistent.
- focused regression tests:
  - added ambiguity regression for multi-item candidate with conjunction but single amount token (must clarify, not save silently);
  - added save-path regression proving total mismatch is rejected fail-loud and invoice is not persisted.

### Scope boundary
- No architecture redesign.
- No scope expansion to delete/edit-contact/unrelated flows.
- Only targeted merge-safety fixes for bounded Phase 1 behavior.

## 2026-04-16 — Session 033 — Phase 1 runtime multi-item support for `create_invoice` intake

### Goal
Implement the smallest safe runtime path for Phase 1 multi-item invoice intake in `create_invoice` flow, while preserving backward-compatible singleton behavior and Python-owned validation/side effects.

### Changes
- prompt contract (`prompts/invoice_draft_prompt.txt`):
  - extended invoice draft prompt with optional bounded `biznis_sk.items[]` candidate shape;
  - preserved singleton fields as mandatory backward-compatible shape;
  - documented Phase 1 bound `items[]` max size = 3 and no open-ended extraction.
- parser/validator (`bot/services/llm_invoice_parser.py`):
  - added optional dual-shape validation for `biznis_sk.items[]`;
  - implemented fail-safe payload errors for invalid items shape, count overflow, and unresolved item service terms;
  - preserved legacy singleton validation path and cleanup behavior.
- runtime normalization/build (`bot/handlers/invoice.py`):
  - intake extraction now always provides internal `items[]` normalized draft shape (singleton auto-wrap);
  - preview builder now supports single-item and bounded multi-item normalization with safe checks:
    - max items bound,
    - boundary ambiguity guard,
    - per-item quantity/unit_price/amount coherence via existing deterministic semantics;
  - added bounded clarification slot for item-split/financial ambiguity (`items`);
  - preview text formatting now renders item lines when draft has multiple items.
- persistence (`bot/services/invoice_service.py`):
  - added `CreateInvoiceItemPayload` and `create_invoice_with_items(...)`;
  - kept `create_invoice_with_one_item(...)` as compatibility wrapper over new multi-item insert path.
- save/confirm path (`bot/handlers/invoice.py`):
  - `process_invoice_preview_confirmation(...)` now persists all normalized draft items when present;
  - singleton save behavior remains compatible.
- service normalization (`bot/services/service_term_normalizer.py`):
  - added Slovak `montáž/montaz` variants to deterministic canonical mapping.
- tests:
  - expanded Phase 2 parser/preview tests with dual-shape extraction, bounds rejection, multi-item preview total, and ambiguous multi-item clarification;
  - added state-decision regression ensuring confirmation persists multiple `invoice_item` rows.

### Scope boundary
- Added: Phase 1 multi-item support for create-invoice intake/runtime path.
- Not added: delete/cancel flow redesign, advanced layout redesign, or unrelated edit-flow redesign.
- LLM remains bounded candidate extractor; Python remains validator/workflow/persistence owner.

## 2026-04-16 — Session 032 — Docs-first dual-shape `create_invoice` intake contract for future multi-item support

### Goal
Define a safe docs-first contract evolution for `create_invoice`/Phase 2 invoice intake so future runtime can support both one item and multiple items without breaking bounded architecture or current single-item behavior.

### Changes
- orchestrator contract (`docs/FakturaBot_LLM_Orchestrator_Contract.md`):
  - added dedicated docs-first section for planned `create_invoice` dual-shape intake;
  - documented backward-compatible strategy:
    - keep existing singleton `biznis_sk` item fields,
    - add optional bounded `biznis_sk.items[]`;
  - fixed authority split for segmentation:
    - LLM may return bounded candidate item segmentation only,
    - Python remains final validator/workflow/persistence owner;
  - documented Phase 1 bounds:
    - `items[]` max size = 3,
    - no open-ended extraction;
  - documented candidate item shape (service term + qty/unit/unit_price/amount + optional detail),
  - documented split semantics examples and fail-safe clarification triggers.
- product spec (`docs/TZ_FakturaBot.md`):
  - added subsection under invoice draft section with same dual-shape decisions, bounds, ambiguity/fallback rules, and future runtime follow-up areas.
- in-action registry (`docs/llm/In_Action_Response_Registry.md`):
  - added docs-first contract-tracking row for `create_invoice` Phase 2 dual-shape intake;
  - added explicit note that runtime remains single-item until follow-up patches.

### Scope boundary
- Docs-first only.
- No runtime implementation in this patch.
- No prompt implementation in this patch.
- Current create flow remains single-item until follow-up parser/runtime/prompt patches.

## 2026-04-15 — Session 031 — Runtime `edit_invoice_date` inside bounded `upraviť` flow

### Goal
Implement runtime support for invoice-date edit (`edit_invoice_date`) inside existing bounded `edit_invoice`/`upraviť` flow, without expanding to contact edit or item numeric/unit/price edits.

### Changes
- invoice edit runtime:
  - extended bounded edit operation detection with invoice-level operation `edit_invoice_date`;
  - added bounded FSM state for invoice-date value input;
  - wired selection path from existing `upraviť` flow (single-item and multi-item invoices) to invoice-date edit state;
  - added bounded Slovak prompts for strict date input:
    - entry: `Aktuálny dátum faktúry je {current_date}. Napíšte nový dátum textom vo formáte DD.MM.RRRR.`
    - invalid: `Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.`
- validation/safety:
  - added strict Phase 1 parser helper `parse_strict_date_dd_mm_yyyy(...)`;
  - accepts only `DD.MM.RRRR`;
  - rejects non-matching format and impossible dates (e.g. `31.02.2026`);
  - no natural-language parsing, no silent reinterpretation, no best-guess date conversion.
- persistence/service:
  - added invoice service helper `update_invoice_issue_date(...)`;
  - on valid input, updates `invoice.issue_date` with normalized ISO value used by current storage model.
- rebuild flow:
  - after successful invoice-date update, runtime rebuilds updated PDF and returns to `waiting_pdf_decision`;
  - previous PDF cleanup path remains aligned with existing edit rebuild behavior.
- voice guard:
  - added text-only guard for invoice-date edit state in voice handler:
    - `Pre dátum faktúry použite textový vstup vo formáte DD.MM.RRRR.`

### Invariant decision for this patch
- Chosen behavior: **B**.
- Editing invoice date is allowed while invoice number remains unchanged in this patch.
- No auto-renumbering is introduced.

### Tests
- added runtime tests for:
  - successful invoice-date edit to valid strict value (+ persistence + PDF rebuild + post-edit state),
  - invalid format rejection with bounded Slovak prompt and preserved old value/state,
  - impossible date rejection with safe retry prompt and preserved old value/state,
  - voice precision-safe guard for invoice-date edit state.
- existing `upraviť položku` and `upraviť číslo faktúry` runtime tests remain in suite as regression coverage.

### Scope boundary
- This runtime patch adds only `edit_invoice_date`.
- Still out of scope (not implemented here):
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`

## 2026-04-15 — Session 030 — Runtime `edit_invoice_number` inside bounded `upraviť` flow

### Goal
Implement runtime support for invoice-number edit (`edit_invoice_number`) inside existing bounded `edit_invoice`/`upraviť` flow, without expanding to other invoice-level or item numeric/date/contact edits.

### Changes
- invoice edit runtime:
  - extended bounded edit operation detection with invoice-level operation `edit_invoice_number`;
  - added bounded FSM state for invoice-number value input;
  - wired selection path from existing `upraviť` flow (single-item and multi-item invoices) to invoice-number edit state;
  - added precision-safe prompts for text-only final invoice-number input;
- validation/safety:
  - added runtime invoice-number validation for project format (`RRRRNNNN`) with issue-year consistency check;
  - added application-level uniqueness check before save;
  - duplicate detection returns bounded Slovak prompt and keeps edit state:
    - `Číslo faktúry už existuje. Zadajte prosím iné číslo.`
  - no overwrite, no auto-rename, no best-guess correction;
- persistence/service:
  - added invoice service helpers:
    - `is_invoice_number_available(...)`
    - `update_invoice_number(...)` with DB-level integrity fallback handling;
  - kept DB unique constraints as final guard (no schema weakening);
- rebuild flow:
  - after successful invoice-number update, runtime rebuilds updated PDF and returns to `waiting_pdf_decision`;
  - previous PDF file path cleanup is attempted when invoice number change produces a different PDF path;
- voice guard:
  - added text-only guard for invoice-number edit state in voice handler.

### Tests
- added runtime tests for:
  - successful invoice-number edit to free value (+ persistence + PDF rebuild + post-edit state),
  - duplicate invoice-number rejection with required bounded Slovak prompt and preserved old value/state,
  - invalid invoice-number rejection with safe retry prompt and preserved old value/state,
  - voice precision-safe guard for invoice-number edit state.
- preserved and reran existing `upraviť položku` regression coverage.

### Scope boundary
- This runtime patch adds only `edit_invoice_number`.
- Still out of scope (not implemented here):
  - `edit_invoice_date`
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`

## 2026-04-15 — Session 029 — Docs-first full `edit_invoice` / `upraviť` scope map

### Goal
Document one unified planned edit surface for `edit_invoice` so future runtime patches follow a single contract (invoice-level + item-level) instead of separate mini-flows.

### Changes
- updated orchestrator contract to formalize full bounded `edit_invoice` subflow map:
  - invoice-level operations:
    - `edit_invoice_number`
    - `edit_invoice_date`
    - `edit_invoice_contact`
  - item-level operations:
    - `replace_service`
    - `edit_item_description`
    - `edit_item_quantity`
    - `edit_item_unit`
    - `edit_item_unit_price`
- documented required decisions:
  - `edit_invoice` remains reserved top-level token with bounded in-action/subflow runtime;
  - invoice-level and item-level fields are documented separately;
  - precision-sensitive item fields require item targeting;
  - single-item invoices may default to first item;
  - multi-item invoices require explicit selection or bounded clarification;
  - precision-sensitive fields are text-first where ambiguity risk is high;
  - destructive/integrity-sensitive edits fail safe (no silent auto-fix).
- updated in-action registry to split `edit_invoice` map into:
  - `edit_invoice:invoice_level` (planned),
  - `edit_invoice:item_level` (partial: implemented + planned).
- updated TZ section 4.7 to align product-level contract with the same full map and explicit status markers.

### Notes
- Docs-only session; no runtime code changes.
- Newly mapped operations are not runtime-implemented yet:
  - `edit_invoice_number`
  - `edit_invoice_date`
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`
- Existing runtime coverage remains:
  - `replace_service`
  - `edit_item_description`

## 2026-04-15 — Session 028 — Runtime Phase 1 item edit inside `upraviť faktúru`

### Goal
Implement runtime Phase 1 item-edit subflow under post-PDF `upraviť` decision, including separate operations (`replace_service`, `edit_item_description`), `item_description_raw` persistence, bounded validation, and PDF rebuild.

### Changes
- DB/schema:
  - added `invoice_item.item_description_raw` column to bootstrap schema;
  - added backward-compatible bootstrap migration path (`ALTER TABLE ... ADD COLUMN item_description_raw`) for legacy local DB shape;
- service layer:
  - extended `InvoiceItemRecord` with `item_description_raw`;
  - added item update methods:
    - `update_item_service(...)`
    - `update_item_description(...)`
  - added `ContactService.get_by_id(...)` for rebuild path;
- invoice runtime flow:
  - replaced post-PDF `upraviť` placeholder cancel path with real item-edit subflow entry;
  - added bounded states for item-edit:
    - target item selection (future-ready multi-item),
    - operation selection (`replace_service` vs `edit_item_description`),
    - service update input,
    - description text input;
  - single-item invoices default to first item target;
  - multi-item invoices require bounded item index clarification;
  - `replace_service` reuses existing alias dictionary resolution path and does not mutate `item_description_raw`;
  - `edit_item_description` supports `set/replace/clear`, does not mutate canonical service fields;
  - added bounded overlength guard (max 2 rendered detail lines) with Slovak shorten prompt;
  - successful edits rebuild and resend updated PDF, then return to `waiting_pdf_decision`;
- voice guard:
  - in precision-sensitive description state, voice no longer writes final detail; bot requests text input;
  - added text-only guard prompts for other edit subflow precision states;
- PDF/render:
  - `PdfInvoiceItem` now supports optional `detail`;
  - PDF item rendering outputs main service title with optional detail line(s) below;
  - added render-fit helper `validate_item_detail_render_fit(...)` used by runtime validator.

### Tests
- added runtime tests for:
  - replace service with description preserved + PDF rebuild,
  - set/replace/clear description with canonical service preserved,
  - reject too-long description with bounded Slovak prompt and unchanged stored value,
  - single-item default targeting,
  - multi-item missing target clarification,
  - voice text-only guard for description state.

### Notes
- add-item flow remains out of scope.
- Runtime now supports Phase 1 item edit only (replace service, edit description).

## 2026-04-15 — Session 027 — Docs cleanup pass for Phase 1 item edit contract

### Goal
Cleanup docs after initial Phase 1 item-edit patch: remove naming drift, make clear semantics explicit, and document minimal machine-safe bounded output shape for `edit_invoice:item_edit`.

### Changes
- unified canonical operation names across docs for item edit:
  - `replace_service`
  - `edit_item_description`
  - `unknown`
- explicitly fixed description mutation semantics for `edit_item_description`:
  - `set`
  - `replace`
  - `clear`
- documented minimal bounded output shape for planned `edit_invoice:item_edit` in docs:
  - `target_item_index`
  - `operation`
  - `value`

### Notes
- Docs cleanup pass completed.
- Runtime implementation is still not included.

## 2026-04-15 — Session 026 — Docs-first Phase 1 item edit contract inside `upraviť faktúru`

### Goal
Introduce documentation-only source-of-truth contract for Phase 1 `upraviť položku` as in-action edit subflow within future `edit_invoice`, before any runtime patch.

### Changes
- updated orchestrator/docs contracts to formalize that:
  - `upraviť položku` is in-action (not top-level action),
  - Phase 1 item edit supports two distinct operations:
    - service replacement (canonical service identity),
    - free-text detail edit via separate `item_description_raw`;
- recorded render/preview rule:
  - main title from service alias/service DB,
  - optional `item_description_raw` rendered below title with max 2-line limit,
  - no silent truncation; bot must request shorter text in bounded Slovak prompt;
- documented precision-sensitive input rule:
  - `item_description_raw` is text-first/text-only safe in Phase 1,
  - voice must not freely guess long detail text into stored value;
- documented future-ready item-targeting contract:
  - current single-item default may target first item,
  - future multi-item invoices require explicit selection or bounded clarification.

### Notes
- Runtime implementation is not included in this session.
- Key decision: keep canonical service semantics separate from optional free-text item detail (`item_description_raw`).
- Add-item flow remains out of scope for this docs patch.

## 2026-04-14 — Session 025 — `add_service_alias` top-level semantic+voice runtime wiring

### Goal
Make existing manual `/service` flow reachable as canonical top-level action `add_service_alias` from text semantics and voice (top-level), without introducing a second service architecture.

### Changes
- runtime routing:
  - added canonical top-level action `add_service_alias` to top-level bounded resolver branch in `process_invoice_text(...)`;
  - routed semantic `add_service_alias` into the existing `/service` flow entry (shared supplier handler intake), no new service flow created;
- bounded resolver hints:
  - added optional runtime `action_hints` support to resolver payload;
  - used compact hints selectively for `add_service_alias` (ambiguous action) and minimal separation hint for `create_invoice`;
- voice:
  - top-level voice keeps current STT -> top-level semantic path; `add_service_alias` now reaches existing `/service` flow via that path;
  - added explicit voice rejection in service precision-sensitive states:
    - short alias: `Napíšte krátky názov položky textom.`
    - full title: `Napíšte plný názov služby textom.`
- tests:
  - top-level semantic resolution coverage for `add_service_alias`;
  - top-level semantic routing test into shared `/service` flow entry;
  - voice top-level pass-through coverage for `add_service_alias` path;
  - voice rejection coverage for service short/full text-only states;
  - manual `/service` command flow regression test (2-step save flow persists mapping).

### Notes
- Python remains execution authority.
- Bot-facing replies added/updated in runtime are Slovak-only.
- Precision-sensitive service fields remain text-only; no STT guessing for these steps.

## 2026-04-13 — Session 024 — `add_service_alias` ambiguous-action documentation prep

### Goal
Prepare docs before runtime work so `add_service_alias` can be introduced as a canonical ambiguous top-level action (manual flow exists now, semantic/voice invoke later).

### Changes
- updated orchestrator contract with optional semantic action hints section for ambiguous actions;
- added `docs/llm/Bounded_Resolver_Prompt_Template.md` with optional `action_hints` format and compact examples for `create_invoice` and `add_service_alias`;
- added `docs/llm/New_Action_Design_Checklist.md` with ambiguity/hints/canonical-vs-noisy wording checklist items;
- updated canonical action registry to explicitly mark `add_service_alias` as ambiguous, manual implemented, voice top-level invoke not yet, and hint support recommended for future bounded resolution;
- updated TZ with concise optional-hints requirement and canonical-vs-noisy wording separation rule;
- updated README doc pointers.

### Notes
- semantic action hints are documented as optional and selective (not mandatory for every action);
- no runtime code changes were made.

## 2026-04-13 — Session 023 — Canonical action audit repair (manual `/service` flow included)

### Goal
Repair canonical action audit after detecting that previous inventory missed at least one already implemented manual user-facing flow (`add_service_alias` via `/service`).

### Changes
- created `docs/llm/Canonical_Action_Registry.md` with corrected evidence-based inventory:
  - top-level user-facing actions,
  - bootstrap/admin flows,
  - explicit reserved placeholders (`send_invoice`, `edit_invoice`),
  - explicit correction note for implemented manual `/service` flow;
- created `docs/llm/In_Action_Response_Registry.md` with bounded in-action groups, deterministic confirmations, and slot-clarification groups;
- updated `docs/FakturaBot_LLM_Orchestrator_Contract.md` with registry linkage discipline;
- updated `README.md` with pointers to new audit registries.

### Audit correction note
`/service` flow is implemented-manual (command + in-flow text) and persists service alias mappings.  
It is not part of top-level semantic resolver list, but it is still a real user-facing action and must be tracked in canonical action audit.

## 2026-04-13 — Session 022 — Quantity/unit-price clarification semantics broadened

### Goal
Broaden existing bounded slot `quantity_unit_price_pair` from pair-only handling to natural clarification semantics:
- accept quantity + unit-price forms,
- accept price-only fallback (`quantity=1`),
while keeping current architecture and FSM flow unchanged.

### Changes
- `bot/handlers/invoice.py`:
  - updated Slovak clarification prompt to explicitly allow either:
    - quantity + unit price,
    - or price-only when quantity is 1.
- `bot/services/semantic_action_resolver.py`:
  - expanded bounded resolver instruction for `resolve_quantity_unit_price_pair(...)` to support:
    - pair input,
    - single-number input (maps to `quantity=1`);
  - expanded deterministic fallback parser to support additional natural forms:
    - `3 1500`, `3 * 1500`, `3 po 1500`, `3x po 1500`,
    - `три kusy по 1500`, `dva krát po 1500`,
    - `množstvo 3, cena za kus 1500`,
    - `количество 3, цена 1500`,
    - single-number price fallback (`1500` -> `1 × 1500`).
- tests:
  - added/extended slot-clarification tests for pair forms and price-only fallback;
  - kept existing pair regressions and voice routing regression.

### Constraints preserved
- Same slot token (`quantity_unit_price_pair`) and same FSM state (`waiting_slot_clarification`).
- No contact-flow changes, no service-slot repair changes, no generalized slot-clarification redesign.
- Python remains execution authority and source of truth.

## 2026-04-13 — Session 021 — Bounded quantity × unit_price slot clarification in invoice flow

### Goal
Add a dedicated bounded clarification path for missing financial breakdown in invoice flow (`quantity × unit_price`) without architecture redesign and without touching contact/service flows.

### Changes
- `bot/handlers/invoice.py`:
  - added dedicated slot `quantity_unit_price_pair` (reusing existing `waiting_slot_clarification` FSM state);
  - when financial breakdown is unresolved, clarification now targets this dedicated slot;
  - added slot-specific Slovak clarification prompt: `Uveďte množstvo a cenu za jednotku, napr. 2x po 1500.`;
  - wired bounded quantity/unit-price resolver in slot continuation path and update of partial draft fields (`quantity`, `unit_price`) only.
- `bot/services/semantic_action_resolver.py`:
  - added bounded resolver `resolve_quantity_unit_price_pair(...)` with strict structured output contract:
    - `{"canonical":"quantity_unit_price_pair","quantity":...,"unit_price":...}`
    - or `{"canonical":"unknown"}`;
  - LLM request now includes clarification context, `expected_reply_type=quantity_times_unit_price`, and supported languages `uk/ru/sk`;
  - deterministic fallback parser supports multilingual examples including numeric and small-number-word variants.
- tests:
  - added text clarification coverage for:
    - `2 крат по 1500`,
    - `два крат по 1500`,
    - `dva krát po 1500`;
  - added voice routing assertion that STT transcript in `waiting_slot_clarification` is passed unchanged to slot clarification path;
  - added regression for explicit-total-only invoice semantics (`1 × total`) to remain stable;
  - kept/updated existing generalized clarification expectations for the new dedicated financial slot prompt.

### Constraints preserved
- No new FSM state for clarification.
- No contact flow changes.
- Service-slot repair behavior preserved.
- Python remains source of truth for validation, draft update, amount computation, and preview lifecycle.

## 2026-04-12 — Session 020 — Generalized invoice slot clarification + project-wide partial-draft contract

### Goal
Expand already-merged service-slot clarification pattern to other critical invoice slots and formalize slot-level clarification/partial-draft retention as a structured workflow principle.

### Changes
- `bot/handlers/invoice.py`:
  - generalized unresolved-slot handling for invoice draft build with partial retention in FSM (`invoice_partial_draft`);
  - added slot-specific clarification prompts (Slovak-only) for customer, delivery date, due days, quantity, and unit price;
  - added unified continuation path for slot clarification replies that updates one slot and resumes preview build;
  - preserved existing service clarification behavior and compatibility state;
  - improved debug transparency for recoverable unresolved-slot cases.
- `bot/services/llm_invoice_parser.py`:
  - customer-candidate payload failures now emit recoverable `customer_unresolved` with partial payload snapshot.
- tests:
  - added focused invoice clarification coverage for customer/date/due-days/amount slot continuation;
  - preserved service-slot regression path and fatal payload fail-loud behavior checks.
- docs:
  - updated orchestrator contract + TZ + README + CHANGELOG for project-level slot clarification principle.

### Architectural decision
For structured workflows, fail one slot—not whole workflow:
- preserve partial state,
- clarify only unresolved slot,
- continue from current step,
- reserve full reset for fatal errors only.

## 2026-04-12 — Session 019 — AI orchestration contract shift to bounded canonicalization

### Goal
Record architecture milestone: transition from narrow draft/token-routing model to unified semantic resolver contract.

### Decision
- Adopt **Bounded Semantic Canonicalization** as the AI orchestration contract baseline.
- Introduce a unified **Semantic Action Resolver** concept for:
  - top-level action resolution,
  - in-state reply resolution,
  - value/slot canonicalization.
- Keep Python as the only execution authority for validation, context checks, and side effects.

### Notes
- LLM role is semantic canonicalization within Python-defined bounds (allowed set + context), returning one canonical token or `unknown`.
- This is a documentation/architecture alignment milestone; execution authority boundaries remain fail-loud on Python side.

## 2026-04-12 — Session 018 — Post-PDF fail-loud guard + cleanup-order hardening

### Goal
Close two correctness gaps in deterministic post-PDF lifecycle:
- fail loud when post-PDF FSM state misses `last_invoice_id`;
- prioritize invoice-number release by running DB cleanup before PDF-file cleanup.

### Changes
- `bot/handlers/invoice.py`:
  - `process_invoice_postpdf_decision(...)` now validates `last_invoice_id` at start and fails loud (`Návrh faktúry už nie je dostupný...`) instead of claiming success;
  - post-PDF `upraviť`/`zrušiť` cleanup order reversed to DB-first then file-unlink, with isolated error handling so unlink failure no longer blocks DB cleanup;
  - preview-confirm failure cleanup path (after invoice insert) now also does DB cleanup first and performs file cleanup in a separate guarded block.
- `tests/test_invoice_state_decisions.py`:
  - added regression for missing `last_invoice_id` in post-PDF state (no fake success);
  - added regression for unlink failure on post-PDF cancel ensuring invoice row is still deleted;
  - added regression for preview-confirm failure path with unlink failure ensuring invoice row is still deleted.

## 2026-04-12 — Session 017 — Deterministic post-PDF decision FSM + voice state routing

### Goal
Implement deterministic state-based command handling after invoice preview and after PDF send, while keeping existing top-level invoice pre-router unchanged.

### Changes
- `bot/handlers/invoice.py`:
  - kept top-level pre-router as-is (`_normalize_intent_token`, `_detect_invoice_intent`);
  - added deterministic preview parser for `InvoiceStates.waiting_confirm` (`confirm_preview` / `cancel_preview` / `unknown`) with SK/UA/RU yes-no coverage;
  - added deterministic post-PDF parser for `InvoiceStates.waiting_pdf_decision` (`approve_pdf_invoice` / `edit_pdf_invoice` / `cancel_pdf_invoice` / `unknown`) with SK/UA/RU command coverage;
  - extracted reusable handlers:
    - `process_invoice_preview_confirmation(...)`
    - `process_invoice_postpdf_decision(...)`
  - after PDF send, FSM now stores `last_invoice_id`, `last_invoice_number`, `last_pdf_path`;
  - added cleanup on PDF generation/send failure after invoice insert: remove PDF (if exists), delete invoice items + invoice row, clear FSM.
- `bot/handlers/voice.py`:
  - after STT, routes command deterministically by current FSM state:
    - `waiting_confirm` -> preview confirmation processor,
    - `waiting_pdf_decision` -> post-PDF decision processor,
    - otherwise -> existing generic invoice text flow.
- `bot/services/invoice_service.py`:
  - added lifecycle helpers:
    - `update_invoice_status(invoice_id, status)`
    - `delete_invoice_with_items(invoice_id)`
  - cleanup path now fully deletes invoice items + invoice row so invoice number is freed for reuse on `upraviť` / `zrušiť`.
- `tests/`:
  - extended parser tests for required multilingual preview/post-PDF commands;
  - added state-flow tests for preview confirm and post-PDF approve/edit/cancel behaviors, including cleanup and number release;
  - added voice routing tests to verify FSM-aware deterministic dispatch.

### Constraints preserved
- Top-level create/edit/send pre-router behavior remains unchanged.
- LLM still only drafts invoice payload; state command interpretation is deterministic Python.
- User-facing replies introduced/changed in this session are Slovak-only.

## 2026-04-12 — Session 016 — Delivery-date anchor follow-up (UA months + local year scope)

### Goal
Harden delivery-date year anchoring after review:
- add Ukrainian month forms for day/month-without-year detection;
- avoid disabling anchoring when an unrelated year appears elsewhere in the same message.

### Changes
- `bot/handlers/invoice.py`:
  - added Ukrainian month forms and common short forms to date phrase detection (`січня...грудня`, plus short forms);
  - added `_has_explicit_year_near_day_month(...)` and narrowed explicit-year detection to a local span around matched day+month phrase;
  - anchoring is now kept active when a year is present outside the local delivery-date phrase.
- `tests/test_invoice_phase2_ai_layer.py`:
  - added regression for unrelated-year-in-message case (anchoring must still apply);
  - added regression for Ukrainian month form (`4 квітня`);
  - added regression for explicit local year near day+month (anchoring must be disabled and explicit year respected).

### Constraints preserved
- Deterministic behavior only (no fuzzy parsing, no silent heuristics beyond explicit local-span rule).
- Fail-loud behavior unchanged for inconsistent explicit day/month vs payload date.

---

## 2026-04-11 — Session 015 — Invoice Phase 2 delivery-date year anchoring guardrail

### Goal
Stop LLM-induced wrong-year drift for delivery dates when user says only day+month (no explicit year), e.g. `4 апреля` incorrectly becoming `2023-04-04`.

### Changes
- `prompts/invoice_draft_prompt.txt`:
  - hardened instruction for `datum_dodania`: for explicit day+month without year, use current invoice-flow year (issue-date year), and do not invent arbitrary past/future year.
- `bot/handlers/invoice.py`:
  - added deterministic day+month-without-year detector (SK/RU month forms and common short forms);
  - added `_resolve_delivery_date(...)` guardrail:
    - anchors such inputs to `issue_date.year`,
    - corrects mismatched LLM year when month/day match but year drifts,
    - fails loud on inconsistent day/month mismatch between user input and LLM payload.
  - wired preview build flow to use the new guardrail and clear state on fail-loud date inconsistency.
- `tests/test_invoice_phase2_ai_layer.py`:
  - added regression tests for:
    - `4 апреля` → `2026-04-04`,
    - `4 apríla` → `2026-04-04`,
    - mixed voice-like multilingual input without year,
    - explicit year input remains respected.

### Constraints preserved
- Deterministic Python remains source of truth for final invoice draft normalization.
- No schema changes.
- No hidden auto-fix outside deterministic date anchoring rules.

---

## 2026-04-11 — Session 014 — PDF row alignment + supplier VAT wording follow-up

### Goal
Polish two remaining PDF output seams without redesign:
- visually align item description with numeric columns in item rows;
- improve supplier VAT fallback wording when supplier is not VAT registered.

### Changes
- `bot/services/pdf_generator.py`:
  - added `_item_row_description_first_baseline(...)` and used it for item description drawing so single-line descriptions share baseline alignment with quantity/unit/unit-price/total columns, while wrapped descriptions stay centered in the row block;
  - extracted `_format_supplier_ic_dph_line(...)` and changed supplier fallback from `IČ DPH: -` to `IČ DPH: Nie je platiteľ DPH`.
- `tests/test_pdf_generator_layout_wrapping.py`:
  - added regression checks for description baseline behavior (single-line parity with numeric baseline and wrapped text staying inside row bounds);
  - added regression checks for supplier VAT fallback wording.

### Constraints preserved
- No PDF redesign.
- Amount semantics in preview/save/PDF path unchanged.
- Current preview/save flow unchanged.

---

## 2026-04-11 — Session 013 — Invoice service display title regression guard

### Goal
Fix invoice runtime regression where service display title could fall back to raw multilingual text despite existing supplier alias mapping under a deterministic related form.

### Regression shape
- Raw item input: `ремонт`
- Internal canonical term: `oprava`
- Supplier alias stored only as: `opravy -> <full Slovak display title>`
- Previous runtime checked only raw alias key and then fell back to raw text in preview/PDF.

### Root cause
Cross-layer bridge was incomplete: internal canonicalization and supplier alias mapping are separate deterministic layers, but invoice runtime used only raw `service_short_name` for final alias lookup.

### Decision
Keep supplier alias mapping as source of truth for final preview/PDF title and implement deterministic, explicit lookup cascade in invoice handler:
1. raw alias (`service_short_name`)
2. canonical internal term alias (`service_term_internal`)
3. deterministic bridge forms (`oprava -> opravy`)
4. raw fallback as last resort

No fuzzy search, no LLM, no DB/schema changes, no auto-creation of aliases.

### Safeguard
Added regression tests to lock behavior:
- bridge-form resolution (`ремонт -> oprava -> opravy`)
- raw alias priority over fallback stages
- raw fallback when no deterministic alias matches

---


Р В РІР‚вЂњР РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р В Р’В°Р В Р’В» Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР РЋРЎвЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ.
Р В Р’В¤Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В Р’Вµ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’Вµ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРЎвЂњ Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРЎвЂњ, Р В Р’В° Р В РІвЂћвЂ“ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРЎвЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р РЋР Р‰, Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ, scope Р РЋРІР‚С™Р В Р’В° Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚В Р В Р’ВµР В РЎвЂ”Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.

---

## 2026-04-06 вЂ” Session 012 вЂ” PDF wrapping polish (items + identity blocks + Slovak glyph coverage)

### Р¦С–Р»СЊ

Р—Р°РєСЂРёС‚Рё Р·Р°Р»РёС€РєРѕРІС– seam-Рё PDF СЂРµРЅРґРµСЂР° Р±РµР· СЂРµРґРёР·Р°Р№РЅСѓ:
- РїРµСЂРµРЅРѕСЃ РґРѕРІРіРёС… РЅР°Р·РІ РїРѕР·РёС†С–Р№ Сѓ С‚Р°Р±Р»РёС†С–;
- РґРёРЅР°РјС–С‡РЅС– РІРёСЃРѕС‚Рё СЂСЏРґРєС–РІ/identity block-С–РІ;
- СЃС‚Р°Р±С–Р»СЊРЅРёР№ СЂРµРЅРґРµСЂ СЃР»РѕРІР°С†СЊРєРёС… СЃРёРјРІРѕР»С–РІ (РІРєР»СЋС‡РЅРѕ Р· `Дѕ`, `ЕҐ`) Сѓ РїСЂР°РєС‚РёС‡РЅРёС… С‚РµРєСЃС‚Р°С….

### Р©Рѕ Р·РјС–РЅРµРЅРѕ

- `bot/services/pdf_generator.py`:
  - РґРѕРґР°РЅРѕ helper `_wrap_text_lines(...)` РЅР° Р±Р°Р·С– `pdfmetrics.stringWidth(...)` РґР»СЏ word-wrap РІ РѕР±РјРµР¶РµРЅС–Р№ С€РёСЂРёРЅС–;
  - РґРѕРґР°РЅРѕ helper `_measure_party_block_height(...)` РґР»СЏ СЂРѕР·СЂР°С…СѓРЅРєСѓ РґРёРЅР°РјС–С‡РЅРѕС— РІРёСЃРѕС‚Рё identity block;
  - `_draw_party_block(...)` РѕРЅРѕРІР»РµРЅРѕ:
    - РїС–РґС‚СЂРёРјСѓС” wrapped multi-line lines,
    - РїРѕРІРµСЂС‚Р°С” С„Р°РєС‚РёС‡РЅСѓ РІРёСЃРѕС‚Сѓ Р±Р»РѕРєСѓ;
  - СЃРµРєС†С–СЋ `DodГЎvateДѕ` / `OdberateДѕ` РїРµСЂРµРІРµРґРµРЅРѕ РЅР° СЃРїС–Р»СЊРЅРёР№ baseline:
    - РЅРёР¶РЅСЏ РјРµР¶Р° РЅР°СЃС‚СѓРїРЅРѕРіРѕ Р±Р»РѕРєСѓ СЂР°С…СѓС”С‚СЊСЃСЏ РІС–Рґ `max(height_left, height_right)`,
    - РїСЂРёР±СЂР°РЅРѕ СЂРёР·РёРє РІС–Р·СѓР°Р»СЊРЅРѕРіРѕ overlap РјС–Р¶ Р±Р»РѕРєР°РјРё;
  - items table РѕРЅРѕРІР»РµРЅРѕ:
    - `poloЕѕka` РїРµСЂРµРЅРѕСЃРёС‚СЊСЃСЏ РїРѕ СЃР»РѕРІР°С… РІ РјРµР¶Р°С… РєРѕР»РѕРЅРєРё,
    - РІРёСЃРѕС‚Р° row РґРёРЅР°РјС–С‡РЅРѕ Р·СЂРѕСЃС‚Р°С” РїСЂРё 2+ СЂСЏРґРєР°С… РѕРїРёСЃСѓ,
    - С‡РёСЃР»РѕРІС– РєРѕР»РѕРЅРєРё (`mnoЕѕstvo`, `m.j.`, `cena za m.j.`, `spolu`) Р·Р°Р»РёС€РµРЅС– С„С–РєСЃРѕРІР°РЅРёРјРё С‚Р° РІРµСЂС‚РёРєР°Р»СЊРЅРѕ РІРёСЂС–РІРЅСЏРЅС– РїРѕ С†РµРЅС‚СЂСѓ СЂСЏРґРєР°.
- РґРѕРґР°РЅРѕ regression-С‚РµСЃС‚Рё `tests/test_pdf_generator_layout_wrapping.py`:
  - РїРµСЂРµРІС–СЂРєР°, С‰Рѕ РґРѕРІРіРёР№ description СЂРµР°Р»СЊРЅРѕ СЂРѕР·Р±РёРІР°С”С‚СЊСЃСЏ РЅР° РєС–Р»СЊРєР° СЂСЏРґРєС–РІ;
  - РїРµСЂРµРІС–СЂРєР°, С‰Рѕ РІРёСЃРѕС‚Р° identity block Р·Р±С–Р»СЊС€СѓС”С‚СЊСЃСЏ РґР»СЏ РґРѕРІРіРѕС— Р°РґСЂРµСЃРё.

### Р РµР·СѓР»СЊС‚Р°С‚

- РґРѕРІРіС– РЅР°Р·РІРё РїРѕР·РёС†С–Р№ Р±С–Р»СЊС€Рµ РЅРµ РІвЂ™С—Р¶РґР¶Р°СЋС‚СЊ Сѓ РєРѕР»РѕРЅРєСѓ `mnoЕѕstvo`;
- Р°РґСЂРµСЃРЅС– СЂСЏРґРєРё РІ `DodГЎvateДѕ`/`OdberateДѕ` РїРµСЂРµРЅРѕСЃСЏС‚СЊСЃСЏ РІ РјРµР¶Р°С… Р±Р»РѕРєСѓ;
- РІРёСЃРѕС‚Рё Р±Р»РѕРєС–РІ С– СЂСЏРґРєС–РІ Р°РґР°РїС‚РёРІРЅС–, Р±РµР· Р·РјС–РЅРё Р·Р°РіР°Р»СЊРЅРѕС— СЃС‚СЂСѓРєС‚СѓСЂРё one-page invoice;
- Unicode TTF С€Р»СЏС… С‡РµСЂРµР· ReportLab (`Vera.ttf`, `VeraBd.ttf`) Р»РёС€Р°С”С‚СЊСЃСЏ Р±Р°Р·РѕРІРёРј РјРµС…Р°РЅС–Р·РјРѕРј СЂРµРЅРґРµСЂР° СЃР»РѕРІР°С†СЊРєРёС… РґС–Р°РєСЂРёС‚РёРє.

---

## 2026-04-06 вЂ” Session 011 вЂ” PDF polish (Unicode font + payment block spacing)
## 2026-04-06 РІР‚вЂќ Session 011 РІР‚вЂќ PDF polish (Unicode font + payment block spacing)

### Р В¦РЎвЂ“Р В»РЎРЉ

Р вЂ™Р С‘Р С—РЎР‚Р В°Р Р†Р С‘РЎвЂљР С‘ Р В°РЎР‚РЎвЂљР ВµРЎвЂћР В°Р С”РЎвЂљР С‘ Р Р† PDF-РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚РЎвЂ“ Р В±Р ВµР В· РЎР‚Р ВµР Т‘Р С‘Р В·Р В°Р в„–Р Р…РЎС“: РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”РЎвЂ“ Р Т‘РЎвЂ“Р В°Р С”РЎР‚Р С‘РЎвЂљР С‘Р С”Р С‘, РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…РЎвЂ“РЎРѓРЎвЂљРЎРЉ payment Р В±Р В»Р С•Р С”РЎС“ РЎвЂљР В° Р С”Р С•Р Р…РЎРѓР С‘РЎРѓРЎвЂљР ВµР Р…РЎвЂљР Р…РЎвЂ“РЎРѓРЎвЂљРЎРЉ РЎвЂћРЎвЂ“Р Р…Р В°Р В»РЎРЉР Р…Р С•РЎвЂ” Р Р…Р В°Р В·Р Р†Р С‘ Р С—Р С•Р В·Р С‘РЎвЂ РЎвЂ“РЎвЂ”.

### Р В©Р С• Р В·Р СРЎвЂ“Р Р…Р ВµР Р…Р С•

- `bot/services/pdf_generator.py`:
  - Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎР‚Р ВµРЎвЂќРЎРѓРЎвЂљРЎР‚Р В°РЎвЂ РЎвЂ“РЎР‹ Unicode TTF-РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљРЎвЂ“Р Р† РЎвЂЎР ВµРЎР‚Р ВµР В· ReportLab (`Vera.ttf`, `VeraBd.ttf` РЎвЂ“Р В· Р С—Р В°Р С”Р ВµРЎвЂљР В° `reportlab`);
  - РЎС“РЎРѓРЎвЂ“ Р Р†Р С‘Р Т‘Р С‘Р СРЎвЂ“ РЎвЂљР ВµР С”РЎРѓРЎвЂљР С•Р Р†РЎвЂ“ `setFont(...)` Р С—Р ВµРЎР‚Р ВµР Р†Р ВµР Т‘Р ВµР Р…РЎвЂ“ Р Р…Р В° РЎвЂ РЎвЂ“ РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР С‘ (Р В·Р В°Р СРЎвЂ“РЎРѓРЎвЂљРЎРЉ Helvetica), РЎвЂ°Р С•Р В± Р С”Р С•РЎР‚Р ВµР С”РЎвЂљР Р…Р С• РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚Р С‘РЎвЂљР С‘ РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”РЎвЂ“ РЎРѓР С‘Р СР Р†Р С•Р В»Р С‘;
  - payment block Р С—Р ВµРЎР‚Р ВµРЎР‚Р С•Р В±Р В»Р ВµР Р…Р С• РЎС“ Р В±РЎвЂ“Р В»РЎРЉРЎв‚¬ РЎвЂЎР С‘РЎвЂљР В°Р В±Р ВµР В»РЎРЉР Р…Р С‘Р в„– stacked layout:
    - `IBAN` РЎвЂ“ `SWIFT/BIC` РЎС“ Р В»РЎвЂ“Р Р†РЎвЂ“Р в„– Р С”Р С•Р В»Р С•Р Р…РЎвЂ РЎвЂ“ Р Р…Р В° РЎР‚РЎвЂ“Р В·Р Р…Р С‘РЎвЂ¦ РЎР‚РЎРЏР Т‘Р С”Р В°РЎвЂ¦;
    - `SpР“Т‘sob Р“С”hrady` Р Р†Р С‘Р Р…Р ВµРЎРѓР ВµР Р…Р С• Р С•Р С”РЎР‚Р ВµР СР С• Р Р† Р С—РЎР‚Р В°Р Р†РЎС“ РЎвЂЎР В°РЎРѓРЎвЂљР С‘Р Р…РЎС“ Р В±Р ВµР В· Р С—Р ВµРЎР‚Р ВµРЎвЂљР С‘Р Р…РЎС“;
  - Р Р†Р С‘РЎРѓР С•РЎвЂљРЎС“ payment block Р В·Р В±РЎвЂ“Р В»РЎРЉРЎв‚¬Р ВµР Р…Р С• Р С—Р С•Р СРЎвЂ“РЎР‚Р Р…Р С• (`18mm` РІвЂ вЂ™ `24mm`) Р Т‘Р В»РЎРЏ РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…Р С•Р С–Р С• spacing.
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• regression-РЎвЂљР ВµРЎРѓРЎвЂљ `tests/test_invoice_service_item_normalized.py`:
  - Р С—Р ВµРЎР‚Р ВµР Р†РЎвЂ“РЎР‚РЎРЏРЎвЂќ, РЎвЂ°Р С• `description_normalized` РЎР‚Р ВµР В°Р В»РЎРЉР Р…Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† `invoice_item` РЎвЂ“ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С‘Р в„– Р Т‘Р В»РЎРЏ PDF/fallback Р В»Р С•Р С–РЎвЂ“Р С”Р С‘.

### Р В Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ

PDF Р В»Р С‘РЎв‚¬Р С‘Р Р†РЎРѓРЎРЏ Р Р† Р С—Р С•РЎвЂљР С•РЎвЂЎР Р…РЎвЂ“Р в„– РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ“ (Р В±Р ВµР В· major redesign), Р В°Р В»Р Вµ РЎРѓРЎвЂљР В°Р Р† РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…РЎвЂ“РЎв‚¬Р С‘Р С Р Р† РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚РЎвЂ“:
- РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”Р С‘Р в„– РЎвЂљР ВµР С”РЎРѓРЎвЂљ РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚Р С‘РЎвЂљРЎРЉРЎРѓРЎРЏ Unicode-РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР С•Р С;
- payment block Р Р…Р Вµ РЎРѓРЎвЂљР С‘Р С”Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р С—Р С• Р С—Р С•Р В»РЎРЏРЎвЂ¦;
- РЎвЂћРЎвЂ“Р Р…Р В°Р В»РЎРЉР Р…Р В° canonical Р Р…Р В°Р В·Р Р†Р В° Р С—Р С•Р В·Р С‘РЎвЂ РЎвЂ“РЎвЂ” Р В·Р В°Р В»Р С‘РЎв‚¬Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р В·Р В±Р ВµРЎР‚Р ВµР В¶Р ВµР Р…Р С•РЎР‹ Р Р† persistence-РЎв‚¬Р В°РЎР‚РЎвЂ“ Р Т‘Р В»РЎРЏ Р Р†Р С‘Р С”Р С•РЎР‚Р С‘РЎРѓРЎвЂљР В°Р Р…Р Р…РЎРЏ Р Р† PDF.

---

## 2026-04-06 РІР‚вЂќ Session 010 РІР‚вЂќ Optional SMTP in supplier onboarding/storage

### Р В¦РЎвЂ“Р В»РЎРЉ

Р вЂ”Р Р…РЎРЏРЎвЂљР С‘ Р В±Р В»Р С•Р С”РЎС“РЎР‹РЎвЂЎРЎС“ Р Р†Р С‘Р СР С•Р С–РЎС“ SMTP host/user/pass РЎС“ supplier onboarding Р Т‘Р В»РЎРЏ MVP, РЎвЂ°Р С•Р В± Р С—РЎР‚Р С•РЎвЂћРЎвЂ“Р В»РЎРЉ Р С—Р С•РЎРѓРЎвЂљР В°РЎвЂЎР В°Р В»РЎРЉР Р…Р С‘Р С”Р В° Р СР С•Р В¶Р Р…Р В° Р В±РЎС“Р В»Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂљР С‘ Р В±Р ВµР В· email-Р С”Р С•Р Р…РЎвЂћРЎвЂ“Р С–РЎС“РЎР‚Р В°РЎвЂ РЎвЂ“РЎвЂ”.

### Р В©Р С• Р В·Р СРЎвЂ“Р Р…Р ВµР Р…Р С•

- `supplier` schema Р Р† `bot/services/db.py` Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•: `smtp_host`, `smtp_user`, `smtp_pass` РЎвЂљР ВµР С—Р ВµРЎР‚ nullable (`TEXT` Р В±Р ВµР В· `NOT NULL`);
- `SupplierProfile` Р Р† `bot/services/supplier_service.py` Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С• Р Р…Р В° optional SMTP-Р С—Р С•Р В»РЎРЏ (`str | None`);
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·Р В°РЎвЂ РЎвЂ“РЎР‹ optional SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ РЎС“ service layer:
  - Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“/whitespace Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏ Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎР‹РЎвЂљРЎРЉРЎРѓРЎРЏ РЎРЏР С” `NULL`,
  - РЎвЂЎР С‘РЎвЂљР В°Р Р…Р Р…РЎРЏ РЎРѓРЎвЂљР В°РЎР‚Р С‘РЎвЂ¦ РЎР‚РЎРЏР Т‘Р С”РЎвЂ“Р Р† Р В· Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“Р СР С‘ SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏР СР С‘ Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·РЎС“РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Т‘Р С• `None`;
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎРЏР Р†Р Р…Р С‘Р в„– Р С”Р С•Р Р…РЎвЂљРЎР‚Р В°Р С”РЎвЂљ helper `SupplierService.has_complete_smtp_config(profile)`:
  - email send Р С—Р С•Р Р†Р С‘Р Р…Р ВµР Р… Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљР С‘РЎРѓРЎРЉ РЎвЂљРЎвЂ“Р В»РЎРЉР С”Р С‘ Р С”Р С•Р В»Р С‘ Р Р†РЎРѓРЎвЂ“ 3 SMTP Р С—Р С•Р В»РЎРЏ Р В·Р В°Р Т‘Р В°Р Р…РЎвЂ“;
- onboarding flow (`bot/handlers/onboarding.py`) Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•:
  - SMTP Р С”РЎР‚Р С•Р С”Р С‘ Р СР В°РЎР‹РЎвЂљРЎРЉ РЎвЂљР ВµР С”РЎРѓРЎвЂљ `voliteР”С•nР“В©, "-" alebo /skip pre preskoР”РЊenie`,
  - `-`, `/skip` РЎвЂ“ Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏ Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·РЎС“РЎР‹РЎвЂљРЎРЉРЎРѓРЎРЏ РЎРЏР С” `None`,
  - summary Р С—Р С•Р С”Р В°Р В·РЎС“РЎвЂќ `-` Р Т‘Р В»РЎРЏ Р Р†РЎвЂ“Р Т‘РЎРѓРЎС“РЎвЂљР Р…РЎвЂ“РЎвЂ¦ SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ.
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎвЂљР ВµРЎРѓРЎвЂљР С‘ `tests/test_supplier_smtp_optional.py`:
  - save/load supplier Р В±Р ВµР В· SMTP;
  - save/load supplier Р В· SMTP;
  - Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·Р В°РЎвЂ РЎвЂ“РЎРЏ skip token/empty Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ.

### Р В Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ

`/supplier` Р СР С•Р В¶Р Вµ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р С‘РЎвЂљР С‘РЎРѓРЎРЏ Р В±Р ВµР В· SMTP Р Р…Р В°Р В»Р В°РЎв‚¬РЎвЂљРЎС“Р Р†Р В°Р Р…РЎРЉ; Р С—РЎР‚Р С•РЎвЂћРЎвЂ“Р В»РЎРЉ РЎС“РЎРѓР С—РЎвЂ“РЎв‚¬Р Р…Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ РЎвЂ“ Р Р†Р С‘Р С”Р С•РЎР‚Р С‘РЎРѓРЎвЂљР С•Р Р†РЎС“РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† invoice/PDF flow Р В±Р ВµР В· Р В·Р СРЎвЂ“Р Р… Р С”РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР Р…Р С•Р С–Р С• MVP РЎв‚¬Р В»РЎРЏРЎвЂ¦РЎС“.

---

## 2026-04-06 РІР‚вЂќ Session 009 РІР‚вЂќ Service alias list cleanup (inactive hidden by default)
## 2026-04-06 Р Р†Р вЂљРІР‚Сњ Session 009 Р Р†Р вЂљРІР‚Сњ Service alias list cleanup (inactive hidden by default)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РЎСџР РЋР вЂљР В РЎвЂР В Р’В±Р РЋР вЂљР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚вЂњ alias mappings Р В Р’В·Р РЋРІР‚вЂњ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РўвЂР В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў `/service` Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂќР РЋРЎвЂњ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂ UX flow.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- `ServiceAliasService.list_mappings(...)` Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - default Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р РЋРІР‚С™Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В РЎвЂќР В РЎвЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂ (`is_active = 1`);
  - Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂўР В РЎвЂќ Р РЋР С“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В РЎвЂў (`canonical_title`, `alias`);
  - Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В РЎвЂ”Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `include_inactive=True` Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ;
- `/service` handler Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В РЎвЂР В Р вЂ Р РЋР С“Р РЋР РЏ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂў Р В Р вЂ Р В РЎвЂР В РЎвЂќР В Р’В»Р В РЎвЂР В РЎвЂќР РЋРЎвЂњ Р РЋРІР‚вЂњ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’Вµ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ alias;
- Р РЋРІР‚С™Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В РЎвЂўР В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ `deactivate_mapping` Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р Р†Р вЂљРІвЂћСћР РЋР РЏР В Р вЂ Р В Р’В»Р РЋР РЏР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРЎвЂњ default list;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ alias Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  list;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў `resolve_alias` Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ alias;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В° `include_inactive=True`.

### Р В Р’В Р В Р’ВµР В Р’В·Р РЋРЎвЂњР В Р’В»Р РЋР Р‰Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™

Normal `/service` list Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР РЋРІР‚В¦Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ mappings, Р В Р’В° Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ invoice Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚вЂњ alias.

---

## 2026-04-06 Р Р†Р вЂљРІР‚Сњ Session 008 Р Р†Р вЂљРІР‚Сњ Service alias Р Р†РІР‚В РІР‚в„ў canonical invoice title normalization

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В Р’ВµР РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ normalization layer Р В РўвЂР В Р’В»Р РЋР РЏ invoice item:
alias (Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В Р’В° spoken/text Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В°) Р Р†РІР‚В РІР‚в„ў canonical full title, Р В РЎвЂќР В Р’ВµР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В РЎвЂўР В РЎВ.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ persistence-Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР вЂ№ `supplier_service_alias`:
  - Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋР РЏ `id`, `supplier_id`, `alias`, `canonical_title`, `is_active`, `created_at`;
  - `alias` Р В Р’В· case-insensitive Р РЋРЎвЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р РЋР вЂ№ Р В Р вЂ  Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р РЋРІР‚В¦ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В° (`UNIQUE(supplier_id, alias)` + `COLLATE NOCASE`);
  - bootstrap/schema-check Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В Р вЂ  `init_db` Р В Р’В· fail-loud Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР В РўвЂР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂќР В РЎвЂўР РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ Р В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В¦Р В Р’ВµР В РЎВР РЋРІР‚вЂњ;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/service_alias_service.py`:
  - `create_mapping`,
  - `list_mappings`,
  - `resolve_alias` (exact + trimmed + case-insensitive),
  - `deactivate_mapping` (MVP-safe optional helper);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў supplier-side chat flow `/service` (`bot/handlers/supplier.py`):
  - Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂќР РЋРЎвЂњ alias mappings,
  - Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ 1: Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ alias,
  - Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ 2: Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ canonical title,
  - Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂўР В РЎвЂќ;
- invoice flow (`bot/handlers/invoice.py`) Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ `item_name_raw`,
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂ preview/save/PDF Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ deterministic alias resolution Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· Python/SQLite,
  - Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ match Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ canonical title Р РЋР РЏР В РЎвЂќ `item_name_final`,
  - Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ miss Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ fallback Р В Р вЂ¦Р В Р’В° raw text;
- preview Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў: Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР РЋРІР‚Сњ `raw` Р РЋРІР‚вЂњ `finР вЂњР Р‹lna` Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р РЋРЎвЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ;
- save/PDF Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р РЋРЎвЂњ `invoice_item.description_normalized` Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚С›Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В° (canonical Р В Р’В°Р В Р’В±Р В РЎвЂў fallback raw),
  - PDF Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р РЋРІР‚С›Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРЎвЂњ Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р РЋРЎвЂњ (`description_normalized` Р В Р’В· fallback Р В Р вЂ¦Р В Р’В° `description_raw`);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С™Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ `tests/test_service_alias_service.py`:
  - alias resolution success,
  - fallback when alias not found,
  - case-insensitive + trimmed match.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- fuzzy matching;
- auto-canonicalization Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· LLM;
- Р РЋР С“Р В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ admin/settings UI Р В РўвЂР В Р’В»Р РЋР РЏ mappings.

### Р В Р’В Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

Final service/item title Р В РўвЂР В Р’В»Р РЋР РЏ invoice preview/save/PDF Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В Р вЂ Р В РЎвЂР В Р’В·Р В Р вЂ¦Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’ВµР РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў
Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· supplier-defined mapping Р РЋРЎвЂњ Python/storage, Р В Р’В° Р В Р вЂ¦Р В Р’Вµ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· LLM paraphrasing.

---

## 2026-04-03 Р Р†Р вЂљРІР‚Сњ Session 007 Р Р†Р вЂљРІР‚Сњ Phase 4: invoice draft Р Р†РІР‚В РІР‚в„ў confirm Р Р†РІР‚В РІР‚в„ў PDF preview

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ invoice flow Р В РўвЂР В Р’В»Р РЋР РЏ text/voice input:
draft Р Р†РІР‚В РІР‚в„ў local contact resolution Р Р†РІР‚В РІР‚в„ў preview Р Р†РІР‚В РІР‚в„ў confirm Р Р†РІР‚В РІР‚в„ў save Р Р†РІР‚В РІР‚в„ў PDF preview.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў persistence Р В РўвЂР В Р’В»Р РЋР РЏ faktР вЂњРЎвЂќr:
  - Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР РЏ `invoice`,
  - Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР РЏ `invoice_item`,
  - fail-loud schema compatibility checks Р В Р’В±Р В Р’ВµР В Р’В· auto-drop;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/invoice_service.py`:
  - Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР В РЎВР В Р’ВµР РЋР вЂљР РЋРЎвЂњ `RRRRNNNN`,
  - save faktР вЂњРЎвЂќry Р В Р’В· Р В РЎвЂўР В РўвЂР В Р вЂ¦Р В РЎвЂР В РЎВ Р РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂќР В РЎвЂўР В РЎВ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ,
  - get by id/number,
  - save `pdf_path`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/pdf_generator.py` (reportlab + qrcode):
  - one-page business invoice layout,
  - DodР вЂњР Р‹vateР вЂќРЎвЂў/OdberateР вЂќРЎвЂў block,
  - meta/dates block,
  - payment block,
  - items table,
  - strong `Na Р вЂњРЎвЂќhradu` block,
  - QR block;
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/invoice.py`:
  - `/invoice` text entry point,
  - preview Р РЋР С“Р В Р’В»Р В РЎвЂўР В Р вЂ Р В Р’В°Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂќР В РЎвЂўР РЋР вЂ№,
  - confirm (`ano`/`nie`),
  - PDF decision step (`schvР вЂњР Р‹liР вЂўРўС’`/`upraviР вЂўРўС’`);
- voice flow Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРЎвЂњ Р РЋРІР‚С™Р В РЎвЂўР В РІвЂћвЂ“ Р РЋР С“Р В Р’В°Р В РЎВР В РЎвЂР В РІвЂћвЂ“ invoice path:
  - STT text Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ Р В РЎвЂўР В Р’В±Р РЋР вЂљР В РЎвЂўР В Р’В±Р В Р’В»Р РЋР РЏР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· Р РЋР С“Р В РЎвЂ”Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Phase 4 flow;
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў local contact-only resolution:
  - exact match,
  - case-insensitive exact match;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў date semantics Р В Р вЂ  Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРІР‚вЂњ:
  - `issue_date` = auto today,
  - Р В РўвЂР В Р’В°Р РЋРІР‚С™Р В Р’В° Р В Р’В· input Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ `delivery_date`,
  - Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋР РЏ Р Р†Р вЂљРІР‚Сњ `delivery_date = issue_date`,
  - `due_date = issue_date + due_days`.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- email send;
- external lookup / FinStat;
- contract extraction;
- fuzzy matching;
- multi-item UI;
- advanced edit workflow;
- migration framework.

### Follow-up note (QR scope honesty)

- Phase 4 merge Р В Р вЂ¦Р В Р’Вµ Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· QR subsystem.
- Р В РЎСџР В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ QR block Р РЋРЎвЂњ PDF Р В Р вЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РЎВ placeholder-Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ Р В РўвЂР В Р’В»Р РЋР РЏ payment QR.
- Р В РЎвЂєР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ:
  - Р В РўвЂР В РЎвЂўР РЋР С“Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В РЎвЂР РЋРІР‚С™Р В РЎвЂ/Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В¶Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Pay by Square payload generator;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р РЋР Р‰ payload Р РЋРІР‚вЂњР В Р’В· Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВ Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ.

---


## 2026-04-03 Р Р†Р вЂљРІР‚Сњ Session 006 Р Р†Р вЂљРІР‚Сњ PDF Layout Spec (docs-only)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРЎвЂњ docs-only Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р В Р вЂ Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ PDF-Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р’В°.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р В РўвЂР В РЎвЂўР В РЎвЂќР РЋРЎвЂњР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™ `docs/FakturaBot_PDF_Layout_Spec.md`;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў purpose PDF Р РЋР РЏР В РЎвЂќ Р РЋРІР‚РЋР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В РЎвЂ wow-Р В Р’ВµР РЋРІР‚С›Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ;
- Р В РЎвЂўР В РЎвЂ”Р В РЎвЂР РЋР С“Р В Р’В°Р В Р вЂ¦Р В РЎвЂў design principles (clean, restrained, readability-first);
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў color principles Р В Р’В· Р В Р вЂ Р В РЎвЂР В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР РЋР вЂ№ Р В РўвЂР В Р вЂ Р В РЎвЂўР РЋРІР‚В¦ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР РЋРІР‚СњР В РЎВР В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ Р РЋРІР‚С›Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В¦ Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ¦Р РЋРІР‚вЂњР В Р вЂ  Р В Р’В±Р В Р’ВµР В Р’В· Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚С™Р В Р’В°Р В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ;
- Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂўР В РЎвЂќ Р В РЎвЂўР В Р’В±Р В РЎвЂўР В Р вЂ Р Р†Р вЂљРІвЂћСћР РЋР РЏР В Р’В·Р В РЎвЂќР В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В¦ layout-Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР РЋРІР‚вЂњР В Р вЂ :
  header, DodР вЂњР Р‹vateР вЂќРЎвЂў/OdberateР вЂќРЎвЂў, meta/dates, payment, items table, total, QR, footer;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў date semantics Р В РўвЂР В Р’В»Р РЋР РЏ `DР вЂњР Р‹tum vystavenia`, `DР вЂњР Р‹tum dodania`, `DР вЂњР Р‹tum splatnosti`;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў preview/approval rule (`schvР вЂњР Р‹liР вЂўРўС’` / `upraviР вЂўРўС’`);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў typography/spacing guidelines Р РЋРІР‚С™Р В Р’В° Р РЋР С“Р В Р’ВµР В РЎвЂќР РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р Р†Р вЂљРЎС™Do notР Р†Р вЂљРЎСљ.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ Р РЋР С“Р РЋР РЏ PDF generator;
- Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋР вЂ№Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂўР РЋР С“Р РЋР РЏ Р В РЎС›Р В РІР‚вЂќ;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋРІР‚С›Р РЋРІР‚вЂњР РЋРІР‚РЋР РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В Р’В° Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р В РЎВР В РЎвЂ layout specification.

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 004 Р Р†Р вЂљРІР‚Сњ Phase 2: supplier onboarding (chat-based)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding Р В Р’В±Р В Р’ВµР В Р’В· fancy UI, Р В Р’В±Р В Р’ВµР В Р’В· Р РЋР С“Р В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ FSM-Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ,
Р РЋР РЏР В РЎвЂќ Р В Р’В±Р В Р’В°Р В Р’В·Р РЋРЎвЂњ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ invoice phases.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў SQLite schema `supplier` Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В°;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/supplier_service.py` Р В Р’В· Р В РЎвЂўР В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏР В РЎВР В РЎвЂ:
  - create or replace profile,
  - get by `telegram_id`,
  - update profile (Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· upsert);
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/onboarding.py` Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ chat flow:
  12 Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋРІР‚вЂњР В Р вЂ  Р Р†РІР‚В РІР‚в„ў summary Р Р†РІР‚В РІР‚в„ў confirm (`yes/no`) Р Р†РІР‚В РІР‚в„ў save;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў MVP-Р РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р’ВµР В Р вЂ¦Р РЋР Р‰ Р В Р вЂ Р В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РўвЂР В Р’В»Р РЋР РЏ IР вЂќР Р‰O/DIР вЂќР Р‰/IР вЂќР Р‰ DPH/email/IBAN/days_due;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў UX-Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ, Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р РЋРЎвЂњР В Р’В¶Р В Р’Вµ Р РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚Сњ, Р В Р’В· Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚СњР РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋРІР‚С™Р В РЎвЂ flow Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р вЂ¦Р В РЎвЂў.

### Р В РІР‚ВР В Р’ВµР В Р’В·Р В РЎвЂ”Р В Р’ВµР В РЎвЂќР В Р’В° / Р В РЎвЂўР В Р’В±Р В РЎВР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ

- SMTP Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР Р‰ Р В Р вЂ¦Р В Р’Вµ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ;
- Р РЋРЎвЂњ summary Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР Р‰ Р В РЎВР В Р’В°Р РЋР С“Р В РЎвЂќР РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ (`********`);
- Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ SMTP Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР РЏ Р В Р вЂ  Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р РЋРІР‚вЂњ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ plain-text Р РЋРЎвЂњ SQLite (Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂў, Р В РўвЂР В Р’В»Р РЋР РЏ MVP);
- production-grade secure credential storage Р РЋРІР‚В°Р В Р’Вµ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- contact onboarding;
- invoice save flow;
- PDF/email send;
- contract extraction;
- lookup API;
- Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ settings center.

### Р В Р’В Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

Phase 2 Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В° Р РЋРІР‚С™Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р’В° Р В Р вЂ  Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р РЋРІР‚В¦ simple chat-based supplier onboarding.
Fancy UI Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў.
Supplier profile Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ  Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РЎВ persistence-Р РЋРІвЂљВ¬Р В Р’В°Р РЋР вЂљР В РЎвЂўР В РЎВ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ invoice phases.

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 003 Р Р†Р вЂљРІР‚Сњ Phase 1: voice-to-draft preview flow

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ wow-flow: Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“ Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў AI draft preview Р В Р вЂ  Р РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р РЋРІР‚вЂњ.
Р В РІР‚ВР В Р’ВµР В Р’В· save Р В Р вЂ  Р В РІР‚ВР В РІР‚Сњ, Р В Р’В±Р В Р’ВµР В Р’В· PDF, Р В Р’В±Р В Р’ВµР В Р’В· email, Р В Р’В±Р В Р’ВµР В Р’В· supplier/contact persistence.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- `bot/services/speech_to_text.py` Р Р†Р вЂљРІР‚Сњ STT Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· OpenAI Audio API (Whisper)
- `bot/services/llm_invoice_parser.py` Р Р†Р вЂљРІР‚Сњ LLM draft parsing Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· OpenAI Chat API
- `bot/handlers/voice.py` Р Р†Р вЂљРІР‚Сњ voice message handler: download Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў parse Р Р†РІР‚В РІР‚в„ў preview
- `prompts/invoice_draft_prompt.txt` Р Р†Р вЂљРІР‚Сњ Р РЋР С“Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’ВµР В РЎВР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎВР В РЎвЂ”Р РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ Р В РЎвЂР РЋРІР‚С™Р РЋР РЏР В РЎвЂ“Р РЋРЎвЂњ invoice draft
- `bot/config.py` Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `openai_stt_model`, `openai_llm_model`
- `bot/main.py` Р Р†Р вЂљРІР‚Сњ config Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  polling workflow data
- `requirements.txt` Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `openai>=1.30`

### Р В РЎвЂ™Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р РЋРІР‚вЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

- STT Р РЋРІР‚вЂњ LLM parsing Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В Р вЂ Р В Р’В° Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРІР‚вЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р РЋРІР‚вЂњР РЋР С“Р В РЎвЂ, Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В»Р В РЎвЂР РЋРІР‚С™Р РЋРІР‚вЂњ Р В Р вЂ  Р В РЎвЂўР В РўвЂР В РЎвЂР В Р вЂ¦
- Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В РЎвЂ Р В Р вЂ Р В РЎвЂР В РўвЂР В Р’В°Р В Р’В»Р РЋР РЏР РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РЎвЂўР В РўвЂР РЋР вЂљР В Р’В°Р В Р’В·Р РЋРЎвЂњ Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р В РЎвЂўР В Р’В±Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂќР В РЎвЂ (try/finally)
- Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў `OPENAI_API_KEY` Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р Р†Р вЂљРІР‚Сњ app Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂў, voice handler
  Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р В Р’В·Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР В Р’В»Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В±Р В Р’ВµР В Р’В· Р В РЎвЂ”Р В Р’В°Р В РўвЂР РЋРІР‚вЂњР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ
- graceful error handling Р В РўвЂР В Р’В»Р РЋР РЏ STT Р РЋРІР‚вЂњ LLM failure Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂў

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- save draft Р РЋРЎвЂњ Р В РІР‚ВР В РІР‚Сњ
- PDF Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ
- email
- supplier/contact persistence
- contract extraction
- FSM / multi-step dialog

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Phase 2: Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding (chat-based, sequential)

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 002 Р Р†Р вЂљРІР‚Сњ Phase 0 implementation skeleton

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- docs bootstrap Р В Р вЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РЎВ;
- Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ  Phase 0 implementation skeleton;
- Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ deploy Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў;
- Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р Р†Р вЂљРІР‚Сњ Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В Р’В»Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ runnable Р В РЎвЂќР В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р РЋР С“ Р В Р’В±Р В Р’ВµР В Р’В· feature-Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР РЋРЎвЂњ `bot/`, `prompts/`, `storage/`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `config.py` Р В Р’В· Р РЋРІР‚РЋР В РЎвЂР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ `.env`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў SQLite bootstrap Р В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂќР В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂ№ Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р В Р’ВµР РЋР вЂ№ `supplier`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `/start` handler Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р В РЎвЂќ aiogram polling;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `.env.example`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ voice / Whisper / LLM draft / PDF / email / contract extraction;
- Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ Р РЋР С“Р РЋР РЏ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ deploy;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ internet lookup, SaaS/multi-tenant Р В Р’В°Р В Р’В±Р В РЎвЂў Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІвЂљВ¬Р РЋРІР‚вЂњ Р В РЎВР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В Р’В° Phase 0.

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р Р†Р вЂљРІР‚Сњ Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ voice/draft flow;
- Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р Р†Р вЂљРІР‚Сњ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ onboarding Р РЋРІР‚С™Р В Р’В° contacts Р РЋРЎвЂњ chat-based Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р’В»Р РЋРІР‚вЂњ.

---

## 2026-03-30 Р Р†Р вЂљРІР‚Сњ Session 001 Р Р†Р вЂљРІР‚Сњ Р В РЎв„ўР В РЎвЂўР В Р вЂ¦Р РЋРІР‚В Р В Р’ВµР В РЎвЂ”Р РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р В РЎСџР В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚В Р РЋРІР‚вЂњР В Р вЂ¦Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎВР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ SaaS Р В Р вЂ¦Р В Р’В° Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРІР‚вЂњ Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В РЎвЂР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂў.
- Р В РЎСџР В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р РЋР С“ Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР С“Р В Р’В°Р В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р’В°.
- FakturaBot Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В Р’В»Р РЋР РЏР В РўвЂР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В Р’В° Р В РўвЂР В Р’ВµР В РЎВР В РЎвЂўР В Р вЂ¦Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р РЋРІР‚вЂњР РЋРІР‚С™Р РЋР вЂљР В РЎвЂР В Р вЂ¦Р В Р’В°.
- Р В РЎСџР РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ Р РЋРІР‚РЋР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В Р’В° Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚вЂќ Р В РЎВР В РЎвЂўР В РўвЂР В Р’ВµР В Р’В»Р РЋРІР‚вЂњ:
  Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р РЋРІР‚вЂњР В Р вЂ  Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р В Р’В·Р В Р’В°Р В РўвЂР В Р’В°Р РЋРІР‚РЋР РЋРІР‚вЂњ Р В РЎВР В Р’В°Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В±Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРЎвЂњ.

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР В РЎвЂР РЋРІР‚С™Р РЋР Р‰ Р РЋРЎвЂњ MVP v1.0

- Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™
- Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР В РІвЂћвЂ“
- Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР В РІвЂћвЂ“
- Whisper STT
- AI invoice draft
- Р РЋР вЂљР РЋРЎвЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding
- Р РЋР вЂљР РЋРЎвЂњР РЋРІР‚РЋР В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В°
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В° Р В Р’В· Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРЎвЂњ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· AI
- Р В Р’В»Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В Р’В°Р В РўвЂР РЋР вЂљР В Р’ВµР РЋР С“Р В Р вЂ¦Р В Р’В° Р В РЎвЂќР В Р вЂ¦Р В РЎвЂР В РЎвЂ“Р В Р’В°
- Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂўР РЋР вЂљР В РЎвЂР В РЎвЂ“Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋРЎвЂњ Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРЎвЂњ
- PDF-Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р’В°
- QR Pay by Square
- email-Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В РЎвЂќР В Р’В°
- Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљ

## 2026-07-31 - FakturaBot test taxonomy and consolidation Phase 1

- Started from origin/main
  4a69b312226b7c4254427f3c3c1b0a99243647c8 in an isolated worktree and
  carried forward the approved audit baseline.
- Registered the eleven audit-defined pytest markers and documented focused,
  adjacent, full-suite, integration, acceptance, external opt-in, and server
  smoke tiers. Marker coverage remains intentionally partial.
- Parametrized only the approved high-confidence Pay by Square,
  service-normalization, work-time routing, contact normalization, invoice
  analytics, and customization-admin scenarios with stable IDs.
- Moved three literal Google Drive Product Truth copies to one canonical test
  in tests/test_product_truth.py. Product Truth values and production code did
  not change.
- Centralized ten equivalent Google/network import-boundary checks while
  retaining every module-specific forbidden set and the archive-worker
  required token. Independent parser, callback, phrase-dictionary, and
  side-effect source contracts remain separate.
- Collection changed from 2,433 to 2,431 only because three literal duplicate
  nodes became one; 2,431 unique logical protections remain.
- Validation: changed-file focused set 431 passed; adjacent sets 949 passed
  and 210 passed plus 7 subtests; final collection 2,431; full suite 2,431
  passed plus 7 subtests in 490.10s.
- Delivery-date parametrization and legacy service-account retirement remain
  deferred. No CI, dependency, schema, runtime, server, deploy, restart, or
  production-data change was made.
- Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“Р В РЎвЂ
- SQLite
- Docker deploy

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў

- lookup Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р РЋРІР‚вЂњР В Р вЂ  Р В Р’В· Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™Р РЋРЎвЂњ
- FinStat
- ORSR Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ
- Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ OCR pipeline
- Google Drive
- billing
- multi-tenant Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р’В°
- Р В РЎвЂќР В Р’В°Р В Р’В±Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’В°

### Р В РЎв„ўР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂ”Р В РЎвЂў AI

- AI Р В Р вЂ¦Р В Р’Вµ Р РЋРІР‚Сњ Р В РўвЂР В Р’В¶Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В»Р В РЎвЂўР В РЎВ Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В РЎвЂ.
- Р В Р в‚¬Р РЋР С“Р РЋРІР‚вЂњ Р В РЎвЂќР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р РЋРІР‚вЂњ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋР вЂ№Р РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· draft + validation + confirmation.
- Р В РІР‚СњР В Р’В»Р РЋР РЏ Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР В Р вЂ  Р В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎВР В РЎвЂўР В РўвЂР В Р’ВµР В Р’В»Р РЋР Р‰:
  Python orchestrates Р Р†РІР‚В РІР‚в„ў AI extracts Р Р†РІР‚В РІР‚в„ў Python validates Р Р†РІР‚В РІР‚в„ў user confirms.
- AI Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РўвЂР В РЎвЂР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р В Р’В° Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В РЎвЂР РЋРІР‚В¦ Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ  Р РЋР вЂљР В РЎвЂўР В Р’В±Р РЋРІР‚вЂњР РЋРІР‚С™.

### Р В РЎСџР РЋР вЂљР В РЎвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР РЋР вЂ№

Р В РІР‚СљР В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ input Р РЋРІР‚С™Р В РЎвЂР В РЎвЂ”Р РЋРЎвЂњ:
Р Р†Р вЂљРЎС™Р В РЎС›Р В Р’ВµР РЋР С“Р В Р’В»Р В Р’В° Р В Р Р‹Р В Р’В»Р В РЎвЂўР В Р вЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚вЂњР РЋР РЏ Р В Р’В·Р В Р’В° Р В РЎвЂўР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В РЎвЂ Р В РЎвЂўР В РўвЂР В РЎвЂР В Р вЂ¦ Р В РЎвЂќР РЋРЎвЂњР РЋР С“ Р РЋРІР‚С™Р В Р’В°Р В РЎВ 2000 Р РЋРІР‚СњР В Р вЂ Р РЋР вЂљ, Р В РўвЂР В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР В РЎВ Р В Р вЂ Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ 30 Р В РЎВР В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В Р’В° 2026, Р РЋР С“Р В РЎвЂ”Р В Р’В»Р В Р’В°Р РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™ 30 Р В РўвЂР В Р вЂ¦Р РЋРІР‚вЂњР В Р вЂ Р Р†Р вЂљРЎСљ

Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋР вЂ№Р В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋР С“Р РЋР Р‰ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРЎвЂњ invoice draft-Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™Р В РЎвЂќР РЋРЎвЂњ.

### Р В РІР‚в„ўР В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р В Р’В° Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В° Р РЋРІР‚вЂњР В РўвЂР В Р’ВµР РЋР РЏ

FakturaBot Р Р†Р вЂљРІР‚Сњ Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р В Р’В±Р В РЎвЂўР РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљ.
Р В Р’В¦Р В Р’Вµ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂ Р В РЎвЂќР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В Р’В° Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В Р’В±Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’ВµР РЋР С“-Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚В Р В Р’ВµР РЋР С“.

### Р В РІР‚СњР В РЎвЂўР В РЎвЂќР РЋРЎвЂњР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В РЎвЂ

Р В РЎвЂ™Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎС›Р В РІР‚вЂќ:
`docs/TZ_FakturaBot.md`

### Р В РЎСљР В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р РЋРІР‚вЂњ Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќР В РЎвЂ

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР РЋРЎвЂњ Р РЋР вЂљР В Р’ВµР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР РЋР вЂ№
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ README
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ AGENTS
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ CHANGELOG
- Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎС›Р В РІР‚вЂќ Р РЋРЎвЂњ docs
- Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂќР В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р РЋР С“ MVP

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 003 Р Р†Р вЂљРІР‚Сњ Phase 1 voice-to-draft preview

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Phase 1 Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ¦Р В Р’Вµ Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РІвЂћвЂ“ voice Р Р†РІР‚В РІР‚в„ў text smoke test, Р В Р’В° Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ wow-flow:
  **voice Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў AI draft preview**
- Р В РЎСљР В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р РЋРІР‚вЂњ Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В РЎВР В РЎвЂў:
  - save Р РЋРЎвЂњ Р В РІР‚ВР В РІР‚Сњ
  - PDF
  - email
  - supplier/contact persistence
- STT Р РЋРІР‚вЂњ LLM parsing Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РўвЂР РЋРІР‚вЂњР В Р’В»Р В Р’ВµР В Р вЂ¦Р РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’В° Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРІР‚вЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р РЋРІР‚вЂњР РЋР С“Р В РЎвЂ.
- Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚вЂњ API Р В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  repo; Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ `.env`.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР РЋРІР‚С™Р РЋР вЂљР В РЎвЂР В РЎВР В РЎвЂќР РЋРЎвЂњ `OPENAI_STT_MODEL` Р РЋРІР‚вЂњ `OPENAI_LLM_MODEL` Р РЋРЎвЂњ config;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/speech_to_text.py`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/llm_invoice_parser.py`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў prompt `prompts/invoice_draft_prompt.txt`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/voice.py`;
- Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В РЎвЂў voice router;
- Phase 1 flow Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ:
  Telegram voice Р Р†РІР‚В РІР‚в„ў local temp file Р Р†РІР‚В РІР‚в„ў OpenAI transcription Р Р†РІР‚В РІР‚в„ў OpenAI draft parsing Р Р†РІР‚В РІР‚в„ў preview in chat.

### Р В РІР‚в„ўР В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р РЋРІР‚вЂњ Р В РўвЂР РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњ / Р РЋРЎвЂњР РЋР вЂљР В РЎвЂўР В РЎвЂќР В РЎвЂ

- Р В РЎСљР В Р’В° Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР РЋР РЏР РЋРІР‚С™Р В РЎвЂ, Р РЋРІР‚В°Р В РЎвЂў `.env` Р В Р вЂ Р В Р вЂ¦Р В Р’ВµР РЋР С“Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРЎвЂњ `.gitignore`.
- Р В РЎвЂєР В РўвЂР В РЎвЂР В Р вЂ¦ `OPENAI_API_KEY` Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚вЂњ Р В РўвЂР В Р’В»Р РЋР РЏ STT, Р РЋРІР‚вЂњ Р В РўвЂР В Р’В»Р РЋР РЏ LLM parsing.
- Р В РЎСџР В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ voice-flow Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ”Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™, Р В Р’В° Р РЋР С“Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В Р’В±Р РЋРЎвЂњ Р В Р’В·Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋРІР‚С™Р В РЎвЂ Р В Р вЂ¦Р В Р’В°Р В РЎВР РЋРІР‚вЂњР РЋР вЂљ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’В°.
- Preview Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂќР РЋР вЂљР В РЎвЂР В Р вЂ Р РЋРІР‚вЂњ Р В Р’В·Р В Р вЂ¦Р В Р’В°Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р В РЎвЂР В РЎвЂ”Р РЋРЎвЂњ `Р Р†Р вЂљРІР‚Сњ Р Р†Р вЂљРІР‚Сњ`; Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В РЎвЂўР В РўвЂР РЋР вЂљР В Р’В°Р В Р’В·Р РЋРЎвЂњ Р РЋРІР‚РЋР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ.
- Р В Р вЂЎР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў STT Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ  Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР В РЎвЂўР В Р’В¶Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™, Р В Р вЂ¦Р В Р’Вµ Р В РЎВР В РЎвЂўР В Р’В¶Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР РЋРІР‚С™Р В РЎвЂ Р В РІвЂћвЂ“Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ  LLM Р Р†Р вЂљРІР‚Сњ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В Р’В·Р РЋРЎвЂњР В РЎвЂ”Р В РЎвЂР В Р вЂ¦Р РЋР РЏР РЋРІР‚С™Р В РЎвЂ flow Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’Вµ.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ supplier onboarding, contacts, PDF, email, contract extraction;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В°Р РЋР С“Р РЋР Р‰ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В Р’В° save draft;
- Р В Р вЂ¦Р В Р’Вµ Р В Р’В±Р РЋРЎвЂњР В Р’В»Р В РЎвЂў Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў deploy;
- internet lookup / FinStat Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР РЋР РЏР РЋРІР‚С™Р РЋР Р‰ Р РЋРЎвЂњ Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ flow.

### Р В Р Р‹Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ

Phase 1 Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р’В° Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРЎвЂњ.
Р В РІР‚вЂњР В РЎвЂР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ runtime test Р В Р’В· Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВ `BOT_TOKEN` Р РЋРІР‚вЂњ `OPENAI_API_KEY` Р РЋРІР‚В°Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р’ВµР В Р вЂ¦.

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Phase 2 Р Р†Р вЂљРІР‚Сњ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding Р РЋРЎвЂњ chat-based Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р’В»Р РЋРІР‚вЂњ;
- Р В Р’В±Р В Р’ВµР В Р’В· fancy UI;
- Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰: Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂ“Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В°, Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎВР В Р’В°Р В РІвЂћвЂ“Р В Р’В±Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚В¦ invoice flows.
## 2026-04-01 - Session 005 - Phase 3: manual contact creation

### Goal
Implement minimal manual customer contact creation required for next invoice phases.

### Implemented
- SQLite bootstrap extended with `contact` table (fail-loud compatibility check, no auto-drop/migrations).
- Added `bot/services/contact_service.py` with repository-style operations:
  - `ContactProfile`
  - `get_all_by_supplier(telegram_id)`
  - `get_by_name(telegram_id, name)`
  - `create_contact(...)`
  - `create_or_replace(...)`
- Implemented `bot/handlers/contacts.py` as a simple chat-based flow:
  1. company name
  2. ICO
  3. DIC
  4. optional IC DPH (`-`)
  5. address
  6. email
  7. optional contact person (`-`)
  8. summary
  9. confirm `yes`/`no`
  10. save
- Added exact-name duplicate check per supplier; existing name is warned and confirmed overwrite saves via upsert.
- Added supplier-profile guard: contact flow is blocked until `/supplier` onboarding is completed.

### Explicitly not included in this phase
- contract-based contact extraction
- contact search UI
- invoice save flow
- PDF generation
- email send
- external lookup API / FinStat
- complex dedup/fuzzy matching

### Decision
Phase 3 remains intentionally simple and chat-based; contract extraction and external lookup stay deferred to later phases.

### Follow-up note (language consistency)
- Text confirmation in supplier onboarding aligned to Slovak: `ano / nie` instead of `yes / no`.
- Text confirmation in manual contact flow aligned to Slovak: `ano / nie` instead of `yes / no`.
- User-facing language consistency improved across `/start`, voice preview, supplier onboarding, and manual contact flow.
- Why this matters:
  - bot is oriented to a Slovak interface;
  - mixed-language confirmations create product inconsistency;
  - language consistency is better fixed early while flows are still small.
## 2026-04-03 - Session 006 - Research spike: real PAY by square integration path

### Goal
Р В РЎСџР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ technical research spike Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ PAY by square QR Р РЋРЎвЂњ FakturaBot Р В Р’В±Р В Р’ВµР В Р’В· blind implementation.

### Implemented
- Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ research artifact: `docs/PayBySquare_Research_Spike.md`.
- Р В РІР‚вЂќР РЋРІР‚вЂњР В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С™Р В Р’В° Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р вЂ¦Р РЋР РЏР В Р вЂ¦Р В РЎвЂў Р В РўвЂР В Р’В¶Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В»Р В Р’В°:
  - Р В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’В° Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ PAY by square 1.2.0,
  - by square API docs,
  - Python package `pay-by-square`,
  - Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ non-Python implementation repos (TS/Go/PHP) Р РЋР РЏР В РЎвЂќ Р РЋР вЂљР В Р’ВµР РЋРІР‚С›Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ¦Р РЋР С“Р В РЎвЂ.
- Р В РІР‚вЂќР В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В Р вЂ Р В Р’ВµР РЋР вЂљР В РўвЂР В РЎвЂР В РЎвЂќР РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ repo:
  - Р РЋР вЂљР В Р’ВµР В РЎвЂќР В РЎвЂўР В РЎВР В Р’ВµР В Р вЂ¦Р В РўвЂР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІвЂљВ¬Р В Р’В»Р РЋР РЏР РЋРІР‚В¦: Р В Р вЂ Р В Р’В»Р В Р’В°Р РЋР С“Р В Р вЂ¦Р В Р’В° Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Python-Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ payload encoder (spec-driven),
  - Р В Р’В±Р В Р’ВµР В Р’В· Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В·Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р вЂ¦Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў SaaS Р РЋР РЏР В РЎвЂќ Р В РЎвЂќР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р В Р’В·Р В Р’В°Р В Р’В»Р В Р’ВµР В Р’В¶Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р РЋРІР‚вЂњ,
  - Р В Р’В±Р В Р’ВµР В Р’В· cross-runtime Р В Р’В°Р В РўвЂР В Р’В°Р В РЎвЂ”Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В Р’В° Р РЋР РЏР В РЎвЂќ Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋРІвЂљВ¬Р В Р’В»Р РЋР РЏР РЋРІР‚В¦Р РЋРЎвЂњ.
- Р В РІР‚вЂќР В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ required payload Р РЋРІР‚вЂњ field constraints Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.
- Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў implementation recommendation Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎВР В Р’В°Р В РІвЂћвЂ“Р В Р’В±Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂў PR (Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ runtime Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ Р РЋРЎвЂњ Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋР С“Р В Р’ВµР РЋР С“Р РЋРІР‚вЂњР РЋРІР‚вЂќ).

### Explicitly not included in this session
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ Р РЋРЎвЂњ `bot/services/pdf_generator.py`.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ production integration patch Р В РўвЂР В Р’В»Р РЋР РЏ PAY by square.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ scope Р В Р вЂ¦Р В Р’В° email / external bank API / Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІвЂљВ¬Р РЋРІР‚вЂњ Р В РЎВР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р РЋРІР‚вЂњ.

### Decision
Р В Р Р‹Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂќР РЋРЎвЂњ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р РЋРЎвЂњР РЋРІР‚СњР В РЎВР В РЎвЂў research + decision record, Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р РЋРІР‚РЋР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РЎВ PR Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В РЎВР В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРЎвЂњ production Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў PAY by square payload Р РЋРЎвЂњ PDF flow.


## 2026-04-03 - Session 007 - Implementation: real PAY by square payload in PDF flow

### Goal
Р В РІР‚вЂќР В Р’В°Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ QR placeholder Р РЋРЎвЂњ Phase 4 Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ PAY by square payload generator Р В РўвЂР В Р’В»Р РЋР РЏ invoice payment use case.

### Implemented
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/pay_by_square.py` Р В Р’В· internal spec-driven encoder pipeline:
  1) mapping paymentorder Р В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦,
  2) CRC32,
  3) LZMA raw compression (LZMA1),
  4) header/length prepend,
  5) Base32hex payload output.
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў strict validation: IBAN, amount, currency, VS, due date, beneficiary name (fail-loud Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· `PayBySquareValidationError`).
- `bot/services/pdf_generator.py` Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р’В· placeholder Р РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂќР В Р’В° `PAYBYSQUARE|...` Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р В РЎвЂР В РЎвЂќР В Р’В»Р В РЎвЂР В РЎвЂќ `build_pay_by_square_payload(...)`.
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў unit tests:
  - deterministic payload vector,
  - validation failures,
  - PDF integration smoke (QR payload looks encoded and PDF still written).
- Р В РЎвЂєР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў `README.md`, `docs/TZ_FakturaBot.md`, `CHANGELOG.md` Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР С“Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“Р РЋРЎвЂњ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.

### Explicitly not included
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ external SaaS generation path.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Node/Go/PHP sidecar adaptation.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ email/bank API scope expansion.

### Manual verification status
- Р В Р в‚¬ Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂўР В РЎВР РЋРЎвЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂР В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В°Р РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В°Р РЋР С“Р РЋР Р‰ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В° Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ QR Р В Р’В±Р В Р’В°Р В Р вЂ¦Р В РЎвЂќР РЋРІР‚вЂњР В Р вЂ Р РЋР С“Р РЋР Р‰Р В РЎвЂќР В РЎвЂР В РЎВР В РЎвЂ Р В РЎВР В РЎвЂўР В Р’В±Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВР В РЎвЂ Р В Р’В°Р В РЎвЂ”Р В РЎвЂќР В Р’В°Р В РЎВР В РЎвЂ.
- Р В РЎСџР РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ deploy Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В Р’В° manual verification Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ SK banking clients.
### Follow-up note (Р РЋР С“Р В Р’ВµР В РЎВР В Р’В°Р В Р вЂ¦Р РЋРІР‚С™Р В РЎвЂР В РЎвЂќР В Р’В° Р В РўвЂР В Р’В°Р РЋРІР‚С™ Р РЋРЎвЂњ faktР вЂњРЎвЂќre)
- Р В РЎСџР В Р’В»Р РЋРЎвЂњР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В Р вЂ¦Р РЋРЎвЂњ Р В РЎВР РЋРІР‚вЂњР В Р’В¶ `DР вЂњР Р‹tum vystavenia` Р РЋРІР‚вЂњ `DР вЂњР Р‹tum dodania` Р РЋРЎвЂњ Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р РЋРЎвЂњР РЋР С“Р РЋРЎвЂњР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂў.
- Р В РІР‚СњР В Р’В°Р РЋРІР‚С™Р В Р’В°, Р В Р вЂ Р В РЎвЂќР В Р’В°Р В Р’В·Р В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’ВµР В РЎВ Р РЋРЎвЂњ voice/text input, Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎвЂ”Р РЋР вЂљР В Р’ВµР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ `DР вЂњР Р‹tum dodania`.
- `DР вЂњР Р‹tum vystavenia` Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’В¶Р В РўвЂР В РЎвЂ Р В Р вЂ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р РЋР вЂ№Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В РЎВ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў Р В Р вЂ  Р В РЎВР В РЎвЂўР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™ Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ.

## 2026-04-03 - Session 008 - Verification support: PAY by square manual scan checklist

### Goal
Prepare a local verification-task plan for manual validation of the real PAY by square QR after merge, without runtime code changes.

### Implemented
- Added a short verification artifact: `docs/PayBySquare_Manual_Verification_Checklist.md`.
- Documented the local verification flow:
  - how to generate a PDF invoice locally;
  - where to find the generated PDF;
  - which fields must be checked after scanning in a banking app.
- Added expected outcomes:
  - success,
  - partial success,
  - fail.
- Added a short record checklist for the post-test note so follow-up patch decisions are explicit.

### Explicitly not included
- No runtime code changes.
- No new feature work.
- No email flow changes.
- No Phase 5 work.

### Decision
Before PAY by square production sign-off, a separate manual scan verification in a real banking mobile app must be completed and recorded in `PROJECT_LOG.md`.



## 2026-04-06 - Session 009 - Local env support for FakturaBot

### Goal
Allow FakturaBot to run locally from a dedicated local-only env file without breaking existing `.env`-based startup.

### Implemented
- `bot/config.py` now loads a dedicated local-only env file first when it exists.
- If that local-only env file is absent, startup falls back to `.env`.
- Added a dedicated repo-root local env file with empty/default placeholders only.
- Added that local env file to `.gitignore` while keeping `.env` ignore intact.

### Explicitly not included
- No config field renames.
- No secret values.
- No runtime behavior changes beyond env-file selection.
- `.env.example` left unchanged.

### Decision
Local FakturaBot setup now supports a dedicated non-committed local env file while preserving `.env` compatibility.

## 2026-04-08 - Session 010 - Docs ownership split: Implementation Plan vs LLM Contract

### Goal
Remove overlap risk between planning and contract docs by clarifying document ownership.

### Implemented
- `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` kept as rollout document (phase scope/order/risks/acceptance) and Phase 2 detail reduced to planning-level with explicit reference to LLM contract.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md` marked as detailed Phase 2 AI contract and cross-referenced back to the implementation plan for sequencing.
- `README.md` docs structure updated with concise role distinction for both docs.

### Scope
- Docs-only clarification; no code changes.

## 2026-04-08 - Session 011 - Phase 1 implementation: deterministic contact lookup + service-term canonicalization

### Goal
Implement Phase 1 Python-side canonicalization only (no AI/orchestrator changes).

### Implemented
- Added deterministic contact lookup normalization in `ContactService` with structured states:
  - `exact_match`, `normalized_match`, `multiple_candidates`, `no_match`.
- Added lookup-only company normalization for case/punctuation/separator/legal-form variants.
- Added conservative legal-form support (token-boundary):
  - `s.r.o.` variants (`sro`, `s r o`, `s. r. o.`),
  - `a.s.` variants (`as`, `a s`),
  - conservative `spol` + `sro` / `s r o` tail variants.
- Integrated invoice flow with lookup-state branching:
  - continue on exact/normalized,
  - explicit fail-loud message on multiple candidates,
  - explicit non-assumptive guidance on no match (retry or `/contact`, no auto-create).
- Added deterministic internal service-term normalizer:
  - `opravy -> oprava`, `ремонт -> oprava`, `монтаж -> montáž`.
- Kept alias precedence unchanged: supplier alias mapping remains source of truth for final preview/PDF title.

### Tests
- Added `tests/test_contact_lookup_normalization.py`.
- Added `tests/test_service_term_normalizer.py`.
- Added `tests/test_invoice_contact_lookup_feedback.py`.
- Full test suite passes with `PYTHONPATH=. pytest -q`.

### Scope
- No DB migration.
- No LLM/prompt/orchestrator schema changes.

## 2026-04-08 - Session 012 - Test runner expectation clarified (pytest)

### Goal
Remove ambiguity between legacy unittest habits and current pytest workflow.

### Implemented
- Added explicit test-runner note in `README.md`:
  - canonical runner is `pytest`,
  - command: `PYTHONPATH=. pytest -q`,
  - unittest is not the default expected workflow.
- Added minimal `pytest.ini` with `testpaths = tests` as repo tooling baseline.

### Scope
- Docs/tooling only; no runtime code changes.
---

## 2026-04-06 - Session 013 - Windows-safe SQLite connection closing in tests

### Goal
Eliminate Windows test-suite failures during `TemporaryDirectory` cleanup by ensuring SQLite connections are explicitly closed after each DB access path.

### Implemented
- Added `managed_connection(...)` in `bot/services/db.py` to guarantee `connection.close()` in `finally`.
- Switched SQLite usage in `bot/services/supplier_service.py`, `bot/services/service_alias_service.py`, `bot/services/invoice_service.py`, `bot/services/contact_service.py`, and DB bootstrap in `bot/services/db.py` from direct `sqlite3.connect(...)` context usage to the shared managed helper.
- Preserved existing transaction behavior (`commit()` remains where it already existed).
- Preserved `row_factory = sqlite3.Row` behavior on read paths.
- Verified with `python -m unittest discover -s tests -p "test_*.py" -v`: 18 tests passed on Windows, including the previously affected temp SQLite DB cleanup paths.

### Explicitly not included
- No schema changes.
- No business logic changes.
- No test behavior changes beyond the connection lifecycle fix.

### Decision
SQLite connection lifetime in services/bootstrap is now treated as an explicit resource lifecycle concern, not only a transaction context concern, to remain Windows-safe for temporary DB files.

---

## 2026-04-06 - Session 014 - PDF Slovak glyph completion (ľ, ť)

### Goal
Finish PDF glyph coverage for the remaining Slovak characters (`ľ`, `ť`) without changing the existing layout.

### Implemented
- Confirmed that bundled ReportLab `Vera.ttf` / `VeraBd.ttf` do not contain `ľ` and `ť`.
- Updated `bot/services/pdf_generator.py` to resolve a Unicode-capable font pair from installed Windows fonts first (`arial.ttf` / `arialbd.ttf`, with fallbacks), and only use a fallback font if it actually covers the required Slovak glyphs.
- Normalized visible Slovak PDF literals in `bot/services/pdf_generator.py` to proper Unicode text so headers and labels render correctly with the selected font.
- Added a regression test to verify the selected regular and bold PDF fonts cover `ľ` and `ť`, while keeping existing wrapping/layout tests intact.
- Re-verified the full test suite after the font-selection change.

### Explicitly not included
- No layout redesign.
- No payment block or table layout refactor.
- No schema or business logic changes.

### Decision
PDF rendering now depends on an explicitly validated Unicode font path instead of assuming bundled ReportLab Vera fonts are sufficient for Slovak invoice text.

---

## 2026-04-07 - Session 015 - Manual PAY by square banking-app verification passed for one local FakturaBot flow

### Goal
Record the completed local end-to-end FakturaBot verification session for the currently tested PAY by square PDF flow.

### Verified
- Local supplier -> contact -> invoice flow completed successfully.
- A PDF invoice artifact was generated successfully and reviewed.
- Latest local generated PDF artifact was present in the local invoice output area at the time of verification (timestamp observed locally before this log update: 2026-04-07 18:45).
- The PAY by square QR from the tested PDF was scanned successfully in a real banking mobile app.
- Manual user confirmation states the bank-app recipient account data matched the expected recipient account data.
- Manual user confirmation states the amount was populated correctly.
- Manual user confirmation states the due date (`datum splatnosti`) was populated correctly.

### Scope note
- This log entry records one successful real local end-to-end verification case for the currently tested FakturaBot flow.
- This closes the previously pending manual scan verification milestone for that tested flow.
- This does not claim universal compatibility across all banking apps or full production sign-off.

### Decision
The PAY by square PDF flow now has at least one recorded successful real banking-app verification milestone in addition to local code/test validation.


## 2026-04-10 — Session 016 — Service naming terminology audit + safe refactor

### Goal
Align service naming wording in `/service` and related code to user-friendly Slovak and consistent internal English names.

### Audit findings
- User-facing texts still used technical wording `alias` / `canonical názov` in `/service` flow and README.
- Internal Python naming mixed old terms (`alias`, `canonical_title`, `item_name_final`) with business semantics.
- Persistence schema used `supplier_service_alias(alias, canonical_title)` and related bootstrap checks.
- Tests reflected old naming (`test_alias_resolution_*`, `entry.alias`).

### What changed
- User-facing Slovak wording in `/service` and invoice preview now uses:
  - `krátky názov služby`
  - `plný názov služby`
- Internal naming in service/handlers moved to:
  - `service_short_name`
  - `service_display_name`
- Service layer added explicit method `resolve_service_display_name(...)`; kept compatibility wrapper `resolve_alias(...)`.
- README `/service` command description updated to new wording.
- Tests renamed/updated to new internal naming.

### Compatibility / DB
- DB schema intentionally left unchanged (`alias`, `canonical_title` stay as storage columns in `supplier_service_alias`).
- No migration introduced.

## 2026-04-10 — Session 013 — Phase 2 minimal AI layer (invoice draft only)

### Goal
- Added minimal Phase 2 AI entrypoint for invoice draft flow only.
- LLM now returns Slovak-facing business payload (`vstup`, `zamer`, `biznis_sk`, `stopa`) and Python continues deterministic truth flow.

### What changed
- Updated `prompts/invoice_draft_prompt.txt` to require strict JSON payload for Phase 2 invoice-only schema.
- Reworked `bot/services/llm_invoice_parser.py`:
  - added strict payload validator `validate_invoice_phase2_payload(...)`;
  - added explicit error `LlmInvoicePayloadError` for malformed payload;
  - added `parse_invoice_phase2_payload(...)` that fails loud on shape violations.
- Updated `bot/handlers/invoice.py`:
  - integrated new parser path before deterministic preview flow;
  - mapped Phase 2 `biznis_sk` into existing Python invoice draft fields;
  - preserved original text from `vstup.povodny_text` in preview context;
  - added clear retry message when AI payload is invalid or key fields are missing.
- Added `tests/test_invoice_phase2_ai_layer.py` covering:
  - multilingual/mixed payload validation path,
  - original text preservation,
  - malformed payload handling,
  - preview flow still using Python truth for contact lookup and service display mapping,
  - missing amount handling with clean retry message.

### Notes
- Scope is intentionally invoice-flow only (no contact onboarding redesign, no supplier/document AI expansion).
- No DB migration required.

## 2026-04-10 — Session 017 — Temporary structured debug transparency for voice → STT → Phase 2 invoice flow

### Goal
- Add temporary, env-flagged structured debug trace to identify where customer name is lost/corrupted across STT, validated LLM payload, and deterministic Python contact lookup.

### What changed
- Added `DEBUG_INVOICE_TRANSPARENCY` config flag in `bot/config.py` (default off).
- Added JSON debug event in voice handler after successful STT with:
  - `request_id`
  - `telegram_update_id`
  - `telegram_message_id`
  - `stt_text`
- Added JSON debug event in invoice flow right after validated Phase 2 payload with:
  - `vstup.povodny_text`
  - `biznis_sk.odberatel_kandidat`
  - `biznis_sk.polozka_povodna`
  - `biznis_sk.termin_sluzby_sk`
- Added JSON debug events around deterministic contact lookup:
  - before lookup (`lookup_raw_input`, `lookup_normalized_input`),
  - after lookup (`lookup_state`, `matched_contact_id`, and candidate metadata when multiple matches).
- Added JSON debug event before preview/save handoff with final resolved contact and service title fields.
- `request_id` is propagated across voice STT → Phase 2 parse → lookup → preview path.

### Safety / constraints
- No business logic, fallback behavior, or contact auto-fix/auto-create behavior changed.
- Lookup debug normalization reuses existing `ContactService.normalize_lookup_forms(...)` (no duplicate debug-only normalization logic).

## 2026-04-10 — Session 018 — Phase 2 odberateľ candidate contract hardening

### Goal
- Harden invoice Phase 2 AI contract so `biznis_sk.odberatel_kandidat` is canonical, lookup-ready, and fail-loud if raw/noisy fragments leak from multilingual voice/STT input.

### What changed
- Prompt (`prompts/invoice_draft_prompt.txt`) now explicitly requires lookup-ready canonical candidate in `biznis_sk.odberatel_kandidat`:
  - disallows cyrillic/raw inflected fragments and preposition/filler phrases,
  - keeps original multilingual input only in `vstup.povodny_text`,
  - allows raw extraction notes only in trace (`stopa`),
  - adds multilingual voice-like examples (RU/mixed, s.r.o./sro, imperfect STT).
- Validator (`bot/services/llm_invoice_parser.py`) now fail-loud rejects non lookup-ready candidates:
  - empty/whitespace values,
  - obvious raw phrase fragments (`на техкомпании`, `для компании`, `pre firmu`, `kompanii`),
  - cyrillic-only values,
  - preposition-start and too noisy candidates for deterministic lookup.
- Tests (`tests/test_invoice_phase2_ai_layer.py`) extended for:
  - rejection of Cyrillic/raw candidate variants,
  - acceptance of valid Latin/Slovak lookup-ready candidate,
  - preservation of original multilingual text in `vstup.povodny_text`.

### Notes
- No DB migrations, no contact auto-create, no fuzzy matching.
- Existing Python source-of-truth preview/contact flow remains unchanged for valid payloads.

## 2026-04-11 — Session 014 — Invoice Phase 2 regression fixes (amount semantics + SK text boundary + PDF row alignment)

### Bug shape
- Voice/text phrases with multiplier semantics (e.g. `2 razy po 1500`) could be persisted as `quantity=2`, `total=1500`, causing wrong unit price derivation in PDF.
- `biznis_sk` service short text could still contain raw Cyrillic (`ремонт`) and leak into preview short title.
- PDF item rows with wrapped descriptions looked visually split because numeric columns sat too high relative to multiline description blocks.

### Root cause
- Amount pipeline had only one numeric `suma` path and derived `unit_price` as `total/quantity` without deterministic multiplier normalization.
- Invoice preview trusted `polozka_povodna` too directly, so multilingual/raw text could pass through instead of canonical Slovak term.
- Item-row vertical baseline used a static offset tuned for single-line rows.

### Decision
- Add optional invoice-only payload field `biznis_sk.cena_za_jednotku`, keep Python as numeric source of truth, and enforce deterministic normalization for `N × unit-price` phrases.
- Make preview short title prefer Slovak-normalized term (`termin_sluzby_sk` / deterministic canonical map), with fail-loud validation when `biznis_sk` text fields contain Cyrillic.
- Keep PDF design unchanged and fix only row measurement + numeric baseline helper logic for wrapped rows.

### Tests added/updated
- Amount semantics tests for:
  - `2 razy po 1500`
  - `2 kusy po 1500 eur`
  - `2x 1500`
  - `2 krát po 1500 eur`
  and fail-loud path for ambiguous multiplier hints.
- Service text normalization tests proving `biznis_sk` Cyrillic rejection and Slovak short-title in preview while preserving original multilingual `vstup.povodny_text`.
- PDF layout helper tests for wrapped row height expansion and numeric baseline staying inside row block.

## 2026-04-12 — Session 019 — Deterministic top-level create-invoice pre-router

### Goal
- Add deterministic pre-routing before current invoice Phase 2 parsing so create-invoice starts are recognized reliably from multilingual/noisy action verbs.
- Reserve edit-intent verbs for future branching without implementing edit flow now.

### What changed
- Added top-level deterministic intent detector in `bot/handlers/invoice.py`:
  - normalizes first action tokens (Latin diacritics-safe + Cyrillic-safe),
  - maps supported Slovak/Ukrainian/Russian create verbs to single intent `create_invoice`,
  - recognizes reserved edit placeholders (`upraviť/upravit/управить/исправь/отредактируй`) as `edit_invoice`.
- Inserted pre-router guard at the start of `process_invoice_text(...)`:
  - `edit_invoice` is explicitly blocked from entering current create flow,
  - current create Phase 2 flow is kept unchanged after routing.
- Added focused tests in `tests/test_invoice_intent_prerouter.py` covering required mixed/noisy create examples and ensuring edit-like verbs are not misrouted into create.

### Notes
- No invoice parsing logic moved into intent layer.
- No edit flow implemented; only placeholder recognition for future branching.

## 2026-04-12 — Session 020 — Intent pre-router final minimal verb set (create/edit/send)

### Goal
- Extend deterministic top-level invoice intent pre-router to explicitly separate create/edit/send starts before Phase 2 parsing.

### What changed
- Added deterministic `send_invoice` placeholder intent and `unknown` fallback return in `_detect_invoice_intent(...)`.
- Extended create verb set with required `сделать` and ensured all required create/edit/send verbs are normalized and recognized.
- Updated pre-routing in `process_invoice_text(...)` so both reserved `edit_invoice` and `send_invoice` are blocked from entering current create flow.
- Extended focused tests to cover required create/edit/send examples plus misrouting guards proving edit/send verbs never call Phase 2 parser.

### Notes
- No edit flow or send flow implementation added.
- Existing create flow after routing remains unchanged.

## 2026-04-12 — Session 021 — Unified bounded semantic resolver + contact intake with contract PDF branch

### Goal
- Align runtime with documented LLM orchestrator contract: one bounded semantic resolution layer for top-level action, in-state decisions, and reusable value canonicalization contract.
- Add `add_contact` runtime path for text/voice and document-assisted intake while preserving Python execution authority and fail-loud behavior.

### What changed
- Added reusable semantic resolver service (`bot/services/semantic_action_resolver.py`):
  - bounded API: `context_name` + `allowed_actions/values` + user text + optional context,
  - structured output contract (`canonical_action` or `unknown`),
  - runtime guard: Python validates/executes, LLM only canonicalizes,
  - minimal deterministic fallback for resilience when LLM is unavailable.
- Integrated semantic resolver into invoice runtime:
  - top-level routing now resolves `create_invoice` / `add_contact` / `send_invoice` / `edit_invoice` / `unknown`,
  - preview confirmation now semantic `ano` / `nie`,
  - post-PDF decision now semantic `schvalit` / `upravit` / `zrusit`.
- Added top-level semantic text entry handler (non-command text in idle state) to route through unified runtime path.
- Added contact intake runtime extensions in `bot/handlers/contacts.py`:
  - new intake states for missing-fields clarification and confirmation,
  - Slovak fail-loud prompts for missing critical fields,
  - semantic yes/no confirmation before DB save,
  - reuse of existing `ContactService.create_or_replace(...)` persistence.
- Added document intake service (`bot/services/document_intake.py`):
  - detects and downloads Telegram attachment,
  - handles text-PDF extraction path,
  - distinguishes scan-PDF (no text layer) and returns explicit fallback status,
  - unsupported type handling.
- Added contact field extraction service (`bot/services/llm_contact_parser.py`):
  - bounded structured extraction target for company/contact fields,
  - optional role-ambiguity signal,
  - deterministic fallback parser for critical fields.
- Extended voice routing (`bot/handlers/voice.py`) so voice also routes in contact intake states (`missing`, `confirm`) and does not leak back into invoice flow.

### OCR/vision note
- Scan-PDF branch is implemented as explicit detection + fail-loud user message + pluggable fallback point.
- Full OCR runtime is not wired in this session due current project constraints/tooling baseline.

### Tests
- Added/updated tests for:
  - semantic top-level action resolver and in-state mapping,
  - voice routing into contact clarification state,
  - contact intake with missing email/address clarification,
  - document intake branches: text-PDF, scan-PDF detection, unsupported type,
  - invoice post-PDF cleanup regressions retained in focused suite.

## 2026-04-12 — Session 022 — Stabilization fixes for unified semantic/contact intake patch

### Goal
- Close concrete correctness gaps before merge without redesigning architecture.

### Fixes
- Tightened top-level fallback priority in semantic resolver:
  - reserved `edit/send` stay higher priority than generic invoice nouns,
  - `create_invoice` keeps precedence over `add_contact` when invoice evidence is present,
  - `add_contact` now requires explicit add/store verb + contact/company target evidence.
- Prevented accidental contact import from random idle documents:
  - document intake now starts only when caption/intent semantically resolves to `add_contact`,
  - otherwise bot responds with bounded Slovak guidance and does not guess side effects.
- Preserved explicit company hint path:
  - added deterministic hint extraction from text/caption,
  - passed hint into contact draft extraction.
- Fixed deterministic `ic_dph` extraction bug:
  - extractor now returns actual VAT value token (e.g. `SK1234567890`) instead of label fragment.
- Extended focused regression tests for:
  - fallback top-level create/edit/send/unknown behavior with `api_key=None`,
  - create-vs-add_contact misroute guard when company token is present,
  - idle document rejection (no implicit contact intake),
  - company_hint propagation path,
  - deterministic `ic_dph` extraction correctness.

## 2026-04-12 — Session 023 — Contact wizard step-1 dual input (text or PDF)

### Goal
- Reuse existing `/contact` onboarding UX naturally for semantic `add_contact` while allowing contract PDF as an alternative input at step 1.

### What changed
- `start_add_contact_intake(...)` now enters the existing contact wizard at step 1 instead of launching separate intake UX.
- Step 1 prompt changed to dual-input Slovak wording:
  - `1/7 Zadajte názov firmy odberateľa alebo pošlite zmluvu/PDF.`
- Added dual-step handler (`ContactStates.name_or_document`) so first input can be:
  - text company name -> continue existing 2/7..7/7 manual wizard,
  - PDF/document -> branch into extraction draft flow, then missing-fields/confirm path.
- Kept idle-document safety guard: document is only imported when semantic intent resolves to `add_contact`; otherwise bounded guidance is returned.
- Updated focused tests to cover wizard entry behavior and preserved document extraction regressions.

## 2026-04-12 — Session 024 — Contact onboarding order fix: manual company name first

### Goal
- Correct add-contact onboarding sequence so company name is entered manually first, then user chooses source via next input (PDF or IČO), while preserving semantic/document safety improvements.

### What changed
- Contact flow state order updated to `name_hint -> source_after_name -> (PDF extraction branch OR manual ICO branch)`.
- `start_add_contact_intake(...)` now only enters onboarding and sends:
  - `V poriadku, vytvoríme nový kontakt. Najprv napíšte názov firmy.`
- Company hint is stored from manual text (`contact_company_hint`) and reused for PDF extraction even when PDF has no caption.
- After company name step bot prompts:
  - `Pošlite zmluvu/PDF alebo zadajte IČO.`
- In `source_after_name`:
  - text is treated as IČO (validated), then manual wizard continues from DIČ,
  - document goes through existing intake/extraction flow.
- Voice safety tightened:
  - `name_hint` and `source_after_name` reject voice with bounded Slovak messages,
  - existing invoice and intake_missing/intake_confirm voice routing preserved.
- Role ambiguity path now preserves partial extracted draft in FSM state instead of dropping extracted fields.

### Tests
- Added/updated focused tests for:
  - semantic add-contact entry to `name_hint`,
  - name-hint transition and company-hint storage,
  - source-after-name manual IČO path valid/invalid,
  - source-after-name PDF path with no caption using saved company hint,
  - role-ambiguity partial draft retention,
  - voice restrictions in `name_hint` and `source_after_name`.

## 2026-04-12 — Session 025 — Invoice Phase 2 service-slot repair and clarification retention

### Goal
- Fix Phase 2 invoice payload handling so noisy/non-Slovak `biznis_sk.polozka_povodna` does not drop full draft when service meaning is recoverable, and add slot-level clarification path when only service term is unresolved.

### What changed
- Added deterministic service-slot repair in `validate_invoice_phase2_payload(...)`:
  - canonical service term is now resolved primarily from `biznis_sk.termin_sluzby_sk` (fallback to `polozka_povodna`),
  - when canonical term is recognized, payload is repaired in-place (`termin_sluzby_sk` canonical, safe Slovak `polozka_povodna`) instead of fail-loud on Cyrillic/noisy item text,
  - when service term remains unresolved after repair attempt, validator raises structured `LlmInvoicePayloadError` with `error_code=service_term_unresolved` and partial payload for continuation.
- Improved Phase 2 invalid-payload observability in invoice handler:
  - added focused debug log event `invoice_phase2_payload_invalid` with raw/repaired service fields and structured error code.
- Added slot-level clarification FSM branch:
  - new state `InvoiceStates.waiting_service_clarification`,
  - when parser returns `service_term_unresolved`, bot preserves partial draft (`invoice_partial_draft`) and asks Slovak-only clarification: `Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.`,
  - clarification reply is normalized via existing service normalizer and flow continues directly to preview build without restarting full invoice input.

### Tests
- Updated focused tests to cover:
  - repair path for noisy/Cyrillic-like service item tokens (`ремонт`, `управы`, `оправы`) with recognized service concept,
  - unresolved service slot structured error behavior,
  - partial draft retention + clarification prompt path in `process_invoice_text`,
  - continuation from clarification reply to preview build without full restart.

## 2026-04-14 — Session 026 — Audit-only map for confirmation/decision resolver paths

### Goal
Produce a code-evidenced audit map for bounded short in-action confirmations/decisions (invoice preview, post-PDF decision, contact confirms, related deterministic confirms), including voice/STT routing and contract gaps before any runtime patch.

### Changes
- added audit document `docs/llm/Confirmation_Decision_Audit_2026-04-14.md` with:
  - resolver/prompt inventory,
  - voice call map,
  - contract-gap notes against bounded template,
  - STT-noise production-risk lens,
  - test coverage note and likely repair surface pointers.

### Notes
- Audit-only session: no runtime behavior changes.
- No architecture redesign introduced.

## 2026-04-14 — Session 027 — Conservative bounded resolver for short in-action confirmations/decisions

### Goal
Implement targeted runtime hardening for short confirmation/decision states so noisy/ambiguous STT transcripts resolve to `unknown` (retry), with no architecture redesign.

### Changes
- `bot/services/semantic_action_resolver.py`:
  - added dedicated strict resolver `resolve_bounded_confirmation_reply(...)` for short in-action confirmations/decisions;
  - resolver payload now explicitly includes:
    - `context_name`,
    - `expected_reply_type`,
    - `supported_input_languages=['sk','uk','ru']`,
    - `allowed_canonical_outputs`,
    - `user_input_text`;
  - added conservative deterministic fallback for bounded short replies:
    - accepts only clear one-token canonical equivalents,
    - ambiguous/noisy/off-target inputs return `unknown`;
  - left existing generic resolver and slot quantity/unit-price resolver intact.
- `bot/handlers/invoice.py`:
  - preview confirmation now uses strict bounded resolver (`yes_no_confirmation`);
  - post-PDF decision now uses strict bounded resolver (`postpdf_decision`);
  - existing retry UX/messages preserved.
- `bot/handlers/contacts.py`:
  - semantic intake confirm now uses strict bounded resolver (`yes_no_confirmation`);
  - existing retry UX/message preserved.
- tests:
  - added noisy transcript regressions (`Ah, não.`) for preview confirmation, post-PDF decision, and contact semantic confirm;
  - added guard that post-PDF noisy input does not trigger destructive cleanup;
  - added positive regression tests for strict bounded resolver canonical outputs.

### Notes
- No STT model/transport changes.
- No top-level action routing changes.
- No invoice amount semantics or service-alias flow changes.

## 2026-04-16 — Session 028 — Invoice service/customer bounded candidate migration batch

### Goal
Finish coherent migration of invoice slot resolution to bounded LLM contract for service/customer slots (including clarification and edit-replace service path), while keeping deterministic Python validation/state/side effects.

### Changes
- `bot/handlers/invoice.py`:
  - added bounded customer candidate resolver helper that:
    - builds allowed contact candidate set from supplier contacts,
    - includes deterministic normalized/compressed direct-match shortcut,
    - then uses bounded resolver (`resolve_semantic_action`) with strict allowed candidates and metadata,
    - returns exact contact or unresolved.
  - preview build path now applies bounded customer candidate selection when deterministic contact lookup is not exact/normalized single-match:
    - for `multiple_candidates`: bounded candidate set from lookup candidates,
    - for `no_match`: bounded candidate set from supplier contacts,
    - unresolved continues to slot clarification with bounded customer choices.
  - customer slot clarification now uses bounded candidate resolver (reusing bounded candidate set saved in FSM partial draft) instead of raw phrase heuristics as final chooser.
  - service slot clarification/edit service replacement continue using supplier alias bounded candidate contract (exact allowed alias or unknown).
- `bot/services/semantic_action_resolver.py`:
  - aligned resolver payload envelope with docs/llm template fields for bounded action/value resolution:
    - `context_name`,
    - `current_state` (when present in auxiliary context),
    - `supported_languages`,
    - `allowed_actions`,
    - `user_input_text`,
    - `expected_output`,
    - `auxiliary_context`,
    - `action_hints`.
- `bot/services/service_term_normalizer.py`:
  - marked as legacy migration helper (fallback/support only; not primary runtime resolver).
- tests:
  - added regression for DB alias `stavebné práce` with noisy input `stavbné práce` resolved through bounded allowed alias selection;
  - added coverage that noisy customer candidate resolves via bounded contact candidate set;
  - added coverage that customer clarification reuses bounded candidates from FSM partial payload.

### Notes
- Deterministic Python responsibilities preserved: cleaning/normalization, DB lookup, validation, FSM/state transitions, numbering/PDF and side effects.
- No hidden concept changes: migration keeps existing invoice workflow architecture and fail-loud behavior for unresolved slots.

## 2026-04-17 — Session 029 — Final cleanup of parser legacy customer gate + clarification seam

### Goal
Complete remaining cleanup seams from invoice service/customer bounded migration before merge readiness check.

### Changes
- `bot/services/llm_invoice_parser.py`:
  - removed legacy semantic phrase/prefix/blocklist customer gating in parser validation;
  - parser customer candidate validation now keeps only structural sanity checks (type, non-empty, max length, alphanumeric presence) and no longer rejects phrase-like candidates as semantic decision logic.
- `bot/handlers/invoice.py`:
  - removed dead duplicate `_SLOT_CUSTOMER` branch from `_apply_slot_clarification(...)`;
  - customer clarification runtime path remains single canonical bounded path via `process_invoice_slot_clarification(...)` + `_resolve_customer_candidate_bounded(...)`.
- `tests/test_invoice_phase2_ai_layer.py`:
  - updated parser tests to match new contract:
    - reject only structurally invalid customer candidates,
    - accept noisy phrase-like customer candidates for later bounded runtime resolution.

### Notes
- No architecture redesign.
- Service/customer runtime bounded resolution paths remain unchanged for create/clarify/edit.

## 2026-04-18 — Session 030 — Approval-step diagnostic trace for waiting_pdf_decision

### Goal
Add transparent runtime diagnostics for the post-PDF approval step (`waiting_pdf_decision`) and add narrow tests that expose bounded contract behavior and potential mismatch risks, without changing edit-flow or create/edit/PDF business logic.

### Changes
- `bot/handlers/voice.py`:
  - added diagnostic log `approval_voice_routing` for `waiting_pdf_decision` voice routing path with:
    - `request_id`,
    - `current_state`,
    - `recognized_text`,
    - `telegram_message_id`.
- `bot/handlers/invoice.py` (`process_invoice_postpdf_decision`):
  - added diagnostic request/response logs around bounded resolver call:
    - `approval_resolver_request`,
    - `approval_resolver_response`;
  - added branch decision log before each final branch:
    - `approval_branch_decision` with `branch_taken` in `{schvalit, upravit, zrusit, unknown}`;
  - added explicit unknown-gap log event:
    - `approval_unknown_contract_gap` with full resolver/branch context.
- `bot/services/semantic_action_resolver.py`:
  - extended `resolve_bounded_confirmation_reply(...)` with optional `diagnostics` payload output (backward compatible);
  - diagnostics include:
    - `raw_model_output`,
    - `normalized_output`,
    - `fallback_used`,
    - `fallback_output`;
  - fallback/exception path now populates diagnostics deterministically for traceability.
- tests:
  - `tests/test_invoice_intent_prerouter.py`:
    - added post-PDF bounded synonym matrix assertions (canonical + multilingual/noisy variants).
  - `tests/test_invoice_state_decisions.py`:
    - added runtime branch regression for multilingual destructive synonyms (`отменить`, `delete`);
    - added unknown-contract-gap logging regression (`unknown` does not auto-cancel).
  - `tests/test_voice_state_routing.py`:
    - added voice parity regression for `waiting_pdf_decision` to confirm STT text pass-through and `approval_voice_routing` logging.

### Notes
- This session is diagnostic-only and keeps existing runtime behavior unchanged.
- No hidden concept changes, no edits to invoice edit subflows or PDF generation logic.

## 2026-04-27 — Session 031 — Server ops context routing clarification

### Goal
Prevent agents from mistaking the public `docs/local-only/*.example.md` placeholder for the real FakturaBot server runbook.

### Server operation
- Performed a one-time server-side invoice cleanup using the temporary `reset_invoice_sequence_to_4.py` script.
- Kept invoice numbers `20260001` through `20260004`.
- Removed later 2026 invoice rows above `20260004`.
- Restarted the `fakturabot` container after the operation.
- Removed the temporary script from the server repo after the one-time run.

### Changes
- Local ignored file placement:
  - moved the private server context from `docs/FakturaBot_Server_Agent_Context.md` to `docs/local-only/FakturaBot_Server_Agent_Context.md`;
  - confirmed the new path is ignored by `.gitignore`.
- `AGENTS.md`:
  - added explicit server-side operational context guidance;
  - documented that `docs/local-only/FakturaBot_Server_Agent_Context.md` is the private local server context file to check before server work;
  - documented that `docs/local-only/*.example.md` files are public placeholders only.
- `docs/local-only/README.md`:
  - clarified that example files are not live runbooks.
- `docs/local-only/FakturaBot_Server_Agent_Context.example.md`:
  - added a clear pointer to the private ignored `docs/local-only/FakturaBot_Server_Agent_Context.md` file for real server operations.

### Notes
- No product logic, MVP scope, or architecture changes.
- No secrets were added to tracked docs.

## 2026-04-29 — Session 032 — Delivery date confirmation-window guards

### Goal
Investigate why server invoice `20260005` received `delivery_date = 2023-04-25` after the user dictated `25 квітня`, and harden future-date handling for day+month inputs without an explicit year.

### Findings
- Current flow already has year anchoring for recognized day+month inputs without year.
- The failure path is `_resolve_delivery_date(...)` accepting the LLM-provided full date when Python cannot independently extract day+month from raw/STT text.
- That allowed an old LLM year (`2023`) to pass into draft/PDF.
- The same anchoring rule could also produce a far-future delivery date when a user says a late-year date near the start of the invoice year.

### Changes
- Added Python confirmation-window guards:
  - more than 62 days before `Dátum vystavenia` requires explicit raw/STT year confirmation near the same day;
  - more than 93 days after `Dátum vystavenia` also requires explicit raw/STT year confirmation near the same day;
  - otherwise the flow fails into date clarification.
- Tightened the invoice draft prompt so LLM must not invent a year from model/training context and must return `null` when the year is not reliable.
- Updated TZ date interpretation rules with the 2-month stale-year guard and 3-month future-date guard.
- Added regression tests for the `20260005` stale-year scenario, explicitly confirmed old year, unconfirmed far-future date, and explicitly confirmed future date.

### Notes
- Code change was deployed to the server after merge/push.
- Server invoice `20260005` was corrected after backup:
  - `delivery_date` changed from `2023-04-25` to `2026-04-25`;
  - `/bot/data/storage/invoices/20260005.pdf` was regenerated;
  - backup copies were stored under `/bot/repo/data/storage/backups/`.

## 2026-05-01 — Session 033 — Shared OfficeFlow idle attachment router foundation

### Goal
Implement docs-first and runtime foundation for a shared OfficeFlow idle attachment classifier/router above accounting intake and contact/contract intake.

### Decisions
- Active FSM state remains authoritative:
  - `/doklad` upload state continues to own accounting uploads;
  - contact source/intake states continue to own contact document uploads;
  - the shared router is registered idle-only with `StateFilter(None)`.
- LMM classifies document type only:
  - `receipt`,
  - `incoming_invoice`,
  - `contract`,
  - `contact_source`,
  - `unknown`.
- Python maps `document_type` to a bounded proposal and asks the user before any save/create side effect.
- `bot/services/document_intake.py` remains the old contract/contact PDF helper and was not expanded for accounting documents.
- Standalone `save_contract` remains reserved; the runtime fails explicitly if selected.

### Changes
- Docs:
  - updated `docs/llm/Canonical_Action_Registry.md`;
  - updated `docs/llm/In_Action_Response_Registry.md`;
  - updated `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
  - updated `docs/Document_Intake_Module_Proposal.md`.
- Runtime:
  - added `bot/services/officeflow_attachment_models.py`;
  - added `bot/services/officeflow_attachment_storage.py`;
  - added `bot/services/officeflow_attachment_classifier.py`;
  - added `bot/services/officeflow_attachment_lmm.py`;
  - added `prompts/officeflow_attachment_classification_prompt.txt`;
  - added `bot/handlers/officeflow_attachment_router.py`;
  - registered the shared router before `contacts_router`;
  - added a staged-file entrypoint for existing accounting document processing.
- DecisionResolver:
  - added `attachment_route_choice`;
  - added `attachment_document_type_choice`;
  - kept accounting proposal on existing `yes_no`.
- Tests:
  - added strict parser coverage for all allowed attachment document types and invalid payloads;
  - added idle router coverage for receipt, incoming invoice, contract, unknown, LMM failure cleanup, and idle-only registration;
  - added DecisionResolver coverage for attachment route/document-type choices and STT-noise fallback.

### Verification
- `python -m pytest -q` — 402 passed.

### Notes
- No DB schema changes.
- No invoice flow, `storage/invoices`, or `pdf_path` changes.
- No Google Drive sync, bank matching, or Zevs runtime profile.
- No confirmed accounting document, contact, or contract is saved from idle classification alone.

## 2026-05-01 — Session 034 — Idle attachment accounting proposal DecisionResolver bugfix

### Goal
Fix the idle attachment accounting proposal confirmation path so it does not rely on a flow-specific yes/no fallback.

### Changes
- Kept `bot/handlers/officeflow_attachment_router.py` on `decision_resolver.resolve_yes_no(...)`.
- Removed the `idle_attachment_accounting_proposal` context from context-specific yes/no fallback logic.
- Consolidated yes/no confirmation fallback into one shared `yes_no_confirmation` family helper inside the canonical resolver layer.
- Updated the idle accounting proposal prompt to explicitly say: `Odpovedzte: áno / nie.`
- Added regression coverage for:
  - `ano`,
  - `áno`,
  - `tak`,
  - `ok`,
  - Cyrillic `так`,
  - Cyrillic `да`,
  - unknown clarification,
  - no/cancel cleanup,
  - no local confirmation parser in the idle attachment handler.

### Verification
- `python -m pytest -q tests\test_decision_resolver.py tests\test_officeflow_attachment_router.py` — 64 passed.
- `python -m pytest -q` — 417 passed.

### Notes
- No DB schema changes.
- No invoice flow, `storage/invoices`, or `pdf_path` changes.
- No Document Intake confirmed storage structure changes.

## 2026-05-01 — Session 035 — DecisionResolver design gate documentation

### Goal
Prevent future actions/subflows from adding duplicate local confirmation parsers instead of using the Canonical DecisionResolver.

### Changes
- `docs/Canonical_Decision_Resolver_Contract.md`:
  - clarified that the contract is an implementation gate, not guidance;
  - added forbidden patterns for handler-local and flow-specific confirmation parsing;
  - added required pattern for canonical decision outputs;
  - added a new decision-family gate for future actions/subflows.
- `docs/llm/New_Action_Design_Checklist.md`:
  - added a mandatory DecisionResolver gate before runtime handler implementation;
  - added test expectations for shared resolver usage and no local parser.
- `docs/llm/In_Action_Response_Registry.md`:
  - clarified that new response groups must use `bot/services/decision_resolver.py`;
  - marked deterministic confirmations as legacy/manual documentation, not a template for new work.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`:
  - added an implementation gate requiring confirmation/route/save/delete replies to go through `decision_resolver.py`.

### Notes
- Documentation-only change.
- No runtime, DB, storage, invoice, Google Drive, or bank matching changes.

## 2026-05-01 — Session 036 — OfficeFlow idle attachment voice continuation bugfix

### Goal
Fix OfficeFlow idle attachment accounting proposal voice replies being consumed by the global voice router and falling through to top-level invoice routing.

### Changes
- Refactored OfficeFlow attachment continuation handlers to expose explicit-text helpers for:
  - accounting proposal;
  - contact/contract route choice;
  - unknown document-type clarification.
- Updated `bot/handlers/voice.py` to route STT text for OfficeFlow attachment states back into those helpers before invoice fallback.
- Preserved Canonical DecisionResolver usage; no local yes/no parser was added.
- Added regression coverage for voice `ano`, `ANO`, `tak`, Cyrillic `так`, `nie`, and noisy unknown input in `OfficeFlowAttachmentRouterStates.accounting_proposal`.

### Verification
- `python -m pytest -q tests\test_decision_resolver.py tests\test_officeflow_attachment_router.py` — 70 passed.
- `python -m pytest -q tests\test_accounting_document_intake_flow.py tests\test_contact_intake_semantic_flow.py` — 23 passed.
- `python -m pytest -q` — 423 passed.

### Notes
- No DB schema changes.
- No invoice flow semantics, `storage/invoices`, or `pdf_path` changes.
- No accounting/contact auto-save behavior changes.

## 2026-05-02 — Session 037 — Accounting preview DecisionResolver voice parity

### Goal
Apply the Canonical DecisionResolver contract consistently to accounting document preview approve/edit/cancel decisions for text and voice.

### Changes
- Refactored accounting document preview decision handling to expose an explicit-text helper.
- Routed `AccountingDocumentIntakeStates.waiting_preview_decision` voice/STT input through that same helper before invoice fallback.
- Kept approve/edit/cancel resolution on `decision_resolver.resolve_approve_edit_cancel(...)`.
- Updated accounting preview `edit` behavior to fail safe without saving or cleanup:
  - keep FSM state;
  - keep staged original;
  - reply that accounting document editing is not available yet.
- Added shared resolver coverage for additional multilingual approve/edit/cancel variants.
- Added contract tests that relevant handlers do not branch on legacy `schvalit` / `upravit` / `zrusit` decisions.

### Verification
- `python -m pytest -q tests\test_decision_resolver.py tests\test_accounting_document_intake_flow.py tests\test_voice_state_routing.py tests\test_officeflow_attachment_router.py` — 232 passed.
- `python -m pytest -q` — 550 passed.

### Notes
- No DB schema changes.
- No `storage/invoices` or `pdf_path` changes.
- No full accounting document edit-flow was implemented.
- Invoice draft/post-PDF edit behavior was not changed.

## 2026-05-02 - Session 038 - OfficeFlow architecture framing after Document Intake Phase 1

### Goal
Align the OfficeFlow architecture framing document with the implemented Document Intake Phase 1 runtime without implying a full workspace runtime or invoice storage migration.

### Changes
- Updated `docs/OfficeFlow_Architecture_Framing.md` to document that FakturaBot outgoing invoices remain unchanged and still use `storage/invoices/` plus `pdf_path`.
- Documented current accounting Document Intake Phase 1 support for receipts and incoming invoices.
- Documented confirmed accounting storage under `storage/workspaces/mykhailo-szco/years/<YYYY>/expenses/<MM>/<receipts|incoming_invoices>/<originals|metadata>/`.
- Documented neutral idle attachment staging under `storage/uploads/attachment_intake/<id>/original.<ext>`.
- Added cross-references to `docs/Document_Intake_Module_Proposal.md` and `docs/OfficeFlow_Storage_Model_Proposal.md`.
- Documented future Google Drive sync storage rules in `docs/OfficeFlow_Storage_Model_Proposal.md`:
  - confirmed accounting metadata should use storage-relative paths;
  - future sync should resolve files as `STORAGE_ROOT + relative_path`;
  - host-only paths and temp upload staging are not canonical sync inputs.

### Verification
- Tests not run; documentation-only update.

### Notes
- No code changes.
- No DB schema changes.
- No `storage/invoices` or `pdf_path` changes.
- No Google Drive sync runtime was implemented.
- No Zevs s.r.o. runtime profile or full workspace runtime was introduced.

## 2026-05-02 - Session 039 - Accounting intake purchase subject extraction

### Goal
Replace premature accounting category extraction in Document Intake Phase 1 with raw factual purchase subject extraction.

### Changes
- Replaced accounting candidate/metadata field `category_candidate` with `purchase_subject`.
- Updated the accounting extraction prompt to require raw facts only and forbid accounting/tax/bookkeeping category inference.
- Updated Slovak accounting preview from `Kategória` to `Predmet nákupu`.
- Kept read compatibility for legacy `category_candidate` payload/state values by mapping them into `purchase_subject`, while new metadata writes only `purchase_subject`.
- Updated Document Intake docs to describe purchase subject as the factual item/service bought.
- Added ASFINAG/vignette-style coverage for factual purchase subject extraction.

### Verification
- `python -m pytest -q tests\test_accounting_document_extraction.py tests\test_accounting_document_lmm.py tests\test_accounting_document_intake_flow.py` - 38 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- No confirmed accounting storage layout changes.
- No accounting categorization or Google Drive sync was implemented.

## 2026-05-02 - Session 040 - Temporary intake inactivity timeout

### Goal
Prevent abandoned OfficeFlow/accounting temporary intake sessions from leaving staged upload files and stale FSM state.

### Changes
- Added shared temporary intake session helper with:
  - 5-minute FSM/session timeout metadata;
  - safe cleanup restricted to `storage/uploads/attachment_intake/` and `storage/uploads/accounting_intake/`;
  - filesystem orphan cleanup helper for old upload-staging directories.
- Added expiry metadata to OfficeFlow idle attachment routing states.
- Added expiry metadata to accounting document preview state.
- Guarded OfficeFlow attachment continuation handlers and accounting preview decisions before any business continuation.
- Voice/STT replies reuse the same guarded continuation helpers, so expired voice replies do not fall into invoice fallback.
- Documented the temporary intake lifecycle boundary in `docs/Document_Intake_Module_Proposal.md`.

### Verification
- `python -m pytest -q tests\test_temp_intake_session.py tests\test_officeflow_attachment_router.py tests\test_accounting_document_intake_flow.py` - 51 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- Confirmed accounting storage, invoice PDFs, and contracts are excluded from timeout cleanup.
- No Google Drive sync or global cleanup scheduler was implemented.

## 2026-05-02 - Session 041 - Accounting intake duplicate warning

### Goal
Warn before processing a receipt/incoming invoice that appears to duplicate already confirmed accounting metadata.

### Changes
- Added deterministic duplicate scanning over confirmed accounting metadata only.
- Duplicate matching compares document type, issue date, normalized vendor name, total amount, and currency.
- Added `AccountingDocumentIntakeStates.waiting_duplicate_decision`.
- Duplicate decision uses the shared `resolve_yes_no(...)` DecisionResolver family.
- If the user continues, the normal accounting preview is shown and explicit preview approval is still required before save.
- Added voice routing for duplicate decisions through the same guarded helper.
- Documented that filename is not duplicate truth and that Slice 1 does not use AI/fuzzy/image/PDF duplicate matching.

### Verification
- `python -m pytest -q tests\test_accounting_document_duplicates.py tests\test_accounting_document_intake_flow.py` - 35 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- No changes to `storage/contracts`.
- No automatic overwrite, deletion, fuzzy matching, AI duplicate matching, or Google Drive sync was implemented.

## 2026-05-02 - Session 042 - Recent accounting documents view

### Goal
Add a lightweight read-only `/blocky` command for recent confirmed receipts/incoming accounting documents.

### Changes
- Added `show_recent_accounting_documents` as a command-backed read-only action.
- Added confirmed metadata registry scanning for the last 5 receipts/incoming invoices.
- Added `/blocky` and narrow deterministic aliases for recent bločky/receipts phrases.
- Kept the view isolated from outgoing invoice PDFs, contracts, temp uploads, DB schema, and LMM routing.
- Documented the `/blocky` storage boundary and non-goals.

### Verification
- `python -m pytest -q tests\test_accounting_document_registry.py tests\test_accounting_documents_handler.py tests\test_invoice_intent_prerouter.py` - 99 passed.
- `python -m pytest -q` - 769 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- No `storage/contracts` changes.
- No Google Drive sync, delete/edit/search, or broad document browser was implemented.
# 2026-07-28 - Runtime Issue Intake V1

- Implemented administrator-only `report_runtime_issue` through exact `/issue`,
  bounded idle text/voice, and the shared active-FSM interrupt.
- Added deterministic secret/path redaction, trusted Telegram/workspace/FSM
  metadata collection, stable delivery deduplication, and an additive dedicated
  SQLite `runtime_issues` table at schema version 1.
- Kept active business state/data unchanged and added no issue FSM, confirmation,
  callback, repair, maintenance, merge, deployment, or other Stage 2 behavior.
- Synchronized Product Truth, InfoHelp and the canonical action registry. Runtime
  proof and final test totals are recorded in the conversation acceptance proof.

# 2026-07-28 - Canonical Stage 2 workshop documentation reconciliation

- Replaced the canonical daily maintenance runbook with the approved workshop
  version and removed the suffixed upload duplicate.
- Canonicalized the workshop queue schema and Slovak notification templates
  under filenames without upload suffixes.
- Replaced the package README and Architecture Design Proof with the supplied
  Stage 2 workshop documents.
- Documentation only: Stage 2 runtime, database behavior, tests, production,
  merge, and deployment were not changed.

# 2026-07-29 - Runtime Issue Workshop Bridge Phase 1

- Added the additive, strictly validated `runtime_issue_handoffs` table while
  keeping Stage 1 `runtime_issues` immutable.
- Added atomic 60-minute leases, stable receipt digests, safe redelivery, and
  remote-receipt-gated acknowledgment with stdin-only raw lease tokens.
- Added bounded recorded-evidence collection for STT, Docker, network, and
  provider facts, plus idempotent workshop queue/log bootstrap.
- Added focused migration, handoff, CLI, evidence, and bootstrap tests and a
  repository-only acceptance proof.
- No public route, FSM, callback, Product Truth, InfoHelp, nightly schedule,
  diagnosis, repair, notification, production migration, deploy, or restart
  was added.
## 2026-07-29 - Accounting intake cancel keyboard bugfix

### Finding
- This was a deterministic router-order bug, not evidence of a transient Telegram connection failure: `state_control_router` receives the reply-keyboard text before the accounting intake state handler, but its response did not remove the reply keyboard.

### Changes
- Shared global cancel responses now send `ReplyKeyboardRemove`.
- Accounting temp cleanup now recognizes every `AccountingDocumentIntakeStates` state, including the post-recognition unknown-category step.
- Added regressions for cancel after recognition/category review and from the final accounting preview; both prove FSM clear, temp-file cleanup, and keyboard removal.

### Verification
- `python -m pytest -q tests\test_state_control.py tests\test_accounting_document_intake_flow.py` - 58 passed.
- `python -m pytest -q tests\test_state_control.py tests\test_accounting_document_intake_flow.py tests\test_decision_resolver.py tests\test_officeflow_attachment_router.py tests\test_voice_state_routing.py` - 815 passed.
- Full `python -m pytest -q` was attempted but did not complete within the 120-second tool timeout; no full-suite verdict is claimed.

### Scope
- Deterministic FSM/cancel UX fix only; AI maturity and DecisionResolver authority are unchanged.
- No DB schema, confirmed storage, access, server, PDF, LLM, STT, or LMM changes. Server deployment and live Telegram smoke were not performed.

## 2026-07-29 - Mark-paid decision button cleanup audit

### Finding
- Normal `mark_existing_invoice_paid` `yes` and `no` callbacks already dispatched through the shared wrapper and removed inline markup after handling.
- Stale, expired, malformed, or state-less shared decision callbacks failed closed but left obsolete inline buttons visible.

### Changes
- The shared decision callback wrapper now removes inline markup before returning from stale/expired rejection paths.
- Added public-wrapper regressions for both mark-paid buttons and an expired mark-paid callback; the expired callback clears state and markup without dispatching `mark_paid`.

### Verification
- `python -m pytest -q tests\test_decision_callbacks.py tests\test_invoice_intent_prerouter.py -k "mark_existing_invoice_paid or stale_decision_callback"` - 6 passed, 239 deselected.
- `python -m pytest -q tests\test_decision_callbacks.py tests\test_invoice_followup_handler.py tests\test_workspace_invoice_followup_service.py` - 42 passed.

### Scope
- Shared inline-button lifecycle and tests only; no invoice content, payment semantics, DB schema, storage, access, LLM/STT/LMM, server, or deployment change.


## 2026-07-29 - Periodic official-registry contact monitor V1

### Decision

- Approved schedule: every 14 days at 03:00 `Europe/Bratislava`, anchored Monday 2026-08-03.
- Capability remains `partial`, `requires_setup`, and `requires_external_credentials`; code default is disabled.
- Added two additive SQLite tables for monitor state and bounded change proposals. No existing contact/invoice/PDF migration or rewrite is required.

### Implementation

- Added exact-IČO background checks for active authorized workspaces, bounded official-field diffs, Telegram yes/no proposals, transactional revalidation, replay/stale/conflict rejection, and user-deletion cleanup.
- Missing registry tax values preserve existing DIČ/IČ DPH. Approval may update only name, address, DIČ, and IČ DPH.
- Invoice rows/items, `pdf_path`, PDF bytes, email, IBAN, contact person, and contract path are outside the workflow.
- Added architecture and conversation acceptance proofs plus Product Truth/InfoHelp/TZ/in-action documentation.

### Migration and rollout

- Production pre-audit: SQLite quick check ok; 5 contacts, 4 valid IČO, 10 invoices, 2 referenced contacts, zero `(workspace_id, ico)` duplicate groups, and no monitor tables.
- Approved rollout: stop and backup, deploy disabled, validate additive schema, no-write/no-notification dry-run, then enable and health-check.

### Verification

- Focused implementation/regression set: `67 passed`.
- Full-suite and production rollout evidence will be appended after completion.

## 2026-07-29 - One-time Telegram keyboard lifecycle audit

### Decision

- Strengthened the existing top-level subflow, DecisionResolver, action-design,
  and evaluation contracts instead of creating a competing keyboard contract.
- Added `docs/evals/telegram_keyboard_lifecycle_audit_2026_07_29.md` as a
  one-time inventory/evidence artifact. Its verdict remains `needs_revision`.

### Findings and changes

- Audited all seven current `ReplyKeyboardMarkup`/`InlineKeyboardMarkup`
  families and every decorated callback handler under `bot/handlers/`.
- Repaired shared intake timeout exits so they send `ReplyKeyboardRemove`.
- Repaired owned expired/legacy invoice follow-up callbacks so obsolete inline
  buttons are removed; cross-workspace/forbidden callbacks remain fail-closed
  without editing a message whose ownership is not proven.
- Added cleanup-failure logging for shared decision and contact registry lookup
  keyboards without rolling back already completed business handling.
- Added final-keyboard assertions for business-profile select/cancel,
  OfficeFlow proposal no/timeout, accounting preview timeout, shared mark-paid
  yes/no/stale, cleanup-failure, and invoice follow-up expiry paths.
- Open gaps remain in contact registry lookup validation semantics and in the
  concurrent uncommitted registry monitor: owned stale/expired results must be
  distinguished from forbidden/unproven ownership before cleanup is expanded.

### Verification

- `python -m pytest -q tests\test_business_profiles_handler.py tests\test_decision_callbacks.py tests\test_contact_registry_flow.py` - 37 passed.
- `python -m pytest -q tests\test_temp_intake_session.py tests\test_officeflow_attachment_router.py tests\test_accounting_document_intake_flow.py tests\test_invoice_followup_handler.py` - 94 passed.
- `python -m pytest -q` - 2373 passed, 7 subtests passed in 753.68s.
- `git diff --check` - passed before the final documentation entry; rerun at
  handoff.

### Scope

- Deterministic Telegram UI lifecycle, tests, and contracts only. No DB schema,
  confirmed storage, access, PDF, AI maturity, Product Truth capability claim,
  server operation, deployment, or live Telegram smoke changed.


### Production rollout evidence - 2026-07-29

- Before writes, stopped the live container and created `/var/backups/fakturabot/20260729T193158Z_contact_registry_monitor` containing the pre-change DB, `.env`, image id, commit, and `SHA256SUMS`. DB backup SHA-256: `a90c9cc8dc65ab05cbf6e97b011d259c40fd2fc7354fe17f753c0084b852612a`; environment backup SHA-256: `aac22b958d9ca5840774911b6dd0620736639ca214d90bebae4112ce80594f75`.
- Fast-forwarded the server base from `acb1c75` to current GitHub `main` `6ce8493`, overlaid the tested monitor runtime files, and built image `sha256:b921ec05e7d8e262bb421014ec7747c4db2cb10e7adf87d254b10e89a020087d`. The server tree is intentionally dirty because this feature has not been committed/pushed.
- An initial operational command used the dev compose file and started an isolated container with an empty ephemeral DB. It was stopped immediately; no production business row was touched. The required `docker-compose.prod.yml` was then used and its mount was verified as `/bot/repo/data/storage -> /bot/data/storage`.
- Disabled deploy created only the two additive empty tables. Production then reported `quick_check=ok`, 5 contacts, 10 invoices, 0 monitor-state rows, and 0 proposal rows.
- The no-write/no-notification live dry-run audited five exact-IČO contacts. Initial bounded external calls returned three checks, two detected changes, one unchanged contact, and two temporary registry-unavailable failures. A bounded retry resolved all five exact identities; no raw provider/contact values were logged.
- Before/after dry-run DB SHA-256 remained `61d6dad55da3dae35884e296c427e93626edf00cfa013623382916917e6c3c2a`; aggregate invoice-PDF fingerprint remained `6efc241ac94e254cfac9cd3a1f513ca4ab6113bd2df33c057d348502a8da59a2`; monitor/proposal rows remained 0/0.
- Enabled `CONTACT_REGISTRY_MONITOR_ENABLED=1` with timezone `Europe/Bratislava`, anchor `2026-08-03T03:00:00`, 14-day interval, batch 20, and proposal TTL 30 days. Post-change `.env` SHA-256 is `e069c0e512aac8c89c1a6315d5d776b43fe04954902ac28bbb0697f287fa2fca`.
- Final runtime is `running`, restart count 0, polling active, monitor scheduler started, DB `quick_check=ok`, 5 contacts, 10 invoices, and 0/0 monitor/proposal rows before the first scheduled slot.

## 2026-07-29 - Git publication and clean production redeploy

- Full repository verification passed: `2373 passed, 7 subtests passed in 753.68s`.
- Published the complete project change set as commit
  `c70e0576a3df2effd09072af0410d6f2b214c1f3` on `origin/main`; local Codex
  attachment and generated pytest output files were excluded.
- All eight dirty server runtime files matched the local release payload by
  SHA-256. The prior server tree was retained as Git stash
  `predeploy-c70e057-2026-07-29` before the clean fast-forward.
- Rebuilt and restarted with `docker-compose.prod.yml`. The container reported
  `Up`; logs showed FakturaBot startup, Telegram polling, invoice follow-up,
  Google Drive archive, and contact registry monitor schedulers without a
  polling conflict or startup error.
- Server `.env`, business storage, and SQLite data were not manually rewritten;
  normal application startup behavior remained in effect.


### Final local verification

- After synchronizing local `main` to GitHub `6ce8493`, compileall, diff check, and the merged focused monitor/runtime-issue set passed: 107 passed.
- The complete 92-file test inventory was run in three bounded groups to avoid the desktop child-process time limit: 409 passed; 1528 passed plus 7 subtests; 436 passed. Aggregate: 2373 passed, 7 subtests passed.
- One earlier monolithic run reached 2372 passes with one transient business-profile cancel failure; that exact test passed immediately in isolation. Later monolithic attempts were killed by the desktop runner without pytest traceback. The complete grouped inventory above is the authoritative final verdict.


## 2026-07-30 - Interactive repair skill merged through PR #53

- Moved the public-safe OfficeFlow interactive repair skill from `docs/features/runtime_issue_autorepair_v1/OfficeFlow_Interactive_Repair_SKILL.md` to the requested root path `Skils/OfficeFlow_Interactive_Repair_SKILL.md` without changing its content.
- Marked PR #53 ready for review and merged exact head `f5be15bf24e54a7f700ed481b99c96ad28d63209` into `main`.
- Merge commit: `e1112251f36c5e22b96b72f98ea542be8b490b0d`.
- Documentation layout only; no runtime, database, storage, production, or business-data change.

## 2026-07-31 - FakturaBot Python test-suite audit

- Completed a documentation-only audit of all 101 Python test files on
  `origin/main` baseline `4a69b31`; no test, production code, behavior,
  dependency, pytest configuration, CI, database, storage, server, or
  deployment state changed.
- Exact collection: 2,433 pytest tests. Two full runs passed with seven
  additional passing unittest subtests in 467.17s and 485.03s.
- Repeated 123 stateful migration/handoff/OAuth/archive/work-time cases three
  times and once in reverse file order; all four runs passed.
- Added the canonical audit and complete per-file evidence inventory under
  `docs/audits/`. The audit recommends no deletions: 78 `KEEP_CRITICAL`, 10
  `KEEP`, 7 `PARAMETRIZE`, 3 `CONSOLIDATE`, 2 `INVESTIGATE`, and 1
  `OBSOLETE_CANDIDATE` file-level classification.
- The obsolete candidate is legacy Google Drive service-account coverage and
  remains blocked on Product Truth/deployment confirmation. Current owner-OAuth
  and retention protections must exist before any future retirement.
- Documented missing marker/CI taxonomy, over-mocked public-route boundaries,
  open keyboard lifecycle evidence, externally unproven Gmail/Drive/provider
  smoke, PDF visual acceptance, phased cleanup, risks, rollback, and product
  owner questions.


## 2026-08-02 - Contextual InfoHelp AI Assistant V2 repository implementation

### Preflight and architecture

- Initially audited current `origin/main` at `3cd85de54015a8bf5b8de01bcd24a5544db7af79` and inspected the existing remote `feat/infohelp-contextual-ai-assistant-v2`; it contained no implementation beyond historical main and required no force-push. During verification, `origin/main` advanced through the Gmail signed-relay evidence merges. Final delivery was refreshed onto exact base `4ab8f5bde30104b817d2cdfeca15d7f89044828b` as one clean V2 commit without force-push or unrelated branch work.
- Materialized `docs/architecture/INFOHELP_CONTEXTUAL_AI_ASSISTANT_V2_ARCHITECTURE_DESIGN_PROOF.md` with verdict `ready_for_handoff`; final implementation status is `implemented_pending_interactive_acceptance`.
- Preserved the PR #63/#65 rollback history. No V1 recovery handler/service, synthetic action-label dispatcher, generic callback, nearest-action selector, RAG, vector store, persistent transcript, or log-derived context was restored.

### Implementation decision

- Extended the existing `bot/services/info_help_resolver.py` owner with exactly one context-rich bounded assistant call. Python still owns Product Truth, exact domain/object/operation validation, canonical action eligibility, tenant/workspace scope, FSM, callbacks, confirmations, and effects.
- Added a compact Product Truth view, a Python-owned existing-action semantic registry, strict result parser, process-memory context limited to three user and three bot turns for ten minutes per user/chat/workspace, same-chat explicit Telegram reply context, active-FSM descriptors, and a shared invoice-reference continuation owner for text/voice.
- Callback business identity is `callback.from_user`; `callback.message` remains the source chat/message. Capability questions, correction/negation, vague destructive requests, unsupported receipt deletion, unsupported contact editing, and account-delete suggestions fail closed.
- Added `INFOHELP_CONTEXTUAL_V2_ROLLOUT=disabled|admin_pilot|enabled`; default and invalid values are `disabled`. Production configuration was not changed.

### Regression-first and verification evidence

- Before production code, `python -m pytest -q tests/test_info_help_contextual_v2.py tests/test_invoice_reference_continuation_v2.py` failed during collection because `INFO_HELP_INTENT_GENUINELY_UNCLEAR` and `InvoiceReferenceContinuationStates` did not yet exist.
- First green expanded contextual checkpoint: `19 passed in 6.36s`.
- Final focused InfoHelp/Product Truth/continuation command: `155 passed in 8.13s`.
- Adjacent invoice/Product Truth compatibility command: `254 passed in 41.98s`.
- Consolidated adjacent invoice/voice/FSM/contact/profile/callback/access/workspace/state/customization command: `502 passed, 7 subtests passed in 173.70s`.
- Final full suite on refreshed base: `python -m pytest -q` -> `2463 passed, 7 subtests passed in 751.20s`; no skipped tests reported.
- `python -m compileall -q bot` passed. `git diff --check` passed with only Git line-ending conversion warnings.

### Scope and rollout

- Repository implementation, tests, docs, commit, pushed branch, and PR only. No merge, deployment, restart, server access, production data access, DB migration, schema/storage write, or production configuration change.
- AI maturity remains `partial Level 2`; interactive 20-journey Telegram acceptance under an explicitly enabled `admin_pilot` remains pending before any production acceptance claim.

# 2026-08-03 - One-time labelled Gmail statement import

- The configured user applied the dedicated `FakturaBot-import` Gmail label to
  one recent message containing one PDF statement that had been sent from a
  personal mailbox and therefore could not match the permanent bank-sender
  query.
- A read-only label probe found exactly one message, one attachment candidate,
  and one PDF. Before import, an online SQLite backup passed
  `PRAGMA quick_check`, was stored under the FakturaBot backup root, and was
  restricted to mode `0600`.
- One isolated collector process used a temporary label-only query without
  changing `.env` or the running scheduler query. It stored one new
  workspace-scoped original with `parse_status=deferred`; there were no
  rejects, failures, source duplicates, or content duplicates.
- The resulting `bank_statement_original` archive job and authoritative
  accounting archive state both reached `uploaded` with no error. The
  permanent query still contains the trusted bank `from:` filter and does not
  contain the temporary label override.
- This is operational recovery evidence, not a new general capability:
  forwarded statements are not automatically accepted, statement content is
  not parsed, and per-client or broad mailbox synchronization remains out of
  scope. No OAuth scope, token, bot process, product code, or production
  configuration changed.
