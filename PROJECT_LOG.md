# PROJECT_LOG

## 2026-05-30 - Session 116 - Confirmed accounting document archive enqueue

Summary:
- Wired the accounting document intake confirmation path to enqueue a local
  Google Drive archive outbox job after `save_confirmed_accounting_document(...)`
  succeeds.
- The hook derives `document_id` from the confirmed metadata filename stem and
  uses the confirmed original and metadata paths; no temporary upload path is
  archived.
- Archive enqueue failures are logged with a bounded diagnostic and do not roll
  back the already-confirmed local accounting document save.
- Added handler-flow tests for confirmed receipt and incoming-invoice enqueue,
  no enqueue before preview approval, no enqueue on cancel, no enqueue on save
  failure, idempotent duplicate enqueue, confirmed path/state mirroring, and
  archive enqueue failure preserving the confirmed original.

Constraints:
- Phase 1B only: enqueue archive state/job after confirmed accounting document
  save.
- No Google OAuth, Google API calls, real Drive adapter, worker run, upload,
  local cleanup/deletion of confirmed originals, invoice lifecycle/reminders,
  outgoing invoice PDF archive, or recent-docs UI change.
- Product Truth/InfoHelp remain unchanged and must not claim active Google
  Drive archiving.

Verification:
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_accounting_document_archive_service.py tests/test_archive_job_service.py`
  - 80 passed.
- `python -m pytest -q tests/test_accounting_document_registry.py tests/test_accounting_documents_handler.py`
  - 18 passed.
- `python -m pytest -q tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 43 passed.
- `python -m pytest -q`
  - 1368 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 115 - Google Drive archive outbox transition hardening

Summary:
- Hardened `ArchiveJobService` with explicit bounded transitions for
  `pending`, `uploading`, `uploaded`, `retry_wait`, `failed`, and `abandoned`.
- Added additive worker lease columns on `archive_jobs`: `locked_by` and
  `lease_until`.
- Added atomic runnable job claiming for pending jobs, due retry jobs, and
  expired uploading leases.
- Clarified terminal enqueue policy: an existing `uploaded`, `failed`, or
  `abandoned` job for the same workspace/document/provider blocks automatic
  duplicate enqueue and is returned as-is.
- Tightened archive input validation to accepted accounting document originals
  under `workspaces/<workspace>/years/<year>/expenses/<month>/<receipts|incoming_invoices>/originals/`.
- Hardened `AccountingDocumentArchiveService` so mark operations require an
  existing archive state and fail safely before mutating a direct job-service
  job without mirrored state.
- Added static handler-boundary coverage proving accounting handlers still do
  not import or call archive services in this slice.

Constraints:
- Service hardening and tests only.
- No Telegram handler wiring or archive job creation from accounting document
  confirmation.
- No Google OAuth, Google API calls, real Drive adapter, external credentials,
  upload, notification, local cleanup/deletion, invoice lifecycle/reminders, or
  outgoing invoice PDF archive.
- Product Truth/InfoHelp remain unchanged and must not claim active Google
  Drive archiving.

Verification:
- `python -m pytest -q tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 43 passed.
- `python -m pytest -q tests/test_accounting_document_registry.py tests/test_accounting_documents_handler.py`
  - 18 passed.
- `python -m pytest -q`
  - 1361 passed, 7 subtests passed.
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-30 - Session 114 - Google Drive accounting archive outbox foundation

Summary:
- Added the tracked design source
  `docs/Google_Drive_Faktury_Bloceky_Storage_Policy.md` after checking it for
  obvious secrets/credentials.
- Added additive SQLite archive foundation tables:
  `archive_jobs` and `accounting_document_archive_state`.
- Added `bot/services/archive_job_service.py` for local outbox job creation,
  idempotent active-job enqueue, runnable job listing, and status transitions.
- Added `bot/services/accounting_document_archive_service.py` to mirror archive
  state for confirmed accounting documents by workspace/document id.
- Added service tests for schema bootstrap, enqueue idempotency, runnable jobs,
  upload/retry/failure/abandoned status updates, local-file retention, no
  Google/network imports, and Product Truth non-overclaim.

Constraints extracted:
- Phase 1A only: DB/outbox services and tests.
- No Google OAuth, Google API calls, external credentials, real upload, Drive
  delete/archive, notifications, local cleanup, invoice lifecycle/reminders, or
  outgoing invoice PDF archive.
- Existing accounting document naming/storage remains canonical; new archive
  state references existing `metadata_path` and `original_path`.
- Telegram handlers are not wired to enqueue or upload in this slice.
- Product Truth/InfoHelp still must not claim active Google Drive archive.

Touched scopes:
- DB schema: yes, additive tables only;
- storage: references only, no file moves/deletes;
- accounting document services: archive foundation only;
- Telegram handlers/FSM/routing/LLM/STT/LMM/access/server: no behavior changes.

Current implementation status:
- Google Drive accounting archive: partial foundation only, no runtime upload.
- Google Drive integration/OAuth: unsupported / requires external credentials.
- AI maturity: not an AI-layer change; Product Truth remains the source for user
  capability claims.

Verification:
- `python -m pytest -q tests/test_archive_job_service.py tests/test_accounting_document_archive_service.py`
  - 27 passed.
- `python -m pytest -q tests/test_accounting_document_registry.py tests/test_accounting_documents_handler.py`
  - 18 passed.
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py`
  - 84 passed.
- `python -m pytest -q`
  - 1345 passed, 7 subtests passed.

## 2026-05-24 - Session 113 - InfoHelp human-review offer wording

Summary:
- Cleaned InfoHelp human-review offer rendering so escalation copy is
  contextual rather than appended as global boilerplate.
- Replaced internal-sounding "samostatný potvrdený náhľad" wording with
  user-facing Slovak copy that says a request is saved only after confirmation.
- Improved unsupported invoice email guidance: automatic email sending remains
  unsupported, while users can manually forward the PDF in Telegram or
  share/download it and attach it in their own email app with recipient and
  message filled manually.

Scope:
- InfoHelp rendering, InfoHelp docs, and tests only.
- No email sending implementation.
- No human-review storage or delivery flow changes.
- No Product Truth status changes.

Verification:
- `python -m pytest -q tests/test_info_help.py tests/test_product_truth.py`
  - 84 passed.
- `python -m pytest -q`
  - 1318 passed, 7 subtests passed.

## 2026-05-24 - Session 112 - Capability completion documentation gate

Summary:
- Added a docs-only capability completion gate across agent instructions,
  implementation checklists, action design guidance, Product Truth, InfoHelp,
  eval standards, and product doctrine.
- Clarified that user-facing runtime changes are incomplete when Product Truth,
  InfoHelp, eval/smoke artifacts, tests, forbidden claims, or `PROJECT_LOG.md`
  are stale.
- Added a concrete future Google Drive invoice storage example: runtime
  integration must be accompanied by Product Truth status/limitations, InfoHelp
  answers for "Vieš ukladať faktúry na Google Drive?" and "Ako zapnem Google
  Drive?", eval smoke, tests, log entry, and forbidden claims.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No handler, DB/schema, Product Truth runtime data, integration, retry,
  backlog, code-agent, or self-learning changes.
- No complete InfoHelp Level 2 or complete Level 3 claim.

Verification:
- `git diff --check`
  - passed; line-ending warnings only.

## 2026-05-24 - Session 111 - Align Product Truth with human review runtime

Summary:
- Updated Product Truth to describe `customization_requests` as partial
  human-review runtime support instead of unsupported storage.
- Added Product Truth records for admin status review, answer-only admin
  response-to-user, admin-facing response delivery observability, access
  request approval, and invoice draft edit flow.
- Expanded InfoHelp Slovak answers for request lifecycle, admin answer
  delivery, accepted/rejected status meaning, confirmed admin-review submission,
  admin-facing delivery observability, recent bločky, contacts, services,
  existing invoice edit/delete, and generic voice usage.
- Updated InfoHelp triage payload truth so confirmed request storage is marked
  available while admin notification remains unavailable.
- Updated Product Truth/InfoHelp/customization eval/doctrine docs to reflect
  answer-only admin response delivery and observability without overstating
  maturity.

Constraints:
- Truth/docs/tests alignment only.
- No new runtime feature, admin command, retry/recovery command, notification,
  backlog conversion, Product Truth candidate conversion, code-agent handoff, or
  self-learning.
- No dynamic runtime Product Truth mutation.
- Still a partial Level 3 human-review slice, not the complete Customization
  Request Layer.
- Still partial InfoHelp, not complete Level 2.

Verification:
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_customization_request_admin.py`
  - 135 passed.
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_customization_request_admin.py tests/test_invoice_intent_prerouter.py`
  - 282 passed.
- `python -m pytest -q`
  - 1317 passed, 7 subtests passed.

## 2026-05-23 - Session 110 - Admin response delivery observability

Summary:
- Added admin detail observability for the latest Admin Response delivery state.
- `/customization_request <id_or_prefix>` now shows computed `not_started`,
  `send_pending`, `send_succeeded`, and `send_failed` response delivery states
  using existing `customization_requests` fields.
- Added a stuck `send_pending` warning for pending responses older than 15
  minutes with attempts and no `response_sent_at`; this marks the result as
  unknown/manual-check-needed only.
- Detail output shows bounded response metadata and a redacted/truncated
  admin response preview without exposing `raw_text_hash`.
- Updated the Customization Request contract and MVP smoke eval catalog.

Constraints:
- Observability-only slice.
- No schema change.
- No retry or auto retry.
- No recovery command or `delivery_unknown` marking.
- No Product Truth mutation.
- No request review status mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No notifications.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py`
  - 87 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1308 passed, 7 subtests passed.

## 2026-05-23 - Session 109 - Admin Response delivery idempotency hardening

Summary:
- Hardened Admin Response to User MVP delivery idempotency before push.
- The service now atomically claims a response as `send_pending` before any
  Telegram delivery attempt.
- Duplicate confirms for the same `response_id` in `send_pending`,
  `send_succeeded`, or `send_failed` do not trigger another outbound send.
- The handler now sends to the persisted request row `telegram_id` returned by
  the service, not a final-send FSM draft target.
- Added handler/service tests for pending duplicate confirms, already-succeeded
  duplicate confirms, same-id failed response no-retry behavior, tampered FSM
  target safety, missing bot failure, Telegram exception failure, outbound
  redaction, persisted failed response text, attempts behavior, review status
  separation, and no downstream Product Truth/backlog/code-agent/self-learning
  effects.

Constraints:
- No new response kinds.
- No retry flow.
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No automatic accept/reject notifications.
- No broad routing changes.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_voice_state_routing.py`
  - 149 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1303 passed, 7 subtests passed.

## 2026-05-23 - Session 108 - Admin Response to User MVP

Summary:
- Implemented explicit admin response delivery for customization/human-review
  requests.
- Added admin-only `/customization_request_reply <id_or_prefix>`.
- Added a confirmation-gated admin response FSM: text entry, preview,
  send/edit/cancel, and shared DecisionResolver callback/voice preview routing.
- Added latest-response metadata fields on `customization_requests`:
  `admin_response_text`, `response_kind`, `response_sent_at`,
  `response_sent_by`, `response_delivery_status`, `response_attempts`,
  `response_failed_reason`, `responded_to_request_status`,
  `response_updated_at`, and `response_id`.
- Persisted confirmed response metadata/text before Telegram send attempt;
  delivery result then records `send_succeeded` or `send_failed`.
- Duplicate confirm for an already sent `response_id` does not send again.
- Failed send keeps the response persisted with a safe bounded failure reason
  and no automatic retry.
- Updated docs/evals to mark only default `answer` response delivery as
  implemented.

Constraints:
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No automatic notifications on accept/reject.
- No automatic retry.
- No threaded/multi-response conversation history.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_voice_state_routing.py`
  - 142 passed, 7 subtests passed.
- `python -m pytest -q tests/test_decision_resolver.py tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_voice_state_routing.py`
  - 658 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1296 passed, 7 subtests passed.

## 2026-05-23 - Session 107 - Refine admin response MVP delivery semantics

Summary:
- Refined the docs-only Admin Response MVP design before runtime
  implementation.
- Clarified that confirmed admin response text/metadata must persist before the
  Telegram send attempt, and delivery status/timestamps/failure reason are
  updated after the send result.
- Clarified that MVP stores only latest response metadata on
  `customization_requests`; multi-response or threaded conversation history is
  future scope.
- Defined `clarification_request` as one-way outbound communication if included
  in MVP; it does not reopen a structured workflow or automatically move the
  request to `needs_user_input`.
- Clarified failed-send recovery: failed responses remain persisted with
  `send_failed`, no automatic retry happens, and a future manual retry may
  reuse persisted response data.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No admin replies implemented.
- No user notifications implemented.
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- Still a partial Level 3 MVP design, not the complete Customization Request
  Layer or complete human-review loop.

Verification:
- `git diff --check`

## 2026-05-23 - Session 106 - Document admin response loop for customization requests

Summary:
- Broadened Customization Request documentation into an Admin Response / Human
  Review Loop concept.
- Clarified that current `customization_requests` rows may conceptually cover
  feature/customization requests, unanswered product/support/troubleshooting
  questions, possible Product Truth gaps, and admin-review candidates.
- Documented the current runtime limitation: capture, confirmed save, admin
  list/detail, and status-only accept/reject review exist; admin response to
  user, answer text storage, response delivery metadata, user notifications,
  `needs_user_input` delivery, and Product Truth mutation are not implemented.
- Extended eval artifacts with future/next-slice scenarios for admin answers,
  rejection explanations, clarification requests, out-of-domain/spam safety,
  and Product Truth gap non-mutation.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No admin replies.
- No user notifications.
- No Product Truth mutation.
- No backlog conversion.
- No code-agent handoff.
- No self-learning.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer or closed human-review loop.

Verification:
- `git diff --check`

## 2026-05-22 - Session 105 - Customization request MVP docs and eval checkpoint

Summary:
- Aligned Customization Request MVP documentation with the current partial
  Level 3 runtime slice.
- Clarified user preview/save behavior, tenant-scoped storage, redacted
  draft/save data, deterministic request IDs, admin list/detail commands, and
  status-only accept/reject review commands.
- Tightened runtime-supported status terminology versus reserved/future
  statuses.
- Added `docs/evals/customization_request_mvp_smoke.md` with user, admin,
  privacy, and forbidden-claim smoke scenarios.

Constraints:
- Docs/evals only.
- No runtime code changes.
- No admin notes.
- No notifications.
- No Product Truth mutation.
- No Product Truth candidate conversion.
- No backlog conversion.
- No code-agent handoff.
- No self-learning.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `git diff --check`

## 2026-05-22 - Session 104 - Customization request review idempotency hardening

Summary:
- Hardened admin customization request review transitions for repeated or
  racing review attempts.
- The service now checks the guarded review `UPDATE` row count and refetches
  the current row if another review already changed the status.
- Repeat accept/reject attempts return safe already-processed results and do
  not overwrite the original `reviewed_by`, `reviewed_at`, or `updated_at`.
- Added focused regression tests for accept-accepted, reject-rejected,
  reject-accepted, accept-rejected, audit-field preservation, pending-list
  exclusion, detail visibility, and no downstream side effects.

Constraints:
- No new feature surface.
- No notifications.
- No Product Truth mutation.
- No backlog conversion.
- No Product Truth candidate conversion.
- No code-agent handoff.
- No self-learning.
- No admin notes.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py`
  - 61 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1250 passed, 7 subtests passed.

## 2026-05-22 - Session 103 - Admin customization request review statuses

Summary:
- Added admin-only `/customization_request_accept <request_id>` and
  `/customization_request_reject <request_id>` commands.
- Added a status-only review transition in `CustomizationRequestService`:
  `confirmed_pending_review` can become `reviewed_accepted` or
  `reviewed_rejected`.
- Review transitions set `reviewed_by`, `reviewed_at`, and `updated_at`.
- Re-reviewing an already processed request is safe and does not change the
  existing reviewed status.
- Existing pending list now naturally excludes reviewed requests, while detail
  remains able to show reviewed requests.

Constraints:
- No Product Truth mutation.
- No user/admin notification.
- No backlog conversion.
- No code-agent handoff.
- No Product Truth candidate conversion.
- No self-learning.
- No free-form LLM review.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_customization_requests.py tests/test_access_request_flow.py`
  - 77 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1248 passed, 7 subtests passed.

## 2026-05-21 - Session 102 - Admin-only customization request detail view

Summary:
- Added `/customization_request <request_id>` as an admin-only read-detail
  command for customization requests.
- The detail view is read-only, supports full `request_id` lookup and safe
  unique short-prefix lookup, and rejects ambiguous prefixes.
- Output uses conservative display redaction and omits `raw_text_hash`.
- Added tests for full ID lookup, unique-prefix lookup, ambiguous/missing
  lookup, non-admin denial, unauthorized middleware blocking, read-only
  behavior, and sensitive value redaction.

Constraints:
- No approve/reject status changes.
- No admin notifications.
- No Product Truth mutation.
- No code-agent handoff or backlog conversion.
- No self-learning.
- Still a partial Level 3 MVP slice, not the complete Customization Request
  Layer.

Verification:
- `python -m pytest -q tests/test_customization_request_admin.py tests/test_access_request_flow.py tests/test_customization_requests.py`
  - 61 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1232 passed, 7 subtests passed.

## 2026-05-21 - Session 101 - Admin-only customization request pending list

Summary:
- Added `/customization_requests` as an admin-only read/list command for
  pending confirmed customization requests.
- The list is read-only and shows a compact pending-review summary for the
  newest requests across tenants for administrators.
- Added a narrow limit/newest-first option to the existing admin/internal
  `CustomizationRequestService.list_pending_customization_requests_for_admin`.
- Added tests for admin access, non-admin denial, middleware blocking for
  unauthorized users, pending-only filtering, conservative output redaction,
  admin-wide visibility, read-only behavior, and list limiting.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Add a minimal read-only admin review surface only.
- Do not add approve/reject status changes.
- Do not add admin notifications.
- Do not mutate Product Truth.
- Do not implement code-agent handoff or backlog conversion.
- Do not add self-learning.
- Do not expose requests to non-admin users.
- Do not call the complete Level 3 customization layer.
- Do not change InfoHelp/Triage creation flow.

Touched scopes:
- Admin/access: added one admin command and middleware admin-command allowlist
  entry.
- Storage/DB: read-only admin list query only; no schema change and no status
  mutation.
- Product docs: synchronized Customization Request contract narrowly.
- LLM/STT/LMM/FSM/routing/voice/PDF/server: unchanged.

Current implementation status:
- Admin pending customization request list: implemented read-only MVP slice.
- Approve/reject/status review decisions: unsupported.
- Admin notification: unsupported.
- Product Truth mutation: unsupported and unchanged.
- Code-agent handoff/backlog conversion: unsupported.
- Complete Customization Request Layer / complete Level 3: not complete.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_access_request_flow.py tests/test_customization_request_admin.py`
  - 248 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1222 passed, 7 subtests passed.

## 2026-05-21 - Session 100 - Customization Request Phase 2 edge-case regression tests

Summary:
- Added Phase 2 edge-case regression coverage for customization request
  confirmation hardening.
- Covered cross-user duplicate `request_id` collision, non-pending duplicate
  `request_id`, full `decision_callback(...)` approve/edit/cancel routing,
  edit draft identity preservation, and same-draft duplicate approval.
- Tests-only change; no runtime bug was found during implementation.

Constraints:
- No admin list command.
- No admin notification.
- No Product Truth mutation.
- No code-agent handoff.
- No routing behavior change.
- No new canonical actions.
- No complete Level 3 claim.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_decision_callbacks.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py`
  - 233 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1212 passed, 7 subtests passed.

## 2026-05-21 - Session 099 - Customization Request Phase 2 ownership/idempotency hardening

Summary:
- Hardened the existing Phase 2 confirmation flow without adding new feature
  surface.
- Preview drafts now carry the original requester `telegram_id`, workspace
  context, and deterministic `request_id` generated at preview time.
- Approval uses the draft owner and stored `request_id`; mismatched users are
  rejected without saving.
- Duplicate approval attempts for the same `request_id` are handled
  idempotently and do not create duplicate rows.
- FSM draft storage now minimizes raw input by keeping redacted original text
  plus a raw text hash; save still re-applies service-level redaction.
- Added focused text/button/voice regression tests for ownership,
  idempotency, callback decisions, voice approve/cancel, text-first edit, and
  all four eligible triage classes.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Runtime hardening and tests only.
- No admin notification or admin list command.
- No Product Truth mutation.
- No code-agent handoff.
- No new canonical action.
- No InfoHelp heuristic/dictionary expansion.
- No broad routing change without a failing narrow test.
- Do not call Level 3 complete.

Touched scopes:
- Confirmation: kept shared DecisionResolver `approve_edit_cancel` context.
- FSM: hardened Customization Request preview draft ownership/idempotency data.
- Storage/DB: no schema change; save still goes only through
  `CustomizationRequestService.create_confirmed_customization_request(...)`
  after approval.
- Voice/STT: added coverage for voice approval/cancel and text-first edit
  boundary; no voice phrase dictionary expansion.
- Product docs: synchronized Customization Request contract only.

Current implementation status:
- Customization Request preview/save: partial Level 3 MVP slice, hardened.
- Admin notification/list: unsupported and unchanged.
- Product Truth mutation: unsupported and unchanged.
- Code-agent handoff: unsupported and unchanged.
- Complete Customization Request Layer / complete Level 3: not complete.

Self-learning hooks considered:
- None added. This hardening stores only confirmed request rows after explicit
  approval and does not learn aliases, topics, or workflow rules.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_info_help.py tests/test_voice_state_routing.py tests/test_invoice_intent_prerouter.py tests/test_decision_resolver.py tests/test_decision_callbacks.py`
  - 775 passed, 7 subtests passed.
- `python -m pytest -q`
  - 1205 passed, 7 subtests passed.

## 2026-05-21 - Session 098 - Customization Request MVP Phase 2 preview/save flow

Summary:
- Added a confirmation-gated Customization Request preview/save flow for
  eligible idle InfoHelp/Triage candidates:
  `new_business_feature_request`, `customization_request_candidate`,
  `admin_review_candidate`, and `possible_product_truth_candidate`.
- Drafts live only in FSM/temp state until the user explicitly approves.
- Approval saves exactly one `confirmed_pending_review` row through
  `CustomizationRequestService.create_confirmed_customization_request(...)`.
- Edit lets the user revise a short title/summary before returning to the
  preview.
- Cancel clears the draft and saves nothing.
- Idle voice transcripts can start the same preview flow, while exact
  title/summary edits remain text-preferred.
- Button, text, and voice confirmation paths use the shared
  DecisionResolver `approve_edit_cancel` family with context
  `customization_request_preview`.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- No save before explicit confirmation.
- No admin notification or admin list command.
- No Product Truth mutation.
- No code-agent handoff.
- No new canonical business action.
- Active FSM state and direct executable actions keep precedence.
- Unauthorized/unknown users must not start or save request drafts.

Touched scopes:
- Confirmation: added `customization_request_preview` DecisionResolver context.
- Routing: idle unknown InfoHelp/Triage candidate path only.
- FSM: added `CustomizationRequestStates.waiting_preview_decision` and
  `CustomizationRequestStates.waiting_edit_text`.
- Storage/DB: uses existing `customization_requests` table/service only after
  approval; no schema change.
- Voice/STT: idle voice transcript can start preview; edit text remains
  text-preferred.
- LLM/LMM/server/PDF/layout/access model: no architecture expansion.
- Product docs: updated active Customization Request and InfoHelp contracts.

Current implementation status:
- Customization Request storage foundation: implemented partial foundation.
- Confirmation-gated preview/save: implemented partial MVP slice.
- Admin notification/list: unsupported.
- Product Truth mutation: unsupported and unchanged.
- Code-agent handoff: unsupported.
- Complete Level 3 customization layer: partial, not complete.

AI maturity:
- Partial Level 3 MVP slice. This does not complete the Customization Request
  Layer because admin/developer review, richer structured request objects,
  Product Truth candidate conversion, and code-agent handoff are still absent.

Out of scope:
- Admin notification/list command.
- Product Truth writes or status changes.
- Code-agent handoff/task creation.
- New canonical business actions.
- Timeout/cleanup scheduler beyond existing FSM clear/cancel behavior.

Product/user journey proving the change:
- An authorized idle user asks for a new business feature or customization.
- The bot shows a Slovak preview with title, summary, what will be saved, and
  what will not happen.
- Approve saves one pending-review row; cancel saves nothing; edit then approve
  saves the edited title/summary.

Self-learning hooks considered:
- None implemented. Request capture is explicit and confirmed, but no alias,
  topic, or workflow learning is stored.

Source of truth for user-facing claims:
- Runtime code and tests prove preview/save only after approval.
- `CustomizationRequestService` proves persisted status and tenant scope.
- Product Truth registry is not mutated and no support claim is upgraded.

Verification:
- `python -m pytest -q tests/test_customization_requests.py tests/test_info_help.py tests/test_voice_state_routing.py tests/test_invoice_intent_prerouter.py`
  - 268 passed, 7 subtests passed.

## 2026-05-20 - Session 097 - Harden Customization Request service boundaries

Summary:
- Hardened the Customization Request Phase 1 storage/service API before any
  user-facing flow is wired.
- Added `get_customization_request_for_user()` as the tenant-scoped read API;
  it requires `telegram_id` and returns only rows matching both `request_id`
  and user scope.
- Renamed the unscoped lookup to
  `get_customization_request_by_id_for_admin()` and documented it as
  admin/internal only.
- Renamed pending-review listing to
  `list_pending_customization_requests_for_admin()` and documented it as an
  admin/internal primitive, not a tenant-user listing API.
- Re-redacts caller-provided `redacted_original_text` before persistence so a
  handler-side mistake cannot store obvious secrets as redacted text.
- Restricts request creation to request-starting triage classes:
  `new_business_feature_request`, `customization_request_candidate`,
  `admin_review_candidate`, and `possible_product_truth_candidate`.
- Added tests for scoped reads, cross-user read prevention, required
  `telegram_id`, admin/internal method naming, direct-redacted-text
  re-redaction, invalid triage classes, and invalid source channel.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`

Constraints extracted:
- Service/API hardening and tests only.
- No user-facing InfoHelp/Triage flow, handlers, routing changes, admin list
  command, admin notification, Product Truth mutation, code-agent handoff, or
  complete Level 3 claim.

Touched scopes:
- Customization Request storage service, tests, and project log.
- DB table shape, runtime routing, handlers, voice/STT, LLM behavior, admin
  notification, Product Truth registry, and code-agent handoff are unchanged.

Current implementation status:
- Customization Request storage/service foundation: hardened partial Phase 1
  runtime foundation for confirmed rows only.
- User-facing Customization Request flow: not implemented.
- Admin review/notification: not implemented.
- Code-agent handoff: not implemented.
- Customization Request Level 3: not complete.

AI maturity:
- Storage prerequisite hardening for future Level 3. This patch does not
  provide a confirmation-gated user journey.

Out of scope:
- Draft preview FSM, confirmation UI, InfoHelp integration, admin list,
  admin notification, Product Truth candidate conversion, and code-agent
  task creation.

Verification:
- Service tests:
  `python -m pytest -q tests/test_customization_requests.py`.
- Required focused suite:
  `python -m pytest -q tests/test_customization_requests.py tests/test_product_truth.py tests/test_info_help.py`.
- Full suite:
  `python -m pytest -q`.

## 2026-05-20 - Session 096 - Customization Request storage foundation

Summary:
- Added additive SQLite storage foundation for confirmed customization
  requests through the new `customization_requests` table.
- Added `bot/services/customization_requests.py` with a narrow service API for
  creating confirmed request rows, fetching by id, listing user-scoped
  requests, listing pending review rows, hashing raw text, and deterministic
  redaction.
- Persisted records require tenant/user scope, non-empty title and summary,
  allowed persisted status, and explicit confirmed storage semantics.
- `draft_unconfirmed` is rejected from long-term persistence in Phase 1.
- Duplicate `request_id` creation fails deterministically instead of silently
  upserting.
- Added redaction coverage for API keys / `sk-` tokens, password/secret/token
  fields, IBAN-like values, email addresses, and phone numbers.
- Added tests proving tenant-scoped listing, status filtering, timestamp
  population, redaction/hash behavior, Product Truth immutability, and absence
  of admin notification / code-agent hooks.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Customization_Request_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Storage/service foundation only.
- No user-facing InfoHelp/Triage flow, routing behavior change, admin
  notification, admin list command, code-agent handoff, Product Truth mutation,
  pre-confirmation request persistence, handler-local matching, or complete
  Level 3 claim.

Touched scopes:
- DB schema bootstrap, storage service, tests, and project log.
- Runtime routing, handlers, voice/STT, LLM behavior, admin notification,
  Product Truth registry, and code-agent handoff are unchanged.

Current implementation status:
- Customization Request storage/service foundation: partial Phase 1 runtime
  foundation for confirmed rows only.
- User-facing Customization Request flow: not implemented.
- Admin review/notification: not implemented.
- Code-agent handoff: not implemented.
- Customization Request Level 3: not complete.

AI maturity:
- Storage prerequisite for future Level 3. This patch does not itself provide
  a confirmation-gated user journey.

Out of scope:
- Draft preview FSM, confirmation UI, InfoHelp integration, admin list,
  admin notification, Product Truth candidate conversion, and code-agent
  task creation.

Verification:
- Focused service test:
  `python -m pytest -q tests/test_customization_requests.py`.
- Required focused suite:
  `python -m pytest -q tests/test_customization_requests.py tests/test_product_truth.py tests/test_info_help.py`.
- Full suite:
  `python -m pytest -q`.

## 2026-05-20 - Session 095 - Harden LLM InfoHelp triage fallback tests

Summary:
- Added regression tests for the LLM-backed InfoHelp / Unknown-Triage fallback
  path without changing runtime behavior.
- Covered absent and non-`sk-` API key no-call behavior so the OpenAI client is
  not instantiated when the LLM fallback is unavailable.
- Extended payload assertions to exclude both `safe_next` and
  `safe_next_steps`, plus request/admin/action side-effect fields.
- Added parser coverage proving an invalid topic for a known capability is not
  trusted and normalizes to the safe `product_capability` topic.
- Added service and top-level integration coverage for model `unknown`
  returning generic bounded fallback guidance.
- Added service and top-level integration coverage for
  `possible_product_truth_candidate` clarification without Product Truth
  mutation, DB/storage writes, admin notification, or request save.
- Added mocked multilingual/noisy LLM-path smoke inputs for SK, SK without
  diacritics, Ukrainian, Russian, mixed/surzhyk, and mild STT-like text.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Tests-only unless a failing test exposes a tiny safety bug.
- No new features, routing behavior changes, storage/admin/customization
  writes, canonical actions, heuristic/dictionary expansion, DecisionResolver
  changes, or complete Level 2 claims.

Touched scopes:
- Tests and project log only.
- Runtime routing, handlers, DB/storage/schema, admin notifications,
  customization storage, canonical actions, DecisionResolver, and Product
  Truth status are unchanged.

Current implementation status:
- LLM-backed bounded InfoHelp / Unknown-Triage resolver path: partial Level 2
  foundation.
- InfoHelp Level 2: still not complete.
- Customization Request storage/admin notification: still unsupported runtime.

AI maturity:
- Test hardening for a partial Level 2 foundation. No new runtime capability
  claims.

Out of scope:
- Runtime behavior changes.
- Request persistence, admin sends, new business actions, Product Truth status
  mutation, broad heuristic expansion, and self-learning.

Verification:
- Focused suite required:
  `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_product_truth.py`.
- Full suite required:
  `python -m pytest -q`.

## 2026-05-19 - Session 094 - LLM-backed InfoHelp triage resolver path

Summary:
- Added `bot/services/info_help_resolver.py` as the bounded LLM-backed
  InfoHelp / Unknown-Triage classifier path behind deterministic v1.
- Deterministic Product Truth / triage matching remains the first fast-path;
  LLM classification is used only when deterministic triage returns no
  renderable result and a plausible API key is configured.
- LLM input is classification-only: context name, input channel, user text,
  supported languages, known capability IDs with title/domain/classification
  summaries, allowed topic IDs, allowed triage classes, disabled request
  storage/admin notification flags, and the expected output schema.
- LLM output is validated back into Python-owned fields only:
  `capability_id`, `topic_id`, `triage_class`, `confidence`, and
  `needs_clarification`.
- Hardened validation so conflicting `capability_id` + `triage_class`
  combinations fail safe instead of forcing a known capability.
- Wired the unknown top-level text path and idle voice transcript path to use
  deterministic triage first, then the bounded LLM classifier fallback.
- Added mocked LLM payload, parser, fallback, rendering, text integration, and
  voice transcript regression tests.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- No Customization Request storage, admin notifications, DB/storage request
  records, new canonical business actions, DecisionResolver changes,
  handler-local keyword matching, or deterministic phrase dictionary expansion
  as the main solution.
- LLM output must not choose final `response_mode`, decide Product Truth
  `primary_status`, return answer text, return canonical actions, draft
  requests, or create admin messages.
- Product Truth remains the only source of primary status, flags/context,
  limitations, setup requirements, forbidden claims, and safe next steps.

Touched scopes:
- InfoHelp resolver/service, unknown top-level text routing, idle voice
  transcript channel wiring, tests, and project log.
- No DB/storage/schema, admin notification, DecisionResolver, canonical action,
  customization storage, or handler-local keyword matching changes.

Current implementation status:
- LLM-backed bounded InfoHelp / Unknown-Triage resolver path: implemented as
  partial Level 2 foundation.
- InfoHelp Level 2: still not complete.
- Customization Request storage/admin notification: still unsupported runtime.

AI maturity:
- Partial Level 2 foundation only. Broader Level 2 still requires evaluated
  resolver behavior, voice/STT parity coverage beyond smoke, multilingual/noisy
  evals, and account-context-aware Product Truth evidence.

Out of scope:
- Runtime support claims beyond Product Truth.
- Request persistence, admin sends, new business actions, Product Truth status
  mutation, and self-learning.

Verification:
- Focused suite required:
  `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_product_truth.py`.
- Full suite required:
  `python -m pytest -q`.

## 2026-05-19 - Session 093 - Harden bounded InfoHelp triage regressions

Summary:
- Added regression coverage for bounded InfoHelp / Unknown-Triage v1.
- Covered unsupported triage class rejection, confidence bounds, invalid
  `topic_id` fallback, ignored model `response_mode`, ignored model
  `primary_status`, and ignored free-form `answer_text`.
- Added idle voice transcript triage coverage for new business feature
  requests, out-of-domain questions, smalltalk, unclear requests, and
  admin/customization candidates.
- Added voice regression proving final delete-database confirmation remains
  typed-only and does not call STT.
- Extended multilingual/noisy smoke coverage and action separation tests.
- Added a minimal parser hardening fix so an unsupported triage class cannot
  keep a model-provided topic as trusted output.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Prefer tests-only.
- No Customization Request storage, admin notification, DB/storage request
  records, new canonical business actions, DecisionResolver changes,
  handler-local keyword matching, or phrase dictionaries as main
  understanding.
- LLM output must not choose final response mode or decide Product Truth
  support status.

Touched scopes:
- Tests, project log, and one narrow `bot/services/info_help.py` parser
  validation fix.
- Runtime routing, handlers, DB/storage/schema, DecisionResolver, STT/LMM
  implementation, and Product Truth status are unchanged.

Current implementation status:
- Bounded Unknown / Discovery / Triage: v1 foundation implemented.
- Bounded InfoHelp resolver: partial foundation only, not complete Level 2.
- Customization Request storage/admin notification: unsupported runtime.
- InfoHelp Level 2: not complete.

AI maturity:
- Test hardening for a partial Level 2 foundation. This does not complete
  arbitrary capability-aware Q&A, request storage, self-learning, or
  code-agent handoff.

Out of scope:
- Runtime feature expansion.
- Broader deterministic phrase dictionaries.
- Persistence, admin notifications, new actions, and Product Truth status
  changes.

Verification:
- Focused suite required:
  `python -m pytest -q tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_product_truth.py tests/test_voice_state_routing.py`.
- Full suite required:
  `python -m pytest -q`.

## 2026-05-18 - Session 092 - Add bounded InfoHelp triage resolver foundation

Summary:
- Added bounded InfoHelp / Unknown / Discovery / Triage v1 classification.
- Resolver output is Python-owned structured data only:
  `capability_id`, `topic_id`, `triage_class`, `confidence`, and
  `needs_clarification`.
- Added validation that rejects invented capability IDs, invalid JSON, and
  free-form answer-only model output.
- Explicitly ignores model-provided support status and final `response_mode`;
  Python still derives answers from Product Truth primary status, flags/context,
  routing/FSM/account state, and safety policy.
- Wired triage only after active-state routing, direct top-level action
  resolution, and conservative Product Truth fast-paths.
- Added safe non-persistent responses for new business feature requests,
  customization/admin candidates, out-of-domain input, spam/noise, smalltalk,
  unclear text, and possible Product Truth candidates.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `bot/services/info_help.py`
- `bot/services/product_truth.py`
- `bot/services/semantic_action_resolver.py`
- `bot/handlers/invoice.py`
- `bot/handlers/voice.py`
- `tests/test_info_help.py`
- `tests/test_product_truth.py`
- `tests/test_invoice_intent_prerouter.py`
- `tests/test_voice_state_routing.py`

Constraints extracted:
- Classification only; no Customization Request storage, admin notification,
  DB/storage request records, new canonical business actions, DecisionResolver
  changes, handler-local keyword matching, or phrase dictionaries as the main
  understanding layer.
- LLM output must not choose final response mode or decide Product Truth
  support status.
- Product Truth remains authoritative for primary status, flags/context,
  limitations, setup requirements, forbidden claims, and safe next steps.

Touched scopes:
- InfoHelp service: yes.
- Product Truth `info_help` capability metadata: yes.
- Top-level routing: narrow integration after existing direct-action and
  Product Truth fast-path precedence.
- Shared semantic action resolver: tightened generic `urob/sprav` so it does
  not create invoices without an invoice target.
- Tests/docs/project log: yes.
- Confirmation, DecisionResolver, STT, LMM, FSM side effects, storage, DB,
  access, server, PDF/layout: unchanged.

Current implementation status:
- Product Truth MVP: implemented foundation.
- Deterministic Product Truth-backed InfoHelp fast-path: partial.
- Bounded Unknown / Discovery / Triage: v1 foundation implemented.
- Bounded InfoHelp resolver: partial foundation only, not complete Level 2.
- Customization Request storage/admin notification: unsupported runtime.
- InfoHelp Level 2: not complete.

AI maturity:
- Partial Level 2 foundation. This patch adds safe classification and
  rendering paths, but does not complete arbitrary capability-aware Q&A,
  request storage, self-learning, or code-agent handoff.

Out of scope:
- Customization Request persistence/admin send flow.
- New canonical actions.
- Product Truth status changes based on model output.
- Runtime storage/DB/schema changes.
- Broad multilingual production evaluation beyond focused tests.

Self-learning hooks considered:
- None implemented. Triage classifications are not learned or persisted.

Verification:
- Focused and full test commands required before commit:
  `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py`
  and `python -m pytest -q`.

## 2026-05-18 - Session 091 - Clarify InfoHelp response policy and Product Truth flags

Summary:
- Performed a docs-only consistency cleanup before bounded InfoHelp resolver
  implementation.
- Clarified that LLM output may classify into Python-provided
  capability/topic/triage options, but must not authoritatively choose the
  final `response_mode`.
- Documented that Python derives final response behavior from Product Truth
  `primary_status`, flags/context, account state, active FSM/routing state, and
  safety policy.
- Clarified Product Truth status model:
  `supported`, `partial`, `planned`, `unsupported`, and `unknown` are primary
  support statuses; `dangerous`, `requires_setup`, `requires_admin`, and
  `requires_external_credentials` are flags/context, not primary statuses.

Constraints:
- Documentation-only update.
- No runtime code, resolver, handlers, phrase dictionaries, DB/storage/schema,
  or customization request storage changes.
- InfoHelp Level 2 remains not complete.

Touched scopes:
- Product/AI/InfoHelp/LLM docs and project log only.
- Runtime code, routing, LLM execution, STT, FSM, storage, DB, access, server,
  and tests unchanged.

Verification:
- `git diff --check` is the required verification for this docs-only update.
- Runtime tests were not required because no code changed.

## 2026-05-17 - Session 090 - Document Unknown Discovery Triage layer

Summary:
- Added docs-only architecture guidance for the Unknown / Discovery / Triage
  layer before bounded InfoHelp resolver implementation.
- Clarified that `unknown capability_id` is not a final answer and must be
  triaged safely when auth/state/routing allow it.
- Defined the Python-owned triage classes:
  `known_product_capability`, `new_business_feature_request`,
  `customization_request_candidate`, `admin_review_candidate`,
  `out_of_domain`, `spam_or_abuse`, `smalltalk`,
  `unclear_needs_clarification`, `possible_product_truth_candidate`, and
  `unknown`.
- Documented the intended order: authorization, active FSM ownership, direct
  executable action resolver, known Product Truth capability/topic resolver,
  Unknown / Discovery / Triage resolver, then Python-controlled outcome.
- Added examples and eval expectations for known Product Truth, new business
  feature discovery, out-of-domain questions, spam/noise, smalltalk, unclear
  requests, and admin/developer candidates.

Reason:
- Prevent Product Truth from becoming only a search index over known
  capability IDs and preserve OfficeFlow/FakturaBot as a safe business
  discovery layer.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Product_Doctrine_2030.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Customization_Request_Layer.md`
