# Customization Request Layer

## Purpose

This document defines how OfficeFlow/FakturaBot should handle non-standard,
unsupported, partial, planned, or account-specific business requests and
human-review items.

The product must not answer a real business need with only "I do not
understand" or `/menu`. It also must not pretend that an unsupported feature is
available. The correct behavior is to classify the need against Product Truth,
draft a controlled request or review item, ask for confirmation, and save it
only when the request/review layer actually exists.

## Current Status

This document is an active contract with a partial runtime foundation.

As of Admin Response to User MVP:

- confirmed customization request storage exists through
  `CustomizationRequestService`;
- eligible idle InfoHelp/Triage candidates can show a user-facing preview and
  save one confirmed pending-review request only after explicit approval;
- draft previews live only in FSM/temp state before approval;
- draft previews are owner-bound and carry a deterministic `request_id` so
  duplicate approval attempts do not create duplicate rows;
- pre-confirmation FSM draft data keeps redacted original text plus a raw text
  hash instead of raw unredacted transcripts; save re-applies redaction;
- admin-only `/customization_requests` lists pending confirmed requests;
- admin-only `/customization_request <id_or_prefix>` shows one request detail,
  including latest admin response delivery observability;
- admin-only `/customization_request_accept <id_or_prefix>` and
  `/customization_request_reject <id_or_prefix>` can mark a confirmed pending
  request as `reviewed_accepted` or `reviewed_rejected` for status tracking
  only;
- admin-only `/customization_request_reply <id_or_prefix>` can send one
  confirmation-gated `answer` response to the original requester through
  Telegram;
- the response flow persists latest response text/metadata before attempting
  Telegram delivery, then records `send_succeeded` or `send_failed`;
- latest response metadata is stored on `customization_requests`; multi-response
  or threaded conversation history is not implemented;
- current persisted rows do not yet have a dedicated `request_kind` or
  `request_type` field;
- current rows may conceptually represent a broader review item only through
  their source triage class and text fields;
- admin notification is not implemented;
- admin response kind selection is not implemented; MVP response kind is
  `answer` only;
- `needs_user_input` delivery to the user is not implemented;
- user notification on review decision is not implemented;
- admin notes are not implemented;
- review status transitions do not mean implementation approval, Product Truth
  change, backlog conversion, notification, or code-agent handoff;
- Product Truth mutation is not implemented;
- Product Truth candidate conversion is not implemented;
- backlog conversion is not implemented;
- code-agent handoff is not implemented;
- self-learning from customization requests is not implemented;
- request expiry/cleanup and rich pagination are not implemented;
- this is a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

## Normative Status

This is a mandatory-read contract for work touching:

- unsupported/partial/planned feature handling;
- InfoHelp customization offers;
- unanswered product/support/how-to/troubleshooting questions that may require
  human review;
- request drafting;
- admin/developer review workflows;
- future code-agent handoff;
- account-specific workflow preferences;
- storage for user business requests and human-review items.

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

The Customization Request Layer is part of a broader Admin Response / Human
Review Loop. It turns user intent into a structured product/support signal that
can be reviewed by a human without pretending the bot already knows the answer
or that a feature is already available.

The current `customization_requests` storage/flow may represent these broader
item types conceptually:

- `feature_request`;
- `customization_request`;
- `unanswered_product_question`;
- `support_question`;
- `troubleshooting_question`;
- `possible_product_truth_gap`;
- `admin_review_candidate`.

A dedicated persisted `request_kind` / `request_type` field is not implemented
yet. Adding one is a planned/next implementation requirement and must be
migration-safe.

It is for requests or review items such as:

- "I want invoices stored on Google Drive."
- "I want invoices sent to my accountant."
- "I want SMS reminders."
- "I want my old PDF invoice layout."
- "I want a monthly work-hours report."
- "I want accounting software export."
- "I want an extra VAT row."
- "I want receipts categorized differently."
- "I asked whether the bot can do X and the bot cannot answer reliably."
- "I need help with a supported workflow but the guidance is not enough."
- "The bot says this is unknown; can an admin check?"

It is not:

- immediate implementation;
- deployment approval;
- a replacement for deterministic runtime actions;
- a support-ticket or admin-response claim if no confirmed storage/response
  delivery exists;
- a way to bypass Product Truth.

## Trigger Conditions

A customization request may be offered when:

- Product Truth status is `unsupported`, `partial`, `planned`, or `unknown`;
- the user asks for account-specific behavior;
- the user asks for a new workflow or integration;
- the user asks for a different PDF/layout/business output;
- the user asks a product, support, how-to, or troubleshooting question that
  the bot cannot answer reliably from Product Truth and current runtime state;
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

Current implemented flow:

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

