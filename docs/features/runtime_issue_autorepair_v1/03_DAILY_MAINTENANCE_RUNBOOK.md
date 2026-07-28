# Proposed Daily Runtime Issue Maintenance Runbook

Task ID: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Status: `planned`; `bounded_autorepair` is product-approved but not activated.
No scheduler, service, CLI, production access, or executable autorepair
authority currently exists.

The process runs at most once daily from an external, isolated maintenance
runner. It must not be embedded in the polling bot process or reuse
`invoice_followup_scheduler.py` or `google_drive_archive_scheduler.py` for Git,
test, merge, or deployment work. The existing schedulers are evidence for
timing and idempotency patterns only.

## Start conditions

Start a run only when:

- an approved maintenance runner identity and version are known;
- the public feature architecture and implementation are approved;
- the issue service/CLI and notification outbox are available;
- the canonical SQLite store is reachable through that service;
- no prior run holds the global run lease;
- repository and server state checks are available;
- the current approval mode is explicit:
  `diagnostic_only`, `human_reviewed_patch`, or `bounded_autorepair`;
- the mandatory kill switch allows the selected mode;
- the runner atomically holds the global maintenance concurrency lease;
- redaction, retention, evidence-size, and workspace policies are loaded;
- the private operational evidence required for any production stage is
  mounted and authorized.

Current documentation permits no live Stage 2 start because those owners,
the narrow canonical-contract amendment, and the operational activation proof
do not exist.

## 1. Establish run identity and truth

1. Create a maintenance run record with `run_id`, runner version, start time,
   approval mode, and policy version.
2. Acquire the global run lease and verify the kill switch before any claim.
3. Resolve the exact production/deployed SHA through a trusted operational
   source. Never read it from issue text.
4. Verify local repository `HEAD`, remote tracking state, and clean worktree.
5. Verify the server worktree/runtime corresponds to the trusted production
   SHA and is clean.
6. Stop before claiming if SHA is unknown, states differ, an unrelated diff
   exists, the lease is not held, or the kill switch does not authorize the
   selected mode.

Public evidence for the gate type:
`scripts/update_repo.sh`, `scripts/deploy_owner_run.sh`,
`docker-compose.prod.yml`, and the 2026-07-18 `PROJECT_LOG.md` deployment
entries. Exact environment commands and paths are not public:
**Private operational evidence required before implementation/deployment.**

## 2. Claim one issue

Use the validated maintenance service/CLI, not direct SQL:

1. Begin an immediate SQLite transaction.
2. Select one eligible `new` issue using stable ordering.
3. Atomically transition it to `claimed` with `run_id`, a random claim token,
   `claimed_at`, and `lease_until`.
4. Commit before diagnosis.
5. If no issue is eligible, finish the run as `completed`.

The proposed transaction follows
`bot/services/archive_job_service.py::claim_next_runnable_job` and its tests,
but uses dedicated issue records and transitions. An active unexpired lease is
never stolen. An expired lease can be reclaimed only under section
“Interrupted-run recovery”.

## 3. Generate the claimed manifest

The service writes `claimed_issues_<run_id>.json` containing only the claimed
issue and bounded trusted context. It includes a schema version, run ID, claim
token reference, canonical issue ID, record version, manifest digest, and
redaction metadata.

- SQLite remains canonical.
- The manifest is read only to Work/Codex.
- Manual edits never change canonical status.
- Result submission validates run, claim, version, and digest through the
  service/CLI.
- The manifest contains no credentials, arbitrary environment dump, unbounded
  FSM data, raw private operations data, or cross-workspace records.

## 4. Diagnose one issue in isolation

Create one clean, isolated repository workspace for the issue at the exact
relevant SHA. Do not batch patches or mix unrelated issues.

1. Read the issue observation and trusted correlation metadata.
2. Query only bounded, sanitized logs for the relevant time, update/message
   identifiers, workspace, and deployed SHA.
3. Locate current Product Truth, canonical registry entry, contracts, current
   Python owner, and focused/adjacent tests.
