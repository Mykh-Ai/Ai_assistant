# InfoHelp Guidance Layer

## Purpose

This document defines the target InfoHelp layer for OfficeFlow/FakturaBot.

InfoHelp is not a menu fallback and not a free-form chatbot. It is the
capability-aware support concierge for the product: it answers real business
questions, explains current workflow state, classifies requested capabilities
against Product Truth, and offers safe next steps.

Current runtime has Level 1 unknown-input guidance plus partial Product
Truth-backed fast-paths for selected conservative capability/safety topics.
This document defines the Level 2+ target and the acceptance rules for getting
there.

## Normative Status

This document is a mandatory-read contract for work touching:

- `bot/services/info_help.py`;
- top-level unknown text or voice handling;
- support/capability/how-to answers;
- fallback guidance;
- active-FSM confusion handling;
- Product Truth responses;
- customization request / human-review handoff from user questions;
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
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
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

- current top-level unknown-input guidance is Level 1 static guidance;
- current Product Truth-backed InfoHelp is partial and limited to selected
  conservative topics plus bounded Unknown / Discovery / Triage v1
  classification;
- it is not full capability-aware Q&A;
- eligible idle InfoHelp/Triage customization candidates can enter a
  confirmation-gated preview/save flow backed by
  `CustomizationRequestService`;
- this preview/save path is a partial Level 3 MVP slice only;
- admin-only list/detail and status-only accept/reject review commands exist,
  but they do not notify users/admins, mutate Product Truth, convert to
  backlog, or create code-agent handoff;
- answer-only admin response-to-user exists through a separate
  confirmation-gated admin flow with latest response metadata and admin-facing
  delivery observability;
- clarification delivery, response kind selection beyond `answer`, retry,
  recovery commands, and threaded conversation history are not implemented;
- it does not implement broad self-learning for topics/capability questions;

Agents must not call current fallback or partial fast-path behavior "InfoHelp
complete" or "complete Level 2".

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

Product Truth separates primary support status from safety/account context.
Allowed primary statuses:

- `supported`;
- `partial`;
- `planned`;
- `unsupported`;
- `unknown`.

Allowed flags/context:

- `dangerous`;
- `requires_setup`;
- `requires_admin`;
- `requires_external_credentials`.

Flags are not primary support statuses. They modify how Python renders or
gates a capability whose primary status is known.

Product Truth rules are governed by `docs/Product_Truth_Layer.md`.

Until a runtime Product Truth registry exists, InfoHelp must derive truth from:

1. current runtime code;
2. `PROJECT_LOG.md`;
3. `docs/TZ_FakturaBot.md`;
4. focused contract docs;
5. `CHANGELOG.md` as supporting historical context.

Roadmap intent is not runtime support. If runtime does not prove the feature,
InfoHelp must say `planned`, `partial`, `unsupported`, or `unknown`.

## Unknown / Discovery / Triage

An unknown `capability_id` is not one thing and is not a final answer.
It is a signal that the input did not map to a known Product Truth capability
or topic. When authorization, active state, and routing permit it, InfoHelp
should hand the input to a separate Unknown / Discovery / Triage step.

The triage step is Python-owned and side-effect free. It classifies the input
into one allowed class:

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

These classes do not change Product Truth. They help choose a safe response:

- render Product Truth when the input maps to a known capability;
- ask a clarification question when the business need is unclear;
- politely reject or redirect out-of-domain questions;
- ignore/block spam or abusive noise safely;
- answer smalltalk briefly and return to business workflow scope;
- offer to prepare a feature/customization/admin review item only when the flow
  is implemented and confirmation-gated.

Current status: Product Truth MVP exists, deterministic Product
Truth-backed InfoHelp fast-paths exist for selected topics, and bounded
Unknown / Discovery / Triage v1 classification exists. Eligible
customization/admin/product-truth-gap candidates can enter the implemented
confirmation-gated preview/save flow. Bounded InfoHelp resolver coverage is
still not complete. Admin answer-only response-to-user exists as a separate
admin-confirmed runtime flow, but InfoHelp itself does not send responses.
InfoHelp Level 2 is not complete.

