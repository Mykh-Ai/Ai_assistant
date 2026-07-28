# Runtime Issue Intake and Autorepair V1

Task ID: `RUNTIME_ISSUE_INTAKE_AND_AUTOREPAIR_V1`

Canonical action candidate: `report_runtime_issue`

Package status: documentation foundation; target behavior is not implemented.

Architecture Design Proof verdict: `needs_architecture_revision`.

## Purpose

This package defines an administrator-only, one-message runtime-issue intake
and a proposed once-daily maintenance process. It separates two concerns:

1. a bot-owned top-level action that records a trusted, bounded diagnostic
   snapshot without changing the current business FSM; and
2. a future maintenance process that classifies claimed reports and may repair
   only proven, local, low-risk defects after every safety gate passes.

The package is an architecture and policy draft. It does not authorize an
implementation agent, a merge, an unattended deployment, or a production
change.

## Current and target truth

Current Product Truth does not contain `report_runtime_issue`; `/issue` is not
registered; no runtime-issue SQLite owner, maintenance CLI, generic bot result
outbox, or autorepair process exists. The candidate action therefore remains
`planned`, not `implemented`.

Target Product Truth, subject to architecture approval, is:

- an administrator can send `/issue <complete description>`;
- bounded natural text or voice can converge on the same canonical action;
- capture is a one-shot global interrupt, including while a business FSM is
  active;
- capture writes one canonical SQLite record and sends an acknowledgement;
- the pre-capture FSM state and business FSM data are unchanged after capture;
- a separate daily process can claim reports, classify them, and return a
  truthful result through a bot-owned notification outbox;
- code repair, merge, deploy, and rollback remain unavailable until the
  blockers in the Architecture Design Proof are resolved and reviewed.

## Scope

- Canonical-action, slot, route, authorization, FSM-preservation, response, and
  negative-space design.
- Evidence-backed reuse of current authorization, semantic routing, workspace,
  SQLite, claim/lease, callback-safety, scheduler, test, deploy, and rollback
  patterns.
- Feature-specific autorepair classification and safety policy.
- Proposed issue, maintenance-run, manifest, evidence, result, and notification
  contracts.
- Acceptance scenarios and future test ownership.

## Explicit non-scope

- Python, tests, schema, migrations, configuration, dependencies, CI, Docker,
  server state, credentials, infrastructure, or bot behavior.
- Registration of `/issue`, aliases, buttons, handlers, FSMs, tables,
  schedulers, CLIs, outboxes, agents, branches, repair commits, deployments, or
  rollbacks.
- Broad intent whitelists, free-form agent authority, automatic feature
  approval, or a general code-change mechanism.
- Modification of the current canonical action registries, Product Truth, or
  InfoHelp documents.
- An implementation handoff.

## Source-of-truth order

For this package the current repository order is:

1. `AGENTS.md` for repository conduct and the controlling current-truth order.
2. Current runtime code and deterministic tests for implemented behavior.
3. `PROJECT_LOG.md` for recent decisions and deployment evidence.
4. `docs/TZ_FakturaBot.md` and `docs/Product_Doctrine_2030.md` for product
   intent.
5. Focused active contracts and canonical registries.
6. `CHANGELOG.md` for release history.
7. This package for the proposed feature only.

If this package conflicts with a current owner, the current owner wins until an
approved design explicitly changes that owner. Archived or superseded
documents are not current evidence. `README.md` contains an older ordering that
places the specification and log before code; `AGENTS.md` is the controlling
repository rule for current implementation truth.

SQLite is the proposed canonical issue store. A generated claimed-issue JSON
manifest is a bounded, read-only transport artifact and never a second writable
source of truth.

## Document index

- [00_REPOSITORY_AUDIT.md](00_REPOSITORY_AUDIT.md) — baseline, current owners,
  tests, operations evidence, gaps, and contradictions.
- [01_ARCHITECTURE_DESIGN_PROOF.md](01_ARCHITECTURE_DESIGN_PROOF.md) — complete
  top-level-action proof and readiness verdict.
- [02_AUTOREPAIR_POLICY.md](02_AUTOREPAIR_POLICY.md) — feature-specific
  classification, allowlist, prohibitions, evidence gates, and truthful
  reporting.
- [03_DAILY_MAINTENANCE_RUNBOOK.md](03_DAILY_MAINTENANCE_RUNBOOK.md) — proposed
  once-daily process, interruption recovery, and unresolved operational inputs.
- [04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md](04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md)
  — conceptual records, state transitions, claim/lease, manifests, evidence,
  results, and outbox.
- [05_ACCEPTANCE_SCENARIOS.md](05_ACCEPTANCE_SCENARIOS.md) — public-route,
  preservation, classification, repair, deployment, rollback, security, and
  notification scenarios.

## Approval and implementation gates

No implementation handoff may be written until:

1. a reviewer resolves the unattended merge/deploy conflict with the current
   human-approval contracts;
2. the exact deployed-SHA owner, approved production rollback procedure,
   sanitized log-evidence owner, and idempotent bot-notification owner are
   defined;
3. the language and active-FSM metadata-preservation decisions listed in the
   Architecture Design Proof are approved;
4. the proof verdict is revised to `ready_for_handoff`;
5. the implementation package is derived from that approved proof; and
6. implementation later supplies the Conversation Acceptance Proof owned by
   `docs/Evaluation_and_Smoke_Test_Standards.md`.

Human review remains required before merge and before any production change.

## Future private operations input

A later implementation or deployment phase may receive a separately mounted
private operations folder inside the Work/Codex container. That folder:

- will not be copied into or committed to this public repository;
- will not become a competing architecture or Product Truth source;
- may provide only environment-specific evidence needed to materialize the
  already approved public design, such as the approved private deployment and
  rollback procedures, server-side SHA verification, health checks, and
  issue-specific production smoke instructions; and
- must remain subject to the authorization, redaction, least-privilege, and
  human-review gates that apply to production operations.

Where such evidence is required later, this package uses the exact boundary:
“Private operational evidence required before implementation/deployment.”
Server addresses, SSH details, credentials, secrets, private filesystem paths,
backup locations, and sensitive commands must never be added to this package.

## Deferred general contract

The future general LLM/Work/Codex autorepair contract is intentionally not
created in this phase. It may be extracted only after this feature design is
approved, the first implementation exists, tests and Conversation Acceptance
Proof pass, and the real server, deployment, rollback, issue-claim, and bot
notification paths have been proven.
