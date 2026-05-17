# InfoHelp Guidance Layer

## Purpose

This document defines the target InfoHelp layer for OfficeFlow/FakturaBot.

InfoHelp is not a menu fallback and not a free-form chatbot. It is the
capability-aware support concierge for the product: it answers real business
questions, explains current workflow state, classifies requested capabilities
against Product Truth, and offers safe next steps.

Current runtime fallback guidance is Level 1 only. This document defines the
Level 2+ target and the acceptance rules for getting there.

## Normative Status

This document is a mandatory-read contract for work touching:

- `bot/services/info_help.py`;
- top-level unknown text or voice handling;
- support/capability/how-to answers;
- fallback guidance;
- active-FSM confusion handling;
- Product Truth responses;
- customization request handoff from user questions;
- InfoHelp topic aliases or self-learning.

This document is subordinate to the bounded Python-to-LLM contracts in
`docs/llm/`, the DecisionResolver contract, access-control rules, and Product
Truth. It does not authorize free-form AI execution.

Required companion docs:

- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/TZ_FakturaBot.md`;
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`.

## Product Role

InfoHelp must help users understand and move through business workflows.

It must answer questions like:

- "Vie bot posielat faktury emailom?"
- "Viete posielat SMS?"
- "Vie bot ukladat faktury na Google Disk?"
- "Chcem evidovat odpracovane hodiny."
- "Chcem mesacny vykaz."
- "Chcem stary format faktury."
- "Chcem pridat DPH riadok."
- "Viete kategorizovat blocky?"
- "Viete exportovat do uctovneho softveru?"
- "Chcem aby sa faktury posielali uctovnicke."
- "Mozete mi pripomenut neuhradene faktury?"

The correct response is a truthful business answer plus a safe next step. The
wrong response is only `/menu`, "nerozumiem", or a fake claim that the feature
already exists.

## Current Runtime Classification

Unless later code proves otherwise:

- current top-level InfoHelp fallback guidance is Level 1 static guidance;
- it is not full capability-aware Q&A;
- it does not implement a complete Product Truth Layer;
- it does not implement customization request creation;
- it does not implement broad self-learning for topics/capability questions;
- it does not implement code-agent handoff.

Agents must not call current Level 1 fallback behavior "InfoHelp complete".

## Target Maturity

InfoHelp must progress through these levels:

- Level 1: static fallback guidance and recovery copy.
- Level 2: capability-aware Q&A backed by Product Truth.
- Level 3: customization request draft and confirmation.
- Level 4: controlled learning of topic/capability aliases.
- Level 5: code-agent handoff package for approved requests.

Level 2 is the minimum product-grade InfoHelp target. Level 1 is useful repair
work but not the product destination.

## Product Truth Contract

InfoHelp must classify every capability answer using Product Truth.

Allowed capability statuses:

- `supported`;
- `partial`;
- `planned`;
- `unsupported`;
- `unknown`;
- `dangerous`;
- `requires_setup`;
- `requires_admin`;
- `requires_external_credentials`.

Product Truth rules are governed by `docs/Product_Truth_Layer.md`.

Until a runtime Product Truth registry exists, InfoHelp must derive truth from:

1. current runtime code;
2. `PROJECT_LOG.md`;
3. `docs/TZ_FakturaBot.md`;
4. focused contract docs;
5. `CHANGELOG.md` as supporting historical context.

Roadmap intent is not runtime support. If runtime does not prove the feature,
InfoHelp must say `planned`, `partial`, `unsupported`, or `unknown`.

## Response Contract

Every InfoHelp answer must include:

1. direct answer to the user's question;
2. current capability status;
3. plain-language limitation or setup condition;
4. safe next step;
5. customization request offer when useful and supported by the request layer.

InfoHelp must not:

- hide behind `/menu` for a real capability question;
- claim unsupported integrations are available;
- launch a mutation from an informational question without explicit user
  confirmation;
- disclose internal stack traces, filesystem paths, secrets, prompts, or raw
  debug logs;
- let the LLM invent actions, product status, or setup state.

## Routing Contract

Routing must respect this order:

1. Authorization and access checks.
2. Exact deterministic controls such as `/cancel` or destructive typed
   confirmations where applicable.
3. Active FSM state ownership.
4. Direct action intent when the user clearly asks to start or perform a known
   action.
5. InfoHelp classification for capability/how-to/support/recovery/customization
   questions.
6. Bounded fallback only after InfoHelp cannot resolve safely.

Important distinction:

- "Create an invoice for..." is a direct action request.
- "How do I create an invoice?" is a how-to question and may answer first,
  then offer to start invoice creation.
