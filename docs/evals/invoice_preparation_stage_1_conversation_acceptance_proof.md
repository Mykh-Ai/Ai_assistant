# Invoice preparation Stage 1 conversation acceptance

Design verification used GitHub main `84ff360`, specification version 6,
[Design Proof version 2](../architecture/FAKTURABOT_INVOICE_PREPARATION_ARCHITECTURE_DESIGN_PROOF.md)
and the owner's 17 November decision. A stated
replacement rate applies to the current invoice, and a separate offer follows
successful save. Text and STT replies use the existing yes/no decision family.
The offer binds the actor, workspace, contact, previous rate (including NULL)
and expiry. A decline or an expired offer preserves the future rate.

The test environment uses disposable SQLite, real PDF generation and PDF
readback, and synthetic Telegram, STT and OpenAI transports.

| Scenario | Local evidence |
|---|---|
| Authorized command, voice and button | Production dispatcher registrations and middleware handle `/invoice`, a synthetic voice transcript and the bound approval. Unauthorized voice triggers zero STT. The current approval removes its keyboard and sends the calculated PDF. |
| Text with stated inputs | `Вистав Tech Company за два попередні тижні, 120 годин, відніми 14 ночей по 29 €` follows `create_invoice`. At 2026-11-16 the draft shows KW45 and KW46, delivery on 2026-11-13, 3840 gross, 406 lodging and 3434 payable. Weekly split remains null. The previous invoice provides only the service label. Approval creates one item and matching SQLite, JSON and PDF amounts. |
| Missing service and typed continuation | First-time invoicing asks for the exact service in the same partial draft. Its reply reaches the calculation and preview. Approval is still required to write the invoice. |
| One-time rate and separate offer | An explicit 40 replaces a default 32 for the current invoice. Before consent, the contact still contains 32. The yes and no branches independently save 40 and preserve 32. The approved invoice retains its amount in both cases. |
| Editing and stale controls | Editing from 120 to 100 hours issues a new token and shows 2794. Old nonce, wrong actor, wrong message and legacy generic approval cannot write. Concurrent approvals and repeat clicks produce one invoice. Owned timeout and global cancel remove the keyboard without an invoice write. |
| Saved manual edit | An injected renderer failure leaves the previous PDF, invoice amount and bundle intact. Retrying with 3500 updates all effective totals and marks the 3434 calculation historical. Closing the resulting review retains the saved invoice. |
| Initial PDF failure | A failed renderer after approval removes the new invoice, items and partial PDF. |
| Calendar and arithmetic | Both year boundaries, an explicitly stated historical year, a year shown only as an amount, invalid KW53/2027, conflicting gross/net, absent lodging and two lodging rates are covered. |
| Tenant isolation | A shared actor in two workspaces cannot read the other profile's latest service or rate, or apply a rate change across profiles. |
| SQLite compatibility | Legacy and workspace schemas boot before and after the migration. The read-only dry run preserves source bytes, a mismatched fingerprint stops apply, and the verified backup matches the old database. The compatibility runtime produces a plain invoice and preserves new data after migration. |
| Existing behavior | The full suite covers manual invoices, legacy and unrelated decision callbacks, archive workflows, voice routing and InfoHelp. |

The original candidate recorded 3066 passed tests and 7 subtests.

### PR #119 review regressions

