# Runtime Issue Intake and Autorepair V1

Package IDs:

- Stage 1: `RUNTIME_ISSUE_INTAKE_V1`
- Stage 2: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Canonical Stage 1 action: `report_runtime_issue`

Package status:

- Stage 1 Architecture Design Proof: `ready_for_handoff`
- Stage 1 implementation handoff: available
  (`06_IMPLEMENTATION_HANDOFF.md`)
- Stage 1 implementation: not started
- Stage 2: `planned`; activation blocked
- Runtime behavior: not implemented

## Handoff status

`06_IMPLEMENTATION_HANDOFF.md` now transfers the approved
`RUNTIME_ISSUE_INTAKE_V1` design to a future implementation agent without
delegating architecture choices.

- The Stage 1 Architecture Design Proof verdict remains
  `ready_for_handoff`.
- Stage 1 implementation has not started.
- The handoff is not merge, deployment, migration, server-write, or production
  approval.
- The handoff is not an implementation prompt.
- Stage 2 remains `planned / activation-blocked` and is excluded from the
  Stage 1 implementation.

This documentation change does not modify runtime behavior.

## Purpose and staged model

### Stage 1 — `RUNTIME_ISSUE_INTAKE_V1`

Stage 1 is the first implementable top-level feature. It defines:

- administrator-only `/issue <complete description>`;
- bounded natural-text and voice convergence to `report_runtime_issue`;
- one-message intake with no issue-intake FSM;
- preservation of active business FSM state, business FSM data, and current
  journey ownership;
- trusted runtime-context capture, including a nullable trusted workspace;
- additive SQLite persistence in dedicated runtime-issue tables;
- idempotent Telegram-delivery handling;
- truthful Slovak acknowledgement; and
- only a bounded read-only issue retrieval/export boundary if later
  maintenance requires it.

Stage 1 performs no code repair, Git operation, deployment, business-data
mutation, callback replay, issue claim/lease, claimed-manifest generation,
maintenance run, diagnosis/result write, or notification-outbox work.

### Stage 2 — `RUNTIME_ISSUE_AUTOREPAIR_V1`

Stage 2 is a later external Work/Codex maintenance feature. Its target scope is:

- a daily run with a global concurrency lease and kill switch;
- issue claim/lease, diagnosis, classification, and bounded evidence;
- an explicit low-risk repair allowlist and forbidden-scope gate;
- focused, adjacent, and required broader tests;
- marked `[AUTOREPAIR]` branch/commit/merge history;
- optional bounded automatic deployment, verification, and rollback; and
- truthful bot result notification through a retryable outbox.

The product target mode is `bounded_autorepair`. It is distinct from
`diagnostic_only` and `human_reviewed_patch`. The product decision is approved;
executable authority is not. Stage 2 remains `planned` and activation-blocked
until the narrow canonical-contract amendment, public service contracts, and
private operational interfaces defined by this package are implemented,
proven, and approved.

Stage 2 activation blockers do not block the Stage 1 Architecture Design
Proof.

## Current and target truth

Current Product Truth does not contain `report_runtime_issue`; `/issue` is not
registered; no runtime-issue SQLite owner, maintenance CLI, generic bot-result
outbox, or autorepair process exists. Both capabilities therefore remain
planned at runtime.

The approved Stage 1 target truth is:

- the administrator sends the complete report in one message;
- user-facing feature responses are Slovak;
- Ukrainian, Russian, Slovak, or mixed-language administrator input may be
  resolved through the existing bounded semantic-resolver pattern;
- bare `/issue` returns same-message usage, creates no row, opens no FSM,
  captures no later message, and does not cancel the active business action;
- a successful intake writes one canonical SQLite record and acknowledges only
  what was actually stored;
- business FSM state and business FSM data remain unchanged, while ordinary
  shared technical activity metadata such as `last_activity` may follow the
  authorized message-lifecycle invariant; and
- absence of an active workspace does not discard a valid report:
  `workspace_id` is null with a bounded trusted reason.

## Scope

- Stage 1 canonical action, slots, routing, authorization, FSM preservation,
  response, persistence, compatibility, negative space, and acceptance design.
- Repository evidence for current authorization, routing, workspace, SQLite,
  claim/lease, callback-safety, scheduler, test, deploy, and rollback patterns.
- Stage 2 feature-specific classification, authority, safety, evidence, deploy,
  rollback, notification, and interruption-recovery policy.
- Conceptual data/status/agent interfaces. This task creates no schema.

## Explicit non-scope

- Python, tests, schema, migrations, configuration, dependencies, CI, Docker,
  server state, credentials, infrastructure, production, or current bot
  behavior.
- Registration of `/issue`, aliases, buttons, handlers, FSMs, tables,
  schedulers, CLIs, outboxes, repair branches, commits, deployments, or
  rollbacks.