### Analytics Capability Guidance

InfoHelp must distinguish analytics domains by Product Truth, not by broad
business wording alone.

- Invoice analytics is partial and read-only. It may be described only as
  questions over saved outgoing invoices for the current authorized supplier,
  including counts, sums, periods, customers, and normalized bot payment states.
- Simple current/previous/explicit calendar-year count/total questions are
  supported as an internal deterministic fast path under invoice analytics, not
  as a separate competing top-level user-facing capability.
- Receipt/incoming-invoice categories are partial. InfoHelp may say that
  categories can be reviewed inside the existing upload preview flow and that
  the model only suggests bounded candidates from Python-provided categories.
  It must also say this is not a standalone top-level action, not tax advice,
  not accounting export, and not analytics.
- Accounting-document analytics is partial and read-only through
  `accounting_document_analytics`. InfoHelp may describe bounded analytics over
  confirmed receipts/bloceky and incoming invoices/prijate faktury in the
  current workspace: counts, sums, vendor/category/month/document-type grouping,
  comparisons, limited lists, averages, and top rankings.
- Receipt/blocek analytics is partial as a receipt-focused alias of that
  runtime. InfoHelp must not route analytics questions to the add/upload
  receipt flow.
- InfoHelp must still distinguish category capture from analytics: categories
  are confirmed intake metadata, not tax deductibility, VAT reporting, or
  accounting approval.
- Bank, cashflow, VAT, tax, accounting export, and full accounting analytics
  are unsupported
  unless later code/docs add a separate proven implementation.
- User-facing business answers should be Slovak by default, even when the
  user asks in Ukrainian, Russian, or English.

## Response Contract

Every InfoHelp answer must include:

1. direct answer to the user's question;
2. current Product Truth primary status plus relevant flags/context;
3. plain-language limitation or setup condition;
4. safe next step;
5. customization request or human-review offer when useful and supported by the
   request layer.

Human-review offers are contextual, not global boilerplate. Add them when the
question is about an unsupported capability, missing requested behavior in a
partial or planned capability, an unknown product/support/how-to topic, or an
explicit user request that the bot cannot satisfy. Supported how-to answers
should stay direct and must not end with unrelated escalation text.

Preferred user-facing offer copy:

```text
Ak chcete, môžem z toho pripraviť požiadavku na kontrolu správcom. Uloží sa iba vtedy, keď ju potvrdíte.
```

Do not expose internal architecture wording such as "samostatný potvrdený
náhľad" unless the conversation is explicitly about the confirmation step and
the wording is natural for the user.

InfoHelp must not:

- hide behind `/menu` for a real capability question;
- claim unsupported integrations are available;
- launch a mutation from an informational question without explicit user
  confirmation;
- disclose internal stack traces, filesystem paths, secrets, prompts, or raw
  debug logs;
- let the LLM invent actions, product status, or setup state.

### Mark Invoice Paid

User: "Can I mark invoice 06 as paid?"

Expected guidance:

- classify as `mark_existing_invoice_paid`;
- answer from Product Truth as `supported` MVP;
- explain that it stores bot-local paid/uhradena state;
- explain that configured owner OAuth Drive can enqueue/upload the existing local PDF through the worker, while unconfigured Drive falls back to the local stub;
- explicitly avoid claiming bank confirmation, bank matching, or upload success before worker state `uploaded`;
- suggest: "oznac fakturu 06 ako uhradenu" and confirm with the provided button.

## InfoHelp Answer Obligation For Implemented Capabilities

Every user-facing capability that exists in runtime must be explainable through
InfoHelp within the evidence available in Product Truth. This applies to
top-level actions, admin commands, integrations, workflow slices, partial
features, and support/human-review surfaces.

