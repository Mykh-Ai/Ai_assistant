# Accounting Document Google Drive Workspace Folder Isolation V1

Verdict: `ready_for_handoff`

Implementation verification: `design_matches_runtime`

## 1. Task Identity And Product Need

Task id: `ACCOUNTING_DOCUMENT_GOOGLE_DRIVE_WORKSPACE_FOLDER_ISOLATION_V1`.

Business need: confirmed receipts and incoming invoices from each business
workspace must use the existing shared owner Google Drive connection and
archive worker while landing below that workspace's persisted Drive folder.

User-visible outcome: accounting-document intake remains unchanged. A local
confirmed save succeeds first; asynchronous Drive archival, when configured,
uses the owning business profile's separate folder tree.

Current and target Product Truth status: `partial`, `requires_setup`,
`requires_admin`, and `requires_external_credentials`. This task does not
promote Google Drive archival to fully supported SaaS sync.

Risk: high tenant-isolation and external-storage risk; no schema migration or
remote-file migration is approved.

Date: 2026-07-16. Architecture owner: product-owner approved handoff.

## 2. Architecture Classification

Primary class: `deterministic internal strategy / existing archive-path
correction`.

It is not a top-level action, structured LLM slot, FSM/subflow, callback,
voice route, new OAuth integration, new intake flow, or storage migration.
The existing confirmed-save archive enqueue is the correct owner.

## 3. Canonical Action Contract

Not applicable. No canonical token, registry row, allowed-action set, public
command, or user-facing route changes.

## 4. Semantic Boundary Matrix

| Input/event | Expected owner/result | Must not become |
|---|---|---|
| Confirmed receipt | Existing intake save then archive enqueue | invoice-PDF archive or synchronous upload claim |
| Confirmed incoming invoice | Existing intake save then archive enqueue | outgoing invoice flow |
| Capability/how-to question | Product Truth / InfoHelp only | archive enqueue or Drive call |
| Active profile switch after enqueue | No job mutation | target-folder retargeting |
| Missing/unsafe workspace Drive folder | Local save succeeds; no archive job | generic-root or cross-workspace upload |

## 5. Structured Slot Contract

No LLM slot is added. Python obtains all target values from persisted and
validated state:

| Value | Source | Validation |
|---|---|---|
| `workspace_id` | bound and revalidated `WorkspaceContext` | active membership and exact workspace |
| `storage_key` | persisted `workspace.storage_key` | local confirmed paths remain below that workspace tree |
| `drive_folder_name` | persisted `workspace.drive_folder_name` | one safe relative folder segment |
| year/month | validated accounting-document issue date / canonical saved path | four-digit year and two-digit month |
| document type folder | Python mapping | `receipt -> blocky`; `incoming_invoice -> prijate_faktury` |

## 6. Public Route And Convergence Map

The existing text, voice, button, command, and attachment entry modes continue
through `bot/handlers/accounting_document_intake.py`. This task changes only
the internal target passed from confirmed save to the existing archive service.

## 7. FSM Graph And State Ownership

No state or transition changes. The existing accounting-document FSM binds the
starting workspace in state data, revalidates membership before confirmed
save, persists the local document, enqueues archival best-effort, cleans only
temporary staging, clears state, and returns the existing success response.

## 8. Decision And Callback Contract

No decision or callback change. Existing preview/category/duplicate decisions
continue through the shared DecisionResolver and existing handlers.

## 9. Side-Effect And Ownership Map

| Side effect | Python owner | Gate | Failure behavior |
|---|---|---|---|
| Confirmed original and metadata save | `save_confirmed_accounting_document` | authorization, bound workspace, validation, confirmation | existing save failure UX |
| Archive job/state insert | `AccountingDocumentArchiveService` / `ArchiveJobService` | safe workspace local paths and safe explicit Drive target | local save remains; no generic job |
| Drive upload | existing `ArchiveWorker` and shared owner OAuth provider | persisted job, provider configuration, worker lifecycle | bounded retry/failure; original preserved |
| Original cleanup | existing `ArchiveWorker` retention policy | state marked `uploaded` first | metadata remains; cleanup failure is bounded |

