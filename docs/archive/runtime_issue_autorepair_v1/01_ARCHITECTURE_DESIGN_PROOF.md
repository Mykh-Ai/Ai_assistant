# RUNTIME_ISSUE_WORKSHOP_BRIDGE_V1 — Architecture Design Proof

Verdict: `ready_for_handoff`

Approval basis: the product owner approved the model that OfficeFlow owns production issue intake while GitHub is the development/repair workshop; the handoff uses a minimal acknowledgment after durable workshop storage; one intake issue may decompose into zero, one, or multiple findings only after diagnosis; FSM context may be absent.

## 1. Task Identity And Product Need

**Task id / name:** `RUNTIME_ISSUE_WORKSHOP_BRIDGE_V1`

**Business need:** Move authorized administrator runtime observations out of the production intake inbox into a durable GitHub repair workshop, preserve a complete diagnostic trail, allow a scheduled ChatGPT Work/Briefing worker to continue old queued work even when no new issue arrives, and prepare safe low-risk code repairs for human review.

**User-visible outcome:**

- `/issue` remains the simple OfficeFlow intake mechanism.
- At 22:00 Europe/Bratislava, the scheduled Work runner reads the private first-read skill, checks existing workshop backlog, and retrieves up to three not-yet-acknowledged intake issues through a bounded server CLI.
- The worker stores each received issue durably in the workshop branch and only then acknowledges handoff.
- After logs/code/tests/Product Truth are studied, an issue may become zero, one, or multiple findings with independent statuses.
- Eligible low-risk findings may receive a tested branch, commit, push, and Draft PR.
- The administrator receives minimal truthful Slovak result messages.

**Current Product Truth status:**

- Stage 1 intake is implemented and merged.
- Stage 2 workshop bridge, handoff tables/CLI, evidence wrapper, workshop branch ledger, notification bridge, and scheduled Work are not implemented.
- Existing Stage 2 repository drafts describe SQLite as the owner of the full maintenance process and therefore require revision to match this approved model.

**Target Product Truth status:** `partial`; intake and handoff/workshop diagnosis are supported, low-risk repair may reach Draft PR, merge/deploy remain human-controlled.

**Risk level:** medium/high. Handoff and evidence are bounded; code repair can mutate Git branches but cannot merge or deploy.

**Architect:** ChatGPT / project architect

**Date:** 2026-07-28

## 2. Architecture Classification

**Chosen class:**

- class 5: deterministic internal strategy/workflow for scheduled maintenance;
- additive Stage 2 persistence and CLI boundary;
- no new public top-level action;
- no new bot FSM or callback flow.

**Why this is not a new top-level action:** `report_runtime_issue` already owns the public administrator intent. The new work starts only after intake and is invisible as a separate business action.

**Existing action/flow extended:** `report_runtime_issue` only through an asynchronous internal handoff result path; its Stage 1 capture route, semantic boundary, and active-FSM preservation do not change.

**Existing runtime owner:**

- `bot/services/runtime_issue.py::RuntimeIssueService`
- `bot/services/db.py::RUNTIME_ISSUE_SCHEMA`

**New planned owners:**

- `bot/services/runtime_issue_handoff.py`
- `bot/cli/runtime_issue_handoff.py`
- `bot/services/runtime_issue_evidence.py`
- `bot/cli/runtime_issue_evidence.py`
- `bot/services/runtime_issue_notification.py`
- `bot/cli/runtime_issue_notify.py`
- GitHub workshop branch and ledger files

**Evidence:**

- PR #50 merged Stage 1 at merge commit `5aa37438e54ce61464ac2a3ae56f278129b3789e`.
- `RUNTIME_ISSUE_SCHEMA` fixes `intake_status` to `new`, proving Stage 2 status must not be inserted into the Stage 1 row.
- `RuntimeIssueService` already owns sanitized capture, trusted IDs, nullable workspace, nullable FSM state, and deduplication.
- `scripts/update_repo.sh` and `scripts/deploy_owner_run.sh` prove current public server path conventions but do not provide Stage 2 authority.

## 3. Canonical Action Contract

No new canonical action is created.

