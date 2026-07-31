# Runtime Issue Autorepair V1

Status: `phase1_bridge_implemented_repository_only`

Stage 1 keeps administrator runtime observations immutable in `runtime_issues`.
Phase 1 of Stage 2 adds only the bounded production-inbox-to-workshop bridge:

```text
runtime_issues
-> 60-minute atomic handoff lease
-> durable workshop receipt
-> verified acknowledgment
-> bounded recorded evidence
```

Implemented internal commands:

```bash
python -m bot.cli.runtime_issue_handoff take-next --limit 3 --format json
printf '%s' "$LEASE_TOKEN" | python -m bot.cli.runtime_issue_handoff ack \
  --handoff-id RH-... --lease-token-stdin \
  --manifest-digest sha256:... \
  --workshop-branch maintenance/runtime-issue-workshop \
  --workshop-commit <40-hex-sha>
python -m bot.cli.runtime_issue_evidence collect \
  --issue-id IR-... --handoff-id RH-... --format json
python -m bot.cli.runtime_issue_workshop bootstrap --format json
```

The raw lease token is returned only by `take-next`, accepted by `ack` only on
stdin, and stored only as a SHA-256 verifier. `reconciled` is schema-reserved
and has no Phase 1 transition or CLI owner.

This repository implementation is not deployed or activated. It adds no
nightly schedule, diagnosis, finding generation, repair automation,
notification delivery, merge, deployment, restart, or production migration.
Product Truth and InfoHelp therefore remain unchanged.

Canonical documents:

- `01_ARCHITECTURE_DESIGN_PROOF.md`
- `02_AUTOREPAIR_POLICY.md`
- `03_DAILY_MAINTENANCE_RUNBOOK.md`
- `03_AUTOREPAIR_QUEUE_SCHEMA.json`
- `04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md`
- `04_SLOVAK_NOTIFICATION_TEMPLATES.md`
- `05_ACCEPTANCE_SCENARIOS.md`
- `07_IMPLEMENTATION_NOTES.md`
- `08_AGENT_CLAIM_BRIDGE_V2_ARCHITECTURE_DESIGN_PROOF.md` — planned V2
  delivery claim that does not wait for GitHub publication; not implemented or
  deployed yet
- `workshop/AUTOREPAIR_QUEUE.json`
- `workshop/AUTOREPAIR_LOG.md`
