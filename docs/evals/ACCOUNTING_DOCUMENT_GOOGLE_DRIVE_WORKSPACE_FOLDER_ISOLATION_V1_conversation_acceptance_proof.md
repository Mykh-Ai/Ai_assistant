# Accounting Document Google Drive Workspace Folder Isolation V1

Verdict: `safe_to_commit`

This verdict means the applicable automated journeys pass and no known
implementation defect remains. It is not permission to commit or deploy.
Real configured two-profile Google Drive smoke was not performed and remains a
separate deployment gate.

Test fixtures use synthetic workspace identities and company names. No
production Telegram id, workspace id, folder name, document content, or Google
credential is recorded here.

## 1. Existing SŽČO confirmed receipt

- Precondition: synthetic authorized existing workspace with distinct canonical id, storage key, and Unicode/punctuation Drive folder.
- Input/event: enqueue one confirmed receipt dated 2026-07.
- Bound workspace: synthetic existing workspace.
- Python owner: `AccountingDocumentArchiveService` and `accounting_document_archive_path`.
- Expected target: `<existing-folder>/2026/blocky/2026-07`.
- Actual target: exact expected persisted target; canonical workspace id retained.
- Side effect: one pending archive job and state; no Drive call.
- Retention: original and metadata present while pending.
- Idempotency/retry: not applicable to first enqueue.
- Final state: `pending`.
- User-visible response: unchanged local-save success contract.
- Boundary: mocked local DB/filesystem.
- Result: pass, `test_existing_profile_receipt_persists_exact_workspace_target`.

## 2. Second-profile confirmed receipt

- Precondition: synthetic second workspace with a different storage key and persisted Drive folder.
- Input/event: enqueue one confirmed receipt.
- Bound workspace: exact second workspace.
- Python owner: shared archive service/path builder; no second provider or worker.
- Expected target: `<second-folder>/2026/blocky/2026-07`.
- Actual target: exact expected target with no Telegram-derived or first-profile segment.
- Side effect: one second-workspace job; no Drive call.
- Retention: original and metadata present.
- Idempotency/retry: isolated by workspace/document/provider key.
- Final state: `pending`.
- User-visible response: unchanged.
- Boundary: mocked local DB/filesystem.
- Result: pass, `test_second_profile_receipt_has_no_telegram_or_first_profile_segment`.

## 3. Same-date receipts in both profiles

- Precondition: two synthetic workspaces and same 2026-07 document period.
- Input/event: enqueue one receipt per workspace.
- Bound workspace: each job uses its own exact workspace.
- Python owner: shared path builder.
- Expected target: equal suffixes but different first workspace folders.
- Actual target: two different persisted targets.
- Side effect: two isolated jobs; no Drive call.
- Retention: both local originals and metadata remain.
- Idempotency/retry: each job has an independent idempotency key.
- Final state: both `pending`.
- User-visible response: unchanged.
- Boundary: mocked local DB/filesystem.
- Result: pass, `test_same_date_receipts_in_two_workspaces_have_different_targets`.

## 4. Second-profile incoming invoice

- Precondition: second workspace and confirmed incoming-invoice local tree.
- Input/event: enqueue one incoming invoice dated 2026-07.
- Bound workspace: exact second workspace.
- Python owner: shared path builder and archive service.
- Expected target: `<second-folder>/2026/prijate_faktury/2026-07`.
- Actual target: exact expected persisted target.
- Side effect: one pending incoming-invoice job; no Drive call.
- Retention: original and metadata present while pending.
- Idempotency/retry: standard archive-job contract.
- Final state: `pending`.
- User-visible response: unchanged.
- Boundary: mocked local DB/filesystem.
- Result: pass, `test_second_profile_incoming_invoice_uses_expected_folder`.

## 5. Profile switch after enqueue

- Precondition: first-workspace job already persisted.
- Input/event: mutate synthetic `active_workspace_selection` to the second workspace.
- Bound workspace: first workspace remains on the job.
- Python owner: worker/job record; no active-selection lookup.
- Expected target: original first-workspace target.
- Actual target: unchanged exact persisted target.
- Side effect: selection changes only; job is not rewritten.
- Retention: unchanged.
- Idempotency/retry: immutable target retained.
- Final state: job remains `pending`.
- User-visible response: no archive response change.
- Boundary: mocked local DB.
- Result: pass, `test_active_workspace_switch_after_enqueue_does_not_retarget_job`.

## 6. Retry after transient Drive failure

