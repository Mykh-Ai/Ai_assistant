# OfficeFlow Platform-Neutral Android Foundation V1 — Stage A Acceptance Proof

Verdict: `safe_to_commit`

This is an infrastructure/application-boundary acceptance proof. A traditional
Conversation Acceptance Proof is not applicable because Stage A adds no
canonical business action, conversation route, callback, confirmation, or FSM.
It does not invent a conversation trace.

The implemented boundary is a controlled administrator enrollment flow, opaque
server-side API sessions, and membership-validated read-only workspace,
invoice, contact, and persisted-PDF projections. The Android application is not
implemented. Telegram remains the current end-user runtime.

Evidence was produced against synthetic local SQLite/filesystem fixtures only.
No production database migration, server restart, deployment, Cloudflare route,
credential change, external-service call, Telegram send, or AI call occurred.

## Validation summary

- New Stage A focused suite: `39 passed` across
  `tests/test_officeflow_api_identity.py`,
  `tests/test_officeflow_api_http.py`, and
  `tests/test_officeflow_api_schema_and_boundaries.py`.
- Shared access/workspace/tenant owner regression: `64 passed` across the
  existing access, tenant, workspace, invoice, contact, and architecture-boundary
  suites.
- Final full repository regression: `2601 passed, 7 subtests passed in 167.08s`.
- Static validation: `python -m compileall -q bot` and `git diff --check` pass.

## Scenario 1 — controlled enrollment happy path

- Precondition: active synthetic `authorized_users` row; no principal mapping.
- Exact HTTP/CLI entry: `officeflow_api_access issue --telegram-id <existing>` then `POST /v1/enrollment/exchange` with the issued secret.
- Authorization result: CLI validates the existing active Telegram identity; exchange resolves only the server-bound principal.
- Python service owner: `ApiEnrollmentService`, `PrincipalIdentityService`, `ApiSessionService`.
- DB/session effect or no-effect: one principal and Telegram mapping are created at approved issuance; enrollment becomes `consumed`; one hashed session is inserted; business rows are unchanged.
- Workspace scope: none until a protected business read.
- Response: raw access/refresh credentials and expiries returned once; no principal, Telegram id, session id, or hash.
- Final state: one active API session; raw enrollment/access/refresh secrets absent from SQLite.
- Test/evidence reference: `test_enrollment_lazily_creates_and_reuses_one_telegram_principal`, `test_enrollment_is_hashed_one_time_and_replay_fails`, `test_http_enrollment_exchange_refresh_rotation_and_replay`.
- Result: pass.

## Scenario 2 — enrollment replay

- Precondition: Scenario 1 enrollment already consumed.
- Exact HTTP/CLI entry: repeat `POST /v1/enrollment/exchange` with the same secret.
- Authorization result: rejected generically; no principal can be selected by the caller.
- Python service owner: `ApiEnrollmentService`.
- DB/session effect or no-effect: no second session; original session remains.
- Workspace scope: none.
- Response: `401` with bounded `invalid_enrollment`.
- Final state: consumed enrollment and one original session.
- Test/evidence reference: `test_enrollment_is_hashed_one_time_and_replay_fails`, `test_http_enrollment_exchange_refresh_rotation_and_replay`, concurrent `test_concurrent_enrollment_consumption_creates_exactly_one_session`.
- Result: pass.

## Scenario 3 — expired enrollment

- Precondition: pending enrollment whose expiry is in the past.
- Exact HTTP/CLI entry: enrollment secret exchange.
- Authorization result: rejected before session creation.
- Python service owner: `ApiEnrollmentService`.
- DB/session effect or no-effect: no session row and no business-row mutation.
- Workspace scope: none.
- Response: bounded invalid enrollment result.
- Final state: unusable enrollment, no new session.
- Test/evidence reference: `test_expired_and_revoked_enrollment_fail_without_session`.
- Result: pass.

## Scenario 4 — session refresh rotation

- Precondition: active session with valid refresh credential.
- Exact HTTP/CLI entry: `POST /v1/session/refresh` with the refresh token.
- Authorization result: hash/expiry/revocation and current `authorized_users` state validate.
- Python service owner: `ApiSessionService`.
- DB/session effect or no-effect: access and refresh hashes rotate atomically on one session lineage; token version advances.
- Workspace scope: none.
- Response: new opaque access/refresh credentials; no hashes or identity assertions.
- Final state: old access/refresh credentials invalid; exactly one rotated session row.
- Test/evidence reference: `test_access_expiry_refresh_rotation_restart_revoke_and_replay`, `test_concurrent_refresh_fails_closed`, `test_http_enrollment_exchange_refresh_rotation_and_replay`.
- Result: pass.