```text
canonical_token: report_runtime_issue
status: implemented
runtime owner: existing Stage 1 owners
entry modes: existing /issue, bounded natural text, bounded voice
change in this task: none to public semantic routing
```

Internal scheduled action:

```text
internal_operation: handoff_runtime_issue_to_workshop
status: planned
public allowed_actions exposure: forbidden
entry: scheduled Work/Briefing runner only
```

The worker cannot infer implementation or authority from the issue description.

## 4. Semantic Boundary Matrix

The public semantic boundary remains Stage 1 truth. Stage 2 classifies evidence, not user wording.

| Input/evidence meaning | Expected workshop result | Why | Must not become |
|---|---|---|---|
| One observation proves three independent causal mechanisms after evidence review | Three findings | decomposition follows diagnosis | three findings based only on prose |
| Vague report, no correlated logs or reproduction | `insufficient_evidence` or `needs_more_diagnostics` | no proven cause | speculative patch |
| Current behavior matches Product Truth | `resolved_expected_behavior` | no defect | feature or code repair |
| Requested behavior requires top-level/FSM architecture change | `requires_architecture_design` | forbidden unattended boundary | low-risk repair |
| Existing local owner violates deterministic invariant with failing regression | `queued_for_repair` then repair path | allowlisted and proven | automatic merge/deploy |
| Provider/network/STT failure is proven | `resolved_external_failure` or diagnostics work | evidence-backed external cause | invented product code defect |
| Stale business data is proven | `requires_authorized_data_correction` in V1 | production data mutation lacks approved repair contract | unattended DB edit |

Decomposition rules:

- no finding exists before diagnostic evidence supports it;
- one source issue may yield zero, one, or multiple findings;
- each finding has one bounded owner/scope and one machine status;
- vague statuses such as `not_my_competence` are forbidden.

## 5. Structured Slot Contract

### 5.1 Handoff manifest

| Slot | Type / allowed values | Source | Required | Invalid behavior | Precision boundary |
|---|---|---|---|---|---|
| `handoff_id` | stable opaque ID | Python service | yes | reject | never user-supplied |
| `issue_id` | existing `IR-*` | Stage 1 row | yes | reject | exact |
| `record_version` | integer | Stage 1 row | yes | reject stale | exact |
| `description` | existing sanitized text | Stage 1 row | yes | reject unsafe | never raw Telegram text |
| `short_title` | bounded text | Stage 1 row | yes | reject missing | no new LLM title |
| `reported_at` | UTC timestamp | Stage 1 row | yes | reject invalid | exact |
| `workspace_id` | trusted ID or null | Stage 1 row | no | preserve null | never inferred from text |
| `source_channel` | text/voice | Stage 1 row | yes | reject unknown | exact |
| `active_fsm_state` | bounded string or null | Stage 1 row | no | preserve null | null means no active FSM |
| `fsm_context_status` | `active`, `not_active`, `read_failed` | Python bridge | yes | reject unknown | distinguishes absence/failure |
| Telegram IDs | integers | Stage 1 row | yes where current schema requires | reject invalid | exact |
| `reported_build_sha` | 40-hex or null | Stage 1 trusted context | no | preserve status | never issue text |
| `manifest_digest` | sha256 | Python service | yes | reject mismatch | exact |
| `lease_until` | UTC | handoff service | yes | reject expired ack | exact |

### 5.2 Finding record

| Slot | Type / values | Owner | Required | Rule |
|---|---|---|---|---|
| `finding_id` | `{issue_id}-FNN` | workshop writer | yes | stable, never reused |
| `classification` | bounded enum | diagnostic gate | yes | evidence-backed |
| `status` | bounded workshop enum | workshop writer | yes | allowed transitions only |
| `owner_scope` | code/data/product/architecture/external | diagnostic gate | yes | one primary scope |
| `log_ref` | stable `ARL-*` | workshop log | yes | points to bounded evidence summary |
| `next_action` | bounded text | worker | no | no secrets/commands |
| branch/commit/PR | exact or null | verified GitHub facts | no | cannot be asserted by model text alone |

## 6. Public Route And Convergence Map