| Scenario | Review evidence |
|---|---|
| Calendar and ISO year | Tests freeze the Bratislava date at midnight and exercise the 2026/2027 boundary in both directions. They cover completed KW52/KW53, explicit KW1, user-specified historical years, yearless dates on and outside the inclusive limits, and a model-proposed array contradicting the user text. A labeled delivery date survives a model omission or unsupported year. |
| Clarification and continuation | Missing singleton and `items[]` labels reuse scoped invoice history or ask for the exact service. Two distinct labels in the latest invoice still require an answer. One corrected period endpoint preserves the original year evidence and the unaffected endpoint, hours and deductions. |
| First and replacement rate | Yes and no are tested both with NULL and with a stored 32 EUR/h. The PDF and saved calculation are identical after the rate decision. A stale NULL offer and attempts from another workspace cannot overwrite a contact. |
| Process interruption | Child processes stop immediately after replacing a real PDF, one before SQLite COMMIT and one after. Recovery verifies bytes and calculation revision. Additional cases prove restoration of a missing original and fail-closed handling when the replacement hash has changed. Recovery is repeatable. |
| Legacy path and confirmation | Direct command/voice fixture coverage, exact-preview approval/edit/cancel, stale and duplicate callbacks, synthetic unauthorized users, existing PDF and SQLite total checks, and the compatibility-mode plain invoice are exercised locally. |

The new regressions produced 15 failures on the unmodified `42e2572` runtime.
The corrected invoice, workspace, decision, InfoHelp and Product Truth tests
passed as a 297-test group. Compilation and `git diff --check` passed.
The full Windows run passed 3075 tests and 7 subtests with 23 failures in
`test_archive_delivery_recovery.py` and `test_archive_delivery_v1.py`.
The failures match the prior repair run by test ID and are Windows-specific
process, file-permission or temporary SQLite cleanup cases. Representative
cases also fail on the unmodified `42e2572` export. The invoice suites passed.

Seven end-to-end preview probes used the real OpenAI API with `gpt-4o`, a
synthetic contact and isolated SQLite/storage, and a frozen Bratislava date
on each test boundary. They exercised Ukrainian relative weeks and service
continuation, Slovak explicit KW and 2 January delivery, Russian позавчера,
Russian explicitly historical issue and delivery dates, Ukrainian out-of-window
year clarification, a Slovak legacy invoice, and Slovak previous week with
last Friday delivery. All seven passed the final run. Each reached the
expected preview with zero approvals, no generated PDFs and identical SQLite
bytes before and after the conversation. Earlier probes exposed model omission
of a date and once of a stated service. Exact labeled calendar dates now have
a Python verification path. The prompt explicitly distinguishes named services
from unnamed calculated lines.

### Second review of `37ee697`

The tests-first run produced 17 failures and one pass. The fixtures showed
partial week lists and ranges, incomplete groups reaching calculation, and
dates borrowing a year from the customer, a total, an invoice ID, or a
separate dated field. The corrected suite also covers historical rollovers,
an ordinary yearless date carrying a spurious model year, and an in-draft
year-only reply that preserves the other calculation inputs and writes no PDF
or database rows.

The approved Design Proof was recovered as the original Markdown attachment
from the design verification chat. Its SHA-256 is
`e54a1e09f7b71cdef63fa454a939f1ce8c885d78c48c17c6696933f6152a2391`.
The later owner decision about saving a rate remains recorded in this eval
and `PROJECT_LOG.md`.

The focused invoice, workspace, decision, InfoHelp and Product Truth run
passed 332 tests on the repaired candidate. Compilation passed.

#### Windows audit of the 23 prior full-suite failures

Replayed the exact 23 test IDs on Windows 11 with Python 3.12.0 against
pre-PR `main` at `84ff360` and the repaired candidate. Both runs produced the
same 23 failed test IDs, the same per-test errors, and one additional teardown
error for the encrypted-payload case. The archive source and test fixtures
are identical across those versions.

The paired replay deferred automatic garbage collection to reproduce the
fixture's open SQLite handles deterministically. `sqlite3.connect()` used as
a context manager commits a transaction on exit and leaves the connection
open. On Windows, cleanup raises `WinError 32` when it removes the temporary
`bot.db` while that connection is open. With normal collection, several cases
pass when isolated. The paired replay ran outside loopback sandbox restrictions
so the two child-process checks reached the Windows `signal` assertion.

Every row below failed with the listed cause on both `84ff360` and the candidate.
The first two rows are from `test_archive_delivery_recovery.py`. The remaining
rows are from `test_archive_delivery_v1.py::DeliveryTests`.