Duplicate enqueue remains idempotent per workspace/document/provider and never
silently overwrites an existing job's target.

## 10. Authorization, Tenant, And Precision Boundaries

Authorization and active-FSM ownership remain before storage or AI work. The
tenant key is `workspace_id`; local ownership uses `storage_key`; the first
Drive segment uses `drive_folder_name`. Telegram ids, message text, LLM output,
vendor names, local Telegram-derived folder names, and later active selection
must not choose the Drive target.

## 11. User-Facing Response And Exit Contract

No response or keyboard changes. `Doklad bol ulozeny` means the authoritative
local save succeeded; it does not claim Drive upload success. Archive target or
enqueue failure remains internal and bounded.

## 12. Product Truth And InfoHelp Contract

Capability id remains `google_drive_invoice_storage` with partial owner OAuth
archive semantics. Guidance may state that one configured owner connection is
shared while receipts, incoming invoices, and workspace-scoped outgoing
invoice PDFs use separate workspace folder trees. It must also state that upload is asynchronous, local save may succeed
while Drive is pending/unavailable, configured cleanup may remove only the
uploaded original, metadata remains local, and historical remote files are not
automatically migrated.

Forbidden claims include synchronous upload, per-profile OAuth, shared profile
folder, historical remote migration, deletion on failed upload, metadata
deletion, Gmail, bank-statement, or full SaaS sync support.

## 13. Negative-Space And Regression Contract

Do not change classification, extraction, categories, duplicate detection,
preview/save/cancel UX, local storage layout, local invoice-PDF paths/retention,
mark-paid, OAuth/token storage, connection commands, worker count, scheduler,
contacts, invoices, work-time, profile switching, Gmail, or bank behavior.

## 14. Acceptance Scenario Contract

The dedicated Conversation Acceptance Proof must cover:

1. existing-profile receipt;
2. second-profile receipt;
3. same-date receipts in both profiles;
4. second-profile incoming invoice;
5. profile switch after enqueue;
6. retry and duplicate enqueue;
7. missing/unsafe Drive folder;
8. Drive disabled and upload failure;
9. successful retention with metadata preservation;
10. unchanged invoice-PDF archive and intake UX;
11. cross-workspace path attempt;
12. Product Truth question with no side effect;
13. non-terminal legacy jobs with missing/unsafe targets reported as a deploy blocker.

## 15. Out Of Scope And Known Architecture Gaps

No production audit/apply, archive-job backfill, server mutation, Drive file
move, remote folder reorganization, real Drive smoke, second OAuth connection,
Gmail, bank statements, generic Google foundation redesign, or invoice-PDF
archive change is included. Real configured two-profile Drive smoke remains a
later explicit deployment gate.

## 16. Evidence Index And Verdict

Current evidence:

- `bot/handlers/accounting_document_intake.py::_require_accounting_scope`
- `bot/handlers/accounting_document_intake.py::_enqueue_archive_after_confirmed_save`
- `bot/services/accounting_document_storage.py`
- `bot/services/accounting_document_archive_service.py`
- `bot/services/archive_job_service.py`
- `bot/services/archive_worker.py`
- `bot/services/google_drive_archive_scheduler.py`
- `bot/services/google_drive_owner_oauth_client.py`
- `bot/services/google_drive_service_account_client.py::_drive_folder_parts`
- `bot/services/workspace_context.py::WorkspaceContext`
- `tests/test_accounting_document_intake_flow.py`
- `tests/test_archive_job_service.py`
- `tests/test_archive_worker.py`
- `tests/test_google_drive_service_account_archive.py`

Read-only verification found the frozen route and owners intact. The known gap
is exactly the approved correction: confirmed accounting-document enqueue does
not persist a workspace-specific target and the provider fallback derives only
the generic year/type/month suffix.

Final verdict: `ready_for_handoff`.
