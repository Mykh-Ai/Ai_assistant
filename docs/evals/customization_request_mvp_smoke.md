# Customization Request / Human Review MVP Smoke

## Scope

feature_or_layer: Customization Request MVP / Admin Response Human Review Loop
declared_maturity_level: partial Level 3
runtime_status: partial
artifact_status: scenario catalog, not a completed manual run log

This artifact records smoke scenarios for the implemented partial Level 3 MVP
slice:

- eligible InfoHelp/Triage candidates can create a preview;
- no database row is saved before explicit approve;
- approve saves one `confirmed_pending_review` request;
- edit updates draft title/summary and returns to preview;
- cancel clears the draft and saves nothing;
- voice can start preview while idle and can approve/cancel through the
  controlled path;
- exact title/summary edits remain text-first;
- admins can list, detail, accept, and reject requests;
- admin accept/reject is status review only.

Conceptually, current rows may represent broader review items such as
`feature_request`, `customization_request`, `unanswered_product_question`,
`support_question`, `troubleshooting_question`, `possible_product_truth_gap`,
or `admin_review_candidate`. A dedicated persisted `request_kind` /
`request_type` field is not implemented yet.

Out of scope for this MVP slice:

- admin response sent to user;
- answer text storage;
- `response_sent_at`;
- `response_sent_by`;
- `response_kind`;
- user notification on review decision;
- `needs_user_input` delivery to user;
- admin notes;
- user/admin notifications;
- Product Truth mutation;
- Product Truth candidate conversion;
- backlog conversion;
- code-agent handoff;
- self-learning;
- complete Level 3 lifecycle;
- request expiry/cleanup;
- rich pagination.

## Runtime Statuses

Runtime-supported persisted statuses:

- `confirmed_pending_review`
- `reviewed_accepted`
- `reviewed_rejected`

Reserved/future persisted statuses or lifecycle concepts:

- `needs_user_input`
- `answered`
- `response_sent`
- `closed_no_answer`
- `converted_to_product_truth_candidate`
- `converted_to_backlog`
- `cancelled_by_user`
- `expired_unconfirmed`

FSM-only draft states are not persisted as customization request rows.

Existing `reviewed_accepted` / `reviewed_rejected` statuses are review
decisions only. They are not answer delivery statuses and do not mean
implementation, Product Truth mutation, notification, or code-agent handoff.

## User Smoke Scenarios

### CR-MVP-USER-001 - Feature Request Candidate Preview

account_state: authorized user, idle FSM
input_channel: text
user_input: "Chcem mesačný report tržieb."
expected_response_behavior: show customization request preview with title,
summary, what will be saved, and what will not happen.
side_effect_expectation: no DB row before approve.
forbidden_behavior: direct implementation promise, admin notification, Product
Truth mutation, backlog conversion, code-agent handoff.
automation_status: covered by handler/service tests; manual smoke not recorded
in this artifact.
last_result: not_run_manual

### CR-MVP-USER-001B - Unanswered Product Question Review Preview

account_state: authorized user, idle FSM
input_channel: text
user_input: product/support/how-to question that Product Truth cannot answer
reliably
expected_response_behavior: show human-review/customization request preview
only if triage class is eligible and safe; copy says the bot cannot confirm the
answer from current Product Truth and asks for confirmation before save.
side_effect_expectation: no DB row before approve.
forbidden_behavior: claiming support, claiming Product Truth was updated,
claiming admin will definitely answer, admin notification, code-agent handoff.
automation_status: future/next slice for full human-review semantics; current
preview/save mechanics are covered for eligible triage classes.
last_result: not_run_manual

### CR-MVP-USER-002 - Approve Saves Pending Review

account_state: authorized user with preview draft
input_channel: text or decision button
user_input: approve / schváliť
expected_response_behavior: Slovak saved message says the request was stored
for later review and does not mean the feature is supported or will be
implemented.
side_effect_expectation: exactly one tenant-scoped `confirmed_pending_review`
row.
forbidden_behavior: duplicate row, implementation promise, notification,
Product Truth mutation, backlog conversion, code-agent handoff.
automation_status: covered by tests.
last_result: not_run_manual

### CR-MVP-USER-003 - Edit Updates Preview

account_state: authorized user with preview draft
input_channel: text
user_input: edit / upraviť, then revised title/summary text
expected_response_behavior: bot asks for text edit, updates draft
title/summary, preserves request identity, and returns to preview.
side_effect_expectation: no DB row until approve.
forbidden_behavior: changing requester, changing `request_id`, changing
redacted original text/hash, silent voice overwrite of exact text.
automation_status: covered by tests.
last_result: not_run_manual

### CR-MVP-USER-004 - Cancel Saves Nothing

account_state: authorized user with preview draft
input_channel: text or decision button
user_input: cancel / zrušiť
expected_response_behavior: Slovak cancellation message says nothing was saved.
side_effect_expectation: no customization request row.
forbidden_behavior: pending row, notification, admin task, Product Truth
mutation.
automation_status: covered by tests.
last_result: not_run_manual