No side effect may happen at step 5 or 6. Drafting is not saving.
Current runtime covers the user preview/edit/approve/cancel path, read-only
admin list/detail review surfaces, and status-only admin accept/reject review
transitions for confirmed requests. Voice can start the preview from an idle
STT transcript and can approve/cancel through the same controlled decision
path. Exact title/summary edits remain text-first. Current runtime also covers
an explicit admin reply path for one latest `answer` response to the original
requester: admin enters text, previews it, and sends only after explicit
confirmation.

Accept/reject changes only the request review status. Product Truth mutation,
Product Truth candidate conversion, backlog conversion, user/admin
notification, code-agent handoff, self-learning, and implementation approval
remain later phases. Admin reply does not change review status and does not
create an automatic notification on accept/reject.

Target closed loop:

1. User asks an unsupported/unknown product question, support/how-to question,
   troubleshooting question, or submits a feature/customization need.
2. Bot checks Product Truth and current runtime state.
3. If the bot cannot answer reliably or the need is unsupported/partial/planned
   and safe to capture, it asks whether to submit the item for human review.
4. User confirms.
5. Python saves a tenant-scoped review item.
6. Admin reviews the item.
7. Admin sends an answer, reason, or clarification request through the bot.
8. User receives the response.
9. System stores response metadata.

