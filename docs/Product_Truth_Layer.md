# Product Truth Layer
## InfoHelp contextual recovery rollback truth (2026-08-02)

The `info_help` capability remains `partial` because the older deterministic Product Truth and bounded Unknown / Discovery / Triage foundation remains. Contextual InfoHelp Recovery V1 from PR `#63` is rolled back after confirmed interactive production regressions and must not be described as active.

The rollback removes the PR `#63` contextual recovery classifier, recent-turn context, unmatched-command recovery router, suggestion callbacks, generic recovery action dispatcher, active-FSM contextual descriptors/help, and feature-only voice/context capture. The prior unknown-input and InfoHelp behavior is authoritative again.

V2 is not implemented or planned by this rollback. Any replacement requires a revised Architecture Design Proof, explicit owner approval, real callback actor modeling, continuation-state proof, quoted-message context design, and interactive Telegram acceptance.

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

This document is a docs-first contract, with a current Python Product Truth
MVP foundation in `bot/services/product_truth.py`.

As of the current logged state:

- a Product Truth MVP registry foundation exists;
- deterministic Product Truth-backed InfoHelp fast-paths exist for selected
  conservative capability/safety topics;
- the `info_help` Product Truth status is partial, not complete Level 2;
- bounded Unknown / Discovery / Triage v1 classification exists for safe
  non-persistent responses;
- broader bounded InfoHelp resolver coverage is not complete;
- customization request creation/storage has a partial Level 3 MVP slice:
  eligible triage candidates can enter a confirmation-gated preview/save flow,
  and admins can list/detail/accept/reject requests as status-only review;
- that customization request slice is now documented as part of a broader
  Admin Response / Human Review Loop; answer-only admin response-to-user and
  admin-facing delivery observability are implemented as partial MVP slices;
- Product Truth mutation, Product Truth candidate conversion, backlog
  conversion, notifications, retry/recovery commands, self-learning, and
  code-agent handoff are not implemented by the customization request slice.

Product Truth must be derived from current code, `PROJECT_LOG.md`,
`docs/TZ_FakturaBot.md`, active contract docs, and focused evidence in tests.

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
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
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

## Product Truth vs Unknown Discovery

Product Truth answers what is known about registered product capabilities.
It is not the whole discovery layer for every user utterance.

An unknown `capability_id` lookup is not a final product answer. It means
Product Truth has no verified capability record for that input. When routing,
authorization, and active state allow it, the next safe step is Unknown /
Discovery / Triage, not registry guessing.

The triage layer may classify the user's input as one of these Python-owned
classes:

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

Triage classes are not Product Truth statuses. They must never mark anything
as `supported`, create new capability IDs, or imply runtime support. They only
decide the safe next response path: render known Product Truth, ask a
clarifying question, politely reject out-of-domain input, ignore/block
spam/noise safely, or offer to prepare a future request / human-review item
under the Customization Request Layer.

The current Unknown / Discovery / Triage runtime is a bounded v1 foundation
only: it may classify inputs and, for eligible customization/admin/product
truth gap candidates, enter the confirmation-gated preview/save flow. It must
not notify admins, send admin responses to users, create Product Truth entries,
or claim complete Level 2 InfoHelp.

## Capability Status Model

Every user-facing capability answer must separate:

1. `primary_status`: availability truth.
2. flags/context: safety, setup, admin, credential, and account-state facts
   that modify the answer or gate the next step.

Allowed `primary_status` values:

- `supported`;
- `partial`;
- `planned`;
- `unsupported`;
- `unknown`.

Allowed flags/context include:

- `dangerous`;
- `requires_setup`;
- `requires_admin`;
- `requires_external_credentials`.

Flags/context must not be treated as primary support statuses. For example,
real outbound email can be `unsupported` with
`requires_external_credentials=true`; deleting user data can be `supported`
with `dangerous=true`; invoice creation can be `supported` with account-level
`requires_setup` when the user has not completed required setup.

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

`unknown` at Product Truth level must not collapse all inputs into the same
fallback. Unknown may mean a new business feature request, an admin/developer
request, out-of-domain text, spam/noise, smalltalk, unclear wording, or a
possible future Product Truth candidate. That distinction belongs to the
separate triage layer and must remain side-effect free.

