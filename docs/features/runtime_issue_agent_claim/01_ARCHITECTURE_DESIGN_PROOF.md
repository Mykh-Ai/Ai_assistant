# Runtime Issue Agent Claim - Architecture Design Proof

Task ID: `RUNTIME_ISSUE_AGENT_CLAIM`

Verdict: `implemented_repository_only`

Deployment status: `production_not_deployed`

## 1. Owner decision

A supervised repair agent must be able to accept a leased runtime issue without
creating or verifying any GitHub commit. The bot-side bridge records the
delivery fact immediately after the agent proves possession of the live lease
token and exact bounded manifest.

The former V1 GitHub-dependent acknowledgment design is obsolete. Its
documents are historical only under
`docs/archive/runtime_issue_autorepair_v1/`.

## 2. Ownership

- `runtime_issues`: immutable administrator observation.
- `runtime_issue_handoffs`: lease and agent-delivery state.
- local/GitHub Workshop: diagnosis, findings, repair, tests, and publication.
- Python: every validation and state transition.
- AI/LLM/STT/FSM/Product Truth: unchanged.

Receiving an issue is not diagnosis, repair, merge, deployment, or user
notification.

## 3. Reused persisted shape

No database migration is required. The implementation reuses:

| Existing column | Current meaning |
|---|---|
| `handoff_id` / `issue_id` | stable delivery identity |
| `status=leased` | live bounded lease |
| `status=acknowledged` | terminal fact that the agent accepted delivery |
| `lease_token_hash` | verifier for the stdin token |
| `lease_owner` | approved repair-agent identity |
| `leased_at` / `lease_until` | lease window |
| `manifest_digest` | exact bounded issue-manifest binding |
| `acknowledged_at` | time accepted by the agent |
| `workshop_branch` | deprecated nullable V1 field; unused by claim |
| `workshop_commit_sha` | deprecated nullable V1 field; unused by claim |

The outward CLI response includes
`delivery_state=accepted_by_agent`. The persisted value remains
`acknowledged` to avoid a SQLite CHECK-constraint migration and to preserve
existing terminal rows.

No existing row is renamed, deleted, rewritten, or backfilled. Historical
acknowledged rows remain terminal delivery facts.

## 4. State machine

```text
no handoff -> leased
leased -> acknowledged (outward: accepted_by_agent)
leased -> expired_unacknowledged
expired_unacknowledged -> leased
acknowledged -> terminal
```

`reconciled` remains reserved and has no ordinary transition.

## 5. Claim interface

```text
python -m bot.cli.runtime_issue_handoff claim
  --handoff-id RH-...
  --lease-token-stdin
  --manifest-digest sha256:...
```

Rules:

1. raw token is accepted only through stdin;
2. validate handoff ID and manifest digest format;
3. open the existing database through the canonical connection owner;
4. begin one immediate transaction;
5. validate live status, lease owner, lease expiry, token hash, and manifest
   digest;
6. require legacy GitHub fields and `acknowledged_at` to be null for a new
   claim;
7. atomically set existing `status='acknowledged'`,
   `acknowledged_at`, and `updated_at`;
8. return the same result idempotently for the same token and manifest;
9. reject a different token/digest, expired lease, reserved state, or stale
   race without mutation.

The claim does not receive a receipt digest. The server needs proof that the
approved agent owns the exact live manifest, not proof of GitHub or filesystem
storage. Durable repair memory is published later in the Workshop after the
local outcome is final.

## 6. Security and privacy

- no token in argv, files, logs, workshop, PR, or response;
- no GitHub network access in `claim`;
- no arbitrary SQL interface;
- no change to Stage 1 issue rows;
- no cross-workspace evidence expansion;
- no raw logs, environment values, credentials, or tenant records in Git;
- no automatic merge, deployment, restart, diagnosis, or repair.

## 7. Compatibility

The database schema and manifest schema remain unchanged. This is intentional:
the rejected behavior lived in service/CLI validation, not in missing storage
capacity.

Legacy nullable GitHub columns remain physically present. Removing them would
require a table rebuild and would add migration risk without improving the
claim boundary. They may be removed only in a later separately approved schema
cleanup.

The old CLI `ack` and remote commit verifier are removed from the active
implementation. Existing historical rows remain readable by the evidence
service because `acknowledged` remains the terminal delivery status.

## 8. Acceptance scenarios

1. A live lease plus matching stdin token and manifest digest becomes terminal
   without GitHub access.
2. The same claim is idempotent.
3. A mismatched token or manifest changes nothing.
4. An expired lease cannot be claimed and can be safely redelivered.
5. An acknowledged issue is excluded from `take-next`.
6. New claims leave both GitHub legacy columns null.
7. Historical acknowledged rows remain terminal and readable.
8. `ack` is absent from CLI help.
9. Token values never appear in stdout or stderr.
10. No schema, Stage 1 issue, tenant, business data, Telegram route, or AI layer
    changes.

## 9. Deployment gate

Repository implementation does not prove production availability. Before a
repair agent may lease a new issue:

1. merge the reviewed implementation;
2. retain a pre-deploy SQLite backup even though no migration is expected;
3. deploy the exact merged SHA through the server runbook;
4. verify existing schema validation and database integrity;
5. verify CLI help exposes `claim` and not `ack`;
6. execute fixture/temporary-database claim smoke in the production image;
7. verify the live business database was not modified by the smoke;
8. only then mark the skill deployment status implemented.

No production database write or deployment is authorized by this document
alone.

## 10. Explicitly out of scope

- deleting historical handoff rows or legacy columns;
- changing `runtime_issues`;
- automated scheduling;
- automatic diagnosis/repair;
- GitHub publication during intake;
- merge/deployment without explicit approval;
- business-data correction;
- user notification changes;
- reassignment of accepted issues.
