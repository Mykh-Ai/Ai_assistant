# Repository Audit

Task ID: `RUNTIME_ISSUE_INTAKE_AND_AUTOREPAIR_V1`

Audit date: 2026-07-28

## Exact baseline

- Repository: `Mykh-Ai/Ai_assistant`
- Baseline branch: `main`
- Baseline SHA:
  `acb1c75274b8c69a94b90a82eec113c7d203b4f7`
- Baseline commit: `docs: record registry tax preview repair`
- Remote state at branch creation: local `main`, `origin/main`, and GitHub
  `main` were identical; GitHub comparison was zero commits ahead and zero
  behind.
- Worktree at branch creation: clean.
- Documentation branch:
  `docs/runtime-issue-autorepair-v1`, created from the exact baseline SHA.

## Canonical documents read

The audit used current files only:

- `AGENTS.md`
- `README.md`
- `docs/Product_Doctrine_2030.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/Implementation_Agent_Checklist.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/FakturaBot_Server_Rollout_Roadmap.md`
- `docs/FakturaBot_Data_Migration_Runbook.md`
- `docs/Google_Drive_Service_Account_Owner_Run_MVP.md`
- `docs/architecture/OfficeFlow_Architecture_Framing.md`
- `docs/architecture/OfficeFlow_Storage_Model_Proposal.md`
- `docs/local-only/README.md`

The original prompt referenced the standalone
`docs/llm/Conversation_Acceptance_Proof_Contract.md`. It does not exist and is
removed from the mandatory-document list. No contents are attributed to that
nonexistent file and no replacement is created. The equivalent real canonical
owner found in the repository is the section “Conversation Acceptance Proof”
inside `docs/Evaluation_and_Smoke_Test_Standards.md`; that real section also
prohibits a parallel standalone contract.

The original prompt also referenced
`docs/FakturaBot_LLM_Orchestrator_Contract.md`. That exact path does not exist.
The equivalent current file found and read is
`docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`. This audit cites only that
real file and does not attribute evidence to the absent path.

## Current source-of-truth order

`AGENTS.md`, section “Source Of Truth And Conflict Order”, makes current code
the strongest implementation evidence, followed by `PROJECT_LOG.md`, the
technical specification, focused contracts, and `CHANGELOG.md`. For product
mission it gives `docs/Product_Doctrine.md` and `docs/TZ_FakturaBot.md`
priority. `README.md` still contains an older abbreviated order with the
specification and log ahead of code. This package follows `AGENTS.md` and
records the README mismatch rather than silently treating the older order as
controlling.

## Current runtime owners

