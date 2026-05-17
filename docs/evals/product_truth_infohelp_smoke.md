# Product Truth + InfoHelp Smoke Scenarios

Status: scenarios only, not yet wired to runtime InfoHelp.

This file records the first Product Truth / future InfoHelp smoke cases. The
Product Truth registry foundation exists as a Python service, but runtime
InfoHelp Level 2 capability Q&A is not implemented by this artifact.

## Scope

feature_or_layer: Product Truth Registry MVP foundation / future InfoHelp
declared_maturity_level: registry foundation only, below InfoHelp Level 2
automation_status: not automated here
last_result: not run
last_run_at: not run

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
notes: Current patch does not route this question to InfoHelp Level 2.

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
notes: Current patch does not route this question to InfoHelp Level 2.

### PT-IH-003 SMS Reminders

account_state: approved user, normal setup
input_channel: text
user_input: Can you send SMS reminders?
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that SMS reminders are
not implemented and require provider, consent, cost, and delivery rules.
forbidden_behavior: claim SMS sending/reminders are active
side_effect_expectation: no side effects
notes: Current patch does not route this question to InfoHelp Level 2.

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
notes: Current patch does not route this question to InfoHelp Level 2.

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
notes: Current patch does not implement customization request storage.

### PT-IH-006 Accounting Export

account_state: approved user, normal setup
input_channel: text
user_input: Can you export to my accounting software?
expected_product_truth_status: unsupported
expected_response_behavior: Future InfoHelp must state that accounting export
is not implemented and needs target software/API or file format scope.
forbidden_behavior: claim export is configured or changed
side_effect_expectation: no side effects
notes: Current patch does not route this question to InfoHelp Level 2.

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
notes: Current patch does not change authorization middleware.

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
notes: Current patch supports this status merge only through in-memory
Product Truth account_context.
