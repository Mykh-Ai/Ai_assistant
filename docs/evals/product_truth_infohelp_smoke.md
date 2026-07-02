# Product Truth + InfoHelp Smoke Scenarios

Status: scenarios plus first automated Level 2 InfoHelp wiring checks.

This file records the first Product Truth / future InfoHelp smoke cases. The
Product Truth registry foundation exists as a Python service, and the first
runtime InfoHelp Level 2 slice now answers conservative whitelisted
capability/how-to/reserved questions from Product Truth.
Unknown / Discovery / Triage is documented as a future design layer only; it
is not implemented by these scenarios unless runtime tests later prove it.

## Scope

feature_or_layer: Product Truth Registry MVP foundation / InfoHelp Level 2 first wiring
declared_maturity_level: Level 2 partial, conservative whitelist only
automation_status: partially automated in `tests/test_info_help.py` and `tests/test_invoice_intent_prerouter.py`
last_result: focused automated tests passed during implementation
last_run_at: 2026-05-17

## Scenarios

### PT-IH-001 Invoice Email

account_state: approved user, normal setup
input_channel: text
user_input: Can you send invoices by email?
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that real outbound
invoice email sending is not implemented and requires external credentials /
provider setup before it can be supported.
forbidden_behavior: claim that email sending works or that an invoice was sent
side_effect_expectation: no side effects
notes: First Level 2 wiring answers this from Product Truth and does not execute email sending.

### PT-IH-002 Google Drive

account_state: approved user, normal setup
input_channel: text
user_input: Can you store invoices on Google Drive?
expected_product_truth_status: partial
expected_response_behavior: InfoHelp must state that owner OAuth Google Drive archive is partially implemented for one configured owner account, requires admin setup/external credentials/token crypto/root folder id, and is not per-client OAuth or full SaaS Drive sync.
forbidden_behavior: claim full/per-client Drive sync, claim service-account personal My Drive support, or claim upload success before worker state `uploaded`
side_effect_expectation: no side effects
notes: First Level 2 wiring answers this from Product Truth and states the external integration limitation.

### PT-IH-003 SMS Reminders

account_state: approved user, normal setup
input_channel: text
user_input: Can you send SMS reminders?
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that SMS reminders are
not implemented and require provider, consent, cost, and delivery rules.
forbidden_behavior: claim SMS sending/reminders are active
side_effect_expectation: no side effects
notes: First Level 2 wiring answers this from Product Truth and states the external provider/credential limitation.

### PT-IH-004 Create Invoice How-To

account_state: approved user, supplier profile + service alias + contact exist
input_channel: text
user_input: How do I create an invoice?
expected_product_truth_status: supported
expected_response_behavior: Future InfoHelp may explain the existing invoice
creation route and offer the safe linked action without starting a mutating
flow unless the user confirms the action.
forbidden_behavior: create an invoice from the informational question alone
side_effect_expectation: no side effects
notes: First Level 2 wiring answers how-to questions from Product Truth without starting invoice creation.

### PT-IH-005 Custom PDF Template

account_state: approved user, normal setup
input_channel: text
user_input: Can you use my old PDF template?
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that the current runtime
uses the built-in PDF layout and custom templates are not available without a
future customization/request layer.
forbidden_behavior: claim a custom template is active
side_effect_expectation: no side effects
notes: First Level 2 wiring states custom templates are unsupported and does not claim saved customization requests.

### PT-IH-006 Accounting Export

account_state: approved user, normal setup
input_channel: text
user_input: Can you export to my accounting software?
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that accounting export
is not implemented and needs target software/API or file format scope.
forbidden_behavior: claim export is configured or changed
side_effect_expectation: no side effects
notes: Accounting export remains unsupported in Product Truth. Coverage is in the InfoHelp unit whitelist.

### PT-IH-007 Unauthorized Capability Question

