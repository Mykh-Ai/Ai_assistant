# Product Truth Layer

## Purpose

This document defines how OfficeFlow/FakturaBot decides what is true about its
own capabilities.

Product Truth is the authoritative layer that prevents the bot, an LLM, a
handler, or a future agent from claiming that a feature exists when it is only
planned, partial, unsupported, risky, or unknown.

The product direction is AI-assisted business operation. The trust model is not
"the model sounds confident"; the trust model is "Python and structured
registries provide verified truth, AI explains it inside bounds."

## Current Status

This document is a docs-first contract.

As of this documentation reset:

- no complete runtime Product Truth registry exists;
- current InfoHelp fallback is Level 1 only;
- capability-aware InfoHelp is planned as Level 2+;
- customization request creation is not implemented unless later code proves
  otherwise.

Until a runtime registry exists, Product Truth must be derived from current
code, `PROJECT_LOG.md`, `docs/TZ_FakturaBot.md`, active contract docs, and
focused evidence in tests.

## Normative Status

This is a mandatory-read contract for work touching:

- InfoHelp capability answers;
- user-facing support/help copy;
- semantic routing that explains capabilities;
- customization request creation;
- code-agent handoff;
- product docs that claim support;
- account/workspace-specific setup behavior;
- dangerous/sensitive operation descriptions.

Companion docs:

- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Registry_MVP_Design.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Code_Agent_Handoff_Contract.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`.

## Core Rule

LLM output is never Product Truth.

The model may:

- map user wording to a known capability candidate;
- draft a plain-language explanation from Python-provided facts;
- suggest a customization request draft inside bounds.

The model must not:

- invent capabilities;
- upgrade `planned` to `supported`;
- hide limitations;
- infer account setup that Python has not provided;
- promise external integrations;
- classify dangerous operations as ordinary support.

## Capability Statuses

Every user-facing capability answer must use one of these statuses.

### `supported`

The current runtime implements the capability end to end for the relevant user
state.

Required evidence:

- runtime owner exists;
- route/handler/service exists;
- access and tenant scoping are enforced where relevant;
- tests or documented manual verification cover the main path;
- user-facing docs do not contradict the claim.

### `partial`

The runtime implements only a bounded subset.

Use when:

- a feature works only for one document type, one flow, or one channel;
- voice works for intent but exact values are text-only;
- a read-only path exists but edit/delete/export does not;
- setup is incomplete for some accounts.

The answer must state the limit clearly.

### `planned`

The product direction or docs describe the capability, but runtime support does
not exist yet.

Planned must never be phrased as available.

### `unsupported`

The current product does not support the capability and no active plan should
be implied.

The answer may offer a customization request if the request layer exists and
the request is safe to capture.

### `unknown`

The system cannot establish truth from active sources.

Unknown must not become action execution. The safe next step is to ask for
clarification, route to admin/developer review, or say that support cannot be
confirmed.

### `dangerous`

The request is destructive, security-sensitive, financial-risky, data-risky, or
legally/compliance-sensitive.

Dangerous capabilities require stronger deterministic gates, explicit
confirmation, and often human/admin approval.

### `requires_setup`

The capability exists but depends on user/workspace setup that is missing or
not yet verified.

Example categories:

- supplier profile not complete;
- no service alias;
- no contacts;
- workspace-specific preference not configured.

### `requires_admin`

The capability requires admin approval or admin-side configuration.

Examples:

- access approval;
- workspace enablement;
- high-risk customization approval;
- future integration activation.

### `requires_external_credentials`

The capability depends on third-party credentials, API keys, OAuth consent, or
external service configuration.

Examples:

- Google Drive;
- real outbound email;
- SMS provider;
- accounting software export.

If credentials/setup do not exist, the answer must not imply the integration is
ready.

## Source Precedence

For current runtime truth, use this order:

1. current code and tests;
2. `PROJECT_LOG.md`;
3. `docs/TZ_FakturaBot.md`;
4. active focused contract docs;
5. `CHANGELOG.md` as historical support.

For product direction, use:

1. `docs/Product_Doctrine_2030.md`;
2. active roadmap/contract docs.

If direction and runtime differ, runtime truth wins for user-facing capability
claims. Direction may be reported only as `planned`.

Archived docs are not active Product Truth. They may give background only after
every claim is checked against active docs/code/logs.

## Registry Shape

The target runtime Product Truth registry should be structured. It may begin as
a Python data structure or JSON/YAML file, but Python must validate it before
use.

Minimum capability entry:

```text
capability_id
title
domain
status
summary_for_user
current_limitations
runtime_owner
commands
canonical_actions
linked_handlers
truth_source_refs
test_refs
safe_next_steps
customization_allowed
dangerous
requires_setup
requires_admin
requires_external_credentials
setup_state_keys
forbidden_claims
last_verified_at
last_verified_by
notes_for_agents
```

Optional fields:

```text
supported_channels
unsupported_channels
partial_subcapabilities
account_specific_overrides
external_service_name
admin_review_required_reason
data_sensitivity
migration_sensitivity
```

## Capability Domains

Initial domains should include:

- `invoices`;
- `invoice_pdf`;
- `contacts`;
- `supplier_profile`;
- `service_aliases`;
- `accounting_documents`;
- `officeflow_attachment_router`;
- `voice`;
- `access_control`;
- `storage`;
- `email`;
- `sms`;
- `google_drive`;
- `accounting_export`;
- `reminders`;
- `customization`;
- `admin`;
- `server_ops`.

Domain names are not user-facing promises. They are classification buckets.

## Account Setup Truth

Product Truth must include both product-level and account-level facts.

Product-level truth:

- feature exists or does not exist in runtime;
- feature is partial/planned/unsupported;
- feature is dangerous or integration-dependent.

Account-level truth:

- user is authorized or unauthorized;
- supplier profile exists or is missing;
- service alias exists or is missing;
- contacts exist or are missing;
- workspace/account has required setup;
- external credentials exist or are missing;
- admin approval is required.

Example:

```text
Capability: create invoice
Product status: supported
Account status: requires_setup when supplier profile or service alias is
missing
```

## Response Policy

Every Product Truth answer should produce:

1. answer status;
2. short direct answer;
3. current limitation/setup condition;
4. safe next step;
5. linked action or customization option when allowed.

Example for unsupported integration:

```text
Status: unsupported / requires_external_credentials
Answer: Google Drive storage is not available in the current runtime.
Limit: invoices are stored in the bot system and can be viewed/downloaded via
Telegram.
Next step: offer a customization request if the request layer exists.
```

## Forbidden Claims

The registry must explicitly block claims such as:

- "I can send invoices by email" unless real outbound email is implemented;
- "I can store invoices on Google Drive" unless integration and credentials are
  implemented;
- "I can send SMS reminders" unless provider, consent, and sending flow exist;
- "I created a support request" unless request storage and confirmation exist;
- "I changed your accounting export" unless deterministic execution happened;
- "I will deploy this change" without human approval.

Forbidden claims are part of Product Truth, not style guidance.

## Dangerous Capability Rules

Dangerous or sensitive capabilities include:

- database deletion;
- invoice deletion;
- data export;
- external sending;
- credential setup;
- storage migration;
- accounting/tax-sensitive transformations;
- tenant/workspace configuration changes;
- code-agent implementation/deployment.

These require deterministic gates. LLM may explain the gate but must not pass
it.

## Interaction With InfoHelp

InfoHelp must query Product Truth before answering capability/how-to/support
questions.

InfoHelp may:

- map user language to a known `capability_id`;
- explain the status;
- offer linked safe actions;
- offer customization requests where allowed.

InfoHelp must not:

- answer from memory alone;
- use roadmap docs as runtime proof;
- override dangerous/setup/admin flags;
- create side effects from informational questions.

## Interaction With Customization Requests

Customization requests are allowed when:

- the capability is `unsupported`, `partial`, `planned`, `unknown`, or
  account-specific;
- Product Truth marks `customization_allowed = true`;
- the request is safe to capture;
- the user confirms the draft;
- storage/admin review path exists.

Customization requests are not allowed when:

- the user asks for a destructive confirmation alias;
- the request would bypass access control;
- the request needs secrets/credentials that the bot cannot safely collect;
- the product has no implemented request storage/admin review path but the bot
  would imply one exists.

## Registry Lifecycle

Adding or changing a capability entry requires:

1. evidence from code/docs/logs;
2. status classification;
3. forbidden claims review;
4. safe next step definition;
5. tests/evals for user-facing answers;
6. `PROJECT_LOG.md` entry;
7. docs update if product scope changes.

Do not silently change a capability from `planned` to `supported`.

## Acceptance Criteria For Runtime Product Truth

The Product Truth Layer is not runtime-complete until:

- a controlled registry exists;
- InfoHelp reads from it;
- supported/partial/planned/unsupported/unknown statuses are tested;
- forbidden claims are enforced;
- account setup state can affect answers safely;
- dangerous/setup/admin/external-credential flags are represented;
- unknown does not execute side effects;
- customization offers depend on request-layer availability;
- product UX evals prove real business questions are answered honestly.

## Evaluation Scenarios

Required smoke/eval cases:

- "Can you send invoices by email?"
- "Can you store invoices on Google Drive?"
- "Can you send SMS reminders?"
- "Can you create an invoice now?"
- "Why can I not create an invoice?"
- "Can you export to accounting software?"
- "Can you delete my database?"
- "Can you use my old PDF template?"
- unauthorized user asks a capability question;
- user with missing supplier profile asks for invoice creation;
- user in active FSM asks why input failed.

## Current Known Truth Examples

These are documentation-level examples and must still be checked against
current code before runtime claims:

- invoice creation from text/voice: supported with bounded extraction and
  confirmation;
- invoice exact numeric/date/identifier values by voice: partial/text-only for
  precision-sensitive fields;
- invoice PDF generation: supported in current invoice flow;
- Google Drive invoice storage: unsupported/planned only unless later runtime
  code proves otherwise;
- SMS sending: unsupported unless later runtime code proves otherwise;
- real outbound invoice email sending: unsupported unless later runtime code
  proves otherwise;
- customization request creation: not implemented unless later runtime code
  proves otherwise;
- code-agent handoff from bot runtime: not implemented unless later runtime
  code proves otherwise.

## No-Go Rules

Do not:

- use LLM confidence as Product Truth;
- answer capability questions only with `/menu`;
- mark a roadmap idea as `supported`;
- hide partial limits;
- ignore account setup state;
- skip dangerous/admin/external-credential flags;
- offer customization request storage if it does not exist;
- update Product Truth without evidence and log entry;
- let learned aliases bypass Product Truth.
