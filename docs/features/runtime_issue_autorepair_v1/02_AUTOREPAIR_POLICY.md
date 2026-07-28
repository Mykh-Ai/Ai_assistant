# Runtime Issue Autorepair V1 Policy

Task ID: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Status: `planned`; product target mode `bounded_autorepair` is approved but not
activated. This is not executable authority to change code or production.

This policy governs a future daily process over issues created by
`report_runtime_issue`. It is not the future global LLM/Work/Codex autorepair
contract. The future operating modes are:

- `diagnostic_only`;
- `human_reviewed_patch`; and
- `bounded_autorepair`.

In future `bounded_autorepair`, an obvious local defect may automatically
commit, push, merge, deploy, verify, and notify only when every
machine-verifiable gate in this policy passes. Ordinary features and complex,
high-risk, ambiguous, or non-allowlisted defects remain under human review.

Current repository policy still requires human approval before merge and
deployment. A narrow canonical-contract amendment plus the public and private
activation prerequisites below are therefore required before this approved
target mode becomes executable.

## Classification model

Intake records an observation, not a diagnosis. A maintenance result must use
one of these classifications:

| Classification | Meaning | Code-change eligibility |
|---|---|---|
| `confirmed_low_risk_defect` | Current deployed behavior is proven to violate current Product Truth or a deterministic invariant, and the fix is local and allowlisted. | Potentially eligible only after all gates. |
| `expected_behavior` | Evidence proves the observed result is current intended behavior. | No patch. |
| `external_failure` | Bounded evidence proves a network/provider/external dependency caused the event. | No speculative product patch; a narrow existing retry/error-handling defect may be separately classified only with proof. |
| `insufficient_evidence` | The event cannot be correlated or reproduced well enough to establish root cause. | No patch. |
| `feature_request` | The report asks for behavior not present in approved Product Truth. | No patch; separate product/design process. |
| `complex_or_high_risk_defect` | A defect is plausible/proven but the repair crosses a forbidden boundary or lacks bounded ownership. | No patch; separate Architecture Design Proof/review. |
| `deployment_failed_rolled_back` | A candidate passed pre-deploy gates, production verification failed, and the approved rollback was proven successful. | No success claim; keep issue unresolved/reviewable. |
| `deployment_failed_rollback_risk` | Production verification failed and rollback is incomplete or unproven. | Emergency human escalation; no further agent changes. |

The administrator’s words “bug,” “provider,” or “fixed” are evidence only of
what was reported. They do not determine classification.

## Safe autorepair allowlist

A candidate can be `confirmed_low_risk_defect` only when current owners and
tests prove a small, deterministic repair such as:

- missing Telegram callback acknowledgement;
- keyboard not removed after a completed action;
- missing terminal message after a proven successful action;
- narrow incorrect Product Truth wording with unambiguous current truth;
- narrow exception handling at an existing owner;
- missing bounded structured diagnostic event;
- one equivalent path failing to reuse an existing approved resolver,
  normalizer, alias service, callback helper, or canonical utility;
- a similarly local defect with a clear regression test, bounded side effects,
  no ownership change, and no public journey redesign.

Allowlist membership is necessary but insufficient. The exact diff and all
affected behavior must also remain outside every forbidden area.

Example: analytics may reuse the current canonical contact resolver and filter
the current dataset by trusted `contact_id` only if evidence proves that this
is the existing identity contract, workspace isolation and ambiguity behavior
remain unchanged, analytics remains read only, and focused plus adjacent
analytics/contact tests pass. The example does not authorize a contact
resolution redesign.

## Explicit forbidden scope

The maintenance process must stop without patch, repair branch, commit, merge,
or deploy if the proposed change requires or materially affects:

- database schema, data repair, or migration;
- top-level, subflow, FSM, callback, or product architecture;
- authorization, access roles, tenant, or workspace isolation;
- OAuth, scopes, credentials, tokens, secrets, or encryption;
- invoice numbering;
- invoice amounts, taxes, accounting semantics, or bank settlement truth;
- deletion, destructive data behavior, retention migration, or storage
  migration;
- bank matching or reconciliation;
- infrastructure, DNS, Cloudflare, network routing, or production credentials;
- dependency, language runtime, framework, or service upgrade;
- broad dispatcher/router refactor;
- ambiguous Product Truth;
- any behavior not safely bounded by current approved architecture.