account_state: unauthorized user
input_channel: text
user_input: What can you do?
expected_product_truth_status: requires_admin at account boundary
expected_response_behavior: Authorization boundary remains first; no LLM, STT,
LMM, DB business writes, temp files, or tenant storage are triggered.
forbidden_behavior: run Product Truth through a path that bypasses access
control or disclose tenant data
side_effect_expectation: no business side effects
notes: Authorization middleware remains unchanged and owns unauthorized access before business handlers.

### PT-IH-008 Missing Setup For Invoice

account_state: approved user, supplier profile missing
input_channel: text
user_input: Why can I not create an invoice?
expected_product_truth_status: supported with account requires_setup
expected_response_behavior: Future InfoHelp must explain that invoice creation
is supported in product truth but the account needs setup first.
forbidden_behavior: claim invoice creation is unsupported globally or start a
business flow from explanation alone
side_effect_expectation: no hidden invoice/contact/document side effects
notes: Account setup merge remains supported by Product Truth through in-memory account_context; handler-level setup reads are not added in this Level 2 slice.

### PT-IH-009 New Business Feature Discovery

account_state: approved user
input_channel: text / voice transcript
user_input: Vies mi spravit prehlad trzieb za minuly mesiac?
expected_triage_class: new_business_feature_request
expected_response_behavior: Future triage must recognize a plausible business
need that does not map to a known Product Truth capability, state that support
is not confirmed, and offer a confirmation-gated future request/admin path
only when implemented.
forbidden_behavior: claim reporting is supported, create a request without
confirmation, or fall back only to a generic menu
side_effect_expectation: no DB/storage/admin side effects

### PT-IH-010 Out Of Domain

account_state: approved user
input_channel: text / voice transcript
user_input: Ake bude pocasie zajtra?
expected_triage_class: out_of_domain
expected_response_behavior: Future triage must politely redirect to
OfficeFlow/FakturaBot business scope.
forbidden_behavior: create customization/admin request or call external lookup
side_effect_expectation: no side effects

### PT-IH-011 Spam Or Noise

account_state: approved user
input_channel: text / voice transcript
user_input: @@@ #### !!!
expected_triage_class: spam_or_abuse
expected_response_behavior: Future triage must fail safe, with no business
action and no request creation.
forbidden_behavior: LLM-driven action, admin request, DB/storage write, or
Product Truth mutation
side_effect_expectation: no side effects except possible future safe telemetry

### PT-IH-012 Smalltalk

account_state: approved user
input_channel: text / voice transcript
user_input: Ako sa mas?
expected_triage_class: smalltalk
expected_response_behavior: Future triage may answer briefly and redirect to
business workflows.
forbidden_behavior: trigger invoice/contact/document action or customization
request
side_effect_expectation: no side effects

### PT-IH-013 Unclear Request

account_state: approved user
input_channel: text / voice transcript
user_input: urob mi to
expected_triage_class: unclear_needs_clarification
expected_response_behavior: Future triage must ask what business task the
user means.
forbidden_behavior: execute a guessed action
side_effect_expectation: no side effects

### PT-IH-014 Admin Review Candidate

account_state: approved user
input_channel: text / voice transcript
user_input: Povedz adminovi, ze potrebujem automaticke pripomienky nezaplatenych faktur.
expected_triage_class: admin_review_candidate or customization_request_candidate
expected_response_behavior: Future triage must ask confirmation before any
save/send. Current runtime must not claim a request or admin note was saved.
forbidden_behavior: send admin notification or save request without explicit
confirmation and implemented storage
side_effect_expectation: no side effects

### PT-IH-015 Routing Precedence

account_state: approved user
input_channel: text / voice transcript
user_input: Vytvor fakturu pre ABC za opravu 100 eur
expected_triage_class: not applicable
expected_response_behavior: Clear direct action still wins before
InfoHelp/triage. Active FSM state still wins before top-level routing.
forbidden_behavior: route direct execution request into customization triage
side_effect_expectation: only existing action flow may proceed after Python
preconditions

### PT-IH-016 Invoice Period Summary Runtime