- `docs/Self_Learning_Layer.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `bot/services/product_truth.py`
- `bot/services/info_help.py`
- `bot/services/semantic_action_resolver.py`
- `tests/test_info_help.py`
- `tests/test_product_truth.py`

Constraints extracted:
- Documentation-only update.
- No runtime code, resolver, handlers, phrase dictionaries, DB/storage/schema,
  or customization request storage changes.
- Unknown / Discovery / Triage may classify only into Python-owned classes and
  must not execute, save, notify, invent capability IDs, change Product Truth,
  or mark anything as supported.
- Direct executable actions and active FSM state remain higher priority than
  InfoHelp/triage.

Touched scopes:
- Product docs/contracts/eval artifact: yes.
- Runtime code, confirmation, routing, LLM, STT, LMM, FSM, storage, DB,
  access, server, PDF/layout: unchanged.

Current implementation status:
- Product Truth MVP: implemented foundation.
- Deterministic Product Truth-backed InfoHelp fast-path: partial.
- Unknown / Discovery / Triage layer: documented, not implemented.
- Bounded InfoHelp resolver: not complete.
- Customization Request storage: unsupported runtime.
- InfoHelp Level 2: not complete.

AI maturity:
- Design documentation only. No runtime maturity increase.

Out of scope:
- Bounded InfoHelp resolver implementation.
- Customization Request storage/admin notification flow.
- Self-learning triage patterns.
- Runtime telemetry.

Self-learning hooks considered:
- Documented as future only; no learning behavior added.

Verification:
- `git diff --check` is the required verification for this docs-only update.
- Runtime tests were not required because no code changed.

## 2026-05-17 - Session 089 - Align InfoHelp Product Truth status

Summary:
- Updated the `info_help` Product Truth capability record so it matches the
  current runtime after Sessions 087-088.
- Classified current InfoHelp as partial: selected conservative Product
  Truth-backed capability/safety topics plus Level 1 unknown-input guidance.
- Removed the stale forbidden claim that live Product Truth InfoHelp does not
  exist at all.
- Kept explicit forbidden claims against overstatement: complete Level 2,
  arbitrary capability Q&A, saved customization requests, and voice/STT parity.
- Added a focused registry regression test for the `info_help` record.

Contracts read:
- `AGENTS.md`
- `PROJECT_LOG.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `bot/services/product_truth.py`
- `tests/test_product_truth.py`
- `tests/test_info_help.py`
- `tests/test_invoice_intent_prerouter.py`

Constraints extracted:
- Product Truth must not claim roadmap or future capability as implemented.
- InfoHelp may be described only as a partial Level 2 foundation with
  deterministic fast-path coverage for selected topics.
- Full Level 2 still requires bounded InfoHelp resolver coverage, voice/STT
  parity, multilingual/noisy tests, and account-context-aware runtime evidence.
- Customization request storage and code-agent handoff remain unsupported.
- No resolver, handler, phrase dictionary, prompt, LLM/STT/LMM, DB/storage,
  access, server, or PDF/layout change belongs in this patch.

Touched scopes:
- Product Truth registry: yes, `info_help` capability metadata only.
- Tests: yes, registry-level status regression.
- Project log: yes.
- Confirmation, routing, handlers, LLM, STT, LMM, FSM, storage, DB, access,
  server, PDF/layout: unchanged.

Current implementation status:
- InfoHelp: partial.
- AI maturity: Level 2 foundation only, not complete Level 2.
- Customization requests: unsupported runtime storage.
- Code-agent handoff: unsupported runtime behavior.

Out of scope:
- Bounded InfoHelp resolver implementation.
- Broad arbitrary capability question support.
- Phrase dictionaries or handler-local keyword matching.
- Customization Request Layer storage.
- Voice/STT parity work.

Self-learning hooks considered:
- None added. Product Truth status metadata does not create learning behavior.

Product/user journey proof:
- Product Truth payloads now describe current InfoHelp honestly: selected
  supported fast-path coverage exists, but complete Level 2 is still not
  claimed.

User-facing product claim sources:
- `bot/services/product_truth.py`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/AI_Layer_Implementation_Standards.md`
- `PROJECT_LOG.md`

## 2026-05-17 - Session 088 - Product UX InfoHelp smoke fix-only patch

Summary:
- Implemented the approved fix-only service patch for six failed Level 2
  InfoHelp UX smoke phrases.
- Extended conservative InfoHelp topic matching for accounting export
  materials, PDF template customization, own/custom function requests,
  code-agent handoff wording, and delete-database safety questions.
- Tightened top-level edit intent fallback so persisted invoice editing
  requires invoice-edit semantics and no longer captures PDF template
  questions; `Uprav fakturu 15` resolves to existing `edit_existing_invoice`.
- Added focused service and prerouter regression tests proving Product Truth
  answers for the failed phrases and no invoice/edit/delete execution from
  informational questions.

Contracts read:
- `AGENTS.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Product_Truth_Layer.md`
- `bot/services/product_truth.py`
- `bot/services/info_help.py`
- `bot/services/semantic_action_resolver.py`
- `bot/handlers/invoice.py`
- `tests/test_info_help.py`
- `tests/test_invoice_intent_prerouter.py`

Constraints extracted:
- Product Truth remains the source for capability status and user-facing
  capability claims.
- InfoHelp may classify only known topic/capability IDs and must not execute
  actions.
- No new canonical action names, LLM classifier, prompt changes, handler-local
  business phrase dictionaries, DecisionResolver changes, or DB/storage/config
  changes belong in this patch.
- Direct destructive execution remains behind existing deterministic gates;
  delete-user-database final typed confirmation is unchanged.

Touched scopes:
- InfoHelp service: yes, conservative topic-bound Product Truth matching.
- Semantic action resolver: yes, narrowed top-level persisted-invoice edit
  fallback.
- Tests and project log: yes.
- `invoice.py`, handlers, DecisionResolver, prompts, LLM/STT/LMM integration,
  DB/storage/config, invoice/contact/accounting/supplier flows: unchanged.

Current implementation status:
- InfoHelp Level 2: partial, limited to controlled Product Truth topics.
- Accounting export, custom PDF templates, customization request storage, and
  code-agent handoff: unsupported runtime capabilities.
- Delete user database: supported but dangerous and confirmation-gated.
- Existing invoice edit: supported through `edit_existing_invoice`.

AI maturity:
- Level 2 partial. This patch fixes specific capability/safety smoke coverage
  without broad free-form classification, learning, or customization storage.

Out of scope:
- Broad semantic guessing, new actions, new prompts, handler routing changes,
  request persistence, code-agent execution, data migration, server changes,
  and product scope expansion.

Self-learning hooks considered:
- None added. These smoke phrases are fixed through controlled Product Truth
  topic matching, not learned aliases.

Product/user journey proof:
- Capability/safety questions receive Slovak Product Truth guidance with no
  hidden invoice/edit/delete side effects.
- Direct persisted invoice edit phrase still enters the existing bounded
  `edit_existing_invoice` route.

User-facing product claim sources:
- `bot/services/product_truth.py`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/llm/Canonical_Action_Registry.md`
- current runtime tests

Verification:
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_invoice_intent_prerouter.py` - 143 passed.
- `python -m pytest -q` - 1031 passed.

## 2026-05-17 - Session 087 - InfoHelp Level 2 first Product Truth wiring

Summary:
- Added the first Product Truth-aware InfoHelp runtime slice in
  `bot/services/info_help.py`.
- Added a conservative whitelist classifier for clearly informational
  capability/help questions and reserved unsupported send-invoice intent.
- Added Slovak Product Truth response rendering from structured registry
  payloads for supported, partial, unsupported, dangerous, and
  external-credential cases.
- Wired the existing idle invoice top-level path to Product Truth guidance only
  for unknown/reserved informational messages and narrow how-to/safety
  questions before existing action execution.
- Kept direct invoice/contact/accounting/supplier behavior, active FSM
  ownership, DecisionResolver semantics, prompts, LLM/STT/LMM calls, DB schema,
  storage, config, and Product Truth statuses unchanged.
- Updated `docs/evals/product_truth_infohelp_smoke.md` from scenarios-only to
  first partial automated Level 2 wiring coverage.

Contracts read:
- `AGENTS.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/evals/README.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `bot/services/product_truth.py`
- `bot/services/info_help.py`
- `bot/handlers/invoice.py`
- `bot/services/semantic_action_resolver.py`
- focused idle routing tests in `tests/test_invoice_intent_prerouter.py`

Constraints extracted:
- Product Truth remains the only source for capability truth.
- InfoHelp answers must be Slovak, structured, and side-effect free.
- No LLM classifier, prompt change, new canonical action, customization request
  storage, code-agent handoff, email/SMS/Google Drive/accounting-export
  implementation, or Product Truth status change belongs in this patch.
- Direct actions must remain direct actions; active FSM state must not fall
  through to idle InfoHelp.
- Reserved unsupported send-invoice intent must not become executable.

Touched scopes:
- InfoHelp service: yes, first Level 2 Product Truth renderer/classifier.
- Idle top-level invoice routing: narrow guidance hook only.
- Tests/eval/log: yes.
- Semantic resolver, DecisionResolver, active FSM flows, invoice/contact/
  accounting/supplier execution, delete-user-database final typed confirmation,
  prompts, LLM/STT/LMM, DB/storage/config/access/server/PDF layout: unchanged.

Current implementation status:
- InfoHelp Level 2: partial first runtime slice for conservative whitelisted
  topics only.
- Product Truth Registry: existing MVP foundation consumed by InfoHelp.
- Customization requests and code-agent handoff: unsupported runtime.
- Email, SMS, Google Drive, accounting export, and custom PDF templates:
  unsupported runtime capabilities.

AI maturity:
- Level 2 partial. The bot can answer selected capability/how-to/reserved
  questions from Product Truth, but broad arbitrary InfoHelp, customization
  request creation, topic learning, and code-agent handoff remain out of scope.

Out of scope:
- Broad semantic guessing.
- LLM-backed InfoHelp classification.
- Mutation from informational questions.
- Account-context DB reads for setup-aware handler answers.
- Any persisted data, storage, tenant, or authorization model change.

Verification:
- `python -m pytest -q tests/test_product_truth.py tests/test_info_help.py tests/test_invoice_intent_prerouter.py` - 131 passed.
- `python -m pytest -q` - 1019 passed.

## 2026-05-17 - Session 086 - Product Truth Registry MVP foundation

Summary:
- Added `bot/services/product_truth.py` as the first Python-owned runtime
  Product Truth registry foundation.
- Added the required MVP capability ids with primary product statuses limited
  to `supported`, `partial`, `planned`, `unsupported`, and `unknown`.
- Represented dangerous/setup/admin/external-credential facts as boolean
  flags, not as primary product statuses.
- Added structured query payloads for future InfoHelp consumption:
  `get_capability(...)`, `search_capabilities(...)`, and
  `get_safe_answer_payload(...)`.
- Added in-memory account-context merging so `create_invoice` can remain
  product-supported while returning account-level `requires_setup` when setup
  facts such as supplier profile, service alias, or contact are missing.
- Added `tests/test_product_truth.py` for registry validation, required ids,
  status constraints, forbidden claims, dangerous/external flags, account setup
  overlay, unknown lookup behavior, and side-effect import guards.
- Added `docs/evals/product_truth_infohelp_smoke.md` as scenarios only. It is
  explicitly marked not wired to runtime InfoHelp and not a completed Level 2
  InfoHelp eval result.

Contracts read:
- `AGENTS.md`
- `docs/Product_Truth_Layer.md`
- `docs/Product_Truth_Registry_MVP_Design.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/Product_UX_Eval_Artifacts.md`
- `docs/evals/README.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/TZ_FakturaBot.md`

Constraints extracted:
- Python remains the Product Truth source of truth.
- LLM output is not Product Truth and no LLM/STT/LMM call belongs in this
  foundation patch.
- Primary product status must describe availability only; dangerous,
  requires-setup, requires-admin, and requires-external-credentials are flags.
- InfoHelp must consume Product Truth later, but Level 2 InfoHelp is not
  implemented in this patch.
- Unsupported integrations such as email, SMS, Google Drive, accounting
  export, custom PDF templates, customization request storage, and code-agent
  handoff must not be claimed supported.
- Product Truth must not change invoice/contact/accounting/supplier runtime
  behavior or tenant/access boundaries.

Touched scopes:
- Product Truth registry foundation: yes;
- product UX eval scenarios: scenario artifact only;
- project log: yes;
- InfoHelp runtime, Telegram handlers, routing, semantic resolver, prompts,
  LLM/STT/LMM integration, FSM, DB, storage, config, invoice/contact/accounting
  behavior, supplier behavior, access, server, PDF/layout: no behavior changes.

Current implementation status:
- Product Truth Registry MVP foundation: partial runtime foundation
  implemented.
- InfoHelp: still Level 1 static fallback only; Level 2 capability-aware
  InfoHelp is not implemented.
- Customization requests and code-agent handoff: unsupported runtime.

AI maturity:
- This patch is below Level 2. It creates the controlled Product Truth source
  needed by future Level 2 InfoHelp but does not answer arbitrary capability
  questions in Telegram.

Out of scope:
- InfoHelp Level 2 routing/answers.
- Any LLM/STT/LMM calls or prompt changes.
- Any DB/storage/config/server changes.
- Any invoice/contact/accounting/supplier/runtime behavior changes.
- Any customization request storage or code-agent handoff.
- Any self-learning expansion. Existing confirmed alias learning remains
  partial and cannot change Product Truth.

Product/user journey proof:
- Unit tests prove registry load, schema/status rules, required capability ids,
  unsupported-feature honesty, dangerous/external flags, account setup overlay,
  unknown lookup, and no side-effect imports.
- Human-readable eval scenarios were recorded for future Product Truth +
  InfoHelp smoke checks, but they are not marked as run because InfoHelp is not
  wired to the registry yet.

Source-of-truth basis:
- Runtime-supported claims reference current code owners, active docs, and
  focused test files.
- Unsupported/partial/planned claims are backed by `docs/Product_Truth_Layer.md`,
  `docs/Product_Truth_Registry_MVP_Design.md`, `docs/TZ_FakturaBot.md`,
  `docs/llm/Canonical_Action_Registry.md`, and `PROJECT_LOG.md`.

Verification:
- `python -m pytest -q tests/test_product_truth.py` -> 12 passed.
- `python -m pytest -q` -> 1005 passed.

## 2026-05-17 - Session 085 - Documentation cleanup after architecture review

Summary:
- Accepted the external architecture review verdict as a cleanup backlog before
  runtime implementation.
- Updated `docs/TZ_FakturaBot.md` to remove stale active-truth claims around
  real outbound email support, align InfoHelp routing/status language with
  Product Truth, and split current accounting document intake Phase 1 from
  broader planned Document Intake.
- Updated `docs/llm/Canonical_Action_Registry.md` with explicit implemented
  rows for `edit_existing_invoice` and `delete_existing_invoice`, and clarified
  reserved `send_invoice` / `edit_invoice` behavior under Product Truth /
  InfoHelp rather than generic support.
- Updated `README.md` current-runtime date framing and added an explicit
  archive warning.
- Added `docs/Product_Truth_Registry_MVP_Design.md` and
  `docs/Product_UX_Eval_Artifacts.md` to define the first concrete registry and
  eval artifact conventions before runtime work.
- Added `docs/evals/README.md` as the placeholder/index for future eval
  artifacts.

Touched scopes:
- documentation/product truth cleanup: yes;
- action registry documentation: yes;
- Product Truth registry design and eval artifact convention: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only cleanup patch.

## 2026-05-17 - Session 084 - Top-level action Product Truth and InfoHelp sync gate

Summary:
- Updated `docs/llm/New_Action_Design_Checklist.md` so new or upgraded
  top-level canonical actions must synchronize Product Truth and InfoHelp /
  support guidance, not only action registries, TZ, README, and tests.
- Added explicit requirements for capability status, limitations,
  setup/admin/external-credential flags, forbidden claims, safe next steps,
  capability/how-to answer paths, and product UX evals for new actions.

Touched scopes:
- documentation/product direction: yes;
- top-level action implementation checklist: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 083 - General implementation agent checklist

Summary:
- Added `docs/Implementation_Agent_Checklist.md` as the general implementation
  gate for approved product/customization changes that are not necessarily new
  top-level canonical actions.
- The checklist requires agents to read governing docs, inspect current code
  ownership, decide whether to integrate into existing modules or create a new
  module, analyze Product Truth, data/migration, AI, FSM, access, PDF/layout,
  risks, tests, and product UX evals before coding.
- Updated `AGENTS.md`, `README.md`, `docs/Code_Agent_Handoff_Contract.md`,
  `docs/Customization_Request_Layer.md`, and
  `docs/Evaluation_and_Smoke_Test_Standards.md` to reference the new checklist.

Touched scopes:
- documentation/product direction: yes;
- implementation-agent checklist: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 082 - Evaluation and smoke test standards

Summary:
- Added `docs/Evaluation_and_Smoke_Test_Standards.md` as the mandatory
  evaluation contract for AI/product layers, Product Truth, InfoHelp,
  customization requests, self-learning, code-agent handoff, FSM recovery,
  access safety, document intake, PDF/layout, and migration/server checks.
- Clarified that unit tests are required but not sufficient for Level 2+
  AI/product layers; product UX evals and smoke scenarios must prove real user
  journeys, truthfulness, safety, state-awareness, and no hidden side effects.
- Updated `AGENTS.md`, `README.md`, `docs/Product_Doctrine_2030.md`,
  `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`,
  `docs/Info_Help_Guidance_Layer.md`, `docs/Customization_Request_Layer.md`,
  `docs/Self_Learning_Layer.md`, and `docs/Code_Agent_Handoff_Contract.md` to
  reference the new evaluation contract.

Touched scopes:
- documentation/product direction: yes;
- evaluation and smoke-test contract: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 081 - Self-learning and code-agent handoff contracts

Summary:
- Added `docs/Self_Learning_Layer.md` as the umbrella contract for controlled
  learning beyond current invoice customer/service aliases.
- Added `docs/Code_Agent_Handoff_Contract.md` as the contract for converting
  approved customization/product requests into bounded implementation tasks
  with docs, scope, tests, evals, no-go constraints, rollback notes, and human
  approval gates.
- Updated `docs/Confirmed_Semantic_Alias_Learning_Contract.md` to clarify that
  it remains the focused runtime contract for current confirmed aliases under
  the broader self-learning policy.
- Updated `AGENTS.md`, `README.md`, `docs/Product_Doctrine_2030.md`,
  `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`,
  `docs/Customization_Request_Layer.md`, and
  `docs/Info_Help_Guidance_Layer.md` to reference the new contracts.

Touched scopes:
- documentation/product direction: yes;
- self-learning and code-agent handoff contracts: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 080 - Product Truth and Customization Request contracts

Summary:
- Added `docs/Product_Truth_Layer.md` as the source-of-truth contract for
  supported/partial/planned/unsupported/unknown/dangerous/setup/admin/external
  credential capability answers.
- Added `docs/Customization_Request_Layer.md` as the contract for turning
  unsupported, partial, planned, unknown, or account-specific business needs
  into confirmed pending requests instead of fake promises or blind fallback.
- Updated `AGENTS.md`, `README.md`, `docs/Product_Doctrine_2030.md`,
  `docs/AI_Layer_Implementation_Standards.md`, and
  `docs/Info_Help_Guidance_Layer.md` to reference the new contracts.

Touched scopes:
- documentation/product direction: yes;
- Product Truth and customization request contracts: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 079 - AI layer standards and InfoHelp contract reset

Summary:
- Added `docs/AI_Layer_Implementation_Standards.md` as the mandatory maturity
  and acceptance contract for AI-facing product layers.
- Rewrote `docs/Info_Help_Guidance_Layer.md` from a Phase 1 fallback-oriented
  planning spec into a Level 2+ capability-aware support concierge contract.
- Clarified that current top-level InfoHelp fallback behavior remains Level 1
  only until Product Truth, capability-aware Q&A, customization request
  creation, controlled learning, and UX evals exist.
- Updated `AGENTS.md`, `README.md`, and `docs/Product_Doctrine_2030.md` so the
  new AI-layer standard is part of the active documentation set.

Touched scopes:
- documentation/product direction: yes;
- InfoHelp contract: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access,
  server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 078 - Archive superseded planning and audit docs

Summary:
- Moved superseded historical planning/audit/task docs out of the active documentation set:
  - `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` -> `docs/archive/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md`
  - `docs/Invoice_Draft_Review_Lifecycle_Design.md` -> `docs/archive/Invoice_Draft_Review_Lifecycle_Design.md`
  - `docs/llm/Confirmation_Decision_Audit_2026-04-14.md` -> `docs/archive/llm/Confirmation_Decision_Audit_2026-04-14.md`
  - `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md` -> `docs/archive/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`
- Updated `README.md` so active docs no longer list archived planning files as current planning docs.
- Updated `docs/archive/README.md` with the newly archived documents and their historical role.
- Updated `AGENTS.md` to state that `docs/archive/` is historical context only and must not be used as active source of truth.

Touched scopes:
- documentation organization: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access, server: no behavior changes.

Verification:
- Tests not run; documentation-only archive move.

## 2026-05-16 - Session 077 - Product doctrine and agent contract reset

Summary:
- Rewrote `AGENTS.md` as the main OfficeFlow/FakturaBot agent contract instead of a narrow Telegram-bot MVP instruction file.
- Added `docs/Product_Doctrine_2030.md` as the product north-star: OfficeFlow/FakturaBot is an AI-assisted business operating layer, not a command bot.
- Clarified the current runtime truth: controlled tenant-scoped multi-user runtime exists, while full SaaS, public signup, billing, per-client bot/runtime provisioning, and complex role/workspace administration remain not implemented.
- Preserved and strengthened existing safety rules: no invented project state, docs-first work, approval discipline, migration safety, Python-owned execution, DecisionResolver, access boundaries, OfficeFlow attachment boundaries, and project-log discipline.
- Added explicit AI-layer maturity language so static fallback/repair work cannot be called a completed AI product layer.
- Added Product Truth, customization request, self-learning, code-agent handoff, state-aware explanation, and product UX evaluation expectations as mandatory project direction.

Source material:
- `AGENTS.md`
- `PROJECT_LOG.md` read from first line to last line before the patch
- prior read-only audit context over the listed FakturaBot/OfficeFlow docs and runtime files

Touched scopes:
- documentation/product direction: yes;
- runtime code, routing, LLM/STT/LMM behavior, FSM, DB, storage, access, server: no behavior changes.

Verification:
- Tests not run; documentation-only patch.

## 2026-05-16 - Session 076 - Invoice edit fallback examples

Summary:
- Added an example date to invoice edit invalid-date recovery copy: `DD.MM.RRRR, napr. 15.03.2026`.
- Made invoice item numeric edit invalid-value recovery copy field-specific: quantity examples for `edit_item_quantity`, price examples for `edit_item_unit_price` and `edit_item_total_amount`.
- Kept the existing cancel hint unchanged: `Ak nechcete pokračovať v úprave, napíšte „zrušiť“.`
- Did not change InfoHelp, routing, DB/storage/PDF paths, LLM behavior, delete flows, `/start`, `/menu`, accounting/contact/service flows, or action switching.

Contracts read:
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/Canonical_Decision_Resolver_Contract.md`

Constraints extracted:
- active FSM state owns invoice edit recovery and must not fall through to top-level routing;
- invoice item quantity, unit price, and total amount edits are precision-sensitive exact-value steps;
- Python validates exact values and state data, while LLM/routing behavior remains out of scope;
- fallback copy must stay Slovak and preserve the existing state-cancel hint.

Touched scopes:
- FSM: yes, invoice edit fallback copy only;
- confirmation/routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_invoice_state_decisions.py` -> `71 passed`.
- `python -m pytest -q` -> `993 passed`.

## 2026-05-15 - Session 075 - Phase 1 top-level info help fallback

Summary:
- Added deterministic Phase 1 top-level `info_help` guidance for idle unknown text input.
- Routed idle voice unknown transcripts through the same `process_invoice_text(...)` unknown fallback guidance.
- Kept active FSM handlers, FSM recovery hints, global cancel, `/start`, `/menu`, delete database flow, DB schema, storage paths, invoice PDF paths, Google Drive, LMM/accounting extraction, action switching, and buttons/callbacks unchanged.
- Did not implement Phase 2/3 runtime explainability or LLM-backed help-topic resolution.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/Info_Help_Guidance_Layer.md`

Constraints extracted:
- top-level action resolution runs first and `info_help` may run only after a top-level miss;
- Phase 1 guidance must be deterministic/template-based and must not add a new LLM call;
- known top-level actions must continue through existing Python-owned routes;
- active FSM state must not fall through to top-level action routing or `info_help`;
- user-facing guidance must stay Slovak and must not claim planned Phase 2/3 explainability runtime exists.

Touched scopes:
- top-level routing: yes, unknown-only fallback copy through `process_invoice_text(...)`;
- voice: yes, idle voice benefits through the existing `process_invoice_text(...)` path only;
- FSM/confirmation/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_state_control.py` -> `152 passed`.
- `python -m pytest -q` -> `993 passed`.

## 2026-05-15 - Session 074 - Accounting and OfficeFlow recovery hints

Summary:
- Added Slovak cancel recovery hints to invalid/wrong-input accounting document intake fallbacks for upload waiting, duplicate decision, and preview decision states.
- Added Slovak cancel recovery hints to OfficeFlow idle attachment accounting proposal, route choice, and document-type clarification fallbacks.
- Kept successful paths, state transitions, temp staging lifecycle, cleanup behavior, LMM classification/extraction, confirmed accounting storage, Google Drive, DB schema, storage paths, invoice PDF paths, top-level `info_help`, and FSM action switching unchanged.

Contracts read:
- `AGENTS.md`
- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Canonical_Decision_Resolver_Contract.md`

Constraints extracted:
- active OfficeFlow/accounting FSM state remains owned by its state handlers and must not fall through to top-level action routing;
- Python keeps ownership of validation, confirmation, cleanup, and save side effects;
- temporary attachment/accounting staging paths remain temporary only and confirmed accounting storage is not touched by fallback copy changes;
- LMM classification/extraction, accounting categorization, Google Drive sync, DB schema, storage paths, and invoice PDF paths are out of scope;
- confirmation-like replies continue through the shared DecisionResolver families;
- user-facing fallback text must stay Slovak and should use `zrušiť` instead of `/start` for temp-staged flows.

Touched scopes:
- FSM: yes, invalid/wrong-input fallback copy only in accounting intake and OfficeFlow attachment routing states;
- confirmation: no new decision family, existing DecisionResolver calls unchanged;
- routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_accounting_document_intake_flow.py tests/test_officeflow_attachment_router.py tests/test_state_control.py` -> `65 passed`.
- `python -m pytest -q` -> `989 passed`.

## 2026-05-15 - Session 073 - Business FSM recovery hints

Summary:
- Added Slovak cancel recovery hints to invalid contact intake/manual contact fallbacks.
- Added Slovak cancel recovery hints to service alias empty-value fallbacks.
- Added Slovak cancel recovery hints to invoice exact-value edit fallbacks for service, invoice number, date, numeric, and item description values.
- Kept successful paths, state transitions, DB writes, PDF generation, storage paths, delete database flow, top-level `info_help`, and FSM action switching unchanged.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Canonical_Action_Registry.md`

Constraints extracted:
- active FSM state remains owned by its handler and must not execute top-level actions from invalid input;
- LLM may only do bounded canonicalization where already designed and must not become a free-form fallback;
- confirmation-like decisions stay routed through the shared DecisionResolver;
- exact business values remain text-first and Python-validated;
- user-facing fallback text must stay Slovak;
- no DB schema, storage path, invoice PDF path, delete database final gate, top-level `info_help`, FSM action switching, buttons/callbacks, Google Drive, accounting intake, or OfficeFlow router changes belong in this patch.

Touched scopes:
- FSM: yes, invalid-value/wrong-input fallback copy only in contact, service alias, and invoice exact-value edit states;
- confirmation: no new decision family, existing confirmation paths unchanged except unknown fallback copy;
- routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_contact_intake_semantic_flow.py tests/test_service_alias_flow.py tests/test_invoice_state_decisions.py tests/test_state_control.py` -> `99 passed`.
- `python -m pytest -q` -> `985 passed`.

## 2026-05-15 - Session 072 - Destructive and onboarding recovery hints

Summary:
- Added Slovak safe-exit hints to wrong-input destructive confirmation fallbacks for scoped database deletion and existing invoice deletion.
- Added Slovak cancel/restart hints to invalid-value onboarding steps without changing successful onboarding paths.
- Kept the exact database deletion confirmation phrase unchanged and preserved global `zrušiť` / `назад` cancellation behavior.
- Did not add top-level `info_help`, FSM action switching, buttons/callbacks, DB schema changes, storage path changes, or invoice PDF path changes.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/Info_Help_Guidance_Layer.md`

Constraints extracted:
- active FSM state remains owned by its current handler and must not execute top-level actions from invalid input;
- destructive delete confirmations must not mention `/start` and must preserve the final exact typed confirmation gate;
- non-destructive onboarding recovery may mention `/start` because active `/start` clears FSM state and restarts setup/status guidance;
- user-facing recovery text must stay Slovak;
- no DB schema, storage path, invoice PDF path, Google Drive, accounting intake, contacts, service alias, or general voice routing changes belong in this patch.

Touched scopes:
- FSM: yes, invalid-value/wrong-input fallback copy only;
- confirmation: yes, existing shared decision flows keep their current yes/no/exact gates;
- routing/LLM/STT/storage/DB/access/server: no behavior changes.

Verification:
- `python -m pytest -q tests/test_state_control.py tests/test_delete_user_database_flow.py tests/test_invoice_state_decisions.py tests/test_onboarding_decisions.py` -> `93 passed`.
- `python -m pytest -q` -> `982 passed`.

## 2026-05-15 - Session 071 - FSM recovery hints and deterministic exact cancel

Summary:
- Changed exact global cancel text shortcuts to run `cancel_current_state(...)` directly without entering the LLM-backed global cancel resolver.
- Kept `/cancel` and `/start` behavior unchanged: `/cancel` cancels active state, while `/start` clears active FSM state and shows the current start/status guidance.
- Added `назад` as a deterministic cancel/back-style shortcut because there is no separate back action in the current FSM architecture.
- Added Slovak recovery hints to invoice edit FSM menu/choice fallbacks so noisy input repeats the state-specific menu and explains `zrušiť` and `/start`.
- Did not add top-level `info_help`, FSM action switching, new buttons/callbacks, DB schema changes, storage path changes, or invoice PDF path changes.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/Info_Help_Guidance_Layer.md`

Constraints extracted:
- active FSM state remains owned by its state handlers and must not fall through to top-level routing;
- exact global cancel shortcuts are deterministic Python state control, not LLM interpretation;
- non-exact/bounded semantic interpretation may still use the existing resolver path where already designed;
- `info_help` remains planned/docs-only and is not implemented in this slice;
- user-facing recovery text must stay Slovak;
- `/start` is safe to mention as a restart because the active `/start` handler clears FSM state;
- final `delete_user_database` confirmation remains an exact typed-text gate and is unchanged;
- no DB schema, storage path, invoice PDF path, or persisted-data migration is involved.

Touched scopes:
- FSM: yes, invoice edit menu/choice fallback copy only;
- routing: yes, exact global cancel shortcut path and active-FSM top-level guard tests;
- LLM/STT: yes, exact text and exact STT transcript global cancel now bypass the LLM resolver;
- confirmation/state-control: yes, global state cancel behavior;
- storage/DB/access/server: no runtime behavior changes.

Verification:
- `python -m pytest -q tests/test_decision_resolver.py tests/test_state_control.py tests/test_voice_state_routing.py tests/test_invoice_intent_prerouter.py tests/test_invoice_state_decisions.py` -> `643 passed`.
- `python -m pytest -q` -> `982 passed`.

## 2026-05-09 - Session 070 - Profile edit return menu alignment

