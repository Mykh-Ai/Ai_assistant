# Runtime Issue Intake V1 — Implementation Handoff

Handoff status: approved design transferred for a future implementation task.

This document is a code-agent handoff under
`docs/Code_Agent_Handoff_Contract.md`. It derives directly from the approved
Stage 1 Architecture Design Proof and does not authorize the implementation
agent to choose a different action, route, FSM, persistence, authorization, or
Product Truth architecture.

This is not an implementation prompt. It is not merge, deploy, migration,
server-write, or production approval.

## Task identity

| Field | Handoff value |
|---|---|
| Task ID | `RUNTIME_ISSUE_INTAKE_V1` |
| Source request | Product-owner task `CREATE_RUNTIME_ISSUE_INTAKE_V1_IMPLEMENTATION_HANDOFF` |
| Source request ID | `CREATE_RUNTIME_ISSUE_INTAKE_V1_IMPLEMENTATION_HANDOFF` |
| Created by | Documentation agent under the product-owner request |
| Approved by | Product owner through the source request and the approved Stage 1 Architecture Design Proof |
| Created at | 2026-07-28 |
| Task status | `approved_for_agent`; implementation has not started |
| Product-owner approval | Stage 1 architecture approved through merged PR #48; this task approves creation of the implementation handoff only |
| Approved main baseline | `a070f419f1c3e75b25101f4d52ff6c6cdfe31540` |
| Architecture Design Proof | `docs/features/runtime_issue_autorepair_v1/01_ARCHITECTURE_DESIGN_PROOF.md` |
| Architecture Design Proof verdict | `ready_for_handoff` |
| Design verification status | `design_matches_runtime` |
| Risk level | Medium: shared routing, active-FSM preservation, administrator authorization, privacy-bounded context, and additive persisted data |
| Target maturity | Public-route-proven administrator-only canonical action with synchronized Product Truth, InfoHelp, tests, and Conversation Acceptance Proof; no autorepair maturity |
| Current Product Truth | Unsupported/not registered: `/issue`, `report_runtime_issue`, issue persistence, and runtime issue guidance do not exist |
| Target Product Truth | `supported` only after implementation and proof: an administrator can store one issue through the approved command, bounded text, or bounded voice routes; `requires_admin=true`; repair remains unavailable |
| Workspace/account scope | Trusted active workspace when resolvable; otherwise nullable workspace with the trusted reason `no_active_workspace` |
| Persisted-data impact | Additive dedicated runtime-issue table or tables only |
| Security review | Required for administrator gating, trusted identifiers, context sanitization, secret redaction, and workspace isolation |
| External credentials | None for Stage 1 |
| Human approval gate | Implementation output requires human review before merge, migration, deployment, or production use |
| Observability/logging | Bounded structured technical logging only; never persist secrets, raw FSM data, files, audio, or unbounded logs |
| Deployment notes | No deployment or production action is authorized by this handoff |
| Post-merge verification | Requires separate approved migration/deployment/smoke work after implementation review; not part of this handoff |

### Code-Agent Handoff Contract field coverage

| Required package field | Owner in this handoff |
|---|---|
| `task_id` | Task identity |
| `source_request_id` | Task identity |
| `created_by` | Task identity |
| `approved_by` | Task identity |
| `created_at` | Task identity |
| `product_need` | Product need |
| `current_product_truth_status` | Task identity and Product Truth and InfoHelp target |
| `risk_level` | Task identity |
| `target_maturity_level` | Task identity |
| `docs_to_read` | Required reading for the implementation task |
| `contracts_to_follow` | Required reading, Canonical action, FSM contract, Database and migration handoff, and Strict Stage 2 exclusion |
| `likely_files` | Public routing and verified insertion points |
| `implementation_scope` | Canonical action, Public routing, FSM contract, Side-effect ownership, and Database and migration handoff |
| `out_of_scope` | Forbidden Stage 1 effects and Strict Stage 2 exclusion |
| `acceptance_criteria` | Acceptance criteria |
| `tests_to_run` | Required test plan |
| `product_evals` | Conversation Acceptance Proof and Product Truth and InfoHelp target |
| `no_go_constraints` | No-go constraints |
| `human_approval_gate` | Task identity and Implementation output requirements |
| `rollback_plan` | Required implementation pre-work |

Relevant recommended fields are also explicit: workspace/account scope,
persisted-data impact, additive migration classification, security review,
external credentials, observability/logging, deployment notes, post-merge
verification, Architecture Design Proof reference/verdict, and Conversation
Acceptance Proof reference/verdict vocabulary.

### Design verification evidence

The approved design was rechecked against exact `main` at
`a070f419f1c3e75b25101f4d52ff6c6cdfe31540`.

