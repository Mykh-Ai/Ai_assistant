# Self-Learning Layer

## Purpose

This document defines the controlled self-learning layer for
OfficeFlow/FakturaBot.

Self-learning means the product can improve future recognition of confirmed
user language, aliases, topics, and request patterns. It does not mean the bot
can invent features, create new canonical actions, store raw transcripts as
knowledge, or bypass deterministic Python gates.

The product target is adaptive business assistance. The safety rule is that
learning happens only from confirmed, scoped, reviewable signals.

## Current Status

This document is a docs-first umbrella contract.

Current implemented/partial learning is narrower:

- invoice customer lookup aliases under the `invoice_customer` domain;
- invoice service lookup aliases under the `invoice_service` domain;
- both governed by `docs/Confirmed_Semantic_Alias_Learning_Contract.md`;
- both remain bounded by existing Python owner services and confirmation
  rules.

Broad self-learning for action aliases, InfoHelp topics, capability questions,
customization request patterns, document classification hints, and
account-specific workflow preferences is not implemented unless later code
proves otherwise.

## Normative Status

This is a mandatory-read contract for work touching:

- semantic aliases;
- action aliases;
- InfoHelp topic aliases;
- capability question phrasings;
- customization request patterns;
- document classification hints;
- contact/customer/service aliases;
- account-specific workflow preferences;
- any storage that improves future semantic resolution.

Companion docs:

- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`;
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`.

## Core Rule

The product may learn only after successful resolution or explicit user
confirmation.

Learning must never:

- create canonical actions;
- claim unsupported capabilities;
- bypass Product Truth;
- bypass action registries;
- bypass DecisionResolver confirmation rules;
- save destructive confirmations;
- store broad raw sensitive transcripts as reusable knowledge;
- cross tenant/workspace boundaries.

## What May Be Learned

Allowed learning candidates:

- action aliases for existing canonical actions;
- InfoHelp topic aliases;
- capability question phrasings;
- contact/customer aliases;
- service aliases;
- document classification hints;
- recurring customization request patterns;
- non-sensitive account/workflow preferences after explicit approval.

Every learned record must be scoped, typed, and linked to an existing owner or
registry entry.

## What Must Not Be Learned

Never learn:

- destructive confirmation phrases;
- final database deletion confirmation values;
- raw passwords, API keys, tokens, credentials, OAuth codes, or secrets;
- full invoice request transcripts as reusable aliases;
- full STT transcripts as reusable aliases;
- personal/private text not needed for the target mapping;
- new canonical action names outside the registry;
- Product Truth status from model guesses;
- unsupported features as if they were supported;
- cross-tenant patterns that expose one workspace to another.

## Learning Candidate Object

Minimum candidate shape:

```text
candidate_id
workspace_id / tenant_scope
user_id
domain
target_type
target_id
source_text_normalized
source_kind
intent
slots_policy
confirmation_source
confidence_source
status
created_at
updated_at
expires_at
review_required
```

Recommended additional fields:

```text
raw_text_ref_or_hash
redaction_policy
language
channel
resolver_owner
registry_ref
product_truth_ref
usage_count
last_used_at
last_reviewed_by
last_reviewed_at
rejection_reason
notes_for_admin
```

`source_text_normalized` must be the minimal useful phrase, not an entire raw
business message.

## Domains

Initial domain families:

- `invoice_customer`;
- `invoice_service`;
- `top_level_action`;
- `info_help_topic`;
- `capability_question`;
- `customization_pattern`;
- `document_classification`;
- `account_workflow_preference`.

Each domain requires:

- Python owner service;
- allowed target type;
- storage scope;
- lookup order;
- confirmation signal;
- forbidden side effects;
- tests.

## Intent And Slots Separation

Self-learning must separate intent from slots.

Correct:

```text
intent: ask_google_drive_storage
slot: storage_provider = google_drive
```

Incorrect:

```text
literal alias: "please store invoice 2026-001 for customer ABC to my drive"
```

Variable commands must be patterns, not literal aliases. A learned pattern may
help classify a question, but Python must still validate slots, Product Truth,
and side-effect gates.

## Confirmation Rules

Valid confirmation signals:

- explicit DecisionResolver confirmation;
- approval of a workflow preview where the resolved target is visibly shown;
- admin review approval for higher-risk learned patterns;
- successful repeated safe resolution where the product explicitly asks to
  remember the mapping.

Invalid confirmation signals:

- low-confidence fuzzy match alone;
- LLM confidence alone;
- STT transcript alone;
- user silence;
- cancelled flow;
- edited/rejected preview;
- destructive operation confirmation;
- unauthorized user message.

## Storage And Scope

Learning storage must be scoped by:

- tenant/workspace;
- user or supplier where applicable;
- domain;
- target type;
- target id;
- language/channel where useful.

Default safety expectations:

- cap aliases per target/domain;
- avoid duplicate aliases;
- support review and deletion;
- support expiry for stale or low-value patterns;
- do not store raw sensitive transcripts as reusable knowledge;
- do not allow learned records to cross access boundaries.

## Product Truth Boundary

Learned patterns may improve recognition. They must not change Product Truth.

Example:

- A user often asks "disk" when meaning "Google Drive".
- The system may learn that phrase as a capability-question alias.
- The answer must still come from Product Truth and remain
  `unsupported`/`requires_external_credentials` until runtime support exists.

## Registry Boundary

Learned action aliases may map only to existing canonical actions in
`docs/llm/Canonical_Action_Registry.md` and runtime `allowed_actions`.

Learned InfoHelp topic aliases may map only to known topics/capabilities.

Learning must never create:

- new top-level actions;
- new InfoHelp capabilities;
- new side-effect routes;
- new Product Truth statuses.

## LLM Role

The LLM may:

- propose a normalized candidate phrase;
- classify the candidate into a Python-provided domain list;
- select a target from Python-provided candidates;
- explain why a confirmation is being requested.

Python must:

- provide allowed domains/targets;
- validate target ownership;
- enforce confirmation;
- enforce caps and duplicate checks;
- write storage;
- use learned records only through owner services.

The LLM must not:

- save learned records;
- create targets;
- bypass scopes;
- learn from destructive confirmations;
- turn learned phrases into Product Truth.

## Relationship To Confirmed Semantic Alias Contract

`docs/Confirmed_Semantic_Alias_Learning_Contract.md` remains the detailed
runtime contract for confirmed invoice customer and invoice service aliases.

This document is broader. It defines how future domains must behave before
they can reuse the pattern.

If the two documents conflict for current invoice customer/service aliases, the
more specific confirmed alias contract governs that runtime domain.

## Domain Acceptance Criteria

A new self-learning domain is not complete until:

- domain and target type are documented;
- Python owner service is defined;
- storage scope is tenant/workspace safe;
- lookup order is documented;
- confirmation signal is documented;
- raw transcript storage is avoided or explicitly justified;
- caps/duplicate checks exist;
- review/expiry behavior is defined;
- tests prove no cross-tenant leakage;
- tests prove learned mappings cannot bypass Product Truth or canonical
  registries;
- product evals prove the learned mapping improves a real user journey without
  fake claims.

## Required Tests

For any new learning domain, add tests for:

- write only after valid confirmation;
- no write after cancel/edit/reject/unknown;
- no write for unauthorized user;
- no raw full transcript storage;
- per-tenant/workspace scoping;
- cap enforcement;
- duplicate prevention;
- lookup uses owner service;
- invalid target id is rejected;
- Product Truth is not changed by learned mapping;
- destructive confirmations are never learned.

## Product UX Evals

Required eval patterns:

- repeated capability phrasing maps to the right known topic;
- learned alias improves later resolution;
- unsupported feature remains unsupported after learning;
- active FSM behavior is not bypassed by learned top-level alias;
- user can correct or reject a learned mapping;
- stale/incorrect alias can expire or be reviewed.

## No-Go Rules

Do not:

- call current invoice alias learning broad self-learning;
- learn from model confidence alone;
- store full raw transcripts as reusable aliases;
- learn destructive confirmations;
- create canonical actions from learned phrases;
- let learned aliases override Product Truth;
- let learned patterns cross tenant/workspace boundaries;
- add a learning domain without owner service, tests, and review/expiry rules.