### CR-MVP-USER-005 - Out Of Domain Does Not Start Draft

account_state: authorized user, idle FSM
input_channel: text
user_input: clearly unrelated non-business request
expected_response_behavior: safe non-request response.
side_effect_expectation: no draft, no DB row.
forbidden_behavior: customization preview, admin work, Product Truth mutation.
automation_status: covered by tests where triage class is exercised.
last_result: not_run_manual

### CR-MVP-USER-006 - Spam Or Noise Does Not Start Draft

account_state: authorized user, idle FSM
input_channel: text
user_input: spam/noise/abuse
expected_response_behavior: safe no-request path.
side_effect_expectation: no draft, no DB row.
forbidden_behavior: customization preview, saved request, notification.
automation_status: covered by tests where triage class is exercised.
last_result: not_run_manual

### CR-MVP-USER-006B - Product Truth Gap Does Not Mutate Truth

account_state: authorized user, idle FSM
input_channel: text
user_input: plausible product question that maps to
`possible_product_truth_candidate`
expected_response_behavior: bot may offer confirmation-gated review capture,
but states Product Truth support cannot be confirmed.
side_effect_expectation: approve may save one review item; Product Truth
registry is unchanged.
forbidden_behavior: creating/updating Product Truth, saying feature is
supported, saying a Product Truth candidate was created unless that conversion
flow exists.
automation_status: current no-mutation behavior covered by tests; admin
response/Product Truth review remains future.
last_result: not_run_manual

### CR-MVP-USER-007 - Direct Invoice Action Still Wins

account_state: authorized user, idle FSM
input_channel: text
user_input: clear invoice creation/editing action
expected_response_behavior: route to the existing invoice action flow.
side_effect_expectation: no customization request preview.
forbidden_behavior: treating direct executable action as customization request.
automation_status: covered by invoice prerouter tests.
last_result: not_run_manual

### CR-MVP-USER-008 - Active FSM Still Wins

account_state: authorized user in an active non-customization FSM flow
input_channel: text
user_input: possible feature request wording
expected_response_behavior: active FSM owns the conversation.
side_effect_expectation: no top-level customization preview.
forbidden_behavior: falling back to idle InfoHelp/Triage while FSM is active.
automation_status: covered by handler/voice state tests.
last_result: not_run_manual

### CR-MVP-USER-009 - Voice Preview And Controlled Decision

account_state: authorized user, idle FSM or customization preview FSM
input_channel: voice
user_input: STT transcript for a feature request, then approve/cancel wording
expected_response_behavior: idle transcript may start preview; voice
approve/cancel uses the same controlled decision context; exact edits are
rejected back to text.
side_effect_expectation: approve saves one row; cancel saves none.
forbidden_behavior: local yes/no parser, voice overwriting exact
title/summary, duplicate save.
automation_status: covered by voice state routing tests.
last_result: not_run_manual

## Admin Smoke Scenarios

### CR-MVP-ADMIN-010 - List Pending

account_state: authorized admin
input_channel: Telegram command
user_input: `/customization_requests`
expected_response_behavior: compact Slovak list of newest pending
`confirmed_pending_review` requests, limited to 10.
side_effect_expectation: read-only.
forbidden_behavior: status change, notification, raw hash display, raw secret
display.
automation_status: covered by admin tests.
last_result: not_run_manual

### CR-MVP-ADMIN-011 - Detail Request

account_state: authorized admin
input_channel: Telegram command
user_input: `/customization_request <request_id_or_8+char_prefix>`
expected_response_behavior: read-only detail for one request; short ambiguous
prefixes fail safely.
side_effect_expectation: read-only.
forbidden_behavior: raw hash display, raw unredacted secret display, status
change.
automation_status: covered by admin tests.
last_result: not_run_manual

### CR-MVP-ADMIN-012 - Accept Pending

account_state: authorized admin
input_channel: Telegram command
user_input: `/customization_request_accept <request_id_or_prefix>`
expected_response_behavior: pending request becomes `reviewed_accepted`; copy
states this does not automatically mean implementation.
side_effect_expectation: `reviewed_by`, `reviewed_at`, and `updated_at` are
set; no other side effects.
forbidden_behavior: Product Truth mutation, notification, backlog conversion,
code-agent handoff.
automation_status: covered by admin/service tests.
last_result: not_run_manual

### CR-MVP-ADMIN-013 - Reject Pending

account_state: authorized admin
input_channel: Telegram command
user_input: `/customization_request_reject <request_id_or_prefix>`
expected_response_behavior: pending request becomes `reviewed_rejected`; copy
states Product Truth did not change.
side_effect_expectation: `reviewed_by`, `reviewed_at`, and `updated_at` are
set; no other side effects.
forbidden_behavior: Product Truth mutation, notification, backlog conversion,
code-agent handoff.
automation_status: covered by admin/service tests.
last_result: not_run_manual

### CR-MVP-ADMIN-013B - Send Answer To User