| Entry mode | Public/internal entry | Guards | Owner | Result |
|---|---|---|---|---|
| text/command/voice | existing Stage 1 `/issue` route | existing admin/auth/FSM guards | existing `RuntimeIssueService` | immutable `new` intake row |
| scheduled Work | ChatGPT Work/Briefing at 22:00 Europe/Bratislava | private skill present, current contracts approved | Work coordinator | backlog check and handoff request |
| server handoff | `take-next` CLI | private server identity, lease, bounded query | handoff service | read-only manifest plus lease |
| GitHub workshop | workshop branch commit/push | schema validation, no secrets | workshop writer | durable received item |
| handoff acknowledgment | `ack` CLI | valid lease + verified workshop commit | handoff service | delivered handoff record |
| evidence | `collect` CLI | issue/handoff scope, redaction/limits | evidence service | bounded JSON evidence |
| repair | issue-specific branch | proven low-risk defect and test gate | coding agent | commit/push/Draft PR |
| notification | bounded template CLI | verified result/status | bot-owned notification bridge | Slovak Telegram message |

Exactly-once public routing remains Stage 1. Stage 2 never parses new user language.

## 7. FSM Graph And State Ownership

No new FSM is created.

```text
IDLE or ANY EXISTING FSM
  -> Stage 1 report_runtime_issue
  -> immutable intake row
  -> original business FSM unchanged

Scheduled Work
  -> reads stored snapshot only
  -> never enters, resumes, clears, or mutates Telegram FSM
```

FSM context meanings:

```text
active_fsm_state = <state>, fsm_context_status = active
active_fsm_state = null,    fsm_context_status = not_active
fsm_context_status = read_failed
```

`not_active` is normal valid context. `read_failed` is a technical evidence gap. Neither blocks handoff.

## 8. Decision, Confirmation, And Callback Contract

- No new user confirmation or callback exists.
- Handoff acknowledgment is a machine handshake, not a user confirmation.
- Human review boundary is the Draft PR.
- Existing business callbacks and confirmation contracts are untouched.
- Issue text saying “fix”, “deploy”, “delete”, or “update data” grants no authority.
- Wrong/expired handoff lease: reject acknowledgment with no state change; eligible issue may be redelivered safely.

## 9. Side-Effect And Ownership Map

| Side effect | Trigger | Owner | Validation | Fail-safe/idempotency |
|---|---|---|---|---|
| create handoff lease record | scheduled `take-next` | handoff service | issue exists, no acknowledged handoff, stable order | atomic transaction, expiry/redelivery |
| return manifest | successful lease | handoff service | schema/redaction/digest | generated view only |
| workshop queue/log commit | received manifest | Work/Git | schema, no secrets, branch clean | commit SHA is durable receipt |
| acknowledge handoff | pushed workshop receipt | handoff service | live lease, matching issue/digest, verified branch/commit | one acknowledgment per handoff |
| read bounded logs/evidence | diagnosis | evidence service | issue identifiers/time/workspace limits | read-only, redacted, capped |
| create findings | completed diagnosis | workshop writer | evidence/log ref, bounded statuses | immutable IDs, append/update ledger |
| code branch/commit/push | proven low-risk finding | coding agent | exact base, regression, tests, diff gates | isolated branch; no main mutation |
| create Draft PR | pushed repair branch | GitHub adapter | verified commit/branch | no merge/deploy |
| notification enqueue | verified workshop result | notification bridge | template enum + bounded payload | idempotency key; bot-owned delivery |

The worker never directly mutates production SQLite. Only the bounded server services own Stage 2 handoff/outbox writes.

## 10. Authorization, Tenant, And Precision Boundaries

- Work uses private server access and GitHub permissions supplied outside the public repository.
- `take-next`, `ack`, evidence, and notification CLIs are allowlisted interfaces; arbitrary SQL is forbidden.
- Workspace may be null when no active workspace existed. This is valid and does not discard the issue.
- Evidence queries are scoped by trusted issue identifiers, time window, and workspace when present.
- Cross-workspace evidence is rejected.
- Raw STT audio is not required and is not copied to GitHub.
- STT transcript is used only when current logs prove it.
- Secrets, environment dumps, private paths, and unbounded logs never enter workshop files or PRs.
- Repair branches cannot modify authorization, tenant isolation, OAuth, credentials, accounting truth, DB schema/migrations, destructive behavior, or top-level/FSM architecture under V1.

