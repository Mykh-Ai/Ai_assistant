# Runtime Issue Autorepair V1 Policy

Task ID: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Status: `approved_design_pending_implementation`

This policy governs the scheduled ChatGPT Work/Briefing maintenance process after an administrator report has been captured by Stage 1. It implements the approved ownership split:

```text
OfficeFlow owns production intake.
GitHub owns diagnosis, findings, repair backlog, code changes, and review artifacts.
```

Stage 2 starts only through bounded server interfaces. The worker must not query or mutate production SQLite directly.

## 1. Operating mode

Initial executable mode:

```text
human_reviewed_patch
```

Under this mode the worker may diagnose, create findings, add a regression test, make an allowlisted low-risk repair, commit, push, and create a Draft PR.

It may not automatically merge, deploy, restart production, migrate a database, roll back production, or change production business data.

## 2. Unit of diagnosis and repair

A Stage 1 issue is an administrator observation, not a diagnosis.

One source issue may produce:

- zero findings when no defect or actionable work is established;
- one finding;
- multiple independent findings.

Findings may be created only after bounded evidence, code, Product Truth, and tests have been inspected. The worker must not split an issue merely because the original text contains several sentences.

Every finding receives a stable identifier:

```text
{issue_id}-F01
{issue_id}-F02
...
```

Each finding has its own classification, status, log reference, owner scope, and next action.

## 3. Approved classifications

- `confirmed_low_risk_defect`
- `expected_behavior`
- `external_failure`
- `insufficient_evidence`
- `feature_request`
- `complex_or_high_risk_defect`
- `authorized_data_correction_required`

The reporter's words such as “bug”, “internet”, “STT”, “fixed”, or “three problems” are observations only. They do not set classification.

## 4. Workshop finding statuses

- `received_for_diagnosis`
- `diagnosing`
- `needs_more_diagnostics`
- `queued_for_repair`
- `repair_in_progress`
- `patch_ready_for_review`
- `resolved_expected_behavior`
- `resolved_external_failure`
- `resolved_no_code`
- `requires_architecture_design`
- `requires_product_decision`
- `requires_authorized_data_correction`
- `blocked_by_security_boundary`
- `blocked_by_accounting_truth`
- `insufficient_evidence`
- `branch_pushed_pr_blocked`
- `repair_failed_no_patch`

Do not use vague machine statuses such as `not_my_competence`. The exact reason belongs in a bounded log entry and one of the explicit statuses above.

`patch_ready_for_review` means the patch is tested, committed, pushed, and represented by a Draft PR. It does not mean merged or deployed.

## 5. Safe repair allowlist

A finding may become `confirmed_low_risk_defect` and enter `queued_for_repair` only when evidence proves a local deterministic defect such as:

- missing Telegram callback acknowledgment;
- keyboard not removed after a completed action;
- missing terminal message after a proven successful action;
- narrow incorrect Product Truth wording with unambiguous current truth;
- narrow exception handling at an existing owner;
- missing bounded structured diagnostic event;
- one equivalent path failing to reuse an existing approved helper, resolver, normalizer, alias service, or canonical utility;
- a bounded semantic hint/example correction that does not change canonical action architecture;
- a similarly local defect with a clear regression test, bounded side effects, no ownership change, and no public journey redesign.

Allowlist membership is necessary but not sufficient. Root cause, exact owner, regression test, diff, and all required tests must still pass.

## 6. Forbidden unattended scope

The worker must not patch, create a speculative repair branch, or claim success when the work materially affects:

- database schema or migration;
- arbitrary SQL or direct production SQLite mutation;
- production contact, invoice, payment, accounting, or business data;
- top-level, subflow, FSM, callback, or product architecture;
- authorization, roles, tenant, or workspace isolation;
- OAuth, credentials, tokens, encryption, or secrets;
- invoice numbering, amounts, taxes, settlement, or accounting truth;
- deletion, retention, destructive behavior, or storage migration;
- bank matching or reconciliation;
- infrastructure, DNS, Cloudflare, network routing, or production credentials;
- dependency, framework, language runtime, or service upgrade;
- broad router/dispatcher refactor;
- ambiguous Product Truth;
- behavior outside current approved architecture.

