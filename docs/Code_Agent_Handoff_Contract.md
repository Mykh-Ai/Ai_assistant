# Code-Agent Handoff Contract

## Purpose

This document defines how OfficeFlow/FakturaBot may turn an approved
customization or product request into a bounded task for a code agent.

Code-agent handoff is not runtime magic, not deployment approval, and not a
replacement for human review. It is a controlled task-packaging layer that
gives an implementation agent the correct context, contracts, files, tests,
acceptance criteria, no-go constraints, and approval gates.

## Current Status

This document is a docs-first contract.

As of this documentation reset:

- bot runtime does not implement automatic code-agent handoff unless later code
  proves otherwise;
- customization request storage is not implemented unless later code proves
  otherwise;
- no runtime path may claim that a code agent has been launched or that work
  will be deployed without implemented integration and human approval.

## Normative Status

This is a mandatory-read contract for work touching:

- customization request conversion to implementation tasks;
- admin/developer review flows;
- future code-agent orchestration;
- PDF/layout customization tasks;
- integration tasks such as email, SMS, Google Drive, accounting export;
- migration-sensitive implementation planning;
- AI-generated implementation proposals.

Companion docs:

- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Implementation_Agent_Checklist.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/FakturaBot_Data_Migration_Runbook.md`;
- `docs/FakturaBot_PDF_Layout_Spec.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/New_Action_Design_Checklist.md`.

## Core Rule

A code-agent handoff is allowed only after:

1. Product Truth classification;
2. user-confirmed customization or admin-created task;
3. risk classification;
4. human/admin approval where required;
5. clear scope and out-of-scope boundaries;
6. acceptance criteria;
7. test/evaluation plan;
8. no-go constraints;
9. rollback/migration notes where relevant.

The handoff must not imply merge, deploy, or production execution.

## Allowed Sources

A task package may originate from:

- confirmed customization request;
- admin/developer-created implementation request;
- documented product roadmap item approved for implementation;
- bug fix with clear runtime evidence;
- migration/repair request with backup and rollback plan.

A task package must not originate from:

- raw unconfirmed user request;
- unsupported capability question without request confirmation;
- LLM suggestion alone;
- unauthorized user input;
- destructive request without explicit human review.

## Handoff Package

Minimum task package:

```text
task_id
source_request_id
created_by
approved_by
created_at
product_need
current_product_truth_status
risk_level
target_maturity_level
docs_to_read
contracts_to_follow
likely_files
implementation_scope
out_of_scope
acceptance_criteria
tests_to_run
product_evals
no_go_constraints
human_approval_gate
rollback_plan
```

Recommended additional fields:

```text
workspace_or_account_scope
data_migration_required
persisted_data_affected
security_review_required
external_credentials_required
manual_review_steps
visual_layout_criteria
observability_logging_required
deployment_notes
post_merge_verification
status
agent_output_refs
review_notes
```

## Required Docs To Include

Every task package must include `AGENTS.md` and the focused docs relevant to
the touched scope.

AI-layer task examples:

- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Implementation_Agent_Checklist.md`;
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`.

PDF/layout task examples:

- `docs/FakturaBot_PDF_Layout_Spec.md`;
- invoice PDF tests/snapshots/manual review notes;
- relevant invoice generation modules.

Migration-sensitive task examples:

- `docs/FakturaBot_Data_Migration_Runbook.md`;
- affected storage/DB docs;
- backup and rollback plan.

## Task Status Model

Task statuses:

- `draft`;
- `awaiting_admin_approval`;
- `approved_for_agent`;
- `assigned_to_agent`;
- `agent_patch_proposed`;
- `tests_failed`;
- `needs_revision`;
- `ready_for_human_review`;
- `approved_for_merge`;
- `merged`;
- `deployed`;
- `rejected`;
- `cancelled`;
- `expired`.

Do not use `merged`, `deployed`, or `implemented` unless the real action
happened and is verified.

## Risk Rules

Risk levels inherit from `docs/Customization_Request_Layer.md`.

High/critical tasks require explicit human approval before:

- code-agent execution if credentials, external sending, storage sync,
  accounting export, security, or migration are involved;
- merge;
- deployment;
- production data changes.

The code agent may prepare a proposal. It must not be treated as an authority
to ship.

## No-Go Constraints

Every handoff must state no-go constraints. Common no-go rules:

- do not invent Product Truth;
- do not bypass Python-owned validation;
- do not bypass access control;
- do not bypass DecisionResolver;
- do not add external dependencies without approval;
- do not change DB/storage semantics without migration plan;
- do not store secrets in repo or chat;
- do not auto-save AI outputs without confirmation;
- do not weaken tenant/workspace scoping;
- do not call Level 0/1 fallback a complete AI layer;
- do not modify unrelated flows.

## Acceptance Criteria

Acceptance criteria must be concrete and testable.

Weak:

```text
Make Google Drive work.
```

Better:

```text
When a workspace has approved Google credentials and a configured folder,
generated invoice PDFs are copied to that folder after local PDF generation
succeeds. If Drive upload fails, the local invoice/PDF remains valid and the
user receives a clear retry/admin message. No upload is attempted without
configured credentials. Tests cover success, missing credentials, upload
failure, and tenant isolation.
```

## Test And Eval Requirements

Task packages must include:

- unit tests for deterministic logic;
- handler/service tests for user-facing flows;
- access/tenant tests when data is involved;
- DecisionResolver tests for confirmation-like replies;
- Product Truth/InfoHelp evals for capability answers;
- migration dry-run tests where persisted data is touched;
- product UX evals for real journeys;
- manual review steps where automation is insufficient.

Unit tests alone are not enough for user-facing AI/product changes.

## PDF/Layout Tasks

PDF or invoice template tasks must include visual criteria:

- target page size;
- fonts and fallback behavior;
- table column widths;
- row wrapping rules;
- item detail wrapping;
- QR / Pay by Square placement;
- footer placement;
- logo/assets handling;
- long customer/supplier names;
- long item names/descriptions;
- multi-item invoices;
- regression snapshots or manual rendered-PDF review.

PDF layout tasks must not be accepted only because code compiles.

## Migration-Sensitive Tasks

If a task touches persisted data, include:

- affected tables/files/paths;
- current data shape;
- proposed data shape;
- migration or repair requirement;
- read-only audit plan;
- backup plan;
- rollback plan;
- dry-run plan where practical;
- server approval gate.

This applies to DB rows, invoice PDFs, accounting document storage, JSON
sidecars, tenant/workspace keys, backup/archive/delete routines, and path
conventions.

## External Integration Tasks

For email, SMS, Google Drive, accounting export, or other external services,
include:

- provider/integration choice;
- credential model;
- consent/authorization model;
- failure mode;
- retry policy;
- logging/audit needs;
- cost/rate-limit considerations;
- tenant/workspace isolation;
- admin setup requirements;
- safe fallback when integration is unavailable.

Do not implement external sending/storage as a hidden side effect.

## Agent Output Requirements

A code agent must return:

- changed files;
- summary of behavior;
- tests run and results;
- tests not run and why;
- product evals/manual checks run;
- known limitations;
- migration/rollback notes if relevant;
- docs updated;
- remaining review questions.

The agent output is not approval. A human/developer review gate remains.

## Human Approval Gates

Human approval is required before:

- converting high/critical requests into implementation;
- merging code;
- deploying runtime changes;
- running migrations/repairs;
- changing server state;
- enabling external sending/storage integrations;
- accepting PDF/layout changes as final if visual review is required.

## Prompt Skeleton For Handoff

Use a structured task, not a vague prompt:

```text
Task:
Product need:
Current Product Truth:
Target maturity level:
Docs/contracts to read:
Files/modules likely touched:
Existing code owners to inspect:
Scope:
Out of scope:
Acceptance criteria:
Tests:
Product UX evals:
Migration/storage impact:
Security/access impact:
PDF/layout criteria:
No-go constraints:
Approval gates:
Expected output:
```

The implementation agent must follow
`docs/Implementation_Agent_Checklist.md` before editing code.

## Runtime Claim Rules

The bot may say a code-agent handoff is available only when:

- request storage exists;
- admin/developer approval path exists;
- task package generation exists;
- status tracking exists;
- the claim is backed by Product Truth.

Until then, user-facing text must say only that such a request can be planned
or reviewed according to implemented request/admin flows.

## Acceptance Criteria For Handoff Layer

The Code-Agent Handoff Layer is not complete until:

- confirmed requests can be converted into task packages;
- packages include docs/contracts/files/tests/evals/no-go constraints;
- high/critical tasks require human approval;
- status tracking exists;
- code-agent output is reviewed before merge/deploy;
- runtime claims are backed by Product Truth;
- product UX evals cover at least one PDF/layout request and one integration
  request;
- no production side effects happen automatically.

## No-Go Rules

Do not:

- launch code-agent work from unconfirmed user text;
- imply deployment approval;
- omit docs/contracts from task package;
- omit tests/evals;
- omit migration/rollback notes when data is touched;
- allow code-agent output to bypass human review;
- claim handoff exists in runtime before Product Truth proves it;
- use handoff as a way to sneak in unrelated refactors.