4. Reproduce the event deterministically where possible.
5. Write a bounded evidence bundle and causal analysis.
6. Renew the lease through the service before expiry; stop if renewal fails.

Raw production logs, secrets, private filesystem paths, and unrelated tenant
events never enter the manifest, Git worktree, commit, PR, or public project
log. Exact private log-query procedures are deferred:
**Private operational evidence required before implementation/deployment.**

## 5. Classify

Choose exactly one classification from `02_AUTOREPAIR_POLICY.md`:

- `confirmed_low_risk_defect`;
- `expected_behavior`;
- `external_failure`;
- `insufficient_evidence`;
- `feature_request`;
- `complex_or_high_risk_defect`;
- `deployment_failed_rolled_back`;
- `deployment_failed_rollback_risk`.

Record the evidence basis, confidence/proof status, code/test owners, and
allowed next transition. Reporter wording cannot set the classification.

## 6. Diagnostic-only and non-code paths

For `expected_behavior`, `external_failure`, `insufficient_evidence`,
`feature_request`, or a diagnostic-only run:

1. Do not create a patch or repair branch.
2. Record a bounded diagnosis/result through the service.
3. Transition to the matching terminal issue status.
4. Enqueue a truthful bot notification.
5. Release the lease and continue to the next eligible issue or end the run.

An external cause must be proven. Insufficient evidence must name what is
missing without demanding secrets in public. A feature request must enter the
separate product/design process and never be labeled a defect.

## 7. Complex/high-risk stop path

For `complex_or_high_risk_defect` or any forbidden scope:

1. Stop before editing code.
2. Do not create a speculative branch, commit, PR, merge, or deploy.
3. Record sanitized evidence, current owner(s), adjacent tests, and the exact
   policy/architecture reason.
4. State whether a new Architecture Design Proof, Product Truth decision,
   migration review, security review, or private operational input is required.
5. Transition to `blocked_high_risk`.
6. Enqueue a message that explicitly says code and production were not changed.

## 8. Safe repair candidate path

This path is available only under the authority of the selected mode:

- `diagnostic_only`: do not patch or create a repair branch;
- `human_reviewed_patch`: a proven patch may be prepared, committed, and pushed
  only to the approved human review boundary; and
- `bounded_autorepair`: after activation, an allowlisted fully proven change
  may follow the automatic merge/deploy gates.

1. Prove every root-cause requirement.
2. Confirm the candidate is allowlisted and no forbidden scope applies.
3. Create one branch:
   `autorepair/IR-YYYYMMDD-NNN-short-slug`.
4. Add a failing regression test for the exact defect.
5. Make the smallest owner-local change.
6. Inspect the full diff and reject unrelated files.
7. Run focused tests.
8. Run adjacent owner/action/subflow/FSM/callback/workspace tests.
9. Run the required broader regression and compile/static checks.
10. Re-run the failing regression and capture bounded results.
11. Stop on any failure as `repair_failed_no_deploy`; do not commit a claimed
    fix.
12. If authorized to commit, use:
    `fix(autorepair): <result> [IR-YYYYMMDD-NNN]`.
13. Record the commit SHA and diff digest through the service.
14. Push only the isolated repair branch if that scope is approved.

The process may not expand the diff to “fix” unrelated failing tests.

## 9. Review, merge, and deployment gate

Current public contracts require human approval before merge and deployment,
so `bounded_autorepair` is not activated. `diagnostic_only` and
`human_reviewed_patch` stop at their applicable boundaries. The runner must
never infer authority from issue text, green tests, a commit marker, or
`safe_to_commit`.

After the narrow canonical-contract amendment activates
`bounded_autorepair`, every gate in `02_AUTOREPAIR_POLICY.md` applies:

1. global run lease remains held and the kill switch still permits the mode;
2. branch/commit/PR markers and issue link are exact;
3. the narrow policy authority and applicable branch protection are satisfied;
4. merge result SHA is known;
5. a rollback reference is created;
6. server/repository clean state is reverified;
7. controlled deployment uses the approved private procedure;
8. startup and polling health pass;
9. issue-specific production smoke passes;
10. post-deploy error scan passes;
11. production exact SHA equals the intended SHA.