For each implemented or changed capability, InfoHelp should cover:

- what it does;
- how to start or use it;
- setup, credential, authorization, or admin requirements;
- limitations and partial-scope boundaries;
- dangerous or sensitive warnings;
- what it does not do;
- what to do when the user needs unsupported behavior;
- whether human-review escalation is available and whether it requires
  confirmation.

Common question templates that should be considered when adding a capability:

- `Čo vieš?`
- `Ako zapnem/použijem <feature>?`
- `Vieš <capability>?`
- `Prečo to nefunguje?`
- `Čo sa stane po potvrdení?`
- `Vieš to urobiť hlasom?`
- `Je to automatické?`
- `Posiela sa to správcovi?`
- `Dá sa to upraviť?`

Do not add runtime support and leave only action routing. A user who asks about
the capability must get a truthful answer instead of stale unsupported wording
or a menu fallback.

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
6. Unknown / Discovery / Triage classification when no known capability/topic
   fits and the current state allows discovery.
7. Bounded fallback only after InfoHelp and triage cannot resolve safely.

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
primary_status
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
- `unknown`;
- one Python-provided triage class when running Unknown / Discovery / Triage;
- bounded slots requested by Python for a customization draft.

Forbidden model outputs:

- new canonical actions;
- unregistered capabilities;
- product status not present in Product Truth;
- authoritative final response modes;
- direct side effects;
- DB/storage writes;
- unauthorized support claims.
- triage classes outside the Python-provided enum;
- saved customization/admin/developer request claims without an implemented
  confirmation-gated flow.

Python owns final response policy. The model may provide an optional
non-authoritative `response_mode_hint` only when Python explicitly asks for
one, but Python must derive the final response mode from Product Truth
`primary_status`, flags/context, account state, active FSM/routing state, and
safety policy.

For Unknown / Discovery / Triage, the model may select only one allowed triage
class and optional bounded metadata requested by Python. It must not invent
capability IDs, change Product Truth status, promise feature availability,
send admin notifications, save requests, bypass active FSM ownership, or
bypass authorization.

## Response Modes

InfoHelp response modes are Python-owned rendering decisions:

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
- `offer_human_review`;
- `state_guidance`;
- `offer_reset`;
- `bounded_fallback`.

Each mode must have deterministic safety rules and tests.

The LLM must not choose these modes authoritatively. If examples include a
response-mode-like field, it is only an optional hint for Python to validate or
ignore.

## Customization Request / Human Review Handoff

When a user asks for a feature that is unsupported, partial, planned, or
account-specific, InfoHelp should offer a customization request when safe.
When the user asks a product/support/how-to/troubleshooting question that the
bot cannot answer reliably from Product Truth and current runtime state,
InfoHelp may offer a human-review item when the confirmed request layer exists.

Example:

```text
Momentálne Google Disk nie je podporovaný. Faktúry sa teraz ukladajú v systéme
bota a môžete si ich zobraziť alebo stiahnuť cez Telegram.

Ak chcete, môžem z toho pripraviť požiadavku na kontrolu správcom. Uloží sa iba
vtedy, keď ju potvrdíte.
```

Customization request rules are governed by
`docs/Customization_Request_Layer.md`.

InfoHelp may draft a request only when the runtime Customization Request Layer
exists. Until then, it may say that the feature is a future/requestable product
direction only if the wording does not imply storage happened. Otherwise it
must not pretend a request was created.