- Precondition: a pending job with explicit workspace target.
- Input/event: mark uploading, then transient `retry_wait`.
- Bound workspace: original workspace.
- Python owner: `ArchiveWorker` / archive state service.
- Expected target: first persisted target reused.
- Actual target: unchanged through retry and later duplicate call.
- Side effect: bounded status/attempt update; no second job.
- Retention: original and metadata preserved.
- Idempotency/retry: one job, immutable target.
- Final state: `retry_wait`.
- User-visible response: no false upload-success claim.
- Boundary: mocked provider/local DB.
- Result: pass, retry/duplicate focused test plus transient worker test.

## 7. Duplicate enqueue

- Precondition: existing job for workspace/document/provider.
- Input/event: enqueue same document after a persisted profile display/folder change.
- Bound workspace: exact original workspace.
- Python owner: `ArchiveJobService` idempotency lookup.
- Expected target: original job target, not newly derived replacement.
- Actual target: original target returned; row count remains one.
- Side effect: no duplicate upload job and no overwrite.
- Retention: unchanged.
- Idempotency/retry: proven idempotent.
- Final state: existing job/state returned.
- User-visible response: unchanged.
- Boundary: mocked local DB.
- Result: pass, `test_retry_and_duplicate_enqueue_reuse_first_persisted_target`.

## 8. Missing or unsafe workspace Drive folder

- Precondition: confirmed original and metadata already saved locally.
- Input/event: blank, traversal, separator, or absolute-like folder value.
- Bound workspace: supplied canonical workspace/storage context.
- Python owner: shared path validator before archive schema/job write.
- Expected target: none.
- Actual target: none; exception becomes bounded handler log category.
- Side effect: no DB/job/root-level upload; local files remain.
- Retention: original and metadata preserved.
- Idempotency/retry: repair can enqueue later; no invalid job exists.
- Final state: authoritative local save remains successful.
- User-visible response: existing local-save success UX.
- Boundary: mocked local filesystem; no Drive.
- Result: pass, unsafe-folder and handler-preservation tests.

## 9. Drive disabled or not configured

- Precondition: archive runtime disabled or provider configuration incomplete.
- Input/event: scheduler/worker tick.
- Bound workspace: persisted job workspace.
- Python owner: existing scheduler/worker configuration gate.
- Expected target: persisted target is not contacted/uploaded.
- Actual target: no provider upload; bounded noop or retry/not-configured state.
- Side effect: no remote call.
- Retention: original and metadata preserved.
- Idempotency/retry: existing bounded lifecycle retained.
- Final state: pending/noop or `retry_wait`, according to existing mode.
- User-visible response: no Drive-success claim.
- Boundary: disabled/mocked provider.
- Result: pass, existing Drive disabled/not-configured provider tests.

## 10. Successful upload with original cleanup enabled

- Precondition: confirmed receipt, fake successful provider, receipt cleanup enabled.
- Input/event: one worker tick.
- Bound workspace: persisted job workspace.
- Python owner: `ArchiveWorker` retention after `mark_uploaded`.
- Expected target: persisted job target.
- Actual target: provider receives job target; state becomes uploaded.
- Side effect: one upload result and Drive ids stored.
- Retention: receipt original deleted only after uploaded; metadata remains.
- Idempotency/retry: terminal job is not re-uploaded.
- Final state: `uploaded`.
- User-visible response: separate from enqueue success.
- Boundary: fake Drive provider.
- Result: pass, `test_worker_deletes_original_only_after_uploaded_state_and_keeps_metadata`.

## 11. Failed upload with original preserved

- Precondition: pending job and transient/permanent failing fake provider.
- Input/event: one worker tick.
- Bound workspace: persisted job workspace.
- Python owner: existing worker error classification.
- Expected target: persisted target, no retarget.
- Actual target: unchanged.
- Side effect: bounded retry/failed DB status only.
- Retention: original and metadata both preserved.
- Idempotency/retry: transient attempts advance on same job.
- Final state: `retry_wait` or `failed`.
- User-visible response: no false upload-success claim.
- Boundary: fake provider.
- Result: pass, strengthened transient/permanent worker tests.

## 12. Metadata preserved after successful upload

- Precondition: successful receipt or incoming-invoice upload and cleanup enabled.
- Input/event: worker completion.
- Bound workspace: persisted job workspace.
- Python owner: `ArchiveLocalRetentionPolicy` and worker.
- Expected target: persisted job target.
- Actual target: unchanged.
- Side effect: upload state/ids persisted.
- Retention: metadata exists after original cleanup.
- Idempotency/retry: terminal uploaded state.
- Final state: `uploaded`.
- User-visible response: no metadata deletion claim.
- Boundary: fake provider/local filesystem.
- Result: pass, receipt and incoming-invoice retention tests.