- The baseline is the docs-only merge commit for PR #48. No runtime, test,
  schema, configuration, or deployment change occurred between the audited
  runtime and this handoff baseline.
- Idle semantic routing is still owned by
  `bot/handlers/invoice.py::process_invoice_text` and
  `bot/services/semantic_action_resolver.py::resolve_semantic_action`.
- Idle non-command text still enters through
  `bot/handlers/invoice.py::semantic_top_level_input`.
- Voice/STT routing is still owned by
  `bot/handlers/voice.py::handle_voice`.
- Active-FSM global interception is still owned by
  `bot/services/active_fsm_guard.py::ActiveFsmMessageMiddleware` and
  `handle_active_fsm_text_update`.
- General authorization and explicit administrator checks are still owned by
  `bot/services/authorization.py::TelegramUserAuthorizationMiddleware` and
  `is_admin_telegram_user`.
- Trusted read-only workspace resolution is still owned by
  `bot/services/workspace_context.py::WorkspaceContextService.resolve_for_user_readonly`.
- SQLite bootstrap is still owned by `bot/services/db.py::init_db`, with both
  exact-column checks for existing tables and additive-column patterns.
- Product Truth and InfoHelp are still owned by
  `bot/services/product_truth.py` and `bot/services/info_help.py`.
- No current symbol owns `report_runtime_issue`, `/issue`, runtime-issue
  persistence, or Stage 2 maintenance behavior.

Verdict: `design_matches_runtime`. Proposed symbols below remain proposed
because the approved design intentionally precedes implementation.

## Product need

An administrator must be able to report one observed bot/runtime problem
immediately, including while a business journey is active, without cancelling,
clearing, replaying, advancing, or otherwise mutating that journey.

The intake stores an observation and trusted bounded context. It does not prove
that the observation is a bug, diagnose a cause, approve a repair, or promise
that anything will be fixed.

## Required reading for the implementation task

The implementation agent must read current versions of:

- `AGENTS.md`;
- this handoff;
- `docs/Code_Agent_Handoff_Contract.md`;
- `docs/Implementation_Agent_Checklist.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/FakturaBot_Data_Migration_Runbook.md`;
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
- `docs/features/runtime_issue_autorepair_v1/README.md`;
- `docs/features/runtime_issue_autorepair_v1/00_REPOSITORY_AUDIT.md`;
- `docs/features/runtime_issue_autorepair_v1/01_ARCHITECTURE_DESIGN_PROOF.md`;
- `docs/features/runtime_issue_autorepair_v1/02_AUTOREPAIR_POLICY.md` for the
  downstream exclusion boundary only;
- `docs/features/runtime_issue_autorepair_v1/03_DAILY_MAINTENANCE_RUNBOOK.md`
  for the downstream exclusion boundary only;
- `docs/features/runtime_issue_autorepair_v1/04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md`;
- `docs/features/runtime_issue_autorepair_v1/05_ACCEPTANCE_SCENARIOS.md`;
- recent relevant `PROJECT_LOG.md` entries; and
- every current code/test owner named in this handoff.

Before editing runtime code, the implementation agent must repeat the
read-only design verification and report exactly one:

- `design_matches_runtime`;
- `minor_nonsemantic_variance`;
- `material_design_variance`.

For `material_design_variance`, stop. Report the exact contradiction and the
minimum architecture decision required. Do not modify the approved
Architecture Design Proof or invent a replacement design.

## Canonical action

The implementation must transfer exactly this action:

| Field | Required value |
|---|---|
| Canonical action | `report_runtime_issue` |
| Official command | `/issue <complete description>` |
| Execution authority | Administrator only |
| Convergence | Command, bounded natural text, and bounded voice use one shared Python capture owner |
| Button support | None in V1 |
| Issue-intake FSM | None |
| Confirmation | None |
| Repair permission | Never implied by report text, wording, urgency, or acknowledgement |

The complete description is supplied in the same message. Bare `/issue` sends
usage immediately, creates no row, opens no FSM, and does not capture the next
message.

All user-facing feature responses are Slovak. Slovak, Ukrainian, Russian, or
mixed-language administrator input may be recognized through the existing
bounded semantic-resolver pattern. Do not implement a multilingual issue
phrase whitelist.

## Semantic boundary

### Positive issue examples

- `/issue Po stlačení Uhradená zostalo tlačidlo načítavať.`
- `Chyba: po potvrdení sa nezobrazila správa.`
- `Po uložení bločku zostala stará klávesnica; ulož to ako problém.`
- A voice transcript with the same explicit observed-problem meaning.

Examples are semantic context, not literal aliases or a Python keyword list.

### Boundary matrix