- Modification of existing business tables.
- A multilingual phrase whitelist, free-form agent authority, automatic
  feature approval, or a general code-change mechanism.
- Modification of current canonical registries, Product Truth, or InfoHelp.
- `docs/llm/Runtime_Autorepair_Agent_Contract.md`.

## Source-of-truth order

For this package the current repository order is:

1. `AGENTS.md` for repository conduct and current-truth ordering.
2. Current runtime code and deterministic tests for implemented behavior.
3. `PROJECT_LOG.md` for recent decisions and deployment evidence.
4. `docs/TZ_FakturaBot.md` and `docs/Product_Doctrine_2030.md` for product
   intent.
5. Focused active contracts and canonical registries.
6. `CHANGELOG.md` for release history.
7. This package for the approved target design only.

SQLite is the proposed canonical issue store. Stage 1 may expose a bounded
read-only issue retrieval/export boundary without changing issue status.
Stage 2 alone may atomically claim an issue and generate a claimed-issue JSON
manifest. That manifest is a bounded read-only transport artifact, never a
competing writable source of truth.

## Document index

- [00_REPOSITORY_AUDIT.md](00_REPOSITORY_AUDIT.md) — baseline, current and
  proposed owners, tests, schema behavior, operations evidence, and gaps.
- [01_ARCHITECTURE_DESIGN_PROOF.md](01_ARCHITECTURE_DESIGN_PROOF.md) — Stage 1
  top-level-action proof and `ready_for_handoff` verdict.
- [02_AUTOREPAIR_POLICY.md](02_AUTOREPAIR_POLICY.md) — Stage 2 approved target
  mode, allowlist, prohibitions, evidence gates, and truthful reporting.
- [03_DAILY_MAINTENANCE_RUNBOOK.md](03_DAILY_MAINTENANCE_RUNBOOK.md) — Stage 2
  modes, proposed daily process, interruption recovery, and activation inputs.
- [04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md](04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md)
  — exact Stage 1 intake/read boundary and later Stage 2
  claim/run/result/outbox ownership.
- [05_ACCEPTANCE_SCENARIOS.md](05_ACCEPTANCE_SCENARIOS.md) — separate Stage 1
  mandatory acceptance and downstream Stage 2 policy scenarios that are not
  required for Stage 1 implementation or handoff.
- [06_IMPLEMENTATION_HANDOFF.md](06_IMPLEMENTATION_HANDOFF.md) — complete
  Stage 1 implementation handoff derived from the approved Architecture Design
  Proof; no Stage 2 implementation authority.

## Approval and implementation gates

Stage 1 now has the approved implementation handoff in
`06_IMPLEMENTATION_HANDOFF.md`. Stage 1 implementation has not started. The
handoff transfers the approved proof without allowing the implementation
agent to redesign the action, and it excludes Stage 2 claim/lease,
claimed-manifest, maintenance-run, diagnosis/result, outbox, repair, merge,
deployment, and rollback work.

Stage 2 activation separately requires:

1. a narrow amendment to the canonical human-review contracts that permits
   only policy-allowlisted, fully proven `[AUTOREPAIR]` changes to use the
   bounded automatic path while leaving ordinary development under human
   review;
2. implemented and tested issue claim/lease, global run lease, kill switch,
   sanitized evidence, result writer, and retryable bot-notification owners;
3. a trusted deployed-SHA owner and exact clean-state/SHA checks;
4. separately mounted private deploy, health, smoke, rollback, and escalation
   evidence;
5. machine-verifiable allowlist, test, rollback, deploy, smoke, and post-deploy
   error-scan gates; and
6. reviewer approval of the implemented public and private operational
   boundaries.

Any failed or unavailable Stage 2 gate stops before merge/deploy. Production
smoke failure triggers the approved private rollback procedure; unresolved
rollback risk freezes the run and escalates to a human.

## Future private operations input

A later implementation or deployment phase may receive a separately mounted
private operations folder inside the Work/Codex container. That folder:

- is not committed and must never be copied into the public repository;
- is not Product Truth and cannot override approved public architecture;
- may supply only environment-specific deploy, rollback, SHA, log-query,
  health, smoke, and escalation evidence; and
- remains subject to authorization, redaction, least privilege, and the
  relevant Stage 2 gates.

Its absence does not block Stage 1 architecture approval. It blocks only an
implementation or production step that actually requires the missing private
evidence. Server addresses, SSH details, credentials, tokens, private paths,
backup locations, sensitive commands, and private rollback procedures must
never enter this package.

## Deferred general contract

The future general LLM/Work/Codex autorepair contract is intentionally not
created here. This PR produces no implementation prompt and no Stage 2 or
general autorepair implementation handoff. The Stage 1 intake handoff is
`06_IMPLEMENTATION_HANDOFF.md`.
