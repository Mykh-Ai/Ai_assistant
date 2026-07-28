# Daily Runtime Issue Workshop Runbook

Task ID: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Status: `approved_design_pending_implementation`

Schedule target:

```text
daily at 22:00 Europe/Bratislava
```

Execution environment: ChatGPT Work / Briefing on OpenAI infrastructure, using the project container and private first-read skill.

## 1. Mandatory first read

Read in full before any server or GitHub action:

```text
/mnt/data/FakturaBot_Runtime_Maintenance_Worker_SKILL.md
```

Then read current `main` versions of the repository contracts listed by that skill. Do not rely on a previous run's memory.

## 2. Establish current truth

Before retrieving a new production issue:

1. Resolve current GitHub `main` SHA.
2. Fetch/check the workshop branch `maintenance/runtime-issue-workshop`.
3. Verify the workshop worktree is clean and synchronized.
4. Read `workshop/AUTOREPAIR_QUEUE.json`.
5. Read the log entries referenced by pending items in `workshop/AUTOREPAIR_LOG.md`.
6. Check for interrupted work, a pushed branch without PR, or another worktree owning overlapping files.
7. Confirm current mode is `human_reviewed_patch`.
8. Confirm merge/deploy/restart/data mutation remain forbidden.

A run may have work even when there are no new production issues.

## 3. Work-selection order

1. unresolved security/rollback integrity problem: stop and escalate;
2. interrupted handoff or workshop receipt requiring reconciliation;
3. oldest eligible `queued_for_repair` finding;
4. `needs_more_diagnostics` finding when new evidence is available;
5. new production handoffs, oldest first;
6. a newly proven low-risk finding if the one-repair slot remains unused.

Default limits:

```text
new handoffs: up to 3 per run
code repairs: up to 1 per run
```

## 4. Retrieve new intake issues

Target command:

```bash
cd /bot/repo
python -m bot.cli.runtime_issue_handoff take-next --limit 3 --format json
```

The CLI must:

- select only Stage 1 issues without an acknowledged workshop handoff;
- use stable oldest-first ordering;
- create a short-lived handoff lease in a dedicated Stage 2 table;
- return bounded sanitized JSON;
- never expose arbitrary SQL or the entire database;
- never alter the immutable Stage 1 issue row;
- support `active_fsm_state=null` as valid no-active-FSM context;
- distinguish `fsm_context_status=not_active` from `read_failed`;
- allow safe redelivery if acknowledgment never occurs.

The worker never runs manual SQL.

## 5. Durable workshop receipt and acknowledgment

For every returned handoff:

1. Add the source issue to `AUTOREPAIR_QUEUE.json` with `received_for_diagnosis`.
2. Append a receipt entry to `AUTOREPAIR_LOG.md` containing the sanitized observation, issue ID, handoff ID, received time, and explicit `code changed: no`, `production changed: no`.
3. Validate JSON and scan the diff for secrets/private data.
4. Commit the workshop receipt.
5. Push `maintenance/runtime-issue-workshop`.
6. Only after push, call:

```bash
python -m bot.cli.runtime_issue_handoff ack \
  --handoff-id RH-... \
  --workshop-branch maintenance/runtime-issue-workshop \
  --workshop-commit <40-hex-sha>
```

Acknowledgment records delivery only. It does not record diagnosis, findings, repair, or production truth.

If the worker fails before durable push, do not acknowledge. The lease may expire and the issue may be redelivered.

## 6. Collect bounded evidence

Target command:

```bash
python -m bot.cli.runtime_issue_evidence collect \
  --issue-id IR-... \
  --handoff-id RH-... \
  --format json
```

The wrapper may inspect only bounded relevant evidence, including when available:

- STT transcript/error;
- semantic action/result;
- Python exception/error event;
- Docker startup/restart/health facts;
- network/provider timeout or HTTP status;
- reported/current build SHA;
- approved lines around trusted update/message IDs and time window.

No raw day-long logs, `.env`, secrets, unrelated users, or cross-workspace events may be copied into the workshop.

If the interface cannot prove a fact, record it as unavailable rather than guessing.

## 7. Diagnose before decomposition

For each received source issue:

1. read current Product Truth and focused contracts;
2. locate current code owner(s);
3. inspect focused and adjacent tests;
4. inspect recent related Git history;
5. inspect bounded server evidence;
6. attempt deterministic reproduction where practical;
7. write a bounded diagnosis entry;
8. only then create zero, one, or multiple findings.

Each finding receives its own stable ID, classification, status, `log_ref`, owner scope, and next action.

## 8. Non-code outcomes

Examples:

- `resolved_expected_behavior`;
- `resolved_external_failure`;
- `insufficient_evidence`;
- `requires_architecture_design`;
- `requires_product_decision`;
- `requires_authorized_data_correction`;
- security/accounting boundary.

For these outcomes:

- do not create a speculative repair branch;
- update queue and log;
- push the workshop ledger;
- enqueue a truthful Slovak result notification.

## 9. Low-risk repair path

Only for a proven allowlisted finding:

1. set `repair_in_progress` in workshop state and push;
2. create an isolated worktree from exact approved `main` SHA;
3. create `autorepair/IR-...-FNN-short-slug`;
4. add a failing regression test;
5. make the smallest owner-local fix;
6. inspect full diff;
7. run focused tests;
8. run adjacent tests;
9. run required broad/static checks;
10. rerun the regression;
11. commit with the canonical marker;
12. push the branch;
13. create a Draft PR;
14. update workshop queue/log with exact test results, branch, commit, PR, and `production changed: no`;
15. push workshop state;
16. enqueue the Slovak Draft-PR notification.

If any gate fails, stop without claiming `patch_ready_for_review`.

## 10. GitHub failure handling

- Local commit, push failed: incomplete; preserve isolated branch/worktree, record exact blocker, no success notification.
- Branch pushed, PR creation failed: `branch_pushed_pr_blocked`; record branch/SHA, no `patch_ready_for_review` claim.
- Workshop branch push failed before handoff ack: do not acknowledge.
- Workshop conflict: stop and reconcile; do not force-push.

## 11. Notification

Target bridge:

```bash
python -m bot.cli.runtime_issue_notify enqueue \
  --issue-id IR-... \
  --template <approved-enum> \
  --payload-json <bounded-json>
```

The worker never uses the bot token. The bridge validates the template and bounded fields; the bot-owned delivery owner sends business Slovak copy.

Send only terminal or materially useful messages. Do not spam “analysis started” progress messages.

## 12. End-of-run summary

Record and push a bounded workshop run entry containing:

- run date/time;
- baseline `main` SHA;
- new handoffs received/acknowledged;
- source issues diagnosed;
- findings created by status;
- repair attempted/completed/blocked;
- exact branch/commit/PR facts;
- notifications queued;
- explicit production-change truth.

Do not include raw logs, credentials, private commands, or full tenant data.

## 13. Interrupted-run recovery

- Unacknowledged handoff: server lease may expire and redeliver.
- Acknowledged source issue: recover from the durable workshop branch, not production intake.
- Pending finding: continue from `AUTOREPAIR_QUEUE.json` and its `log_ref` even when `take-next` returns nothing.
- Repair branch/commit recorded: verify GitHub facts before any status transition.
- Notification retry: retry delivery only; do not rerun diagnosis or repair.

## 14. Current no-go boundary

No automatic merge, deployment, restart, production smoke, rollback, schema migration, or production data correction is part of this runbook version.