### Administrative session revocation contract

- Precondition: administrator is handling a lost device; the target has multiple sessions and may already be blocked.
- Exact HTTP/CLI entry: `python -m bot.cli.officeflow_api_access sessions --telegram-id <target>` followed by `revoke-session --telegram-id <target> --session-id <opaque-id>`.
- Authorization result: operational administrator CLI binds the opaque session id to the exact server-resolved Telegram external identity; a foreign user's session id is indistinguishable from not found.
- Python service owner: `ApiSessionService`.
- DB/session effect or no-effect: only the selected `api_session.revoked_at` is set; repeated revocation is idempotent; no enrollment or business row changes.
- Workspace scope: none; the operation is principal/session infrastructure and cannot grant business access.
- Response: opaque session id, device label, timestamps, and `active`/`expired`/`revoked` status only; no principal, Telegram id, token, or hash.
- Final state: selected access and refresh credentials fail; other same-user and foreign-user sessions remain unchanged.
- Test/evidence reference: `test_admin_session_list_and_revoke_are_target_scoped_and_secret_free`, `test_admin_cli_issues_once_lists_safely_and_revokes`.
- Result: pass.

## Scenario 5 — blocked/deleted user after token issuance

- Precondition: valid token, then legacy access state becomes `blocked` or `deleted_database`.
- Exact HTTP/CLI entry: protected `GET /v1/workspaces` or refresh.
- Authorization result: current `AccessControlService` authority rejects both states despite valid stored credentials.
- Python service owner: `OfficeFlowApiContextService`, `AccessControlService`, `ApiSessionService`.
- DB/session effect or no-effect: no business read or business write; refresh does not rotate.
- Workspace scope: membership resolution is not reached.
- Response: `401 unauthorized` for protected HTTP reads.
- Final state: legacy blocked/deleted state remains authoritative.
- Test/evidence reference: `test_inactive_user_cannot_issue_or_exchange_enrollment`, `test_current_access_revocation_invalidates_existing_session`, `test_session_and_workspace_list_are_current_authorized_and_sanitized`.
- Result: pass.

## Scenario 6 — list accessible workspaces

- Precondition: active session and active authorization with one owned workspace plus a foreign workspace.
- Exact HTTP/CLI entry: `GET /v1/workspaces` with bearer access token.
- Authorization result: token -> principal -> active Telegram mapping -> current access -> current memberships.
- Python service owner: `OfficeFlowApiContextService` and `WorkspaceContextService`.
- DB/session effect or no-effect: bounded `last_seen_at` update only; no business or active-selection write.
- Workspace scope: only active membership-valid workspaces.
- Response: allowlisted `workspace_id`, display name, and role; no foreign workspace.
- Final state: business/workspace selection rows unchanged.
- Test/evidence reference: `test_session_and_workspace_list_are_current_authorized_and_sanitized`.
- Result: pass.

## Scenario 7 — single-workspace deterministic read default

- Precondition: exactly one accessible active workspace.
- Exact HTTP/CLI entry: `GET /v1/invoices` without `workspace_id`.
- Authorization result: one current membership is selected for that request only.
- Python service owner: `OfficeFlowApiContextService`, `WorkspaceContextService`, `OfficeFlowReadService`, `WorkspaceInvoiceService`.
- DB/session effect or no-effect: permitted session last-seen update; no `active_workspace_selection` or business write.
- Workspace scope: the sole accessible workspace.
- Response: only that workspace's sanitized invoice list.
- Final state: byte/row-equivalent business and active-selection data.
- Test/evidence reference: `test_single_workspace_default_reads_without_selection_mutation`.
- Result: pass.

## Scenario 8 — multi-workspace missing read scope

- Precondition: two accessible workspaces and an existing persistent Telegram selection.
- Exact HTTP/CLI entry: `GET /v1/invoices` without `workspace_id`.
- Authorization result: authenticated, but read scope remains unresolved.
- Python service owner: `OfficeFlowApiContextService`.
- DB/session effect or no-effect: no business/selection mutation; only bounded session metadata may update.
- Workspace scope: none guessed; persistent Telegram selection is ignored.
- Response: `409 workspace_selection_required`.
- Final state: `active_workspace_selection` and business rows unchanged.
- Test/evidence reference: `test_multi_workspace_requires_explicit_scope_and_ignores_active_selection`.
- Result: pass.

## Scenario 9 — valid explicit workspace invoice list

