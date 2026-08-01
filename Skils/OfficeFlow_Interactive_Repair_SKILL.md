---
name: officeflow-interactive-repair
description: Use when the user starts a supervised OfficeFlow / FakturaBot repair session from a local CLI. Retrieve recorded runtime issues from production through the approved handoff CLI over SSH, classify the likely error domain, find the canonical architecture and expected-behavior documents before diagnosis, inspect bounded evidence, preserve the GitHub workshop ledger, implement safe repairs, run the required tests, and only then commit, push, and open reviewable pull requests. Do not schedule work or silently merge, deploy, restart, migrate, or change production business data.
---

# OfficeFlow Interactive Runtime Repair

Status: `manual_supervised_cli_mode`

Agent Claim status: `implemented_and_deployed_verified` as of 2026-08-01.

Publication boundary: this repository copy must remain public-safe. Keep server addresses, environment-specific paths, commands, tenant facts, secrets, and raw logs only in the local `FakturaBot_Server_Agent_Context.md`; do not duplicate them here or in public GitHub content.

## 1. Purpose

This skill runs a user-started repair session for OfficeFlow / FakturaBot.

The user reports a runtime problem when it happens. The bot records the observation. Later, the user starts a local CLI agent. The agent retrieves the recorded issue, reads the relevant server evidence and repository truth, diagnoses it, records durable findings, and repairs safe defects without requiring the user to remember or rewrite the original report.

Target workflow after the Agent Claim implementation is deployed:

```text
runtime issue reported in OfficeFlow
-> immutable runtime_issues observation
-> approved handoff lease
-> local workshop receipt
-> agent delivery claim without waiting for GitHub publication
-> bounded server and repository evidence
-> candidate error class and canonical architecture/behavior documents
-> diagnosis
-> zero, one, or multiple findings
-> safe repair(s), blocked outcome, or product/architecture decision
-> tests
-> commit + push + pull request when code changed
-> durable GitHub workshop receipt
-> concise session report to the user
```

This is not a scheduled or autonomous worker. The user decides when to start a session.

There is no separate diagnostic bridge. The implemented bridge only delivers recorded intake issues and bounded evidence. Diagnosis is performed by the interactive CLI agent using SSH, current code, contracts, tests, Git history, and bounded server logs.

## 2. Operating model

The agent runs on the user's computer from a local clone of:

```text
Mykh-Ai/Ai_assistant
```

The agent may use:

- the local repository and worktrees;
- Git and GitHub;
- SSH to the authorized OfficeFlow VPS;
- the implemented runtime-issue handoff CLI;
- bounded production logs and read-only runtime facts;
- local tests and repository tooling.

The skill does not grant SSH, GitHub, filesystem, or network access. Verify that the current CLI session actually has the required access before claiming work can proceed.

### GitHub connection and authentication order

Prefer the connected GitHub app/connector for repository, issue, pull request,
review, PR creation, and PR merge operations that it exposes. The connector and
the local `gh` executable use separate authentication paths. An
unauthenticated `gh` CLI does not mean that GitHub or PR merge is unavailable.

Before reporting `github_auth_unavailable`:

1. resolve the intended `Mykh-Ai/Ai_assistant` repository from the local
   `origin`;
2. test the required read through the GitHub connector;
3. inspect whether the connector exposes the required write, including PR
   merge;
4. use the existing local Git transport for fetch/push when it works;
5. fall back to `gh` only for a connector coverage gap.

If `gh` is genuinely required, first run:

```powershell
gh auth status --hostname github.com
```

If it is not authenticated, the correct interactive setup is:

```powershell
gh auth login --hostname github.com --git-protocol https --web
gh auth status --hostname github.com
gh auth setup-git
gh repo view Mykh-Ai/Ai_assistant
```

The user completes the browser/device confirmation. Never ask the user to paste
a token into chat, source code, repository documentation, shell history, or
workshop files. Do not block a connector-supported operation merely because
the CLI path is unauthenticated.

The user's act of starting an OfficeFlow repair session authorizes the agent to perform the routine repair workflow described here. Git publication is the final phase of a completed local outcome, not an intake or progress checkpoint:

- read the repository and current contracts;
- perform read-only SSH inspection inside the OfficeFlow boundaries;
- retrieve pending issues through the approved CLI;
- publish finalized workshop receipts only after a final local outcome;
- claim successfully delivered handoffs through the deployed claim CLI;
- inspect bounded relevant logs;
- diagnose and decompose issues into findings;
- edit local code for safe, in-scope defects;
- add tests and update affected active documentation;
- create commits, push repair branches, and open pull requests.

Do not push an intake-only receipt, `repair_in_progress` state, partial
diagnosis, failing repair, or other intermediate artifact. Commit and push only
after the finding has a final local outcome, required tests have completed, the
full diff has been inspected, and the workshop record can truthfully describe
the result. Independent findings may publish independently when each has its
own final local outcome.

Do not stop for repeated confirmation before each routine step above.

Explicit user approval in the current session is still required before:

- merge;
- deployment or rollback;
- production restart;
- production migration or schema change;
- direct production data correction;
- destructive file/storage action;
- credentials, OAuth, tokens, encryption, or secret handling changes;
- authorization, tenant, or workspace security changes;
- external dependency installation or runtime upgrade;
- infrastructure, DNS, Cloudflare, network routing, or provider configuration;
- a new or materially changed top-level, subflow, FSM, callback authorization boundary, or user journey architecture.

Never edit application code directly on the server. Code changes belong in the local clone, a Git branch, and GitHub review.

## 3. Mandatory local server context

Before any SSH command, server inspection, production evidence collection,
deployment, restart, backup, migration, or other server-side action:

1. find the local file named `FakturaBot_Server_Agent_Context.md`;
2. read it in full;
3. treat it as the authority for the current server target, project boundaries,
   paths, commands, runtime names, and safe update runbook;
4. verify that the current environment matches that file before proceeding.

If the file is missing, unreadable, ambiguous, or conflicts with observed
server state, stop the server-side portion of the session and report the
blocker. Do not infer access details or substitute an example file.

`FakturaBot_Server_Agent_Context.example.md` is never the live server runbook.

The server may contain other live projects. Never inspect, search, edit,
restart, deploy, or read secrets outside the boundaries defined by the local
server context.

Never print, copy, or commit:

- `.env` contents;
- environment dumps;
- bot tokens;
- API keys;
- OAuth credentials;
- private keys;
- full user, invoice, contact, or accounting records;
- raw unbounded logs;
- another workspace's evidence.

## 4. Canonical implementation truth

Stage 1 runtime issue intake and Stage 2 Phase 1 handoff/evidence bridge are merged in the repository.

Relevant bridge merge:

```text
PR #52
merge commit: 6ce84936cbcb1254f86a5cf43f29320df069eb2b
```

Current bridge owners include:

- `bot/services/db.py::RUNTIME_ISSUE_HANDOFF_SCHEMA`;
- `bot/services/runtime_issue_handoff.py::RuntimeIssueHandoffService`;
- `bot/services/runtime_issue_evidence.py::RuntimeIssueEvidenceService`;
- `bot/services/runtime_issue_evidence.py::FixedDockerLogSource`;
- `bot/services/runtime_issue_workshop.py::bootstrap_workshop`;
- `bot/cli/runtime_issue_handoff.py`;
- `bot/cli/runtime_issue_evidence.py`;
- `bot/cli/runtime_issue_workshop.py`.

`runtime_issues` remains the immutable intake observation. Delivery state belongs to `runtime_issue_handoffs`.

Executable handoff states are:

```text
leased
expired_unacknowledged
acknowledged
```

`reconciled` is reserved and has no ordinary repair-session transition.

A source issue is an observation, not a diagnosis. One source issue may produce zero, one, or multiple findings.

## 5. Mandatory first read

Read this entire skill before any server or repository mutation.

Then read current files from the current `main` branch. Never rely on a previous session's memory.

### Always read

