# Runtime Issue Agent Claim Bridge V2 — Architecture Design Proof

Task ID: `RUNTIME_ISSUE_AGENT_CLAIM_BRIDGE_V2`

Verdict: `ready_for_owner_approval`

Status: `planned_not_implemented`

## 1. Product decision

When a supervised repair agent retrieves an issue, writes its bounded local
receipt, and confirms possession with the live lease token, the production
bridge must mark the issue as accepted by that agent. This delivery handshake
must not wait for a GitHub workshop commit, repair commit, pull request, merge,
or deployment.

Git publication occurs only after diagnosis, repair, tests, and final diff
inspection produce a truthful final local outcome.

## 2. Current mismatch

Bridge V1 has only:

```text
leased -> acknowledged
```

Its `ack` command requires a workshop branch and remotely verified workshop
commit. The interactive skill then extended that wait through diagnosis,
repair, tests, repair publication, and final workshop publication. That caused
the 60-minute delivery lease to remain open while unrelated repair work was in
progress.

The current implementation is therefore incompatible with the approved V2
journey. Until V2 is implemented and deployed, agents must not claim that an
issue can be accepted without GitHub verification.

## 3. Architecture class and ownership

- Class: deterministic internal delivery/state workflow.
- Public Telegram action: unchanged.
- LLM/STT/FSM/Product Truth: unchanged.
- Stage 1 `runtime_issues`: remains immutable.
- Stage 2 `runtime_issue_handoffs`: owns delivery state only.
- GitHub Workshop: owns diagnosis, findings, repairs, tests, and publication.
- AI maturity: not applicable; Python owns every transition.

No repair wording, model output, or GitHub state may execute a handoff
transition.

## 4. Target state machine

```text
no handoff -> leased
leased -> accepted_by_agent
leased -> expired_unaccepted
expired_unaccepted -> leased
accepted_by_agent -> terminal delivery fact
```

`accepted_by_agent` means only:

- the bounded manifest was delivered;
- the authenticated lease holder confirmed receipt;
- a bounded local receipt was written;
- the issue must not be offered as new work again.

It does not mean diagnosed, repaired, committed, pushed, reviewed, merged,
deployed, or acknowledged by a user.

Legacy V1 `acknowledged` rows remain terminal historical delivery facts. They
must not be rewritten merely to rename the state.

## 5. Claim interface

Target CLI:

```text
runtime_issue_handoff claim
  --handoff-id RH-...
  --lease-token-stdin
  --manifest-digest sha256:...
  --receipt-digest sha256:...
```

Recovery CLI:

```text
runtime_issue_handoff show-accepted
  --handoff-id RH-...
  --format json
```

It returns only the same bounded manifest and delivery facts to the authorized
server-side operator. It does not return the raw or hashed token and does not
change state.

Rules:

- accept the raw lease token only through stdin;
- validate the live lease, owner, token hash, and manifest digest;
- accept only a SHA-256 digest of the bounded local receipt;
- do not accept local paths, raw issue text, GitHub branch names, or commits;
- perform one atomic transition to `accepted_by_agent`;
- return the same result idempotently for the same token and digests;
- reject expired, mismatched, conflicting, or already-owned claims without
  changing canonical state.

The server trusts the authenticated agent's receipt assertion. The digest
binds the assertion to exact bounded content but does not prove remote storage.
Durable diagnosis and repair memory remains the final GitHub Workshop
publication.

Canonical receipt payload:

```json
{
  "schema_version": "runtime-issue-agent-receipt-v2",
  "handoff_id": "RH-...",
  "issue_id": "IR-...",
  "manifest_digest": "sha256:...",
  "received_at": "UTC"
}
```

Compute `receipt_digest` over canonical UTF-8 JSON with sorted keys and compact
separators. Do not include issue description, paths, secrets, or lease token.

## 6. Proposed persisted shape

Add or migrate Stage 2 fields:

| Field | Rule |
|---|---|
| `status` | include `accepted_by_agent` and `expired_unaccepted`; preserve legacy terminal values |
| `accepted_at` | UTC, required only for `accepted_by_agent` |
| `receipt_digest` | SHA-256, required only for `accepted_by_agent` |
| `workshop_branch` | legacy nullable field; not required by V2 claim |
| `workshop_commit_sha` | legacy nullable field; not required by V2 claim |
| `acknowledged_at` | legacy nullable field; do not reuse as `accepted_at` |

Do not add diagnosis, finding, PR, merge, or deployment status to the
production handoff table.

## 7. Repair-session journey

```text
1. inspect existing local Workshop backlog
2. take-next obtains a bounded issue and live lease
3. write and validate a bounded local source receipt
4. claim the handoff immediately through stdin
5. confirm accepted_by_agent
6. classify the candidate error domain
7. find and record canonical architecture/behavior documents
8. collect bounded evidence and diagnose
9. repair locally when allowlisted
10. run regression, focused, adjacent, full, and required smoke tests
11. inspect the final diff
12. commit and push the completed repair branch and open the PR
13. publish the finalized Workshop queue/log
```

No background helper waits for lease expiry or GitHub confirmation. After step
5, repair duration is independent of the delivery lease.

## 8. Failure and recovery

- Crash before claim: lease expires and the issue may be safely offered again.
- Claim rejected: preserve the local receipt, report the exact reason, and do
  not pretend ownership.
- Crash after claim: the issue remains accepted and recoverable through the
  Workshop receipt or an owner-scoped read-only accepted-handoff query.
- GitHub unavailable after claim: preserve local work; delivery remains true,
  publication remains incomplete.
- Repair fails: publish a final no-patch or blocked outcome when GitHub becomes
  available; do not release the issue as new intake.
- Recovery/reassignment of an abandoned accepted issue requires a separate
  bounded administrative operation; automatic stealing is forbidden.

## 9. Migration and rollout safety

This is migration-sensitive because SQLite CHECK constraints and existing
handoff rows are affected.

Before implementation or production write:

1. perform a read-only audit of handoff schema, row counts, and statuses;
2. record the current and proposed table shapes;
3. create a timestamped database backup and verify its digest/integrity;
4. implement a transactional, dry-run-tested schema migration;
5. preserve all existing V1 rows and terminal delivery facts;
6. test rollback from the backup;
7. deploy code and schema through the approved runbook;
8. verify `take-next`, `claim`, idempotency, expiry, and legacy-row reads;
9. update the interactive skill from planned to implemented only after the
   production CLI exposes `claim` and the smoke test passes.

No production migration or data write is authorized by this design document.

## 10. Acceptance scenarios

1. A live lease plus matching token/manifest/receipt digests becomes
   `accepted_by_agent` without any GitHub access.
2. The same claim is idempotent.
3. A mismatched token or digest changes nothing.
4. An expired lease cannot be claimed and can be safely redelivered.
5. An accepted issue is excluded from `take-next`.
6. GitHub outage after claim does not alter delivery truth.
7. Legacy `acknowledged` rows remain readable and terminal.
8. No Stage 1 issue row, business data, tenant scope, or Telegram FSM changes.
9. Repair branch/workshop push occurs only after a final local outcome.
10. Logs and CLI output never expose the raw lease token or tenant data.

## 11. Explicitly out of scope

- autonomous scheduling;
- automatic diagnosis or repair;
- automatic merge or deployment;
- production business-data changes;
- user notification changes;
- GitHub status synchronization back into the handoff table;
- arbitrary reassignment of accepted issues.