Summary:
- Reused the `/start` staged setup/status navigation after successful `/upravit_profil` saves.
- Ready users now see the main operational menu after profile edits, including create/view invoice options, instead of always being pointed back to `/sluzbu`.
- Added show/edit invoice wording to the advanced `/start` navigation.
- Expanded `/menu` into the broader user-facing capability list, including create/show/edit/delete existing invoice flows without exposing internal canonical tokens as slash commands.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `CHANGELOG.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- `/start` is the source of the staged setup/status menu for approved users;
- ready users should get the main operational menu, while incomplete users should see only the next missing setup step;
- `/menu` may list broader user-facing capabilities, but internal canonical tokens such as `edit_existing_invoice` must not be presented as Telegram slash commands;
- `/vymazat_databazu` menu wording must not imply a simple restart; the flow deletes scoped data and removes bot access until reapproval;
- profile edit exact values remain text-only and Python-validated;
- no new top-level action, DB schema, storage layout, access rule, or LLM prompt change is required.

Touched scopes:
- routing/FSM: yes, post-profile-edit response navigation only;
- access: no policy change, reused approved-user `/start` status logic;
- LLM/STT/confirmation/storage/DB/server: no.

Verification:
- `python -m pytest -q tests/test_access_request_flow.py tests/test_onboarding_decisions.py tests/test_delete_user_database_flow.py` -> `34 passed`.
- `python -m pytest -q` -> `983 passed`.

## 2026-05-09 - Session 069 - State reset and read-only invoice view

Summary:
- Added canonical top-level action `show_existing_invoice` for read-only viewing of an existing outgoing invoice by number/reference.
- Split “show/open invoice” from `edit_existing_invoice`: viewing sends the invoice summary/PDF and clears FSM state; editing still enters the bounded persisted invoice edit FSM.
- Added global state cancellation through `/cancel` and shared DecisionResolver-backed text/voice cancel wording (`zrušiť`, `скасувати`, `відмінити`, `відминити`, `отменить`, “почни з початку”).
- Made `/start`, `/menu`, existing `/moj_profil` display, and `/blocek` behave as stateless interruptions by clearing active FSM state where applicable.
- Kept persisted invoice edit cancellation safe: leaving `waiting_pdf_decision` after a persisted edit exits edit mode without deleting the stored invoice; newly generated unconfirmed invoice cancellation still uses existing cleanup.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `CHANGELOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Constraints extracted:
- new top-level actions require registry/docs/runtime/tests/voice reachability;
- active FSM state normally wins over idle routing, but explicit system/read-only commands may be state-clearing interruptions;
- confirmation/cancel-like wording must go through `bot/services/decision_resolver.py`;
- Python owns supplier-scoped invoice lookup, validation, FSM changes, DB/file side effects, and cleanup;
- voice may launch top-level actions but must not fill exact invoice numbers or destructive exact confirmations;
- temp Document Intake/OfficeFlow cleanup must remain restricted to approved temporary staging paths;
- no DB schema or storage layout migration is allowed in this slice.

Touched scopes:
- FSM: yes, global cancel and stateless read-only interruption behavior;
- routing: yes, new `show_existing_invoice` top-level route and `/start`/`/blocek` state reset behavior;
- LLM/STT: yes, bounded top-level action resolver, active-state voice cancellation, and voice reachability tests;
- confirmation/decision: yes, new `global_state_cancel` DecisionResolver family;
- storage: temporary intake cleanup only;
- DB: no schema changes, no migration; existing invoice read/delete behavior unchanged except safe persisted-edit cancel;
- access/server: no runtime server writes or access model changes; server logs were read-only inspected.

Verification:
- `python -m pytest -q tests\test_decision_resolver.py tests\test_invoice_intent_prerouter.py tests\test_voice_state_routing.py tests\test_access_request_flow.py tests\test_state_control.py` -> `579 passed`.
- `python -m pytest -q tests\test_voice_state_routing.py tests\test_state_control.py tests\test_decision_resolver.py` -> `463 passed`.
- `python -m pytest -q` -> `968 passed`.

## 2026-05-06 - Session 068 - Invoice service raw mention self-learning

Summary:
- Implemented confirmed semantic service alias learning for invoice service raw mentions extracted from text/STT.
- Added `ServiceAliasService` support for `confirmed_semantic_alias` domain `invoice_service`, target type `supplier_service_alias`, and a default cap of 10 aliases per service target per supplier/domain.
- Integrated confirmed service alias lookup into invoice service resolution after exact manual `/sluzbu` alias lookup and before bounded LLM fallback.
- Wired approved invoice previews to store safe `service_raw_mention` variants only when the service resolved to one existing manual service mapping.
- Kept `supplier_service_alias` as the manual `/sluzbu` table only; learned practical variants are not written there and do not rewrite service titles or invoice item descriptions.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`
- `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`

Constraints extracted:
- Python remains the only lookup, validation, persistence, and execution authority;
- LLM/STT may provide raw service mention candidates only;
- learned service aliases must target existing supplier-scoped manual service mappings;
- `supplier_service_alias` remains user-owned manual `/sluzbu` storage and must not receive learned variants;
- alias persistence requires approved invoice preview where the resolved service is visible;
- exact-value service alias creation remains text-only through `/sluzbu`;
- no DB schema, storage layout, access, server, or confirmation behavior change is required.

Touched scopes:
- invoice runtime/service lookup: yes;
- persisted DB rows: yes, existing `confirmed_semantic_alias` table only;
- LLM prompt/parser: no new prompt shape beyond existing `service_raw_mention`;
- confirmation: no behavior change, uses existing preview approval;
- FSM: no new states;
- DB schema/storage/access/server: no schema, storage, authorization, or server writes.

Verification:
- `python -m pytest -q tests/test_service_alias_service.py tests/test_invoice_phase2_ai_layer.py::test_preview_uses_service_raw_mention_as_alias_candidate tests/test_invoice_phase2_ai_layer.py::test_preview_rejects_full_command_as_service_alias_candidate tests/test_invoice_phase2_ai_layer.py::test_resolve_service_alias_bounded_uses_confirmed_semantic_alias tests/test_invoice_state_decisions.py::test_preview_approval_stores_confirmed_service_alias_from_raw_mention tests/test_invoice_state_decisions.py::test_preview_cancel_does_not_store_service_alias` -> `14 passed`.
- `python -m pytest -q` -> `948 passed`.

## 2026-05-06 - Session 067 - Invoice raw customer mention extraction

Summary:
- Added optional `biznis_sk.odberatel_raw_mention` to the invoice draft prompt as the source/STT phrase for the customer/company mention.
- Added optional `biznis_sk.service_raw_mention` and per-item `service_raw_mention` prompt/parser support as future-ready extraction fields only.
- Preserved normalized Python-facing fields: `odberatel_kandidat`, `polozka_povodna`, and `termin_sluzby_sk` remain the lookup/validation inputs.
- Allowed the invoice parser to keep the new optional raw mention fields without breaking older payloads.
- Wired only `odberatel_raw_mention` into existing contact alias learning as a safe candidate; alias persistence still happens only after preview approval or explicit alias confirmation.
- Added safety filtering so a full invoice command, amount/date/payment-like data, or command phrase is not stored as a contact alias candidate.
- Did not implement service confirmed-alias persistence; `/sluzbu` manual aliases and service runtime behavior remain unchanged.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`

Constraints extracted:
- Python remains the execution, lookup, validation, and persistence authority;
- LLM may extract raw/source mention candidates but must not create aliases or claim contact/service matches;
- raw aliases must come from isolated customer/service phrases, not full invoice commands;
- contact aliases may be stored only after preview approval or explicit confirmation;
- service semantic alias persistence is future work and must not write to `supplier_service_alias` in this slice;
- no DB schema, storage layout, access, or confirmation behavior change is required.

Touched scopes:
- LLM prompt: yes, invoice draft prompt shape;
- invoice parser/runtime: yes, optional fields and contact alias candidate selection;
- confirmation: no behavior change;
- FSM: no new states;
- DB/storage/access/server: no schema, storage, authorization, or server writes.

Verification:
- `python -m pytest -q tests/test_invoice_phase2_ai_layer.py tests/test_invoice_state_decisions.py::test_preview_approval_stores_confirmed_customer_alias tests/test_invoice_state_decisions.py::test_preview_approval_stores_confirmed_customer_alias_from_raw_mention tests/test_invoice_state_decisions.py::test_preview_cancel_does_not_store_customer_alias` -> `66 passed`.
- `python -m pytest -q` -> `940 passed`.

## 2026-05-06 - Session 066 - Runtime documentation tree and new-action checklist alignment

Summary:
- Updated the agent-facing top-level action completion gate: a new canonical top-level action is not considered implemented until the registry, Python route, resolver integration, text/command path, tests, and voice reachability or an explicit voice exclusion are covered.
- Reworked `docs/llm/New_Action_Design_Checklist.md` into a practical implementation guide for future top-level actions.
- Mined recurring project failure patterns from `PROJECT_LOG.md` into the checklist, including literal prompt matching, dead phrase dictionaries, voice gaps, FSM fallthrough, premature action exposure, `edit_invoice` vs `edit_existing_invoice` confusion, exact-value voice mistakes, and docs/runtime/test drift.
- Updated LLM/DecisionResolver contracts to reflect current Phase 2 runtime boundaries rather than treating Decision UI Phase 1 as the current endpoint.
- Updated the README into an architecture tree of runtime top-level actions, subflows, in-FSM controls, voice boundaries, and not-implemented areas.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

Constraints extracted:
- Python/FSM remains the execution authority; LLM may only canonicalize or draft within bounded allowed outputs;
- top-level voice coverage is part of implementation completeness unless the action is intentionally text/button/file-only;
- active FSM state wins over idle/top-level routing;
- exact values and destructive confirmations remain text-first;
- confirmation-like replies remain owned by the shared Canonical DecisionResolver;
- docs must not describe reserved or planned behavior as implemented runtime.

Touched scopes:
- routing/LLM/FSM/voice/confirmation docs: yes, documentation alignment only;
- runtime code, DB, storage, access, server: no changes.

## 2026-05-06 - Session 065 - Tenant storage migration gap and repair governance

Summary:
- Recorded the discovered tenant-scope data routing gap as a migration/repair issue, not as data loss.
- Server read-only inventory found existing confirmed accounting document originals and metadata JSON under legacy workspace `mykhailo-szco`.
- `/blocek` uses tenant-scoped recent-document routing, so it does not read legacy owner metadata from `mykhailo-szco`.
- Invoice DB rows exist, but some historical `invoice.pdf_path` values point to local Windows paths and are invalid on the Linux server.
- Server dry-run repair plan found 17 accounting metadata JSON files and 17 matching originals that can be copied from `mykhailo-szco` into the owner tenant workspace with metadata storage fields rewritten.
- Server dry-run found 3 invoice rows with Windows-local `pdf_path` values, but no unambiguous matching PDF files on the server for those invoice numbers, so invoice repair requires a separate decision or PDF regeneration.
- After explicit approval, the bloček repair was applied on the server: backup created under `/bot/repo/data/backups/tenant-storage-repair-20260506T111128Z`, 17 metadata JSON files and 17 originals copied into the owner tenant workspace, and 17 metadata storage blocks rewritten.
- Post-repair runtime registry validation returned 5 recent accounting documents for the owner tenant workspace; bad JSON and missing original references were 0.
- After explicit approval, invoice PDFs `20260003` and `20260004` were regenerated on the server from existing DB rows/items and their `invoice.pdf_path` values were updated to tenant-scoped server paths. Backup was created under `/bot/data/storage/backups/invoice-pdf-repair-20260506T134251Z`.
- Post-repair invoice path validation showed PDFs exist for `20260001`, `20260003`, `20260004`, `20260005`, and `20260006`; `20260002` remains a draft row with a historical Windows-local `pdf_path` and no matching server PDF.
- Added migration-sensitive data rules to `AGENTS.md`.
- Added `docs/FakturaBot_Data_Migration_Runbook.md` for audit, backup, dry-run, apply, and post-repair validation workflow.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/local-only/FakturaBot_Server_Agent_Context.md`

Constraints extracted:
- supplier profile data is DB-backed and scoped by `telegram_id`;
- outgoing invoices are DB-backed by `supplier_telegram_id`, while PDFs are resolved through persisted `invoice.pdf_path`;
- accounting documents consist of confirmed originals plus metadata JSON sidecars;
- recent accounting document view reads only confirmed metadata under the requesting tenant workspace;
- legacy `mykhailo-szco` must not become a cross-tenant fallback source in multi-user dry run;
- server-side data repair requires backup, dry-run, and explicit apply approval.

Touched scopes:
- confirmation/routing/LLM/FSM/access: no runtime behavior change;
- storage/DB: documented migration-sensitive issue and governance only;
- server: read-only inventory only, no data writes.

## 2026-05-06 - Session 064 - In-action voice control cleanup

Summary:
- Added voice routing for supplier profile field selection inside `SupplierProfileEditStates.field`.
- Added voice routing from `InvoiceStates.waiting_input` into the same invoice text processing path used by `/invoice` text input.
- Kept supplier profile value entry text-first; voice in `SupplierProfileEditStates.value` still asks for typed text.
- Changed contact missing-field intake voice handling to ask for typed text because that state captures business data values, not command choices.
- Changed invoice-number edit value voice handling to ask for typed text; voice can still choose the edit-number action in the previous bounded action-selection state.
- Added supplier profile field selection fallback through the shared Semantic Action Resolver after Python fast-path aliases fail.

Contracts read:
- `AGENTS.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`

Constraints extracted:
- Active FSM state wins over top-level routing;
- voice can control bounded state actions/field choices when Python supplies allowed outputs;
- exact value capture remains text-first for invoice numbers, identifiers, bank/email fields, numeric values, descriptions, and destructive confirmations;
- `voice.py` must not contain business phrase dictionaries.

Touched scopes:
- confirmation: no new confirmation family;
- routing/voice routing: yes, in-FSM voice routing only;
- LLM prompt behavior: no;
- FSM/DB/storage/access/server: no.

## 2026-05-06 - Session 063 - Supplier profile edit confirmation wording

Summary:
- Updated the targeted supplier profile edit confirmation message.
- Removed the inline `ano` / `nie` instruction from the message because the confirmation buttons already provide the available actions.
- Kept the shared `yes_no` DecisionResolver flow, FSM behavior, callbacks, DB writes, and access checks unchanged.

Contracts read:
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`

Constraints extracted:
- confirmation-like replies must continue through `bot/services/decision_resolver.py`;
- button callbacks must converge into the same state-aware confirmation handler;
- UI wording can change without adding local confirmation parsing or changing canonical decision outputs.

Touched scopes:
- confirmation: yes, UI wording only;
- routing/LLM/FSM/storage/DB/access/server: no behavior change.

## 2026-05-06 - Session 062 - STT transcription context prompt

Summary:
- Added a compact multilingual FakturaBot / OfficeFlow context prompt to the STT transcription call.
- The prompt tells the transcription model to expect Slovak, Ukrainian, Russian, English, and mixed Surzhyk / mixed Slovak-Ukrainian-Russian-English speech.
- The prompt explicitly keeps STT as transcription only: no translation, no summary, no conversion into commands, and no canonical action routing.
- Kept `voice.py`, semantic action routing, confirmation logic, FSM execution, DB, and storage unchanged.

Contracts read:
- `AGENTS.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`

Constraints extracted:
- Python authorization and tenant scoping must happen before STT/LLM/LMM;
- STT may produce only a raw transcript candidate;
- Python/FSM/DecisionResolver/Semantic Action Resolver remain responsible for state, routing, validation, and side effects;
- voice transport code must not become a business-command router.

Touched scopes:
- confirmation: no;
- routing/voice routing: no `voice.py` change;
- LLM/STT prompt behavior: yes, STT transcription prompt only;
- FSM/DB/storage/access/server: no.

## 2026-05-06 - Session 061 - Top-level LLM action context repair

Summary:
- Repaired top-level Semantic Action Resolver guidance so SK/UK/RU/mixed user input is interpreted into Slovak FakturaBot product semantics before choosing one allowed canonical action.
- Expanded `show_supplier_profile` and `edit_supplier` action context as supplier/company/business/billing profile semantics instead of narrow "profile" wording or command aliases.
- Kept `voice.py` unchanged; voice remains STT/state routing only.
- Adjusted tests so natural/polite top-level phrases with an API key exercise the bounded resolver path instead of requiring Python alias coverage.

Contracts read:
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Python defines `allowed_actions`, validates output, and executes existing routes;
- LLM canonicalizes multilingual/noisy input by internally normalizing the user meaning into Slovak FakturaBot product semantics within those bounds;
- `action_hints` are compact domain context, not keyword-parser replacement;
- deterministic aliases must remain a narrow fast path, not the primary voice reachability mechanism.

Touched scopes:
- confirmation: no;
- routing/voice routing: no `voice.py` change, but top-level semantic routing behavior is affected;
- LLM prompt behavior: yes;
- FSM/DB/storage/access/server: no.

## 2026-05-05 - Session 060 - Delete user database runtime flow

Summary:
- Implemented `delete_user_database` as a destructive leave/reset flow.
- Added `/vymazat_databazu` and bounded top-level text/voice intent routing that only start a Slovak warning + exact-confirmation FSM.
- Required exact typed confirmation phrase `vymazať databázu`; voice in the final confirmation state is rejected before STT and cannot delete.
- Added scoped deletion service for current user's supplier profile, contacts, invoices/items, service aliases, invoice-number settings, confirmed semantic aliases, tenant invoice PDFs, tenant workspaces, tenant upload staging dirs, and only contract files referenced by that user's contacts.
- Added `deleted_database` access/request status behavior: active access is revoked without removing the `authorized_users` row, future `/start` creates a new pending request, and `/approve` reactivates the user with old business data gone.
- Preserved `blocked` as admin-blocked, kept existing invoice delete flow unchanged, and did not touch `docs/llm/TASK_invoice_customer_raw_mention_for_alias_learning.md`.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Constraints extracted:
- Python owns authorization, tenant scope, deletion, and side effects;
- resolver/LLM may only classify `delete_user_database` when Python includes it in `allowed_actions`;
- final deletion confirmation is an exact typed destructive exception, not a yes/no DecisionResolver flow;
- voice must not pass final confirmation;
- deleted users are not authorized, including static allowlist users, until admin reapproval.

Touched scopes:
- confirmation: yes, exact typed destructive exception;
- routing/voice routing: yes;
- FSM: yes;
- LLM prompt behavior: no prompt file changes; bounded resolver remains allowed-actions only;
- DB/storage/access: yes;
- server/Git history: no.

Verification:
- `python -m pytest -q tests/test_delete_user_database_flow.py tests/test_access_request_flow.py` -> `23 passed`.
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_tenant_safety.py` -> `138 passed`.
- `python -m pytest -q tests/test_decision_resolver.py` -> `408 passed`.
- `python -m pytest -q` -> `926 passed`.

## 2026-05-05 - Session 059 - Top-level voice command reachability

Summary:
- Made existing canonical top-level/system actions voice-reachable through the shared Semantic Action Resolver and existing Python route handlers.
- Added bounded top-level routing for `start`, `show_supplier_profile`, `edit_supplier`, `show_recent_accounting_documents`, and `add_receipt`.
- Reused existing `/start`, `/moj_profil`, `/upravit_profil`, `/blocek`, and `/add_blocek`/`/dodat_blocek` flows instead of duplicating business logic.
- Kept `voice.py` as transport/STT/state routing only; it now refuses unhandled active FSM voice input with a text-required message instead of falling through to top-level routing.
- Kept `edit_invoice` as in-action/FSM invoice editing and preserved `edit_existing_invoice` for persisted invoice editing.
- Kept `add_receipt` as upload-waiting flow only: voice text does not create invoices, extract receipts, or save accounting documents.
- Did not expose or implement `delete_user_database`.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`

Constraints extracted:
- Python remains the execution and validation authority;
- resolver output must be one Python-allowed canonical token or `unknown`;
- `voice.py` must not contain business phrase dictionaries;
- confirmation-like replies must continue through `bot/services/decision_resolver.py`;
- exact/manual fields remain text-first;
- destructive/manual confirmation gates must not be weakened.

Touched scopes:
- confirmation: no new decision family;
- routing/voice routing: yes;
- FSM: yes, route reuse and active-state safety fallback only;
- LLM prompt behavior: no prompt file changes; bounded resolver payload remains strict;
- DB schema/storage model/server: no.

Verification:
- `python -m pytest -q tests/test_invoice_intent_prerouter.py tests/test_voice_state_routing.py tests/test_accounting_documents_handler.py tests/test_accounting_document_intake_flow.py tests/test_onboarding_decisions.py tests/test_decision_resolver.py` -> `579 passed`.
- `python -m pytest -q` -> `918 passed`.

## 2026-05-05 - Session 058 - Shared STT ano artifact fallback

Summary:
- Consolidated known spoken `áno` STT artifacts in the shared Canonical DecisionResolver/semantic lexicon layer.
- Normalized `Ah, não`, `Ah no`, `Ah ňao`, and `Ахняо` to affirmative `yes` for the `yes_no` family before LLM fallback.
- Kept invoice preview approve/edit/cancel behavior aligned so the same artifacts resolve to `approve` where `áno` is already an approve alias.
- Preserved standalone `no`, `nó`, `noo`, and `nou` as non-affirmative inputs; no handler dictionaries or button callback changes were added.

Contracts read:
- `AGENTS.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`

Constraints extracted:
- confirmation-like text and voice replies must pass through `bot/services/decision_resolver.py`;
- deterministic known STT artifacts must be handled in one shared resolver/lexicon layer;
- handlers must branch only on canonical outputs and must not define local confirmation dictionaries;
- LLM prompts must not change, and deterministic artifacts must not be routed to LLM.

Touched scopes:
- confirmation: yes;
- routing/callback routing: no;
- FSM: no;
- LLM prompt behavior: no;
- DB schema/storage model/server: no.

Verification:
- `python -m pytest -q tests\test_decision_resolver.py` -> `408 passed`.
- `python -m pytest -q` -> `904 passed`.

## 2026-05-05 - Session 057 - Decision UI Layer Phase 1

Summary:
- Added Telegram inline decision buttons for stable confirmation flows: invoice preview, invoice customer alias confirmation, invoice delete confirmation, contact confirmations, supplier onboarding confirmation, and supplier profile edit confirmation.
- Added a shared decision callback dispatcher that accepts only canonical Phase 1 callback tokens: `decision:yes`, `decision:no`, `decision:approve`, `decision:edit`, and `decision:cancel`.
- Kept text and voice confirmation replies on the Canonical DecisionResolver path; button callbacks skip LLM/STT/LMM and pass pre-canonicalized tokens into the same state-aware handler execution paths.
- Added callback-query authorization middleware so unauthorized or blocked users cannot trigger decision callback side effects.
- Left standalone contract save/archive buttons, OfficeFlow route/document-type buttons, `reupload`, and accounting-document edit buttons out of Phase 1.

Contracts read:
- `AGENTS.md`
- `docs/TZ_FakturaBot.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/User_Access_Model_Roadmap.md`

Constraints extracted:
- callbacks must emit canonical decision tokens only;
- callbacks must validate authorization and active FSM state before side effects;
- text/voice fallback must keep using `bot/services/decision_resolver.py`;
- LLM/STT/LMM must not run from button callbacks;
- unknown users must not create business data, temp files, storage paths, invoices, contacts, or documents.

Touched scopes:
- confirmation: yes;
- routing/callback routing: yes;
- FSM: yes;
- access: yes;
- LLM/STT/LMM prompts: no;
- DB schema/storage model/server: no.

Verification:
- `python -m pytest -q tests\test_decision_callbacks.py tests\test_access_request_flow.py tests\test_contact_intake_semantic_flow.py tests\test_onboarding_decisions.py tests\test_invoice_state_decisions.py -q` -> passed.
- `python -m pytest -q` -> `864 passed`.

## 2026-05-04 - Session 056 - Preview-approved contact alias learning

Summary:
- Changed supplier-scoped contact lookup so high-confidence customer-name variants such as missing-letter STT transcriptions can resolve to one safe local contact without a separate `áno / nie` alias prompt.
- Kept country-token guardrails: explicit `CZ` does not silently match `SK`, and multiple plausible country variants remain ambiguous.
- Added preview-approved alias learning: when fuzzy or bounded LLM customer resolution is used in the invoice preview, the cleaned customer candidate is stored as a confirmed alias only after the user approves the invoice preview.
- Kept raw full STT/request text out of alias storage and left unrelated low-similarity contacts from forcing clarification.

Contracts read:
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`

Verification:
- `python -m compileall bot\services bot\handlers` -> passed.
- `python -m pytest -q tests\test_contact_lookup_normalization.py tests\test_invoice_phase2_ai_layer.py tests\test_invoice_state_decisions.py` -> `142 passed`.
- `python -m pytest -q` -> `858 passed`.

## 2026-05-04 - Session 055 - Alias confirmation STT retry guard

Summary:
- Treated ambiguous STT yes/no noise such as `Ah non !` narrowly as `unknown` in `invoice_customer_alias_confirm`, before LLM fallback can misread it as a real `no`.
- Kept real `nie` / `no` behavior unchanged for the alias confirmation flow.
- Changed alias confirmation `unknown` handling to keep the same FSM state: first unclear reply asks the user to try again with `áno / nie` or `yes / no`; repeated unclear reply asks for a text answer.
- Added structured `invoice_customer_alias_confirm_resolved` logging with decision and retry count.

Contracts read:
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`

Verification:
- `python -m compileall bot\services bot\handlers` -> passed.
- `python -m pytest -q tests\test_decision_resolver.py tests\test_invoice_phase2_ai_layer.py` -> `428 passed`.

## 2026-05-04 - Session 054 - Staged user onboarding profile commands

Summary:
- Updated admin approval notification so the approved user is told access was approved, their FakturaBot working database is ready, and the next action is `/start`.
- Changed `/start` into a staged setup/status router: `/moj_profil` for approved users without profile, `/sluzbu` after profile, `/contact` after service aliases, and an advanced menu after profile + service aliases + contacts.
- Added `/moj_profil` as the user-facing supplier profile surface: it starts profile creation when missing and shows a read-only profile summary when present.
- Added `/upravit_profil` for targeted one-field supplier profile edits with Python validation and shared `yes_no` DecisionResolver confirmation context `supplier_profile_edit_confirm`.
- Changed post-profile onboarding guidance to point only to `/sluzbu` as the next staged step, instead of showing service/contact/invoice commands together.
- Added `/sluzbu` as the primary user-facing service-alias command while preserving `/service` and `/alias`.
- Added `/blocek` as the user-facing recent receipts/accounting-documents view, while preserving legacy `/blocky`.
- Added `/add_blocek` and `/dodat_blocek` as user-facing commands for adding a new receipt/blocek through the existing accounting Document Intake flow; `/doklad` remains legacy/reserved and is not promoted in `/start`.
- Updated missing-profile guidance from `/supplier` to `/moj_profil` in invoice/contact/document-intake paths.
- Documented `delete_user_database` as the reserved destructive top-level action for a follow-up hard-delete implementation; no hard-delete runtime was implemented in this session.

Contracts read:
- `docs/TZ_FakturaBot.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/OfficeFlow_Architecture_Framing.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`
- `docs/Document_Intake_MVP_Implementation_Plan.md`

Verification:
- `python -m pytest -q tests\test_access_request_flow.py tests\test_onboarding_decisions.py tests\test_service_alias_flow.py tests\test_decision_resolver.py tests\test_accounting_documents_handler.py tests\test_accounting_document_intake_flow.py` -> `425 passed`.
- `python -m pytest -q` -> `852 passed`.

## 2026-05-03 - Session 053 - Confirmed customer alias learning

Summary:
- Added a reusable confirmed semantic alias contract for bounded, user-confirmed alias learning.
- Added a supplier-scoped `confirmed_semantic_alias` table for aliases learned only after explicit confirmation.
- Integrated confirmed customer aliases into the existing `ContactService.resolve_contact_lookup(...)` path instead of adding a separate invoice lookup.
- Added invoice customer alias confirmation: when one safe close customer candidate is found, the bot asks a shared `yes_no` DecisionResolver question and saves only the cleaned extracted customer candidate after `yes`.
- Kept raw STT transcripts out of alias storage and preserved country-token safety: explicit `CZ` does not silently match stored `SK`.
- Added a service-layer supplier-scope guard so aliases cannot be created for another supplier's contact id.
- Added voice routing for the new alias-confirmation FSM state.

Contracts read:
- `docs/TZ_FakturaBot.md`
- `PROJECT_LOG.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `docs/llm/New_Action_Design_Checklist.md`

Verification:
- `python -m compileall bot\services bot\handlers` -> passed.
- `python -m pytest -q tests\test_contact_lookup_normalization.py tests\test_invoice_phase2_ai_layer.py tests\test_voice_state_routing.py tests\test_decision_resolver.py` -> `448 passed`.
- `python -m pytest -q` -> `826 passed`.

## 2026-05-03 - Session 052 - Voice delete intent and STT confirmation noise

Summary:
- Hardened top-level invoice intent routing so explicit delete phrases such as `udalit fakturu 10`, `vidaly fakturu 11`, `vymaz fakturu 7`, or noisy STT variants are routed to `delete_existing_invoice` before generic invoice creation.
- Kept deletion outside `create_invoice`; delete remains a separate bounded top-level action and still requires explicit `yes_no` confirmation before any destructive DB/PDF action.
- Added a narrow confirmation fallback for the observed STT pattern `Ah, nao` / `Ah, nao!` as Slovak `ano`, without adding broad Portuguese-language support.
- Added `top_level_intent_resolved` logs so server diagnostics show the canonical top-level intent selected for voice/text inputs.

Verification:
- `python -m pytest -q tests\test_invoice_intent_prerouter.py tests\test_decision_resolver.py tests\test_invoice_state_decisions.py tests\test_contact_intake_semantic_flow.py tests\test_accounting_document_intake_flow.py tests\test_officeflow_attachment_router.py` -> `561 passed`.
- `python -m pytest -q` -> `804 passed`.

## 2026-05-03 - Session 051 - Contact address validation and optional customer email

Summary:
- Made customer/contact email optional in manual and document/semantic contact intake.
- Kept DB schema unchanged by storing an omitted contact email as an empty string.
- Added contact address validation requiring a house/building number, so incomplete addresses such as city-only or street-only values do not pass confirmation.
- Updated contact intake missing-field behavior so missing email no longer blocks contact save, while incomplete address still requires clarification.
- Updated invoice PDF customer block rendering so the customer `Email:` line is omitted when contact email is empty.

Verification:
- `python -m pytest -q tests\test_contact_intake_semantic_flow.py tests\test_pdf_generator_layout_wrapping.py` -> `28 passed`.
- `python -m pytest -q` -> `801 passed`.

## 2026-05-03 - Session 050 - Supplier onboarding saved next-step guidance

Summary:
- Updated the successful `/supplier` completion message so the user is told what to do after the supplier profile is saved.
- The message now starts with `/alias`, then points the user to `/contact`, then `/invoice` or text/voice invoice creation.
- Added `/alias` as a command alias for the existing service-alias flow; `/service` remains supported.
- Updated `/start` for users with an existing supplier profile to show the same operational next steps.
- Clarified that `/alias` means short service name -> full invoice/PDF service title, for example `opravy` -> `Opravy vyhradených zariadení elektrických`.
- User-facing guidance now says these flows can be started by Slovak voice/text examples such as `dodaj novú službu` and `dodaj nový kontakt`.
- Kept the supplier save confirmation on the existing shared DecisionResolver path; no DB schema, access model, LLM, STT, LMM, storage, or invoice numbering changes.

Verification:
- `python -m pytest -q tests\test_onboarding_decisions.py tests\test_access_request_flow.py tests\test_service_alias_flow.py` -> `16 passed`.
- `python -m pytest -q` -> `796 passed`.

## 2026-05-03 - Session 049 - Supplier onboarding first invoice number and SMTP schema repair

Summary:
- Fixed the new-user supplier save failure seen on the server by migrating legacy `supplier.smtp_host`, `supplier.smtp_user`, and `supplier.smtp_pass` `NOT NULL` columns to nullable columns during `init_db()`.
- Added a tenant-scoped `invoice_number_settings` table for the first invoice number FakturaBot should generate per supplier/year.
- Extended `/supplier` onboarding: after email, the bot now asks for the first invoice number for the current year, then asks the default due-days question as the last step.
- Invoice numbering now starts from the configured first number for a supplier/year and then continues from the larger of existing bot invoices or that configured first number.
- No historical invoice import or automatic fake invoice creation was added.

Verification:
- `python -m pytest -q tests\test_onboarding_no_smtp.py tests\test_onboarding_decisions.py tests\test_tenant_safety.py tests\test_supplier_smtp_optional.py` -> `15 passed`.
- `python -m pytest -q` -> `794 passed`.

## 2026-05-03 - Session 048 - Access approval onboarding next step

Summary:
- Updated `/approve <telegram_id>` so the approved user receives a direct bot message after approval.
- Reused the same next-step text for `/approve` notification and `/start` when an approved user has no supplier profile yet.
- The approved-user message tells the user that access is approved and that `/supplier` is the next command when they are ready to enter supplier registration data.
- Kept supplier onboarding explicit: approval does not create a supplier profile, tenant business data, invoices, documents, temp files, or AI/STT/LMM calls.
- Added masked access approval notification logs for server diagnostics.

Verification:
- `python -m pytest -q tests\test_access_request_flow.py` -> `11 passed`.
- `python -m pytest -q` -> `791 passed`.

## 2026-05-02 - Session 047 - Admin command text aliases

Summary:
- Added deterministic text aliases for admin access commands:
  - `користувачі` for `/users`;
  - `запит` and `запрос` for `/access_requests`.
- Kept aliases admin-only by recognizing them in the authorization middleware as admin command equivalents before handler routing.
- Added tests for direct alias handlers and middleware pass-through for bootstrap admins.

Verification:
- `python -m pytest -q tests\test_access_request_flow.py` -> `9 passed`.

## 2026-05-02 - Session 046 - Controlled access-request onboarding

Audit summary:
- User-facing entry points remain centrally protected by Telegram authorization middleware before `/start`, `/supplier`, invoice, contact, accounting-document intake, OfficeFlow attachment routing, voice/STT, text pre-routing, and other mutating handlers can run.
- The previous static `ALLOWED_TELEGRAM_USER_IDS` model was safe for the two-user dry run but operationally inconvenient for additional access requests.
- Unknown users must not create supplier profiles, contacts, invoices, accounting documents, temp storage workspaces, or trigger LLM/STT/LMM calls.
- Admin access management must remain deterministic Python logic and must not be routed through LLM/STT/LMM.

Summary:
- Added `ADMIN_TELEGRAM_USER_IDS` config parsing while preserving `ALLOWED_TELEGRAM_USER_IDS` as bootstrap/static access.
- Added persistent `access_requests` and `authorized_users` tables through `init_db()` with fail-loud compatibility checks and no destructive migration.
- Added `AccessControlService` for pending requests, approvals, rejections, blocking, active-user checks, and admin checks.
- Updated authorization middleware so unknown `/start` creates or refreshes only a minimal pending access request, sends a neutral Slovak access message, and optionally notifies configured admins.
- Added admin-only `/access_requests`, `/approve <telegram_id>`, `/reject <telegram_id>`, `/block <telegram_id>`, and `/users` commands.
- Preserved local/test behavior when both `ALLOWED_TELEGRAM_USER_IDS` and `ADMIN_TELEGRAM_USER_IDS` are empty.
- Updated docs to describe controlled access requests, admin approval, bootstrap allowlists/admins, one-bot model, and the no-public-signup boundary.

Verification:
- `python -m pytest -q tests\test_access_request_flow.py tests\test_tenant_safety.py` -> `13 passed`.
- `python -m pytest -q` -> `787 passed`.

Notes:
- This is not public self-service signup and does not add billing, payments, SaaS dashboard, multiple bot tokens, Postmark, email/password accounts, or full tenant provisioning.
- Blocked users keep existing data but cannot pass the authorization guard.

## 2026-05-02 - Session 045 - User access rollout phases documented

Summary:
- Added `docs/User_Access_Model_Roadmap.md` to separate Phase 1 static allowlist dry run, Phase 2 admin-approved access request automation, and Phase 3 future commercial deployment.
- Updated the server rollout roadmap to state that the current second-user dry run uses one shared Telegram bot token, one backend, one SQLite DB, and `ALLOWED_TELEGRAM_USER_IDS`.
- Reframed the TZ deployment section so the current shared-bot controlled dry run is distinct from the future commercial/per-client installation model.
- Added a local-only safe `docs/local-only/New_User_Onboarding_Checklist.md` checklist with no real Telegram IDs, tokens, names, or private client data.
- Preserved the future per-client bot/VPS/container/DB/storage/API-key model as out of scope for the current dry run and Phase 2 access-request work.
- Strengthened the documentation-only wording so Phase 2 is treated as planned/not implemented unless current code, tests, and `PROJECT_LOG.md` separately confirm implementation.

Verification:
- Documentation-only change; tests not run.

## 2026-05-02 - Session 044 - Minimal tenant-safety hardening for controlled two-user dry run

Audit summary:
- User-facing Telegram entry points include `/start`, `/supplier`/onboarding, invoice creation and edit/delete/view flows, contact flows, accounting document intake, OfficeFlow idle attachment routing, voice routing, and generic text/document pre-routing.
- Supplier profile access was already keyed by `telegram_id`; contact list/name flows were supplier-scoped, while invoice PDF rebuild/display paths still used unscoped contact lookup and were changed to scoped lookup.
- Invoice number generation and DB uniqueness were global; this was changed to tenant-aware `UNIQUE(supplier_telegram_id, invoice_number)` with per-supplier generation and availability checks.
- Existing invoice edit/delete/view resolution already used supplier-scoped number reference matching in the main pre-router; persisted edit subflows were hardened to reload invoices by current `supplier_telegram_id` before mutations.
- Invoice PDF storage was flat by `invoice_number`; it is now tenant-scoped under `storage/invoices/{supplier_telegram_id}/{invoice_number}.pdf`.
- Accounting document confirmed storage, duplicate detection, recent-document views, and temp staging previously used a fixed workspace/default temp path; runtime paths now pass the current Telegram user and use tenant workspaces such as `telegram-{supplier_telegram_id}`.
- Legacy supplier SMTP fields (`smtp_host`, `smtp_user`, `smtp_pass`) existed and onboarding collected them historically; onboarding now collects only business email and saves SMTP fields as `None`.
- LLM/STT/LMM cost boundary is now protected by centralized Telegram user authorization middleware before handlers run.

Summary:
- Added `ALLOWED_TELEGRAM_USER_IDS` config parsing and centralized Telegram user authorization middleware with neutral unauthorized response.
- Registered authorization middleware in `bot/main.py` so unauthorized users are blocked before onboarding, contacts, invoices, accounting intake, OfficeFlow attachment routing, voice/STT, LLM, and LMM handler work.
- Changed invoice schema/bootstrap to migrate from global invoice-number uniqueness to tenant-aware uniqueness, retaining existing rows and documenting the need for DB backup before rollout.
- Updated invoice number generation, availability checks, invoice lookup-by-number, invoice PDF paths, contact lookups during invoice PDF rebuild, and persisted invoice edit/delete flows to respect the requesting Telegram user.
- Added tenant-scoped accounting document temp storage, confirmed storage metadata, duplicate checks, and recent-document views.
- Deprecated per-user SMTP credential collection in onboarding while keeping DB columns for compatibility.
- Updated docs with the controlled two-user model, allowlist requirement, tenant-scoped storage rules, SMTP purge SQL, and out-of-scope items.

Migration note:
- `init_db()` now rebuilds the `invoice` table when it detects the legacy global `UNIQUE(invoice_number)` shape and recreates it with `UNIQUE(supplier_telegram_id, invoice_number)`.
- Before server rollout, back up the SQLite DB and storage directory. Rollback risk is mainly schema rollback/manual restore if the live DB contains unexpected duplicate rows for the same supplier and invoice number.
- Existing legacy SMTP values should be purged after backup with:

```sql
UPDATE supplier
SET smtp_host = NULL,
    smtp_user = NULL,
    smtp_pass = NULL;
