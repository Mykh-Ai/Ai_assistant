# Product Doctrine 2030

## Purpose

OfficeFlow/FakturaBot is an AI-assisted business operating layer for
craftspeople, živnostníci, small s.r.o. companies, accountants, and people who
run business from conversations, documents, invoices, receipts, and recurring
workflows.

The product must stay useful in 2026 and still make sense in 2027+. It must not
be designed as a 2023 command bot with a menu and a collection of static
fallbacks.

Telegram is the current primary interface. The product identity is larger than
Telegram: OfficeFlow/FakturaBot is the layer that understands business intent,
checks product truth, guides workflows, drafts safe changes, and keeps final
execution under deterministic gates.

## Product Identity

OfficeFlow/FakturaBot is:

- a natural-language business front door;
- a guided workflow assistant;
- a bounded AI interpreter over Python-owned business logic;
- a product-truth aware support concierge;
- a safe document/invoice/accounting intake layer;
- a future customization request and code-agent handoff system;
- a controlled self-learning system for confirmed aliases and patterns.

OfficeFlow/FakturaBot is not:

- a command-only Telegram menu bot;
- free-form autonomous AI;
- a model that executes side effects;
- a static FAQ pasted onto runtime fallback;
- a fake SaaS claim;
- a product that says "supported" because an idea exists in a roadmap.

## Current Reality

Current implemented and partial runtime includes:

- Telegram interface built with Python and aiogram;
- SQLite persistence;
- supplier profiles and onboarding;
- controlled user access and admin approval;
- contacts/customer management;
- invoice drafting from text/voice with OpenAI STT/LLM boundaries;
- bounded semantic action resolver;
- canonical DecisionResolver for confirmation-like replies;
- invoice PDF generation with Pay by Square support and layout regression tests;
- invoice create/edit/delete/read flows with deterministic gates;
- service aliases and confirmed semantic alias learning for selected invoice
  paths;
- OfficeFlow accounting document intake for receipts and incoming invoices;
- idle attachment router with confirmation before side effects;
- recent accounting document view;
- tenant/workspace scoped storage in the controlled rollout model.

Current gaps and partial foundations that must not be overstated:

- Product Truth MVP registry foundation exists, but Product Truth is not yet a
  complete runtime Product Truth layer;
- InfoHelp has Level 1 unknown-input guidance plus partial Product
  Truth-backed fast-paths for selected conservative capability/safety topics;
- Unknown / Discovery / Triage is documented design only unless later code
  proves otherwise;
- bounded InfoHelp resolver is not complete;
- Customization Request Layer has a partial Level 3 MVP slice for
  confirmation-gated request capture plus admin read/status review, but it is
  not complete;
- Code-Agent Handoff Layer is not yet implemented;
- broad self-learning for topics/capabilities/customization patterns is not yet
  implemented;
- Google Drive sync is not runtime-supported;
- SMS sending is not runtime-supported;
- real outbound email sending is not runtime-supported unless later docs/code
  prove otherwise;
- full commercial SaaS, billing, public signup, per-client bot-token/runtime
  provisioning, and complex role/workspace admin are not implemented.

## Core Doctrine

### 1. Natural Language Business Front Door

Users should be able to ask normal business questions:

- "môžete posielať faktúry emailom?"
- "viete posielať SMS?"
- "viete ukladať faktúry na Google Disk?"
- "chcem evidovať odpracované hodiny"
- "chcem mesačný výkaz"
- "chcem starý formát faktúry"
- "chcem pridať DPH riadok"
- "viete kategorizovať bločky?"
- "viete exportovať do účtovného softvéru?"
- "chcem aby sa faktúry posielali účtovníčke"
- "môžete mi pripomenúť neuhradené faktúry?"

The correct product direction is to answer the business question honestly and
offer the next safe step. The wrong direction is to reply only with `/menu` or
generic "I do not understand".

### 2. Product Truth Before Product Claims

The bot must not claim a feature exists because an LLM can phrase it.

Every capability answer must be grounded in Product Truth:

- `supported`;
- `partial`;
- `planned`;
- `unsupported`;
- `unknown`;
- `dangerous`;
- `requires_setup`;
- `requires_admin`;
- `requires_external_credentials`.

The LLM may explain Product Truth, but Python or structured registries must
provide it.

Detailed Product Truth rules are governed by
`docs/Product_Truth_Layer.md`.

### 3. Bounded AI, Deterministic Execution

The architecture stays:

- Python orchestrates.
- AI extracts, canonicalizes, explains, or drafts.
- Python validates.
- User confirms where needed.
- Python saves or executes.

No AI layer may invent canonical actions, write storage, bypass registries, or
execute side effects.

### 4. Capability-Aware InfoHelp

InfoHelp is not complete when it only emits static fallback guidance.

The target InfoHelp layer must:

- understand capability/how-to/support questions;
- check Product Truth;
- say whether the capability is supported, partial, planned, unsupported, or
  unknown;
- explain current limitations in plain business language;
- offer a safe next step;
- offer customization request creation when useful;
- stay state-aware when the user is inside an active FSM flow.

Example target answer:

User:

> Vie bot ukladať faktúry na Google Disk?

Expected:

> Momentálne nie. Faktúry sa teraz ukladajú v systéme bota a môžete si ich
> zobraziť alebo stiahnuť cez Telegram.
>
> Ak potrebujete Google Disk alebo iné vlastné ukladanie faktúr, môžem z toho
> pripraviť požiadavku na úpravu účtu. Správca potom skontroluje, čo presne
> treba nastaviť.