| User meaning | Required outcome | Must not become |
|---|---|---|
| Explicit administrator request to record one concrete observed runtime problem | `report_runtime_issue` | Diagnosis, repair, callback replay, customization request |
| `/issue` without a description | Slovak usage response; no row | Pending intake or next-message capture |
| “Vieš nahlásiť chybu?” | Product Truth/InfoHelp | Issue write |
| “Pridajte automatické mesačné faktúry.” | Existing customization/feature-request handling or `unknown` | Confirmed defect |
| “Ktoré faktúry nie sú uhradené?” | `invoice_analytics` | Issue write |
| “Označ faktúru 06 ako uhradenú.” | `mark_existing_invoice_paid` | Issue write |
| Supplier/profile edit request | `edit_supplier` or its current owner | Issue write |
| Contact creation/edit input | Existing contact owner | Issue write |
| Work-time command or slot input | Existing work-time owner | Issue write |
| Ordinary active-FSM free text | Current FSM owner | Issue interrupt |
| Ambiguous normal business text | Existing action, clarification, or `unknown` | Write default |

### Neighboring-action rules

- Capability/how-to/support questions remain informational and perform no
  issue write.
- Customization and feature requests remain owned by the existing
  customization/human-review architecture.
- Invoice, contact, supplier, receipt, accounting-document, work-time,
  analytics, access, profile, and callback actions retain their current
  owners.
- `edit_supplier`, contact actions, work-time actions, and any other existing
  canonical action must not be silently reclassified without approved
  evidence.
- A message mentioning “bug”, “chyba”, “issue”, or “error” is not sufficient
  by itself.
- Conflicting evidence, insufficiently concrete observations, ambiguity, and
  `unknown` must never default to issue persistence.
- The report may describe a business action, but reporting must not execute,
  repeat, undo, or repair that action.

## Slot contract

Every Stage 1 slot below is required by the approved design.

| Slot | Required contract |
|---|---|
| `description` | Sanitized original observation, target bound 10–2000 UTF-8 characters; required; sourced from command remainder, resolved text, or STT transcript |
| `short_title` | Maximum 120 characters; deterministically derived by Python from the sanitized description |
| `reported_at` | Trusted UTC runtime timestamp and the only intake timestamp |
| `actor_telegram_id` | Trusted Telegram actor ID; required; never accepted from report text or voice |
| `telegram_update_id` | Trusted Telegram update identity; required by the approved contract |
| `telegram_message_id` | Trusted Telegram message identity; required |
| `telegram_chat_id` | Trusted Telegram chat identity; required |
| `workspace_id` | Trusted active workspace ID or `null`; never accepted from report content |
| `workspace_resolution_reason` | `active_workspace` or `no_active_workspace`, derived by Python |
| `source_channel` | `text` or `voice`, assigned by the route; `/issue` is `text` |
| `active_fsm_state` | Trusted bounded FSM state name or `null` |
| `active_fsm_context_summary` | Versioned, allowlisted, sanitized, size-bounded context map |
| `reported_build_sha` | Trusted 40-hex SHA or `null`; no current runtime owner may be invented |
| `build_sha_status` | Bounded trusted status such as `known`, `unavailable`, or `stale` |
| `privacy_metadata` | Redaction-policy version, bounded flags/categories, and truncation status without secret values |
| `deduplication_key` | Versioned stable key derived by Python from trusted Telegram delivery identity, actor/chat, and source; description alone is forbidden |

### Slot invariants

- `reported_at` is the only Stage 1 intake timestamp.
- Do not add `occurred_at`, occurrence-time parsing, or natural-language time
  guessing.
- Python derives `short_title`; do not call an LLM solely to title an issue.
- Workspace, actor, Telegram identifiers, FSM state, build SHA,
  authorization, permissions, repair authority, and deployment authority never
  come from user text or voice.
- One trusted active workspace stores its ID. If no active workspace is
  resolvable, store `workspace_id=null` and
  `workspace_resolution_reason=no_active_workspace`; do not discard the valid
  administrator issue.
- The implementation must identify a real trusted source for every required
  Telegram identifier. Existing `getattr(message, "update_id", None)` debug
  usage is not proof of a non-null stable update identity. If the approved
  required identity cannot be obtained from the aiogram event context, fail
  safely and report design variance rather than synthesizing it from user
  text.
- A missing trusted runtime build owner stores `reported_build_sha=null` with
  the appropriate status. It does not reject intake.
- Do not persist raw FSM data, full transcripts as reusable knowledge, raw
  audio, files, credentials, tokens, secrets, private keys, private paths,
  environment dumps, or unbounded logs.
- Secret-like input must be redacted before description/title persistence and
  before any acknowledgement echo. If safe redaction cannot be guaranteed,
  reject the write truthfully.

