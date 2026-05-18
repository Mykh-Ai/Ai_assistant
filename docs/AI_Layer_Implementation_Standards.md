# AI Layer Implementation Standards

## Purpose

This document defines how OfficeFlow/FakturaBot evaluates, designs, and accepts
AI-assisted product layers.

OfficeFlow/FakturaBot is not a command bot with static fallback text. It is an
AI-assisted business operating layer where Python owns truth, validation, and
side effects, while AI interprets, explains, drafts, or selects only inside
explicit bounds.

This document exists to prevent a recurring failure mode: implementing a
primitive fallback or repair patch and calling it a completed AI product layer.

## Normative Status

This is a mandatory-read contract for any task that touches:

- LLM/STT/LMM behavior;
- semantic routing;
- InfoHelp or support guidance;
- capability answers;
- customization requests;
- self-learning aliases or topic mappings;
- code-agent handoff;
- state-aware explanations;
- AI-facing user experience;
- product documentation that claims an AI capability.

If a change touches user-facing AI behavior, the agent must declare the maturity
level implemented by the change before calling the task complete.

## Architecture Boundary

The authority split is mandatory:

```text
Python orchestrates.
AI extracts, canonicalizes, explains, drafts, or selects inside bounds.
Python validates.
User confirms when required.
Python saves or executes.
```

AI must not:

- invent canonical actions;
- claim unsupported product capabilities;
- execute side effects;
- write directly to DB/storage;
- bypass access control;
- bypass the canonical action registry;
- bypass the DecisionResolver for confirmation-like decisions;
- convert an unknown request into a destructive or persistent action;
- use roadmap language as runtime truth.

## Product Truth Requirement

Any user-facing capability answer must be backed by Product Truth, not model
confidence.

The detailed Product Truth contract is `docs/Product_Truth_Layer.md`.

Until a runtime Product Truth registry exists, Product Truth must be derived
from current code, `PROJECT_LOG.md`, `docs/TZ_FakturaBot.md`, and focused
contract docs. If those sources do not prove support, the answer must be
`partial`, `planned`, `unsupported`, or `unknown`.

Product Truth status model:

Primary support statuses:

- `supported`: current runtime implements the capability end to end.
- `partial`: current runtime implements only a bounded subset.
- `planned`: documented direction exists, runtime support does not.
- `unsupported`: current product does not support this capability.
- `unknown`: truth cannot be established from current sources.

Flags/context:

- `dangerous`: capability is sensitive/destructive and needs stronger gates.
- `requires_setup`: supported only after user/workspace setup exists.
- `requires_admin`: requires admin approval or admin-side configuration.
- `requires_external_credentials`: requires third-party credentials or
  integration setup.

Flags/context are not primary support statuses. Python must derive final
response behavior from the primary status, flags/context, account state,
active FSM/routing state, and safety policy.

The LLM may phrase the answer or classify user input into Python-provided
capability/topic/triage options, but it cannot be the source of the status,
flags, account context, or final response mode.

## Unknown / Discovery / Triage Requirement

Product Truth `unknown` is not enough by itself for the 2026-2030 OfficeFlow
front door. If user input does not map to a known Product Truth
`capability_id`, the system must not behave like a registry search engine or
a command-menu bot.

When authorization, active state, and routing allow discovery, Python should
run a separate Unknown / Discovery / Triage layer. Its allowed classes are:

```text
known_product_capability
new_business_feature_request
customization_request_candidate
admin_review_candidate
out_of_domain
spam_or_abuse
smalltalk
unclear_needs_clarification
possible_product_truth_candidate
unknown
```

This layer is classification only. It may not execute actions, change Product
Truth, create capability IDs, mark anything as supported, save customization
requests, send admin notifications, write DB/storage, or bypass FSM/state/auth
gates.

The correct runtime order for top-level natural language is:

1. authorization gate;
2. active FSM state wins;
3. clear direct executable action resolver;
4. known Product Truth capability/topic resolver;
5. Unknown / Discovery / Triage resolver;
6. Python-controlled outcome.

Python-controlled outcomes include known Product Truth answer rendering,
clarification, bounded out-of-domain refusal, safe spam/noise handling,
smalltalk redirect, and a confirmation-gated future request/admin-review flow
when implemented.

## Maturity Model

Every AI-layer change must state the highest level it actually implements.