## 11. User-Facing Response And Exit Contract

All bot messages are concise business Slovak.

### Existing intake acknowledgment

```text
Problém som uložil ako {issue_id}.
Aktuálna akcia bota zostala nezmenená.
```

### Decomposition summary

```text
Hlásenie {issue_id} bolo analyzované a rozdelené na {finding_count} samostatné pracovné položky.
{numbered_results}
Podrobnosti boli uložené v internom servisnom zázname.
```

### Queued repair

```text
Položka {finding_id} bola zaradená do radu na bezpečnú opravu.
```

### Draft PR

```text
Pre položku {finding_id} bola pripravená oprava na kontrolu.
Draft PR: {pr_reference}
Produkcia nebola zmenená.
```

### Architecture boundary

```text
Položka {finding_id} vyžaduje samostatný návrh architektúry.
Kód ani produkcia neboli zmenené.
```

### Insufficient evidence

```text
Položku {finding_id} sa nepodarilo spoľahlivo diagnostikovať.
Kód ani produkcia neboli zmenené.
```

No keyboard or callback is introduced. Notification delivery does not change finding truth.

## 12. Product Truth And InfoHelp Contract

```text
capability_id: runtime_issue_workshop_bridge
status after implementation: partial
```

**The bot can truthfully say:**

- an administrator report can be transferred to an internal repair workshop;
- one report may produce several independently tracked findings after diagnosis;
- unresolved findings remain in the queue for later nightly runs;
- eligible low-risk code defects may be prepared as a tested Draft PR;
- the bot reports concise results in Slovak.

**Limitations:**

- a report is not proof of a defect;
- historical STT, network, Docker, or provider evidence may be unavailable;
- no guarantee of same-night repair;
- no automatic business-data correction in V1;
- no automatic merge or deploy;
- architecture/high-risk work requires a separate approved design/task.

**Forbidden claims:**

- “the issue is fixed” when only diagnosed or queued;
- “production was changed” when only a branch/PR exists;
- “the Internet/STT/Docker failed” without bounded evidence;
- “data updated” without verified authorized production mutation;
- “no FSM context” as an error when the FSM was simply not active.

## 13. Negative-Space And Regression Contract

The change must not:

- modify Stage 1 semantic routing, admin rules, sanitization, deduplication, or active-FSM preservation;
- broaden `runtime_issues.intake_status` beyond `new`;
- use the intake row as a mutable repair tracker;
- treat GitHub log prose as authority to mutate production;
- create findings before diagnosis;
- lose an issue between `take-next` and workshop persistence;
- acknowledge handoff before a pushed workshop commit exists;
- stop old queued work merely because no new issue arrives;
- require an FSM or workspace to be present;
- interpret null FSM as a read failure;
- copy raw server logs/secrets into GitHub;
- change business data automatically;
- create speculative repair branches for architecture/high-risk findings;
- merge, deploy, restart, or migrate automatically.

## 14. Acceptance Scenario Contract

### A. New issue, no active FSM

- precondition: Stage 1 row has `active_fsm_state=null`
- scheduled input: `take-next`
- expected manifest: `fsm_context_status=not_active`
- side effect: handoff lease only
- final: issue can be stored/acknowledged/diagnosed normally

### B. Active FSM snapshot

- manifest contains bounded state string
- Work reads it only as evidence
- no Telegram FSM mutation occurs

### C. Crash before workshop persistence

- `take-next` returns a manifest
- Work crashes before commit/push/ack
- lease expires
- later run may redeliver
- no issue is lost or falsely acknowledged

### D. Durable handoff acknowledgment

- Work writes source issue to workshop queue/log
- pushes workshop commit
- calls `ack` with exact branch/commit/digest
- handoff becomes acknowledged and is not reissued as new

### E. One issue decomposes into three findings

