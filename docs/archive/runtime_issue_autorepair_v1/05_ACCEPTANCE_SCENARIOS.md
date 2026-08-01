# Runtime Issue Workshop Acceptance Scenarios

Stage 2 task ID: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Status: `approved_target_contract`

These scenarios cover the OfficeFlow-intake / GitHub-workshop bridge. Stage 1 intake acceptance remains owned by its completed Conversation Acceptance Proof.

## 1. No active FSM

- Stage 1 source issue has `active_fsm_state=null`.
- Handoff manifest returns `fsm_context_status=not_active`.
- Issue is received, acknowledged, diagnosed, and may be decomposed normally.
- No missing-FSM error is claimed.

## 2. FSM read failure

- Technical read fails while preparing trusted context/evidence.
- Interface returns `fsm_context_status=read_failed` rather than `not_active`.
- Handoff may continue with an explicit evidence gap.
- Worker does not claim that no FSM was active.

## 3. Durable handoff before acknowledgment

- `take-next` leases and returns `IR-1`.
- Worker writes queue/log receipt, commits, and pushes workshop branch.
- `ack` verifies handoff/digest/branch/commit and records acknowledgment.
- Future `take-next` does not return `IR-1` as a new issue.

## 4. Failure before workshop push

- `take-next` returns `IR-1`.
- Worker crashes before durable push.
- No acknowledgment exists.
- After lease expiry, `IR-1` may be returned again.
- No issue is lost.

## 5. Push succeeds, acknowledgment temporarily fails

- Durable workshop receipt exists with exact commit SHA.
- `ack` fails due to temporary server/network error.
- Worker retries or reconciles acknowledgment using the same handoff and receipt facts.
- It does not append a duplicate source issue.

## 6. One issue decomposes into three findings

- Source observation is received as one issue.
- Worker inspects bounded logs, code, Product Truth, tests, and Git history.
- Evidence proves three independent work items.
- Queue contains `F01`, `F02`, `F03` with independent statuses and log references.
- Source issue becomes `partially_resolved` when one is resolved, one blocked, and one queued.

## 7. No premature decomposition

- Intake wording appears to mention three symptoms.
- Evidence shows one shared root cause.
- Worker creates one finding, not three.
- Log explains the causal result.

## 8. No new production issue, old repair remains

- `take-next` returns an empty set.
- Workshop queue contains an eligible old `queued_for_repair` finding.
- Worker continues that finding.
- Run does not report “no work”.

## 9. STT evidence available

- Trusted issue IDs/time window correlate to a stored STT transcript or STT error.
- Evidence wrapper returns a sanitized bounded fact.
- Worker may use it in diagnosis and cite only the bounded summary.

## 10. STT evidence unavailable

- No retained STT fact exists.
- Evidence wrapper reports unavailable.
- Worker does not reconstruct or invent the transcript.
- Finding may become `needs_more_diagnostics` or rely on other proof.

## 11. Docker or network disturbance

- Bounded evidence proves a container restart/unhealthy state or provider/network timeout at the relevant time.
- Worker classifies `external_failure` or a separate local error-handling defect only when causal proof exists.
- It does not patch application code merely because “internet jumped”.

## 12. Proven low-risk callback/keyboard defect

- Deterministic reproduction and failing regression prove an allowlisted local defect.
- Worker creates an isolated branch, minimal fix, required tests, commit, push, and Draft PR.
- Finding becomes `patch_ready_for_review`.
- Telegram states production was not changed.

## 13. Top-level or FSM architecture requirement

- Diagnosis proves material top-level/FSM architecture work is required.
- Finding becomes `requires_architecture_design`.
- No speculative repair branch, commit, or PR is created.
- Log identifies relevant owners/contracts/tests.

## 14. Verified stale contact/company data

- Authoritative registry evidence proves stored production data is stale.
- Finding becomes `requires_authorized_data_correction`.
- Worker records verification and required next action.
- It does not mutate production data under V1.

## 15. Expected behavior

- Current Product Truth and deterministic behavior prove the observation is intended.
- Finding becomes `resolved_expected_behavior`.
- No code change.
- Slovak notification truthfully explains the result without calling it a bug.

## 16. Insufficient evidence

- Logs/reproduction cannot establish root cause.
- Finding becomes `insufficient_evidence` or `needs_more_diagnostics` with exact missing evidence.
- No patch is created.

## 17. Cross-workspace evidence request

- Requested scope conflicts with trusted issue workspace.
- Evidence interface rejects it with no data disclosure.
- Worker records a bounded policy failure, not a diagnosis.

## 18. Workshop secret scan

- Returned observation/evidence contains a token-like or private-path value.
- Sanitizer redacts it or rejects the item.
- Secret does not enter queue, log, commit, PR, or Telegram.

## 19. Repair limit

- Two findings are eligible for low-risk repair in the same run.
- Worker repairs at most one.
- The other remains `queued_for_repair` for a later run.

## 20. Local commit without push

- Repair is committed locally but push fails.
- Finding does not become `patch_ready_for_review`.
- Log records exact blocker and preservation state.

## 21. Branch pushed, Draft PR failed

- Exact repair branch and commit exist remotely.
- PR creation fails.
- Finding becomes `branch_pushed_pr_blocked`.
- Notification does not claim review is ready.

## 22. Notification retry

- Result is already recorded in workshop state.
- First Telegram delivery attempt fails.
- Bot-owned delivery retries the same idempotent notification.
- Diagnosis and repair do not rerun.

## 23. Business Slovak decomposition message

For a source issue with three findings, the notification contains:

- source issue ID;
- count of separate work items;
- compact truthful result for each;
- explicit code/production truth where relevant;
- no raw logs or private technical details.

## 24. Direct SQL prohibition

- Worker attempts or is instructed to run arbitrary SQLite commands.
- Private skill and CLI contract require it to stop.
- Only `take-next`, `ack`, bounded evidence, and notification interfaces are allowed.

## 25. Existing Stage 1 behavior remains unchanged

- `/issue` still stores one sanitized observation and preserves the active business state/data.
- Stage 2 adds no public top-level action, issue FSM, callback, or next-message capture.
- Stage 2 cannot replay, undo, or execute the reported business action.