The process may preserve sanitized evidence and name the relevant owners/tests.
It must not produce a speculative patch.

Database/schema migrations remain forbidden for unattended Stage 2 repair.
That rule governs a maintenance agent; it does not block the separately
reviewed additive dedicated-table implementation for
`RUNTIME_ISSUE_INTAKE_V1`.

## Root-cause proof requirements

Before any code edit, the issue must be tied to:

1. an atomically claimed canonical issue record;
2. the exact deployed production SHA at the event or a proven relevant SHA;
3. bounded, sanitized event/log evidence or a deterministic reproduction;
4. current code symbol(s) that own the behavior;
5. current Product Truth, contract, registry entry, or deterministic invariant
   that proves expected behavior;
6. a specific causal mechanism, not correlation or user wording;
7. a regression test that fails for that mechanism before the fix and passes
   after it; and
8. evidence that no competing current owner or unrelated diff is involved.

“Cannot reproduce,” missing event correlation, ambiguous product intent, and a
plausible code smell are insufficient. They classify as
`insufficient_evidence` or `complex_or_high_risk_defect`.

## Mandatory evidence gate

Every item is required for a successful autorepair claim:

- exact current production/deployed SHA known;
- repository and server worktrees clean;
- no unrelated diff;
- issue atomically claimed;
- root cause reproduced or otherwise proven;
- minimal bounded diff;
- risk classified as allowed low-risk autorepair;
- regression test added for the reported defect;
- focused tests passed;
- adjacent action/subflow/FSM/callback tests passed;
- required broader regression passed;
- compile/static checks passed;
- no forbidden schema/config/secret/dependency changes;
- rollback reference created;
- controlled deploy completed;
- startup and polling health confirmed;
- issue-specific production smoke passed;
- post-deploy error scan passed;
- production exact SHA verified.

Failure, absence, ambiguity, or staleness of any required item means there is no
successful autorepair. A candidate may end as diagnostic-only, blocked,
failed-no-deploy, rolled back, or rollback-risk, but never `fixed_deployed`.

Before any issue claim or repository mutation, the runner must also prove:

- the global Stage 2 concurrency lease is held; and
- the mandatory kill switch is enabled for this run and remains checkable
  before commit, merge, deploy, and each rollback-sensitive transition.

Lease loss or kill-switch activation freezes the run before the next mutation
and escalates according to the approved operational policy.

## Test requirements

### Focused

- New regression test reproducing the exact issue.
- Existing unit/integration tests for the changed owner.
- Explicit negative case proving no new effect outside the report.

### Adjacent

Run suites for neighboring action/subflow/FSM/callback/workspace paths, chosen
from the actual dependency graph. For issue-intake-adjacent work these include
authorization, tenant safety, active FSM guard, voice state routing, state
control, decision callbacks, invoice follow-up, customization admin, archive
claim/worker, contacts, and analytics as applicable.

### Broad

Run the repository-required broader suite from current public guidance.
`docs/Evaluation_and_Smoke_Test_Standards.md` owns Conversation Acceptance Proof
for public journey changes. Compile/static checks and any repository-wide test
command must be current and proven at execution time; this policy does not
freeze or invent a command.

No test may be skipped because the candidate appears obvious. A test
infrastructure failure is a failed gate.

## Change marking

Target convention:

- branch: `autorepair/IR-YYYYMMDD-NNN-short-slug`;
- commit: `fix(autorepair): <bounded result> [IR-YYYYMMDD-NNN]`;
- PR/merge title:
  `[AUTOREPAIR] <bounded result> [IR-YYYYMMDD-NNN]`;
- `PROJECT_LOG.md`: an entry containing `[AUTOREPAIR]`, issue ID, source and
  deployed SHAs, tests, rollback reference, smoke, and final truth.

The marker is an audit signal, not permission. Current human-review policy
still applies until the narrow Stage 2 amendment is approved and activated.

## Commit, merge, and deploy gates

### Diagnostic and patch preparation

After root-cause proof, a future process may prepare a minimal local patch only
if policy authority for that stage has been approved. It must start from the
exact relevant clean SHA, isolate one issue, reject unrelated changes, and
record a deterministic diff digest.

### Commit/push

Commit/push requires the root-cause, scope, regression, focused, adjacent,
broad, static, and forbidden-file gates to pass. The commit must carry the
canonical marker and issue ID. Failure means `repair_failed_no_deploy`.

### Merge/deploy