| Concern | Current owner and evidence | Finding for this feature |
|---|---|---|
| General Telegram authorization | `bot/services/authorization.py::TelegramUserAuthorizationMiddleware`; registration in `bot/main.py` | Outer middleware rejects unauthorized users before handlers, STT, LLM, and business persistence. |
| Administrator authorization | `bot/services/authorization.py::is_admin_telegram_user`, `ADMIN_COMMANDS`; `bot/services/access_control.py` role/status model; `bot/handlers/access_admin.py` | Reusable Python-owned admin check exists. `/issue` is absent. |
| Command registration and router order | `bot/handlers/__init__.py::get_routers`; handler decorators in `bot/handlers/access_admin.py`, `bot/handlers/state_control.py`, and other handler modules | Commands are distributed among routers; no single command registry and no `/issue` owner exists. |
| Idle top-level semantic routing | `bot/handlers/invoice.py::process_invoice_text`; `bot/services/semantic_action_resolver.py` | Bounded resolver and canonical-action allowlist pattern exist. `report_runtime_issue` is absent. |
| Active-FSM global controls | `bot/services/active_fsm_guard.py::ActiveFsmMessageMiddleware`, `handle_active_fsm_text_update`; `bot/handlers/state_control.py` | Only `/cancel`, `/menu`, and `/start` are deterministic active-state controls. Fresh unrelated top-level switching is not generally supported. |
| Voice and STT | `bot/handlers/voice.py`; outer authorization in `bot/main.py` | Voice is authorized generally, transcribed, then passed through the active-FSM guard or idle top-level owner. |
| Text/voice convergence | `bot/handlers/voice.py` calls state-specific owners or `bot/handlers/invoice.py::process_invoice_text` | A shared Python owner is feasible; no issue-specific convergence exists. |
| FSM state inspection and preservation | aiogram `FSMContext` use in `bot/services/active_fsm_guard.py`; shared cleanup in `bot/handlers/state_control.py` | State/data snapshots are accessible. Exact preservation is not yet proven because downstream pass-through stamps FSM activity. |
| Workspace scope | `bot/services/workspace_context.py::resolve_for_user_readonly`, `resolve_for_background_workspace`; membership checks in `bot/services/access_control.py` | Trusted, fail-closed workspace resolution exists and must own `workspace_id`. |
| SQLite bootstrap/service style | `bot/services/db.py` and domain services | SQLite is current persisted-data infrastructure. No runtime-issue, maintenance-run, or notification-outbox schema exists. |
| Atomic claim/lease | `bot/services/archive_job_service.py::claim_next_runnable_job`; `bot/services/archive_worker.py` | `BEGIN IMMEDIATE`, worker lock, lease expiry, retry, and terminal-state patterns are reusable by design, not their domain table. |
| Deferred file-delivery outbox | `bot/services/archive_job_service.py`; `bot/services/google_drive_archive_scheduler.py` | This outbox is specifically for archive uploads and must not become a generic bot-result outbox. |
| Admin response persistence | `bot/services/customization_requests.py`; `bot/handlers/access_admin.py` | Response state and duplicate-send protection exist, but failed bot delivery is explicitly not automatically retried. |
| Schedulers | `bot/services/invoice_followup_scheduler.py`, `bot/services/google_drive_archive_scheduler.py`; startup in `bot/main.py` | Both are bot-process schedulers. Neither is an approved owner for repository mutation or production deployment. |
| Callback acknowledgement and staleness | `bot/handlers/decision_callbacks.py`; `bot/handlers/invoice_followup.py` | Current patterns acknowledge callbacks, reject stale/mismatched payloads, and bound duplicate effects. |
| Contact resolution | `bot/services/contact_service.py::resolve_contact_lookup`; workspace counterpart in `bot/services/workspace_contact_service.py` | Canonical exact/normalized/alias/legal-suffix/bounded-fuzzy resolution exists. |
| Analytics identity filtering | `bot/services/invoice_analytics_dataset.py`, `workspace_invoice_analytics_dataset.py`, and `invoice_analytics_planner.py` | Datasets expose trusted `contact_id`; the planner currently has customer-name filtering and no proven resolver-to-analytics identity bridge. |
| Structured event logging | partial JSON debug output in `bot/handlers/invoice.py` and `bot/handlers/voice.py` under `DEBUG_INVOICE_TRANSPARENCY` | No central sanitized structured-event owner exists. Existing traces may include raw user/STT text and are unsuitable as an unbounded maintenance feed. |
| Trusted build SHA | deployment records in `PROJECT_LOG.md`; no owner in `bot/config.py` or a runtime service | Exact deployed SHA is sometimes proven manually, but the bot has no trusted runtime source for `reported_build_sha`. |
| Generic bot notification outbox | no current owner | A new approved owner is required. Direct `Bot.send_message` paths are not an idempotent retryable generic outbox. |

## Current tests inspected

The following current suites establish adjacent behavior and future regression
owners:

- `tests/test_active_fsm_guard.py`
  - `test_active_text_show_main_menu_clears_state_and_uses_existing_menu`
  - `test_active_text_resume_start_status_clears_state_and_uses_start_router`
  - `test_active_text_cancel_current_flow_uses_state_control_cancel`
  - `test_active_text_pass_through_is_not_swallowed_and_stamps_after_handler`
  - `test_stale_state_new_business_text_clears_then_routes_idle_once`
- `tests/test_voice_state_routing.py`
  - active navigation before state routing;
  - active-state pass-through to the existing state owner;
  - unhandled active state does not fall back to idle routing;
  - idle voice reaches the top-level owner.
- `tests/test_state_control.py`
  - idle cancel;
  - cleanup of edit scope without deleting persisted invoice data;
  - cancellation of an edit keeps the invoice.