Current runtime can save confirmed review items through the customization
request flow, expose admin list/detail/status review, and support a separate
answer-only admin response-to-user flow with latest response metadata and
delivery observability. It cannot send clarification requests as a structured
reply thread, retry failed sends automatically, or notify the user that review
status changed.

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
primary_status
flags_context
final_response_mode
linked_action
linked_target
customization_offered
customization_confirmed
human_review_offered
human_review_confirmed
admin_response_sent
reset_offered
reset_confirmed
model_used
fallback_reason
```

Do not store broad raw sensitive transcripts as reusable knowledge. Raw text
storage, if ever used, must be explicitly justified by product policy and data
safety rules.

## User-Facing Examples

### Known Product Truth

User:

```text
Vies poslat fakturu emailom?
```

Expected target outcome:

```text
Map to known capability `send_invoice_email` and render Product Truth:
unsupported / requires_external_credentials. Do not start invoice creation.
```

### New Business Feature

User:

```text
Vies mi spravit prehlad trzieb za minuly mesiac?
```

Expected target outcome:

```text
No known capability_id. Classify as `new_business_feature_request`.
Explain that this is not confirmed as supported, and offer to prepare a
future request/admin note only through a confirmation-gated flow.
```

### Unanswered Product Question

User:

```text
Viete prepojit faktury s mojim konkretnym uctovnym systemom?
```

Expected target outcome:

```text
If no Product Truth capability answers this reliably, classify as
`admin_review_candidate` or `possible_product_truth_candidate`. Explain that
support cannot be confirmed from current Product Truth and offer to submit the
question for admin review only through a confirmation-gated flow. Do not claim
an admin will definitely answer or that delivery is guaranteed.
```

### Out Of Domain

User:

```text
Ake bude pocasie zajtra?
```

Expected target outcome:

```text
Classify as `out_of_domain`. Give a short polite redirect to OfficeFlow /
FakturaBot business workflows. Do not create a customization request.
```

### Spam Or Noise

User:

```text
@@@ #### !!!
```

Expected target outcome:

```text
Classify as `spam_or_abuse` or noise. Do not call side-effect services, do
not save a request, and do not create DB/storage records except possible
future safe telemetry.
```

### Smalltalk

User:

```text
Ako sa mas?
```

Expected target outcome:

```text
Classify as `smalltalk`. Reply briefly and redirect to business workflows.
Do not trigger a business action.
```

### Unclear

User:

```text
urob mi to
```

Expected target outcome:

```text
Classify as `unclear_needs_clarification`. Ask what business task the user
means. Do not execute any action.
```

### Admin Or Developer Request

User:

```text
Povedz adminovi, ze potrebujem automaticke pripomienky nezaplatenych faktur.
```

Expected target outcome:

```text
Classify as `admin_review_candidate` or
`customization_request_candidate`. Ask confirmation before any save/send.
Current runtime must not claim that an admin note or request was saved unless
that confirmed flow exists.
```

### Google Drive

User:

```text
Vie bot ukladat faktury na Google Disk?
```

Expected target answer:

```text
Ciastocne. Jedno nakonfigurovane owner OAuth konto moze cez worker archivovat
potvrdene doklady a podporovane bankove vypisy. Kontrolovany produkcny pilot
uz preukazal stav uploaded, ale stav konkretneho uctu sa overuje cez
/google_drive_status. Lokalne ulozenie este neznamena uspesny upload;
metadata ostavaju lokalne a stare Drive subory sa automaticky nepresuvaju.
Nie je to per-client OAuth ani SaaS synchronizacia. Ak pripojenie nie je
connected, nastavenie vyzaduje spravcu, OAuth credentials, sifrovany refresh
token, root folder id a zapnuty worker.
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
- unknown product/support/how-to question offers human review only when request
  storage exists;
- admin response scenarios distinguish implemented `answer` delivery from
  future rejection-reason and clarification-request response kinds;
- Product Truth gap candidates do not auto-mutate Product Truth;
- no hidden invoice/contact/document side effects occur.
- unknown but plausible business feature request does not fall to only static
  menu fallback;