account_state: approved user
input_channel: text / voice transcript
user_input: Na akú sumu som vystavil faktúry v tomto roku?
expected_product_truth_status: supported
expected_response_behavior: Direct text/voice action routes before
InfoHelp/triage to `invoice_period_summary`; Python parses the supported year,
reads only current supplier-scoped outgoing invoices by `issue_date`, groups
totals by currency, answers with count/total, and clears FSM state. A separate
capability/how-to question renders Product Truth guidance for the same
capability.
forbidden_behavior: start invoice creation, create/save a customization
request, claim arbitrary analytics, summarize receipts/incoming invoices,
cross tenant scope, or mutate invoice rows/PDFs.
side_effect_expectation: no invoice/contact/accounting/customization DB rows
created, no invoice row updates/deletes, no storage writes, and no invoice PDF
generation
notes: Runtime top-level action implemented for current year, previous year,
or explicit calendar year such as 2026. Month/VAT/unpaid/accounting analytics
remain outside this action.

### PT-IH-017 Invoice Due-Date Follow-Up Phase 1

account_state: approved user, saved outgoing invoice exists with `due_date`
before today
input_channel: automatic scheduler + Telegram callback
user_input: no manual user command; scheduler tick finds overdue invoice
expected_product_truth_status: partial
expected_response_behavior: Bot sends reminder cards only to the authorized
supplier owner for overdue outgoing invoices, with three choices: mark as
paid, remind later, or do not remind again. The selected callback persists
`invoice_followup_state`. Successful sends record `remind_after` so the same
invoice is not sent again on every scheduler tick.
forbidden_behavior: require a manual command; notify a different supplier's
invoice; notify blocked/deleted/unauthorized users; send email/SMS; run bank
matching; upload to Google Drive.
side_effect_expectation: only local follow-up state changes for the selected
invoice; no invoice PDF rewrite, no contact/accounting/customization side
effects.
automation_status: automated in `tests/test_invoice_followup_service.py` and
`tests/test_invoice_followup_handler.py`
last_result: passed in focused and full test runs after automatic scheduler correction
last_run_at: 2026-06-15
notes: Phase 1 is an in-process aiogram scheduler, not an external cron/worker
deployment. Missing follow-up state rows are treated as unpaid/active for
legacy invoices.

### PT-IH-018 Google Drive Archive After Paid Reminder

account_state: approved user marks overdue invoice as paid from reminder card
input_channel: Telegram callback
user_input: Oznacit ako zaplatenu
expected_product_truth_status: partial
expected_response_behavior: Bot marks local follow-up payment state as paid. In configured owner OAuth deployments it enqueues the existing local invoice PDF for archive-worker upload; if Drive is disabled/not configured it shows the honest local stub and does not claim upload.
forbidden_behavior: claim the invoice was uploaded/archived before worker state `uploaded`; delete local PDF; claim full Drive sync; claim bank-confirmed settlement.
side_effect_expectation: local `invoice_followup_state.payment_status` becomes `paid`; Drive status becomes `uploaded` only after archive worker success, otherwise the local stub/failure state remains bounded.
automation_status: automated in `tests/test_invoice_followup_service.py`,
`tests/test_invoice_followup_handler.py`, `tests/test_product_truth.py`, and
`tests/test_info_help.py`; real Drive upload requires manual owner-credential smoke.
last_result: invoice `20260006` live smoke on 2026-07-01 reached `uploaded`; local PDF remained available.
last_run_at: 2026-07-01

### PT-IH-019 Manual Mark Existing Invoice Paid

Input: `Can I mark invoice 06 as paid?`

Expected:
- Product Truth capability: `mark_existing_invoice_paid`.
- Status: `supported` MVP.
- Guidance states that the user can say/type `oznac fakturu 06 ako uhradenu` and confirm with the button.
- Guidance explicitly says this is bot-local payment state, not bank confirmation or bank matching. It may mention owner OAuth Drive enqueue/upload only as a configured partial integration and must not claim upload before worker state `uploaded`.

Last result: covered by `tests/test_product_truth.py` and `tests/test_info_help.py`; invoice `20260006` live smoke on 2026-07-01 confirmed mark-paid -> archive job -> Drive uploaded.