| Test | Failure on both versions |
|---|---|
| `test_actual_child_sigkill_notice_restarts_without_upload_retry[before_ack]` | Missing SIGKILL |
| `test_actual_child_sigkill_notice_restarts_without_upload_retry[after_ack]` | Missing SIGKILL |
| `test_403_rate_limit_differs_from_permission_failure` | Open SQLite cleanup |
| `test_annual_routing_is_document_based_for_2026_2027_2028` | Open SQLite cleanup |
| `test_context_probe_does_not_create_missing_database` | Open SQLite cleanup |
| `test_duplicate_annual_folder_fails_closed` | Open SQLite cleanup |
| `test_encrypted_payload_original_and_period_preserved` | Open SQLite cleanup / POSIX mode 0600 |
| `test_external_tree_with_valid_workspace_suffix_is_rejected` | Open SQLite cleanup |
| `test_legacy_provider_cannot_report_routed_success` | Open SQLite cleanup |
| `test_missing_gmail_pointer_is_not_silently_lost` | Open SQLite cleanup |
| `test_missing_original_message_is_honest_and_cutoff_frozen` | Open SQLite cleanup |
| `test_missing_provider_exhausts_exactly_five_attempts` | Open SQLite cleanup |
| `test_notice_restart_delivery_retry_and_no_keyboard` | Open SQLite cleanup |
| `test_remote_mismatch_is_not_overwritten` | Open SQLite cleanup |
| `test_revoked_member_cannot_receive_notice` | Open SQLite cleanup |
| `test_rollout_audit_is_read_only_and_blocks_legacy_jobs` | Open SQLite cleanup |
| `test_route_config_invalid_never_becomes_legacy` | Open SQLite cleanup |
| `test_same_folder_reused_and_immutable_route_after_config_change` | Open SQLite cleanup |
| `test_snapshot_job_insert_is_atomic_and_duplicate_is_stable` | Open SQLite cleanup |
| `test_timeout_reconciles_same_file_without_duplicate` | Open SQLite cleanup |
| `test_transient_authority_lookup_retries_instead_of_blocking` | Open SQLite cleanup |
| `test_worker_rejects_untrusted_storage_before_payload_write` | Open SQLite cleanup |
| `test_wrong_secret_worker_notifies_without_upload` | Open SQLite cleanup |

The encrypted-payload check expects `0o600` and reads Windows mode `0o666`.
The separate error for that same test occurs during SQLite cleanup. This audit
establishes that the 23 listed failures predate PR #119. The full Windows suite
remains non-green and a full Linux run was not performed.

### Service fallback review of `a420dbd`

The public text handler receives a new ventilation-installation service. Phase 2
omits its canonical fields and echoes text without the service. The same contact's
last invoice contains electrical work. These scenarios cover the singleton and
`items[]` forms with a raw mention, a bounded `service_named` result, and a
bounded `unknown` result. The first four cases reproduced the incorrect
history-based preview on `a420dbd`.

The corrected route asks for the exact service without reading history. The
reply advances the same draft to confirmation with the new service, 120 hours,
EUR 406.00 in deductions and EUR 3434.00 payable. The fixture verifies identical
SQLite bytes and zero delivered PDFs before approval. The positive control still
uses the unique scoped historical label when the request genuinely omits the
service. Telegram and OpenAI transport are synthetic in these regressions.
The focused invoice, workspace, decision, InfoHelp and Product Truth run
passed 338 tests. All 12 service-fallback regressions and controls also passed
in a separate run.

## Verdict

`runtime_not_proven` for rollout. The local result uses the real SQLite and
PDF layers. Interactive Telegram, server clock/NTP, production-copy audit
and sudden host or storage loss remain unverified. The process interruption
tests cover abrupt exit of the bot writer process. They do not simulate
simultaneous failure of SQLite and the filesystem.
