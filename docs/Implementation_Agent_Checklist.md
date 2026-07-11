# Implementation Agent Checklist

## Purpose

This guide defines how an implementation agent must approach an approved
OfficeFlow/FakturaBot product change, customization request, bug fix, or
feature implementation.

It is the general implementation gate for changes that are not necessarily new
top-level canonical actions. For top-level actions or in-FSM canonical
controls, also use `docs/llm/New_Action_Design_Checklist.md`, the task-specific
approved Architecture Design Proof, and the Conversation Acceptance Proof
section of `docs/Evaluation_and_Smoke_Test_Standards.md`.

The goal is to prevent shallow "just patch it" work. The agent must understand
the product need, read the governing docs, inspect the current code, choose the
lowest-risk implementation path, preserve existing behavior, add tests/evals,
and report what was proven.

## When To Use This Guide

Use this guide for:

- approved customization requests;
- product features that extend an existing flow;
- PDF/layout changes;
- Product Truth or InfoHelp runtime work;
- self-learning extensions;
- code-agent task execution;
- external integration work;
- reporting/export/reminder/workflow changes;
- bug fixes with product behavior impact;
- any implementation where the safest path is not obvious.

Do not use this guide to skip the top-level action checklist. If the change
adds or upgrades a canonical top-level action, read and apply
`docs/llm/New_Action_Design_Checklist.md` too.

## User-Facing Capability / Top-Level Action Completion Checklist

Any user-facing runtime change must close the product truth and guidance loop
in the same implementation slice. Runtime code alone is not enough.

For every new or changed capability, top-level action, admin command,
integration, workflow, support path, or user-visible limitation, verify:

- canonical action registry and `allowed_actions` are updated when the change
  adds or changes a top-level executable intent;
- bounded resolver examples and action hints describe product meaning, not just
  literal aliases;
- Product Truth has a `capability_id` for the changed surface;
- Product Truth status is correct: `supported`, `partial`, `planned`,
  `unsupported`, or `unknown`;
- flags/context are correct: `dangerous`, `requires_setup`, `requires_admin`,
  and `requires_external_credentials`;
- safe next steps are accurate for the current runtime;
- limitations are explicit, especially for partial integrations or workflows;
- forbidden claims cover overpromises, hidden side effects, automatic learning,
  implementation promises, unsupported integrations, and delivery guarantees;
- InfoHelp can answer what the capability does, how to use it, setup
  requirements, limitations, and what it does not do;
- eval/smoke artifacts include the new happy path and overclaim boundaries;
- tests cover Product Truth, InfoHelp, runtime behavior, authorization, setup
  state, and no hidden side effects where applicable;
- `PROJECT_LOG.md` records the implemented maturity level and what remains out
  of scope.

If a feature is implemented only partly, Product Truth must say `partial` and
InfoHelp must explain the subset. If a feature is removed, disabled, or blocked
by missing credentials/setup, Product Truth and InfoHelp must be downgraded in
the same patch.

Example: future Google Drive invoice storage cannot be closed by adding an
upload helper alone. The implementation must also update Product Truth status
and limitations, InfoHelp answers for "Vieš ukladať faktúry na Google Drive?"
and "Ako zapnem Google Drive?", eval smoke, tests, `PROJECT_LOG.md`, and
forbidden claims such as "all documents sync automatically" unless that is
actually implemented.

## Required Starting Inputs

The agent must not begin implementation from a vague request.

Minimum task input:

```text
Task:
Product/business need:
Decision status:
Current Product Truth:
Target behavior:
Out of scope:
Acceptance criteria:
Risk level:
Required docs:
Tests/evals expected:
Approval gates:
Architecture Design Proof path and verdict, when applicable:
Required Conversation Acceptance Proof artifact/path and verdict model, when applicable:
```

If the task came from a user customization request, the agent must also know:

- source request id or summary;
- user-confirmed need;
- required user inputs or examples;
- admin/developer approval status;
- whether the request is product-wide or account-specific.

If those inputs are missing, the first job is to produce a short clarification
or implementation-readiness report, not to patch code.

## Mandatory Docs To Read

Always read:

1. `AGENTS.md`;
2. `docs/Product_Doctrine_2030.md`;
3. `docs/AI_Layer_Implementation_Standards.md`;
4. `docs/Product_Truth_Layer.md`;
5. `docs/Evaluation_and_Smoke_Test_Standards.md`;
6. `docs/TZ_FakturaBot.md`;
7. `PROJECT_LOG.md` recent relevant entries;
8. current code around the target module.

For customization/request-driven work, also read:

- `docs/Customization_Request_Layer.md`;
- `docs/Code_Agent_Handoff_Contract.md`.

For AI/LLM/FSM/routing/action work, also read:

- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
- the task-specific approved Architecture Design Proof;
- the Conversation Acceptance Proof section of
  `docs/Evaluation_and_Smoke_Test_Standards.md`.

For confirmation-like replies, read:

- `docs/Canonical_Decision_Resolver_Contract.md`.

For self-learning, read:

- `docs/Self_Learning_Layer.md`;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`.

For PDF/layout work, read:

- `docs/FakturaBot_PDF_Layout_Spec.md`;
- invoice PDF generator code and tests.

For DB/storage/path/server-impacting work, read:

- `docs/FakturaBot_Data_Migration_Runbook.md`;
- storage/DB owner code;
- server/local runbook when server state is in scope.

For OfficeFlow/document intake work, read:

- `docs/architecture/OfficeFlow_Architecture_Framing.md`;
- `docs/architecture/OfficeFlow_Storage_Model_Proposal.md`;
- `docs/Document_Intake_Module_Proposal.md`;
- `docs/Document_Intake_MVP_Implementation_Plan.md`.

## Pre-Implementation Analysis

Before editing code, the agent must answer:

```text
What user problem is being solved?
Is this already supported, partial, planned, unsupported, or unknown?
Is this a new top-level action, an extension of an existing flow, or internal
runtime behavior?
Which existing module/service owns the closest behavior?
Can this be integrated into an existing module safely?
Is a new module justified?
What current behavior must not change?
What data model or storage shape is affected?
Does this touch tenant/workspace boundaries?
Does this touch external credentials/services?
Does this touch PDF/layout output?
Does this touch AI/LLM/STT/LMM behavior?
Does this touch confirmation or destructive behavior?
What tests/evals will prove value and safety?
For top-level/subflow/FSM work, does the approved Architecture Design Proof
match the current repository?
What exact public-entry conversation traces must the final acceptance proof
contain?
```

If any answer depends on guessing, inspect more code/docs or stop with a
readiness report. For a material contradiction between the approved design and
current runtime, report `material_design_variance`; do not silently invent a
replacement architecture.

## Codebase Exploration Rules

The agent must inspect existing ownership before designing a patch.

Required exploration:

- find current handlers/routes for the affected flow;
- find service/storage owner;
- find existing tests for that behavior;
- find Product Truth/docs entries that will need updates;
- search for similar patterns before adding new abstractions;
- check active FSM boundaries if conversation state is involved;
- check access/authorization path before AI or storage behavior;
- check current voice/text boundaries if input mode is involved.

Prefer existing patterns over new architecture. Add a new module only when it
removes real complexity or matches a clear ownership boundary.

## Integrate Or Create New Module

Default preference:

- extend the existing owner service/handler when the behavior belongs to an
  existing workflow;
- create a small helper when shared logic is needed by multiple owners;
- create a new module only for a distinct domain with its own lifecycle,
  storage, tests, and ownership.

Do not create a new module only because it is easier than understanding the
current one.

Decision criteria:

```text
Existing owner can support it without becoming incoherent -> integrate.
Logic is reused by multiple flows but has no storage/lifecycle -> helper.
New domain has separate storage, lifecycle, registry, or review process -> new
module.
```

## Product Truth And Scope

Before implementation, classify the change:

- `supported`;
- `partial`;
- `planned`;
- `unsupported`;
- `unknown`;
- `dangerous`;
- `requires_setup`;
- `requires_admin`;
- `requires_external_credentials`.

After implementation, update Product Truth docs/registry only to the level
actually proven.

Do not mark the capability `supported` if:

- only docs were added;
- only fallback copy exists;
- only a draft prompt exists;
- only one untested branch exists;
- runtime supports only a narrow slice.

## Top-Level Action Decision

Not every product feature needs a new top-level canonical action.

Ask:

- does the user need to start this as a standalone task?
- is there a new business operation?
- is this only an option/field inside an existing flow?
- is this only a PDF/layout/data model extension?
- is this only InfoHelp/Product Truth behavior?

If it is a new top-level action or canonical in-FSM control, use
`docs/llm/New_Action_Design_Checklist.md`.

If it is not a top-level action, do not invent a canonical action just to make
implementation easier.

## AI Boundary

For AI-assisted features:

- Python owns orchestration, validation, Product Truth, side effects, and
  storage.
- AI may extract, classify, draft, explain, or select from Python-provided
  options.
- Python must validate AI output before use.
- User confirmation is required where business data or side effects are
  affected.

Do not:

- let AI invent schema fields;
- let AI save data;
- let AI change Product Truth;
- let AI pass destructive confirmations;
- trigger AI calls for unauthorized users.

## Data And Migration Safety

If the change touches persisted data, stop and prepare migration-sensitive
pre-work.

Persisted data includes:

- SQLite or future DB rows;
- invoice PDFs and `pdf_path`;
- accounting document files and JSON sidecars;
- tenant/workspace keys;
- file names and storage paths;
- archive/backup/delete routines.

Required before write implementation:

- current data shape;
- proposed data shape;
- migration/repair need;
- read-only audit plan;
- backup plan;
- rollback plan;
- dry-run plan where practical;
- user/admin approval if server data is touched.

## PDF/Layout Safety

For invoice PDF/layout work, define visual criteria before implementation:

- exact location of new block/field;
- behavior when value is empty;
- wrapping rules;
- table spacing;
- long text behavior;
- QR placement;
- footer placement;
- multi-item behavior;
- regression/snapshot/manual review expectation.

If the feature depends on a sample invoice or old template, ask for the sample
before implementation or document that the first implementation uses a generic
layout pending sample review.

## Test Plan

Tests must match risk and touched scope.

Common requirements:

- unit tests for pure logic;
- handler/FSM tests for user-facing flows;
- service/storage tests for DB/file writes;
- DecisionResolver tests for confirmation-like flows;
- access/tenant tests for any user data;
- Product Truth/InfoHelp tests for capability claims;
- PDF/layout regression or manual rendered review for invoice layout;
- migration dry-run tests where persisted data changes;
- product UX smoke tests from `docs/Evaluation_and_Smoke_Test_Standards.md`;
- for new or materially changed top-level/subflow/FSM behavior, a task-specific
  Conversation Acceptance Proof that starts at public entrypoints and proves
  action/slot transfer, state transitions, side effects, final state, semantic
  negative space, and Product Truth/InfoHelp behavior.

Run focused tests during development and full suite before marking runtime
complete when feasible:

```powershell
python -m pytest -q
```

If full tests are not run, state why and do not overclaim completion.

## Implementation Plan Required

Before editing code for a non-trivial change, produce or record a short plan:

```text
Docs/contracts read:
Constraints extracted:
Existing code owners:
Chosen implementation path:
Why not a new module / why a new module is justified:
Data/storage impact:
AI/LLM impact:
FSM/confirmation impact:
Access/tenant impact:
PDF/layout impact:
Tests/evals:
Out of scope:
```

This plan can be in the working summary, task package, or project log depending
on scope.

## Implementation Rules

During implementation:

- keep changes scoped;
- preserve existing behavior unless the task explicitly changes it;
- reuse established services and helpers;
- avoid broad refactors;
- keep user-facing copy honest;
- update docs in the same patch when product behavior changes;
- update `PROJECT_LOG.md` after meaningful changes;
- update `CHANGELOG.md` when user-visible release behavior changes.

## Product Eval Examples

For a new optional invoice description block:

- invoice without description keeps old PDF layout;
- invoice with description renders block above item rows;
- long description wraps safely;
- multi-item invoice still renders;
- user can preview/edit/cancel;
- old invoices remain readable;
- Product Truth says partial/supported only for the proven behavior.

For Google Drive storage:

- no upload without credentials;
- local invoice remains valid if upload fails;
- tenant-scoped folder rules are enforced;
- Product Truth says requires external credentials/setup;
- user gets clear failure/retry/admin message.

For SMS reminders:

- no sending without provider/setup/consent;
- schedule and opt-out behavior are explicit;
- rate limits and logs exist;
- high-risk admin approval is required.

## Final Output Required

The implementation agent must report:

- docs/contracts read;
- files changed;
- implementation summary;
- integration path chosen and why;
- risks considered;
- tests run and results;
- tests/evals not run and why;
- Product Truth status after change;
- InfoHelp answer coverage after change;
- forbidden claims checked;
- docs updated;
- migration/rollback notes if relevant;
- remaining gaps or follow-up tasks;
- Architecture Design Proof path and design-variance status when applicable;
- Conversation Acceptance Proof path and final verdict when applicable.

## No-Go Rules

Do not:

- start from code before understanding the product need;
- ignore existing module ownership;
- create a new module to avoid reading current code;
- add a top-level action for an internal field/option;
- call docs-only work runtime implementation;
- call partial behavior supported;
- bypass Product Truth;
- leave InfoHelp unable to explain a new user-facing capability;
- add a user-facing action or integration without eval/smoke coverage;
- bypass DecisionResolver;
- bypass access/tenant gates;
- let AI own side effects;
- change persisted data without migration pre-work;
- change PDF layout without visual criteria;
- skip product UX evals for Level 2+ behavior;
- hide tests not run;
- treat passing component tests as proof of a complete user journey;
- claim a new/changed top-level or subflow complete without the required
  Conversation Acceptance Proof;
- silently deviate from an approved Architecture Design Proof.