- `tests/test_decision_callbacks.py`
  - unauthorized, stale, wrong-state, and legacy callbacks fail closed;
  - mark-paid buttons reuse the same business handler;
  - duplicate admin responses do not double-send.
- `tests/test_invoice_followup_handler.py`
  - mark-paid callback behavior;
  - stale timestamp rejection;
  - keyboard-cleanup failure handling.
- `tests/test_archive_job_service.py`
  - idempotent schema/enqueue;
  - atomic lease claim;
  - active lease exclusion;
  - expired lease reclaim;
  - terminal-transition rejection.
- `tests/test_archive_worker.py`
  - one-job isolation;
  - lease behavior;
  - bounded error logs;
  - no unintended network implementation in the worker unit.
- `tests/test_access_request_flow.py` and
  `tests/test_customization_request_admin.py`
  - unauthorized/admin boundaries;
  - persistence-before-delivery;
  - duplicate and tampered-target protection;
  - the present no-auto-retry delivery boundary.
- `tests/test_workspace_context.py` and `tests/test_tenant_safety.py`
  - read-only workspace selection;
  - membership enforcement;
  - unauthorized-before-LLM/business behavior;
  - tenant-scoped invoices and files.
- `tests/test_contact_lookup_normalization.py`,
  `tests/test_workspace_contact_service.py`,
  `tests/test_invoice_analytics_dataset.py`, and analytics planner tests
  - canonical contact matching, ambiguity handling, workspace boundaries,
    dataset fields, and current analytics behavior.
- `tests/test_multi_workspace_migration_apply.py`
  - preflight, fingerprint, rollback, and storage-drift gates for the existing
    migration workflow. This is operational evidence, not authorization for an
    issue-table migration.

No test currently owns `/issue`, `report_runtime_issue`, exact issue-interrupt
FSM preservation, maintenance issue classification, autorepair, or the proposed
generic result outbox.

## Relevant recent project history

- `PROJECT_LOG.md`, “2026-07-18 - Registry tax preview wording production
  repair”: exact production SHA, rollback image tag, startup/polling checks,
  in-container smoke, post-deploy error scan, and repository integrity.
- “2026-07-18 - Contact registry search/tax enrichment controlled deployment”:
  clean server tree, backup/rollback reference, Docker tag, health checks,
  error scan, and exact SHA evidence.
- “2026-07-17 - FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1”:
  architecture preflight, Conversation Acceptance Proof, workspace callback
  read-only repair, and human delivery gate.
- “2026-07-16 - Production Enqueue Repair For Two Preserved Receipts”:
  use of an existing scheduler and exactly two preserved archive jobs.
- “2026-07-12 - Production-Safe Multi-Workspace Legacy Migration Apply” and
  adjacent July 11–13 entries: explicit preflight, backup, rollback,
  fingerprint, workspace, and human operational gates.
- “2026-07-09 - Active FSM Navigation and Stale-State Guard”: current global
  controls, stale recovery, and explicit deferral of general fresh top-level
  switching because exact preservation/restore was not proven.
- “2026-06-16 - Session 145 - Invoice follow-up callback keyboard cleanup”:
  the adjacent keyboard-cleanup safety repair.
- “2026-06-15 - Session 144 - Automatic overdue invoice follow-up correction”:
  current daily scheduler and controlled deployment evidence.
- “2026-05-30” archive-outbox foundation entries: current claim, lease, retry,
  and one-job worker pattern.
- “2026-04-10” structured debug transparency entry: bounded debug intent, but
  not a generic sanitized diagnostic-event contract.
- “2026-04-27” server-operations context entry: the private owner-run context
  routing that is not available in this checkout.

## Deployment and rollback evidence

Tracked evidence:

- `scripts/update_repo.sh` performs fetch, checkout, and fast-forward-only pull.
- `scripts/deploy_owner_run.sh` prepares required directories and runs
  `docker compose -f docker-compose.prod.yml up -d --build`, followed by
  service status.
- `docker-compose.prod.yml` defines the bot service and persistent storage
  mounts.