A verified stale contact or company record becomes `requires_authorized_data_correction`; it is not silently edited by the worker.

A top-level/FSM requirement becomes `requires_architecture_design`; the worker records owners/evidence/tests but does not create a patch.

## 7. Root-cause proof requirements

Before code editing, the finding must be tied to:

1. a durable acknowledged source handoff in the GitHub workshop;
2. a stable finding ID and workshop log reference;
3. the exact relevant repository SHA and available production SHA truth;
4. bounded sanitized server evidence or deterministic reproduction;
5. current code symbol(s) that own the behavior;
6. current Product Truth, contract, registry entry, or deterministic invariant;
7. a specific causal mechanism;
8. a regression test that fails before the fix and passes after it;
9. evidence that no competing owner or unrelated diff is involved.

Missing logs are not proof of expected behavior. A plausible code smell is not proof of root cause.

## 8. Evidence policy

The evidence wrapper may return only bounded, sanitized facts correlated by trusted issue context:

- reported timestamp and approved time window;
- Telegram update/message identifiers;
- workspace scope, including valid null workspace;
- active FSM when present;
- `fsm_context_status=not_active` when no FSM was active;
- `fsm_context_status=read_failed` when technical reading failed;
- STT transcript or STT error only when actually logged;
- semantic action/result only when actually recorded;
- bounded Python exception/error events;
- Docker startup/restart/health facts;
- provider/network timeout or HTTP status when recorded;
- exact SHA facts from trusted interfaces.

Raw logs, `.env`, tokens, credentials, private keys, full user records, and cross-workspace events never enter GitHub workshop files or PRs.

## 9. Daily limits and backlog

Default V1 limits:

```text
new_handoff_limit_per_run = 3
code_repair_limit_per_run = 1
backlog_carries_forward = true
```

Old unresolved findings do not expire merely because no new issue arrives. The next scheduled run must inspect the workshop queue before concluding there is no work.

## 10. Git and GitHub gates

Workshop branch:

```text
maintenance/runtime-issue-workshop
```

Repair branch:

```text
autorepair/IR-YYYYMMDD-NNN-FNN-short-slug
```

Commit:

```text
fix(autorepair): <bounded result> [IR-YYYYMMDD-NNN-FNN]
```

Rules:

- repair branches start from the approved current `main` SHA, not from the mutable workshop branch;
- a local commit without push is incomplete;
- a pushed branch without Draft PR is `branch_pushed_pr_blocked`;
- unrelated changes are forbidden;
- failing unrelated tests must not be “fixed while here”;
- no force-push of `main` or the workshop branch;
- no private server facts or raw issue text in public PR content.

## 11. Required tests

For a repair candidate:

- exact failing regression test;
- existing unit/integration tests for the owner;
- explicit negative case outside the finding;
- adjacent action/subflow/FSM/callback/workspace tests chosen from the dependency graph;
- required broad repository suite;
- compile/static checks;
- full diff inspection.

A test infrastructure failure is a failed gate.

## 12. Truthful result reporting

Allowed claims only when verified:

- issue received in workshop;
- diagnosis completed;
- source issue decomposed into a specific number of findings;
- classification and evidence basis;
- code and production unchanged;
- repair queued;
- exact commit pushed;
- Draft PR created;
- expected behavior;
- external failure proven;
- insufficient evidence;
- architecture/product/data boundary;
- notification queued/sent.

Forbidden claims:

- guaranteed repair;
- confirmed defect based only on the report;
- STT/network/Docker/provider cause without evidence;
- “fixed” when only a diagnosis or local patch exists;
- deployed when production was not changed and verified;
- data updated without verified authorized mutation;
- “no code change” after creating a branch/commit.

## 13. Notification boundary

The worker never reads the production bot token. It calls only a bounded notification bridge with a template enum and validated fields. Telegram copy is concise business Slovak. Delivery retries must not rerun diagnosis or repair.