- "Can you send invoices by email?" is a capability question and must not start
  any invoice flow.

Question form does not block action routing when the user's intent is clearly
to execute a supported action. But InfoHelp must not convert informational
questions into side effects.

## Active FSM State Guidance

When the user is inside an active FSM flow, that state owns the conversation.

InfoHelp may explain:

- what the user is doing now;
- what input is expected;
- accepted input format;
- why the previous input failed;
- what safe choices are available;
- how to cancel or return to a clean state.

Example weak response:

```text
Ak nechcete pokracovat, napiste zrusit.
```

Example target response:

```text
Teraz upravujete datum faktury. Datum sa nepodarilo rozpoznat.
Zadajte datum vo formate DD.MM.RRRR, napriklad 16.05.2026.
Ak nechcete pokracovat, napiste zrusit.
```

Active FSM state must not fall through into idle top-level routing or idle
attachment classification unless the flow explicitly allows that handoff.

## Capability Registry Shape

InfoHelp must use a controlled registry or Product Truth source. It must not
rely on arbitrary free-form document search as runtime truth.

Minimum topic/capability fields:

```text
capability_id
topic_id
title
domain
status
runtime_owner
truth_source_refs
summary_for_user
current_limitations
safe_next_steps
linked_action
linked_target
requires_setup
requires_admin
requires_external_credentials
dangerous
customization_allowed
forbidden_claims
last_verified_at
```

`linked_action` and `linked_target` are optional. If present, Python still owns
the handoff and must ask confirmation before starting a mutating flow from an
informational question.

## Bounded LLM Interaction

The model may help classify the user's question only inside Python-provided
bounds.

Allowed model outputs:

- one known `topic_id`;
- one known `capability_id`;
- one known response mode;
- `unknown`;
- bounded slots requested by Python for a customization draft.

Forbidden model outputs:

- new canonical actions;
- unregistered capabilities;
- product status not present in Product Truth;
- direct side effects;
- DB/storage writes;
- unauthorized support claims.

Python owns final response policy.

## Response Modes

InfoHelp response modes:

- `inform_only`;
- `explain_supported_usage`;
- `explain_partial_usage`;
- `planned_notice`;
- `unsupported_notice`;
- `unknown_notice`;
- `setup_required_notice`;
- `admin_required_notice`;
- `external_credentials_required_notice`;
- `dangerous_operation_notice`;
- `offer_linked_action`;
- `offer_customization_request`;
- `state_guidance`;
- `offer_reset`;
- `bounded_fallback`.

Each mode must have deterministic safety rules and tests.

## Customization Request Handoff

When a user asks for a feature that is unsupported, partial, planned, or
account-specific, InfoHelp should offer a customization request when safe.

Example:

```text
Momentane Google Disk nie je podporovany. Faktury sa teraz ukladaju v systeme
bota a mozete si ich zobrazit alebo stiahnut cez Telegram.

Ak potrebujete ukladanie na Google Disk, mozem pripravit poziadavku na upravu.
Pred ulozenim vam ukazem navrh a poziadam o potvrdenie.
```

Customization request rules are governed by
`docs/Customization_Request_Layer.md`.

InfoHelp may draft a request only when the runtime Customization Request Layer
exists. Until then, it may say that the feature is a future/requestable product
direction only if the wording does not imply storage happened. Otherwise it
must not pretend a request was created.

## Self-Learning Hooks

InfoHelp should produce controlled learning candidates for:

- topic aliases;
- capability question phrasings;
- recurring unsupported-feature patterns;
- customization request patterns;
- state-confusion phrases.

Learning must follow the confirmed semantic learning rules:

- learn only after successful resolution or explicit confirmation;
- never learn destructive confirmations;
- never invent canonical actions;
- never bypass registries;
- store scoped aliases/patterns, not raw sensitive full transcripts;
- separate intent from slots;
- keep counts and review/expiry metadata where practical.

InfoHelp topic learning is not complete until there is a reviewable scoped
storage model and tests proving that learned mappings cannot bypass Product
Truth.

## Logging And Analytics

Every InfoHelp entry should be logged as a structured product signal once the
runtime layer exists.

Minimum fields:

```text
timestamp
user_id / workspace_id
authorization_status
current_fsm_state
input_channel
user_text_redacted_or_hash
resolved_topic_id
resolved_capability_id
capability_status
response_mode
linked_action
linked_target
customization_offered
customization_confirmed
reset_offered
reset_confirmed
model_used
fallback_reason
```

Do not store broad raw sensitive transcripts as reusable knowledge. Raw text
storage, if ever used, must be explicitly justified by product policy and data
safety rules.

