# Customization Request Layer

## Purpose

This document defines how OfficeFlow/FakturaBot should handle non-standard,
unsupported, partial, planned, or account-specific business requests.

The product must not answer a real business need with only "I do not
understand" or `/menu`. It also must not pretend that an unsupported feature is
available. The correct behavior is to classify the need against Product Truth,
draft a controlled request, ask for confirmation, and save it only when the
request layer actually exists.

## Current Status

This document is an active contract with a partial runtime foundation.

As of Customization Request MVP Phase 2:

- confirmed customization request storage exists through
  `CustomizationRequestService`;
- eligible idle InfoHelp/Triage candidates can show a user-facing preview and
  save one confirmed pending-review request only after explicit approval;
- draft previews live only in FSM/temp state before approval;
- draft previews are owner-bound and carry a deterministic `request_id` so
  duplicate approval attempts do not create duplicate rows;
- pre-confirmation FSM draft data should keep redacted original text plus a raw
  text hash instead of raw unredacted transcripts; save re-applies redaction;
- admin-only read/list and read-detail commands exist as read-only review
  surfaces;
- admin-only accept/reject commands can mark a confirmed pending request as
  `reviewed_accepted` or `reviewed_rejected` for status tracking only;
- admin notification is not implemented;
- review status transitions do not mean implementation approval, Product Truth
  change, backlog conversion, notification, or code-agent handoff;
- Product Truth mutation is not implemented;
- code-agent handoff is not implemented;
- this is a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

## Normative Status

This is a mandatory-read contract for work touching:

- unsupported/partial/planned feature handling;
- InfoHelp customization offers;
- request drafting;
- admin/developer review workflows;
- future code-agent handoff;
- account-specific workflow preferences;
- storage for user business requests.

Companion docs:

- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Code_Agent_Handoff_Contract.md`;
- `docs/Implementation_Agent_Checklist.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`.

## Product Role

The Customization Request Layer turns user intent into a structured product
signal.

It is for requests such as:

- "I want invoices stored on Google Drive."
- "I want invoices sent to my accountant."
- "I want SMS reminders."
- "I want my old PDF invoice layout."
- "I want a monthly work-hours report."
- "I want accounting software export."
- "I want an extra VAT row."
- "I want receipts categorized differently."

It is not:

- immediate implementation;
- deployment approval;
- a replacement for deterministic runtime actions;
- a support-ticket claim if no ticket/request storage exists;
- a way to bypass Product Truth.

## Trigger Conditions

A customization request may be offered when:

- Product Truth status is `unsupported`, `partial`, `planned`, or `unknown`;
- the user asks for account-specific behavior;
- the user asks for a new workflow or integration;
- the user asks for a different PDF/layout/business output;
- repeated InfoHelp questions indicate an unmet business need;
- the request is safe to capture.

Do not offer a customization request when:

- the user is simply trying to execute a supported action;
- the request is a destructive confirmation;
- the user is unauthorized;
- the request would require secrets/credentials to be pasted into chat without
  a safe credential flow;
- the product has no implemented request storage but the wording would imply a
  request was saved;
- the request is illegal, abusive, or clearly unsafe.

Unknown / Discovery / Triage may classify an input as
`new_business_feature_request`, `customization_request_candidate`,
`admin_review_candidate`, or `possible_product_truth_candidate`. The
`possible_product_truth_candidate` class is eligible only when there is enough
business context to draft a safe preview without claiming Product Truth support.
That classification is not a saved request and not a promise that work will
happen. It only permits Python to offer a confirmation-gated next step when the
Customization Request Layer exists.

Out-of-domain, spam/abuse/noise, smalltalk, and unclear inputs must not become
customization requests by default.

## Required Flow

Target flow:

1. Receive user text/voice after authorization.
2. Resolve direct supported actions first when the user clearly wants action
   execution.
3. For capability/customization questions, check Product Truth.
4. If no known capability/topic matches, run Unknown / Discovery / Triage.
5. Detect business need and domain only for safe business/admin/customization
   candidates.
6. Draft a structured request.
7. Show the draft to the user.
8. Ask explicit confirmation.
9. Save a pending request only after confirmation.
10. Route to admin/developer review.
11. Optionally convert to a code-agent handoff task after approval.

No side effect may happen at step 5 or 6. Drafting is not saving.
Current runtime covers read-only admin list/detail review surfaces and
status-only admin accept/reject review transitions for confirmed requests.
Accept/reject changes only the request review status. Product Truth mutation,
backlog conversion, user/admin notification, code-agent handoff, and
implementation approval remain later phases.

## Request Object

Minimum object:

```text
request_id
user_id
workspace_id
original_user_text_ref
normalized_business_need
detected_domain
capability_id
capability_status
proposed_task_title
proposed_description
proposed_acceptance_criteria
required_user_inputs
risk_level
requires_human_approval
status
created_at
updated_at
```

Recommended additional fields:

```text
source_channel
source_message_id
language
redaction_policy
product_truth_refs
linked_capability_ids
linked_existing_actions
setup_requirements
external_credentials_required
admin_notes
developer_notes
code_agent_ready
code_agent_task_id
reviewed_by
reviewed_at
expires_at
```

`original_user_text_ref` should be a stored reference, hash, redacted text, or
policy-approved raw text. Do not blindly store sensitive full transcripts as
reusable knowledge.

## Status Model

Request statuses:

- `draft_shown`: draft prepared for user, not saved as pending work;
- `pending_confirmation`: waiting for user confirmation;
- `pending_admin_review`: confirmed by user and awaiting review;
- `needs_user_input`: admin/developer needs more information;
- `accepted`: approved for implementation planning;
- `converted_to_code_agent_task`: converted to a bounded implementation task;
- `rejected`: declined by admin/developer with reason;
- `cancelled_by_user`: user cancelled before or after confirmation;
- `implemented`: delivered and verified;
- `expired`: stale request closed without action.

Do not use `implemented` unless runtime behavior, tests/evals, docs, and
approval prove delivery.

## Risk Levels

Risk levels:

- `low`: copy, simple configuration, non-sensitive layout preference.
- `medium`: workflow change, PDF layout change, reporting, account-specific
  behavior.
- `high`: external sending, integrations, accounting export, storage sync,
  credential-dependent behavior.
- `critical`: data deletion, migration, security/access changes, tenant
  isolation, payment/billing, legal/compliance-sensitive behavior.

Risk affects required review and acceptance criteria. High and critical
requests require human approval before implementation or deployment.

## Domains

Initial request domains:

- `invoice_pdf_layout`;
- `invoice_delivery`;
- `invoice_storage`;
- `invoice_fields`;
- `reminders`;
- `work_hours`;
- `reports`;
- `accounting_documents`;
- `accounting_export`;
- `contacts`;
- `supplier_profile`;
- `google_drive`;
- `email`;
- `sms`;
- `access_control`;
- `workspace_setup`;
- `other`.

The domain is a routing aid. It is not proof that the feature exists.

## Drafting Rules

The draft shown to the user must include:

- what the user appears to need;
- current Product Truth status;
- what information is still required;
- what the request would ask an admin/developer to review;
- whether human approval is required;
- what will happen if the user confirms.

The draft must not say:

- "I will implement this now";
- "This is already available" unless Product Truth says `supported`;
- "I created the request" before confirmation and save;
- "A developer will definitely do this";
- "This will be deployed" without approval.

## Bounded LLM Role

The LLM may:

- normalize the business need;
- classify likely domain from Python-provided domain list;
- draft proposed title/description/acceptance criteria;
- identify missing user inputs;
- suggest risk level from Python-provided options.

Python must:

- provide allowed domains/statuses;
- provide Product Truth;
- validate the draft;
- redact or reject sensitive content;
- ask confirmation;
- save only after confirmation;
- enforce access, tenant, and admin review rules.

The LLM must not:

- create requests directly;
- write DB/storage;
- invent capability status;
- bypass confirmation;
- create code-agent tasks on its own;
- accept credentials or secrets as ordinary text.

## Confirmation Rules

Saving a customization request is a confirmation-like flow.

The confirmation must use the canonical DecisionResolver family that matches
the UI:

- `yes_no` for simple save/cancel;
- `approve_edit_cancel` when the user can approve, edit, or cancel the draft.

Handler-level tests must prove that local confirmation parsers are not added.

## Storage Rules

Runtime storage is future work and must be migration-safe.

Before implementing storage:

1. define table/filesystem shape;
2. define tenant/workspace scoping;
3. define redaction policy for original text;
4. define status transitions;
5. define admin review access;
6. define retention/expiry;
7. define backup/rollback if server data is touched;
8. update `PROJECT_LOG.md` and relevant docs.

No request storage may be cross-tenant.

## Admin Review

Admin/developer review should be able to answer:

- is the request clear?
- is it safe?
- is it already supported?
- is it duplicate?
- what inputs are missing?
- what risk level applies?
- should this become a code-agent task?
- what acceptance criteria must be met?

Current admin review status commands are limited to marking a confirmed pending
request as `reviewed_accepted` or `reviewed_rejected`. `reviewed_accepted`
means the request was accepted for later human consideration only. It does not
approve implementation, mutate Product Truth, convert to backlog, notify users,
or create a code-agent handoff.

Admin review is required before:

- external integrations;
- credential-dependent features;
- sending email/SMS;
- storage sync;
- accounting export;
- PDF template changes that affect legal/business output;
- access/security/tenant changes;
- data migrations;
- code-agent handoff.

## Code-Agent Handoff Boundary

A customization request may become a code-agent task only after:

- user confirmation;
- Product Truth classification;
- admin/developer approval where required;
- clear acceptance criteria;
- relevant docs/contracts identified;
- tests/evals defined;
- no-go constraints written;
- rollback/migration concerns reviewed.

The handoff contract is governed by `docs/Code_Agent_Handoff_Contract.md`.
Do not claim runtime code-agent handoff is implemented unless Product Truth and
runtime code prove it.

## Examples

### Google Drive Storage

User:

```text
Chcem ukladat faktury na Google Disk.
```

Draft summary:

```text
Current status: unsupported / requires_external_credentials.
Need: store generated invoices in a Google Drive folder.
Required inputs: Google account/workspace, folder rules, authorization model.
Risk: high.
Human approval: required.
Acceptance criteria: invoices are saved to configured Drive folder only after
credentials/setup are approved; Telegram download remains available; failures
do not lose local invoice PDFs.
```

### Old PDF Template

User:

```text
Chcem aby faktura vyzerala ako moja stara PDF sablona.
```

Draft summary:

```text
Current status: partial/customization required.
Need: adapt invoice PDF layout to match old template.
Required inputs: sample PDF/template, logo/assets if any, required fields,
row wrapping expectations, QR position, footer, column widths.
Risk: medium.
Human approval: required.
Acceptance criteria: generated PDF matches agreed layout criteria and existing
invoice PDF regression tests still pass.
```

### SMS Reminders

User:

```text
Mozete mi pripominat neuhradene faktury cez SMS?
```

Draft summary:

```text
Current status: unsupported / requires_external_credentials.
Need: SMS reminders for unpaid invoices.
Required inputs: SMS provider, sender identity, phone numbers, consent rules,
schedule, costs, opt-out behavior.
Risk: high.
Human approval: required.
Acceptance criteria: reminders are sent only under approved rules, with logs,
rate limits, and no sending without explicit setup.
```

## MVP Acceptance Criteria

Customization Request MVP is not complete until:

- Product Truth check happens before request offer;
- request draft includes required fields;
- user can approve/edit/cancel;
- DecisionResolver handles confirmation;
- request is saved only after confirmation;
- request is tenant/workspace scoped;
- unsupported features are not presented as available;
- high/critical risks require admin review;
- no credentials/secrets are collected as normal chat text;
- tests cover save/cancel/edit and unauthorized user behavior;
- product UX evals cover plausible business requests;
- `PROJECT_LOG.md` records the actual maturity level.

## Product UX Evals

Required eval scenarios:

- user asks for Google Drive storage;
- user asks for SMS reminders;
- user asks for old PDF template;
- user asks for invoice email delivery to accountant;
- user asks for accounting export;
- user asks for a supported action and no customization request is created;
- unknown business feature request is offered only as a confirmation-gated
  future request path;
- out-of-domain question is rejected or redirected and does not create a
  request;
- spam/noise does not create a request or admin work;
- smalltalk does not create a request;
- user cancels a request draft;
- user edits a request draft;
- unauthorized user asks for customization;
- user tries to paste credentials/secrets;
- high-risk request requires admin approval;
- request is not saved before confirmation.

## No-Go Rules

Do not:

- promise implementation;
- create a request without confirmation;
- store raw sensitive transcripts as reusable knowledge;
- accept credentials/secrets in ordinary chat;
- bypass Product Truth;
- bypass admin review for high-risk work;
- route unsupported requests directly to code agents;
- call request drafting "implementation";
- mark a request `implemented` without runtime delivery and verification.