Steps 7-9 are implemented only for the bounded Admin Response MVP `answer`
flow. Rejection-reason response kinds, clarification requests, structured
follow-up threads, manual retry, Product Truth candidate conversion, backlog
conversion, and code-agent handoff remain future scope.

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
request_kind
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
admin_response_text
response_sent_at
response_sent_by
response_kind
response_delivery_status
response_attempts
response_failed_reason
responded_to_request_status
expires_at
```

`original_user_text_ref` should be a stored reference, hash, redacted text, or
policy-approved raw text. Do not blindly store sensitive full transcripts as
reusable knowledge.

## Status Model

Review statuses and answer/delivery statuses must remain distinct.

Runtime-supported persisted statuses:

- `confirmed_pending_review`: confirmed by the user and awaiting admin review;
- `reviewed_accepted`: admin accepted the request for later human
  consideration only;
- `reviewed_rejected`: admin rejected the request for status tracking only.

`reviewed_accepted` and `reviewed_rejected` are status-only review decisions.
They do not mean that a user received an answer, that implementation was
promised, or that Product Truth changed.

Runtime FSM-only draft states:

- preview draft shown to user, not saved as pending work;
- waiting for approve/edit/cancel confirmation;
- waiting for text-only title/summary edit.

Reserved or future persisted statuses present in the service/schema:

- `needs_user_input`: reserved for a future admin/developer clarification flow;
- `converted_to_product_truth_candidate`: reserved for a future Product Truth
  candidate conversion flow;
- `converted_to_backlog`: reserved for a future backlog conversion flow;
- `cancelled_by_user`: reserved for a future persisted cancellation lifecycle;
- `expired_unconfirmed`: reserved for a future expiry/cleanup lifecycle.

The legacy terms `pending_admin_review`, `accepted`, `rejected`,
`converted_to_code_agent_task`, `implemented`, and `expired` describe target
workflow concepts only. They are not the current runtime status names unless
runtime code explicitly implements them.

Future/next answer and delivery lifecycle concepts may be represented either
as statuses or separate fields:

- `answered`;
- `response_sent`;
- `needs_user_input`;
- `closed_no_answer`;
- `admin_response_text`;
- `response_sent_at`;
- `response_sent_by`;
- `response_kind`;
- `response_delivery_status`;
- `response_attempts`;
- `response_failed_reason`;
- `responded_to_request_status`.

`answered` must not mutate Product Truth automatically. `response_sent` must
mean an actual user-facing delivery path exists and succeeded.

Do not use `implemented` unless runtime behavior, tests/evals, docs, and
approval prove delivery.

## Product Truth Boundary

Human-reviewed questions can reveal a possible Product Truth gap, but they do
not change Product Truth by themselves.

Rules:

- admin answers do not make a capability `supported`;
- `reviewed_accepted` does not mean Product Truth was updated;
- `answered` does not automatically create or mutate a Product Truth entry;
- possible Product Truth updates remain manual/future review work;
- runtime support claims still require code/docs/tests/log evidence under
  `docs/Product_Truth_Layer.md`.

If an unsupported or human-reviewed request later becomes implemented, update
Product Truth, InfoHelp, eval/smoke artifacts, tests, forbidden claims, and
`PROJECT_LOG.md` in the implementation patch. Future users should get a direct
truthful answer for the implemented capability instead of unnecessary
human-review escalation.

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

The InfoHelp/admin-request preview reuses the existing `customization_request_preview` context and standard `decision:approve`, `decision:edit`, and `decision:cancel` callback tokens. Button callbacks and text/voice decisions must dispatch into the same active-state handler path.

Handler-level tests must prove that local confirmation parsers are not added.

## Storage Rules

Runtime storage exists for confirmed customization requests through
`CustomizationRequestService`. It is intentionally narrow:

- only confirmed requests are persisted by the user-facing flow;
- no row is created before explicit approve;
- saved rows are tenant-scoped by `telegram_id`;
- pre-confirmation drafts remain in FSM/temp state;
- draft identity is deterministic through preview-created `request_id`;
- duplicate approve/callback attempts must not create duplicate rows;
- the FSM draft stores redacted original text plus a raw text hash instead of
  raw unredacted original text;
- save re-applies redaction to title, summary, and original text display data;
- admin/internal reads are explicitly named and must remain admin-only;
- the Admin Response MVP stores only the latest response text/metadata on the
  existing request row;
- response text/metadata are persisted before Telegram send attempt;
- `response_attempts` increments for each confirmed send attempt;
- failed sends remain persisted as `send_failed` with a bounded failure reason;
- no automatic retry or response history table exists in MVP.

Future storage expansion remains migration-safe. Before adding new persisted
fields, status transitions, retention jobs, or conversion flows:

1. define table/filesystem shape;
2. define tenant/workspace scoping;
3. define redaction policy for original text;
4. define status transitions;
5. define admin review access;
6. define retention/expiry;
7. define backup/rollback if server data is touched;
8. update `PROJECT_LOG.md` and relevant docs.

No request storage may be cross-tenant.

## Admin Review And Response

Future admin/developer review should be able to answer:

- is the request clear?
- is it safe?
- is it already supported?
- is it duplicate?
- what inputs are missing?
- what risk level applies?
- should the user receive an answer, rejection reason, or clarification
  request?
- should this become a code-agent task?
- what acceptance criteria must be met?

Current admin review surface:

- `/customization_requests`: read-only list of the newest pending requests;
- `/customization_request <id_or_prefix>`: read-only detail view;
- `/customization_request_accept <id_or_prefix>`: status-only accept review;
- `/customization_request_reject <id_or_prefix>`: status-only reject review;
- `/customization_request_reply <id_or_prefix>`: confirmation-gated admin
  `answer` response to the original requester.

Current admin review status commands are limited to marking a confirmed pending
request as `reviewed_accepted` or `reviewed_rejected`. `reviewed_accepted`
means the request was accepted for later human consideration only. It does not
approve implementation, mutate Product Truth, convert to backlog, notify users
or admins, or create a code-agent handoff. `reviewed_rejected` records a
review decision only and does not mutate Product Truth.

Current Admin Response MVP supports:

- `answer` response kind only;
- text-only admin response body entry;
- admin preview with send/edit/cancel confirmation;
- persistence before Telegram delivery attempt;
- user-facing Telegram send to the original requester only;
- `admin_response_text`;
- `response_kind`;
- `response_sent_at`;
- `response_sent_by`;
- `response_delivery_status`;
- `response_attempts`;
- `response_failed_reason`;
- `responded_to_request_status`;
- `response_updated_at`;
- `response_id`;
- admin detail delivery observability for `not_started`, `send_pending`,
  `send_succeeded`, and `send_failed`;
- duplicate confirm protection for an already pending, already sent, or already
  failed same `response_id`;
- deterministic `send_failed` status without automatic retry when Telegram
  delivery fails.

Current runtime still does not support:

- response kind selection beyond `answer`;
- automatic user notification on accept/reject;
- clarification request delivery through `needs_user_input`;
- structured user reply thread after admin response;
- recovery command for stuck `send_pending`;
- manual retry command for failed sends;
- `delivery_unknown` manual marking;
- Product Truth mutation from answered questions.

Target admin response behavior:

- admin can provide an answer, reason, or clarification request;
- Python sends the response through the bot only after an implemented,
  confirmation-gated delivery path exists;
- confirmed response text and metadata are persisted before the Telegram send
  attempt;
- delivery result fields are updated after the send attempt succeeds or fails;
- the response copy states whether this is guidance, a rejection/explanation,
  or a clarification request;
- the response must not promise implementation or claim Product Truth changed.

Admin Response MVP persistence scope:

- `customization_requests` stores only the latest admin response metadata/text
  in MVP;
- multi-response history, threaded conversations, and structured reply chains
  are future scope;
- a later response may replace the latest-response fields only through another
  explicit admin confirmation-gated send flow;
- response history must not be inferred from overwritten latest-response
  fields.

Admin Response MVP delivery ordering:

1. Admin confirms the response preview.
2. Python persists `admin_response_text`, `response_kind`,
   `response_sent_by`, `responded_to_request_status`, increments
   `response_attempts`, and atomically claims a delivery status such as
   `send_pending`.
3. Python attempts Telegram delivery.
4. If delivery succeeds, Python sets `response_delivery_status` to
   `send_succeeded`, sets `response_sent_at`, and clears
   `response_failed_reason`.
5. If delivery fails, Python keeps the response text/metadata persisted, sets
   `response_delivery_status` to `send_failed`, stores a safe bounded failure
   reason, and does not claim user delivery.

Failed-send recovery:

- no automatic retry happens in MVP;
- failed responses remain persisted with `send_failed`;
- a future manual retry flow may reuse the persisted response text/metadata;
- retries must be explicit, admin-only, confirmation-gated, and idempotent.

Delivery observability:

- `/customization_request <id_or_prefix>` shows the latest response delivery
  state using existing `customization_requests` fields only;
- if no response metadata exists, admin detail displays computed
  `not_started`;
- `send_pending` means a response was persisted and claimed before Telegram
  delivery, but the final delivery result is unknown or still in progress;
- `send_pending` must not be described as failed or delivered;
- `send_pending` is flagged for manual investigation when it is older than 15
  minutes, `response_attempts > 0`, and `response_sent_at` is empty;
- the stuck-pending warning does not retry, mark failure, mark success, notify
  the user, or change request review status;
- `send_failed` means a send attempt failed and only a bounded
  `response_failed_reason` is shown;
- `delivery_unknown` and manual recovery commands are future scope.

MVP response kinds:

- `answer`: runtime-supported in the Admin Response MVP.

Future or constrained response kinds:

- `rejection_reason`: future unless explicit command/kind selection and tests
  are implemented;
- `informational_followup`: future unless explicit command/kind selection and
  tests are implemented;
- `accepted_for_review_note`: future unless explicit product copy and command
  behavior are implemented;
- `clarification_request`: future unless implemented as one-way outbound copy.
  If later included, it must not reopen a structured workflow, set up a user
  reply thread, or automatically move the request to `needs_user_input` unless
  that workflow is explicitly designed and tested.

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

The complete Customization Request Layer is not complete until:

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

The broader Admin Response / Human Review Loop is not complete until:

- unanswered product/support/how-to/troubleshooting questions can be submitted
  only after confirmation;
- a persisted kind/type or equivalent explicit classification exists;
- admin can answer, reject with reason, or ask for clarification;
- user receives the admin response through the bot;
- response metadata/text is persisted before send attempt and delivery result
  is updated after the attempt;
- MVP storage explicitly limits itself to latest-response metadata unless a
  separate history table/thread model is implemented;
- Product Truth is not mutated automatically;
- evals prove the closed loop.

The current partial Level 3 MVP slice satisfies the bounded preview,
confirmation-gated persistence, tenant scoping, redaction, admin list/detail,
status-only review, and one-way admin `answer` delivery subset documented in
Current Status. It does not satisfy the complete lifecycle criteria for Product
Truth conversion, backlog conversion, code-agent handoff, accept/reject
notifications, response kind selection, clarification threading, self-learning,
request expiry, retry, or implementation delivery.

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
- request is not saved before confirmation;
- bot cannot answer product question and asks to submit for admin review;
- user confirms an unanswered product/support question and it is saved;
- admin sends answer and user receives it;
- admin rejects with reason and user receives the explanation;
- admin asks for clarification and user receives the clarification request;
- out-of-domain/spam do not create a human-review item;
- possible Product Truth gap does not auto-mutate Product Truth.

The current smoke artifact is
`docs/evals/customization_request_mvp_smoke.md`. It records scenarios for the
implemented partial MVP, marks the `answer` admin response send as implemented,
keeps rejection-reason/clarification scenarios future, and explicitly lists
forbidden claims.

## No-Go Rules

Do not:

- promise implementation;
- say "Admin will implement this";
- say "This feature is now supported" unless Product Truth and runtime evidence
  prove it;
- create a request without confirmation;
- store raw sensitive transcripts as reusable knowledge;
- accept credentials/secrets in ordinary chat;
- bypass Product Truth;
- bypass admin review for high-risk work;
- route unsupported requests directly to code agents;
- call request drafting "implementation";
- call `reviewed_accepted` an implementation promise;
- claim admin/user notifications were sent when only DB storage/review status
  exists;
- say "Admin was notified" unless actual notification exists;
- say "You will definitely receive an answer" unless the response loop
  guarantees delivery;
- claim an admin response was sent when only status review exists;
- claim Product Truth, backlog, code-agent handoff, or self-learning side
  effects from request capture or review;
- say "A code agent task was created" unless that handoff exists;
- say "The bot learned this automatically";
- claim Product Truth changed because an admin answered a question;
- mark a request `implemented` without runtime delivery and verification.