### 4.1 Unknown / Discovery / Triage

Product Truth is necessary but not sufficient as the whole conversational
front door. When a user asks for something that does not map to a known
Product Truth capability, the bot must not behave like a simple registry
search engine or generic menu fallback.

Unknown input must be triaged safely as one of:

- known product capability;
- new business feature request;
- customization request candidate;
- admin/developer review candidate;
- out-of-domain question;
- spam/abuse/noise;
- smalltalk;
- unclear input that needs clarification;
- possible future Product Truth candidate;
- unknown.

Triage is not support. It must not mark a feature as available, promise
implementation, create requests, notify admins, or write DB/storage without a
later implemented and confirmed flow. Its job is to keep unknown business
needs visible while keeping every side effect behind Python-owned gates.

### 5. Customization Request Layer

When a user asks for a non-standard feature, the product should not fake
support and should not stop at "nerozumiem".

The target behavior:

1. detect the business need;
2. classify current capability status;
3. draft a customization request;
4. ask confirmation;
5. save a pending request after confirmation;
6. route it to admin/developer/code-agent workflow when approved.

The bot must not promise implementation or deployment without approval.

Detailed customization request rules are governed by
`docs/Customization_Request_Layer.md`.

### 6. Code-Agent Handoff

A future confirmed customization request may be converted into a code-agent
task only when the request is clear enough and safe enough.

A handoff task must include:

- source docs/contracts to read;
- files/modules likely touched;
- implementation scope;
- acceptance criteria;
- tests and product UX evals;
- visual/PDF/layout criteria where relevant;
- migration and rollback notes;
- no-go constraints;
- human approval gate before merge/deploy.

PDF/layout work must include real layout criteria such as wrapping, row width,
QR placement, footer spacing, and regression/manual review expectations.

Detailed handoff rules are governed by
`docs/Code_Agent_Handoff_Contract.md`.

### 7. Controlled Self-Learning

Self-learning is part of the product direction, but it must remain controlled.

The product may learn:

- action aliases;
- topic aliases;
- capability question phrasings;
- contact/customer aliases;
- service aliases;
- document classification hints;
- recurring customization patterns.

The product must not learn:

- destructive confirmations;
- raw sensitive transcripts as reusable knowledge;
- new canonical actions outside registry control;
- cross-tenant data;
- unconfirmed guesses.

Learning must be scoped, reviewable, bounded, and expire/clean up where
practical.

Detailed self-learning rules are governed by `docs/Self_Learning_Layer.md`.

### 8. State-Aware Explanation

When the user is in a workflow, the bot must explain the current state.

Weak response:

> Ak nechcete pokračovať, napíšte zrušiť.

Better response:

> Teraz upravujete dátum faktúry. Dátum sa nepodarilo rozpoznať. Zadajte dátum
> vo formáte DD.MM.RRRR, napríklad 16.05.2026. Ak nechcete pokračovať, napíšte
> zrušiť.

The target product tells the user what is happening, what it needs, why the
input failed, and how to recover.

### 9. Evaluation Beyond Unit Tests

AI layers must be evaluated as user experience, not only as unit branches.

Required product eval areas:

- first `/start` journey;
- `/menu` clarity;
- arbitrary capability questions;
- unsupported feature honesty;
- unknown plausible business request;
- active FSM confusion;
- destructive action safety;
- request creation confirmation;
- voice/text parity;
- no hidden side effects;
- no fake product claims.
- unknown/discovery triage for plausible business requests;
- out-of-domain, spam/noise, smalltalk, and unclear input handling;
- multilingual and noisy-STT paths through the same state-aware routing.

Detailed evaluation rules are governed by
`docs/Evaluation_and_Smoke_Test_Standards.md`.

## Maturity Language

Agents must use maturity labels honestly:

- Level 0: placeholder/fallback;
- Level 1: static guidance;
- Level 2: capability-aware Q&A;
- Level 3: customization request creation;
- Level 4: controlled self-learning;
- Level 5: code-agent handoff;
- Level 6: evaluated autonomous implementation proposal with human approval;
- Level 7: account-specific adaptive workflow layer.

Detailed acceptance rules for these levels are governed by
`docs/AI_Layer_Implementation_Standards.md`.

`d8ddbec Implement top-level info_help fallback guidance`, or equivalent
runtime behavior, is Level 1 only unless later code implements capability-aware
Product Truth behavior.

FSM recovery patches are useful repair work. They are not the 2030 product
layer by themselves.

`/start` and `/menu` improvements are UX improvements. They are not an
intelligence layer by themselves.

Exact cancel bypassing LLM is correct architecture hygiene. It is not an AI
product leap by itself.

## Roadmap Direction

The documentation and architecture should move in this order:

1. Documentation reset: AGENTS and Product Doctrine.
2. AI Layer Implementation Standards.
3. Product Truth Registry.
4. Capability-aware InfoHelp.
5. Customization Request MVP.
6. Self-learning topic/action/capability aliases.
7. Code-agent task handoff.
8. UX evaluation suite.
9. Account-specific adaptive workflows.

Runtime implementation should follow these documents, not replace them with
static fallbacks.

Unknown / Discovery / Triage must be designed before broad bounded InfoHelp
resolver work. Otherwise Product Truth risks becoming only a search index over
known capability IDs instead of a safe business-discovery layer.

## Product Standard

Every user-facing AI feature must answer this question:

Does this help a real business user complete or understand a business workflow
more safely, honestly, and efficiently than a command menu?

If the answer is no, the feature is not yet product-grade.