## Public routing and verified insertion points

### Existing verified owners

| Concern | Current owner |
|---|---|
| Router registration/order | `bot/handlers/__init__.py::routers` |
| General authorization | `bot/services/authorization.py::TelegramUserAuthorizationMiddleware` |
| Explicit admin check | `bot/services/authorization.py::is_admin_telegram_user` |
| Idle non-command text entry | `bot/handlers/invoice.py::semantic_top_level_input` |
| Idle semantic action resolution | `bot/handlers/invoice.py::process_invoice_text` |
| Bounded resolver | `bot/services/semantic_action_resolver.py::resolve_semantic_action` |
| Voice/STT entry | `bot/handlers/voice.py::handle_voice` |
| Active-FSM global guard | `bot/services/active_fsm_guard.py::ActiveFsmMessageMiddleware` and `handle_active_fsm_text_update` |
| Read-only workspace resolution | `bot/services/workspace_context.py::WorkspaceContextService.resolve_for_user_readonly` |
| SQLite bootstrap | `bot/services/db.py::init_db` |
| Product Truth | `bot/services/product_truth.py::_REGISTRY`, `get_capability`, and `validate_registry` |
| InfoHelp | `bot/services/info_help.py::_PRODUCT_TRUTH_OVERVIEW_IDS`, `_SLOVAK_CAPABILITY_COPY`, `classify_info_help_capability`, and `build_product_truth_guidance` |

### Proposed Stage 1 owners

The following names do not exist at the approved baseline and must remain
clearly proposed until implemented:

- proposed router module:
  `bot/handlers/runtime_issue.py`;
- proposed command handler:
  `cmd_runtime_issue`;
- proposed shared capture owner:
  `handle_runtime_issue_capture`;
- proposed bounded text/voice issue-intent helper:
  `maybe_handle_runtime_issue`;
- proposed service:
  `bot/services/runtime_issue.py::RuntimeIssueService`;
- proposed sanitizer:
  a versioned Python-owned runtime-issue context/privacy sanitizer;
- proposed DB bootstrap owner:
  `_bootstrap_runtime_issue_table` or an equivalently narrow named owner.

These labels may move for a minor nonsemantic reason, but ownership and
convergence may not change.

### Likely implementation file set

Existing files likely to require narrow implementation edits are:

