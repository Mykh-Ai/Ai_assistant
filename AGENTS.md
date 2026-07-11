# AGENTS.md

## Mission

This repository is the working base for **OfficeFlow / FakturaBot**.

OfficeFlow/FakturaBot is not a Telegram command bot with menus. It is an
AI-assisted business operating layer for craftspeople, živnostníci, small
s.r.o. companies, accountants, and people who run real business workflows.

The current runtime surface is Telegram, but Telegram is only the interface.
The product direction is a business assistant that understands natural
language, guides users through business processes, stays honest about product
capabilities, learns only from confirmed signals, and keeps all side effects
behind deterministic Python gates.

The north-star product doctrine is documented in:

- `docs/Product_Doctrine_2030.md`

Agents must treat that document as mission and product-direction context, not
as proof that every described future capability is already implemented.

## Non-Negotiable Rule

Do not invent project state.

If a capability is not proven by current code, product docs, contract docs, or
`PROJECT_LOG.md`, treat it as not implemented. If the documents describe a
future target but runtime code does not implement it, report it as `planned` or
`partial`, not `supported`.

Static fallback text, a menu reply, a placeholder handler, or a deterministic
repair patch is not a completed AI product layer.

## Current Product Baseline

The current project is a Python/aiogram Telegram runtime with SQLite, OpenAI
STT/LLM/LMM boundaries, invoice PDF generation, supplier profiles, contacts,
service aliases, accounting document intake, access control, FSM flows,
bounded semantic routing, DecisionResolver, and partial self-learning for
confirmed invoice/contact/service aliases.

The project already has **controlled tenant-scoped multi-user runtime**:

- one shared Telegram bot token, backend, and SQLite database in the current
  controlled rollout model;
- authorization/allowlist/admin approval before business flows;
- tenant/workspace scoping through fields such as `telegram_id`,
  `supplier_telegram_id`, and accounting workspace keys;
- tenant-scoped invoice numbering/storage paths where implemented;
- accounting document storage scoped under workspace/year/month structures.

The project does **not** yet have full commercial SaaS runtime unless later
docs/code explicitly say so:

- no public self-serve signup;
- no billing/subscription system;
- no per-client Telegram bot token orchestration;
- no per-client VPS/container/DB provisioning flow;
- no full role/workspace administration system;
- no broad account-specific adaptive workflow engine.

Agents must preserve the current tenant-scoped isolation model and must not
describe the product as either single-user-only or full SaaS.

## Sources Of Truth

Use different sources for different kinds of truth.

Product mission and direction:

1. `docs/Product_Doctrine_2030.md`
2. `docs/TZ_FakturaBot.md`

Current implementation and decision truth:

1. current code
2. `PROJECT_LOG.md`
3. `docs/TZ_FakturaBot.md`
4. focused contract docs
5. `CHANGELOG.md`

Agent conduct and repository workflow:

1. `AGENTS.md`
2. focused contract docs
3. `PROJECT_LOG.md`

If product doctrine and runtime code differ, do not claim the doctrine as
implemented. Classify the capability as `planned`, `partial`, `unsupported`, or
`unknown` according to evidence.

If `docs/TZ_FakturaBot.md`, `PROJECT_LOG.md`, and code disagree, inspect the
code and log first, then state the conflict explicitly before changing
behavior.

`docs/archive/` is historical context only. Do not use archived documents as
active source of truth, mandatory pre-read material, or proof that a capability
is current. If an archived document is useful for background, verify every
claim against active docs, code, and `PROJECT_LOG.md`.

## Documentation Preflight And Maintenance

Before starting non-trivial work, inspect the relevant current documents under
`docs/` and follow the project rules they define. Do not treat `docs/archive/`
or example/local placeholder files as active truth unless an active source
points to them and the claim is verified against current code/logs.

If the current docs, code, `PROJECT_LOG.md`, or runtime evidence disagree,
state the mismatch clearly before changing behavior and propose the needed
documentation or implementation repair.

At the end of each meaningful work session, update the relevant existing
documentation under `docs/` when the work changes product behavior, runtime
architecture, capability truth, AI/LLM contracts, storage, access, deployment,
or user-facing workflows. Prefer updating the current source-of-truth document
over creating a new one; create a new document only when no existing active doc
can own the decision or behavior cleanly. Tiny read-only answers and trivial
commands do not require documentation churn.

## Mandatory Contract Reads

Before changing handlers, FSM flows, top-level actions, in-action decisions,
confirmation flows, LLM prompts, document intake, attachment routing,
voice/text routing, user access, storage, DB schema, or authorization, read the
relevant contract docs first.

For any AI-layer or user-facing intelligence task, read:

- `docs/Product_Doctrine_2030.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Self_Learning_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

For InfoHelp/support/capability guidance tasks, also read:

- `docs/Info_Help_Guidance_Layer.md`
- `docs/Customization_Request_Layer.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`

For code-agent handoff, customization implementation planning, or
agent-generated implementation proposals, also read:

- `docs/Customization_Request_Layer.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/Implementation_Agent_Checklist.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/FakturaBot_Data_Migration_Runbook.md` when persisted data can be
  touched
- `docs/FakturaBot_PDF_Layout_Spec.md` when invoice/PDF layout can be touched

For confirmation-like decisions, read:

- `docs/Canonical_Decision_Resolver_Contract.md`

For OfficeFlow / accounting / document intake / idle attachments, read:

- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`

For user access, onboarding, and authorization, read:

- `docs/User_Access_Model_Roadmap.md`

For server-side operations, first check the private local runbook:

- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Never use `docs/local-only/*.example.md` as the live server runbook. Example
files are public-safe placeholders only.

## Top-Level / Subflow Architecture Gate

For a new or materially changed top-level action, structured slot, in-FSM
control, subflow, preview/confirmation flow, callback flow, or state-aware
text/voice/button route:

1. a task-specific Architecture Design Proof must exist under
   `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
2. its verdict must be `ready_for_handoff` before an implementation prompt is
   written or code changes begin;
3. the implementation prompt must transfer the approved action boundary,
   slots, route, FSM graph, decision/callback rules, side effects, negative
   space, Product Truth target, and acceptance scenarios without asking the
   coding agent to invent them;
4. the coding agent must stop on `material_design_variance` rather than silently
   creating a replacement architecture;
5. post-implementation evidence must include the Conversation Acceptance Proof
   defined in `docs/Evaluation_and_Smoke_Test_Standards.md`.

## Agent Preflight

Before implementation, the agent must state or record:

- docs/contracts read;
- constraints extracted;
- touched scopes: confirmation, routing, LLM, STT, LMM, FSM, storage, DB,
  access, server, PDF/layout, product docs;
- current implementation status: `implemented`, `partial`, `planned`,
  `unsupported`, `unknown`, `dangerous`, `requires_setup`, `requires_admin`, or
  `requires_external_credentials`;
- AI maturity level being implemented;
- what is explicitly out of scope;
- what product/user journey proves the change works;
- for new or materially changed top-level/subflow/FSM work, the approved
  Architecture Design Proof path and verdict;
- the required post-implementation Conversation Acceptance Proof artifact and
  verdict model from `docs/Evaluation_and_Smoke_Test_Standards.md`;
- what self-learning hooks were considered;
- what source of truth backs every user-facing product claim.

If these points are not known, the task is not ready for implementation.

## Approval Discipline

Do not bother the user with secondary confirmations for routine work.

Read-only work inside the repo never requires permission:

- reading files;
- searching code/docs;
- `git status`, `git diff`, `git log`, `git branch`;
- other commands that do not modify files, git history, runtime state,
  database/storage, server state, or external services.

If the user explicitly asks for a scoped edit, that request counts as approval
for that scoped edit.

Ask for explicit approval only before:

- major concept/scope changes not already requested;
- destructive actions;
- server/network actions;
- dependency installation;
- DB/storage/runtime writes not explicitly requested;
- migration-sensitive changes;
- commit, merge, rebase, or push unless directly requested;
- edits outside the approved workspace.

Do not turn sandbox limitations or read-only command failures into repeated
approval loops. Simplify the read-only command, use available context, record
the limitation briefly, and continue when the task can still be done correctly.

## AI Architecture Contract

The authority split is mandatory:

- Python orchestrates.
- AI extracts, canonicalizes, explains, or drafts within Python-provided bounds.
- Python validates.
- User confirms where needed.
- Python saves or executes.

LLM/LMM/STT must not:

- invent canonical actions;
- execute side effects;
- bypass registries;
- query or mutate DB/storage directly;
- claim unsupported product capabilities;
- turn `unknown` into action execution;
- replace deterministic safety gates.

Python must provide allowed actions/options/candidates. The model may select
only from those bounds or return `unknown`.

## AI Layer Maturity Model

Every AI-layer change must declare the maturity level it actually implements.

Level 0 - placeholder/fallback:

- static "I do not understand" or `/menu`;
- no product truth lookup;
- no domain understanding;
- no request capture.

Level 1 - static guidance:

- deterministic help text or fallback hints;
- useful recovery copy;
- no capability-aware product truth.

Level 2 - capability-aware Q&A:

- understands arbitrary capability/how-to/support questions;
- checks a Product Truth source;
- answers `supported`, `partial`, `planned`, `unsupported`, or `unknown`;
- proposes a safe next step.

Level 3 - customization request creation:

- detects unsupported or account-specific business needs;
- drafts a structured request;
- asks confirmation;
- saves a pending request only after approval.

Level 4 - controlled self-learning:

- stores confirmed aliases/topic mappings/patterns;
- scoped, reviewable, bounded, and non-destructive;
- never bypasses canonical registries.

Level 5 - code-agent handoff:

- converts confirmed requests into implementation tasks;
- includes files/contracts/tests/no-go constraints;
- requires human approval before merge/deploy.

Level 6 - evaluated autonomous implementation proposal:

- prepares patch/module proposal, test plan, rollback notes, and evaluation
  results;
- still requires deterministic tests and human approval.

Level 7 - account-specific adaptive workflow layer:

- adapts workflows per workspace/account based on confirmed preferences,
  setup state, and approved patterns;
- remains bounded by Product Truth and deterministic gates.

A phase is not complete unless runtime, docs, tests, product UX evals, and
acceptance criteria match the declared level.

## Product Truth Layer Rules

User-facing AI must answer real business questions, not hide behind `/menu`.
The detailed Product Truth contract is `docs/Product_Truth_Layer.md`.

When a user asks whether the bot can do something, the bot must eventually be
able to:

1. understand the question;
2. check Product Truth;
3. classify the capability as `supported`, `partial`, `planned`,
   `unsupported`, `unknown`, `dangerous`, `requires_setup`, `requires_admin`,
   or `requires_external_credentials`;
4. explain the current limitation honestly;
5. offer a safe next step;
6. offer a customization request when appropriate.

Product Truth must include:

- runtime-supported capabilities;
- partial capabilities;
- planned capabilities;
- unsupported capabilities;
- dangerous/sensitive operations;
- current limitations;
- commands/actions;
- forbidden claims;
- account/workspace setup state.

LLM output is never Product Truth. It may only verbalize truth prepared or
validated by Python.

## Customization Request Layer

Unsupported or account-specific requests must not end in a blind
`nerozumiem`.
The detailed request contract is `docs/Customization_Request_Layer.md`.

Future customization requests must use a structured object with at least:

- `request_id`;
- `user_id` / `workspace_id`;
- `original_user_text`;
- `normalized_business_need`;
- `detected_domain`;
- `capability_status`;
- `proposed_task_title`;
- `proposed_description`;
- `proposed_acceptance_criteria`;
- `required_user_inputs`;
- `risk_level`;
- `requires_human_approval`;
- `status`;
- `created_at` / `updated_at`.

The bot must not promise that unsupported features are already available. It
may draft a request, ask for confirmation, and save a pending request after
approval.

## Self-Learning Layer

Controlled learning is expected for semantic layers, but learning must be
confirmed, tenant-scoped, reviewable, and bounded. Read
`docs/Self_Learning_Layer.md` and
`docs/Confirmed_Semantic_Alias_Learning_Contract.md` before adding learning.

Do not:

- learn from rejected/cancelled output;
- store raw full transcripts as reusable aliases;
- let learned mappings change Product Truth;
- let learned mappings create canonical actions;
- let one tenant's learning affect another tenant.

## Routing And FSM Rules

Active FSM owns ordinary continuation input. Idle top-level routing, InfoHelp,
and generic fallback must not consume input that belongs to an active state.

For new or changed stateful flows:

- use shared active-FSM navigation/stale-state behavior;
- preserve text/voice/button convergence;
- use Canonical DecisionResolver for confirmation-like replies;
- fail closed for stale, wrong-state, legacy, or expired callbacks;
- reject voice where exact typed values are required;
- keep unknown/ambiguous input recoverable and side-effect free.

## Authorization And Tenant Rules

Authorization must happen before STT/LLM/LMM, temp files, storage directories,
DB rows, or business side effects.

All lookups and writes must use the current tenant/workspace/user scope. Never
accept model output as tenant identity or authorization.

## Data, Migration, And Server Safety

Persisted-data changes require current-shape audit, migration/repair decision,
backup, rollback, and dry-run plan where practical. Server/runtime writes,
deployment, and migrations require explicit approval.

Use the private local runbook only for real server operations. Never claim a
server, migration, deployment, or external integration was verified when it was
not.

## Test And Evaluation Rules

Use focused tests during development and run the full suite before claiming
runtime completion when feasible:

```powershell
python -m pytest -q
```

User-facing changes require the evaluation layers defined in
`docs/Evaluation_and_Smoke_Test_Standards.md`. Unit tests alone are not enough
for Level 2+ or a new stateful journey.

## Documentation Synchronization

When behavior changes, update the existing active owner documents, registries,
Product Truth, InfoHelp, `PROJECT_LOG.md`, and `CHANGELOG.md` where appropriate.
Prefer existing owners over creating a new document. Do not maintain duplicate
contracts for the same responsibility.

## Completion And Reporting

Final output must distinguish:

- implemented behavior;
- partial/reserved/planned behavior;
- tests/evals run and not run;
- real versus mocked/manual evidence;
- remaining limitations;
- migration/server/deploy actions actually performed or not performed;
- Architecture Design Proof and Conversation Acceptance Proof verdicts when
  applicable.

Passing tests is not permission to merge or deploy.