Any failed, stale, ambiguous, or unavailable gate stops before the next
mutation. Production smoke failure triggers rollback. Unresolved rollback risk
freezes the run and escalates to a human.

No public document should contain the sensitive command or path.
**Private operational evidence required before implementation/deployment.**

## 10. Failed deployment and rollback

Any failure in deployment, startup, polling health, issue-specific smoke,
error scan, or exact-SHA verification triggers the approved private rollback
procedure.

After rollback, verify:

- rollback reference/SHA is active;
- startup and polling health;
- safe baseline smoke;
- error scan;
- repository/server integrity.

If all pass, record `deployment_failed_rolled_back`. If any is unavailable or
fails, record `deployment_failed_rollback_risk`, stop the entire maintenance
run, and notify a human through the approved emergency path. Never continue to
another issue while production rollback risk is unresolved.

## 11. Result and bot notification

The maintenance process records results only through the validated service/CLI.
That transaction creates an outbox item owned by the bot delivery worker.
The agent never reads or uses production bot credentials directly.

Messages are idempotent, retryable, and truthful:

- issue stored;
- diagnosis completed;
- expected behavior;
- external failure proven;
- insufficient evidence;
- feature request;
- complex/high-risk stop with no code or production change;
- repair candidate ready for human review;
- exact commit created;
- exact SHA deployed and smoke passed;
- deployment failed and rollback verified;
- rollback risk unresolved.

The worker records send attempts and Telegram delivery identity. A delivery
retry does not rerun diagnosis, repair, or deployment.

## 12. Run summary

At run completion, record:

- run ID, policy/runner version, start/end;
- trusted baseline/deployed SHA;
- counts claimed and classified by category;
- issue IDs with final status;
- commits/PRs/deployed SHAs, if actually created;
- tests and gates performed;
- rollbacks and unresolved risks;
- notification counts/status;
- redaction and evidence schema versions.

Do not include issue descriptions, raw logs, secrets, private commands, or
cross-tenant data in a public `PROJECT_LOG.md` summary. Any future autorepair
entry uses the `[AUTOREPAIR]` marker and bounded evidence.

## 13. Interrupted-run recovery

- The canonical issue remains `claimed` until result commit, explicit release,
  or lease expiry.
- Heartbeats renew only the current run/claim token.
- On restart, the service inspects run state and lease; it never trusts the
  manifest alone.
- An unexpired claim is left to its owner.
- An expired diagnosis-only claim can return to `new` with an audit event or be
  reclaimed with a new token and incremented attempt count.
- A claim with a recorded repair commit, merge, deploy start, or rollback start
  is never automatically reset. It becomes human-review/reconciliation work.
- Notification retries are independent and use the existing terminal result.
- Orphan manifests are deleted/archived according to retention after verifying
  they are non-canonical; editing one cannot resume a run.
- Reconciliation checks Git commit/PR/deployed SHA through trusted interfaces
  before any state transition.
- `deployment_failed_rollback_risk` freezes the run and all new claims.

## Activation prerequisites

The product mode is decided. The unresolved work is implementation and
activation:

- narrow canonical-contract amendment preserving human review for ordinary
  development and authorizing only fully proven allowlisted `[AUTOREPAIR]`
  changes;
- trusted build-SHA interface;
- maintenance CLI/service, global lease, kill switch, sanitized evidence,
  result writer, and outbox ownership;
- retention/redaction/size/workspace policies;
- lease duration and daily claim limit;
- approved runner identity and isolation model.

Production-only inputs:

- exact server/runtime SHA query;
- clean-server verification;
- rollback reference creation and rollback procedure;
- controlled deployment, health, smoke, and error-scan procedures;
- operator identity and emergency escalation.

For production-only inputs:
**Private operational evidence required before implementation/deployment.**