```

Verification:
- `python -m pytest -q tests\test_tenant_safety.py tests\test_accounting_document_storage.py tests\test_accounting_document_duplicates.py tests\test_accounting_document_registry.py tests\test_onboarding_decisions.py tests\test_onboarding_no_smtp.py` -> `37 passed`.
- `python -m pytest -q` -> `780 passed`.

Notes:
- This is not full SaaS multi-tenancy.
- Out of scope remains multiple bot-token orchestration, workspace admin UI, billing, Postmark integration, encrypted tenant secret vault, bank-statement matching, and expense categorization.
- Python remains the execution authority; LLM/STT/LMM does not decide authorization, tenant identity, DB scoping, invoice numbering, file paths, or persistence.

## 2026-05-02 - Session 043 - Canonical DecisionResolver matrix tests

Summary:
- Added central Canonical DecisionResolver test registries for yes/no and approve/edit/cancel confirmation contexts.
- Added exact multilingual/noisy/STT-like contract matrices covering existing FakturaBot and OfficeFlow confirmation contexts.
- Added a static handler guard against local confirmation token parsers in `bot/handlers/*.py`.
- Updated the shared resolver fallback to cover newly contracted Slovak/Cyrillic-compatible variants such as `potvrď`, `zmeniť`, and `zahodiť`.
- Updated `docs/Canonical_Decision_Resolver_Contract.md` to require new confirmation-like flows to register their `context_name` in the central test matrix.

Verification:
- `python -m pytest -q tests\test_decision_resolver.py` -> `340 passed`.
- `python -m pytest -q` -> `753 passed`.

Notes:
- No DB schema, storage behavior, invoice PDF path behavior, deployment scripts, or server state was changed.
- No handler-local confirmation parser was added.

## 2026-05-02 - Session 042 - Server rollout roadmap audit and priorities

Summary:
- Audited `docs/FakturaBot_Server_Rollout_Roadmap.md` against the current README, project log, repo deployment files, and local-only server context.
- Reworked the roadmap from a target-only plan into a current audit with stage statuses: done/partial/not started/future.
- Added prioritized rollout tasks for owner-run baseline, DB/storage migration discipline, dependency management, tenant contract, manual onboarding, multi-bot routing, and first external dry run.
- Clarified that the project currently has no full DB migration system; current behavior is bootstrap/fail-loud with one compatible `ALTER TABLE` path, and the next schema/storage change needs an explicit migration plan.
- Clarified that moving from `requirements.txt` to `uv` is a P1 dependency-management decision, not a blocker for owner-run or first dry run and not the same risk category as DB migration.

Verification:
- Documentation-only change; tests not run.

Notes:
- No runtime code, DB schema, storage behavior, deployment script, server state, or dependency file was changed.
- Real server actions still require checking `docs/local-only/FakturaBot_Server_Agent_Context.md` first.

## 2026-05-02 - Session 041 - Docs archive correction and README refresh

Summary:
- Audited markdown documents at repo root, `docs/`, `docs/llm/`, `docs/local-only/`, and `docs/archive/` for current role/status.
- Rewrote `README.md` as a current navigation/status document instead of the outdated Phase 4 snapshot.
- Added `docs/archive/README.md` to mark archived documents as historical context, not current sources of truth.
- Moved the old root `FakturaBot_Implementation_Phases_Spec.md` into `docs/archive/`.
- Moved `docs/PayBySquare_Research_Spike.md` and `docs/PayBySquare_Manual_Verification_Checklist.md` into `docs/archive/`.
- Kept active README references to archived Pay by Square rationale/manual QR scan verification materials.

Verification:
- Documentation/file organization only; tests not run.

Notes:
- Current source-of-truth order remains `docs/TZ_FakturaBot.md`, `PROJECT_LOG.md`, current code, then `CHANGELOG.md`.
- No runtime code, DB schema, storage behavior, invoice flow, or Pay by Square implementation was changed.
- README now explicitly says real SMTP/email sending, standalone `save_contract`, full OfficeFlow workspace runtime, Google Drive sync, bank matching, full OCR, and multi-tenant SaaS runtime are not implemented.

## 2026-05-01 - Session 070 - Local Codex Windows sandbox ACL fix documented

Summary:
- Documented the resolved local Windows Codex elevated sandbox setup failure that occurred before shell command execution with `windows sandbox: setup refresh failed with status exit code: 1`.
- Root cause was unsafe Windows ACL/world-writable paths on the local machine, not project code.
- Removed `C:\Users\Public\KROS`.
- Fixed the `D:\` root ACL by removing `Everyone:(OI)(CI)(F)` inheritance and keeping normal access for the current user, Administrators, SYSTEM, and Users read/execute.
- Cleaned unsafe ACLs on `C:\$360Section`.
- Reset old Codex sandbox state: `.codex\.sandbox`, `cap_sid`, and `sandbox.log`.
- The known local Windows ACL-related sandbox setup failure was resolved and verified.

Verification:
- `Get-Location` -> `D:\AI_Model\Ai_assistant`
- `python --version` -> `Python 3.12.0`
- `python -m pytest -q` -> `373 passed in 13.20s`

Conclusion:
- Sandbox/tooling issue resolved; project tests are green.
- For this repository, the confirmed test command is `python -m pytest -q` from `D:\AI_Model\Ai_assistant`.
- Avoid bare `pytest -q` because it may not include the project root on `sys.path` and can fail during collection with `ModuleNotFoundError: No module named 'bot'`.

## 2026-05-01 — Session 069 — Document Intake real Telegram file payload wiring

Summary:
- Hardened `/doklad` accounting intake so real Telegram photo/PDF downloads are passed into `accounting_document_lmm.py` as file bytes.
- Updated the LMM wrapper to send images as Chat Completions `image_url` data URLs and PDFs as `file` payloads with base64 `file_data`, while keeping strict JSON parser boundaries.
- Added size/mime guards before provider calls and kept provider behavior fully mockable in tests.
- Added user-facing handling for unknown classification, parser/provider errors, and poor readability/blurred documents.
- Added temp staging cleanup after unknown/poor/error paths, cancel, and confirmed save copy.
- No DB schema changes, invoice flow changes, bank matching, Google Drive sync, Zevs runtime profile, `storage/invoices` changes, or `pdf_path` behavior changes were made.

Tests:
- Focused accounting document suite: `52 passed`.
- Full suite: `373 passed`.

## 2026-05-01 — Session 068 — Document Intake Phase 1 Slice 4 explicit Telegram intake

Summary:
- Added an explicit accounting document intake FSM entered only by `/doklad`, `/expense`, or `/intake`.
- Added state-scoped photo/PDF upload handling for receipts and incoming invoices, with temp staging under `storage/uploads/accounting_intake/`.
- Wired Slice 4 to the existing accounting document LMM wrapper, Python validation, Slovak preview, shared `resolve_approve_edit_cancel(...)`, and confirmed JSON-sidecar storage.
- Registered the router without broad idle attachment interception; uploads outside the active intake state are not processed by this router.
- Kept edit as a bounded not-yet-implemented response for this slice.
- No bank matching, DB schema changes, Google Drive sync, Zevs runtime profile, supplier profile changes, invoice flow changes, `storage/invoices` changes, or `pdf_path` behavior changes were made.

Tests:
- Focused Document Intake Slice 1-4 suite: `44 passed`.
- Full suite: `365 passed`.

## 2026-05-01 — Session 067 — Document Intake Phase 1 Slice 3 LMM boundary

Summary:
- Added `bot/services/accounting_document_lmm.py` as an isolated, mockable LMM wrapper for accounting document classification and extraction.
- Added classification and extraction prompt files with strict JSON-only output contracts.
- The wrapper immediately parses provider output through the strict classifier/extraction parsers and returns candidate-only data.
- Added tests with fake provider clients for valid responses, non-JSON responses, forbidden side-effect fields, prompt content, provider isolation, and no file/DB writes.
- No Telegram handlers, preview/confirm flow, real Vision wiring, bank matching, DB schema changes, invoice flow changes, `storage/invoices` changes, `pdf_path` changes, or current contract `document_intake.py` behavior changes were made.

Risks / follow-up:
- Next slice should add preview/FSM handler integration behind explicit command/state routing, not broad idle attachment interception.
- Real photo/PDF Vision payload wiring should stay inside the LMM boundary and continue to feed strict parsers only.

## 2026-05-01 — Session 066 — Document Intake Phase 1 Slice 2 parsers

Summary:
- Added pure classifier parser for strict `receipt` / `incoming_invoice` / `unknown` classification JSON.
- Added pure extraction parser that converts approved candidate JSON into `AccountingDocumentCandidate`.
- Added parser guards against non-JSON, unsupported enums, unexpected top-level fields, and side-effect top-level fields such as `saved_path`, `status`, `confirmed`, and `final_category`.
- Added focused parser tests and compatibility coverage showing extraction output passes existing validation.
- No Telegram handlers, OpenAI/LMM/Vision calls, DB schema changes, file writes, invoice flow changes, `storage/invoices` changes, `pdf_path` changes, or current contract `document_intake.py` behavior changes were made.

Risks / follow-up:
- Next slice should add LMM call wrappers behind these parsers without letting model output create paths, IDs, save status, or final categories.
- Handler integration must remain explicit-command/state first to avoid intercepting existing contact contract uploads.

## 2026-05-01 — Session 065 — Document Intake Phase 1 Slice 1 foundation

Summary:
- Added pure accounting document data models for future receipt/incoming-invoice intake candidates.
- Added Python validation for required fields, positive Decimal amounts, ISO dates, currency handling, document type gating, and non-blocking IBAN/variable-symbol warnings.
- Added storage helpers for temp staging under `storage/uploads/accounting_intake/` and confirmed JSON-sidecar saves under the proposed OfficeFlow yearly/monthly expense tree.
- Added focused tests for validation failures, deterministic filenames, year/month path derivation, confirmed metadata sidecars, temp staging, and the guard against writing to `storage/invoices`.
- No Telegram handlers, LMM/OpenAI calls, DB schema changes, invoice flow changes, supplier profile changes, `storage/invoices` changes, or `pdf_path` changes were made.

Risks / follow-up:
- Next slice should add strict classifier/extraction parser tests before any LMM call.
- Handler integration must remain explicit-state or explicit-command first to avoid stealing existing contact contract uploads.

## 2026-05-01 — Session 064 — Canonical DecisionResolver runtime Phase 1

Summary:
- Added `bot/services/decision_resolver.py` as the shared Canonical DecisionResolver adapter for `approve_edit_cancel` and `yes_no` decision families.
- Migrated invoice preview, post-PDF invoice decision, contact semantic/manual confirmation, supplier onboarding confirmation, and existing-invoice delete confirmation to the shared resolver path.
- Fixed voice routing so confirm-state transcripts route to the active confirmation handler instead of falling through to top-level invoice routing.
- Added regression tests for canonical decisions, manual contact/onboarding confirmation aliases, delete confirmation context, and voice confirm routing.
- No OfficeFlow Document Intake runtime, DB schema, storage paths, supplier profile, invoice PDF path behavior, or `pdf_path` behavior changed.

Risks / follow-up:
- Telegram button/callback decisions are still future work.
- Future Document Intake must reuse the shared resolver and add its own preview/confirm tests before runtime implementation.

## 2026-05-01 — Session 063 — Canonical DecisionResolver docs policy

Summary:
- Added `docs/Canonical_Decision_Resolver_Contract.md` as the project-level policy for confirmation-like replies.
- Defined the required migration target: one shared Canonical DecisionResolver for `approve_edit_cancel` and `yes_no` decision families.
- Documented that LMM/semantic resolver returns only canonical decision tokens while the active FSM flow executes business actions.
- Marked existing local confirmation parsers as technical debt to migrate after tests.
- No runtime code, DB schema, storage paths, or Document Intake runtime were changed.

Risks / follow-up:
- Add tests around existing confirmation behavior before migrating local parsers.
- Migrate invoice/contact/onboarding/delete confirmation paths one at a time after tests.

## 2026-05-01 — Session 062 — Document Intake Phase 1 MVP implementation plan

Summary:
- Added `docs/Document_Intake_MVP_Implementation_Plan.md` as a docs-only Phase 1 plan for future receipt/incoming-invoice intake.
- Defined accepted inputs, classification, LMM JSON contract, Python validation, file naming, yearly/monthly storage target, Telegram preview/confirm flow, DB/storage options, and required tests.
- Explicitly kept bank matching, Google Drive sync, Zevs runtime profile, and multi-workspace runtime out of scope.
- No runtime code, DB schema, existing invoice storage, `pdf_path`, or supplier profile behavior was changed.

## 2026-05-01 — Session 061 — Docs-first OfficeFlow architecture foundation

Summary:
- Created docs-first OfficeFlow framing with FakturaBot defined as the current outgoing invoices module.
- Added a non-runtime OfficeFlow storage model proposal separating persistent master data from yearly accounting documents.
- Added a future Document Intake module proposal for receipts, incoming invoices, contracts, and bank statements.
- Minimally updated README, FakturaBot TZ, and LLM orchestrator contract with OfficeFlow cross-links and explicit non-runtime boundaries.
- No runtime code, DB schema, `pdf_path`, supplier SZČO profile, invoice flow, or existing storage files were changed.

Risks / follow-up:
- Future storage migration requires backup, DB/file compatibility plan, and invoice PDF path regression tests.
- Future Document Intake actions must be added docs-first to the action registry before runtime implementation.

## 2026-04-30 — Session 060 — Explicit hard-delete flow for persisted invoices

Summary:
- Added explicit top-level action `delete_existing_invoice` for persisted invoice deletion by short/full number reference.
- Added mandatory confirmation gate (`áno / nie`) before destructive delete.
- Implemented hard delete of invoice items + invoice row, plus best-effort PDF file deletion.
- Added ownership/invoice existence re-check right before destructive delete to fail loud safely.
- No soft delete, no storno logic, no DB schema migration.

Tests:
- `PYTHONPATH=. pytest -q tests/test_invoice_intent_prerouter.py`
- `PYTHONPATH=. pytest -q tests/test_invoice_state_decisions.py`
- `PYTHONPATH=. pytest -q`

## 2026-04-30 — Session 059 — Deterministic post-PDF save/edit/cancel decision guard

Summary:
- Hardened bounded decision normalization for preview/post-PDF invoice states with local Python marker detection before LLM fallback.
- Clear save markers such as `зберегти`, `сохрани`, `uložiť`, and `save changes` now map to `schvalit` deterministically.
- Removed reliance on ambiguous nouns like `зміни` / `изменения` as edit intent when an explicit save marker is present.
- Conflicting local markers now return `unknown` so the bot asks for clarification instead of guessing.
- Updated TZ with the decision-marker contract and added regression tests for the logged STT phrase.

Tests:
- `PYTHONPATH=. pytest -q tests/test_invoice_intent_prerouter.py` — 82 passed.
- `PYTHONPATH=. pytest -q` — 280 passed.

## 2026-04-30 — Session 058 — Item-level numeric edits inside `upraviť položku`

Summary:
- Extended bounded item action menu with numeric operations: `edit_item_quantity`, `edit_item_unit_price`, `edit_item_total_amount`.
- Added stage-aware numeric value handler for both draft and persisted edit backends under existing `upraviť položku` flow.
- Added strict numeric parser for bounded value input (`1500`, `1500,50`, `1500.50`, `2`, `2,5`) with fail-loud fallback prompt.
- Added deterministic arithmetic semantics:
  - quantity edit recalculates total using existing unit price;
  - unit-price edit recalculates total using existing quantity;
  - total edit recalculates unit price with guard `quantity > 0`.
- Added persisted backend updates for invoice item financial fields + invoice total recomputation before PDF rebuild.
- Updated LLM/action-contract docs and in-action registry status for item-level numeric operations.

## 2026-04-30 — Session 057 — Existing invoice summary preview before persisted edit-flow

Summary:
- Follow-up hardening for explicit `edit_existing_invoice`: when exactly one persisted invoice is resolved, bot now sends a current Slovak invoice summary before entering edit menu.
- Summary includes invoice number, customer, dates, item lines (description/detail), quantity, unit price, item total, and invoice total.
- If persisted `pdf_path` exists and file is available, bot sends current PDF as optional document preview; missing file/path does not fail flow.
- After summary/PDF preview, runtime continues into existing `start_invoice_edit_flow(...)` backend without creating a new draft and without post-PDF menu restoration.

## 2026-04-30 — Session 056 — Explicit existing-invoice edit entrypoint by number reference

Summary:
- Added explicit top-level action `edit_existing_invoice` for persisted invoice editing by command like `upraviť faktúru 15`.
- Kept preview-stage draft `upraviť` flow unchanged; no restoration of post-PDF menu after each generation.
- Implemented supplier-scoped invoice reference resolution in Python/DB layer (LLM does not query DB): short numeric suffix and full number both supported, with deterministic ambiguity handling.

Runtime changes:
- `process_invoice_text(...)` now accepts and handles `edit_existing_invoice` as explicit entrypoint.
- Added extraction of numeric invoice reference from user text and supplier-scoped lookup:
  - 0 matches => `Faktúru s týmto číslom som nenašiel.`
  - >1 matches => `Našiel som viac faktúr. Napíšte celé číslo faktúry.`
  - 1 match => set `last_invoice_id`/`edit_invoice_id` and start persisted `start_invoice_edit_flow(...)`.
- Added `InvoiceService.find_invoices_for_supplier_by_number_reference(...)`.

Tests:
- Added intent routing assertion for `edit_existing_invoice`.
- Added persisted lookup happy-path test for short reference `15` -> invoice `20260015`.
- Added ambiguity and supplier-scope guard test.

## 2026-04-30 — Session 055 — Normalize electrical repair service display title

### Goal
Fix FakturaBot invoice text generation so the supplier service alias/canonical layer uses the correct Slovak display title for electrical reserved technical device repairs.

### Changes
- updated `ServiceAliasService` to normalize the known service display title to `Opravy vyhradených technických zariadení elektrických`;
- applied the normalization on `create_mapping(...)`, `list_mappings(...)`, and `resolve_service_display_name(...)` so both new saves and existing lower-case/no-diacritic records render through the corrected title;
- added focused regression coverage for storing and resolving the corrected Slovak variant.

### Decision
- No schema migration or new service-alias flow was added.
- Existing supplier alias mappings remain the source of truth; this is a narrow canonical-title normalization for one confirmed Slovak service phrase.

## 2026-04-26 — Session 054 — Preview-stage draft edit-flow implementation

### Goal
Move the invoice edit happy path from post-PDF approval to preview / `Náhľad faktúry`, while keeping post-PDF edit as compatibility/fallback and showing a proposed invoice number before final generation.

### Changes
- changed preview confirmation semantics from `ano` / `nie` to draft-review decision `schvalit` / `upravit` / `zrusit`, with `ano` and `nie` kept as aliases;
- added proposed invoice number to FSM `invoice_draft` and preview copy as `Číslo faktúry: <number> (návrh)`;
- changed final preview approval to create the invoice row, use the proposed/final number, generate PDF, set ready status, send PDF, and clear FSM;
- added draft edit backend for invoice number/date edits and item service/description/detail edits, mutating FSM draft only and returning updated preview;
- preserved post-PDF `waiting_pdf_decision` and persisted invoice edit backend as compatibility/fallback;
- updated LLM bounded confirmation contract and in-action registry for preview draft decisions;
- extended tests for preview decision aliases, proposed number behavior, draft edits, duplicate proposed number rejection, and post-PDF compatibility.

### Decision
- No DB schema migration was made.
- Invoice number remains non-null on persisted invoices.
- Proposed number is not reserved before final approval.
- Billing/quota logic remains out of scope.

### Manual verification checklist

Happy path:
- create invoice and verify preview shows `Číslo faktúry: <number> (návrh)`;
- reply `schváliť` or `ano`;
- verify invoice row is created with final number, PDF is generated, status is `pripravena`, bot does not ask post-PDF `schváliť/upraviť/zrušiť` again, and FSM is cleared.

Draft edit before finalization:
- create invoice and choose `upraviť` on preview;
- edit `Dátum dodania`;
- verify bot shows updated text preview, no PDF rebuild happens during draft edit, no final invoice row exists before `schváliť`, and review returns to `schváliť/upraviť/zrušiť`.

Proposed number conflict:
- set draft proposed invoice number to an already existing number;
- reply `schváliť`;
- verify finalization is rejected, no invoice/PDF is created, draft remains available, and bot asks for another invoice number.

## 2026-04-26 — Session 053 — Draft review edit-flow lifecycle design audit

### Goal
Audit current FakturaBot invoice lifecycle and design the migration path for moving `upraviť faktúru` from the post-PDF approval step to the draft review / `náhľad faktúry` step before final invoice/PDF generation.

### Changes
- added docs-only architecture document `docs/Invoice_Draft_Review_Lifecycle_Design.md` with:
  - current runtime lifecycle and confirmation semantics;
  - audit answers for FSM draft vs DB invoice row, invoice number timing, PDF timing, `last_invoice_id`, and edit-flow dependencies;
  - target draft lifecycle and state machine proposal;
  - data model impact for draft status, numbering, PDF storage, and abandoned drafts;
  - LLM contract impact for preview decision canonical outputs `schvalit` / `upravit` / `zrusit`;
  - phased migration plan and risks.

### Decision
- No runtime code, tests, DB schema, numbering logic, PDF generation logic, billing logic, or post-PDF edit behavior changed in this session.
- Current audit conclusion: pre-confirmation preview is FSM-only `invoice_draft`; current edit-flow requires persisted `invoice_id` and is coupled to PDF rebuild side effects, so draft review editing should be implemented through a stage-aware edit orchestrator rather than a narrow `waiting_confirm` patch.

## 2026-04-24 — Session 052 — Clarify implicit first item before explicit `polozka 2`

### Goal
Make the invoice draft prompt explicit that the first item may already start before the user says `polozka 2` / `pozicia 2`.

### Changes
- updated `prompts/invoice_draft_prompt.txt` so the split-semantics section now states:
  - if the user starts describing the first service without saying `polozka 1`,
  - and later says `polozka 2` / `pozicia 2` / `item number 2`,
  - the preceding service fragment should be treated as candidate item 1 and the marker opens candidate item 2.

### Decision
Numbered markers in voice input are not required to start from `1`; the model should infer an implicit first item when earlier service content is already present.

## 2026-04-24 — Session 051 — Align invoice draft prompt with multilingual Slovak-normalized LLM contract

### Goal
Make the invoice draft LLM layer explicitly responsible for normalizing mixed SK/UA/RU/noisy STT input into Slovak business semantics while preserving the exact Python-facing bounded JSON shape.

### Changes
- updated `docs/FakturaBot_LLM_Orchestrator_Contract.md` to state explicitly that:
  - LLM first normalizes multilingual/noisy invoice meaning into Slovak draft semantics;
  - LLM output must stay aligned to the exact Python intake shape (`vstup`, `zamer`, `biznis_sk`, `stopa`, bounded `items[]`);
  - numbered and ordinal item markers across mixed languages are valid candidate split signals at the LLM contract level;
- updated `prompts/invoice_draft_prompt.txt` so the runtime prompt now explicitly instructs the model to:
  - preserve raw transcript in `vstup.povodny_text`;
  - normalize business meaning into Slovak field-by-field in `biznis_sk`;
  - return only the machine-safe JSON shape expected by Python;
  - treat multilingual numbered/ordinal item markers as explicit bounded item separators.

### Decision
Invoice item segmentation and multilingual normalization should be driven primarily by the LLM contract/prompt, while Python remains a bounded validator and fail-safe layer rather than the main natural-language parser.

## 2026-04-24 — Session 050 — Improve numbered voice item boundary handling

### Goal
Reduce invoice-draft misses in multi-item voice input where the user separates positions with numbered markers such as `polozka 2`, `polozka cislo 3`, `pozicia 2`, or `item number 2`.

### Changes
- expanded invoice item-boundary heuristics in `bot/handlers/invoice.py` to treat numbered markers as explicit multi-item separators;
- covered both Latin/transliterated and Cyrillic/diacritic variants of `polozka/položka/pozicia/позиция/положка/item`;
- updated `prompts/invoice_draft_prompt.txt` with explicit examples for numbered multi-item speech up to three positions;
- added regression coverage in `tests/test_invoice_phase2_ai_layer.py` for `item 2` and `item 3` style voice boundaries.

### Decision
Numbered item markers are now treated as strong split signals even when the utterance has no commas and no reliable conjunction split, because this is a natural speech pattern in Telegram voice drafting.

## 2026-04-24 — Session 049 — Fix Linux PDF font resolution for server invoice generation

### Goal
Restore invoice PDF generation in the Linux Docker deployment after runtime failure on missing Slovak glyph-capable fonts.

### Changes
- updated `bot/services/pdf_generator.py` to probe Linux font locations in addition to Windows and ReportLab fallback fonts;
- added `fonts-dejavu-core` installation to `Dockerfile` so the container includes a Unicode-capable TTF font at runtime.

### Problem confirmed
- server logs showed PDF generation failure during invoice confirmation:
  - `RuntimeError: No available PDF font with required Slovak glyph support`

### Decision
Keep the existing Unicode font registration flow, but make it Linux-aware and ensure the Docker image ships with at least one known-good system font.

## 2026-04-24 — Session 048 — Add safe server update runbook to local-only agent context

### Goal
Document the exact safe update procedure for refreshing the server-hosted FakturaBot instance after GitHub changes, without exposing secrets in public repo docs.

### Changes
- updated `docs/local-only/FakturaBot_Server_Agent_Context.md` with a focused safe update runbook:
  - SSH entry point;
  - `/bot/repo` working directory;
  - `git fetch` / `checkout main` / `pull --ff-only`;
  - `docker compose -f docker-compose.prod.yml up -d --build`;
  - status/log verification steps;
  - explicit note for `TelegramConflictError` as a competing-runtime issue.

### Decision
Server update instructions belong in the local-only server agent context because they are operational guidance tied to the live host and should not be expanded in public repo docs.

## 2026-04-24 — Session 047 — Public repo prep for local-only operational materials

### Goal
Prepare the repository for a public GitHub state while keeping private operational/server materials available locally for agents and excluded from the public index.

### Changes
- audited the repo for server access details, absolute server paths, deploy/runtime commands, private runbooks, and local ops handoff materials;
- confirmed the main sensitive local operational file is `docs/local-only/FakturaBot_Server_Agent_Context.md`, which remains local-only and ignored;
- expanded `.gitignore` for a dedicated `docs/local-only/` area while keeping safe placeholders trackable;
- added a minimal production-like deployment baseline for Stage 1-2 rollout:
  - `.dockerignore`
  - `docker-compose.prod.yml`
  - `.env.server.example`
  - `scripts/update_repo.sh`
  - `scripts/deploy_owner_run.sh`
- added public-safe placeholders:
  - `docs/local-only/README.md`
  - `docs/local-only/FakturaBot_Server_Agent_Context.example.md`
- sanitized tracked public docs to avoid direct local artifact/path guidance where not needed:
  - `docs/FakturaBot_Server_Rollout_Roadmap.md`
  - `docs/PayBySquare_Manual_Verification_Checklist.md`
  - `PROJECT_LOG.md`

### Exposure assessment
- no tracked file with real SSH host/IP details was found in the current git index;
- `docs/local-only/FakturaBot_Server_Agent_Context.md` contains real server operational details locally, but is already ignored and not tracked in the current repository state;
- no history rewrite was performed.

## 2026-04-21 — Session 046 — Server rollout/onboarding roadmap + README deployment direction alignment

### Goal
Add a practical docs-first deployment/onboarding roadmap from current local+GitHub state to the first external client pressing `/start` on a server-hosted FakturaBot, and align README with the near-term shared-backend tenant-isolation direction.

### Changes
- added `docs/FakturaBot_Server_Rollout_Roadmap.md` with staged operational path:
  - start point and scope truthfulness notes (plan/target, not completed infrastructure claim);
  - explicit near-term architecture decision: shared backend + tenant isolation as primary rollout model;
  - staged roadmap (server foundation -> owner production-like run -> tenant model -> multi-bot routing -> manual onboarding v1 -> first external client dry run -> later improvements);
  - data/secret handling principles and first milestone definition for external `/start` success.
- updated `README.md` surgically to:
  - link the new rollout roadmap document;
  - state the near-term rollout direction (shared backend + tenant isolation, Telegram-first);
  - clarify self-service setup page is later and not required for first deployment milestone.

### Scope boundary
- Docs-only patch.
- No runtime code changes.
- No claim that multi-tenant runtime, setup page, or full production automation is already implemented.

## 2026-04-19 — Session 045 — TZ alignment with planned `info_help` guidance layer

### Goal
Align `docs/TZ_FakturaBot.md` with the newer docs-first `info_help` architecture at high-level product/requirements level, without duplicating the detailed focused spec.

### Changes
- updated `docs/TZ_FakturaBot.md` (section 5) with a surgical high-level `info_help` alignment block:
  - clarified `info_help` as bounded guidance/navigation/recovery layer (not free-form chat, not direct-action duplicate);
  - fixed routing precedence: top-level action first, question form does not block direct actions, `info_help` only on top-level `unknown`;
  - added concise contract-precedence note: `info_help` remains subordinate to existing bounded `docs/llm` rules;
  - added capability status model (`implemented` / `planned` / `unsupported`) and truthfulness requirement;
  - added structured logging requirement for all `info_help` entries as product signals;
  - added Phase 2/3 future-direction note (state-aware guidance, reset/new-task support, bounded runtime explainability);
  - explicitly prohibited arbitrary source-code/raw-log reading by LLM in this layer;
  - preserved caution for unconfirmed flows (contact edit, old-invoice deletion, send-invoice/send-email, support escalation);
  - added explicit reference to detailed spec `docs/Info_Help_Guidance_Layer.md`.

### Scope boundary
- Docs-only alignment patch.
- No runtime code changes.
- No upgrade of unsupported/planned behavior to implemented.

## 2026-04-19 — Session 044 — Refinement: Phase 2/3 runtime explainability for `info_help` spec

### Goal
Extend the docs-first `info_help` specification with forward-looking runtime explainability/debug-aware guidance rules for later phases, while preserving strict bounded `docs/llm` contract precedence.

### Changes
- updated `docs/Info_Help_Guidance_Layer.md` with targeted additions:
  - future-direction note: controlled runtime explainability in Phase 2/3;
  - new subsection for bounded Python-prepared runtime/debug context (`FSM state`, flow, next actions, reset availability, STT failure count, error category, fallback reason, API/quota status, sanitized summary);
  - explicit prohibitions against arbitrary source-code/raw-log reading by LLM and against leaking secrets/internal traces/paths;
  - added worked examples for repeated STT failure and model/API or quota/credits failure;
  - extended logging rationale with runtime-explainability signals;
  - extended Phase 2/3 rollout bullets with debug-aware guidance and optional admin reliability summaries.

### Scope boundary
- Docs-only refinement.
- No runtime code changes.
- No new implementation claims beyond planned behavior.

## 2026-04-19 — Session 043 — Docs-first spec for `info_help` guidance/navigation layer

### Goal
Add a dedicated docs-first architecture/spec for planned `info_help` capability, explicitly subordinate to existing bounded `docs/llm` contract, without runtime implementation changes.

### Changes
- added new spec document: `docs/Info_Help_Guidance_Layer.md`
  - defines purpose/scope/non-goals for controlled guidance/navigation/recovery layer;
  - fixes routing rule: top-level action resolution first, `info_help` only on top-level miss;
  - defines internal `info_help` submodes (`faq_topic`, `state_guidance`, `action_offer_or_handoff`, `restart_or_reset_request`, `support_escalation`);
  - defines capability status model (`implemented`, `planned`, `unsupported`) with truthful response rules;
  - defines bounded knowledge-registry shape and staged LLM interaction contract;
  - defines safety requirements (no hidden mutation, explicit confirmation for handoff/reset);
  - defines mandatory structured logging fields for all info-layer requests;
  - includes worked examples and explicit truthfulness boundaries for unconfirmed flows;
  - includes phased rollout and docs-alignment checklist.

### Scope boundary
- Docs-only change.
- No runtime code changes.
- No behavior claimed as implemented beyond confirmed current runtime.

## 2026-04-19 — Session 042 — Invoice date edit expansion (issue/delivery/due) with voice-first bounded LLM contract

### Goal
Expand `upraviť faktúru` invoice-level date editing from one narrow `edit_invoice_date` path to full three-date support (`vystavenia`, `dodania`, `splatnosti`) and make value capture voice/text parity via bounded LLM normalization contract.

### Changes
- invoice-level action surface (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - added canonical operations:
    - `edit_invoice_issue_date`
    - `edit_invoice_delivery_date`
    - `edit_invoice_due_date`
  - kept `edit_invoice_date` as clarification-only umbrella intent (`upraviť dátum` -> ask which date).
- user prompts/messages (`bot/handlers/invoice.py`):
  - updated invoice-level edit menu to list all three concrete date actions;
  - added clarification prompt:
    - `Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?`
  - added exact value prompts:
    - `Napíšte alebo nadiktujte nový dátum vystavenia... DD.MM.RRRR`
    - `Napíšte alebo nadiktujte nový dátum dodania... DD.MM.RRRR`
    - `Napíšte alebo nadiktujte nový dátum splatnosti... DD.MM.RRRR`
  - success messages split per field:
    - `Dátum vystavenia bol upravený.`
    - `Dátum dodania bol upravený.`
    - `Dátum splatnosti bol upravený.`
- bounded LLM date normalization contract (`bot/services/semantic_action_resolver.py`, `bot/handlers/invoice.py`):
  - added `resolve_invoice_date_normalization(...)` that enforces bounded output:
    - JSON `{ "normalized_date": "DD.MM.RRRR" }` or `{ "normalized_date": "unknown" }`;
  - invoice date value handler now uses this contract for both text and voice/STT input;
  - Python side only performs strict format/date validation and applies persistence/reject logic.
- validation and persistence (`bot/handlers/invoice.py`, `bot/services/invoice_service.py`):
  - added `update_invoice_delivery_date(...)` and `update_invoice_due_date(...)`;
  - enforced invariant reject:
    - `Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.`
  - also prevents issue-date update that would violate `due_date >= issue_date`.
- tests (`tests/test_invoice_state_decisions.py`):
  - updated issue-date success path to new explicit action;
  - added routing clarification test for generic `upraviť dátum`;
  - added success coverage for delivery-date edit;
  - added invariant reject coverage for due-date earlier than issue-date;
  - added voice-style natural-language date input test with mocked bounded normalization result.

### Scope boundary
- Item-level edit flow was not changed.
- No hidden auto-fix behavior added; all invariant conflicts remain fail-loud with explicit user-facing reject.
- No behavior claimed as implemented beyond confirmed current runtime.

## 2026-04-19 — Session 041 — Hardening `nový opis položky` isolation from alias mappings

### Goal
Close pre-merge risk check: ensure `nový opis položky` mutates only invoice item fields and has no side effects on supplier service-alias DB state.

### Changes
- invoice item mutation path isolation (`bot/services/invoice_service.py`, `bot/handlers/invoice.py`):
  - added explicit `update_item_main_description(...)` method in `InvoiceService`;
  - switched `replace_main_description` handler path from `update_item_service(...)` to `update_item_main_description(...)` to make intent/scope explicit (invoice item only).
- regression coverage (`tests/test_invoice_state_decisions.py`):
  - added test `test_novy_opis_updates_only_invoice_item_without_alias_db_side_effects` that verifies:
    - main item description is replaced exactly (no appended tail),
    - item details are untouched,
    - service-alias mappings remain identical before/after action.

### Scope boundary
- Minimal change only for isolation/clarity.
- No changes to `zmeniť službu` runtime branch.
- No confirmation-flow or FSM redesign changes.

## 2026-04-19 — Session 040 — UX wording cleanup for `upraviť faktúru` item-level edit flow

### Goal
Align item-level edit naming/messages with real runtime semantics without changing confirmation architecture or broad FSM design.

### Changes
- user-facing prompt cleanup (`bot/handlers/invoice.py`):
  - removed `kontakt` from top-level `upraviť faktúru` scope prompt (`faktúra` now shows only `číslo/dátum`);
  - replaced item-action menu wording with explicit four actions:
    - `zmeniť službu`
    - `nový opis položky`
    - `pridať detaily k položke`
    - `vymazať detaily položky`
- item edit action routing/messages (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - split bounded item-action semantics into:
    - `replace_service`
    - `replace_main_description`
    - `add_item_details`
    - `clear_item_details`
  - updated input prompts to match action semantics:
    - main description replacement prompt explicitly states replacement;
    - details prompt explicitly asks for details;
    - clear-details action executes immediately and returns clear-details-specific feedback.
- success-message precision (`bot/handlers/invoice.py`):
  - `Služba položky bola zmenená.`
  - `Opis položky bol nahradený novým textom.`
  - `Detaily položky boli doplnené.`
  - `Detaily položky boli vymazané.`
  - empty-clear case: `Položka nemá žiadne detaily na vymazanie.`
- tests (`tests/test_invoice_state_decisions.py`):
  - updated item-level flow assertions to new user-facing action names and success copy;
  - added state assertion for `nový opis položky` action mode;
  - updated detail-flow expectations to additive details semantics and new messages.

### Scope boundary
- No redesign of confirmation-flow.
- No breaking changes for working `zmeniť službu` branch semantics.
- No large FSM refactor; only minimal routing/message touch for item-level UX fidelity.

## 2026-04-19 — Session 039 — LLM contract rewrite for bounded confirmation/decision normalization

### Goal
Fix unstable `unknown` outcomes in bounded confirmation steps by rewriting only the LLM prompt/instruction contract (no Python routing/fallback expansion).

### Changes
- bounded resolver prompt rewrite (`bot/services/semantic_action_resolver.py`):
  - replaced overly literal/conservative system prompt with explicit intent-normalization policy;
  - added stepwise policy in system prompt: semantic intent inference -> canonical normalization -> `unknown` only for true ambiguity/non-decision/garbage;
  - explicitly documented `yes_no_confirmation` behavior (user not required to answer exact `ano`/`nie`);
  - explicitly documented `postpdf_decision` normalization (`approve/confirm/save` -> `schvalit`, `edit/change/correct` -> `upravit`, `delete/cancel/remove/discard` -> `zrusit`) with destructive-safety guard for unclear intent.
- bounded resolver user payload contract (`bot/services/semantic_action_resolver.py`):
  - added `normalization_contract` object to reinforce semantic-intent-first behavior and context-specific mapping expectations.
- tests (`tests/test_invoice_intent_prerouter.py`):
  - added LLM-path contract tests (mocked `AsyncOpenAI`) for multilingual/noisy confirmation inputs in `invoice_preview_confirmation`;
  - added LLM-path contract tests for multilingual delete/cancel/remove/discard intents in `invoice_postpdf_decision`;
  - assertions verify model path usage (`fallback_used=False`) and presence of new instruction contract fields in prompt/payload.

### Scope boundary
- No FSM/routing changes.
- No fallback keyword/synonym expansion in Python.
- Fix is implemented through LLM contract only.

## 2026-04-18 — Session 038 — Contract-correction pass for edit FSM (item target bounded resolver + runtime contact removal)

### Goal
Finalize previous clean FSM rewrite without redesigning again: align remaining gaps with docs/llm contract by moving multi-item target selection to bounded semantic resolution and removing `edit_invoice_contact` from runtime edit surface.

### Changes
- item-target contract correction (`bot/handlers/invoice.py`):
  - added bounded resolver helper `_resolve_item_target_index_bounded(...)` with dedicated context `invoice_edit_item_target_selection`;
  - `waiting_edit_item_target` no longer relies on local `isdigit()` gate as primary selector;
  - handler now resolves canonical target via bounded resolver first, then Python validates range (`1..N`) and performs fail-loud clarification with state preserved.
- runtime contact edit removal (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - removed `edit_invoice_contact` from invoice-level runtime allowed actions;
  - removed contact wording from invoice-level user prompts;
  - removed invoice-action runtime branch for contact edit;
  - removed fallback mapping for `edit_invoice_contact` in context `invoice_edit_invoice_action`.
- fallback support (`bot/services/semantic_action_resolver.py`):
  - added fallback context `invoice_edit_item_target_selection` for deterministic non-LLM fallback (`1/2/3`, basic ordinal/cardinal forms).
- tests (`tests/test_invoice_state_decisions.py`, `tests/test_voice_state_routing.py`):
  - added multi-item target coverage for numeric and spoken ordinal selection;
  - added ambiguous target + out-of-range fail-loud/state-preserved coverage;
  - added runtime-surface tests proving invoice action prompt no longer offers contact edit and contact text is treated as unknown;
  - added extra voice invoice-action routing check for date phrase.

### Scope boundary
- No new architecture redesign from scratch.
- Kept prior clean state split and value executors unchanged.
- Kept text-only policy for final description value state unchanged.

## 2026-04-18 — Session 037 — Clean FSM/orchestrator redesign for `upraviť faktúru` edit subflow

### Goal
Replace legacy mixed item/invoice edit routing with clean bounded orchestrator states and state-scoped semantic resolution, including voice parity for edit-flow control states.

### Changes
- invoice edit FSM/orchestrator rewrite (`bot/handlers/invoice.py`):
  - replaced mixed `waiting_edit_operation` contract with explicit state split:
    - `waiting_edit_scope`
    - `waiting_edit_invoice_action`
    - `waiting_edit_item_target`
    - `waiting_edit_item_action`
    - value states (`waiting_edit_service_value`, `waiting_edit_invoice_number_value`, `waiting_edit_invoice_date_value`, `waiting_edit_description_value`)
  - replaced heuristic `_detect_edit_operation(...)` primary routing with bounded state-scoped semantic resolvers:
    - scope resolver (`invoice_edit_scope_selection`)
    - invoice action resolver (`invoice_edit_invoice_action`)
    - item action resolver (`invoice_edit_item_action`)
  - removed invoice-level action handling from item-target state; item-target now handles only item index selection.
  - rewrote edit entrypoint from legacy `_start_invoice_item_edit_flow(...)` to clean `start_invoice_edit_flow(...)` with explicit scope selection first.
  - kept integrity rules and reuse of existing executors (`update_item_service`, `update_item_description`, `update_invoice_number`, `update_invoice_issue_date`, PDF rebuild/post-edit prompt helpers).
  - kept `waiting_edit_description_value` as text-only final precision state; number/date states now support voice/text with fail-loud exact-text fallback prompts on invalid/ambiguous input.
- semantic fallback support (`bot/services/semantic_action_resolver.py`):
  - added deterministic fallback contexts for new bounded edit states (`invoice_edit_scope_selection`, `invoice_edit_invoice_action`, `invoice_edit_item_action`) for non-LLM test/runtime fallback paths.
- voice routing parity (`bot/handlers/voice.py`):
  - removed text-only guards for edit-flow selection/control states; STT text now routes through the same edit handlers as text input for:
    - scope
    - invoice action
    - item target
    - item action
    - service value
    - invoice number/date value
  - retained text-only guard only for final item-description value state.
- tests (`tests/test_invoice_state_decisions.py`, `tests/test_voice_state_routing.py`):
  - updated edit-flow tests for clean state graph transitions (scope -> branch-specific states).
  - added explicit routing coverage for `upraviť opis položky` -> description branch and `zmeniť službu` -> service branch.
  - updated single-item and multi-item flow assertions to new orchestrator steps.
  - updated invoice-level branch tests to use `waiting_edit_invoice_action` before number/date value states.
  - expanded voice routing coverage for edit scope, invoice action, item target, item action, service value, and number/date value handler routing.
  - strengthened regression by asserting FSM transition to correct final input state before final handlers (removes prior false-green pattern).

### Scope boundary
- Clean redesign of bounded `upraviť` subflow only (post-PDF in-action model).
- No standalone top-level `edit_invoice` executor added.
- `edit_invoice_contact` remains planned/future-ready (not implemented value persistence).

## 2026-04-17 — Session 036 — Fix post-edit return for `edit_item_description` approval stage

### Goal
Fix narrow runtime bug where successful item description edit inside `upraviť` could return user into edit-loop context instead of reliably staying in post-PDF approval stage.

### Changes
- invoice edit success return hardening (`bot/handlers/invoice.py`):
  - added `_send_post_edit_approval_prompt(...)` helper for post-edit success responses;
  - helper explicitly enforces FSM state `waiting_pdf_decision` before sending approval prompt;
  - wired helper into all successful edit handlers (`replace_service`, `edit_item_description`, `edit_invoice_number`, `edit_invoice_date`) after successful PDF rebuild.
- regression coverage (`tests/test_invoice_state_decisions.py`):
  - extended `replace_service` test with explicit state + approval prompt assertions;
  - extended `edit_item_description` success path test with explicit state + approval prompt assertions;
  - existing invoice number/date tests continue asserting post-edit approval state/prompt behavior.

### Scope boundary
- Narrow runtime bugfix only.
- No edit architecture redesign.
- No expansion to unrelated actions/flows.

## 2026-04-16 — Session 035 — Semantic seam migration batch 1 (bounded service alias contract)

### Goal
Migrate remaining Python-first semantic service resolution seams (invoice parse + service clarification + invoice edit service change) to bounded LLM orchestration with DB-driven allowed sets, while keeping deterministic cleaning/validation unchanged.

### Changes
- invoice parser contract hardening (`bot/services/llm_invoice_parser.py`):
  - removed dictionary/normalizer-based service canonicalization from payload validation;
  - kept deterministic shape checks and safe string normalization only (`strip`, non-empty constraints);
  - service term is now treated as bounded semantic output to be resolved in runtime against allowed aliases.
- invoice runtime bounded resolution (`bot/handlers/invoice.py`):
  - added supplier-scoped bounded service alias resolver that:
    - fetches active alias options from DB,
    - keeps deterministic text cleaning for direct exact/normalized match,
    - otherwise calls bounded semantic resolver with allowed values + per-option description,
    - accepts only one alias from allowed set (or unknown).
  - migrated create-preview item service resolution to this bounded alias contract;
  - migrated service slot clarification (`waiting_service_clarification`) to bounded alias contract;
  - migrated invoice edit `replace_service` path to bounded alias contract;
  - removed old bridge-form/dictionary semantic fallback usage from these paths.
- focused tests (`tests/test_invoice_phase2_ai_layer.py`):
  - updated parser expectations to deterministic-only service-field repair behavior (no dictionary semantic rewrite),
  - added tests for bounded alias resolution (deterministic direct match + bounded LLM canonical selection),
  - adjusted multi-item preview fixture coverage to include alias set required by bounded contract.

### Scope boundary
- Deterministic cleaning/validation/FSM/persistence logic kept in Python.
- No giant synonym dictionaries introduced.
- No architecture expansion beyond bounded service-semantic seams targeted in this batch.

## 2026-04-16 — Session 034 — Pre-merge audit fixes for Phase 1 multi-item `create_invoice`

### Goal
Apply only merge-blocking safety fixes discovered during pre-merge audit of Phase 1 multi-item `create_invoice` runtime patch.

### Changes
- item-boundary ambiguity hardening (`bot/handlers/invoice.py`):
  - strengthened `_looks_like_item_boundary_split(...)` with numeric-token count check against expected item count;
  - prevents silent acceptance of two-item candidate splits when raw text contains only one amount token (e.g. conjunction phrase with one number).
- aggregate total invariant hardening:
  - in confirmation save path, added explicit guard that draft aggregate total equals sum of persisted item totals before DB insert;
  - in `InvoiceService.create_invoice_with_items(...)`, added fail-loud invariant check (`invoice total == sum(item totals)`).
- docs consistency:
  - removed contradictory `single-item` status line in orchestrator contract section 6.2 so runtime status markers are internally consistent.
- focused regression tests:
  - added ambiguity regression for multi-item candidate with conjunction but single amount token (must clarify, not save silently);
  - added save-path regression proving total mismatch is rejected fail-loud and invoice is not persisted.

### Scope boundary
- No architecture redesign.
- No scope expansion to delete/edit-contact/unrelated flows.
- Only targeted merge-safety fixes for bounded Phase 1 behavior.

## 2026-04-16 — Session 033 — Phase 1 runtime multi-item support for `create_invoice` intake

### Goal
Implement the smallest safe runtime path for Phase 1 multi-item invoice intake in `create_invoice` flow, while preserving backward-compatible singleton behavior and Python-owned validation/side effects.

### Changes
- prompt contract (`prompts/invoice_draft_prompt.txt`):
  - extended invoice draft prompt with optional bounded `biznis_sk.items[]` candidate shape;
  - preserved singleton fields as mandatory backward-compatible shape;
  - documented Phase 1 bound `items[]` max size = 3 and no open-ended extraction.
- parser/validator (`bot/services/llm_invoice_parser.py`):
  - added optional dual-shape validation for `biznis_sk.items[]`;
  - implemented fail-safe payload errors for invalid items shape, count overflow, and unresolved item service terms;
  - preserved legacy singleton validation path and cleanup behavior.
- runtime normalization/build (`bot/handlers/invoice.py`):
  - intake extraction now always provides internal `items[]` normalized draft shape (singleton auto-wrap);
  - preview builder now supports single-item and bounded multi-item normalization with safe checks:
    - max items bound,
    - boundary ambiguity guard,
    - per-item quantity/unit_price/amount coherence via existing deterministic semantics;
  - added bounded clarification slot for item-split/financial ambiguity (`items`);
  - preview text formatting now renders item lines when draft has multiple items.
- persistence (`bot/services/invoice_service.py`):
  - added `CreateInvoiceItemPayload` and `create_invoice_with_items(...)`;
  - kept `create_invoice_with_one_item(...)` as compatibility wrapper over new multi-item insert path.
- save/confirm path (`bot/handlers/invoice.py`):
  - `process_invoice_preview_confirmation(...)` now persists all normalized draft items when present;
  - singleton save behavior remains compatible.
- service normalization (`bot/services/service_term_normalizer.py`):
  - added Slovak `montáž/montaz` variants to deterministic canonical mapping.
- tests:
  - expanded Phase 2 parser/preview tests with dual-shape extraction, bounds rejection, multi-item preview total, and ambiguous multi-item clarification;
  - added state-decision regression ensuring confirmation persists multiple `invoice_item` rows.

### Scope boundary
- Added: Phase 1 multi-item support for create-invoice intake/runtime path.
- Not added: delete/cancel flow redesign, advanced layout redesign, or unrelated edit-flow redesign.
- LLM remains bounded candidate extractor; Python remains validator/workflow/persistence owner.

## 2026-04-16 — Session 032 — Docs-first dual-shape `create_invoice` intake contract for future multi-item support

### Goal
Define a safe docs-first contract evolution for `create_invoice`/Phase 2 invoice intake so future runtime can support both one item and multiple items without breaking bounded architecture or current single-item behavior.

### Changes
- orchestrator contract (`docs/FakturaBot_LLM_Orchestrator_Contract.md`):
  - added dedicated docs-first section for planned `create_invoice` dual-shape intake;
  - documented backward-compatible strategy:
    - keep existing singleton `biznis_sk` item fields,
    - add optional bounded `biznis_sk.items[]`;
  - fixed authority split for segmentation:
    - LLM may return bounded candidate item segmentation only,
    - Python remains final validator/workflow/persistence owner;
  - documented Phase 1 bounds:
    - `items[]` max size = 3,
    - no open-ended extraction;
  - documented candidate item shape (service term + qty/unit/unit_price/amount + optional detail),
  - documented split semantics examples and fail-safe clarification triggers.
- product spec (`docs/TZ_FakturaBot.md`):
  - added subsection under invoice draft section with same dual-shape decisions, bounds, ambiguity/fallback rules, and future runtime follow-up areas.
- in-action registry (`docs/llm/In_Action_Response_Registry.md`):
  - added docs-first contract-tracking row for `create_invoice` Phase 2 dual-shape intake;
  - added explicit note that runtime remains single-item until follow-up patches.

### Scope boundary
- Docs-first only.
- No runtime implementation in this patch.
- No prompt implementation in this patch.
- Current create flow remains single-item until follow-up parser/runtime/prompt patches.

## 2026-04-15 — Session 031 — Runtime `edit_invoice_date` inside bounded `upraviť` flow

### Goal
Implement runtime support for invoice-date edit (`edit_invoice_date`) inside existing bounded `edit_invoice`/`upraviť` flow, without expanding to contact edit or item numeric/unit/price edits.

### Changes
- invoice edit runtime:
  - extended bounded edit operation detection with invoice-level operation `edit_invoice_date`;
  - added bounded FSM state for invoice-date value input;
  - wired selection path from existing `upraviť` flow (single-item and multi-item invoices) to invoice-date edit state;
  - added bounded Slovak prompts for strict date input:
    - entry: `Aktuálny dátum faktúry je {current_date}. Napíšte nový dátum textom vo formáte DD.MM.RRRR.`
    - invalid: `Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.`
- validation/safety:
  - added strict Phase 1 parser helper `parse_strict_date_dd_mm_yyyy(...)`;
  - accepts only `DD.MM.RRRR`;
  - rejects non-matching format and impossible dates (e.g. `31.02.2026`);
  - no natural-language parsing, no silent reinterpretation, no best-guess date conversion.
- persistence/service:
  - added invoice service helper `update_invoice_issue_date(...)`;
  - on valid input, updates `invoice.issue_date` with normalized ISO value used by current storage model.
- rebuild flow:
  - after successful invoice-date update, runtime rebuilds updated PDF and returns to `waiting_pdf_decision`;
  - previous PDF cleanup path remains aligned with existing edit rebuild behavior.
- voice guard:
  - added text-only guard for invoice-date edit state in voice handler:
    - `Pre dátum faktúry použite textový vstup vo formáte DD.MM.RRRR.`

### Invariant decision for this patch
- Chosen behavior: **B**.
- Editing invoice date is allowed while invoice number remains unchanged in this patch.
- No auto-renumbering is introduced.

### Tests
- added runtime tests for:
  - successful invoice-date edit to valid strict value (+ persistence + PDF rebuild + post-edit state),
  - invalid format rejection with bounded Slovak prompt and preserved old value/state,
  - impossible date rejection with safe retry prompt and preserved old value/state,
  - voice precision-safe guard for invoice-date edit state.
- existing `upraviť položku` and `upraviť číslo faktúry` runtime tests remain in suite as regression coverage.

### Scope boundary
- This runtime patch adds only `edit_invoice_date`.
- Still out of scope (not implemented here):
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`

## 2026-04-15 — Session 030 — Runtime `edit_invoice_number` inside bounded `upraviť` flow

### Goal
Implement runtime support for invoice-number edit (`edit_invoice_number`) inside existing bounded `edit_invoice`/`upraviť` flow, without expanding to other invoice-level or item numeric/date/contact edits.

### Changes
- invoice edit runtime:
  - extended bounded edit operation detection with invoice-level operation `edit_invoice_number`;
  - added bounded FSM state for invoice-number value input;
  - wired selection path from existing `upraviť` flow (single-item and multi-item invoices) to invoice-number edit state;
  - added precision-safe prompts for text-only final invoice-number input;
- validation/safety:
  - added runtime invoice-number validation for project format (`RRRRNNNN`) with issue-year consistency check;
  - added application-level uniqueness check before save;
  - duplicate detection returns bounded Slovak prompt and keeps edit state:
    - `Číslo faktúry už existuje. Zadajte prosím iné číslo.`
  - no overwrite, no auto-rename, no best-guess correction;
- persistence/service:
  - added invoice service helpers:
    - `is_invoice_number_available(...)`
    - `update_invoice_number(...)` with DB-level integrity fallback handling;
  - kept DB unique constraints as final guard (no schema weakening);
- rebuild flow:
  - after successful invoice-number update, runtime rebuilds updated PDF and returns to `waiting_pdf_decision`;
  - previous PDF file path cleanup is attempted when invoice number change produces a different PDF path;
- voice guard:
  - added text-only guard for invoice-number edit state in voice handler.

### Tests
- added runtime tests for:
  - successful invoice-number edit to free value (+ persistence + PDF rebuild + post-edit state),
  - duplicate invoice-number rejection with required bounded Slovak prompt and preserved old value/state,
  - invalid invoice-number rejection with safe retry prompt and preserved old value/state,
  - voice precision-safe guard for invoice-number edit state.
- preserved and reran existing `upraviť položku` regression coverage.

### Scope boundary
- This runtime patch adds only `edit_invoice_number`.
- Still out of scope (not implemented here):
  - `edit_invoice_date`
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`

## 2026-04-15 — Session 029 — Docs-first full `edit_invoice` / `upraviť` scope map

### Goal
Document one unified planned edit surface for `edit_invoice` so future runtime patches follow a single contract (invoice-level + item-level) instead of separate mini-flows.

### Changes
- updated orchestrator contract to formalize full bounded `edit_invoice` subflow map:
  - invoice-level operations:
    - `edit_invoice_number`
    - `edit_invoice_date`
    - `edit_invoice_contact`
  - item-level operations:
    - `replace_service`
    - `edit_item_description`
    - `edit_item_quantity`
    - `edit_item_unit`
    - `edit_item_unit_price`
- documented required decisions:
  - `edit_invoice` remains reserved top-level token with bounded in-action/subflow runtime;
  - invoice-level and item-level fields are documented separately;
  - precision-sensitive item fields require item targeting;
  - single-item invoices may default to first item;
  - multi-item invoices require explicit selection or bounded clarification;
  - precision-sensitive fields are text-first where ambiguity risk is high;
  - destructive/integrity-sensitive edits fail safe (no silent auto-fix).
- updated in-action registry to split `edit_invoice` map into:
  - `edit_invoice:invoice_level` (planned),
  - `edit_invoice:item_level` (partial: implemented + planned).
- updated TZ section 4.7 to align product-level contract with the same full map and explicit status markers.

### Notes
- Docs-only session; no runtime code changes.
- Newly mapped operations are not runtime-implemented yet:
  - `edit_invoice_number`
  - `edit_invoice_date`
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`
- Existing runtime coverage remains:
  - `replace_service`
  - `edit_item_description`

## 2026-04-15 — Session 028 — Runtime Phase 1 item edit inside `upraviť faktúru`

### Goal
Implement runtime Phase 1 item-edit subflow under post-PDF `upraviť` decision, including separate operations (`replace_service`, `edit_item_description`), `item_description_raw` persistence, bounded validation, and PDF rebuild.

### Changes
- DB/schema:
  - added `invoice_item.item_description_raw` column to bootstrap schema;
  - added backward-compatible bootstrap migration path (`ALTER TABLE ... ADD COLUMN item_description_raw`) for legacy local DB shape;
- service layer:
  - extended `InvoiceItemRecord` with `item_description_raw`;
  - added item update methods:
    - `update_item_service(...)`
    - `update_item_description(...)`
  - added `ContactService.get_by_id(...)` for rebuild path;
- invoice runtime flow:
  - replaced post-PDF `upraviť` placeholder cancel path with real item-edit subflow entry;
  - added bounded states for item-edit:
    - target item selection (future-ready multi-item),
    - operation selection (`replace_service` vs `edit_item_description`),
    - service update input,
    - description text input;
  - single-item invoices default to first item target;
  - multi-item invoices require bounded item index clarification;
  - `replace_service` reuses existing alias dictionary resolution path and does not mutate `item_description_raw`;
  - `edit_item_description` supports `set/replace/clear`, does not mutate canonical service fields;
  - added bounded overlength guard (max 2 rendered detail lines) with Slovak shorten prompt;
  - successful edits rebuild and resend updated PDF, then return to `waiting_pdf_decision`;
- voice guard:
  - in precision-sensitive description state, voice no longer writes final detail; bot requests text input;
  - added text-only guard prompts for other edit subflow precision states;
- PDF/render:
  - `PdfInvoiceItem` now supports optional `detail`;
  - PDF item rendering outputs main service title with optional detail line(s) below;
  - added render-fit helper `validate_item_detail_render_fit(...)` used by runtime validator.

### Tests
- added runtime tests for:
  - replace service with description preserved + PDF rebuild,
  - set/replace/clear description with canonical service preserved,
  - reject too-long description with bounded Slovak prompt and unchanged stored value,
  - single-item default targeting,
  - multi-item missing target clarification,
  - voice text-only guard for description state.

### Notes
- add-item flow remains out of scope.
- Runtime now supports Phase 1 item edit only (replace service, edit description).

## 2026-04-15 — Session 027 — Docs cleanup pass for Phase 1 item edit contract

### Goal
Cleanup docs after initial Phase 1 item-edit patch: remove naming drift, make clear semantics explicit, and document minimal machine-safe bounded output shape for `edit_invoice:item_edit`.

### Changes
- unified canonical operation names across docs for item edit:
  - `replace_service`
  - `edit_item_description`
  - `unknown`
- explicitly fixed description mutation semantics for `edit_item_description`:
  - `set`
  - `replace`
  - `clear`
- documented minimal bounded output shape for planned `edit_invoice:item_edit` in docs:
  - `target_item_index`
  - `operation`
  - `value`

### Notes
- Docs cleanup pass completed.
- Runtime implementation is still not included.

## 2026-04-15 — Session 026 — Docs-first Phase 1 item edit contract inside `upraviť faktúru`

### Goal
Introduce documentation-only source-of-truth contract for Phase 1 `upraviť položku` as in-action edit subflow within future `edit_invoice`, before any runtime patch.

### Changes
- updated orchestrator/docs contracts to formalize that:
  - `upraviť položku` is in-action (not top-level action),
  - Phase 1 item edit supports two distinct operations:
    - service replacement (canonical service identity),
    - free-text detail edit via separate `item_description_raw`;
- recorded render/preview rule:
  - main title from service alias/service DB,
  - optional `item_description_raw` rendered below title with max 2-line limit,
  - no silent truncation; bot must request shorter text in bounded Slovak prompt;
- documented precision-sensitive input rule:
  - `item_description_raw` is text-first/text-only safe in Phase 1,
  - voice must not freely guess long detail text into stored value;
- documented future-ready item-targeting contract:
  - current single-item default may target first item,
  - future multi-item invoices require explicit selection or bounded clarification.

### Notes
- Runtime implementation is not included in this session.
- Key decision: keep canonical service semantics separate from optional free-text item detail (`item_description_raw`).
- Add-item flow remains out of scope for this docs patch.

## 2026-04-14 — Session 025 — `add_service_alias` top-level semantic+voice runtime wiring

### Goal
Make existing manual `/service` flow reachable as canonical top-level action `add_service_alias` from text semantics and voice (top-level), without introducing a second service architecture.

### Changes
- runtime routing:
  - added canonical top-level action `add_service_alias` to top-level bounded resolver branch in `process_invoice_text(...)`;
  - routed semantic `add_service_alias` into the existing `/service` flow entry (shared supplier handler intake), no new service flow created;
- bounded resolver hints:
  - added optional runtime `action_hints` support to resolver payload;
  - used compact hints selectively for `add_service_alias` (ambiguous action) and minimal separation hint for `create_invoice`;
- voice:
  - top-level voice keeps current STT -> top-level semantic path; `add_service_alias` now reaches existing `/service` flow via that path;
  - added explicit voice rejection in service precision-sensitive states:
    - short alias: `Napíšte krátky názov položky textom.`
    - full title: `Napíšte plný názov služby textom.`
- tests:
  - top-level semantic resolution coverage for `add_service_alias`;
  - top-level semantic routing test into shared `/service` flow entry;
  - voice top-level pass-through coverage for `add_service_alias` path;
  - voice rejection coverage for service short/full text-only states;
  - manual `/service` command flow regression test (2-step save flow persists mapping).

### Notes
- Python remains execution authority.
- Bot-facing replies added/updated in runtime are Slovak-only.
- Precision-sensitive service fields remain text-only; no STT guessing for these steps.

## 2026-04-13 — Session 024 — `add_service_alias` ambiguous-action documentation prep

### Goal
Prepare docs before runtime work so `add_service_alias` can be introduced as a canonical ambiguous top-level action (manual flow exists now, semantic/voice invoke later).

### Changes
- updated orchestrator contract with optional semantic action hints section for ambiguous actions;
- added `docs/llm/Bounded_Resolver_Prompt_Template.md` with optional `action_hints` format and compact examples for `create_invoice` and `add_service_alias`;
- added `docs/llm/New_Action_Design_Checklist.md` with ambiguity/hints/canonical-vs-noisy wording checklist items;
- updated canonical action registry to explicitly mark `add_service_alias` as ambiguous, manual implemented, voice top-level invoke not yet, and hint support recommended for future bounded resolution;
- updated TZ with concise optional-hints requirement and canonical-vs-noisy wording separation rule;
- updated README doc pointers.

### Notes
- semantic action hints are documented as optional and selective (not mandatory for every action);
- no runtime code changes were made.

## 2026-04-13 — Session 023 — Canonical action audit repair (manual `/service` flow included)

### Goal
Repair canonical action audit after detecting that previous inventory missed at least one already implemented manual user-facing flow (`add_service_alias` via `/service`).

### Changes
- created `docs/llm/Canonical_Action_Registry.md` with corrected evidence-based inventory:
  - top-level user-facing actions,
  - bootstrap/admin flows,
  - explicit reserved placeholders (`send_invoice`, `edit_invoice`),
  - explicit correction note for implemented manual `/service` flow;
- created `docs/llm/In_Action_Response_Registry.md` with bounded in-action groups, deterministic confirmations, and slot-clarification groups;
- updated `docs/FakturaBot_LLM_Orchestrator_Contract.md` with registry linkage discipline;
- updated `README.md` with pointers to new audit registries.

### Audit correction note
`/service` flow is implemented-manual (command + in-flow text) and persists service alias mappings.  
It is not part of top-level semantic resolver list, but it is still a real user-facing action and must be tracked in canonical action audit.

## 2026-04-13 — Session 022 — Quantity/unit-price clarification semantics broadened

### Goal
Broaden existing bounded slot `quantity_unit_price_pair` from pair-only handling to natural clarification semantics:
- accept quantity + unit-price forms,
- accept price-only fallback (`quantity=1`),
while keeping current architecture and FSM flow unchanged.

### Changes
- `bot/handlers/invoice.py`:
  - updated Slovak clarification prompt to explicitly allow either:
    - quantity + unit price,
    - or price-only when quantity is 1.
- `bot/services/semantic_action_resolver.py`:
  - expanded bounded resolver instruction for `resolve_quantity_unit_price_pair(...)` to support:
    - pair input,
    - single-number input (maps to `quantity=1`);
  - expanded deterministic fallback parser to support additional natural forms:
    - `3 1500`, `3 * 1500`, `3 po 1500`, `3x po 1500`,
    - `три kusy по 1500`, `dva krát po 1500`,
    - `množstvo 3, cena za kus 1500`,
    - `количество 3, цена 1500`,
    - single-number price fallback (`1500` -> `1 × 1500`).
- tests:
  - added/extended slot-clarification tests for pair forms and price-only fallback;
  - kept existing pair regressions and voice routing regression.

### Constraints preserved
- Same slot token (`quantity_unit_price_pair`) and same FSM state (`waiting_slot_clarification`).
- No contact-flow changes, no service-slot repair changes, no generalized slot-clarification redesign.
- Python remains execution authority and source of truth.

## 2026-04-13 — Session 021 — Bounded quantity × unit_price slot clarification in invoice flow

### Goal
Add a dedicated bounded clarification path for missing financial breakdown in invoice flow (`quantity × unit_price`) without architecture redesign and without touching contact/service flows.

### Changes
- `bot/handlers/invoice.py`:
  - added dedicated slot `quantity_unit_price_pair` (reusing existing `waiting_slot_clarification` FSM state);
  - when financial breakdown is unresolved, clarification now targets this dedicated slot;
  - added slot-specific Slovak clarification prompt: `Uveďte množstvo a cenu za jednotku, napr. 2x po 1500.`;
  - wired bounded quantity/unit-price resolver in slot continuation path and update of partial draft fields (`quantity`, `unit_price`) only.
- `bot/services/semantic_action_resolver.py`:
  - added bounded resolver `resolve_quantity_unit_price_pair(...)` with strict structured output contract:
    - `{"canonical":"quantity_unit_price_pair","quantity":...,"unit_price":...}`
    - or `{"canonical":"unknown"}`;
  - LLM request now includes clarification context, `expected_reply_type=quantity_times_unit_price`, and supported languages `uk/ru/sk`;
  - deterministic fallback parser supports multilingual examples including numeric and small-number-word variants.
- tests:
  - added text clarification coverage for:
    - `2 крат по 1500`,
    - `два крат по 1500`,
    - `dva krát po 1500`;
  - added voice routing assertion that STT transcript in `waiting_slot_clarification` is passed unchanged to slot clarification path;
  - added regression for explicit-total-only invoice semantics (`1 × total`) to remain stable;
  - kept/updated existing generalized clarification expectations for the new dedicated financial slot prompt.

### Constraints preserved
- No new FSM state for clarification.
- No contact flow changes.
- Service-slot repair behavior preserved.
- Python remains source of truth for validation, draft update, amount computation, and preview lifecycle.

## 2026-04-12 — Session 020 — Generalized invoice slot clarification + project-wide partial-draft contract

### Goal
Expand already-merged service-slot clarification pattern to other critical invoice slots and formalize slot-level clarification/partial-draft retention as a structured workflow principle.

### Changes
- `bot/handlers/invoice.py`:
  - generalized unresolved-slot handling for invoice draft build with partial retention in FSM (`invoice_partial_draft`);
  - added slot-specific clarification prompts (Slovak-only) for customer, delivery date, due days, quantity, and unit price;
  - added unified continuation path for slot clarification replies that updates one slot and resumes preview build;
  - preserved existing service clarification behavior and compatibility state;
  - improved debug transparency for recoverable unresolved-slot cases.
- `bot/services/llm_invoice_parser.py`:
  - customer-candidate payload failures now emit recoverable `customer_unresolved` with partial payload snapshot.
- tests:
  - added focused invoice clarification coverage for customer/date/due-days/amount slot continuation;
  - preserved service-slot regression path and fatal payload fail-loud behavior checks.
- docs:
  - updated orchestrator contract + TZ + README + CHANGELOG for project-level slot clarification principle.

### Architectural decision
For structured workflows, fail one slot—not whole workflow:
- preserve partial state,
- clarify only unresolved slot,
- continue from current step,
- reserve full reset for fatal errors only.

## 2026-04-12 — Session 019 — AI orchestration contract shift to bounded canonicalization

### Goal
Record architecture milestone: transition from narrow draft/token-routing model to unified semantic resolver contract.

### Decision
- Adopt **Bounded Semantic Canonicalization** as the AI orchestration contract baseline.
- Introduce a unified **Semantic Action Resolver** concept for:
  - top-level action resolution,
  - in-state reply resolution,
  - value/slot canonicalization.
- Keep Python as the only execution authority for validation, context checks, and side effects.

### Notes
- LLM role is semantic canonicalization within Python-defined bounds (allowed set + context), returning one canonical token or `unknown`.
- This is a documentation/architecture alignment milestone; execution authority boundaries remain fail-loud on Python side.

## 2026-04-12 — Session 018 — Post-PDF fail-loud guard + cleanup-order hardening

### Goal
Close two correctness gaps in deterministic post-PDF lifecycle:
- fail loud when post-PDF FSM state misses `last_invoice_id`;
- prioritize invoice-number release by running DB cleanup before PDF-file cleanup.

### Changes
- `bot/handlers/invoice.py`:
  - `process_invoice_postpdf_decision(...)` now validates `last_invoice_id` at start and fails loud (`Návrh faktúry už nie je dostupný...`) instead of claiming success;
  - post-PDF `upraviť`/`zrušiť` cleanup order reversed to DB-first then file-unlink, with isolated error handling so unlink failure no longer blocks DB cleanup;
  - preview-confirm failure cleanup path (after invoice insert) now also does DB cleanup first and performs file cleanup in a separate guarded block.
- `tests/test_invoice_state_decisions.py`:
  - added regression for missing `last_invoice_id` in post-PDF state (no fake success);
  - added regression for unlink failure on post-PDF cancel ensuring invoice row is still deleted;
  - added regression for preview-confirm failure path with unlink failure ensuring invoice row is still deleted.

## 2026-04-12 — Session 017 — Deterministic post-PDF decision FSM + voice state routing

### Goal
Implement deterministic state-based command handling after invoice preview and after PDF send, while keeping existing top-level invoice pre-router unchanged.

### Changes
- `bot/handlers/invoice.py`:
  - kept top-level pre-router as-is (`_normalize_intent_token`, `_detect_invoice_intent`);
  - added deterministic preview parser for `InvoiceStates.waiting_confirm` (`confirm_preview` / `cancel_preview` / `unknown`) with SK/UA/RU yes-no coverage;
  - added deterministic post-PDF parser for `InvoiceStates.waiting_pdf_decision` (`approve_pdf_invoice` / `edit_pdf_invoice` / `cancel_pdf_invoice` / `unknown`) with SK/UA/RU command coverage;
  - extracted reusable handlers:
    - `process_invoice_preview_confirmation(...)`
    - `process_invoice_postpdf_decision(...)`
  - after PDF send, FSM now stores `last_invoice_id`, `last_invoice_number`, `last_pdf_path`;
  - added cleanup on PDF generation/send failure after invoice insert: remove PDF (if exists), delete invoice items + invoice row, clear FSM.
- `bot/handlers/voice.py`:
  - after STT, routes command deterministically by current FSM state:
    - `waiting_confirm` -> preview confirmation processor,
    - `waiting_pdf_decision` -> post-PDF decision processor,
    - otherwise -> existing generic invoice text flow.
- `bot/services/invoice_service.py`:
  - added lifecycle helpers:
    - `update_invoice_status(invoice_id, status)`
    - `delete_invoice_with_items(invoice_id)`
  - cleanup path now fully deletes invoice items + invoice row so invoice number is freed for reuse on `upraviť` / `zrušiť`.
- `tests/`:
  - extended parser tests for required multilingual preview/post-PDF commands;
  - added state-flow tests for preview confirm and post-PDF approve/edit/cancel behaviors, including cleanup and number release;
  - added voice routing tests to verify FSM-aware deterministic dispatch.

### Constraints preserved
- Top-level create/edit/send pre-router behavior remains unchanged.
- LLM still only drafts invoice payload; state command interpretation is deterministic Python.
- User-facing replies introduced/changed in this session are Slovak-only.

## 2026-04-12 — Session 016 — Delivery-date anchor follow-up (UA months + local year scope)

### Goal
Harden delivery-date year anchoring after review:
- add Ukrainian month forms for day/month-without-year detection;
- avoid disabling anchoring when an unrelated year appears elsewhere in the same message.

### Changes
- `bot/handlers/invoice.py`:
  - added Ukrainian month forms and common short forms to date phrase detection (`січня...грудня`, plus short forms);
  - added `_has_explicit_year_near_day_month(...)` and narrowed explicit-year detection to a local span around matched day+month phrase;
  - anchoring is now kept active when a year is present outside the local delivery-date phrase.
- `tests/test_invoice_phase2_ai_layer.py`:
  - added regression for unrelated-year-in-message case (anchoring must still apply);
  - added regression for Ukrainian month form (`4 квітня`);
  - added regression for explicit local year near day+month (anchoring must be disabled and explicit year respected).

### Constraints preserved
- Deterministic behavior only (no fuzzy parsing, no silent heuristics beyond explicit local-span rule).
- Fail-loud behavior unchanged for inconsistent explicit day/month vs payload date.

---

## 2026-04-11 — Session 015 — Invoice Phase 2 delivery-date year anchoring guardrail

### Goal
Stop LLM-induced wrong-year drift for delivery dates when user says only day+month (no explicit year), e.g. `4 апреля` incorrectly becoming `2023-04-04`.

### Changes
- `prompts/invoice_draft_prompt.txt`:
  - hardened instruction for `datum_dodania`: for explicit day+month without year, use current invoice-flow year (issue-date year), and do not invent arbitrary past/future year.
- `bot/handlers/invoice.py`:
  - added deterministic day+month-without-year detector (SK/RU month forms and common short forms);
  - added `_resolve_delivery_date(...)` guardrail:
    - anchors such inputs to `issue_date.year`,
    - corrects mismatched LLM year when month/day match but year drifts,
    - fails loud on inconsistent day/month mismatch between user input and LLM payload.
  - wired preview build flow to use the new guardrail and clear state on fail-loud date inconsistency.
- `tests/test_invoice_phase2_ai_layer.py`:
  - added regression tests for:
    - `4 апреля` → `2026-04-04`,
    - `4 apríla` → `2026-04-04`,
    - mixed voice-like multilingual input without year,
    - explicit year input remains respected.

### Constraints preserved
- Deterministic Python remains source of truth for final invoice draft normalization.
- No schema changes.
- No hidden auto-fix outside deterministic date anchoring rules.

---

## 2026-04-11 — Session 014 — PDF row alignment + supplier VAT wording follow-up

### Goal
Polish two remaining PDF output seams without redesign:
- visually align item description with numeric columns in item rows;
- improve supplier VAT fallback wording when supplier is not VAT registered.

### Changes
- `bot/services/pdf_generator.py`:
  - added `_item_row_description_first_baseline(...)` and used it for item description drawing so single-line descriptions share baseline alignment with quantity/unit/unit-price/total columns, while wrapped descriptions stay centered in the row block;
  - extracted `_format_supplier_ic_dph_line(...)` and changed supplier fallback from `IČ DPH: -` to `IČ DPH: Nie je platiteľ DPH`.
- `tests/test_pdf_generator_layout_wrapping.py`:
  - added regression checks for description baseline behavior (single-line parity with numeric baseline and wrapped text staying inside row bounds);
  - added regression checks for supplier VAT fallback wording.

### Constraints preserved
- No PDF redesign.
- Amount semantics in preview/save/PDF path unchanged.
- Current preview/save flow unchanged.

---

## 2026-04-11 — Session 013 — Invoice service display title regression guard

### Goal
Fix invoice runtime regression where service display title could fall back to raw multilingual text despite existing supplier alias mapping under a deterministic related form.

### Regression shape
- Raw item input: `ремонт`
- Internal canonical term: `oprava`
- Supplier alias stored only as: `opravy -> <full Slovak display title>`
- Previous runtime checked only raw alias key and then fell back to raw text in preview/PDF.

### Root cause
Cross-layer bridge was incomplete: internal canonicalization and supplier alias mapping are separate deterministic layers, but invoice runtime used only raw `service_short_name` for final alias lookup.

### Decision
Keep supplier alias mapping as source of truth for final preview/PDF title and implement deterministic, explicit lookup cascade in invoice handler:
1. raw alias (`service_short_name`)
2. canonical internal term alias (`service_term_internal`)
3. deterministic bridge forms (`oprava -> opravy`)
4. raw fallback as last resort

No fuzzy search, no LLM, no DB/schema changes, no auto-creation of aliases.

### Safeguard
Added regression tests to lock behavior:
- bridge-form resolution (`ремонт -> oprava -> opravy`)
- raw alias priority over fallback stages
- raw fallback when no deterministic alias matches

---


Р В РІР‚вЂњР РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р В Р’В°Р В Р’В» Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР РЋРЎвЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ.
Р В Р’В¤Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В Р’Вµ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’Вµ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРЎвЂњ Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРЎвЂњ, Р В Р’В° Р В РІвЂћвЂ“ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРЎвЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р РЋР Р‰, Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ, scope Р РЋРІР‚С™Р В Р’В° Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚В Р В Р’ВµР В РЎвЂ”Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.

---

## 2026-04-06 вЂ” Session 012 вЂ” PDF wrapping polish (items + identity blocks + Slovak glyph coverage)

### Р¦С–Р»СЊ

Р—Р°РєСЂРёС‚Рё Р·Р°Р»РёС€РєРѕРІС– seam-Рё PDF СЂРµРЅРґРµСЂР° Р±РµР· СЂРµРґРёР·Р°Р№РЅСѓ:
- РїРµСЂРµРЅРѕСЃ РґРѕРІРіРёС… РЅР°Р·РІ РїРѕР·РёС†С–Р№ Сѓ С‚Р°Р±Р»РёС†С–;
- РґРёРЅР°РјС–С‡РЅС– РІРёСЃРѕС‚Рё СЂСЏРґРєС–РІ/identity block-С–РІ;
- СЃС‚Р°Р±С–Р»СЊРЅРёР№ СЂРµРЅРґРµСЂ СЃР»РѕРІР°С†СЊРєРёС… СЃРёРјРІРѕР»С–РІ (РІРєР»СЋС‡РЅРѕ Р· `Дѕ`, `ЕҐ`) Сѓ РїСЂР°РєС‚РёС‡РЅРёС… С‚РµРєСЃС‚Р°С….

### Р©Рѕ Р·РјС–РЅРµРЅРѕ

- `bot/services/pdf_generator.py`:
  - РґРѕРґР°РЅРѕ helper `_wrap_text_lines(...)` РЅР° Р±Р°Р·С– `pdfmetrics.stringWidth(...)` РґР»СЏ word-wrap РІ РѕР±РјРµР¶РµРЅС–Р№ С€РёСЂРёРЅС–;
  - РґРѕРґР°РЅРѕ helper `_measure_party_block_height(...)` РґР»СЏ СЂРѕР·СЂР°С…СѓРЅРєСѓ РґРёРЅР°РјС–С‡РЅРѕС— РІРёСЃРѕС‚Рё identity block;
  - `_draw_party_block(...)` РѕРЅРѕРІР»РµРЅРѕ:
    - РїС–РґС‚СЂРёРјСѓС” wrapped multi-line lines,
    - РїРѕРІРµСЂС‚Р°С” С„Р°РєС‚РёС‡РЅСѓ РІРёСЃРѕС‚Сѓ Р±Р»РѕРєСѓ;
  - СЃРµРєС†С–СЋ `DodГЎvateДѕ` / `OdberateДѕ` РїРµСЂРµРІРµРґРµРЅРѕ РЅР° СЃРїС–Р»СЊРЅРёР№ baseline:
    - РЅРёР¶РЅСЏ РјРµР¶Р° РЅР°СЃС‚СѓРїРЅРѕРіРѕ Р±Р»РѕРєСѓ СЂР°С…СѓС”С‚СЊСЃСЏ РІС–Рґ `max(height_left, height_right)`,
    - РїСЂРёР±СЂР°РЅРѕ СЂРёР·РёРє РІС–Р·СѓР°Р»СЊРЅРѕРіРѕ overlap РјС–Р¶ Р±Р»РѕРєР°РјРё;
  - items table РѕРЅРѕРІР»РµРЅРѕ:
    - `poloЕѕka` РїРµСЂРµРЅРѕСЃРёС‚СЊСЃСЏ РїРѕ СЃР»РѕРІР°С… РІ РјРµР¶Р°С… РєРѕР»РѕРЅРєРё,
    - РІРёСЃРѕС‚Р° row РґРёРЅР°РјС–С‡РЅРѕ Р·СЂРѕСЃС‚Р°С” РїСЂРё 2+ СЂСЏРґРєР°С… РѕРїРёСЃСѓ,
    - С‡РёСЃР»РѕРІС– РєРѕР»РѕРЅРєРё (`mnoЕѕstvo`, `m.j.`, `cena za m.j.`, `spolu`) Р·Р°Р»РёС€РµРЅС– С„С–РєСЃРѕРІР°РЅРёРјРё С‚Р° РІРµСЂС‚РёРєР°Р»СЊРЅРѕ РІРёСЂС–РІРЅСЏРЅС– РїРѕ С†РµРЅС‚СЂСѓ СЂСЏРґРєР°.
- РґРѕРґР°РЅРѕ regression-С‚РµСЃС‚Рё `tests/test_pdf_generator_layout_wrapping.py`:
  - РїРµСЂРµРІС–СЂРєР°, С‰Рѕ РґРѕРІРіРёР№ description СЂРµР°Р»СЊРЅРѕ СЂРѕР·Р±РёРІР°С”С‚СЊСЃСЏ РЅР° РєС–Р»СЊРєР° СЂСЏРґРєС–РІ;
  - РїРµСЂРµРІС–СЂРєР°, С‰Рѕ РІРёСЃРѕС‚Р° identity block Р·Р±С–Р»СЊС€СѓС”С‚СЊСЃСЏ РґР»СЏ РґРѕРІРіРѕС— Р°РґСЂРµСЃРё.

### Р РµР·СѓР»СЊС‚Р°С‚

- РґРѕРІРіС– РЅР°Р·РІРё РїРѕР·РёС†С–Р№ Р±С–Р»СЊС€Рµ РЅРµ РІвЂ™С—Р¶РґР¶Р°СЋС‚СЊ Сѓ РєРѕР»РѕРЅРєСѓ `mnoЕѕstvo`;
- Р°РґСЂРµСЃРЅС– СЂСЏРґРєРё РІ `DodГЎvateДѕ`/`OdberateДѕ` РїРµСЂРµРЅРѕСЃСЏС‚СЊСЃСЏ РІ РјРµР¶Р°С… Р±Р»РѕРєСѓ;
- РІРёСЃРѕС‚Рё Р±Р»РѕРєС–РІ С– СЂСЏРґРєС–РІ Р°РґР°РїС‚РёРІРЅС–, Р±РµР· Р·РјС–РЅРё Р·Р°РіР°Р»СЊРЅРѕС— СЃС‚СЂСѓРєС‚СѓСЂРё one-page invoice;
- Unicode TTF С€Р»СЏС… С‡РµСЂРµР· ReportLab (`Vera.ttf`, `VeraBd.ttf`) Р»РёС€Р°С”С‚СЊСЃСЏ Р±Р°Р·РѕРІРёРј РјРµС…Р°РЅС–Р·РјРѕРј СЂРµРЅРґРµСЂР° СЃР»РѕРІР°С†СЊРєРёС… РґС–Р°РєСЂРёС‚РёРє.

---

## 2026-04-06 вЂ” Session 011 вЂ” PDF polish (Unicode font + payment block spacing)
## 2026-04-06 РІР‚вЂќ Session 011 РІР‚вЂќ PDF polish (Unicode font + payment block spacing)

### Р В¦РЎвЂ“Р В»РЎРЉ

Р вЂ™Р С‘Р С—РЎР‚Р В°Р Р†Р С‘РЎвЂљР С‘ Р В°РЎР‚РЎвЂљР ВµРЎвЂћР В°Р С”РЎвЂљР С‘ Р Р† PDF-РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚РЎвЂ“ Р В±Р ВµР В· РЎР‚Р ВµР Т‘Р С‘Р В·Р В°Р в„–Р Р…РЎС“: РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”РЎвЂ“ Р Т‘РЎвЂ“Р В°Р С”РЎР‚Р С‘РЎвЂљР С‘Р С”Р С‘, РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…РЎвЂ“РЎРѓРЎвЂљРЎРЉ payment Р В±Р В»Р С•Р С”РЎС“ РЎвЂљР В° Р С”Р С•Р Р…РЎРѓР С‘РЎРѓРЎвЂљР ВµР Р…РЎвЂљР Р…РЎвЂ“РЎРѓРЎвЂљРЎРЉ РЎвЂћРЎвЂ“Р Р…Р В°Р В»РЎРЉР Р…Р С•РЎвЂ” Р Р…Р В°Р В·Р Р†Р С‘ Р С—Р С•Р В·Р С‘РЎвЂ РЎвЂ“РЎвЂ”.

### Р В©Р С• Р В·Р СРЎвЂ“Р Р…Р ВµР Р…Р С•

- `bot/services/pdf_generator.py`:
  - Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎР‚Р ВµРЎвЂќРЎРѓРЎвЂљРЎР‚Р В°РЎвЂ РЎвЂ“РЎР‹ Unicode TTF-РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљРЎвЂ“Р Р† РЎвЂЎР ВµРЎР‚Р ВµР В· ReportLab (`Vera.ttf`, `VeraBd.ttf` РЎвЂ“Р В· Р С—Р В°Р С”Р ВµРЎвЂљР В° `reportlab`);
  - РЎС“РЎРѓРЎвЂ“ Р Р†Р С‘Р Т‘Р С‘Р СРЎвЂ“ РЎвЂљР ВµР С”РЎРѓРЎвЂљР С•Р Р†РЎвЂ“ `setFont(...)` Р С—Р ВµРЎР‚Р ВµР Р†Р ВµР Т‘Р ВµР Р…РЎвЂ“ Р Р…Р В° РЎвЂ РЎвЂ“ РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР С‘ (Р В·Р В°Р СРЎвЂ“РЎРѓРЎвЂљРЎРЉ Helvetica), РЎвЂ°Р С•Р В± Р С”Р С•РЎР‚Р ВµР С”РЎвЂљР Р…Р С• РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚Р С‘РЎвЂљР С‘ РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”РЎвЂ“ РЎРѓР С‘Р СР Р†Р С•Р В»Р С‘;
  - payment block Р С—Р ВµРЎР‚Р ВµРЎР‚Р С•Р В±Р В»Р ВµР Р…Р С• РЎС“ Р В±РЎвЂ“Р В»РЎРЉРЎв‚¬ РЎвЂЎР С‘РЎвЂљР В°Р В±Р ВµР В»РЎРЉР Р…Р С‘Р в„– stacked layout:
    - `IBAN` РЎвЂ“ `SWIFT/BIC` РЎС“ Р В»РЎвЂ“Р Р†РЎвЂ“Р в„– Р С”Р С•Р В»Р С•Р Р…РЎвЂ РЎвЂ“ Р Р…Р В° РЎР‚РЎвЂ“Р В·Р Р…Р С‘РЎвЂ¦ РЎР‚РЎРЏР Т‘Р С”Р В°РЎвЂ¦;
    - `SpР“Т‘sob Р“С”hrady` Р Р†Р С‘Р Р…Р ВµРЎРѓР ВµР Р…Р С• Р С•Р С”РЎР‚Р ВµР СР С• Р Р† Р С—РЎР‚Р В°Р Р†РЎС“ РЎвЂЎР В°РЎРѓРЎвЂљР С‘Р Р…РЎС“ Р В±Р ВµР В· Р С—Р ВµРЎР‚Р ВµРЎвЂљР С‘Р Р…РЎС“;
  - Р Р†Р С‘РЎРѓР С•РЎвЂљРЎС“ payment block Р В·Р В±РЎвЂ“Р В»РЎРЉРЎв‚¬Р ВµР Р…Р С• Р С—Р С•Р СРЎвЂ“РЎР‚Р Р…Р С• (`18mm` РІвЂ вЂ™ `24mm`) Р Т‘Р В»РЎРЏ РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…Р С•Р С–Р С• spacing.
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• regression-РЎвЂљР ВµРЎРѓРЎвЂљ `tests/test_invoice_service_item_normalized.py`:
  - Р С—Р ВµРЎР‚Р ВµР Р†РЎвЂ“РЎР‚РЎРЏРЎвЂќ, РЎвЂ°Р С• `description_normalized` РЎР‚Р ВµР В°Р В»РЎРЉР Р…Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† `invoice_item` РЎвЂ“ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С‘Р в„– Р Т‘Р В»РЎРЏ PDF/fallback Р В»Р С•Р С–РЎвЂ“Р С”Р С‘.

### Р В Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ

PDF Р В»Р С‘РЎв‚¬Р С‘Р Р†РЎРѓРЎРЏ Р Р† Р С—Р С•РЎвЂљР С•РЎвЂЎР Р…РЎвЂ“Р в„– РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ“ (Р В±Р ВµР В· major redesign), Р В°Р В»Р Вµ РЎРѓРЎвЂљР В°Р Р† РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…РЎвЂ“РЎв‚¬Р С‘Р С Р Р† РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚РЎвЂ“:
- РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”Р С‘Р в„– РЎвЂљР ВµР С”РЎРѓРЎвЂљ РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚Р С‘РЎвЂљРЎРЉРЎРѓРЎРЏ Unicode-РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР С•Р С;
- payment block Р Р…Р Вµ РЎРѓРЎвЂљР С‘Р С”Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р С—Р С• Р С—Р С•Р В»РЎРЏРЎвЂ¦;
- РЎвЂћРЎвЂ“Р Р…Р В°Р В»РЎРЉР Р…Р В° canonical Р Р…Р В°Р В·Р Р†Р В° Р С—Р С•Р В·Р С‘РЎвЂ РЎвЂ“РЎвЂ” Р В·Р В°Р В»Р С‘РЎв‚¬Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р В·Р В±Р ВµРЎР‚Р ВµР В¶Р ВµР Р…Р С•РЎР‹ Р Р† persistence-РЎв‚¬Р В°РЎР‚РЎвЂ“ Р Т‘Р В»РЎРЏ Р Р†Р С‘Р С”Р С•РЎР‚Р С‘РЎРѓРЎвЂљР В°Р Р…Р Р…РЎРЏ Р Р† PDF.

---

## 2026-04-06 РІР‚вЂќ Session 010 РІР‚вЂќ Optional SMTP in supplier onboarding/storage

### Р В¦РЎвЂ“Р В»РЎРЉ

Р вЂ”Р Р…РЎРЏРЎвЂљР С‘ Р В±Р В»Р С•Р С”РЎС“РЎР‹РЎвЂЎРЎС“ Р Р†Р С‘Р СР С•Р С–РЎС“ SMTP host/user/pass РЎС“ supplier onboarding Р Т‘Р В»РЎРЏ MVP, РЎвЂ°Р С•Р В± Р С—РЎР‚Р С•РЎвЂћРЎвЂ“Р В»РЎРЉ Р С—Р С•РЎРѓРЎвЂљР В°РЎвЂЎР В°Р В»РЎРЉР Р…Р С‘Р С”Р В° Р СР С•Р В¶Р Р…Р В° Р В±РЎС“Р В»Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂљР С‘ Р В±Р ВµР В· email-Р С”Р С•Р Р…РЎвЂћРЎвЂ“Р С–РЎС“РЎР‚Р В°РЎвЂ РЎвЂ“РЎвЂ”.

### Р В©Р С• Р В·Р СРЎвЂ“Р Р…Р ВµР Р…Р С•

- `supplier` schema Р Р† `bot/services/db.py` Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•: `smtp_host`, `smtp_user`, `smtp_pass` РЎвЂљР ВµР С—Р ВµРЎР‚ nullable (`TEXT` Р В±Р ВµР В· `NOT NULL`);
- `SupplierProfile` Р Р† `bot/services/supplier_service.py` Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С• Р Р…Р В° optional SMTP-Р С—Р С•Р В»РЎРЏ (`str | None`);
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·Р В°РЎвЂ РЎвЂ“РЎР‹ optional SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ РЎС“ service layer:
  - Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“/whitespace Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏ Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎР‹РЎвЂљРЎРЉРЎРѓРЎРЏ РЎРЏР С” `NULL`,
  - РЎвЂЎР С‘РЎвЂљР В°Р Р…Р Р…РЎРЏ РЎРѓРЎвЂљР В°РЎР‚Р С‘РЎвЂ¦ РЎР‚РЎРЏР Т‘Р С”РЎвЂ“Р Р† Р В· Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“Р СР С‘ SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏР СР С‘ Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·РЎС“РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Т‘Р С• `None`;
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎРЏР Р†Р Р…Р С‘Р в„– Р С”Р С•Р Р…РЎвЂљРЎР‚Р В°Р С”РЎвЂљ helper `SupplierService.has_complete_smtp_config(profile)`:
  - email send Р С—Р С•Р Р†Р С‘Р Р…Р ВµР Р… Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљР С‘РЎРѓРЎРЉ РЎвЂљРЎвЂ“Р В»РЎРЉР С”Р С‘ Р С”Р С•Р В»Р С‘ Р Р†РЎРѓРЎвЂ“ 3 SMTP Р С—Р С•Р В»РЎРЏ Р В·Р В°Р Т‘Р В°Р Р…РЎвЂ“;
- onboarding flow (`bot/handlers/onboarding.py`) Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•:
  - SMTP Р С”РЎР‚Р С•Р С”Р С‘ Р СР В°РЎР‹РЎвЂљРЎРЉ РЎвЂљР ВµР С”РЎРѓРЎвЂљ `voliteР”С•nР“В©, "-" alebo /skip pre preskoР”РЊenie`,
  - `-`, `/skip` РЎвЂ“ Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏ Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·РЎС“РЎР‹РЎвЂљРЎРЉРЎРѓРЎРЏ РЎРЏР С” `None`,
  - summary Р С—Р С•Р С”Р В°Р В·РЎС“РЎвЂќ `-` Р Т‘Р В»РЎРЏ Р Р†РЎвЂ“Р Т‘РЎРѓРЎС“РЎвЂљР Р…РЎвЂ“РЎвЂ¦ SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ.
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎвЂљР ВµРЎРѓРЎвЂљР С‘ `tests/test_supplier_smtp_optional.py`:
  - save/load supplier Р В±Р ВµР В· SMTP;
  - save/load supplier Р В· SMTP;
  - Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·Р В°РЎвЂ РЎвЂ“РЎРЏ skip token/empty Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ.

### Р В Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ

`/supplier` Р СР С•Р В¶Р Вµ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р С‘РЎвЂљР С‘РЎРѓРЎРЏ Р В±Р ВµР В· SMTP Р Р…Р В°Р В»Р В°РЎв‚¬РЎвЂљРЎС“Р Р†Р В°Р Р…РЎРЉ; Р С—РЎР‚Р С•РЎвЂћРЎвЂ“Р В»РЎРЉ РЎС“РЎРѓР С—РЎвЂ“РЎв‚¬Р Р…Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ РЎвЂ“ Р Р†Р С‘Р С”Р С•РЎР‚Р С‘РЎРѓРЎвЂљР С•Р Р†РЎС“РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† invoice/PDF flow Р В±Р ВµР В· Р В·Р СРЎвЂ“Р Р… Р С”РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР Р…Р С•Р С–Р С• MVP РЎв‚¬Р В»РЎРЏРЎвЂ¦РЎС“.

---

## 2026-04-06 РІР‚вЂќ Session 009 РІР‚вЂќ Service alias list cleanup (inactive hidden by default)
## 2026-04-06 Р Р†Р вЂљРІР‚Сњ Session 009 Р Р†Р вЂљРІР‚Сњ Service alias list cleanup (inactive hidden by default)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РЎСџР РЋР вЂљР В РЎвЂР В Р’В±Р РЋР вЂљР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚вЂњ alias mappings Р В Р’В·Р РЋРІР‚вЂњ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РўвЂР В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў `/service` Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂќР РЋРЎвЂњ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂ UX flow.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- `ServiceAliasService.list_mappings(...)` Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - default Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р РЋРІР‚С™Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В РЎвЂќР В РЎвЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂ (`is_active = 1`);
  - Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂўР В РЎвЂќ Р РЋР С“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В РЎвЂў (`canonical_title`, `alias`);
  - Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В РЎвЂ”Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `include_inactive=True` Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ;
- `/service` handler Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В РЎвЂР В Р вЂ Р РЋР С“Р РЋР РЏ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂў Р В Р вЂ Р В РЎвЂР В РЎвЂќР В Р’В»Р В РЎвЂР В РЎвЂќР РЋРЎвЂњ Р РЋРІР‚вЂњ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’Вµ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ alias;
- Р РЋРІР‚С™Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В РЎвЂўР В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ `deactivate_mapping` Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р Р†Р вЂљРІвЂћСћР РЋР РЏР В Р вЂ Р В Р’В»Р РЋР РЏР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРЎвЂњ default list;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ alias Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  list;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў `resolve_alias` Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ alias;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В° `include_inactive=True`.

### Р В Р’В Р В Р’ВµР В Р’В·Р РЋРЎвЂњР В Р’В»Р РЋР Р‰Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™

Normal `/service` list Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР РЋРІР‚В¦Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ mappings, Р В Р’В° Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ invoice Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚вЂњ alias.

---

## 2026-04-06 Р Р†Р вЂљРІР‚Сњ Session 008 Р Р†Р вЂљРІР‚Сњ Service alias Р Р†РІР‚В РІР‚в„ў canonical invoice title normalization

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В Р’ВµР РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ normalization layer Р В РўвЂР В Р’В»Р РЋР РЏ invoice item:
alias (Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В Р’В° spoken/text Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В°) Р Р†РІР‚В РІР‚в„ў canonical full title, Р В РЎвЂќР В Р’ВµР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В РЎвЂўР В РЎВ.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ persistence-Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР вЂ№ `supplier_service_alias`:
  - Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋР РЏ `id`, `supplier_id`, `alias`, `canonical_title`, `is_active`, `created_at`;
  - `alias` Р В Р’В· case-insensitive Р РЋРЎвЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р РЋР вЂ№ Р В Р вЂ  Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р РЋРІР‚В¦ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В° (`UNIQUE(supplier_id, alias)` + `COLLATE NOCASE`);
  - bootstrap/schema-check Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В Р вЂ  `init_db` Р В Р’В· fail-loud Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР В РўвЂР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂќР В РЎвЂўР РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ Р В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В¦Р В Р’ВµР В РЎВР РЋРІР‚вЂњ;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/service_alias_service.py`:
  - `create_mapping`,
  - `list_mappings`,
  - `resolve_alias` (exact + trimmed + case-insensitive),
  - `deactivate_mapping` (MVP-safe optional helper);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў supplier-side chat flow `/service` (`bot/handlers/supplier.py`):
  - Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂќР РЋРЎвЂњ alias mappings,
  - Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ 1: Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ alias,
  - Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ 2: Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ canonical title,
  - Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂўР В РЎвЂќ;
- invoice flow (`bot/handlers/invoice.py`) Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ `item_name_raw`,
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂ preview/save/PDF Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ deterministic alias resolution Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· Python/SQLite,
  - Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ match Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ canonical title Р РЋР РЏР В РЎвЂќ `item_name_final`,
  - Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ miss Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ fallback Р В Р вЂ¦Р В Р’В° raw text;
- preview Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў: Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР РЋРІР‚Сњ `raw` Р РЋРІР‚вЂњ `finР вЂњР Р‹lna` Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р РЋРЎвЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ;
- save/PDF Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р РЋРЎвЂњ `invoice_item.description_normalized` Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚С›Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В° (canonical Р В Р’В°Р В Р’В±Р В РЎвЂў fallback raw),
  - PDF Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р РЋРІР‚С›Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРЎвЂњ Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р РЋРЎвЂњ (`description_normalized` Р В Р’В· fallback Р В Р вЂ¦Р В Р’В° `description_raw`);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С™Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ `tests/test_service_alias_service.py`:
  - alias resolution success,
  - fallback when alias not found,
  - case-insensitive + trimmed match.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- fuzzy matching;
- auto-canonicalization Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· LLM;
- Р РЋР С“Р В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ admin/settings UI Р В РўвЂР В Р’В»Р РЋР РЏ mappings.

### Р В Р’В Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

Final service/item title Р В РўвЂР В Р’В»Р РЋР РЏ invoice preview/save/PDF Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В Р вЂ Р В РЎвЂР В Р’В·Р В Р вЂ¦Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’ВµР РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў
Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· supplier-defined mapping Р РЋРЎвЂњ Python/storage, Р В Р’В° Р В Р вЂ¦Р В Р’Вµ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· LLM paraphrasing.

---

## 2026-04-03 Р Р†Р вЂљРІР‚Сњ Session 007 Р Р†Р вЂљРІР‚Сњ Phase 4: invoice draft Р Р†РІР‚В РІР‚в„ў confirm Р Р†РІР‚В РІР‚в„ў PDF preview

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ invoice flow Р В РўвЂР В Р’В»Р РЋР РЏ text/voice input:
draft Р Р†РІР‚В РІР‚в„ў local contact resolution Р Р†РІР‚В РІР‚в„ў preview Р Р†РІР‚В РІР‚в„ў confirm Р Р†РІР‚В РІР‚в„ў save Р Р†РІР‚В РІР‚в„ў PDF preview.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў persistence Р В РўвЂР В Р’В»Р РЋР РЏ faktР вЂњРЎвЂќr:
  - Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР РЏ `invoice`,
  - Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР РЏ `invoice_item`,
  - fail-loud schema compatibility checks Р В Р’В±Р В Р’ВµР В Р’В· auto-drop;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/invoice_service.py`:
  - Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР В РЎВР В Р’ВµР РЋР вЂљР РЋРЎвЂњ `RRRRNNNN`,
  - save faktР вЂњРЎвЂќry Р В Р’В· Р В РЎвЂўР В РўвЂР В Р вЂ¦Р В РЎвЂР В РЎВ Р РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂќР В РЎвЂўР В РЎВ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ,
  - get by id/number,
  - save `pdf_path`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/pdf_generator.py` (reportlab + qrcode):
  - one-page business invoice layout,
  - DodР вЂњР Р‹vateР вЂќРЎвЂў/OdberateР вЂќРЎвЂў block,
  - meta/dates block,
  - payment block,
  - items table,
  - strong `Na Р вЂњРЎвЂќhradu` block,
  - QR block;
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/invoice.py`:
  - `/invoice` text entry point,
  - preview Р РЋР С“Р В Р’В»Р В РЎвЂўР В Р вЂ Р В Р’В°Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂќР В РЎвЂўР РЋР вЂ№,
  - confirm (`ano`/`nie`),
  - PDF decision step (`schvР вЂњР Р‹liР вЂўРўС’`/`upraviР вЂўРўС’`);
- voice flow Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРЎвЂњ Р РЋРІР‚С™Р В РЎвЂўР В РІвЂћвЂ“ Р РЋР С“Р В Р’В°Р В РЎВР В РЎвЂР В РІвЂћвЂ“ invoice path:
  - STT text Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ Р В РЎвЂўР В Р’В±Р РЋР вЂљР В РЎвЂўР В Р’В±Р В Р’В»Р РЋР РЏР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· Р РЋР С“Р В РЎвЂ”Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Phase 4 flow;
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў local contact-only resolution:
  - exact match,
  - case-insensitive exact match;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў date semantics Р В Р вЂ  Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРІР‚вЂњ:
  - `issue_date` = auto today,
  - Р В РўвЂР В Р’В°Р РЋРІР‚С™Р В Р’В° Р В Р’В· input Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ `delivery_date`,
  - Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋР РЏ Р Р†Р вЂљРІР‚Сњ `delivery_date = issue_date`,
  - `due_date = issue_date + due_days`.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- email send;
- external lookup / FinStat;
- contract extraction;
- fuzzy matching;
- multi-item UI;
- advanced edit workflow;
- migration framework.

### Follow-up note (QR scope honesty)

- Phase 4 merge Р В Р вЂ¦Р В Р’Вµ Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· QR subsystem.
- Р В РЎСџР В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ QR block Р РЋРЎвЂњ PDF Р В Р вЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РЎВ placeholder-Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ Р В РўвЂР В Р’В»Р РЋР РЏ payment QR.
- Р В РЎвЂєР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ:
  - Р В РўвЂР В РЎвЂўР РЋР С“Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В РЎвЂР РЋРІР‚С™Р В РЎвЂ/Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В¶Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Pay by Square payload generator;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р РЋР Р‰ payload Р РЋРІР‚вЂњР В Р’В· Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВ Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ.

---


## 2026-04-03 Р Р†Р вЂљРІР‚Сњ Session 006 Р Р†Р вЂљРІР‚Сњ PDF Layout Spec (docs-only)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРЎвЂњ docs-only Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р В Р вЂ Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ PDF-Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р’В°.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р В РўвЂР В РЎвЂўР В РЎвЂќР РЋРЎвЂњР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™ `docs/FakturaBot_PDF_Layout_Spec.md`;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў purpose PDF Р РЋР РЏР В РЎвЂќ Р РЋРІР‚РЋР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В РЎвЂ wow-Р В Р’ВµР РЋРІР‚С›Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ;
- Р В РЎвЂўР В РЎвЂ”Р В РЎвЂР РЋР С“Р В Р’В°Р В Р вЂ¦Р В РЎвЂў design principles (clean, restrained, readability-first);
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў color principles Р В Р’В· Р В Р вЂ Р В РЎвЂР В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР РЋР вЂ№ Р В РўвЂР В Р вЂ Р В РЎвЂўР РЋРІР‚В¦ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР РЋРІР‚СњР В РЎВР В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ Р РЋРІР‚С›Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В¦ Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ¦Р РЋРІР‚вЂњР В Р вЂ  Р В Р’В±Р В Р’ВµР В Р’В· Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚С™Р В Р’В°Р В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ;
- Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂўР В РЎвЂќ Р В РЎвЂўР В Р’В±Р В РЎвЂўР В Р вЂ Р Р†Р вЂљРІвЂћСћР РЋР РЏР В Р’В·Р В РЎвЂќР В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В¦ layout-Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР РЋРІР‚вЂњР В Р вЂ :
  header, DodР вЂњР Р‹vateР вЂќРЎвЂў/OdberateР вЂќРЎвЂў, meta/dates, payment, items table, total, QR, footer;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў date semantics Р В РўвЂР В Р’В»Р РЋР РЏ `DР вЂњР Р‹tum vystavenia`, `DР вЂњР Р‹tum dodania`, `DР вЂњР Р‹tum splatnosti`;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў preview/approval rule (`schvР вЂњР Р‹liР вЂўРўС’` / `upraviР вЂўРўС’`);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў typography/spacing guidelines Р РЋРІР‚С™Р В Р’В° Р РЋР С“Р В Р’ВµР В РЎвЂќР РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р Р†Р вЂљРЎС™Do notР Р†Р вЂљРЎСљ.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ Р РЋР С“Р РЋР РЏ PDF generator;
- Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋР вЂ№Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂўР РЋР С“Р РЋР РЏ Р В РЎС›Р В РІР‚вЂќ;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋРІР‚С›Р РЋРІР‚вЂњР РЋРІР‚РЋР РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В Р’В° Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р В РЎВР В РЎвЂ layout specification.

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 004 Р Р†Р вЂљРІР‚Сњ Phase 2: supplier onboarding (chat-based)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding Р В Р’В±Р В Р’ВµР В Р’В· fancy UI, Р В Р’В±Р В Р’ВµР В Р’В· Р РЋР С“Р В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ FSM-Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ,
Р РЋР РЏР В РЎвЂќ Р В Р’В±Р В Р’В°Р В Р’В·Р РЋРЎвЂњ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ invoice phases.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў SQLite schema `supplier` Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В°;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/supplier_service.py` Р В Р’В· Р В РЎвЂўР В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏР В РЎВР В РЎвЂ:
  - create or replace profile,
  - get by `telegram_id`,
  - update profile (Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· upsert);
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/onboarding.py` Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ chat flow:
  12 Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋРІР‚вЂњР В Р вЂ  Р Р†РІР‚В РІР‚в„ў summary Р Р†РІР‚В РІР‚в„ў confirm (`yes/no`) Р Р†РІР‚В РІР‚в„ў save;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў MVP-Р РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р’ВµР В Р вЂ¦Р РЋР Р‰ Р В Р вЂ Р В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РўвЂР В Р’В»Р РЋР РЏ IР вЂќР Р‰O/DIР вЂќР Р‰/IР вЂќР Р‰ DPH/email/IBAN/days_due;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў UX-Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ, Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р РЋРЎвЂњР В Р’В¶Р В Р’Вµ Р РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚Сњ, Р В Р’В· Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚СњР РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋРІР‚С™Р В РЎвЂ flow Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р вЂ¦Р В РЎвЂў.

### Р В РІР‚ВР В Р’ВµР В Р’В·Р В РЎвЂ”Р В Р’ВµР В РЎвЂќР В Р’В° / Р В РЎвЂўР В Р’В±Р В РЎВР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ

- SMTP Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР Р‰ Р В Р вЂ¦Р В Р’Вµ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ;
- Р РЋРЎвЂњ summary Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР Р‰ Р В РЎВР В Р’В°Р РЋР С“Р В РЎвЂќР РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ (`********`);
- Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ SMTP Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР РЏ Р В Р вЂ  Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р РЋРІР‚вЂњ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ plain-text Р РЋРЎвЂњ SQLite (Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂў, Р В РўвЂР В Р’В»Р РЋР РЏ MVP);
- production-grade secure credential storage Р РЋРІР‚В°Р В Р’Вµ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- contact onboarding;
- invoice save flow;
- PDF/email send;
- contract extraction;
- lookup API;
- Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ settings center.

### Р В Р’В Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

Phase 2 Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В° Р РЋРІР‚С™Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р’В° Р В Р вЂ  Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р РЋРІР‚В¦ simple chat-based supplier onboarding.
Fancy UI Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў.
Supplier profile Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ  Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РЎВ persistence-Р РЋРІвЂљВ¬Р В Р’В°Р РЋР вЂљР В РЎвЂўР В РЎВ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ invoice phases.

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 003 Р Р†Р вЂљРІР‚Сњ Phase 1: voice-to-draft preview flow

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ wow-flow: Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“ Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў AI draft preview Р В Р вЂ  Р РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р РЋРІР‚вЂњ.
Р В РІР‚ВР В Р’ВµР В Р’В· save Р В Р вЂ  Р В РІР‚ВР В РІР‚Сњ, Р В Р’В±Р В Р’ВµР В Р’В· PDF, Р В Р’В±Р В Р’ВµР В Р’В· email, Р В Р’В±Р В Р’ВµР В Р’В· supplier/contact persistence.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- `bot/services/speech_to_text.py` Р Р†Р вЂљРІР‚Сњ STT Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· OpenAI Audio API (Whisper)
- `bot/services/llm_invoice_parser.py` Р Р†Р вЂљРІР‚Сњ LLM draft parsing Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· OpenAI Chat API
- `bot/handlers/voice.py` Р Р†Р вЂљРІР‚Сњ voice message handler: download Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў parse Р Р†РІР‚В РІР‚в„ў preview
- `prompts/invoice_draft_prompt.txt` Р Р†Р вЂљРІР‚Сњ Р РЋР С“Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’ВµР В РЎВР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎВР В РЎвЂ”Р РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ Р В РЎвЂР РЋРІР‚С™Р РЋР РЏР В РЎвЂ“Р РЋРЎвЂњ invoice draft
- `bot/config.py` Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `openai_stt_model`, `openai_llm_model`
- `bot/main.py` Р Р†Р вЂљРІР‚Сњ config Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  polling workflow data
- `requirements.txt` Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `openai>=1.30`

### Р В РЎвЂ™Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р РЋРІР‚вЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

- STT Р РЋРІР‚вЂњ LLM parsing Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В Р вЂ Р В Р’В° Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРІР‚вЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р РЋРІР‚вЂњР РЋР С“Р В РЎвЂ, Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В»Р В РЎвЂР РЋРІР‚С™Р РЋРІР‚вЂњ Р В Р вЂ  Р В РЎвЂўР В РўвЂР В РЎвЂР В Р вЂ¦
- Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В РЎвЂ Р В Р вЂ Р В РЎвЂР В РўвЂР В Р’В°Р В Р’В»Р РЋР РЏР РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РЎвЂўР В РўвЂР РЋР вЂљР В Р’В°Р В Р’В·Р РЋРЎвЂњ Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р В РЎвЂўР В Р’В±Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂќР В РЎвЂ (try/finally)
- Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў `OPENAI_API_KEY` Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р Р†Р вЂљРІР‚Сњ app Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂў, voice handler
  Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р В Р’В·Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР В Р’В»Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В±Р В Р’ВµР В Р’В· Р В РЎвЂ”Р В Р’В°Р В РўвЂР РЋРІР‚вЂњР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ
- graceful error handling Р В РўвЂР В Р’В»Р РЋР РЏ STT Р РЋРІР‚вЂњ LLM failure Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂў

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- save draft Р РЋРЎвЂњ Р В РІР‚ВР В РІР‚Сњ
- PDF Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ
- email
- supplier/contact persistence
- contract extraction
- FSM / multi-step dialog

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Phase 2: Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding (chat-based, sequential)

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 002 Р Р†Р вЂљРІР‚Сњ Phase 0 implementation skeleton

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- docs bootstrap Р В Р вЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РЎВ;
- Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ  Phase 0 implementation skeleton;
- Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ deploy Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў;
- Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р Р†Р вЂљРІР‚Сњ Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В Р’В»Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ runnable Р В РЎвЂќР В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р РЋР С“ Р В Р’В±Р В Р’ВµР В Р’В· feature-Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР РЋРЎвЂњ `bot/`, `prompts/`, `storage/`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `config.py` Р В Р’В· Р РЋРІР‚РЋР В РЎвЂР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ `.env`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў SQLite bootstrap Р В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂќР В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂ№ Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р В Р’ВµР РЋР вЂ№ `supplier`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `/start` handler Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р В РЎвЂќ aiogram polling;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `.env.example`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ voice / Whisper / LLM draft / PDF / email / contract extraction;
- Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ Р РЋР С“Р РЋР РЏ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ deploy;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ internet lookup, SaaS/multi-tenant Р В Р’В°Р В Р’В±Р В РЎвЂў Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІвЂљВ¬Р РЋРІР‚вЂњ Р В РЎВР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В Р’В° Phase 0.

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р Р†Р вЂљРІР‚Сњ Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ voice/draft flow;
- Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р Р†Р вЂљРІР‚Сњ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ onboarding Р РЋРІР‚С™Р В Р’В° contacts Р РЋРЎвЂњ chat-based Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р’В»Р РЋРІР‚вЂњ.

---

## 2026-03-30 Р Р†Р вЂљРІР‚Сњ Session 001 Р Р†Р вЂљРІР‚Сњ Р В РЎв„ўР В РЎвЂўР В Р вЂ¦Р РЋРІР‚В Р В Р’ВµР В РЎвЂ”Р РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р В РЎСџР В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚В Р РЋРІР‚вЂњР В Р вЂ¦Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎВР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ SaaS Р В Р вЂ¦Р В Р’В° Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРІР‚вЂњ Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В РЎвЂР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂў.
- Р В РЎСџР В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р РЋР С“ Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР С“Р В Р’В°Р В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р’В°.
- FakturaBot Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В Р’В»Р РЋР РЏР В РўвЂР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В Р’В° Р В РўвЂР В Р’ВµР В РЎВР В РЎвЂўР В Р вЂ¦Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р РЋРІР‚вЂњР РЋРІР‚С™Р РЋР вЂљР В РЎвЂР В Р вЂ¦Р В Р’В°.
- Р В РЎСџР РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ Р РЋРІР‚РЋР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В Р’В° Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚вЂќ Р В РЎВР В РЎвЂўР В РўвЂР В Р’ВµР В Р’В»Р РЋРІР‚вЂњ:
  Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р РЋРІР‚вЂњР В Р вЂ  Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р В Р’В·Р В Р’В°Р В РўвЂР В Р’В°Р РЋРІР‚РЋР РЋРІР‚вЂњ Р В РЎВР В Р’В°Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В±Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРЎвЂњ.

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР В РЎвЂР РЋРІР‚С™Р РЋР Р‰ Р РЋРЎвЂњ MVP v1.0

- Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™
- Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР В РІвЂћвЂ“
- Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР В РІвЂћвЂ“
- Whisper STT
- AI invoice draft
- Р РЋР вЂљР РЋРЎвЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding
- Р РЋР вЂљР РЋРЎвЂњР РЋРІР‚РЋР В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В°
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В° Р В Р’В· Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРЎвЂњ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· AI
- Р В Р’В»Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В Р’В°Р В РўвЂР РЋР вЂљР В Р’ВµР РЋР С“Р В Р вЂ¦Р В Р’В° Р В РЎвЂќР В Р вЂ¦Р В РЎвЂР В РЎвЂ“Р В Р’В°
- Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂўР РЋР вЂљР В РЎвЂР В РЎвЂ“Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋРЎвЂњ Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРЎвЂњ
- PDF-Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р’В°
- QR Pay by Square
- email-Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В РЎвЂќР В Р’В°
- Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљ
- Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“Р В РЎвЂ
- SQLite
- Docker deploy

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў

- lookup Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р РЋРІР‚вЂњР В Р вЂ  Р В Р’В· Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™Р РЋРЎвЂњ
- FinStat
- ORSR Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ
- Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ OCR pipeline
- Google Drive
- billing
- multi-tenant Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р’В°
- Р В РЎвЂќР В Р’В°Р В Р’В±Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’В°

### Р В РЎв„ўР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂ”Р В РЎвЂў AI

- AI Р В Р вЂ¦Р В Р’Вµ Р РЋРІР‚Сњ Р В РўвЂР В Р’В¶Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В»Р В РЎвЂўР В РЎВ Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В РЎвЂ.
- Р В Р в‚¬Р РЋР С“Р РЋРІР‚вЂњ Р В РЎвЂќР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р РЋРІР‚вЂњ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋР вЂ№Р РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· draft + validation + confirmation.
- Р В РІР‚СњР В Р’В»Р РЋР РЏ Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР В Р вЂ  Р В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎВР В РЎвЂўР В РўвЂР В Р’ВµР В Р’В»Р РЋР Р‰:
  Python orchestrates Р Р†РІР‚В РІР‚в„ў AI extracts Р Р†РІР‚В РІР‚в„ў Python validates Р Р†РІР‚В РІР‚в„ў user confirms.
- AI Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РўвЂР В РЎвЂР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р В Р’В° Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В РЎвЂР РЋРІР‚В¦ Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ  Р РЋР вЂљР В РЎвЂўР В Р’В±Р РЋРІР‚вЂњР РЋРІР‚С™.

### Р В РЎСџР РЋР вЂљР В РЎвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР РЋР вЂ№

Р В РІР‚СљР В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ input Р РЋРІР‚С™Р В РЎвЂР В РЎвЂ”Р РЋРЎвЂњ:
Р Р†Р вЂљРЎС™Р В РЎС›Р В Р’ВµР РЋР С“Р В Р’В»Р В Р’В° Р В Р Р‹Р В Р’В»Р В РЎвЂўР В Р вЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚вЂњР РЋР РЏ Р В Р’В·Р В Р’В° Р В РЎвЂўР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В РЎвЂ Р В РЎвЂўР В РўвЂР В РЎвЂР В Р вЂ¦ Р В РЎвЂќР РЋРЎвЂњР РЋР С“ Р РЋРІР‚С™Р В Р’В°Р В РЎВ 2000 Р РЋРІР‚СњР В Р вЂ Р РЋР вЂљ, Р В РўвЂР В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР В РЎВ Р В Р вЂ Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ 30 Р В РЎВР В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В Р’В° 2026, Р РЋР С“Р В РЎвЂ”Р В Р’В»Р В Р’В°Р РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™ 30 Р В РўвЂР В Р вЂ¦Р РЋРІР‚вЂњР В Р вЂ Р Р†Р вЂљРЎСљ

Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋР вЂ№Р В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋР С“Р РЋР Р‰ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРЎвЂњ invoice draft-Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™Р В РЎвЂќР РЋРЎвЂњ.

### Р В РІР‚в„ўР В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р В Р’В° Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В° Р РЋРІР‚вЂњР В РўвЂР В Р’ВµР РЋР РЏ

FakturaBot Р Р†Р вЂљРІР‚Сњ Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р В Р’В±Р В РЎвЂўР РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљ.
Р В Р’В¦Р В Р’Вµ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂ Р В РЎвЂќР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В Р’В° Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В Р’В±Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’ВµР РЋР С“-Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚В Р В Р’ВµР РЋР С“.

### Р В РІР‚СњР В РЎвЂўР В РЎвЂќР РЋРЎвЂњР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В РЎвЂ

Р В РЎвЂ™Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎС›Р В РІР‚вЂќ:
`docs/TZ_FakturaBot.md`

### Р В РЎСљР В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р РЋРІР‚вЂњ Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќР В РЎвЂ

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР РЋРЎвЂњ Р РЋР вЂљР В Р’ВµР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР РЋР вЂ№
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ README
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ AGENTS
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ CHANGELOG
- Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎС›Р В РІР‚вЂќ Р РЋРЎвЂњ docs
- Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂќР В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р РЋР С“ MVP

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 003 Р Р†Р вЂљРІР‚Сњ Phase 1 voice-to-draft preview

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Phase 1 Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ¦Р В Р’Вµ Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РІвЂћвЂ“ voice Р Р†РІР‚В РІР‚в„ў text smoke test, Р В Р’В° Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ wow-flow:
  **voice Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў AI draft preview**
- Р В РЎСљР В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р РЋРІР‚вЂњ Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В РЎВР В РЎвЂў:
  - save Р РЋРЎвЂњ Р В РІР‚ВР В РІР‚Сњ
  - PDF
  - email
  - supplier/contact persistence
- STT Р РЋРІР‚вЂњ LLM parsing Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РўвЂР РЋРІР‚вЂњР В Р’В»Р В Р’ВµР В Р вЂ¦Р РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’В° Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРІР‚вЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р РЋРІР‚вЂњР РЋР С“Р В РЎвЂ.
- Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚вЂњ API Р В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  repo; Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ `.env`.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР РЋРІР‚С™Р РЋР вЂљР В РЎвЂР В РЎВР В РЎвЂќР РЋРЎвЂњ `OPENAI_STT_MODEL` Р РЋРІР‚вЂњ `OPENAI_LLM_MODEL` Р РЋРЎвЂњ config;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/speech_to_text.py`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/llm_invoice_parser.py`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў prompt `prompts/invoice_draft_prompt.txt`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/voice.py`;
- Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В РЎвЂў voice router;
- Phase 1 flow Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ:
  Telegram voice Р Р†РІР‚В РІР‚в„ў local temp file Р Р†РІР‚В РІР‚в„ў OpenAI transcription Р Р†РІР‚В РІР‚в„ў OpenAI draft parsing Р Р†РІР‚В РІР‚в„ў preview in chat.

### Р В РІР‚в„ўР В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р РЋРІР‚вЂњ Р В РўвЂР РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњ / Р РЋРЎвЂњР РЋР вЂљР В РЎвЂўР В РЎвЂќР В РЎвЂ

- Р В РЎСљР В Р’В° Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР РЋР РЏР РЋРІР‚С™Р В РЎвЂ, Р РЋРІР‚В°Р В РЎвЂў `.env` Р В Р вЂ Р В Р вЂ¦Р В Р’ВµР РЋР С“Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРЎвЂњ `.gitignore`.
- Р В РЎвЂєР В РўвЂР В РЎвЂР В Р вЂ¦ `OPENAI_API_KEY` Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚вЂњ Р В РўвЂР В Р’В»Р РЋР РЏ STT, Р РЋРІР‚вЂњ Р В РўвЂР В Р’В»Р РЋР РЏ LLM parsing.
- Р В РЎСџР В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ voice-flow Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ”Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™, Р В Р’В° Р РЋР С“Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В Р’В±Р РЋРЎвЂњ Р В Р’В·Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋРІР‚С™Р В РЎвЂ Р В Р вЂ¦Р В Р’В°Р В РЎВР РЋРІР‚вЂњР РЋР вЂљ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’В°.
- Preview Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂќР РЋР вЂљР В РЎвЂР В Р вЂ Р РЋРІР‚вЂњ Р В Р’В·Р В Р вЂ¦Р В Р’В°Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р В РЎвЂР В РЎвЂ”Р РЋРЎвЂњ `Р Р†Р вЂљРІР‚Сњ Р Р†Р вЂљРІР‚Сњ`; Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В РЎвЂўР В РўвЂР РЋР вЂљР В Р’В°Р В Р’В·Р РЋРЎвЂњ Р РЋРІР‚РЋР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ.
- Р В Р вЂЎР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў STT Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ  Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР В РЎвЂўР В Р’В¶Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™, Р В Р вЂ¦Р В Р’Вµ Р В РЎВР В РЎвЂўР В Р’В¶Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР РЋРІР‚С™Р В РЎвЂ Р В РІвЂћвЂ“Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ  LLM Р Р†Р вЂљРІР‚Сњ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В Р’В·Р РЋРЎвЂњР В РЎвЂ”Р В РЎвЂР В Р вЂ¦Р РЋР РЏР РЋРІР‚С™Р В РЎвЂ flow Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’Вµ.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ supplier onboarding, contacts, PDF, email, contract extraction;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В°Р РЋР С“Р РЋР Р‰ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В Р’В° save draft;
- Р В Р вЂ¦Р В Р’Вµ Р В Р’В±Р РЋРЎвЂњР В Р’В»Р В РЎвЂў Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў deploy;
- internet lookup / FinStat Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР РЋР РЏР РЋРІР‚С™Р РЋР Р‰ Р РЋРЎвЂњ Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ flow.

### Р В Р Р‹Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ

Phase 1 Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р’В° Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРЎвЂњ.
Р В РІР‚вЂњР В РЎвЂР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ runtime test Р В Р’В· Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВ `BOT_TOKEN` Р РЋРІР‚вЂњ `OPENAI_API_KEY` Р РЋРІР‚В°Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р’ВµР В Р вЂ¦.

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Phase 2 Р Р†Р вЂљРІР‚Сњ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding Р РЋРЎвЂњ chat-based Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р’В»Р РЋРІР‚вЂњ;
- Р В Р’В±Р В Р’ВµР В Р’В· fancy UI;
- Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰: Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂ“Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В°, Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎВР В Р’В°Р В РІвЂћвЂ“Р В Р’В±Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚В¦ invoice flows.
## 2026-04-01 - Session 005 - Phase 3: manual contact creation

### Goal
Implement minimal manual customer contact creation required for next invoice phases.

### Implemented
- SQLite bootstrap extended with `contact` table (fail-loud compatibility check, no auto-drop/migrations).
- Added `bot/services/contact_service.py` with repository-style operations:
  - `ContactProfile`
  - `get_all_by_supplier(telegram_id)`
  - `get_by_name(telegram_id, name)`
  - `create_contact(...)`
  - `create_or_replace(...)`
- Implemented `bot/handlers/contacts.py` as a simple chat-based flow:
  1. company name
  2. ICO
  3. DIC
  4. optional IC DPH (`-`)
  5. address
  6. email
  7. optional contact person (`-`)
  8. summary
  9. confirm `yes`/`no`
  10. save
- Added exact-name duplicate check per supplier; existing name is warned and confirmed overwrite saves via upsert.
- Added supplier-profile guard: contact flow is blocked until `/supplier` onboarding is completed.

### Explicitly not included in this phase
- contract-based contact extraction
- contact search UI
- invoice save flow
- PDF generation
- email send
- external lookup API / FinStat
- complex dedup/fuzzy matching

### Decision
Phase 3 remains intentionally simple and chat-based; contract extraction and external lookup stay deferred to later phases.

### Follow-up note (language consistency)
- Text confirmation in supplier onboarding aligned to Slovak: `ano / nie` instead of `yes / no`.
- Text confirmation in manual contact flow aligned to Slovak: `ano / nie` instead of `yes / no`.
- User-facing language consistency improved across `/start`, voice preview, supplier onboarding, and manual contact flow.
- Why this matters:
  - bot is oriented to a Slovak interface;
  - mixed-language confirmations create product inconsistency;
  - language consistency is better fixed early while flows are still small.
## 2026-04-03 - Session 006 - Research spike: real PAY by square integration path

### Goal
Р В РЎСџР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ technical research spike Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ PAY by square QR Р РЋРЎвЂњ FakturaBot Р В Р’В±Р В Р’ВµР В Р’В· blind implementation.

### Implemented
- Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ research artifact: `docs/PayBySquare_Research_Spike.md`.
- Р В РІР‚вЂќР РЋРІР‚вЂњР В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С™Р В Р’В° Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р вЂ¦Р РЋР РЏР В Р вЂ¦Р В РЎвЂў Р В РўвЂР В Р’В¶Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В»Р В Р’В°:
  - Р В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’В° Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ PAY by square 1.2.0,
  - by square API docs,
  - Python package `pay-by-square`,
  - Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ non-Python implementation repos (TS/Go/PHP) Р РЋР РЏР В РЎвЂќ Р РЋР вЂљР В Р’ВµР РЋРІР‚С›Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ¦Р РЋР С“Р В РЎвЂ.
- Р В РІР‚вЂќР В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В Р вЂ Р В Р’ВµР РЋР вЂљР В РўвЂР В РЎвЂР В РЎвЂќР РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ repo:
  - Р РЋР вЂљР В Р’ВµР В РЎвЂќР В РЎвЂўР В РЎВР В Р’ВµР В Р вЂ¦Р В РўвЂР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІвЂљВ¬Р В Р’В»Р РЋР РЏР РЋРІР‚В¦: Р В Р вЂ Р В Р’В»Р В Р’В°Р РЋР С“Р В Р вЂ¦Р В Р’В° Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Python-Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ payload encoder (spec-driven),
  - Р В Р’В±Р В Р’ВµР В Р’В· Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В·Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р вЂ¦Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў SaaS Р РЋР РЏР В РЎвЂќ Р В РЎвЂќР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р В Р’В·Р В Р’В°Р В Р’В»Р В Р’ВµР В Р’В¶Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р РЋРІР‚вЂњ,
  - Р В Р’В±Р В Р’ВµР В Р’В· cross-runtime Р В Р’В°Р В РўвЂР В Р’В°Р В РЎвЂ”Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В Р’В° Р РЋР РЏР В РЎвЂќ Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋРІвЂљВ¬Р В Р’В»Р РЋР РЏР РЋРІР‚В¦Р РЋРЎвЂњ.
- Р В РІР‚вЂќР В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ required payload Р РЋРІР‚вЂњ field constraints Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.
- Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў implementation recommendation Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎВР В Р’В°Р В РІвЂћвЂ“Р В Р’В±Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂў PR (Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ runtime Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ Р РЋРЎвЂњ Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋР С“Р В Р’ВµР РЋР С“Р РЋРІР‚вЂњР РЋРІР‚вЂќ).

### Explicitly not included in this session
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ Р РЋРЎвЂњ `bot/services/pdf_generator.py`.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ production integration patch Р В РўвЂР В Р’В»Р РЋР РЏ PAY by square.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ scope Р В Р вЂ¦Р В Р’В° email / external bank API / Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІвЂљВ¬Р РЋРІР‚вЂњ Р В РЎВР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р РЋРІР‚вЂњ.

### Decision
Р В Р Р‹Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂќР РЋРЎвЂњ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р РЋРЎвЂњР РЋРІР‚СњР В РЎВР В РЎвЂў research + decision record, Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р РЋРІР‚РЋР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РЎВ PR Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В РЎВР В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРЎвЂњ production Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў PAY by square payload Р РЋРЎвЂњ PDF flow.


## 2026-04-03 - Session 007 - Implementation: real PAY by square payload in PDF flow

### Goal
Р В РІР‚вЂќР В Р’В°Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ QR placeholder Р РЋРЎвЂњ Phase 4 Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ PAY by square payload generator Р В РўвЂР В Р’В»Р РЋР РЏ invoice payment use case.

### Implemented
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/pay_by_square.py` Р В Р’В· internal spec-driven encoder pipeline:
  1) mapping paymentorder Р В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦,
  2) CRC32,
  3) LZMA raw compression (LZMA1),
  4) header/length prepend,
  5) Base32hex payload output.
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў strict validation: IBAN, amount, currency, VS, due date, beneficiary name (fail-loud Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· `PayBySquareValidationError`).
- `bot/services/pdf_generator.py` Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р’В· placeholder Р РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂќР В Р’В° `PAYBYSQUARE|...` Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р В РЎвЂР В РЎвЂќР В Р’В»Р В РЎвЂР В РЎвЂќ `build_pay_by_square_payload(...)`.
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў unit tests:
  - deterministic payload vector,
  - validation failures,
  - PDF integration smoke (QR payload looks encoded and PDF still written).
- Р В РЎвЂєР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў `README.md`, `docs/TZ_FakturaBot.md`, `CHANGELOG.md` Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР С“Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“Р РЋРЎвЂњ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.

### Explicitly not included
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ external SaaS generation path.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Node/Go/PHP sidecar adaptation.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ email/bank API scope expansion.

### Manual verification status
- Р В Р в‚¬ Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂўР В РЎВР РЋРЎвЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂР В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В°Р РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В°Р РЋР С“Р РЋР Р‰ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В° Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ QR Р В Р’В±Р В Р’В°Р В Р вЂ¦Р В РЎвЂќР РЋРІР‚вЂњР В Р вЂ Р РЋР С“Р РЋР Р‰Р В РЎвЂќР В РЎвЂР В РЎВР В РЎвЂ Р В РЎВР В РЎвЂўР В Р’В±Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВР В РЎвЂ Р В Р’В°Р В РЎвЂ”Р В РЎвЂќР В Р’В°Р В РЎВР В РЎвЂ.
- Р В РЎСџР РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ deploy Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В Р’В° manual verification Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ SK banking clients.
### Follow-up note (Р РЋР С“Р В Р’ВµР В РЎВР В Р’В°Р В Р вЂ¦Р РЋРІР‚С™Р В РЎвЂР В РЎвЂќР В Р’В° Р В РўвЂР В Р’В°Р РЋРІР‚С™ Р РЋРЎвЂњ faktР вЂњРЎвЂќre)
- Р В РЎСџР В Р’В»Р РЋРЎвЂњР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В Р вЂ¦Р РЋРЎвЂњ Р В РЎВР РЋРІР‚вЂњР В Р’В¶ `DР вЂњР Р‹tum vystavenia` Р РЋРІР‚вЂњ `DР вЂњР Р‹tum dodania` Р РЋРЎвЂњ Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р РЋРЎвЂњР РЋР С“Р РЋРЎвЂњР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂў.
- Р В РІР‚СњР В Р’В°Р РЋРІР‚С™Р В Р’В°, Р В Р вЂ Р В РЎвЂќР В Р’В°Р В Р’В·Р В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’ВµР В РЎВ Р РЋРЎвЂњ voice/text input, Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎвЂ”Р РЋР вЂљР В Р’ВµР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ `DР вЂњР Р‹tum dodania`.
- `DР вЂњР Р‹tum vystavenia` Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’В¶Р В РўвЂР В РЎвЂ Р В Р вЂ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р РЋР вЂ№Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В РЎВ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў Р В Р вЂ  Р В РЎВР В РЎвЂўР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™ Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ.

## 2026-04-03 - Session 008 - Verification support: PAY by square manual scan checklist

### Goal
Prepare a local verification-task plan for manual validation of the real PAY by square QR after merge, without runtime code changes.

### Implemented
- Added a short verification artifact: `docs/PayBySquare_Manual_Verification_Checklist.md`.
- Documented the local verification flow:
  - how to generate a PDF invoice locally;
  - where to find the generated PDF;
  - which fields must be checked after scanning in a banking app.
- Added expected outcomes:
  - success,
  - partial success,
  - fail.
- Added a short record checklist for the post-test note so follow-up patch decisions are explicit.

### Explicitly not included
- No runtime code changes.
- No new feature work.
- No email flow changes.
- No Phase 5 work.

### Decision
Before PAY by square production sign-off, a separate manual scan verification in a real banking mobile app must be completed and recorded in `PROJECT_LOG.md`.



## 2026-04-06 - Session 009 - Local env support for FakturaBot

### Goal
Allow FakturaBot to run locally from a dedicated local-only env file without breaking existing `.env`-based startup.

### Implemented
- `bot/config.py` now loads a dedicated local-only env file first when it exists.
- If that local-only env file is absent, startup falls back to `.env`.
- Added a dedicated repo-root local env file with empty/default placeholders only.
- Added that local env file to `.gitignore` while keeping `.env` ignore intact.

### Explicitly not included
- No config field renames.
- No secret values.
- No runtime behavior changes beyond env-file selection.
- `.env.example` left unchanged.

### Decision
Local FakturaBot setup now supports a dedicated non-committed local env file while preserving `.env` compatibility.

## 2026-04-08 - Session 010 - Docs ownership split: Implementation Plan vs LLM Contract

### Goal
Remove overlap risk between planning and contract docs by clarifying document ownership.

### Implemented
- `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` kept as rollout document (phase scope/order/risks/acceptance) and Phase 2 detail reduced to planning-level with explicit reference to LLM contract.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md` marked as detailed Phase 2 AI contract and cross-referenced back to the implementation plan for sequencing.
- `README.md` docs structure updated with concise role distinction for both docs.

### Scope
- Docs-only clarification; no code changes.

## 2026-04-08 - Session 011 - Phase 1 implementation: deterministic contact lookup + service-term canonicalization

### Goal
Implement Phase 1 Python-side canonicalization only (no AI/orchestrator changes).

### Implemented
- Added deterministic contact lookup normalization in `ContactService` with structured states:
  - `exact_match`, `normalized_match`, `multiple_candidates`, `no_match`.
- Added lookup-only company normalization for case/punctuation/separator/legal-form variants.
- Added conservative legal-form support (token-boundary):
  - `s.r.o.` variants (`sro`, `s r o`, `s. r. o.`),
  - `a.s.` variants (`as`, `a s`),
  - conservative `spol` + `sro` / `s r o` tail variants.
- Integrated invoice flow with lookup-state branching:
  - continue on exact/normalized,
  - explicit fail-loud message on multiple candidates,
  - explicit non-assumptive guidance on no match (retry or `/contact`, no auto-create).
- Added deterministic internal service-term normalizer:
  - `opravy -> oprava`, `ремонт -> oprava`, `монтаж -> montáž`.
- Kept alias precedence unchanged: supplier alias mapping remains source of truth for final preview/PDF title.

### Tests
- Added `tests/test_contact_lookup_normalization.py`.
- Added `tests/test_service_term_normalizer.py`.
- Added `tests/test_invoice_contact_lookup_feedback.py`.
- Full test suite passes with `PYTHONPATH=. pytest -q`.

### Scope
- No DB migration.
- No LLM/prompt/orchestrator schema changes.

## 2026-04-08 - Session 012 - Test runner expectation clarified (pytest)

### Goal
Remove ambiguity between legacy unittest habits and current pytest workflow.

### Implemented
- Added explicit test-runner note in `README.md`:
  - canonical runner is `pytest`,
  - command: `PYTHONPATH=. pytest -q`,
  - unittest is not the default expected workflow.
- Added minimal `pytest.ini` with `testpaths = tests` as repo tooling baseline.

### Scope
- Docs/tooling only; no runtime code changes.
---

## 2026-04-06 - Session 013 - Windows-safe SQLite connection closing in tests

### Goal
Eliminate Windows test-suite failures during `TemporaryDirectory` cleanup by ensuring SQLite connections are explicitly closed after each DB access path.

### Implemented
- Added `managed_connection(...)` in `bot/services/db.py` to guarantee `connection.close()` in `finally`.
- Switched SQLite usage in `bot/services/supplier_service.py`, `bot/services/service_alias_service.py`, `bot/services/invoice_service.py`, `bot/services/contact_service.py`, and DB bootstrap in `bot/services/db.py` from direct `sqlite3.connect(...)` context usage to the shared managed helper.
- Preserved existing transaction behavior (`commit()` remains where it already existed).
- Preserved `row_factory = sqlite3.Row` behavior on read paths.
- Verified with `python -m unittest discover -s tests -p "test_*.py" -v`: 18 tests passed on Windows, including the previously affected temp SQLite DB cleanup paths.

### Explicitly not included
- No schema changes.
- No business logic changes.
- No test behavior changes beyond the connection lifecycle fix.

### Decision
SQLite connection lifetime in services/bootstrap is now treated as an explicit resource lifecycle concern, not only a transaction context concern, to remain Windows-safe for temporary DB files.

---

## 2026-04-06 - Session 014 - PDF Slovak glyph completion (ľ, ť)

### Goal
Finish PDF glyph coverage for the remaining Slovak characters (`ľ`, `ť`) without changing the existing layout.

### Implemented
- Confirmed that bundled ReportLab `Vera.ttf` / `VeraBd.ttf` do not contain `ľ` and `ť`.
- Updated `bot/services/pdf_generator.py` to resolve a Unicode-capable font pair from installed Windows fonts first (`arial.ttf` / `arialbd.ttf`, with fallbacks), and only use a fallback font if it actually covers the required Slovak glyphs.
- Normalized visible Slovak PDF literals in `bot/services/pdf_generator.py` to proper Unicode text so headers and labels render correctly with the selected font.
- Added a regression test to verify the selected regular and bold PDF fonts cover `ľ` and `ť`, while keeping existing wrapping/layout tests intact.
- Re-verified the full test suite after the font-selection change.

### Explicitly not included
- No layout redesign.
- No payment block or table layout refactor.
- No schema or business logic changes.

### Decision
PDF rendering now depends on an explicitly validated Unicode font path instead of assuming bundled ReportLab Vera fonts are sufficient for Slovak invoice text.

---

## 2026-04-07 - Session 015 - Manual PAY by square banking-app verification passed for one local FakturaBot flow

### Goal
Record the completed local end-to-end FakturaBot verification session for the currently tested PAY by square PDF flow.

### Verified
- Local supplier -> contact -> invoice flow completed successfully.
- A PDF invoice artifact was generated successfully and reviewed.
- Latest local generated PDF artifact was present in the local invoice output area at the time of verification (timestamp observed locally before this log update: 2026-04-07 18:45).
- The PAY by square QR from the tested PDF was scanned successfully in a real banking mobile app.
- Manual user confirmation states the bank-app recipient account data matched the expected recipient account data.
- Manual user confirmation states the amount was populated correctly.
- Manual user confirmation states the due date (`datum splatnosti`) was populated correctly.

### Scope note
- This log entry records one successful real local end-to-end verification case for the currently tested FakturaBot flow.
- This closes the previously pending manual scan verification milestone for that tested flow.
- This does not claim universal compatibility across all banking apps or full production sign-off.

### Decision
The PAY by square PDF flow now has at least one recorded successful real banking-app verification milestone in addition to local code/test validation.


## 2026-04-10 — Session 016 — Service naming terminology audit + safe refactor

### Goal
Align service naming wording in `/service` and related code to user-friendly Slovak and consistent internal English names.

### Audit findings
- User-facing texts still used technical wording `alias` / `canonical názov` in `/service` flow and README.
- Internal Python naming mixed old terms (`alias`, `canonical_title`, `item_name_final`) with business semantics.
- Persistence schema used `supplier_service_alias(alias, canonical_title)` and related bootstrap checks.
- Tests reflected old naming (`test_alias_resolution_*`, `entry.alias`).

### What changed
- User-facing Slovak wording in `/service` and invoice preview now uses:
  - `krátky názov služby`
  - `plný názov služby`
- Internal naming in service/handlers moved to:
  - `service_short_name`
  - `service_display_name`
- Service layer added explicit method `resolve_service_display_name(...)`; kept compatibility wrapper `resolve_alias(...)`.
- README `/service` command description updated to new wording.
- Tests renamed/updated to new internal naming.

### Compatibility / DB
- DB schema intentionally left unchanged (`alias`, `canonical_title` stay as storage columns in `supplier_service_alias`).
- No migration introduced.

## 2026-04-10 — Session 013 — Phase 2 minimal AI layer (invoice draft only)

### Goal
- Added minimal Phase 2 AI entrypoint for invoice draft flow only.
- LLM now returns Slovak-facing business payload (`vstup`, `zamer`, `biznis_sk`, `stopa`) and Python continues deterministic truth flow.

### What changed
- Updated `prompts/invoice_draft_prompt.txt` to require strict JSON payload for Phase 2 invoice-only schema.
- Reworked `bot/services/llm_invoice_parser.py`:
  - added strict payload validator `validate_invoice_phase2_payload(...)`;
  - added explicit error `LlmInvoicePayloadError` for malformed payload;
  - added `parse_invoice_phase2_payload(...)` that fails loud on shape violations.
- Updated `bot/handlers/invoice.py`:
  - integrated new parser path before deterministic preview flow;
  - mapped Phase 2 `biznis_sk` into existing Python invoice draft fields;
  - preserved original text from `vstup.povodny_text` in preview context;
  - added clear retry message when AI payload is invalid or key fields are missing.
- Added `tests/test_invoice_phase2_ai_layer.py` covering:
  - multilingual/mixed payload validation path,
  - original text preservation,
  - malformed payload handling,
  - preview flow still using Python truth for contact lookup and service display mapping,
  - missing amount handling with clean retry message.

### Notes
- Scope is intentionally invoice-flow only (no contact onboarding redesign, no supplier/document AI expansion).
- No DB migration required.

## 2026-04-10 — Session 017 — Temporary structured debug transparency for voice → STT → Phase 2 invoice flow

### Goal
- Add temporary, env-flagged structured debug trace to identify where customer name is lost/corrupted across STT, validated LLM payload, and deterministic Python contact lookup.

### What changed
- Added `DEBUG_INVOICE_TRANSPARENCY` config flag in `bot/config.py` (default off).
- Added JSON debug event in voice handler after successful STT with:
  - `request_id`
  - `telegram_update_id`
  - `telegram_message_id`
  - `stt_text`
- Added JSON debug event in invoice flow right after validated Phase 2 payload with:
  - `vstup.povodny_text`
  - `biznis_sk.odberatel_kandidat`
  - `biznis_sk.polozka_povodna`
  - `biznis_sk.termin_sluzby_sk`
- Added JSON debug events around deterministic contact lookup:
  - before lookup (`lookup_raw_input`, `lookup_normalized_input`),
  - after lookup (`lookup_state`, `matched_contact_id`, and candidate metadata when multiple matches).
- Added JSON debug event before preview/save handoff with final resolved contact and service title fields.
- `request_id` is propagated across voice STT → Phase 2 parse → lookup → preview path.

### Safety / constraints
- No business logic, fallback behavior, or contact auto-fix/auto-create behavior changed.
- Lookup debug normalization reuses existing `ContactService.normalize_lookup_forms(...)` (no duplicate debug-only normalization logic).

## 2026-04-10 — Session 018 — Phase 2 odberateľ candidate contract hardening

### Goal
- Harden invoice Phase 2 AI contract so `biznis_sk.odberatel_kandidat` is canonical, lookup-ready, and fail-loud if raw/noisy fragments leak from multilingual voice/STT input.

### What changed
- Prompt (`prompts/invoice_draft_prompt.txt`) now explicitly requires lookup-ready canonical candidate in `biznis_sk.odberatel_kandidat`:
  - disallows cyrillic/raw inflected fragments and preposition/filler phrases,
  - keeps original multilingual input only in `vstup.povodny_text`,
  - allows raw extraction notes only in trace (`stopa`),
  - adds multilingual voice-like examples (RU/mixed, s.r.o./sro, imperfect STT).
- Validator (`bot/services/llm_invoice_parser.py`) now fail-loud rejects non lookup-ready candidates:
  - empty/whitespace values,
  - obvious raw phrase fragments (`на техкомпании`, `для компании`, `pre firmu`, `kompanii`),
  - cyrillic-only values,
  - preposition-start and too noisy candidates for deterministic lookup.
- Tests (`tests/test_invoice_phase2_ai_layer.py`) extended for:
  - rejection of Cyrillic/raw candidate variants,
  - acceptance of valid Latin/Slovak lookup-ready candidate,
  - preservation of original multilingual text in `vstup.povodny_text`.

### Notes
- No DB migrations, no contact auto-create, no fuzzy matching.
- Existing Python source-of-truth preview/contact flow remains unchanged for valid payloads.

## 2026-04-11 — Session 014 — Invoice Phase 2 regression fixes (amount semantics + SK text boundary + PDF row alignment)

### Bug shape
- Voice/text phrases with multiplier semantics (e.g. `2 razy po 1500`) could be persisted as `quantity=2`, `total=1500`, causing wrong unit price derivation in PDF.
- `biznis_sk` service short text could still contain raw Cyrillic (`ремонт`) and leak into preview short title.
- PDF item rows with wrapped descriptions looked visually split because numeric columns sat too high relative to multiline description blocks.

### Root cause
- Amount pipeline had only one numeric `suma` path and derived `unit_price` as `total/quantity` without deterministic multiplier normalization.
- Invoice preview trusted `polozka_povodna` too directly, so multilingual/raw text could pass through instead of canonical Slovak term.
- Item-row vertical baseline used a static offset tuned for single-line rows.

### Decision
- Add optional invoice-only payload field `biznis_sk.cena_za_jednotku`, keep Python as numeric source of truth, and enforce deterministic normalization for `N × unit-price` phrases.
- Make preview short title prefer Slovak-normalized term (`termin_sluzby_sk` / deterministic canonical map), with fail-loud validation when `biznis_sk` text fields contain Cyrillic.
- Keep PDF design unchanged and fix only row measurement + numeric baseline helper logic for wrapped rows.

### Tests added/updated
- Amount semantics tests for:
  - `2 razy po 1500`
  - `2 kusy po 1500 eur`
  - `2x 1500`
  - `2 krát po 1500 eur`
  and fail-loud path for ambiguous multiplier hints.
- Service text normalization tests proving `biznis_sk` Cyrillic rejection and Slovak short-title in preview while preserving original multilingual `vstup.povodny_text`.
- PDF layout helper tests for wrapped row height expansion and numeric baseline staying inside row block.

## 2026-04-12 — Session 019 — Deterministic top-level create-invoice pre-router

### Goal
- Add deterministic pre-routing before current invoice Phase 2 parsing so create-invoice starts are recognized reliably from multilingual/noisy action verbs.
- Reserve edit-intent verbs for future branching without implementing edit flow now.

### What changed
- Added top-level deterministic intent detector in `bot/handlers/invoice.py`:
  - normalizes first action tokens (Latin diacritics-safe + Cyrillic-safe),
  - maps supported Slovak/Ukrainian/Russian create verbs to single intent `create_invoice`,
  - recognizes reserved edit placeholders (`upraviť/upravit/управить/исправь/отредактируй`) as `edit_invoice`.
- Inserted pre-router guard at the start of `process_invoice_text(...)`:
  - `edit_invoice` is explicitly blocked from entering current create flow,
  - current create Phase 2 flow is kept unchanged after routing.
- Added focused tests in `tests/test_invoice_intent_prerouter.py` covering required mixed/noisy create examples and ensuring edit-like verbs are not misrouted into create.

### Notes
- No invoice parsing logic moved into intent layer.
- No edit flow implemented; only placeholder recognition for future branching.

## 2026-04-12 — Session 020 — Intent pre-router final minimal verb set (create/edit/send)

### Goal
- Extend deterministic top-level invoice intent pre-router to explicitly separate create/edit/send starts before Phase 2 parsing.

### What changed
- Added deterministic `send_invoice` placeholder intent and `unknown` fallback return in `_detect_invoice_intent(...)`.
- Extended create verb set with required `сделать` and ensured all required create/edit/send verbs are normalized and recognized.
- Updated pre-routing in `process_invoice_text(...)` so both reserved `edit_invoice` and `send_invoice` are blocked from entering current create flow.
- Extended focused tests to cover required create/edit/send examples plus misrouting guards proving edit/send verbs never call Phase 2 parser.

### Notes
- No edit flow or send flow implementation added.
- Existing create flow after routing remains unchanged.

## 2026-04-12 — Session 021 — Unified bounded semantic resolver + contact intake with contract PDF branch

### Goal
- Align runtime with documented LLM orchestrator contract: one bounded semantic resolution layer for top-level action, in-state decisions, and reusable value canonicalization contract.
- Add `add_contact` runtime path for text/voice and document-assisted intake while preserving Python execution authority and fail-loud behavior.

### What changed
- Added reusable semantic resolver service (`bot/services/semantic_action_resolver.py`):
  - bounded API: `context_name` + `allowed_actions/values` + user text + optional context,
  - structured output contract (`canonical_action` or `unknown`),
  - runtime guard: Python validates/executes, LLM only canonicalizes,
  - minimal deterministic fallback for resilience when LLM is unavailable.
- Integrated semantic resolver into invoice runtime:
  - top-level routing now resolves `create_invoice` / `add_contact` / `send_invoice` / `edit_invoice` / `unknown`,
  - preview confirmation now semantic `ano` / `nie`,
  - post-PDF decision now semantic `schvalit` / `upravit` / `zrusit`.
- Added top-level semantic text entry handler (non-command text in idle state) to route through unified runtime path.
- Added contact intake runtime extensions in `bot/handlers/contacts.py`:
  - new intake states for missing-fields clarification and confirmation,
  - Slovak fail-loud prompts for missing critical fields,
  - semantic yes/no confirmation before DB save,
  - reuse of existing `ContactService.create_or_replace(...)` persistence.
- Added document intake service (`bot/services/document_intake.py`):
  - detects and downloads Telegram attachment,
  - handles text-PDF extraction path,
  - distinguishes scan-PDF (no text layer) and returns explicit fallback status,
  - unsupported type handling.
- Added contact field extraction service (`bot/services/llm_contact_parser.py`):
  - bounded structured extraction target for company/contact fields,
  - optional role-ambiguity signal,
  - deterministic fallback parser for critical fields.
- Extended voice routing (`bot/handlers/voice.py`) so voice also routes in contact intake states (`missing`, `confirm`) and does not leak back into invoice flow.

### OCR/vision note
- Scan-PDF branch is implemented as explicit detection + fail-loud user message + pluggable fallback point.
- Full OCR runtime is not wired in this session due current project constraints/tooling baseline.

### Tests
- Added/updated tests for:
  - semantic top-level action resolver and in-state mapping,
  - voice routing into contact clarification state,
  - contact intake with missing email/address clarification,
  - document intake branches: text-PDF, scan-PDF detection, unsupported type,
  - invoice post-PDF cleanup regressions retained in focused suite.

## 2026-04-12 — Session 022 — Stabilization fixes for unified semantic/contact intake patch

### Goal
- Close concrete correctness gaps before merge without redesigning architecture.

### Fixes
- Tightened top-level fallback priority in semantic resolver:
  - reserved `edit/send` stay higher priority than generic invoice nouns,
  - `create_invoice` keeps precedence over `add_contact` when invoice evidence is present,
  - `add_contact` now requires explicit add/store verb + contact/company target evidence.
- Prevented accidental contact import from random idle documents:
  - document intake now starts only when caption/intent semantically resolves to `add_contact`,
  - otherwise bot responds with bounded Slovak guidance and does not guess side effects.
- Preserved explicit company hint path:
  - added deterministic hint extraction from text/caption,
  - passed hint into contact draft extraction.
- Fixed deterministic `ic_dph` extraction bug:
  - extractor now returns actual VAT value token (e.g. `SK1234567890`) instead of label fragment.
- Extended focused regression tests for:
  - fallback top-level create/edit/send/unknown behavior with `api_key=None`,
  - create-vs-add_contact misroute guard when company token is present,
  - idle document rejection (no implicit contact intake),
  - company_hint propagation path,
  - deterministic `ic_dph` extraction correctness.

## 2026-04-12 — Session 023 — Contact wizard step-1 dual input (text or PDF)

### Goal
- Reuse existing `/contact` onboarding UX naturally for semantic `add_contact` while allowing contract PDF as an alternative input at step 1.

### What changed
- `start_add_contact_intake(...)` now enters the existing contact wizard at step 1 instead of launching separate intake UX.
- Step 1 prompt changed to dual-input Slovak wording:
  - `1/7 Zadajte názov firmy odberateľa alebo pošlite zmluvu/PDF.`
- Added dual-step handler (`ContactStates.name_or_document`) so first input can be:
  - text company name -> continue existing 2/7..7/7 manual wizard,
  - PDF/document -> branch into extraction draft flow, then missing-fields/confirm path.
- Kept idle-document safety guard: document is only imported when semantic intent resolves to `add_contact`; otherwise bounded guidance is returned.
- Updated focused tests to cover wizard entry behavior and preserved document extraction regressions.

## 2026-04-12 — Session 024 — Contact onboarding order fix: manual company name first

### Goal
- Correct add-contact onboarding sequence so company name is entered manually first, then user chooses source via next input (PDF or IČO), while preserving semantic/document safety improvements.

### What changed
- Contact flow state order updated to `name_hint -> source_after_name -> (PDF extraction branch OR manual ICO branch)`.
- `start_add_contact_intake(...)` now only enters onboarding and sends:
  - `V poriadku, vytvoríme nový kontakt. Najprv napíšte názov firmy.`
- Company hint is stored from manual text (`contact_company_hint`) and reused for PDF extraction even when PDF has no caption.
- After company name step bot prompts:
  - `Pošlite zmluvu/PDF alebo zadajte IČO.`
- In `source_after_name`:
  - text is treated as IČO (validated), then manual wizard continues from DIČ,
  - document goes through existing intake/extraction flow.
- Voice safety tightened:
  - `name_hint` and `source_after_name` reject voice with bounded Slovak messages,
  - existing invoice and intake_missing/intake_confirm voice routing preserved.
- Role ambiguity path now preserves partial extracted draft in FSM state instead of dropping extracted fields.

### Tests
- Added/updated focused tests for:
  - semantic add-contact entry to `name_hint`,
  - name-hint transition and company-hint storage,
  - source-after-name manual IČO path valid/invalid,
  - source-after-name PDF path with no caption using saved company hint,
  - role-ambiguity partial draft retention,
  - voice restrictions in `name_hint` and `source_after_name`.

## 2026-04-12 — Session 025 — Invoice Phase 2 service-slot repair and clarification retention

### Goal
- Fix Phase 2 invoice payload handling so noisy/non-Slovak `biznis_sk.polozka_povodna` does not drop full draft when service meaning is recoverable, and add slot-level clarification path when only service term is unresolved.

### What changed
- Added deterministic service-slot repair in `validate_invoice_phase2_payload(...)`:
  - canonical service term is now resolved primarily from `biznis_sk.termin_sluzby_sk` (fallback to `polozka_povodna`),
  - when canonical term is recognized, payload is repaired in-place (`termin_sluzby_sk` canonical, safe Slovak `polozka_povodna`) instead of fail-loud on Cyrillic/noisy item text,
  - when service term remains unresolved after repair attempt, validator raises structured `LlmInvoicePayloadError` with `error_code=service_term_unresolved` and partial payload for continuation.
- Improved Phase 2 invalid-payload observability in invoice handler:
  - added focused debug log event `invoice_phase2_payload_invalid` with raw/repaired service fields and structured error code.
- Added slot-level clarification FSM branch:
  - new state `InvoiceStates.waiting_service_clarification`,
  - when parser returns `service_term_unresolved`, bot preserves partial draft (`invoice_partial_draft`) and asks Slovak-only clarification: `Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.`,
  - clarification reply is normalized via existing service normalizer and flow continues directly to preview build without restarting full invoice input.

### Tests
- Updated focused tests to cover:
  - repair path for noisy/Cyrillic-like service item tokens (`ремонт`, `управы`, `оправы`) with recognized service concept,
  - unresolved service slot structured error behavior,
  - partial draft retention + clarification prompt path in `process_invoice_text`,
  - continuation from clarification reply to preview build without full restart.

## 2026-04-14 — Session 026 — Audit-only map for confirmation/decision resolver paths

### Goal
Produce a code-evidenced audit map for bounded short in-action confirmations/decisions (invoice preview, post-PDF decision, contact confirms, related deterministic confirms), including voice/STT routing and contract gaps before any runtime patch.

### Changes
- added audit document `docs/llm/Confirmation_Decision_Audit_2026-04-14.md` with:
  - resolver/prompt inventory,
  - voice call map,
  - contract-gap notes against bounded template,
  - STT-noise production-risk lens,
  - test coverage note and likely repair surface pointers.

### Notes
- Audit-only session: no runtime behavior changes.
- No architecture redesign introduced.

## 2026-04-14 — Session 027 — Conservative bounded resolver for short in-action confirmations/decisions

### Goal
Implement targeted runtime hardening for short confirmation/decision states so noisy/ambiguous STT transcripts resolve to `unknown` (retry), with no architecture redesign.

### Changes
- `bot/services/semantic_action_resolver.py`:
  - added dedicated strict resolver `resolve_bounded_confirmation_reply(...)` for short in-action confirmations/decisions;
  - resolver payload now explicitly includes:
    - `context_name`,
    - `expected_reply_type`,
    - `supported_input_languages=['sk','uk','ru']`,
    - `allowed_canonical_outputs`,
    - `user_input_text`;
  - added conservative deterministic fallback for bounded short replies:
    - accepts only clear one-token canonical equivalents,
    - ambiguous/noisy/off-target inputs return `unknown`;
  - left existing generic resolver and slot quantity/unit-price resolver intact.
- `bot/handlers/invoice.py`:
  - preview confirmation now uses strict bounded resolver (`yes_no_confirmation`);
  - post-PDF decision now uses strict bounded resolver (`postpdf_decision`);
  - existing retry UX/messages preserved.
- `bot/handlers/contacts.py`:
  - semantic intake confirm now uses strict bounded resolver (`yes_no_confirmation`);
  - existing retry UX/message preserved.
- tests:
  - added noisy transcript regressions (`Ah, não.`) for preview confirmation, post-PDF decision, and contact semantic confirm;
  - added guard that post-PDF noisy input does not trigger destructive cleanup;
  - added positive regression tests for strict bounded resolver canonical outputs.

### Notes
- No STT model/transport changes.
- No top-level action routing changes.
- No invoice amount semantics or service-alias flow changes.

## 2026-04-16 — Session 028 — Invoice service/customer bounded candidate migration batch

### Goal
Finish coherent migration of invoice slot resolution to bounded LLM contract for service/customer slots (including clarification and edit-replace service path), while keeping deterministic Python validation/state/side effects.

### Changes
- `bot/handlers/invoice.py`:
  - added bounded customer candidate resolver helper that:
    - builds allowed contact candidate set from supplier contacts,
    - includes deterministic normalized/compressed direct-match shortcut,
    - then uses bounded resolver (`resolve_semantic_action`) with strict allowed candidates and metadata,
    - returns exact contact or unresolved.
  - preview build path now applies bounded customer candidate selection when deterministic contact lookup is not exact/normalized single-match:
    - for `multiple_candidates`: bounded candidate set from lookup candidates,
    - for `no_match`: bounded candidate set from supplier contacts,
    - unresolved continues to slot clarification with bounded customer choices.
  - customer slot clarification now uses bounded candidate resolver (reusing bounded candidate set saved in FSM partial draft) instead of raw phrase heuristics as final chooser.
  - service slot clarification/edit service replacement continue using supplier alias bounded candidate contract (exact allowed alias or unknown).
- `bot/services/semantic_action_resolver.py`:
  - aligned resolver payload envelope with docs/llm template fields for bounded action/value resolution:
    - `context_name`,
    - `current_state` (when present in auxiliary context),
    - `supported_languages`,
    - `allowed_actions`,
    - `user_input_text`,
    - `expected_output`,
    - `auxiliary_context`,
    - `action_hints`.
- `bot/services/service_term_normalizer.py`:
  - marked as legacy migration helper (fallback/support only; not primary runtime resolver).
- tests:
  - added regression for DB alias `stavebné práce` with noisy input `stavbné práce` resolved through bounded allowed alias selection;
  - added coverage that noisy customer candidate resolves via bounded contact candidate set;
  - added coverage that customer clarification reuses bounded candidates from FSM partial payload.

### Notes
- Deterministic Python responsibilities preserved: cleaning/normalization, DB lookup, validation, FSM/state transitions, numbering/PDF and side effects.
- No hidden concept changes: migration keeps existing invoice workflow architecture and fail-loud behavior for unresolved slots.

## 2026-04-17 — Session 029 — Final cleanup of parser legacy customer gate + clarification seam

### Goal
Complete remaining cleanup seams from invoice service/customer bounded migration before merge readiness check.

### Changes
- `bot/services/llm_invoice_parser.py`:
  - removed legacy semantic phrase/prefix/blocklist customer gating in parser validation;
  - parser customer candidate validation now keeps only structural sanity checks (type, non-empty, max length, alphanumeric presence) and no longer rejects phrase-like candidates as semantic decision logic.
- `bot/handlers/invoice.py`:
  - removed dead duplicate `_SLOT_CUSTOMER` branch from `_apply_slot_clarification(...)`;
  - customer clarification runtime path remains single canonical bounded path via `process_invoice_slot_clarification(...)` + `_resolve_customer_candidate_bounded(...)`.
- `tests/test_invoice_phase2_ai_layer.py`:
  - updated parser tests to match new contract:
    - reject only structurally invalid customer candidates,
    - accept noisy phrase-like customer candidates for later bounded runtime resolution.

### Notes
- No architecture redesign.
- Service/customer runtime bounded resolution paths remain unchanged for create/clarify/edit.

## 2026-04-18 — Session 030 — Approval-step diagnostic trace for waiting_pdf_decision

### Goal
Add transparent runtime diagnostics for the post-PDF approval step (`waiting_pdf_decision`) and add narrow tests that expose bounded contract behavior and potential mismatch risks, without changing edit-flow or create/edit/PDF business logic.

### Changes
- `bot/handlers/voice.py`:
  - added diagnostic log `approval_voice_routing` for `waiting_pdf_decision` voice routing path with:
    - `request_id`,
    - `current_state`,
    - `recognized_text`,
    - `telegram_message_id`.
- `bot/handlers/invoice.py` (`process_invoice_postpdf_decision`):
  - added diagnostic request/response logs around bounded resolver call:
    - `approval_resolver_request`,
    - `approval_resolver_response`;
  - added branch decision log before each final branch:
    - `approval_branch_decision` with `branch_taken` in `{schvalit, upravit, zrusit, unknown}`;
  - added explicit unknown-gap log event:
    - `approval_unknown_contract_gap` with full resolver/branch context.
- `bot/services/semantic_action_resolver.py`:
  - extended `resolve_bounded_confirmation_reply(...)` with optional `diagnostics` payload output (backward compatible);
  - diagnostics include:
    - `raw_model_output`,
    - `normalized_output`,
    - `fallback_used`,
    - `fallback_output`;
  - fallback/exception path now populates diagnostics deterministically for traceability.
- tests:
  - `tests/test_invoice_intent_prerouter.py`:
    - added post-PDF bounded synonym matrix assertions (canonical + multilingual/noisy variants).
  - `tests/test_invoice_state_decisions.py`:
    - added runtime branch regression for multilingual destructive synonyms (`отменить`, `delete`);
    - added unknown-contract-gap logging regression (`unknown` does not auto-cancel).
  - `tests/test_voice_state_routing.py`:
    - added voice parity regression for `waiting_pdf_decision` to confirm STT text pass-through and `approval_voice_routing` logging.

### Notes
- This session is diagnostic-only and keeps existing runtime behavior unchanged.
- No hidden concept changes, no edits to invoice edit subflows or PDF generation logic.

## 2026-04-27 — Session 031 — Server ops context routing clarification

### Goal
Prevent agents from mistaking the public `docs/local-only/*.example.md` placeholder for the real FakturaBot server runbook.

### Server operation
- Performed a one-time server-side invoice cleanup using the temporary `reset_invoice_sequence_to_4.py` script.
- Kept invoice numbers `20260001` through `20260004`.
- Removed later 2026 invoice rows above `20260004`.
- Restarted the `fakturabot` container after the operation.
- Removed the temporary script from the server repo after the one-time run.

### Changes
- Local ignored file placement:
  - moved the private server context from `docs/FakturaBot_Server_Agent_Context.md` to `docs/local-only/FakturaBot_Server_Agent_Context.md`;
  - confirmed the new path is ignored by `.gitignore`.
- `AGENTS.md`:
  - added explicit server-side operational context guidance;
  - documented that `docs/local-only/FakturaBot_Server_Agent_Context.md` is the private local server context file to check before server work;
  - documented that `docs/local-only/*.example.md` files are public placeholders only.
- `docs/local-only/README.md`:
  - clarified that example files are not live runbooks.
- `docs/local-only/FakturaBot_Server_Agent_Context.example.md`:
  - added a clear pointer to the private ignored `docs/local-only/FakturaBot_Server_Agent_Context.md` file for real server operations.

### Notes
- No product logic, MVP scope, or architecture changes.
- No secrets were added to tracked docs.

## 2026-04-29 — Session 032 — Delivery date confirmation-window guards

### Goal
Investigate why server invoice `20260005` received `delivery_date = 2023-04-25` after the user dictated `25 квітня`, and harden future-date handling for day+month inputs without an explicit year.

### Findings
- Current flow already has year anchoring for recognized day+month inputs without year.
- The failure path is `_resolve_delivery_date(...)` accepting the LLM-provided full date when Python cannot independently extract day+month from raw/STT text.
- That allowed an old LLM year (`2023`) to pass into draft/PDF.
- The same anchoring rule could also produce a far-future delivery date when a user says a late-year date near the start of the invoice year.

### Changes
- Added Python confirmation-window guards:
  - more than 62 days before `Dátum vystavenia` requires explicit raw/STT year confirmation near the same day;
  - more than 93 days after `Dátum vystavenia` also requires explicit raw/STT year confirmation near the same day;
  - otherwise the flow fails into date clarification.
- Tightened the invoice draft prompt so LLM must not invent a year from model/training context and must return `null` when the year is not reliable.
- Updated TZ date interpretation rules with the 2-month stale-year guard and 3-month future-date guard.
- Added regression tests for the `20260005` stale-year scenario, explicitly confirmed old year, unconfirmed far-future date, and explicitly confirmed future date.

### Notes
- Code change was deployed to the server after merge/push.
- Server invoice `20260005` was corrected after backup:
  - `delivery_date` changed from `2023-04-25` to `2026-04-25`;
  - `/bot/data/storage/invoices/20260005.pdf` was regenerated;
  - backup copies were stored under `/bot/repo/data/storage/backups/`.

## 2026-05-01 — Session 033 — Shared OfficeFlow idle attachment router foundation

### Goal
Implement docs-first and runtime foundation for a shared OfficeFlow idle attachment classifier/router above accounting intake and contact/contract intake.

### Decisions
- Active FSM state remains authoritative:
  - `/doklad` upload state continues to own accounting uploads;
  - contact source/intake states continue to own contact document uploads;
  - the shared router is registered idle-only with `StateFilter(None)`.
- LMM classifies document type only:
  - `receipt`,
  - `incoming_invoice`,
  - `contract`,
  - `contact_source`,
  - `unknown`.
- Python maps `document_type` to a bounded proposal and asks the user before any save/create side effect.
- `bot/services/document_intake.py` remains the old contract/contact PDF helper and was not expanded for accounting documents.
- Standalone `save_contract` remains reserved; the runtime fails explicitly if selected.

### Changes
- Docs:
  - updated `docs/llm/Canonical_Action_Registry.md`;
  - updated `docs/llm/In_Action_Response_Registry.md`;
  - updated `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
  - updated `docs/Document_Intake_Module_Proposal.md`.
- Runtime:
  - added `bot/services/officeflow_attachment_models.py`;
  - added `bot/services/officeflow_attachment_storage.py`;
  - added `bot/services/officeflow_attachment_classifier.py`;
  - added `bot/services/officeflow_attachment_lmm.py`;
  - added `prompts/officeflow_attachment_classification_prompt.txt`;
  - added `bot/handlers/officeflow_attachment_router.py`;
  - registered the shared router before `contacts_router`;
  - added a staged-file entrypoint for existing accounting document processing.
- DecisionResolver:
  - added `attachment_route_choice`;
  - added `attachment_document_type_choice`;
  - kept accounting proposal on existing `yes_no`.
- Tests:
  - added strict parser coverage for all allowed attachment document types and invalid payloads;
  - added idle router coverage for receipt, incoming invoice, contract, unknown, LMM failure cleanup, and idle-only registration;
  - added DecisionResolver coverage for attachment route/document-type choices and STT-noise fallback.

### Verification
- `python -m pytest -q` — 402 passed.

### Notes
- No DB schema changes.
- No invoice flow, `storage/invoices`, or `pdf_path` changes.
- No Google Drive sync, bank matching, or Zevs runtime profile.
- No confirmed accounting document, contact, or contract is saved from idle classification alone.

## 2026-05-01 — Session 034 — Idle attachment accounting proposal DecisionResolver bugfix

### Goal
Fix the idle attachment accounting proposal confirmation path so it does not rely on a flow-specific yes/no fallback.

### Changes
- Kept `bot/handlers/officeflow_attachment_router.py` on `decision_resolver.resolve_yes_no(...)`.
- Removed the `idle_attachment_accounting_proposal` context from context-specific yes/no fallback logic.
- Consolidated yes/no confirmation fallback into one shared `yes_no_confirmation` family helper inside the canonical resolver layer.
- Updated the idle accounting proposal prompt to explicitly say: `Odpovedzte: áno / nie.`
- Added regression coverage for:
  - `ano`,
  - `áno`,
  - `tak`,
  - `ok`,
  - Cyrillic `так`,
  - Cyrillic `да`,
  - unknown clarification,
  - no/cancel cleanup,
  - no local confirmation parser in the idle attachment handler.

### Verification
- `python -m pytest -q tests\test_decision_resolver.py tests\test_officeflow_attachment_router.py` — 64 passed.
- `python -m pytest -q` — 417 passed.

### Notes
- No DB schema changes.
- No invoice flow, `storage/invoices`, or `pdf_path` changes.
- No Document Intake confirmed storage structure changes.

## 2026-05-01 — Session 035 — DecisionResolver design gate documentation

### Goal
Prevent future actions/subflows from adding duplicate local confirmation parsers instead of using the Canonical DecisionResolver.

### Changes
- `docs/Canonical_Decision_Resolver_Contract.md`:
  - clarified that the contract is an implementation gate, not guidance;
  - added forbidden patterns for handler-local and flow-specific confirmation parsing;
  - added required pattern for canonical decision outputs;
  - added a new decision-family gate for future actions/subflows.
- `docs/llm/New_Action_Design_Checklist.md`:
  - added a mandatory DecisionResolver gate before runtime handler implementation;
  - added test expectations for shared resolver usage and no local parser.
- `docs/llm/In_Action_Response_Registry.md`:
  - clarified that new response groups must use `bot/services/decision_resolver.py`;
  - marked deterministic confirmations as legacy/manual documentation, not a template for new work.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`:
  - added an implementation gate requiring confirmation/route/save/delete replies to go through `decision_resolver.py`.

### Notes
- Documentation-only change.
- No runtime, DB, storage, invoice, Google Drive, or bank matching changes.

## 2026-05-01 — Session 036 — OfficeFlow idle attachment voice continuation bugfix

### Goal
Fix OfficeFlow idle attachment accounting proposal voice replies being consumed by the global voice router and falling through to top-level invoice routing.

### Changes
- Refactored OfficeFlow attachment continuation handlers to expose explicit-text helpers for:
  - accounting proposal;
  - contact/contract route choice;
  - unknown document-type clarification.
- Updated `bot/handlers/voice.py` to route STT text for OfficeFlow attachment states back into those helpers before invoice fallback.
- Preserved Canonical DecisionResolver usage; no local yes/no parser was added.
- Added regression coverage for voice `ano`, `ANO`, `tak`, Cyrillic `так`, `nie`, and noisy unknown input in `OfficeFlowAttachmentRouterStates.accounting_proposal`.

### Verification
- `python -m pytest -q tests\test_decision_resolver.py tests\test_officeflow_attachment_router.py` — 70 passed.
- `python -m pytest -q tests\test_accounting_document_intake_flow.py tests\test_contact_intake_semantic_flow.py` — 23 passed.
- `python -m pytest -q` — 423 passed.

### Notes
- No DB schema changes.
- No invoice flow semantics, `storage/invoices`, or `pdf_path` changes.
- No accounting/contact auto-save behavior changes.

## 2026-05-02 — Session 037 — Accounting preview DecisionResolver voice parity

### Goal
Apply the Canonical DecisionResolver contract consistently to accounting document preview approve/edit/cancel decisions for text and voice.

### Changes
- Refactored accounting document preview decision handling to expose an explicit-text helper.
- Routed `AccountingDocumentIntakeStates.waiting_preview_decision` voice/STT input through that same helper before invoice fallback.
- Kept approve/edit/cancel resolution on `decision_resolver.resolve_approve_edit_cancel(...)`.
- Updated accounting preview `edit` behavior to fail safe without saving or cleanup:
  - keep FSM state;
  - keep staged original;
  - reply that accounting document editing is not available yet.
- Added shared resolver coverage for additional multilingual approve/edit/cancel variants.
- Added contract tests that relevant handlers do not branch on legacy `schvalit` / `upravit` / `zrusit` decisions.

### Verification
- `python -m pytest -q tests\test_decision_resolver.py tests\test_accounting_document_intake_flow.py tests\test_voice_state_routing.py tests\test_officeflow_attachment_router.py` — 232 passed.
- `python -m pytest -q` — 550 passed.

### Notes
- No DB schema changes.
- No `storage/invoices` or `pdf_path` changes.
- No full accounting document edit-flow was implemented.
- Invoice draft/post-PDF edit behavior was not changed.

## 2026-05-02 - Session 038 - OfficeFlow architecture framing after Document Intake Phase 1

### Goal
Align the OfficeFlow architecture framing document with the implemented Document Intake Phase 1 runtime without implying a full workspace runtime or invoice storage migration.

### Changes
- Updated `docs/OfficeFlow_Architecture_Framing.md` to document that FakturaBot outgoing invoices remain unchanged and still use `storage/invoices/` plus `pdf_path`.
- Documented current accounting Document Intake Phase 1 support for receipts and incoming invoices.
- Documented confirmed accounting storage under `storage/workspaces/mykhailo-szco/years/<YYYY>/expenses/<MM>/<receipts|incoming_invoices>/<originals|metadata>/`.
- Documented neutral idle attachment staging under `storage/uploads/attachment_intake/<id>/original.<ext>`.
- Added cross-references to `docs/Document_Intake_Module_Proposal.md` and `docs/OfficeFlow_Storage_Model_Proposal.md`.
- Documented future Google Drive sync storage rules in `docs/OfficeFlow_Storage_Model_Proposal.md`:
  - confirmed accounting metadata should use storage-relative paths;
  - future sync should resolve files as `STORAGE_ROOT + relative_path`;
  - host-only paths and temp upload staging are not canonical sync inputs.

### Verification
- Tests not run; documentation-only update.

### Notes
- No code changes.
- No DB schema changes.
- No `storage/invoices` or `pdf_path` changes.
- No Google Drive sync runtime was implemented.
- No Zevs s.r.o. runtime profile or full workspace runtime was introduced.

## 2026-05-02 - Session 039 - Accounting intake purchase subject extraction

### Goal
Replace premature accounting category extraction in Document Intake Phase 1 with raw factual purchase subject extraction.

### Changes
- Replaced accounting candidate/metadata field `category_candidate` with `purchase_subject`.
- Updated the accounting extraction prompt to require raw facts only and forbid accounting/tax/bookkeeping category inference.
- Updated Slovak accounting preview from `Kategória` to `Predmet nákupu`.
- Kept read compatibility for legacy `category_candidate` payload/state values by mapping them into `purchase_subject`, while new metadata writes only `purchase_subject`.
- Updated Document Intake docs to describe purchase subject as the factual item/service bought.
- Added ASFINAG/vignette-style coverage for factual purchase subject extraction.

### Verification
- `python -m pytest -q tests\test_accounting_document_extraction.py tests\test_accounting_document_lmm.py tests\test_accounting_document_intake_flow.py` - 38 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- No confirmed accounting storage layout changes.
- No accounting categorization or Google Drive sync was implemented.

## 2026-05-02 - Session 040 - Temporary intake inactivity timeout

### Goal
Prevent abandoned OfficeFlow/accounting temporary intake sessions from leaving staged upload files and stale FSM state.

### Changes
- Added shared temporary intake session helper with:
  - 5-minute FSM/session timeout metadata;
  - safe cleanup restricted to `storage/uploads/attachment_intake/` and `storage/uploads/accounting_intake/`;
  - filesystem orphan cleanup helper for old upload-staging directories.
- Added expiry metadata to OfficeFlow idle attachment routing states.
- Added expiry metadata to accounting document preview state.
- Guarded OfficeFlow attachment continuation handlers and accounting preview decisions before any business continuation.
- Voice/STT replies reuse the same guarded continuation helpers, so expired voice replies do not fall into invoice fallback.
- Documented the temporary intake lifecycle boundary in `docs/Document_Intake_Module_Proposal.md`.

### Verification
- `python -m pytest -q tests\test_temp_intake_session.py tests\test_officeflow_attachment_router.py tests\test_accounting_document_intake_flow.py` - 51 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- Confirmed accounting storage, invoice PDFs, and contracts are excluded from timeout cleanup.
- No Google Drive sync or global cleanup scheduler was implemented.

## 2026-05-02 - Session 041 - Accounting intake duplicate warning

### Goal
Warn before processing a receipt/incoming invoice that appears to duplicate already confirmed accounting metadata.

### Changes
- Added deterministic duplicate scanning over confirmed accounting metadata only.
- Duplicate matching compares document type, issue date, normalized vendor name, total amount, and currency.
- Added `AccountingDocumentIntakeStates.waiting_duplicate_decision`.
- Duplicate decision uses the shared `resolve_yes_no(...)` DecisionResolver family.
- If the user continues, the normal accounting preview is shown and explicit preview approval is still required before save.
- Added voice routing for duplicate decisions through the same guarded helper.
- Documented that filename is not duplicate truth and that Slice 1 does not use AI/fuzzy/image/PDF duplicate matching.

### Verification
- `python -m pytest -q tests\test_accounting_document_duplicates.py tests\test_accounting_document_intake_flow.py` - 35 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- No changes to `storage/contracts`.
- No automatic overwrite, deletion, fuzzy matching, AI duplicate matching, or Google Drive sync was implemented.

## 2026-05-02 - Session 042 - Recent accounting documents view

### Goal
Add a lightweight read-only `/blocky` command for recent confirmed receipts/incoming accounting documents.

### Changes
- Added `show_recent_accounting_documents` as a command-backed read-only action.
- Added confirmed metadata registry scanning for the last 5 receipts/incoming invoices.
- Added `/blocky` and narrow deterministic aliases for recent bločky/receipts phrases.
- Kept the view isolated from outgoing invoice PDFs, contracts, temp uploads, DB schema, and LMM routing.
- Documented the `/blocky` storage boundary and non-goals.

### Verification
- `python -m pytest -q tests\test_accounting_document_registry.py tests\test_accounting_documents_handler.py tests\test_invoice_intent_prerouter.py` - 99 passed.
- `python -m pytest -q` - 769 passed.

### Notes
- No DB schema changes.
- No invoice flow changes.
- No `storage/invoices` or `pdf_path` changes.
- No `storage/contracts` changes.
- No Google Drive sync, delete/edit/search, or broad document browser was implemented.