- out-of-domain input does not become a customization request;
- spam/noise does not create admin/developer work;
- smalltalk does not trigger a business action;
- clear direct action still wins before InfoHelp/triage;
- active FSM state still wins before InfoHelp/triage;
- voice transcript follows the same state-aware path;
- Slovak, Ukrainian, Russian, mixed/surzhyk, and noisy STT examples are
  represented for known capabilities, discovery, and unclear cases.

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
- claim admin response delivery when only request storage/status review exists;
- learn raw sensitive transcripts as aliases;
- allow learned aliases to create canonical actions;
- expose internal debug data to users;
- bypass active FSM ownership;
- trigger AI calls for unauthorized users.

### Google Drive Owner OAuth Partial Runtime - 2026-08-02

InfoHelp must answer Google Drive questions from Product Truth as `partial` when
referring to the current owner OAuth archive slice.

Required wording boundaries:

- say it requires admin setup, OAuth client credentials, `GOOGLE_TOKEN_CRYPTO_SECRET`, an encrypted owner refresh token, and a personal My Drive root folder id;
- say it is single-owner only, not per-client OAuth and not full SaaS Drive sync;
- say newly confirmed receipts and incoming invoices use the owning workspace's
  persisted separate Drive folder and immutable queued target;
- say local save may succeed while upload is pending/unavailable, metadata stays
  local, and existing remote files are not migrated automatically;
- say service-account mode is unsupported for personal My Drive unless Workspace/Shared Drive is explicitly configured later;
- say invoice PDFs remain local in this MVP;
- say upload success must not be claimed until the worker records `uploaded`;
- when Drive is disabled/not configured, keep the local stub/no-upload wording;
- direct the user to `/google_drive_status` for the deterministic current
  connection state;
- treat `requires_external_credentials` as a capability dependency, not as
  proof that the current account is unconfigured;
- do not render Gmail/Drive account status when no account context was supplied;
- controlled production evidence may be described as one proven pilot upload,
  never as per-user or general SaaS availability.

Questions about marking an invoice paid must still emphasize bot-local payment
state only: no bank confirmation and no bank matching.

### OfficeFlow Work-Time Partial Runtime - 2026-07-01

InfoHelp must answer work-time / dochadzka questions from Product Truth as `partial`.

Required wording boundaries:

- say the bot can record a simple work day, close it, add a confirmed manual range, configure a fixed lunch-break deduction, and generate a monthly Excel report;
- say authorization/setup is required before business work-time state is written or deleted;
- say exact times and lunch-break changes are preview-confirmed and Python-validated;
- say reports show net hours after the configured lunch deduction; duration-only rows keep the user-confirmed net duration stable;
- say the MVP supports one interval per user/day;
- say payroll, salary calculation, legal HR attendance compliance, multi-employee attendance administration, accounting/payroll export, automatic work-time detection, and generated-report deletion as canonical data are not implemented;
- when the user asks for unsupported attendance features, offer safe clarification or customization-request handling where the current runtime supports it, without claiming implementation.

### Contact registry guidance - 2026-07-17

For questions about adding a contact or finding a Slovak company by name/IČO, InfoHelp must classify to `contacts` and say that manual/document intake is available. Official-registry search is deployment-configurable and is enabled in current production for every authorized user with an active workspace/profile. InfoHelp should direct the user to `/contact`, `/contact_add`, or `/add_kontakt`, explain multiple-candidate selection and final confirmation, and state that email, IBAN, and contact person are normally typed manually.

### Contact search quality and tax-enrichment setup - 2026-07-18

InfoHelp must explain that exact normalized company names suppress unrelated weak results, while close spacing/typing suggestions remain manual selections. It must not call `ZE VS` an exact `Zevs` identity or treat `zevs` inside a longer surname as exact evidence.

RPO supplies identity/address data. Financial Administration DIČ/IČ DPH enrichment uses an audited official exact-IČO mapping; it is disabled by default in code and depends on an API key plus the parent RPO gate. Current production has both providers enabled for all authorized active workspaces. Any unavailable, invalid, ambiguous, or missing DIČ result falls back to typed DIČ without losing the RPO draft. IČ DPH is accepted only when officially returned for the exact selected IČO and is never constructed from DIČ. No commercial scraping is used.

