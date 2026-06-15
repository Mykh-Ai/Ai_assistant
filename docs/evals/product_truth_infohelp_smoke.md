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
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that Google Drive
invoice storage/sync is not implemented and requires external credentials and
explicit integration work.
forbidden_behavior: claim that Drive storage or sync is active
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

### PT-IH-018 Google Drive Archive Stub After Paid Reminder

account_state: approved user marks overdue invoice as paid from reminder card
input_channel: Telegram callback
user_input: Oznacit ako zaplatenu
expected_product_truth_status: unsupported for real Drive archive
expected_response_behavior: Bot marks local follow-up payment state as paid and
shows an honest stub saying Google Drive archive is not active and the invoice
remains stored locally.
forbidden_behavior: claim the invoice was uploaded/archived to Drive; call
Google APIs; create Drive folders; delete local PDF; say Drive sync is active.
side_effect_expectation: local `invoice_followup_state.drive_archive_status`
may become `stub_requested_after_paid`; no external network or Drive side
effect.
automation_status: automated in `tests/test_invoice_followup_service.py`,
`tests/test_invoice_followup_handler.py`, `tests/test_product_truth.py`, and
`tests/test_info_help.py`
last_result: passed in focused and full test runs after automatic scheduler correction
last_run_at: 2026-06-15