- `docs/FakturaBot_Server_Rollout_Roadmap.md`,
  `docs/FakturaBot_Data_Migration_Runbook.md`, and
  `docs/Google_Drive_Service_Account_Owner_Run_MVP.md` provide focused,
  human-run operational gates.
- The July 2026 `PROJECT_LOG.md` entries cited above prove examples of exact-SHA
  verification, rollback references, startup/polling health, smoke checks, and
  error scans.

Missing evidence:

- The ignored live owner-run server file described by
  `docs/local-only/README.md` is not present in this checkout.
- No tracked general production rollback command or validated automatic
  rollback interface exists.
- No runtime-readable deployed-SHA source exists.
- No approved machine interface authorizes an agent to merge, deploy, restart,
  or roll back production.
- Exact issue-specific production smoke commands cannot be known before the
  implementation exists.

The proposed runbook therefore references proven gate types but labels exact
unproven private commands and paths as:
“Private operational evidence required before implementation/deployment.”
Their absence from the public repository is intentional and is not, by itself,
an Architecture Design Proof blocker.

## Private operational evidence boundary

### Public repository architecture evidence

The public repository must contain the product and architecture contract,
trusted-owner boundaries, abstract deployment and rollback gates, test
requirements, status truth, security constraints, and evidence expected in
`PROJECT_LOG.md`. The tracked scripts, Docker composition, public runbooks,
tests, current code owners, and recent deployment records listed above are
sufficient to define those abstract gates without disclosing production
access.

### Private server/runbook evidence not present

Environment-specific server addresses, SSH details, credentials, secrets,
private filesystem and backup paths, sensitive commands, live service
identifiers, and recovery procedures are intentionally outside the public
repository. A later phase may receive them through a separately mounted private
operations folder. That folder is operational evidence only; it cannot override
the approved public architecture, policy, Product Truth, or code owners.

### Required before implementation

- A trusted interface by which the future implementation can obtain or record
  the deployed build SHA without accepting it from untrusted issue text.
- The public service/CLI boundaries and authorization model for issue claims,
  result recording, and notification enqueue.
- Approved public retention, redaction, and workspace-scope rules.
- Resolution of the public human-approval versus unattended merge/deploy
  contradiction.

If materialization of a trusted SHA interface depends on a private runtime
mount or service, then: **Private operational evidence required before
implementation/deployment.**

### Required only before production deployment

- Evidence that the exact production SHA can be read and verified.
- Evidence that repository and server worktrees are clean.
- A current rollback reference and the approved private rollback procedure.
- Controlled deploy, startup/polling health, issue-specific smoke, error-scan,
  and exact-SHA verification instructions.
- The identity and least-privilege authority of the production operator.

For all of these: **Private operational evidence required before
implementation/deployment.** They do not block approval of a complete public
architecture design; they do block any deployment claim until supplied and
verified.

### Information that must never be committed publicly

- Server addresses, usernames, SSH material, access tokens, bot credentials,
  API keys, secrets, or unredacted environment dumps.
- Private filesystem, backup, credential, or certificate paths.
- Sensitive production commands or provider-specific recovery details.
- Raw production logs containing personal, financial, tenant, token, or
  message content.
- Contents of the separately mounted private operations folder.

## Reusable mechanisms

- Outer general authorization and explicit Python admin checks.
- Bounded canonical-action resolution and `allowed_actions` pattern.
- Shared active-FSM global-control middleware and voice-to-text convergence.
- Read-only workspace resolution and membership enforcement.
- SQLite domain-service pattern with explicit transactions.
- Archive-job atomic claim/lease/retry design.
- Callback acknowledgement, stale-payload rejection, and idempotency patterns.
- Deterministic canonical contact resolver and trusted contact identity.
- Existing focused, adjacent, Conversation Acceptance Proof, deployment-smoke,
  and project-log evidence conventions.
- Tracked clean-update/deploy scripts as partial human-run operational
  evidence.

Reuse means a future implementation follows the pattern and its safety
properties; it does not repurpose unrelated domain tables or bypass their
owners.

## Mechanisms that do not currently exist

- `report_runtime_issue` in the canonical action registry or Product Truth.
- `/issue` command registration or natural-language/voice issue routing.
- A no-FSM issue persistence service and SQLite record.
- A global issue interrupt proven to leave state, data, and activity metadata
  byte-for-byte/semantically unchanged.