InfoHelp must disclose that the official source can be unavailable or stale and may omit DIČ/IČ DPH; IČ DPH is never inferred. It must not claim commercial scraping, automatic discovery, automatic save, background synchronization, or a distinct top-level registry action.

### Runtime issue intake guidance - 2026-07-28

Questions such as `Vieš nahlásiť problém?` and `Ako nahlásim problém?` are
informational and must not create a record. InfoHelp answers in Slovak that only an
administrator can store one complete report using `/issue <opis>` or bounded
text/voice. It must state that storage does not confirm, diagnose, repair, merge or
deploy a bug, promise timing, or alter the active business action.


### Periodic contact-registry monitoring guidance - 2026-07-29

InfoHelp must classify the capability under `contacts` as `partial`, `requires_setup`, and `requires_external_credentials`. When enabled, the bot checks eligible exact-IČO contacts every 14 days at 03:00 Bratislava time, reports bounded official name/address/DIČ/IČ DPH differences, and offers buttons to update the contact or leave it unchanged.

InfoHelp must state that no contact changes automatically, unavailable tax data does not clear saved tax fields, and already issued invoices/PDFs are not rewritten. It must not promise live/real-time data, monitoring for contacts without valid IČO, email/IBAN/person discovery, or background monitoring when the deployment flag is off.

### Explicit problem-prefix routing - 2026-07-31

After authorization and STT, the first meaningful token is a deterministic
support boundary. The markers `проблема`, `помилка`, `баг`, `chyba`,
`problem`, `bug`, and `error` must not be interpreted as invoice, contact,
receipt, accounting-document, or analytics commands merely because the report
mentions those domains.

For administrators, the complete text/voice report enters the existing
`report_runtime_issue` capture. For other authorized idle users, the same
prefix starts the existing confirmation-gated admin-review request preview;
no request row exists until approval. Unauthorized users still do not reach
STT/LLM or either persistence path. Active non-admin FSM ownership is unchanged.

## Contextual InfoHelp Assistant V2 - 2026-08-02

Contextual V2 extends the existing InfoHelp owner; it is not a parallel recovery layer. One inbound update may cause exactly one enhanced InfoHelp call after the primary resolver when the primary result is unknown, mutating/destructive, missing a required slot, capability-like, corrective/negative, an unknown command, an explicit reply follow-up, or an active-flow help question.

The bounded JSON distinguishes speech act, domain, exact business object, operation, reference, missing slots, correction/negation, explicit reply, active flow, registered action/capability/command and confidence. Python validates every field, repeats Product Truth lookup, requires exact `domain + object + operation`, and retains FSM, callback, tenant, confirmation and side-effect authority. A receipt delete never becomes invoice/account deletion; contact edit never becomes supplier-profile edit.

Every bounded enum/list is sent with literal allowed values. The primary resolver result is untrusted diagnostic context and must not override an exact object named in the current input. Descriptive placeholder prose is never a valid output value; invalid output fails closed without a retry or side effect.

An explicit reference token is copied as bounded text, including a numeric invoice reference such as `10`. It is never discarded merely because it is numeric, and it is never invented when absent. Python remains responsible for lookup, ambiguity/not-found handling, continuation state, confirmation, and execution.

Recent context is process memory only: at most three user and three visible bot turns, same user/chat/workspace, ten-minute TTL, lost on restart. It excludes unauthorized input, files, logs, DB rows, secrets and background sends. A same-chat reply to this bot is part of the current request independent of TTL. Context clears on `/start`, `/menu`, `/cancel`, workspace switch and completed user-data deletion.

The old broad catalogue is retained only for an explicit overview. Invalid model output and genuinely unclear input receive a short narrow fallback with no button or effect. Rollout is `INFOHELP_CONTEXTUAL_V2_ROLLOUT=disabled|admin_pilot|enabled`; invalid/missing values are `disabled`.