### Level 0: Placeholder / Fallback

Behavior:

- returns "I do not understand", `/menu`, or generic fallback text;
- has no product-truth lookup;
- has no semantic domain understanding;
- captures no actionable business request.

Complete only as:

- a temporary guardrail;
- an explicitly documented placeholder;
- a failure mode that does not claim product intelligence.

Incomplete if called:

- InfoHelp complete;
- semantic support;
- business assistant behavior;
- Product Truth behavior.

### Level 1: Static Guidance

Behavior:

- gives deterministic help text;
- improves recovery copy;
- points to existing commands or actions;
- may reduce user confusion in a known failure path.

Complete only when:

- the limitation is documented as Level 1;
- user-facing copy does not claim unsupported capabilities;
- no hidden side effects occur.

Incomplete if:

- arbitrary capability questions still fall back to a menu;
- planned/unsupported/custom requests are not classified;
- no Product Truth source is consulted.

Project examples:

- top-level `info_help` fallback guidance from Session 075 is Level 1 only;
- FSM recovery hints are useful Level 1/state-copy repair, not a 2030 AI layer;
- `/start` and `/menu` clarity is UX navigation, not intelligence by itself.

### Level 2: Capability-Aware Q&A

Behavior:

- understands arbitrary capability/how-to/support questions;
- classifies them against Product Truth;
- answers `supported`, `partial`, `planned`, `unsupported`, or `unknown`;
- explains current limits in business language;
- proposes a safe next step.
- sends non-matching inputs through safe Unknown / Discovery / Triage instead
  of treating `unknown capability_id` as one generic fallback.

Complete only when:

- a controlled Product Truth source exists;
- capability aliases/topic mappings are bounded by registry entries;
- unsupported/planned features are not phrased as available;
- active FSM state is respected;
- access control is enforced before AI calls;
- UX evals cover real capability questions.

Incomplete if:

- the response is only a static FAQ;
- the model freely invents capability facts;
- the bot answers `/menu` to real business questions;
- no regression/eval suite proves honesty.
- unknown plausible business needs, out-of-domain questions, spam/noise,
  smalltalk, and unclear inputs are not separated safely.

### Level 3: Customization Request Creation

Behavior:

- detects unsupported, partial, account-specific, or custom business needs;
- drafts a structured request;
- asks the user for confirmation;
- saves a pending request only after confirmation.

Detailed request behavior is governed by
`docs/Customization_Request_Layer.md`.

Complete only when the request object includes:

- `request_id`;
- `user_id` / `workspace_id`;
- `original_user_text` or a policy-approved redacted reference;
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

Incomplete if:

- the bot promises implementation immediately;
- requests are stored without confirmation;
- sensitive text is stored without policy;
- there is no admin/developer review path.

### Level 4: Controlled Self-Learning

Behavior:

- stores confirmed aliases, topic mappings, or patterns;
- keeps them scoped, bounded, reviewable, and expirable;
- separates intent from slots;
- never bypasses canonical registries.

Detailed learning behavior is governed by `docs/Self_Learning_Layer.md`.

Complete only when:

- learning happens after successful resolution or explicit confirmation;
- destructive confirmations are never learned;
- tenant/workspace/user scoping is correct;
- raw sensitive transcripts are not reused as knowledge;
- review/expiry limits exist where practical.

Learning candidates:

- action aliases;
- InfoHelp topic aliases;
- capability question phrasings;
- contact/customer aliases;
- service aliases;
- document classification hints;
- recurring customization patterns.

Incomplete if:

- the system learns unconfirmed guesses;
- variable commands are stored as literal aliases;
- cross-tenant patterns leak;
- learned aliases can create new canonical actions.

### Level 5: Code-Agent Handoff

Behavior:

- converts a confirmed request into a bounded implementation task;
- includes the docs, files, contracts, tests, evals, and no-go constraints a
  code agent must follow;
- requires human approval before merge/deploy.

Detailed handoff behavior is governed by
`docs/Code_Agent_Handoff_Contract.md`.

Complete only when task packages include:

- product need and current Product Truth primary status plus flags/context;
- required docs/contracts to read;
- likely files/modules;
- implementation scope;
- acceptance criteria;
- unit/integration tests;
- UX/product evals;
- migration/rollback notes if relevant;
- PDF/layout criteria if relevant;
- explicit no-go constraints;
- approval gate.