## Flags And Context

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
primary_status
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
Primary status: supported
Account context: requires_setup when supplier profile or service alias is
missing
```

## Response Policy

Every Product Truth answer should produce:

1. primary status plus flags/context;
2. short direct answer;
3. current limitation/setup condition;
4. safe next step;
5. linked action or customization option when allowed.

Example for a setup-gated partial integration:

```text
Primary status: partial
Flags/context: requires_setup, requires_admin, requires_external_credentials
Answer: One configured owner OAuth connection can archive selected documents.
Limit: upload is asynchronous. New receipts and incoming invoices use the
owning workspace folder; local save does not prove Drive upload success.
Next step: an admin configures the owner OAuth connection and worker.
```

## Forbidden Claims

The registry must explicitly block claims such as:

- "I can send invoices by email" unless real outbound email is implemented;
- "I can store invoices on Google Drive" unless integration and credentials are
  implemented;
- "I can send SMS reminders" unless provider, consent, and sending flow exist;
- "I created a support request" unless request storage and confirmation exist;
- "Admin will answer you" unless response delivery is guaranteed by runtime;
- "Product Truth was updated" because an admin answered a question;
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
- explain the primary status plus relevant flags/context;
- offer linked safe actions;
- offer customization requests where allowed.

InfoHelp must not:

- answer from memory alone;
- use roadmap docs as runtime proof;
- override dangerous/setup/admin flags;
- create side effects from informational questions.

If InfoHelp cannot map wording to a known `capability_id` or known topic, it
must not behave like a simple registry search engine. It should pass the input
to Unknown / Discovery / Triage only when authorization, active FSM ownership,
and routing rules allow that step.

Correct order:

1. authorization gate;
2. active FSM state wins;
3. clear direct executable action resolver;
4. known Product Truth capability/topic resolver;
5. Unknown / Discovery / Triage resolver;
6. Python-controlled outcome.

Python-controlled outcomes include rendering a known Product Truth answer,
asking clarification, politely rejecting out-of-domain input, safely ignoring
spam/abuse, offering to prepare a feature/customization/human-review item, or
saving/sending an admin response only after explicit confirmation in an
implemented flow.

## Interaction With Customization Requests And Human Review

Customization requests and human-review items are allowed when:

- the capability is `unsupported`, `partial`, `planned`, `unknown`, or
  account-specific;
- Product Truth marks `customization_allowed = true`;
- the request is safe to capture;
- the user confirms the draft;
- storage/admin review path exists.

They are not allowed when:

- the user asks for a destructive confirmation alias;
- the request would bypass access control;
- the request needs secrets/credentials that the bot cannot safely collect;
- the product has no implemented request storage/admin review path but the bot
  would imply one exists.

Answered user questions may reveal a possible Product Truth gap, but Product
Truth is not mutated automatically. An admin answer does not make a capability
supported. Product Truth updates remain manual/future review work and still
require evidence plus a log entry.

## Registry Lifecycle

Adding or changing a capability entry requires:

1. evidence from code/docs/logs;
2. primary status classification plus flags/context review;
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
- human-review offers depend on request-layer availability;
- admin answers do not mutate Product Truth automatically;
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
- unknown but plausible business feature request does not fall to a dumb menu
  fallback;
- out-of-domain question does not become a customization request;
- spam/noise does not create an admin request;
- smalltalk does not trigger business action;
- direct action still wins when clear;
- voice transcript follows the same state-aware path;
- unanswered product/support question can be submitted for human review only
  after confirmation;
- future admin response delivery does not mutate Product Truth.

## Current Known Truth Examples

These are documentation-level examples and must still be checked against
current code before runtime claims:

- invoice creation from text/voice: supported with bounded extraction and
  confirmation;
- invoice exact numeric/date/identifier values by voice: partial/text-only for
  precision-sensitive fields;
- invoice analytics over saved outgoing invoices: partial read-only pilot over
  the current supplier's persisted outgoing invoice rows only, with Slovak
  business answers by default, Python-normalized bot payment status rather
  than raw invoice lifecycle status, unpaid/not-paid wording that includes both
  pending and overdue bot states, and an internal deterministic calendar-year
  count/total fast path for simple yearly questions;
- `mark_existing_invoice_paid`: supported MVP. A user can mark one saved outgoing invoice as paid/uhradena after supplier-scoped lookup and explicit confirmation. This stores bot-local payment/follow-up state; when owner OAuth Drive archive is configured, it may enqueue the existing local PDF for archive-worker upload. It is not bank matching or bank confirmation.
- yearly invoice summary: supported only as an internal deterministic strategy
  under `invoice_analytics`, not as a competing user-facing top-level action;
- receipt/incoming-invoice categories: partial; controlled category candidates,
  workspace category creation, Python validation, user confirmation, and
  confirmed metadata snapshots exist only inside the accounting Document Intake
  preview flow, not as a standalone top-level action or broad category manager;
- accounting-document analytics: partial read-only pilot over confirmed
  receipts/bloceky and incoming invoices/prijate faktury in the current
  workspace through `accounting_document_analytics`; it may answer bounded
  counts, sums, vendor/category/month/document-type grouping, comparisons,
  limited lists, averages, and top rankings from sanitized metadata only;
- receipt/blocek analytics: partial as a receipt-focused Product Truth alias of
  `accounting_document_analytics`, not the upload/add receipt flow;
- incoming invoice analytics: partial only inside the same
  `accounting_document_analytics` runtime and only for confirmed incoming
  invoice metadata in the current workspace;
- bank/cashflow/VAT/tax/full accounting analytics: unsupported unless a
  separate implementation with data sources, validation rules, Product Truth,
  and tests proves otherwise;
- invoice PDF generation: supported in current invoice flow;
- Google Drive invoice storage/archive: partial owner OAuth runtime integration when configured; not full SaaS/per-client Drive sync;
- SMS sending: unsupported unless later runtime code proves otherwise;
- real outbound invoice email sending: unsupported unless later runtime code
  proves otherwise;
- customization request creation/storage: partial Level 3 MVP slice for
  confirmation-gated capture plus admin list/detail/status review;
- admin response-to-user from bot runtime: partial answer-only MVP with
  confirmation-gated delivery and latest response metadata;
- admin response delivery observability: partial admin detail view for
  `not_started`, `send_pending`, `send_succeeded`, and `send_failed`, with no
  retry/recovery command;
- code-agent handoff from bot runtime: not implemented unless later runtime
  code proves otherwise.

## Product Truth Synchronization Required For Runtime Changes

Every user-facing runtime change must update Product Truth in the same patch.
This includes top-level actions, admin commands, integrations, support
surfaces, human-review flows, setup-dependent features, and removed/disabled
features.

Rules:

- if a feature becomes implemented, update its status from `unsupported`,
  `planned`, or `unknown` to `supported` or `partial` according to evidence;
- if only part of a feature is implemented, use `partial` and list the exact
  supported subset and current limitations;
- if setup, credentials, dangerous behavior, or admin action is required, set
  the corresponding flags/context (`requires_setup`, `requires_admin`,
  `requires_external_credentials`, `dangerous`);
- if a feature is removed, disabled, or blocked by a rollout decision, downgrade
  Product Truth in the same patch;
- every integration must have forbidden claims for common overstatements,
  hidden side effects, automatic sync, guaranteed delivery, and credential
  assumptions;
- InfoHelp, eval artifacts, tests, and `PROJECT_LOG.md` must be synchronized
  with the Product Truth record.

Example: Google Drive invoice storage.

Before implementation:

- status: `unsupported` or `planned`;
- limitations: no runtime Drive sync/storage;
- flags: external credentials required if future integration would need them;
- forbidden claims: "Google Drive sync is active", "I saved this invoice to
  Drive".

After a minimal implementation:

- status: `partial`;
- limitations: for example, "only confirmed invoice PDFs sync", "no receipt
  sync", "no folder picker", or "manual credential setup required" unless those
  behaviors are actually implemented;
- flags: `requires_external_credentials` and `requires_setup` stay true until
  runtime setup is proven;
- InfoHelp must explain "Vieš ukladať faktúry na Google Drive?" and "Ako
  zapnem Google Drive?";
- evals/tests must prove the supported path and that unsupported sync claims
  are refused.

## No-Go Rules

Do not:

- use LLM confidence as Product Truth;
- answer capability questions only with `/menu`;
- mark a roadmap idea as `supported`;
- hide partial limits;
- ignore account setup state;
- skip dangerous/admin/external-credential flags;
- offer customization request storage if it does not exist;
- claim admin response-to-user if only status review exists;
- claim guaranteed admin response delivery or automatic retry;
- update Product Truth without evidence and log entry;
- let learned aliases bypass Product Truth.

### Current Google Drive Product Truth - 2026-08-02

`google_drive_invoice_storage` and
`google_drive_invoice_archive_after_due_date` are `partial`, not fully
`supported`.

The implemented slice is owner OAuth archive. The controlled production pilot
was reauthorized on 2026-08-02 and one queued bank-statement job plus its
authoritative archive state reached `uploaded`. This is deployment evidence,
not a static claim that every account or deployment is connected.

- requires admin/server setup and external Google OAuth credentials;
- uses one owner Google account, one encrypted refresh token, and one configured personal My Drive root folder;
- uploads consume the owner Google account quota;
- uploads confirmed receipts, incoming invoice originals, and selected outgoing
  invoice PDFs through the archive worker;
- persists immutable workspace-specific targets for newly queued outgoing
  invoice PDFs, confirmed receipts, and incoming invoices below each workspace
  `drive_folder_name`;
- does not migrate or move existing remote Drive files automatically;
- enqueues outgoing invoice PDFs only after a control event such as mark-paid;
- keeps local invoice PDFs; no invoice PDF deletion is implemented;
- keeps local accounting metadata JSON;
- may delete only the accounting original after `uploaded` when configured;
- keeps accounting originals for pending or failed uploads;
- keeps local files on failed/not-configured upload;
- service-account mode is unsupported for personal My Drive unless a future Google Workspace/Shared Drive setup is explicitly configured.

Forbidden claims now include:

- per-client OAuth Drive storage is active;
- full SaaS Google Drive sync is active;
- service-account mode works with personal My Drive;
- invoice PDFs are deleted after upload;
- upload succeeded before the worker state is `uploaded`;
- marking paid means bank-confirmed settlement.

InfoHelp rendering rule:

- `requires_external_credentials=true` describes a capability dependency; it
  must not be rendered as "this account is not configured" without observed
  account context;
- static Gmail/Drive InfoHelp must not invent `requires_admin` or other live
  integration state when no account context was supplied;
- current connection state is read through `/google_drive_status` or
  `/gmail_status`; generic capability guidance remains `partial` and keeps all
  owner-only, asynchronous, and no-SaaS limitations.

### Current OfficeFlow Work-Time Product Truth - 2026-07-02

`work_time_tracking` is `partial`, not fully `supported`.

The implemented slice is a simple tenant/user-scoped work-time MVP:

- top-level canonical actions: `open_work_day`, `close_work_day`, `add_work_time_entry`, `generate_work_time_report`, `update_work_time_lunch_break`, and `delete_work_time_month`;
- authorized users can open a work day, close it with a preview-confirmed time/duration, add a preview-confirmed manual range, configure a fixed lunch-break deduction, generate a monthly `.xlsx` report, and delete one selected month of stored records after destructive preview confirmation;
- the first monthly report asks once whether lunch break should be deducted; later lunch-break changes are preview-confirmed and can be disabled;
- persisted state is additive SQLite tables `work_time_days`, `work_time_events`, and `work_time_settings`, scoped by `telegram_id`; existing rows are not rewritten;
- `work_time_days` stores gross minutes, lunch-break snapshots, net-duration overrides, and close input mode where available; legacy rows remain readable;
- MVP supports one interval per user/day;
- exact time values are Python-parsed, previewed, and saved only after confirmation;
- reports include all days in the month, Sunday highlighting, and net total hours; explicit start/end rows subtract the currently configured lunch break, while duration-only rows keep the confirmed net duration stable;
- `delete_work_time_month` removes DB work-time records only; generated Excel reports are on-demand artifacts, not canonical stored attendance data.

Forbidden claims include:

- payroll or salary calculation is implemented;
- legal HR attendance compliance is implemented;
- multi-employee attendance administration is implemented;
- payroll/accounting export is implemented;
- the bot automatically detects actual work time;
- lunch-break settings are payroll or legal HR compliance calculations;
- deleting a work-time month deletes payroll/legal HR records;
- deleting a month removes generated Excel reports as canonical records;
- the generated Excel report is an official payroll/legal HR document.

### Contacts: official Slovak registry lookup and optional IBAN - 2026-07-17 / 2026-07-28

`contacts` remains `partial`: manual and document-assisted intake are available. Official-registry lookup remains disabled by default in code and deployment-configurable, but production has enabled it for every authorized user with an active workspace/profile as of 2026-07-28 by setting the parent gate on and leaving the pilot workspace set empty.

Supported when enabled: search an official Slovak company by name or IČO; show at most the configured bounded candidates; require user selection when multiple candidates exist; prefill only official name/IČO/address/status fields actually returned; type missing required DIČ; optionally add or skip email, contact IBAN, and contact person; fall back to manual/PDF intake; and insert/update only after explicit final confirmation.

### Contacts: search quality and staged tax enrichment - 2026-07-18

`contacts` remains `partial`. When the parent RPO gate is enabled, exact normalized names collapse weak provider noise; multiple exact legal entities remain selectable; bounded spacing/one-edit suggestions such as `ZE VS` or `Empbau` always require explicit selection. A substring inside a longer surname is not exact identity evidence.

RPO supplies official identity/address/lifecycle fields. A separate Financial Administration provider boundary uses key-authenticated mappings verified on 2026-07-18: income list `ds_dsrdp` (`ico` -> `dic`) and DPH list `ds_dphs` (`ico` -> directly returned `ic_dph`). Configuration is disabled by default in code and requires external credentials plus the parent RPO gate. Production has both providers enabled globally for authorized active workspaces as of 2026-07-28; deployment setup does not remove provider failure handling or user confirmation. When disabled, unavailable, invalid, ambiguous, or missing an exact DIČ row, typed DIČ remains mandatory.

Forbidden claims:

- a suggested company is an exact match or can be auto-selected;
- Financial Administration enrichment is active merely because code/config placeholders exist;
- IČ DPH can be generated as `SK + DIČ`;
- absence from an unavailable or unverified VAT response proves non-VAT status;
- either official source is guaranteed real-time or always available.

Limitations and forbidden claims: official source availability and freshness are external; source fields may be absent; email, IBAN, and contact person are normally manual; IČ DPH is not inferred; no commercial-registry scraping, automatic contact creation from idle attachments, email/IBAN/person discovery, foreign registry, or automatic invoice creation is supported. Interactive registry search never auto-saves. The separately gated periodic monitor is the only supported background contact check and still requires explicit proposal-button confirmation before a contact update. A shown registry preview is not a saved contact. Registry import never silently overwrites a same-name/different-IČO row.

### Runtime issue intake - 2026-07-28

`runtime_issue_intake` is `supported`, requires an administrator, and is available
through `/issue`, bounded natural text, and bounded voice. It stores one sanitized
observed problem with a stable issue ID. The same ephemeral capture owner is used
from idle and from an existing business FSM, whose protected state and data remain
unchanged.

Forbidden claims: a stored report confirms a bug; performs diagnosis,
classification, repair, maintenance, merge, deployment, restart, or rollback;
promises whether or when a fix will happen; or authorizes Stage 2 autorepair.
Automatic maintenance and autorepair remain unavailable.


### Contacts: periodic official-registry monitoring - 2026-07-29

`contacts` remains `partial`, `requires_setup`, and `requires_external_credentials`. A disabled-by-default deterministic monitor can check eligible workspace-owned contacts with an exact eight-digit IČO every 14 days at 03:00 `Europe/Bratislava`. Active owner authorization is mandatory. The monitor is independent of active-profile selection and may maintain a persisted inactive workspace/membership without reactivating it or exposing it to interactive flows. It compares official name, legal address, DIČ, and IČ DPH, then notifies the workspace owner and asks whether to update the saved contact. No contact field changes before explicit button confirmation.

When the same authorized owner saved the same company in several workspaces, formatting-equivalent IČO values are canonicalized. Pending proposals with the same owner, canonical IČO, and identical official target snapshot are shown as one group and one confirmation applies all explicitly grouped contact rows atomically. A different actor is never grouped, and any stale, unauthorized, expired, or conflicting group member prevents every contact write in that group.

Missing or failed tax data never clears saved DIČ/IČ DPH. Email, IBAN, contact person, contract data, invoice rows, invoice items, `pdf_path`, and existing PDF files are outside the update. Already issued invoices are never rewritten by this monitor.

Forbidden claims: monitoring is active merely because code exists; registry data is always current; every contact can be checked without valid IČO; updates happen automatically; declining changes invoices; or approved contact updates rewrite previously issued invoices/PDFs.

### Runtime issue explicit prefixes - 2026-07-31

For an authorized administrator, text or STT beginning with the first
meaningful token `проблема`, `помилка`, `баг`, `chyba`, `problem`, `bug`, or
`error` deterministically enters the existing runtime issue intake and bypasses
business action routing. The complete original report is stored through the
same sanitized owner; a bare marker requests a complete description.

For an authorized non-admin user while idle, the same prefix opens the
existing confirmation-gated admin-review request preview. This does not create
an administrator runtime issue, notify an administrator, or persist anything
before confirmation. Active non-admin FSM ownership is not interrupted.

## Exact InfoHelp Semantic Validation - 2026-08-02

Contextual InfoHelp receives a compact safe view derived from the existing Product Truth registry. The model is never the authority: Python performs the final capability lookup and validates runtime-owner presence after parsing the model output.

Support for one business object does not transfer to another object with the same verb. An executable/offerable action requires an exact registered `domain_id + object_kind + operation_id` match, applicable `supported` or `partial` Product Truth, a real Python owner, actor/workspace validation, required slots or a real continuation FSM, and all existing confirmation gates. No exact match is `unsupported` or a new feature; it is never a nearest-action substitution. Capability questions are answer-only and account-wide deletion is never suggested by InfoHelp.