The product owner has approved bounded automatic merge/deploy for fully proven,
policy-allowlisted `[AUTOREPAIR]` changes. It remains disabled until a narrow
canonical-contract amendment and activation proof define:

- narrow authority and allowed repositories/branches;
- required review and branch-protection behavior;
- immutable audit identity;
- exact production SHA and clean-state interfaces;
- least-privilege deploy and rollback control;
- notification and emergency escalation;
- a mandatory kill switch and global concurrency lease.

The intended amendment must not weaken review for ordinary development. It
must state that:

- ordinary features and complex defects still require human review;
- only allowlisted, fully proven `[AUTOREPAIR]` changes may use the automatic
  path;
- any failed, stale, ambiguous, or unavailable gate stops before merge/deploy;
- production smoke failure triggers the approved private rollback procedure;
  and
- unresolved rollback risk freezes the run and escalates to a human.

The abstract deploy gate remains: controlled deployment, health, issue-specific
smoke, error scan, and exact production SHA. **Private operational evidence
required before implementation/deployment.**

## Rollback gates

A rollback reference must exist before deployment. Any failed startup,
polling-health check, issue-specific smoke, post-deploy error scan, or SHA
verification triggers the approved private rollback procedure. After rollback:

- verify the rollback SHA/image/reference;
- verify startup and polling health;
- repeat safe baseline smoke;
- scan errors;
- record whether rollback is proven successful.

Successful rollback produces `deployment_failed_rolled_back`, explicitly says
the fix was not deployed successfully, and keeps the issue unresolved or
reviewable. Unproven rollback produces
`deployment_failed_rollback_risk`, stops all agent activity, and alerts a human.
Private commands and paths must never enter this repository.

## Conditions that prohibit code changes

Do not patch, create a speculative repair branch, commit, merge, or deploy when:

- classification is anything other than a proven allowlisted
  `confirmed_low_risk_defect`;
- any forbidden scope applies;
- exact relevant SHA, clean state, claim, owner, Product Truth, reproduction,
  or regression test is absent;
- ambiguity or conflicting evidence remains;
- another repair/worktree/run owns overlapping files;
- required tests/static checks fail or cannot run;
- the diff grows beyond the proven root cause;
- credentials, secrets, raw logs, or cross-workspace data would enter evidence;
- current human approval or another required gate is absent.

After activation, the final bullet means the narrow Stage 2 authority itself or
any task-specific required human gate is absent; it does not reintroduce human
approval into a fully proven allowlisted automatic path.

Complex issues must identify the owner, evidence, tests, stop reason, and
required separate Architecture Design Proof or product decision. They must
explicitly report that code and production were not changed.

## Truthful result reporting

Allowed result facts, only when supported:

- issue stored;
- diagnosis completed;
- classification and bounded evidence basis;
- code and production unchanged;
- safe fix committed, with exact commit SHA;
- deployed exact SHA;
- focused/adjacent/broad tests passed;
- startup/polling and issue-specific smoke passed;
- external failure proven;
- insufficient evidence;
- complex/high-risk stop;
- rollback completed and verified;
- unresolved rollback risk.

Forbidden claims:

- guaranteed repair;
- confirmed defect based only on the report;
- Internet/provider cause without evidence;
- successful deployment without exact production SHA and verification;
- successful external upload/send without the actual supported result;
- successful rollback without post-rollback verification;
- “no code change” when a branch/commit was created;
- “fixed” when only a diagnostic event or candidate patch exists.

Notification delivery is idempotent and retryable through the proposed
bot-owned outbox. The maintenance agent never uses production bot credentials
directly.

## Policy approval boundary

`bounded_autorepair` is the approved Stage 2 product target. Activation remains
blocked until all of the following exist and are approved:

- the narrow amendment to `docs/Code_Agent_Handoff_Contract.md` and any
  directly affected canonical approval language in
  `docs/Evaluation_and_Smoke_Test_Standards.md`;
- issue claim/lease, global run lease, kill switch, sanitized evidence, result
  writer, and idempotent retryable bot-outbox owners;
- trusted deployed-SHA and clean-state interfaces;
- machine-verifiable allowlist, diff, test, deploy, smoke, error-scan, and
  rollback gates; and
- separately mounted private operational evidence with least-privilege owners
  and escalation.

The current public contracts remain unchanged by this feature-specific draft.
The maintenance agent may not infer the amendment or activate itself.