## 13. Existing invoice-PDF archive journey

- Precondition: existing outgoing invoice PDF/control-event job.
- Input/event: existing mark-paid/archive worker journey.
- Bound workspace: existing invoice ownership contract.
- Python owner: `InvoiceDriveArchiveService` and worker.
- Expected target: existing `YYYY/faktury/YYYY-MM` target.
- Actual target: unchanged; no accounting workspace prefix injected.
- Side effect: existing upload/state behavior only.
- Retention: local invoice PDF always kept.
- Idempotency/retry: existing tests remain green.
- Final state: existing contract.
- User-visible response: existing invoice wording.
- Boundary: fake provider.
- Result: pass, invoice-PDF archive and retention tests.

## 14. Existing receipt intake UX

- Precondition: existing accounting-document FSM and confirmed preview.
- Input/event: text/button/voice-owned confirmation paths in current suite.
- Bound workspace: starting FSM workspace, revalidated before save.
- Python owner: existing intake handler and DecisionResolver.
- Expected target: new target only after confirmed local save.
- Actual target: one archive job; no new command/state/callback/message.
- Side effect: existing local original/metadata save and best-effort enqueue.
- Retention: staging cleanup unchanged; confirmed files preserved.
- Idempotency/retry: existing repeated-enqueue test remains green.
- Final state: FSM clears as before.
- User-visible response: existing `Doklad bol uložený` contract.
- Boundary: mocked LMM/classifier; no external Drive.
- Result: pass, full accounting intake suite.

## 15. Cross-workspace path or ownership attempt

- Precondition: workspace id/storage key do not match the local confirmed path, or target traverses.
- Input/event: enqueue with mismatched/unsafe path context.
- Bound workspace: requested workspace cannot claim foreign storage.
- Python owner: shared local/target path validator plus job service.
- Expected target: none.
- Actual target: validation error before insert.
- Side effect: no job and no Drive call.
- Retention: existing local files untouched.
- Idempotency/retry: not applicable until ownership is repaired.
- Final state: fail closed.
- User-visible response: local save remains authoritative where handler owns the call.
- Boundary: mocked local DB/filesystem.
- Result: pass, path normalization, folder, and archive-service tests.

## 16. Product Truth question with no side effect

- Precondition: user asks whether Drive storage is available.
- Input/event: InfoHelp capability question.
- Bound workspace: none; informational route only.
- Python owner: Product Truth/InfoHelp renderer.
- Expected target: none.
- Actual target: none.
- Side effect: no DB/job/provider call.
- Retention: not applicable.
- Idempotency/retry: not applicable.
- Final state: partial/setup-gated answer.
- User-visible response: one owner OAuth, separate owning-profile folders, async upload, local metadata, no historical migration.
- Boundary: deterministic no-network guidance.
- Result: pass, Product Truth and InfoHelp tests.

## 17. Active legacy job deployment blocker

- Precondition: active receipt/incoming-invoice job with missing or unsafe target.
- Input/event: `python -m bot.accounting_document_drive_audit --db-path <db>`.
- Bound workspace: audit joins persisted workspace context without reporting identities.
- Python owner: `accounting_document_drive_audit` in SQLite `mode=ro` and `query_only`.
- Expected target: missing/unsafe row counted as blocker.
- Actual target: blocker category/count reported; deployment readiness false.
- Side effect: none; before/after database SHA-256 equal and `writes_performed=false`.
- Retention: no file mutation.
- Idempotency/retry: repeatable read-only report.
- Final state: deployment blocked; CLI exit code 2.
- User-visible response: none; operator-only aggregate JSON.
- Boundary: local fixture DB, no production query.
- Result: pass, missing-target and unsafe-target audit tests.

## Evidence Summary

- Focused intake/archive contract: `114 passed`.
- Expanded worker/provider/workspace/Product Truth/InfoHelp regression: `292 passed`.
- Final retention/path/provider focused run: `54 passed`.
- Final full suite: `2162 passed, 7 subtests passed in 215.50s`.
- Canonical Action Registry diff: empty.
- Real owner OAuth, production DB, production worker, and remote Drive: not used.

## Manual Deployment Gate

Before any later deployment: back up SQLite/storage, record exact SHA, run the
new read-only target audit, require zero blockers, then perform the approved
two-profile real Drive smoke and unchanged invoice-PDF journey. A separate
approval is required for deployment, production audit, repair/backfill, worker
tick, Docker action, credential use, or remote-file operation.