1. `AGENTS.md`;
2. `docs/features/runtime_issue_agent_claim/README.md`;
3. `docs/features/runtime_issue_agent_claim/01_ARCHITECTURE_DESIGN_PROOF.md`;
4. `docs/Evaluation_and_Smoke_Test_Standards.md`;
5. the recent relevant entries in `PROJECT_LOG.md`;
6. current code owners and focused tests for the issue.

Before the first server-side action, also read the local
`FakturaBot_Server_Agent_Context.md` required by section 3.

Read `docs/Code_Agent_Handoff_Contract.md` when a reported issue is actually a feature/customization request or when implementation readiness is unclear.

Before implementing any code repair, read
`docs/Implementation_Agent_Checklist.md` in full and verify the proposed repair
against it. This checklist is not mandatory when the final diagnostic outcome
is `expected_behavior`, `external_failure`, `insufficient_evidence`, or another
no-code result.

Do not treat `docs/archive/` as current truth.

Do not read every project document blindly. Use the issue-type map below after the first evidence pass.

### Mandatory class-and-contract preflight

Before diagnosing root cause or editing code:

1. assign one or more candidate error classes from the observed surface, such
   as routing, LLM/STT, FSM, confirmation/callback, Product Truth/InfoHelp,
   authorization/tenant, persistence/storage, external integration, PDF, or
   feature-local domain behavior;
2. use the issue-type map below to locate the active canonical documents for
   every candidate class;
3. identify the document, registry, approved design, code owner, or test that
   defines the intended architecture or correct behavior;
4. record the exact documents and owner evidence used in the workshop log
   before recording a root-cause conclusion;
5. if no active source defines the expected behavior, record
   `missing_canonical_truth` and classify the work as an architecture/product
   decision or insufficient evidence; do not invent the contract and do not
   patch by intuition.

The candidate class only selects evidence and documents. It is not the final
finding classification and does not prove a defect.

## 6. Issue-type document map

### A. Top-level action, alias, semantic routing, text/voice convergence, active-FSM navigation

Read:

- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
- the task-specific approved Architecture Design Proof, when one exists;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- Product Truth and InfoHelp owners listed below.

A bug that prevents the existing approved route from working may be repaired to the approved design.

A request that adds or materially changes a top-level, structured slot, subflow, FSM, callback flow, preview/confirmation flow, or text/voice/button journey is not an ordinary repair. Prepare an Architecture Design Proof first. Do not implement until its verdict is `ready_for_handoff` and the user approves it.

### B. Buttons, reply keyboards, inline keyboards, callbacks, approve/edit/cancel decisions

Read:

- `docs/Canonical_Decision_Resolver_Contract.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md` keyboard/callback scenarios;
- the current handler, keyboard builder, callback constants, stale-callback guard, FSM owner, and their tests.

Do not assume a separate button registry exists when current repository truth does not prove one. Follow the actual current owners and registries.

Prove terminal keyboard cleanup, stale/wrong-state/duplicate callback safety, no repeated side effect, and text/voice/button convergence where applicable.

### C. LLM, STT, voice, semantic resolver, prompt, or classification behavior

Read:

- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/Self_Learning_Layer.md` when learning is involved;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md` when aliases are involved;
- focused resolver, voice, authorization, and state-aware routing tests.

Preserve the authority split:

```text
Python orchestrates and validates.
AI extracts, canonicalizes, explains, drafts, or selects from bounded options.
AI does not execute side effects or invent canonical actions.
```

### D. Product Truth, InfoHelp, capability or limitation wording

Read:

- `docs/Product_Truth_Layer.md`;
- `docs/Product_Truth_Registry_MVP_Design.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- relevant Product Truth and InfoHelp tests/evals.

Do not mark a capability supported beyond current runtime evidence. A question about a capability must not execute that capability.

### E. SQLite, persisted data, storage paths, workspace/tenant ownership, archive/delete behavior

Read:

- `docs/FakturaBot_Data_Migration_Runbook.md`;
- current DB and storage owner code;
- workspace/tenant scoping code and tests;
- relevant storage architecture documents;
- the local `FakturaBot_Server_Agent_Context.md`.

Perform read-only audit first. Do not write production data or implement a migration without explicit approval, verified backup, rollback plan, dry-run evidence, and affected-data proof.

### F. Document intake, idle attachments, receipts, incoming invoices, contracts, contact sources

Read:

- `docs/architecture/OfficeFlow_Architecture_Framing.md`;
- `docs/architecture/OfficeFlow_Storage_Model_Proposal.md`;
- `docs/Document_Intake_Module_Proposal.md`;
- `docs/Document_Intake_MVP_Implementation_Plan.md`;
- attachment router, staging, workspace storage, cleanup, and tenant tests.

### G. Invoice PDF or layout

Read:

- `docs/FakturaBot_PDF_Layout_Spec.md`;
- invoice PDF generator code;
- relevant snapshots/rendered output/manual review evidence.

Compilation alone is not proof. Verify long values, wrapping, multi-item output, QR/Pay by Square, footer, and page layout.

### H. Access, onboarding, authorization, tenant/workspace isolation

Read:

- `docs/User_Access_Model_Roadmap.md`;
- authorization middleware and access services;
- workspace resolution owners;
- unauthorized, cross-tenant, and pre-AI/pre-download tests.

Do not weaken these boundaries in an unattended repair.

### I. Google Drive, Gmail, email, provider, OAuth, or other external integrations

Read the integration-specific current docs, credential model, failure/retry policy, tenant ownership, and setup truth.

Do not inspect credentials or add hidden sending/storage side effects. Provider outage or missing credentials may be an external/setup outcome rather than a code defect.

### J. Feature-local domain behavior

Search current `docs/features/`, current code, focused tests, and recent `PROJECT_LOG.md` entries for the affected domain before editing. Prefer the existing domain owner over a new abstraction.

## 7. Session startup preflight

From the local repository:

1. Resolve the repository root with `git rev-parse --show-toplevel`.
2. Verify `origin` is the intended `Mykh-Ai/Ai_assistant` repository.
3. Inspect `git status`, branches, worktrees, and open repair PRs.
4. Fetch current remote state without force.
5. Resolve exact current `origin/main` SHA.
6. Verify the local base/worktree is clean before creating a repair branch.
7. Inspect the workshop branch:

```text
maintenance/runtime-issue-workshop
```

8. Read:

```text
docs/features/runtime_issue_agent_claim/workshop/AUTOREPAIR_QUEUE.json
docs/features/runtime_issue_agent_claim/workshop/AUTOREPAIR_LOG.md
```

9. Check interrupted handoffs, pending findings, pushed branches without PRs, and overlapping worktrees.
10. Prefer existing backlog over leasing more work.

Then use the local `FakturaBot_Server_Agent_Context.md` to perform a bounded
read-only server preflight:

- verify the authorized SSH target;
- verify the intended project and repository boundaries;
- resolve the server repository SHA;
- inspect the approved runtime/container status;
- verify the production database file exists at the approved path;
- verify the bridge CLI modules exist in the deployed server repository;
- do not expose `.env` or full Docker/environment output.

Inspect the deployed handoff CLI help before leasing new work. Under the
final-only Git publication policy, the CLI must expose the `claim` command
that does not require a GitHub branch or commit. If only the obsolete `ack` command
is available, report `agent_claim_bridge_not_deployed` and do not lease a new
issue. Do not start a hidden wait helper and do not push an intake-only receipt
as a workaround.

Repository merge does not prove deployment. If the deployed runtime does not contain the bridge, report `production_bridge_not_deployed` and stop before attempting direct SQL or inventing another intake path.

## 8. Work selection

Selection order:

1. security, rollback, data-integrity, or tenant-isolation concern: stop and escalate;
2. interrupted handoff or workshop conflict;
3. unfinished finding or pushed branch without PR;
4. a specific issue named by the user;
5. oldest new intake issue;
6. additional new issues when the current batch can be durably received before lease expiry.

The handoff CLI accepts at most three issues per call. Process work in batches.
Do not lease more issues than can receive a validated local receipt and a
verified `accepted_by_agent` response within the 60-minute lease. After that
claim, diagnosis and local repair are no longer lease-bound. If the lease
expires before claim, obtain safe redelivery.

There is no artificial one-repair-per-session limit in manual supervised mode. The agent may complete multiple safe findings in one session, one finding at a time, while preserving clean branches, tests, and review boundaries.

Do not bundle unrelated root causes into one patch merely because they came from one source issue.

## 9. Retrieve issues through the bridge

Use the approved service CLI on the server host, not manual SQL. Resolve the
current SSH target, project directory, database path, Python invocation, and
deployed module path from the local `FakturaBot_Server_Agent_Context.md` and
the deployed CLI help. Do not guess or copy environment-specific values from
this public skill.

Treat the returned lease token as ephemeral secret material:

- keep it only in process/session memory;
- do not print it back to the user;
- do not store it in a file;
- do not put it in Git, logs, issue notes, PR text, shell history, or command arguments;
- do not export it as a persistent environment variable.

The bot does not rewrite `runtime_issues.intake_status`. The existing persisted
`acknowledged` handoff status is the terminal delivery fact; the current CLI
renders it as `delivery_state=accepted_by_agent`. It is not diagnosis or
repair status. The legacy GitHub columns are not used by `claim`.

Never use direct SQLite queries as the normal intake interface. If the bridge is broken, report the exact failure. A read-only recovery audit requires explicit user approval; production writes still require a separate migration/data-correction authorization.

## 10. Local receipt and Agent Claim

For each leased source issue:

1. switch to or create a clean local worktree for `maintenance/runtime-issue-workshop`;
2. add a bounded source receipt to `AUTOREPAIR_QUEUE.json` with `received_for_diagnosis`;
3. append a sanitized receipt entry to `AUTOREPAIR_LOG.md`;
4. record issue ID, handoff ID, received time, repository/deployed SHA facts when available, and explicit `code changed: no`, `production changed: no`;
5. do not create findings before evidence-based diagnosis;
6. validate queue JSON;
7. inspect the exact diff for secrets, raw tenant data, private paths, and unrelated changes;
8. use the deployed `claim` interface immediately, piping the raw lease token
   through stdin with `--lease-token-stdin` and the exact manifest digest;
9. verify the returned `delivery_state` is `accepted_by_agent` for the exact
   handoff and manifest digest;
10. make no Git commit or push at this receipt/claim phase;
11. continue diagnosis and repair locally without waiting on the delivery
    lease.

Use the `claim` interface exposed by the deployed
`bot.cli.runtime_issue_handoff` module and the invocation rules from the local
server context. Pipe the raw token through standard input with
`--lease-token-stdin`; do not place it in a visible command or transcript.
Construct the pipe programmatically or with a non-exported ephemeral shell
variable that is never echoed.

A successful claim proves delivery to the agent only. It is not diagnosis,
repair, Git publication, merge, deployment, or user notification. If claim
fails, preserve the local receipt, report the exact handoff state, and allow
safe expiry/redelivery; do not duplicate the source receipt blindly.

## 11. Evidence collection

Start with the approved bounded evidence CLI on the server host. Resolve its
server-side invocation from the local `FakturaBot_Server_Agent_Context.md`,
the deployed module, and CLI help. Do not embed environment-specific access
details in the workshop or public GitHub content.

Because the interactive agent has authorized SSH access, it may inspect additional bounded server evidence when the wrapper is insufficient.

Allowed examples:

- bounded runtime/container logs for the approved OfficeFlow service in a
  narrow time window;
- fixed-line/byte excerpts from the approved OfficeFlow log path;
- exact update/message IDs from the trusted handoff;
- exact deployed/server Git SHA facts;
- container start/restart/health state;
- recorded STT/provider/network errors;
- bounded Python tracebacks related to the trusted issue;
- read-only configuration presence/status without printing secret values.

Use explicit time bounds and output caps. Resolve the fixed runtime/container
name from the local server context; never broaden inspection to unrelated
services.

Do not read a whole day of logs when a narrow issue window exists. Do not copy raw logs into GitHub. Store only sanitized excerpts, digests, source references, and exact conclusions needed to support a finding.

For tenant-specific evidence, require exact trusted correlation. A timestamp or keyword alone is not enough to attach another user's log line to the issue.

Missing evidence means `unavailable` or `insufficient_evidence`, not expected behavior and not a guessed root cause.

## 12. Diagnose before editing

For each source issue:

1. restate the observed behavior without promoting it to fact;
2. inspect the relevant Product Truth and current contract;
3. identify current handler/service/storage/registry owners;
4. inspect focused and adjacent tests;
5. inspect recent relevant Git history and `PROJECT_LOG.md`;
6. inspect bounded server evidence;
7. reproduce deterministically where practical;
8. identify the exact causal mechanism;
9. determine whether the issue represents zero, one, or multiple findings;
10. update the workshop queue/log with evidence-based findings.

Allowed finding classifications include:

```text
confirmed_low_risk_defect
expected_behavior
external_failure
insufficient_evidence
feature_request
complex_or_high_risk_defect
authorized_data_correction_required
```

Use stable finding IDs:

```text
<issue_id>-F01
<issue_id>-F02
...
```

Each finding must have:

- classification;
- current status;
- exact owner scope;
- evidence/log reference;
- causal mechanism or explicit evidence gap;
- next action;
- code-changed and production-changed truth.

The reporter's wording does not decide classification. Several sentences do not automatically mean several bugs. A code smell does not prove root cause.

## 13. Repair authority

A finding may be repaired directly in the supervised session when it is a proven local defect inside existing approved architecture, for example:

- missing callback acknowledgment;
- stale keyboard not removed;
- missing terminal response after a proven successful action;
- narrow incorrect Product Truth wording with unambiguous current truth;
- narrow exception handling at the existing owner;
- missing bounded structured diagnostic event;
- one route failing to reuse an existing approved helper/resolver/normalizer;
- bounded resolver example/hint correction that does not change action architecture;
- another owner-local deterministic defect with a failing regression test and bounded side effects.

Multiple safe findings may be repaired in the same session.

Use separate repair branches/PRs for independent root causes. Findings may share one branch only when they have one owner, one causal mechanism, one atomic acceptance story, and one rollback boundary.

Do not patch as routine repair when the finding requires:

- new or materially changed top-level/subflow/FSM/callback architecture;
- authorization or tenant-boundary redesign;
- schema or migration work;
- production business-data correction;
- accounting/tax/payment truth change;
- OAuth/credential/security redesign;
- destructive retention/delete/storage behavior;
- infrastructure/provider configuration;
- dependency/runtime upgrades;
- broad dispatcher/router refactor;
- an ambiguous product decision.

For new or materially changed top-level, subflow, FSM, slot, preview/confirmation, callback, or text/voice/button architecture:

1. read `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md` in full;
2. prepare the Architecture Design Proof required by that contract;
3. include action boundaries, neighboring actions, slots, FSM graph, text/voice/buttons parity, confirmations, callbacks, side effects, negative space, Product Truth, and acceptance scenarios;
4. stop implementation;
5. obtain user approval;
6. continue only after verdict `ready_for_handoff`.

Do not let a repair session silently become feature architecture.

## 14. Code repair workflow

For each approved safe finding:

1. synchronize current `origin/main`;
2. create an isolated worktree/branch from exact current `main`;
3. record the finding as `repair_in_progress` in the local workshop ledger
   without pushing incomplete work;
4. add a regression test that fails for the proven defect;
5. make the smallest owner-local fix;
6. update affected active contracts, Product Truth, InfoHelp, registries, or eval artifacts only when the behavior actually changes;
7. inspect the full diff;
8. run the focused regression and owner tests;
9. run adjacent tests selected from the dependency graph;
10. run broad/full tests and static/compile checks required by the affected scope;
11. run manual/server/product smoke when the claim requires it and it is authorized;
12. record exactly what was real, mocked, unavailable, and not run;
13. create a commit;
14. push the completed branch;
15. open a pull request;
16. update workshop queue/log with branch, commit, PR, exact tests, remaining risk, and `production changed: no`;
17. push the finalized workshop ledger update and verify both publications.

Do not over-engineer commit messages or PR prose. Follow current repository conventions and make the change reviewable. A local patch is not completed work. For code changes, completion requires at least a pushed commit and an open PR unless the user explicitly requests another endpoint.

Do not merge or deploy merely because tests pass.

## 15. Acceptance evidence

Use evidence proportional to the changed surface.

At minimum:

- exact failing regression before fix;
- passing regression after fix;
- focused owner tests;
- negative case outside the finding;
- adjacent unchanged behavior through modified shared layers;
- full suite or an explicit reason it was not run;
- full diff inspection;
- compile/static checks where applicable.

For user-facing routing, FSM, callbacks, text/voice/buttons, Product Truth, storage, authorization, or side effects, follow `docs/Evaluation_and_Smoke_Test_Standards.md` and create/update the required acceptance artifact.

`safe_to_commit` is not merge or deploy approval.

Never hide tests or smokes that were not run.

## 16. Server and production rules

Read-only SSH evidence is part of the ordinary supervised repair session.

The following remain separate explicit phases:

- merge;
- deployment;
- production restart;
- production backup/rollback;
- migration;
- production data correction;
- destructive cleanup.

When the user explicitly asks to deploy after merge:

1. read the current local `FakturaBot_Server_Agent_Context.md` in full;
2. verify exact merged `main` SHA;
3. verify backup and rollback requirements;
4. perform only the approved deployment steps;
5. run bounded production smoke;
6. report the exact deployed SHA and observed runtime truth.

Do not combine an unreviewed repair patch with production deployment.

## 17. Workshop persistence is the memory

The chat is not the repair backlog.

Durable memory belongs in:

```text
maintenance/runtime-issue-workshop
docs/features/runtime_issue_agent_claim/workshop/AUTOREPAIR_QUEUE.json
docs/features/runtime_issue_agent_claim/workshop/AUTOREPAIR_LOG.md
repair branches, commits, PRs, tests, and acceptance artifacts
```

A later session must continue from these facts even when no new issue is returned and even when the user no longer remembers the original report.

Do not use raw production intake as the long-term diagnosis ledger after the delivery claim.

## 18. Failure and recovery rules

### SSH unavailable

Report `server_access_unavailable`. Do not guess production state.

### Bridge not deployed or CLI unavailable

Report `production_bridge_not_deployed` or `bridge_cli_unavailable`. Do not fall back to manual SQL.

### Lease expires before Agent Claim

Do not claim ownership. Preserve the local receipt and obtain safe redelivery.
After a verified `accepted_by_agent` response, repair work is not tied to the
delivery lease.

### Workshop push fails

The earlier agent claim remains true. Preserve the completed local work and
report the publication blocker.

### Local receipt written but claim fails

Inspect the handoff state through the approved CLI/service path. Do not create
duplicate receipts or push an intake-only workaround.

### Workshop conflict or overlapping worktree

Stop and reconcile. Never force-push the workshop branch.

### Insufficient evidence

Record `insufficient_evidence`, the exact missing fact, and the safest next diagnostic action. Do not create a speculative repair.

### Feature request disguised as a bug

Record `feature_request`. Prepare design/readiness work only when requested. Do not silently implement new architecture.

### High-risk defect

Record the exact boundary and ask for a scoped decision. Preserve evidence and do not make a partial dangerous patch.

## 19. Session completion report

At the end, report concisely:

```text
server access and deployed SHA truth
workshop baseline SHA
new issues leased / accepted by agent
source issues diagnosed
findings and classifications
repairs completed or blocked
branches / commits / PRs
focused / adjacent / full tests
manual or server smoke performed
not run and why
production changed: yes | no
next human decision, if any
```

Do not include raw logs, lease tokens, secrets, full tenant data, or private environment output.

The session is complete when durable workshop and GitHub facts match the report. It is not complete merely because code exists in a local worktree.

## 20. Suggested invocation

After installing this skill, the user may start a session with a brief request such as:

```text
Запусти ремонт OfficeFlow. Перевір незавершений backlog, дістань зафіксовані помилки з production intake, продіагностуй їх і виправ безпечні дефекти. Архітектуру, дані, merge і deploy без мого окремого рішення не змінюй.
```

The user does not need to restate previously recorded issues.