- Precondition: active session and membership in requested workspace.
- Exact HTTP/CLI entry: `GET /v1/invoices?workspace_id=ws_a`.
- Authorization result: supplied workspace is treated only as a requested scope and membership is revalidated.
- Python service owner: `OfficeFlowApiContextService`, `WorkspaceContextService`, `OfficeFlowReadService`, `WorkspaceInvoiceService`.
- DB/session effect or no-effect: read only apart from bounded last-seen metadata.
- Workspace scope: exact validated `workspace_id` SQL predicate.
- Response: allowlisted invoices/items/customer summaries; no Telegram id, `pdf_path`, or server path.
- Final state: business rows unchanged.
- Test/evidence reference: `test_single_workspace_default_reads_without_selection_mutation`, `test_invoice_detail_foreign_and_nonexistent_are_indistinguishable_and_sanitized`.
- Result: pass.

## Scenario 10 — foreign workspace request

- Precondition: active session without membership in `ws_b`.
- Exact HTTP/CLI entry: invoice/contact GET with `workspace_id=ws_b`.
- Authorization result: membership validation fails closed.
- Python service owner: `OfficeFlowApiContextService`, `WorkspaceContextService`.
- DB/session effect or no-effect: no business payload or business mutation.
- Workspace scope: foreign scope is never passed to a domain read.
- Response: bounded `404 workspace_not_found`.
- Final state: both tenants unchanged.
- Test/evidence reference: `test_invoice_detail_foreign_and_nonexistent_are_indistinguishable_and_sanitized`, `test_contacts_are_allowlisted_and_foreign_workspace_fails_closed`.
- Result: pass.

## Scenario 11 — foreign invoice id inside owned workspace request

- Precondition: invoice id exists only in another workspace.
- Exact HTTP/CLI entry: detail/PDF GET using owned `workspace_id` plus foreign invoice id.
- Authorization result: owned workspace validates; invoice lookup remains scoped to it.
- Python service owner: `OfficeFlowReadService`, `WorkspaceInvoiceService`, `WorkspaceInvoicePdfStorageService`.
- DB/session effect or no-effect: no cross-workspace fallback and no business effect.
- Workspace scope: exact owned workspace.
- Response: the same `404 not_found` shape as a nonexistent invoice.
- Final state: foreign and owned invoice rows unchanged.
- Test/evidence reference: `test_invoice_detail_foreign_and_nonexistent_are_indistinguishable_and_sanitized`, `test_owned_pdf_streams_but_missing_unsafe_and_foreign_fail_without_generation`.
- Result: pass.

## Scenario 12 — PDF read

- Precondition: owned invoice with a persisted PDF pointer; missing/unsafe variants also exercised.
- Exact HTTP/CLI entry: `GET /v1/invoices/{id}/pdf?workspace_id=ws_a`.
- Authorization result: session, current access, membership, and scoped invoice ownership validate before file resolution.
- Python service owner: `OfficeFlowReadService`, `WorkspaceInvoiceService`, `WorkspaceInvoicePdfStorageService`.
- DB/session effect or no-effect: stream/read only; no PDF generation, path rewrite, or business mutation.
- Workspace scope: exact owned workspace; resolved file must use the current workspace's unique storage root and exact invoice filename. The numeric legacy-owner root is accepted only when database ownership maps that owner to exactly one workspace; flat/arbitrary or multi-workspace legacy roots fail closed.
- Response: `application/pdf` bytes for valid ownership; bounded `404` for missing, unsafe, poisoned A-to-B, ambiguous legacy, or foreign artifacts; no path disclosure.
- Final state: filesystem and business data unchanged.
- Test/evidence reference: `test_owned_pdf_streams_but_missing_unsafe_and_foreign_fail_without_generation`, `test_missing_pdf_fails_boundedly_without_regeneration`, `test_poisoned_pdf_pointer_to_foreign_workspace_fails_closed`, `test_legacy_pdf_root_requires_unambiguous_owner_workspace`.
- Result: pass.

## Scenario 13 — contacts read

- Precondition: active session and owned workspace containing a contact with internal compatibility fields.
- Exact HTTP/CLI entry: `GET /v1/contacts?workspace_id=ws_a`.
- Authorization result: current access and membership pass.
- Python service owner: `OfficeFlowReadService`, `WorkspaceContactService`.
- DB/session effect or no-effect: read only; no contact create/edit/delete.
- Workspace scope: exact validated workspace.
- Response: allowlisted business fields; no Telegram id, contract path, source note, or server path.
- Final state: contacts unchanged.
- Test/evidence reference: `test_contacts_are_allowlisted_and_foreign_workspace_fails_closed`.
- Result: pass.

## Scenario 14 — attempted business mutation route