account_state: authorized admin and existing confirmed review item
input_channel: Telegram command or future admin UI
user_input: admin answer text
expected_response_behavior: user receives admin answer through the bot and
response metadata is stored.
side_effect_expectation: `admin_response_text`, `response_sent_at`,
`response_sent_by`, and `response_kind` or equivalent fields are persisted.
forbidden_behavior: Product Truth mutation, implementation promise, backlog
conversion, code-agent handoff, silent delivery claim without actual send.
automation_status: future/next slice; not implemented in current runtime.
last_result: not_run_manual

### CR-MVP-ADMIN-013C - Reject With Reason Sent To User

account_state: authorized admin and existing confirmed review item
input_channel: Telegram command or future admin UI
user_input: rejection reason
expected_response_behavior: user receives rejection/explanation through the bot.
side_effect_expectation: response delivery metadata is stored.
forbidden_behavior: Product Truth mutation, saying the feature is now
unsupported because of the review, code-agent handoff.
automation_status: future/next slice; not implemented in current runtime.
last_result: not_run_manual

### CR-MVP-ADMIN-013D - Ask User For Clarification

account_state: authorized admin and existing confirmed review item
input_channel: Telegram command or future admin UI
user_input: clarification request
expected_response_behavior: user receives clarification request through the bot
and the item is marked `needs_user_input` or equivalent.
side_effect_expectation: clarification delivery metadata is stored.
forbidden_behavior: Product Truth mutation, pretending clarification was sent
when no delivery happened.
automation_status: future/next slice; not implemented in current runtime.
last_result: not_run_manual

### CR-MVP-ADMIN-014 - Repeated Review Is Already Processed

account_state: authorized admin
input_channel: Telegram command
user_input: repeated accept/reject against already reviewed request
expected_response_behavior: safe already-processed response.
side_effect_expectation: existing reviewed status and audit fields are
preserved.
forbidden_behavior: accepted changing to rejected, rejected changing to
accepted, audit overwrite, downstream side effects.
automation_status: covered by admin/service tests.
last_result: not_run_manual

### CR-MVP-ADMIN-015 - Non-Admin Denied

account_state: authorized non-admin user
input_channel: Telegram command
user_input: admin list/detail/accept/reject command
expected_response_behavior: safe Slovak denial.
side_effect_expectation: no read disclosure, no status change.
forbidden_behavior: exposing tenant-wide request data, reviewing request.
automation_status: covered by admin/access tests.
last_result: not_run_manual

### CR-MVP-ADMIN-016 - Unauthorized Blocked

account_state: unauthorized Telegram user
input_channel: Telegram command
user_input: admin list/detail/accept/reject command
expected_response_behavior: existing access middleware blocks the command.
side_effect_expectation: no DB read/write side effect from the command
handler.
forbidden_behavior: request listing, detail disclosure, status change.
automation_status: covered by access/admin tests.
last_result: not_run_manual

## Privacy Smoke Scenarios

### CR-MVP-PRIV-017 - Display Redaction

account_state: authorized user/admin as appropriate
input_channel: text, voice transcript, admin commands
user_input: request text containing covered secrets, tokens, emails, IBANs, or
phone numbers
expected_response_behavior: preview/save/admin display uses redacted fields.
side_effect_expectation: saved display fields are redacted; raw hash may be
stored for deduplication/audit but not displayed.
forbidden_behavior: rendering raw secrets/tokens/emails/IBANs/phones where the
redaction policy covers them.
automation_status: covered by service/admin tests.
last_result: not_run_manual

### CR-MVP-PRIV-018 - raw_text_hash Is Not User-Facing

account_state: authorized admin
input_channel: Telegram command
user_input: list/detail customization request
expected_response_behavior: output omits `raw_text_hash`.
side_effect_expectation: read-only.
forbidden_behavior: showing raw hash in list/detail copy.
automation_status: covered by admin tests.
last_result: not_run_manual

## Forbidden Product Claims

Do not claim:

- "This feature will be implemented."
- "Admin will implement this."
- "You will definitely receive an answer."
- "Admin was notified" unless actual notification exists.
- "The request was sent to admin" when only DB storage/review status exists.
- "The admin response was sent" when only status review exists.
- "This feature is now supported."
- "Product Truth was updated."
- "A Product Truth candidate was created."
- "A backlog item was created."
- "A code agent task was created."
- "The complete customization layer is available."
- "The bot learns automatically from this request."
- "`reviewed_accepted` means implementation approval."
- "`answered` means Product Truth changed."
- "`reviewed_rejected` changes Product Truth."

## Evidence

Relevant automated tests:

- `tests/test_customization_requests.py`
- `tests/test_customization_request_admin.py`
- `tests/test_info_help.py`
- `tests/test_invoice_intent_prerouter.py`
- `tests/test_voice_state_routing.py`

Last recorded full-suite evidence in `PROJECT_LOG.md` for this slice:

- Session 104, `python -m pytest -q`: 1250 passed, 7 subtests passed.

Manual product UX smoke run:

- not recorded in this artifact yet.