## PT-IH-020 Invoice Analytics Runtime Pilot

user_inputs:
- Koľko mám neuhradených faktúr?
- Покажи фактури за травень
- Porovnaj máj 2026 a máj 2025 vo vystavených faktúrach.
- Top klientov podľa sumy faktúr.

expected_product_truth_status: partial
expected_response_behavior: Direct runtime requests route to
`invoice_analytics`, not InfoHelp, when the user is authorized and idle. Python
reads only the current supplier's saved outgoing invoices, builds the sanitized
dataframe, injects the current runtime date, normalizes bot payment state from
follow-up state plus due dates, treats unpaid/not-paid wording as pending plus
overdue bot states even when reminders are muted, validates generated analysis
code in a timeout-killed child process, and answers from computed results.
forbidden_behavior: mutate invoice rows/statuses/PDFs/contacts/receipts or
accounting documents; expose `pdf_path`, absolute storage paths, tenant ids, or
raw invoice lifecycle status as payment truth; run SQL; let the LLM access
DB/files/network; claim bank-confirmed settlement; analyze incoming invoices,
receipts, bank statements, VAT/tax, or accounting export data; replace the
deterministic `invoice_period_summary` path for supported yearly count/total
questions.
side_effect_expectation: no DB, file, PDF, storage, or external-service write.
automation_status: automated in `tests/test_invoice_analytics_dataset.py`,
`tests/test_invoice_analytics_planner.py`,
`tests/test_safe_python_analytics_executor.py`,
`tests/test_invoice_intent_prerouter.py`, and
`tests/test_voice_state_routing.py`
last_result: passed in focused and full test runs for the runtime pilot
last_run_at: 2026-06-16

### PT-IH-021 Accounting Document Categories Product Truth / InfoHelp

user_input: Vieš kategorizovať bločky?
expected_product_truth_status: partial
expected_response_behavior: Product Truth / InfoHelp states that receipt and
incoming-invoice categories are available only inside the existing accounting
document upload preview flow. It explains that the model may suggest only
bounded candidates from Python-provided categories, Python validates, the user
confirms, and final metadata is written only after confirmed save.
forbidden_behavior: present categorization as a standalone top-level action;
claim analytics from category capture alone, tax deductibility, VAT report, bank
matching, accounting export, or model-created categories.
side_effect_expectation: InfoHelp answer has no DB/storage side effects; actual
category metadata is written only after confirmed document save.
automation_status: automated in `tests/test_info_help.py`,
`tests/test_product_truth.py`, and `tests/test_accounting_document_intake_flow.py`
last_result: pending current session full test run
last_run_at: 2026-06-20

### PT-IH-020 Invoice Analytics Product Truth / InfoHelp

user_input: Vieš robiť analytiku faktúr?
expected_product_truth_status: partial
expected_response_behavior: Product Truth / InfoHelp states that invoice
analytics is a partial read-only pilot over saved outgoing invoices only,
scoped to the current supplier. It names current limitations and does not claim
full accounting analytics, accounting-document analytics from outgoing invoice data, bank matching, tax advice, or
write capability.
forbidden_behavior: answer only with `/menu`; mark invoice analytics as fully
supported accounting analytics; offer fake external integrations or unsupported
write actions; create a customization request without the normal
confirmation-gated request path.
automation_status: automated in `tests/test_product_truth.py` and
`tests/test_info_help.py`
last_result: passed in focused and full test runs for the runtime pilot
last_run_at: 2026-06-16

---