Incomplete if:

- the handoff is a vague prompt;
- it omits safety contracts;
- it allows code changes without review;
- it treats AI output as deployment approval.

### Level 6: Evaluated Autonomous Implementation Proposal

Behavior:

- prepares a concrete patch/module proposal;
- runs deterministic tests where possible;
- reports product eval results;
- includes rollback and risk notes;
- still requires human approval.

Complete only when:

- tests and evals match the acceptance criteria;
- side effects are gated;
- migration-sensitive changes have a dry-run and rollback plan;
- a human can review the proposed change before merge/deploy.

Incomplete if:

- the model edits production behavior without approval;
- evals are replaced by confidence claims;
- dangerous actions are proposed without deterministic gates.

### Level 7: Account-Specific Adaptive Workflow Layer

Behavior:

- adapts workflows per workspace/account based on confirmed preferences,
  setup state, and approved patterns;
- uses Product Truth plus account setup state;
- remains bounded by Python validation and deterministic gates.

Complete only when:

- tenant/workspace boundaries are proven;
- account-specific preferences are reviewable;
- unsupported integrations are not implied by preference alone;
- behavior is evaluated across multiple realistic account states.

Incomplete if:

- global behavior changes based on one user's data;
- account preferences bypass Product Truth;
- adaptive behavior cannot be inspected or reverted.

## Current Project Classification

These classifications must be used unless later code/docs prove a higher
level:

- Top-level `info_help` fallback guidance from Session 075 / commit
  `d8ddbec` class behavior: Level 1 only.
- FSM recovery patches: useful repair work and state-copy quality, not the
  2030 product layer by themselves.
- `/start` / `/menu` split: UX improvement, not an intelligence layer by
  itself.
- Exact cancel bypassing LLM: correct architecture hygiene and safety, not an
  AI product leap.
- Current bounded semantic action resolver: bounded action interpretation, not
  broad Product Truth or customization support by itself.
- Current bounded InfoHelp / Unknown / Discovery / Triage v1: safe
  non-persistent classification foundation only, not complete Level 2 and not
  customization request creation.
- Current confirmed invoice/contact/service alias learning: partial
  controlled learning in specific flows, not broad self-learning across
  actions, topics, capability questions, or customization patterns.

## Required Implementation Declaration

For every AI-layer task, record this before implementation or in the project
log:

```text
AI layer:
Declared maturity level:
Current lower-level behavior being replaced:
Product Truth source:
User journey being improved:
Out of scope:
Self-learning hooks considered:
Side effects:
Confirmation gates:
Evaluation plan:
```

If the declared level is Level 2 or higher, a static fallback is not sufficient
acceptance.

## Acceptance Rules

A user-facing AI layer is not complete until all applicable items are true:

- runtime behavior matches the declared maturity level;
- documentation states the same level honestly;
- no user-facing copy claims unsupported capabilities;
- Product Truth backs capability statements;
- active FSM state is respected;
- access control happens before AI/STT/LMM calls;
- deterministic gates own side effects;
- tests cover behavior and safety;
- product UX evals cover realistic user journeys;
- `PROJECT_LOG.md` records the decision and actual level.

## Evaluation Requirement

Unit tests are required but not sufficient for AI product layers.

The detailed evaluation contract is
`docs/Evaluation_and_Smoke_Test_Standards.md`.

Each Level 2+ layer needs product evals or smoke tests covering realistic
journeys, such as:

- arbitrary capability question;
- unsupported feature honesty;
- planned feature honesty;
- unknown plausible business request;
- active FSM confusion;
- request creation confirmation;
- no hidden side effects;
- no fake support claims;
- voice/text parity where promised;
- access isolation where data or AI calls are involved.
- unknown business feature request triage;
- out-of-domain rejection without request creation;
- spam/noise without admin/customization side effects;
- smalltalk without business action execution;
- multilingual and noisy-STT triage examples.

## No-Go Patterns

Do not:

- rename fallback copy as AI support;
- claim a phase complete when only Level 0/1 behavior exists;
- use LLM output as Product Truth;
- answer real business questions only with `/menu`;
- store broad raw transcripts as "learning";
- learn destructive confirmations;
- create custom requests without user confirmation;
- send a code-agent task without docs/contracts/tests/no-go constraints;
- deploy or merge AI-proposed changes without deterministic tests and human
  approval.
