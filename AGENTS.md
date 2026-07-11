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
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`
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

- `docs/architecture/OfficeFlow_Architecture_Framing.md`
- `docs/architecture/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`

For user access, onboarding, and authorization, read:

- `docs/User_Access_Model_Roadmap.md`

For server-side operations, first check the private local runbook:

- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Never use `docs/local-only/*.example.md` as the live server runbook. Example
files are public-safe placeholders only.

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

Controlled learning is expected for semantic layers, but it must be safe.
The detailed umbrella contract is `docs/Self_Learning_Layer.md`.

Valid learning candidates include:

- action aliases;
- InfoHelp topic aliases;
- capability question phrasings;
- contact/customer aliases;
- service aliases;
- document classification hints;
- recurring customization patterns.

Learning rules:

- learn only after successful resolution or explicit user confirmation;
- never learn destructive confirmations;
- never invent canonical actions;
- never bypass the canonical action registry;
- store scoped aliases/patterns, not raw sensitive full transcripts;
- separate intent from slots;
- variable commands must be patterns, not literal aliases;
- limit count, allow review, and support expiry/cleanup where practical.

Current implemented learning is partial. Do not generalize it beyond what code
and docs prove.

## State-Aware Runtime Explanation

When a user is inside an FSM flow, that state owns the conversation.

The bot should explain:

- what is happening now;
- what input is expected;
- what format is required;
- why the previous input failed;
- how to cancel safely.

Active FSM state must not fall back into top-level routing, idle attachment
classification, or generic InfoHelp unless the flow explicitly allows it.

## Canonical Action Completion Gate

A new canonical top-level action is not `implemented` until the full runtime,
docs, and tests loop is complete:

- action registered in `docs/llm/Canonical_Action_Registry.md`;
- Python execution owner exists: handler/FSM/service route;
- top-level resolver receives action only through Python-provided
  `allowed_actions`;
- `action_hints`, if used, describe semantic meaning, not a literal alias
  whitelist;
- text/command route works or is explicitly not applicable;
- voice reachability works and has tests, or a documented reason says voice is
  not applicable;
- active FSM states do not fall back into top-level routing;
- in-FSM controls/confirmations are documented in
  `docs/llm/In_Action_Response_Registry.md`;
- precision-sensitive exact-value steps stay text/file-only where needed;
- README/user-facing architecture docs are updated when the action changes the
  surface map;
- `PROJECT_LOG.md` and `CHANGELOG.md` are updated when required;
- product UX evals prove the actual user journey, not just unit branches.

## Capability Completion Rule

A user-facing capability, top-level action, admin command, integration,
workflow, or support surface is not complete if Product Truth, InfoHelp, tests,
evals, forbidden claims, or the project log are stale.

Before the final report for any user-facing feature, the agent must check and
report:

- Runtime changed?
- Canonical action / resolver updated, if applicable?
- Product Truth updated?
- InfoHelp updated?
- UX/eval smoke updated?
- Tests added or updated?
- Forbidden claims checked?
- `PROJECT_LOG.md` updated?
- Docs maturity label updated?

If a runtime change is intentionally not user-facing, say why. If Product Truth
or InfoHelp is intentionally not changed, explain why the user cannot ask about
that behavior as a capability.

## Voice Rules

Voice may:

- start top-level actions;
- choose bounded actions/fields/options in FSM;
- provide non-precision natural language where the flow supports it.

Voice must not fill precision-sensitive exact values unless a specific
documented flow safely normalizes and validates them:

- IBAN;
- IČO;
- DIČ;
- IČ DPH;
- email;
- invoice number;
- item numeric values, prices, quantities;
- final item descriptions;
- service alias names;
- exact destructive confirmations.

## Canonical DecisionResolver Rule

All confirmation-like replies must go through:

- `bot/services/decision_resolver.py`

Do not add local parsers for:

- `ano` / `nie`;
- `ok` / `tak`;
- `schvalit` / `upravit` / `zrusit`;
- Slovak diacritics variants;
- Cyrillic or multilingual confirmation variants.

Every new confirmation-like flow must:

- choose the decision family: `yes_no` or `approve_edit_cancel`;
- register the context in resolver tests;
- add handler-level tests proving shared resolver usage, not local branching.

## Access And Security Boundary

Unknown or unauthorized Telegram users must not create:

- supplier profiles;
- contacts;
- invoices;
- invoice PDFs;
- accounting documents;
- document metadata;
- temporary upload files;
- tenant storage directories;
- workspaces.

Unknown or unauthorized users must not trigger:

- LLM calls;
- STT calls;
- LMM/Vision calls;
- document classification/extraction calls.

Pending access requests are not tenants, not supplier profiles, and not
business onboarding. Approval is required before `/supplier` and before any
business flow.

## OfficeFlow Attachment And Document Intake Boundary

Idle photo/PDF classification may happen only after authorization.

Active FSM state wins over idle classifier. If the user is in an active FSM
flow, attachment routing must respect that state before any idle OfficeFlow
classifier.

No automatic contact creation from receipts, incoming invoices, PDFs, photos,
or idle attachments.

No automatic expense/accounting document save before user approval. AI/LMM may
extract or draft; Python validates; user confirms; only then Python saves.

## Data Migration And Persisted Data Safety

Any change that can affect already-saved data is migration-sensitive.

Persisted data includes:

- SQLite or future DB rows;
- invoice `pdf_path` values and generated PDF files;
- storage folders, file names, and path conventions;
- accounting document originals and metadata JSON sidecars;
- tenant/workspace keys;
- `telegram_id` / `supplier_telegram_id` scoping;
- JSON metadata schemas;
- backup, archive, cleanup, and deletion routines.

Before migration-sensitive implementation, do not proceed directly to code or
server writes.

Required pre-work:

1. identify existing persisted data affected by the change;
2. describe current shape and proposed shape;
3. state whether migration or repair is required;
4. provide a read-only audit plan;
5. provide backup and rollback plan for server-side data;
6. provide dry-run migration/repair plan where practical;
7. ask explicit approval before any write, migration, cleanup, delete, or path
   rewrite;
8. record the decision in `PROJECT_LOG.md`;
9. update `docs/TZ_FakturaBot.md` or a dedicated migration/runbook doc if
   runtime behavior, data ownership, or storage architecture changes.

Forbidden:

- silently changing DB/storage semantics;
- relying on cross-tenant fallback reads instead of migration;
- rewriting persisted paths without backup;
- deleting legacy data because new code no longer reads it;
- treating local/dev absolute paths as canonical server paths;
- changing DB engine, schema, tenant scoping, or storage layout because it
  seems cleaner.

## Evaluation Standards

AI/product changes require more than unit tests.
The detailed evaluation contract is
`docs/Evaluation_and_Smoke_Test_Standards.md`.

Use focused unit tests for code behavior and product UX evals/smoke tests for
real journeys, including:

- first `/start` journey;
- `/menu` clarity;
- arbitrary capability questions;
- unknown plausible business request;
- active FSM confusion;
- destructive action safety;
- unsupported feature honesty;
- customization request confirmation;
- no hidden side effects;
- no fake support claims;
- voice and text parity where promised;
- tenant/access isolation where data is touched.

Do not mark a phase complete if only primitive fallback behavior is present.

## Test Commands

Run tests from `D:\AI_Model\Ai_assistant`.

Use:

```powershell
python -m pytest -q
```

Avoid bare `pytest -q`; it may not include the project root on `sys.path` and
can fail to import `bot`.

## Documentation And Project Log

After every meaningful session, update `PROJECT_LOG.md`.

If a change affects product logic, MVP scope, architecture, capability truth,
or user-facing behavior, update `docs/TZ_FakturaBot.md` or the relevant
contract doc.

No hidden conceptual changes.

Documentation must distinguish:

- runtime-supported;
- partial;
- planned;
- unsupported;
- unknown;
- dangerous;
- requires setup/admin/external credentials.

## Result Format

After project changes, default to:

1. short summary of what changed;
2. unified diff;
3. no unrelated improvements.

If the user asks for another format, follow the user's format.

## What Not To Do

Do not:

- reduce OfficeFlow/FakturaBot to a command menu bot;
- answer capability questions with only `/menu`;
- call Level 0/1 fallback a completed AI layer;
- hide unsupported capabilities behind vague wording;
- invent features, integrations, or setup state;
- bypass Product Truth;
- add handler-local confirmation parsers;
- auto-save AI/LMM results without confirmation;
- trigger AI calls for unauthorized users;
- expand controlled tenant-scoped runtime into full SaaS without explicit
  product decision and docs update;
- add billing, public signup, per-client bot token orchestration, or complex
  role/workspace admin flows without explicit scope decision;
- add external lookup as a critical dependency without product and failure-mode
  approval;
- add modules that expand scope without acceptance criteria and evaluation.

## Definition Of Done

A task is not done if:

- code changed but the decision was not logged;
- concept changed but product docs were not updated;
- a new flow exists but docs/contracts do not mention it;
- a user-facing capability exists but Product Truth or InfoHelp cannot explain
  it truthfully;
- eval/smoke artifacts do not cover the changed capability surface;
- MVP scope changed but no source-of-truth doc records it;
- AI layer level is overstated;
- only unit tests pass but the relevant user journey is not evaluated;
- user-facing copy claims capabilities the runtime cannot prove.