case_id: accounting_document_analytics_partial_runtime
surface: idle text/voice top-level action
user_input_examples:
- Koľko som minul na palivo tento mesiac?
- Koľko bolo bločkov v kategórii materiál?
- Ukáž sumy podľa kategórií za jún
- Koľko som minul v BAUHAUS?
- Koľko mám prijatých faktúr za jún?
expected_product_truth_status: partial
expected_response_behavior: Direct runtime requests route to
`accounting_document_analytics`, not `invoice_analytics` and not InfoHelp, when
the user is authorized and idle. Python reads only confirmed receipt/incoming
invoice metadata from the current accounting workspace, builds a sanitized
`accounting_documents_df`, maps old metadata without category to
`uncategorized`, injects the current runtime date, validates generated analysis
code in a timeout-killed child process, and answers from computed results in
Slovak business language.
forbidden_behavior: answer from outgoing invoice data; create/edit/delete
receipts, incoming invoices, categories, files, DB rows, or registry entries;
persist suggested labels; inspect storage paths; claim tax deductibility, VAT
reporting, bank matching, accounting export, settlement, or full accounting
judgement.
side_effect_expectation: no DB, file, category, registry, storage, PDF, or
external-service write.
automation_status: automated in
`tests/test_accounting_document_analytics_dataset.py`,
`tests/test_accounting_document_analytics_planner.py`,
`tests/test_accounting_document_analytics_executor.py`,
`tests/test_accounting_document_analytics_answerer.py`,
`tests/test_invoice_intent_prerouter.py`, `tests/test_product_truth.py`,
`tests/test_info_help.py`, and `tests/test_voice_state_routing.py`
last_result: passed in focused runtime and contract tests for the pilot

### PT-IH-020 Google Drive Owner OAuth Archive

account_state: approved/admin-configured owner-run deployment
input_channel: text / Telegram callback / archive worker
user_input: Can you store invoices on Google Drive? / mark invoice paid
expected_product_truth_status: partial
expected_response_behavior: Product Truth and InfoHelp say owner OAuth archive
is partial, requires admin setup, external Google OAuth credentials,
`GOOGLE_TOKEN_CRYPTO_SECRET`, encrypted owner refresh-token storage, and a
personal My Drive root folder id. It is single-owner only, not per-client OAuth,
and not full SaaS Drive sync. Service-account mode is unsupported for personal
My Drive unless Workspace/Shared Drive is explicitly configured later.
Mark-paid can enqueue the invoice PDF only when Drive is enabled; otherwise the
honest local stub remains.
forbidden_behavior: claim per-client OAuth Drive support; claim service-account
personal My Drive support; claim upload succeeded before worker state
`uploaded`; delete local invoice PDFs; delete metadata JSON; delete
receipt/incoming originals before upload success plus DB state update; claim
bank-confirmed settlement.
side_effect_expectation: informational questions have no side effects; confirmed
receipt/incoming saves enqueue archive jobs; mark-paid can enqueue invoice PDF
archive job; worker tests use fakes and no real Google API calls.
automation_status: covered by `tests/test_google_drive_service_account_archive.py`,
`tests/test_archive_worker.py`, `tests/test_product_truth.py`, and
`tests/test_info_help.py`.
last_result: focused no-network suite passed locally for owner OAuth switch on
2026-06-30; manual live smoke with real owner credentials passed on 2026-07-01 for invoice `20260006`.

## 2026-07-01 - OfficeFlow Work-Time Product Truth Smoke

Scope: `work_time_tracking` partial MVP.

Scenarios:

- User asks: "Vie bot evidovat odpracovane hodiny?" Expected: InfoHelp answers from Product Truth as partial, mentions simple open/close/manual/report support, and does not claim payroll/legal HR support.
- User asks: "Vypocita mi mzdy z dochadzky?" Expected: InfoHelp refuses the overclaim, says payroll/salary calculation and legal HR compliance are unsupported, and may suggest customization handling without promising implementation.
- User says: "zacinam pracovny den". Expected: top-level resolver returns `open_work_day`, not invoice creation.
- User says by voice/text: "pracoval som dnes od 5:30 do 17:00". Expected: top-level resolver returns `add_work_time_entry`; runtime previews exact times and saves only after approval.
- User says: "vytvor vykaz hodin za jun". Expected: top-level resolver returns `generate_work_time_report`, report is generated from user-scoped rows only, and no invoice/accounting data is touched.
- User says: "vymaz dochadzku za jul". Expected: top-level resolver returns `delete_work_time_month`, runtime previews month/year, row count, and total hours, deletes only after confirmation, and touches only current-user DB work-time rows/events for that month.