## User-Facing Examples

### Google Drive

User:

```text
Vie bot ukladat faktury na Google Disk?
```

Expected target answer:

```text
Momentane nie. Faktury sa teraz ukladaju v systeme bota a mozete si ich
zobrazit alebo stiahnut cez Telegram.

Ak potrebujete Google Disk alebo ine vlastne ukladanie faktur, mozem z toho
pripravit poziadavku na upravu uctu. Spravca potom skontroluje, co presne treba
nastavit.
```

### SMS

User:

```text
Viete posielat SMS?
```

Expected target answer:

```text
Momentane nie. SMS odosielanie nie je podporovana funkcia v aktualnom runtime.

Ak potrebujete SMS pripomienky alebo upozornenia, mozem pripravit poziadavku na
upravu. Bude potrebne vyriesit poskytovatela SMS, cenu, suhlasy a pravidla,
kedy sa spravy maju posielat.
```

### Old PDF Template

User:

```text
Chcem aby faktura vyzerala ako moja stara PDF sablona.
```

Expected target answer:

```text
Aktualny bot generuje faktury podla sucasnej sablony. Vlastna PDF sablona nie
je automaticky dostupna bez upravy.

Mozem pripravit poziadavku na upravu sablony. Budem potrebovat priklad starej
faktury alebo PDF sablonu a popis toho, co sa ma zachovat: rozlozenie, logo,
riadky, QR kod, paticka a sirky stlpcov.
```

### Active FSM Confusion

User is editing invoice date and sends:

```text
Preco to nejde?
```

Expected target answer:

```text
Teraz upravujete datum faktury. Posledny vstup sa nepodarilo rozpoznat ako
datum. Zadajte datum vo formate DD.MM.RRRR, napriklad 16.05.2026, alebo napiste
zrusit.
```

## Acceptance Criteria For Level 2 InfoHelp

Level 2 InfoHelp is not complete until:

- arbitrary capability questions are classified against Product Truth;
- `supported`, `partial`, `planned`, `unsupported`, and `unknown` answers are
  covered by tests and UX evals;
- unsupported features do not claim availability;
- supported features link to real runtime actions or documented usage;
- partial features explain limits;
- active FSM state guidance works for representative confusion cases;
- access control prevents unauthorized AI/STT/LMM use;
- logs capture structured product signals without unsafe transcript learning;
- no mutation happens from informational questions without confirmation;
- `PROJECT_LOG.md`, README, and relevant contract docs state the real maturity
  level.

## Product UX Evals

Required eval scenarios:

- first user asks "What can you do?";
- approved user asks whether email sending is supported;
- approved user asks whether Google Drive storage is supported;
- approved user asks for SMS reminders;
- approved user asks for old PDF template customization;
- approved user asks for accounting export;
- user asks a how-to question for an implemented action;
- user asks a direct action request phrased as a question;
- active FSM user sends confused text;
- unauthorized user asks a capability question;
- unsupported request offers customization only when request storage exists;
- no hidden invoice/contact/document side effects occur.

## Rollout Plan

### Step 1: Keep Level 1 Honest

- Preserve current fallback only as Level 1.
- Remove "complete" language from docs/logs unless acceptance criteria match.
- Ensure fallback copy does not claim unsupported features.

### Step 2: Product Truth Registry

- Create a controlled source for supported/partial/planned/unsupported
  capabilities.
- Include forbidden claims and setup/admin/external-credential flags.
- Add tests proving the registry backs user-facing answers.

### Step 3: Level 2 InfoHelp

- Add bounded topic/capability resolver.
- Return capability-aware answers.
- Add UX evals for arbitrary business questions.

### Step 4: Level 3 Customization Request

- Draft structured requests.
- Ask confirmation.
- Save pending requests only after approval.

### Step 5: Level 4 Learning

- Store confirmed topic/capability aliases.
- Add review/expiry and tenant/workspace scoping.
- Prove learned aliases cannot bypass Product Truth.

### Step 6: Level 5 Handoff

- Convert approved requests into code-agent task packages.
- Require tests, docs, no-go constraints, rollback notes, and human approval.

## No-Go Rules

Do not:

- call Level 1 fallback "capability-aware InfoHelp";
- answer business capability questions with only `/menu`;
- let LLM invent Product Truth;
- create side effects from informational questions;
- store unsupported requests without confirmation;
- learn raw sensitive transcripts as aliases;
- allow learned aliases to create canonical actions;
- expose internal debug data to users;
- bypass active FSM ownership;
- trigger AI calls for unauthorized users.