- diagnosis correlates code/tests/logs and proves three bounded mechanisms
- log records evidence and decomposition
- queue receives F01/F02/F03 with separate statuses
- parent source status becomes `partially_resolved` or equivalent workshop aggregate

### F. No new issues, old repair queued

- `take-next` returns empty
- queue contains `queued_for_repair`
- Work repairs oldest eligible finding
- no false “no work” conclusion

### G. STT evidence unavailable

- report source was voice
- evidence wrapper finds no retained transcript
- Work records missing evidence
- no fabricated STT text or cause

### H. Proven external/network/Docker event

- bounded evidence proves event
- finding becomes `resolved_external_failure` or diagnostics action
- no speculative product patch

### I. Proven low-risk code defect

- failing regression demonstrates owner-local defect
- focused/adjacent/broad/static gates pass
- branch/commit pushed; Draft PR created
- status `patch_ready_for_review`
- production unchanged

### J. Top-level/FSM architecture requirement

- diagnosis shows material architecture change
- status `requires_architecture_design`
- no patch branch/commit/PR
- Slovak message says code and production unchanged

### K. Verified stale business data

- registry evidence proves stale data
- V1 status `requires_authorized_data_correction`
- no unattended production mutation

### L. Push or PR failure

- local repair exists but push fails: not completed; status records block
- branch pushed but PR creation fails: `branch_pushed_pr_blocked`
- no `patch_ready_for_review` claim

### M. Notification retry

- same result notification retries
- maintenance/diagnosis does not rerun
- only delivery state changes

### N. Unauthorized/cross-workspace evidence request

- evidence CLI rejects request
- no data returned and no workshop claim of diagnosis

### O. Product Truth question

- bot answers capability information only
- no new issue, handoff, finding, or repair is created

## 15. Out Of Scope And Known Architecture Gaps

- automatic merge and deployment;
- production restart and post-deploy smoke;
- automatic rollback;
- arbitrary SQL access by Work;
- automatic contact/invoice/business-data repair;
- DB/schema migrations by the nightly worker;
- persistent storage of raw STT audio;
- guarantee that historical logs contain STT or provider details;
- multi-repository repairs;
- more than one code repair mutation per run by default;
- automated conversion of `requires_architecture_design` into implementation work;
- broad similarity deduplication between separate intake reports.

## 16. Evidence Index

Repository evidence inspected:

- `AGENTS.md` — product mission, source-of-truth order, private server runbook requirement, Python/AI authority split.
- `bot/services/runtime_issue.py::RuntimeIssueService` — Stage 1 sanitized immutable capture and nullable `active_fsm_state`.
- `bot/services/db.py::RUNTIME_ISSUE_SCHEMA` — dedicated Stage 1 table and `intake_status='new'` constraint.
- `tests/test_runtime_issue_service.py` — stable IDs, nullable workspace, sanitization, transaction rollback, additive schema safety.
- `tests/test_runtime_issue_routes.py` — public route ownership.
- `tests/test_runtime_issue_voice.py` — voice convergence and restrictions.
- `docs/features/runtime_issue_autorepair_v1/02_AUTOREPAIR_POLICY.md` — low-risk/forbidden repair boundaries and evidence gates.
- `docs/features/runtime_issue_autorepair_v1/03_DAILY_MAINTENANCE_RUNBOOK.md` — isolated runner, bounded evidence, one issue at a time.
- `docs/features/runtime_issue_autorepair_v1/04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md` — current conceptual Stage 2 ownership requiring revision for workshop handoff.
- `docs/Code_Agent_Handoff_Contract.md` — approved-design and human review requirements.
- `scripts/update_repo.sh` — `/bot/repo`, `main`, fast-forward update convention.
- `scripts/deploy_owner_run.sh` — compose path and current deploy owner convention; deployment remains outside V1.
- PR #50 / merge commit `5aa37438e54ce61464ac2a3ae56f278129b3789e` — Stage 1 implementation and explicit Stage 2 exclusion.

Design-to-implementation rule: the implementation agent must report any contradiction and must not redesign handoff ownership, workshop persistence, decomposition timing, nullable FSM semantics, repair authority, or notification boundaries while coding.