- `bot/handlers/__init__.py`;
- `bot/handlers/invoice.py`;
- `bot/handlers/voice.py`;
- `bot/services/active_fsm_guard.py`;
- `bot/services/authorization.py`;
- `bot/services/db.py`;
- `bot/services/product_truth.py`;
- `bot/services/info_help.py`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Info_Help_Guidance_Layer.md`; and
- `PROJECT_LOG.md`.

Likely new files are the proposed handler/service owners and focused
runtime-issue tests. Existing adjacent test files are listed in the Required
test plan. The implementation agent must narrow this set from the current
tree; this list is not authority to modify unrelated files.

### `/issue`

- Register a dedicated command handler through the normal router list.
- Keep `TelegramUserAuthorizationMiddleware` as the outer general guard.
- Perform `is_admin_telegram_user` explicitly before context collection or
  persistence.
- The approved route requires general authorization plus admin authorization;
  do not silently broaden `/issue` into an authorization-bypass command.
- Parse only the exact `/issue` command and its same-message remainder.
- Bare `/issue` calls no resolver and writes nothing.
- The command handler must delegate complete descriptions to the shared Python
  capture owner; it must not own SQL.

### Idle semantic text

- Add `report_runtime_issue` to the Python-provided top-level candidates only
  in an explicitly administrator-authorized context.
- Extend the action hints in
  `bot/handlers/invoice.py::process_invoice_text` with the approved meaning,
  positive examples, and `not_this` boundaries.
- Route the canonical result to the same shared capture owner before any
  invoice-scoped runtime lookup or business action.
- A non-admin must not reach the issue-intent resolver or issue service.
- Capability questions continue through Product Truth/InfoHelp.

### Voice after STT

- Keep the outer middleware rejection for generally unauthorized users before
  file download/STT.
- In `bot/handlers/voice.py::handle_voice`, immediately after successful
  non-empty STT and before issue resolution, persistence, log access, active
  issue capture, or maintenance activity, enforce the explicit admin boundary
  for the issue candidate.
- Generally authorized non-admin voice must not receive
  `report_runtime_issue` as an executable allowed action and must never reach
  issue persistence. Ordinary non-issue voice routing remains unchanged.
- Admin voice uses the same bounded issue intent and the same shared capture
  owner as text. Do not create a voice-only store, phrase parser, sanitizer, or
  acknowledgement path.
- Pass the original trusted Telegram message/update context to capture; an
  injected text adapter must not become the authority for missing identifiers.

### Active-FSM global issue interrupt

- Extend
  `bot/services/active_fsm_guard.py::handle_active_fsm_text_update` with one
  narrow issue branch before state-specific business dispatch and before any
  stale clear-and-idle reroute.
- Exact active `/issue <description>` is deterministic.
- Active natural text/voice requires bounded, administrator-only issue
  resolution. Ordinary active-FSM free text continues to the current state
  owner.
- After handled capture, return `True` so the message/transcript is not
  dispatched into the business state.
- Do not call `_route_through_idle_top_level` for a captured active-FSM issue.
- Do not call `state.clear`, `state.set_state`, or issue-owned
  `state.update_data`.
- The normal middleware may update only its established technical activity
  metadata after an authorized message lifecycle. Tests must distinguish this
  from protected business data.

### Authorization before side effects

The required order is:

```text
general authorization
-> explicit admin gate
-> bounded issue intent where needed
-> trusted context read and sanitizer
-> deduplicated transaction
-> truthful acknowledgement
```

For voice, general authorization precedes STT; the issue-specific admin gate
precedes the issue resolver and persistence immediately after STT. LLM/STT
never decides authorization.

### Workspace resolver

Use
`WorkspaceContextService.resolve_for_user_readonly(actor_telegram_id)`.
Handle no membership or no active selection as the approved nullable-workspace
outcome without calling mutating `resolve_for_user` and without creating an
active selection. Never resolve a workspace from the description.

### SQLite service

The dedicated service owns:

- schema compatibility checks for its own table;
- sanitization-input validation;
- ID/title/dedup derivation;
- explicit named-column SQL;
- one transaction for insert-or-return-existing;
- bounded record reads required for acknowledgement; and
- optional bounded read-only retrieval/export if actually required for Stage
  1 verification.

Handlers and resolvers do not execute SQL.

### Product Truth and InfoHelp

Synchronize the implementation through the current owners:

- add the canonical action to
  `docs/llm/Canonical_Action_Registry.md`;
- add it to executable Python `allowed_actions` only in approved admin
  contexts;
- do not add an issue decision family to
  `docs/llm/In_Action_Response_Registry.md`;
- add `runtime_issue_intake` to
  `bot/services/product_truth.py::_REGISTRY`;
- add Slovak feature copy and capability classification/overview coverage in
  `bot/services/info_help.py`;
- update `docs/Product_Truth_Layer.md` and
  `docs/Info_Help_Guidance_Layer.md` only to the behavior actually proven;
- add focused Product Truth/InfoHelp tests and evals; and
- add the required implementation entry to `PROJECT_LOG.md`.

## FSM contract

Stage 1 has no issue FSM. It is one-message intake.

```text
IDLE or EXISTING BUSINESS FSM
  -> ephemeral capture call
  -> exact original business state