- A trusted runtime build-SHA source.
- A central sanitized structured-event/log-evidence service.
- Runtime-issue claim/status/manifest/result CLI or service.
- A generic idempotent retryable bot notification outbox.
- An external once-daily maintenance scheduler with approved server access.
- An approved unattended commit/merge/deploy/rollback authority.
- A global LLM/Work/Codex autorepair contract.

## Design-to-runtime contradictions

### Human approval versus unattended repair

The proposed target eventually allows a maintenance process to commit, merge,
and deploy an eligible repair. Current policy does not:

- `docs/Code_Agent_Handoff_Contract.md`, sections “Agent Output Requirements”
  and “Human Approval Gates”, says agent output is not approval and requires
  human approval before merging code, deploying runtime changes, running
  repairs, and changing server state.
- Its “Acceptance Criteria For Handoff Layer” requires code-agent output to be
  reviewed before merge/deploy and forbids automatic production side effects.
- `docs/Evaluation_and_Smoke_Test_Standards.md`, “Conversation Acceptance
  Proof”, says `safe_to_commit` is not merge or deploy approval.
- `AGENTS.md` keeps deterministic tests and human approval for agent-generated
  work.

Impact: the daily process may claim, diagnose, classify, produce bounded
evidence, and notify. Automatic repair merge/deploy cannot be an approved V1
path until a product owner approves a narrowly scoped policy change and its
authority/audit controls. This contradiction drives
`needs_architecture_revision`.

### Active-FSM exact preservation

`bot/services/active_fsm_guard.py::handle_active_fsm_text_update` supports only
the established global controls. The middleware calls
`touch_active_fsm_activity` after a downstream active-state handler, and the
2026-07-09 project-log entry explicitly deferred general fresh top-level
switching.

Impact: a future issue interrupt must be a narrow shared-guard branch that
returns as handled before state-specific dispatch and before the activity
stamp. It must neither use the existing “clear and route idle” stale path nor
the current downstream pass-through path. Tests must compare both FSM state and
business data before/after, including activity metadata.

### Administrator voice boundary

General unauthorized users are rejected before STT. For an already authorized
non-admin user, the system cannot know that a voice message expresses an admin
issue intent until after STT. Enforcing “admin before STT” for that semantic
case would require either banning all non-admin voice or a new trusted
pre-transcription signal.

Impact: keep the proven general authorization-before-STT boundary, then perform
the admin check immediately after transcription and before issue-intent LLM
resolution, persistence, or diagnostic lookup. A reviewer must accept this
precise boundary or require an explicit admin-only voice entry mode.

### User-facing language

Current product text policy is Slovak-first/Slovak-only, while the proposed
examples are Ukrainian. This package specifies Slovak target copy and treats
Ukrainian examples as intent examples.

Impact: a product owner must approve either the Slovak copy or an explicit
administrator-language exception before Product Truth is changed.

## Missing evidence

- Approved exception, if any, to human review before repair merge/deploy.
- Exact trusted production SHA source and its freshness/failure contract.
- Available, sanitized, bounded server-log query owner.
- Generic notification outbox and bot delivery worker semantics.
- External scheduler/runner identity, credential boundary, and server access.
- Proven database migration owner for the future records.
- Retention periods, description/evidence size limits, and redaction rules.
- Whether `workspace_id` may be null when the admin has no unambiguous active
  workspace.
- Whether `occurred_at` is useful enough for V1 without creating clarification
  state.
- Whether activity timestamps are part of “business FSM data” for exact
  preservation; this package conservatively treats them as protected.

Private production commands, paths, credentials, and environment-specific
rollback details are intentionally not listed as missing public architecture
evidence. They are deferred production inputs.

## Readiness effect

The repository supports an evidence-backed design for the intake action and for
diagnostic-only daily processing. It does not currently support the full
unattended autorepair authority. The absent private operations material does
not block architecture approval. The unresolved public policy contradiction
over unattended merge/deploy, plus the public product decisions identified in
the proof, drive `needs_architecture_revision`; no implementation handoff is
permitted.
