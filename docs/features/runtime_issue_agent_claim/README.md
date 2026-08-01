# Runtime Issue Agent Claim

Status: `implemented_repository_only`

Deployment status: `production_not_deployed`

This is the current deterministic handoff contract for supervised OfficeFlow
repair sessions.

```text
immutable runtime_issues observation
-> 60-minute atomic lease
-> local bounded workshop receipt
-> claim through stdin
-> existing acknowledged status means accepted by the agent
-> diagnosis and repair proceed without waiting for GitHub
```

The implementation deliberately reuses the existing
`runtime_issue_handoffs` columns. It adds no table, column, status value, or
schema migration. `workshop_branch` and `workshop_commit_sha` remain nullable
legacy columns and are not used by `claim`.

Current active files:

- `01_ARCHITECTURE_DESIGN_PROOF.md`
- `workshop/AUTOREPAIR_QUEUE.json`
- `workshop/AUTOREPAIR_LOG.md`

The former GitHub-verified V1 acknowledgment design is obsolete and preserved
only under `docs/archive/runtime_issue_autorepair_v1/`. It is not active
architecture or Product Truth.

The Stage 1 `runtime_issues` intake remains the immutable source observation.
Only the former V1 delivery method was rejected.