```

Required behavior:

- bare `/issue` gives usage immediately;
- bare `/issue` does not capture the next message;
- active business FSM state remains unchanged;
- protected business FSM data remains unchanged;
- existing business journey ownership remains unchanged;
- ordinary shared technical activity metadata may follow existing authorized
  middleware behavior;
- no `state.clear`;
- no `state.set_state`;
- no issue-owned `state.update_data`;
- no suspend/restore;
- no replay;
- no issue pending context;
- no issue back/cancel route;
- no issue keyboard;
- persistence failure preserves the business journey;
- duplicate Telegram delivery preserves the business journey; and
- acknowledgement failure does not remove or duplicate the committed issue.

The implementation must compare the protected FSM state and business data
separately from ordinary technical activity metadata such as
`active_fsm_started_at` and `active_fsm_last_activity_at`.

## Confirmation and callbacks

Stage 1 has:

- no issue confirmation;
- no DecisionResolver family;
- no callback token;
- no callback nonce;
- no issue keyboard;
- no issue callback state; and
- no callback-owned side effect.

The complete message is the report, not permission to diagnose, repair, replay,
merge, deploy, or roll back anything.

Reporting a problem must not execute or replay the business action described by
the report. Existing callbacks remain owned by their current handlers,
including `bot/handlers/decision_callbacks.py` and
`bot/handlers/invoice_followup.py`. Their authorization, state, expiry,
legacy, duplicate, acknowledgement, and keyboard behavior must remain
unchanged.

## Side-effect ownership

### Allowed Stage 1 effects

Only these effects are allowed:

1. Read trusted bounded actor, Telegram, workspace, FSM, runtime-build, and
   privacy context.
2. Insert at most one dedicated runtime-issue record.
3. Return the existing issue ID for duplicate Telegram delivery.
4. Send one truthful Slovak stored acknowledgement or one truthful Slovak safe
   failure/usage response.
5. Optionally expose a bounded read-only issue retrieval/export operation if
   strictly required for verification.

The optional read boundary may not change status, claim, lease, create a run,
generate a claimed manifest, or create an outbox item.

### Forbidden Stage 1 effects

Stage 1 must not:

- mutate invoices, contacts, suppliers, receipts, accounting documents,
  work-time, profiles, access records, or any other business object;
- execute, repeat, acknowledge, or replay an existing business callback;
- mutate files or persist issue attachments/audio;
- repair code;
- perform Git work;
- claim or lease an issue;
- acquire a maintenance/global lease;
- create a maintenance run;
- generate a claimed issue manifest;
- diagnose or classify a report;
- create a diagnosis/result;
- create a notification outbox record;
- merge, deploy, restart, roll back, or touch production.

## Database and migration handoff

Stage 1 is an additive persisted-data change.

### Required target shape

- Create dedicated runtime-issue table or tables.
- Do not add runtime-issue columns to invoice, contact, supplier, receipt,
  accounting-document, work-time, customization, archive, access, workspace,
  or other business tables.
- Do not rebuild any existing business table.
- Do not copy or transform existing business data.
- Do not change existing identifiers, constraints, uniqueness, tenant keys, or
  paths.
- SQLite is the canonical writable source for the Stage 1 issue record.

The future implementation must propose the exact dedicated table shape from
the approved slots before editing `bot/services/db.py`. It must not import
Stage 2 statuses, claim fields, run fields, manifest fields, diagnosis fields,
result fields, or outbox fields into the Stage 1 schema.

Service-owned Stage 1 record metadata is distinct from user/route slots and
must carry forward the approved data contract:

- service-generated `issue_id`;
- `schema_version`;
- `intake_status=new`, with no Stage 2 transition authority;
- `record_version`; and
- service-owned `created_at` and `updated_at`.

These fields are never supplied by report text or voice.

### SQL and compatibility rules

The implementation must:

- use `CREATE TABLE IF NOT EXISTS`;
- use explicit named columns in every `SELECT`, `INSERT`, and `UPDATE`;
- never use `SELECT *`;
- never depend on tuple column positions;
- set `sqlite3.Row` or use explicit aliases and read by column name;
- validate compatibility from required owned columns plus an approved schema
  version;
- tolerate an unknown optional column when all owned requirements remain
  compatible;
- fail safely or require an approved additive migration when a required column
  is missing;
- fail safely for an incompatible type or constraint;
- never silently ignore an incompatible required field; and
- never use automatic DROP/rebuild.

An additive migration is limited to a new table, new nullable/defaulted column,
or new index. Table rebuild, data copy, constraint replacement, column
removal, identifier change, and business-data transformation are destructive
or transforming and outside Stage 1.

### Required implementation pre-work

Before schema code, the implementation agent must document:

1. current database shape relevant to bootstrap and connections;
2. exact proposed dedicated-table shape, types, constraints, indexes, and
   schema version;
3. read-only schema audit;
4. additive bootstrap/migration sequence;
5. temporary-database migration test;
6. backup expectation before production startup/deployment;
7. rollback/removal plan before production deployment; and
8. proof method that existing business tables, schemas, row counts, values,
   constraints, and identifiers remain unchanged.

The temporary-database proof must cover:

- fresh empty database;
- current pre-issue database shape;
- repeated idempotent bootstrap;
- required columns plus one unknown optional column;
- missing required column;
- incompatible required type or constraint; and
- pre/post fingerprints or equivalent table/row comparisons for existing
  business data.

Implementation may prepare reviewed additive schema code and tests. It may not
run a production migration, start the production bot against a production
database, or claim production readiness without a separate backup,
rollback, deployment, and smoke approval.

## Acceptance criteria

Stage 1 is acceptable only when all of the following are proven together:

1. An authorized administrator can store exactly one sanitized issue through
   `/issue <complete description>`, bounded natural text, or bounded voice.
2. Bare `/issue`, ambiguous business text, capability questions, and
   unauthorized input create no issue.
3. All public routes converge on one Python capture owner and one dedicated
   SQLite service.
4. Duplicate Telegram delivery returns the original issue ID and creates no
   second record.
5. Active business FSM state, protected business data, business journey
   ownership, and existing callbacks remain unchanged.
6. Trusted actor/workspace/Telegram/FSM/build/privacy context cannot be
   supplied or overridden by report text or voice.
7. The additive bootstrap and compatibility checks preserve every existing
   business table and row.
8. Product Truth, InfoHelp, registries, tests, evals, and Slovak user-facing
   copy match only the behavior actually proven.
9. The Conversation Acceptance Proof covers section A only and has an allowed
   verdict supported by real public-route evidence.
10. No Stage 2 schema, status transition, service, interface, side effect, or
    placeholder is introduced.

## Required test plan

Resolver-only or service-only tests are insufficient. The implementation must
prove the real public routes and shared-layer regressions.

### Routing and semantics

- exact `/issue <description>`;
- bare `/issue`;
- bounded natural-text recognition;
- ambiguous normal business text;
- capability question;
- customization/feature request negative space;
- invoice, contact, supplier/profile, receipt, accounting-document, and
  work-time neighboring actions remain unchanged;
- ambiguity and `unknown` create no issue row.

### Voice and authorization

- voice converges to the shared capture owner;
- generally unauthorized voice is blocked before STT;
- generally authorized but non-admin voice is blocked from the issue resolver
  immediately after STT and before issue persistence/log/maintenance access;
- non-admin ordinary voice behavior remains unchanged;
- admin voice supplies no trusted slots from transcript text.

### FSM and callbacks

- active-FSM text capture preserves state and protected business data;
- active-FSM voice capture preserves state and protected business data;
- ordinary technical activity metadata follows only the current middleware
  invariant;
- bare `/issue` in an active FSM does not arm another state;
- persistence failure preserves the active journey;
- duplicate delivery preserves the active journey;
- existing callbacks remain unchanged, including valid, stale, wrong-state,
  legacy, duplicate, and unauthorized cases.

### Workspace, actor, and privacy

- trusted active workspace;
- no active workspace stores null plus the trusted reason;
- workspace isolation;
- actor/admin isolation;
- text/voice workspace override is ignored as authority;
- secret redaction;
- sanitizer safe rejection;
- no raw FSM state, audio, file, secret, or unbounded log persistence.

### Persistence and idempotency

- committed insert;
- persistence failure and transaction rollback;
- duplicate Telegram delivery returns the original issue ID;
- a similar description in a new Telegram delivery creates a new issue;
- additive schema with one unknown optional column;
- missing required-column safe failure;
- incompatible type/constraint safe failure;
- repeated bootstrap;
- existing business tables and rows unchanged.

### Product Truth and InfoHelp

- capability entry status, `requires_admin`, supported channels, limitations,
  forbidden claims, and safe next steps;
- “Vieš nahlásiť problém?” answers without executing intake;
- “Ako nahlásim problém?” explains one-message `/issue`;
- no claim that a report proves a defect or authorizes repair;
- automatic maintenance/autorepair remains unavailable.

### Unchanged public journeys

For every modified shared routing layer, prove at least:

- one unchanged old text journey; and
- one unchanged old voice journey.

At minimum include representative existing text and voice journeys through
`process_invoice_text`, `handle_voice`, and the active-FSM guard. Select actual
existing journeys such as invoice creation/view, contact intake, work-time, or
active-FSM continuation according to the final touched files.

### Adjacent current suites

The implementation test selection must include or justify the relevant parts
of:

- `tests/test_active_fsm_guard.py`;
- `tests/test_voice_state_routing.py`;
- `tests/test_state_control.py`;
- `tests/test_invoice_intent_prerouter.py`;
- `tests/test_decision_callbacks.py`;
- `tests/test_invoice_followup_handler.py`;
- `tests/test_access_request_flow.py`;
- `tests/test_tenant_safety.py`;
- `tests/test_workspace_context.py`;
- `tests/test_product_truth.py`;
- `tests/test_info_help.py`;
- DB/bootstrap and temporary migration tests; and
- focused new runtime-issue public-route/service tests.

Run focused tests during implementation and the repository-required broader
suite before claiming completion. If the full suite or a required environment
smoke is not run, record exactly why and use `runtime_not_proven` where the
evidence does not establish the public journey.

## Conversation Acceptance Proof

The implementation agent must create:

`docs/evals/RUNTIME_ISSUE_INTAKE_V1_conversation_acceptance_proof.md`

Use only these verdicts from
`docs/Evaluation_and_Smoke_Test_Standards.md`:

- `safe_to_commit`;
- `needs_revision`;
- `blocked_by_design_gap`;
- `runtime_not_proven`.

`safe_to_commit` is not merge or deployment approval.

The proof must:

- reference the approved Architecture Design Proof and this handoff;
- identify the tested branch/commit or working-tree state;
- state real versus mocked boundaries and tests not run;
- trace the actual command, text, voice, authorization, active-FSM, shared
  Python owner, persistence, idempotency, response, and final-state paths;
- map every Stage 1 slot and material design requirement to a current
  file/symbol plus named test/eval; and
- prove only section A of
  `docs/features/runtime_issue_autorepair_v1/05_ACCEPTANCE_SCENARIOS.md`.

Sections B–D are Stage 2 design continuity only. They are not part of Stage 1
implementation, tests, handoff completion, or Conversation Acceptance Proof.
The Stage 1 implementation agent must not materialize them.

## Product Truth and InfoHelp target

The implementation must synchronize:

- canonical action registry;
- executable allowed-action contexts;
- Product Truth capability entry and primary status;
- `requires_admin=true`;
- supported channels: command/text/voice, with the approved authorization
  boundaries;
- current limitations;
- forbidden claims;
- safe next steps;
- InfoHelp capability question;
- InfoHelp usage question;
- relevant evals and tests; and
- the implementation entry in `PROJECT_LOG.md`.

After implementation is genuinely proven, user-facing truth is exactly:

- an administrator can save a runtime issue through `/issue`, bounded text, or
  bounded voice;
- the bot stores the report;
- the active business action remains unchanged;
- the report does not prove the bug;
- the report does not authorize repair;
- the bot does not promise when or whether the problem will be fixed; and
- automatic maintenance and autorepair remain unavailable until separately
  implemented and activated.

All feature copy is Slovak.

Forbidden claims include:

- “The bug is confirmed” based only on intake;
- “The problem will be fixed” or a promised time/SLA;
- “Repair was authorized” from issue text;
- “Autorepair is active”;
- “The issue was deployed”;
- “The reported action was repeated”;
- “The workspace/build/state came from the user”;
- “The issue was stored” after a failed or rolled-back transaction.

## Canonical state and logs

- SQLite is the only canonical writable issue-state store. Stage 1 owns the
  intake record, `intake_status=new`, and deduplication. Later Stage 2 alone
  may add and own processing statuses, claim/lease state, maintenance runs,
  and results after separate architecture, implementation, and activation.
- `AUTOREPAIR_LOG.md` is not created or written in Stage 1. It belongs to later
  Stage 2 human-readable diagnosis/repair history and is explicitly excluded.
- `PROJECT_LOG.md` receives one normal implementation entry when Stage 1 is
  implemented and proven. It remains the project/production change history,
  not the canonical issue state.
- A Markdown write failure must never determine, restore, or alter issue state.

## Strict Stage 2 exclusion

> **Stage 2 is not optional implementation work in this handoff. Do not create
> placeholders, hooks, schemas, tables, statuses, interfaces, or services for
> it.**

`RUNTIME_ISSUE_INTAKE_V1` must not implement:

- issue decomposition into findings;
- diagnosis;
- classification;
- code autorepair;
- operational remediation;
- combined repair;
- contact registry refresh;
- accounting-document deletion or quarantine;
- atomic issue claim/lease;
- global maintenance claim/lease;
- maintenance run records;
- claimed manifest generation;
- bounded log evidence collection;
- diagnosis or repair result records;
- repair branches or commits;
- `AUTOREPAIR_LOG.md` writes;
- notification outbox;
- merge;
- deploy;
- rollback.

Do not add these as optional follow-up work inside the Stage 1 patch. Do not
create future-facing Stage 2 interfaces unless Stage 1 itself strictly needs
the interface and the approved Architecture Design Proof already includes it.
The only such approved optional boundary is bounded read-only issue
retrieval/export; it cannot mutate status or create a manifest.

## No-go constraints

The implementation agent must not:

- redesign the approved action, slots, routes, FSM, persistence, authorization,
  or Product Truth;
- create a phrase whitelist or local multilingual issue parser;
- add an issue confirmation, keyboard, callback, or FSM;
- use an LLM for title derivation;
- extract occurrence time;
- accept trusted context or permissions from report content;
- broaden admin or workspace authority;
- weaken unauthorized-before-STT behavior;
- modify existing business tables;
- add destructive migration behavior;
- use `SELECT *` or tuple-position row mapping in the new service;
- store raw secrets, FSM data, files, audio, logs, or private operational data;
- call Stage 1 complete from resolver/service tests alone;
- modify unrelated flows;
- merge, deploy, migrate production, or alter production state.

## Implementation output requirements

The future implementation agent must return:

- docs/contracts read;
- design verification status;
- files changed;
- design-to-code mapping and any nonsemantic variance;
- public routing and convergence summary;
- exact schema audit, proposed/implemented dedicated-table shape, migration
  classification, backup expectation, and rollback/removal plan;
- proof that existing business tables and rows remain unchanged;
- tests/evals run and exact results;
- tests/evals not run and why;
- Product Truth and InfoHelp status after the change;
- forbidden claims checked;
- Conversation Acceptance Proof path and verdict;
- known limitations and unresolved blockers;
- final git status; and
- explicit confirmation that Stage 2, deployment, and production were not
  changed.

Human review is required before merge, additive production migration,
deployment, or production activation.