- Precondition: valid session and populated business tables.
- Exact HTTP/CLI entry: guessed invoice POST/DELETE/mark-paid, workspace switch, and generic action routes.
- Authorization result: route unavailable or method denied; no action resolution.
- Python service owner: aiohttp router negative space; no business owner invoked.
- DB/session effect or no-effect: zero business and active-selection effects.
- Workspace scope: none trusted or executed.
- Response: bounded `404 not_found` or `405 method_not_allowed`.
- Final state: supplier/contact/invoice/item/selection snapshots identical.
- Test/evidence reference: parameterized `test_guessed_mutation_routes_have_zero_business_effects`, exact-route contract test.
- Result: pass.

## Scenario 15 — active Telegram FSM coexistence

- Precondition: same conceptual actor has a fresh Telegram invoice FSM sentinel.
- Exact HTTP/CLI entry: Stage A invoice GET.
- Authorization result: API validates only its token/current-access/workspace chain; it has no aiogram/FSM dependency.
- Python service owner: API context/read services; existing Telegram FSM owner is not imported or called.
- DB/session effect or no-effect: FSM data/state/revision and active workspace selection remain unchanged.
- Workspace scope: validated API read scope only.
- Response: normal read response.
- Final state: Telegram sentinel remains intact and API process remains independent.
- Test/evidence reference: `test_api_read_has_no_telegram_fsm_dependency_or_mutation`, `test_fresh_api_import_does_not_load_telegram_or_ai_modules`, `test_api_import_boundary_excludes_telegram_fsm_ai_and_external_services`.
- Result: pass.

## Scenario 16 — no AI invocation on API reads

- Precondition: valid sessions used across every Stage A business GET.
- Exact HTTP/CLI entry: workspace, invoice list/detail/PDF, and contacts GET routes.
- Authorization result: deterministic token/access/membership checks only.
- Python service owner: API context and workspace-scoped read services.
- DB/session effect or no-effect: bounded last-seen only; zero STT/LLM/LMM/Semantic Action Resolver/InfoHelp effects.
- Workspace scope: validated membership scope.
- Response: deterministic JSON/file projections.
- Final state: no AI state or external calls.
- Test/evidence reference: all HTTP read tests plus `test_api_import_boundary_excludes_telegram_fsm_ai_and_external_services` and fresh-process import boundary.
- Result: pass.

## Scenario 17 — Telegram regression

- Precondition: Stage A code present; API process not started.
- Exact HTTP/CLI entry: existing Telegram/access/workspace/invoice/contact/document/work-time regression suite.
- Authorization result: unchanged Telegram middleware and `AccessControlService` behavior.
- Python service owner: existing `bot.main`, Telegram routers/FSM middleware, and shared workspace domain services.
- DB/session effect or no-effect: existing journeys retain their established effects; no API session is required.
- Workspace scope: existing Telegram workspace resolution semantics remain unchanged.
- Response: existing Telegram contracts remain green.
- Final state: polling runtime has no import/lifecycle dependency on `officeflow_api_app`.
- Test/evidence reference: full `2601 passed, 7 subtests passed`; shared `64 passed`; `test_api_import_boundary_excludes_telegram_fsm_ai_and_external_services` verifies `bot.main` does not import the API app.
- Result: pass.

## Scenario 18 — Product Truth capability question

- Precondition: Stage A implemented; no separately approved Product Truth capability synchronization exists.
- Exact HTTP/CLI entry: existing Telegram InfoHelp question “Do you support Android?”; this is not a Stage A HTTP route.
- Authorization result: unchanged existing Telegram/InfoHelp authority; no API enrollment is triggered.
- Python service owner: existing Product Truth/InfoHelp layer, unchanged by this patch.
- DB/session effect or no-effect: no Product Truth, enrollment, session, or business mutation.
- Workspace scope: none added.
- Response: no supported-Android claim is registered. Approved documentation truth is: secure first-party API/auth foundation exists for an administrator-controlled read-only pilot; Android app and Android workflows remain planned/not implemented; Telegram remains the current end-user runtime.
- Final state: no `first_party_android_client` or other Android capability id exists in the registry.
- Test/evidence reference: `test_stage_a_does_not_invent_android_product_truth_support`; repository diff contains no InfoHelp/Product Truth runtime edit.
- Result: pass as required negative-space evidence; runtime Product Truth synchronization remains explicitly deferred.

## Existing-data and rollout gate

`test_additive_bootstrap_preserves_existing_business_database` models an
existing valid OfficeFlow database, removes only the four Stage A tables,
reapplies bootstrap, and proves existing authorization, workspace ownership,
membership, active selection, supplier, contact, invoice, item relationships,
and persisted PDF pointer are unchanged. Only the four approved tables and
three approved lookup indexes are added. An incompatible pre-existing Stage A
table fails closed without rebuild.

This proof authorizes review of code only. It is not a production migration,
merge, deploy, public exposure, or Android-support approval.
