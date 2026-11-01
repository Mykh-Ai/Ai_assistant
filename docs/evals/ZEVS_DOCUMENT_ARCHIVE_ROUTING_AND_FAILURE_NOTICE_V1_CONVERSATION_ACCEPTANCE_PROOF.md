# ZEVS Archive V1 — Conversation Acceptance Proof

Verdict: `runtime_not_proven`

Updated: 2026-11-01 (Europe/Berlin). Baseline HEAD: `487ea4513d5e260edcfde472473fd018b8a4b303`.
Reviewed candidate for publication on
`feat/zevs-archive-annual-routing-notices-v1`; local verification branch was
`work/zevs-archive-implementation`. Exact publication commit/PR is supplied by
the publishing agent in the handoff; no commit identity is invented here.
Approved design: `docs/architecture/ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1_ARCHITECTURE_DESIGN_PROOF.md`, revision 3.
Task: `docs/tasks/ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1_IMPLEMENTATION_TASK.md`.
Canonical evidence standard: `docs/Evaluation_and_Smoke_Test_Standards.md`.

The declared evidence scope is isolated local Python/SQLite/filesystem execution,
real registered public handlers and middleware, with synthetic users/documents,
fake external transports, and bounded fake model/STT outputs. This proves local
behavior at those boundaries. It does not prove a deployed service, live Google
permissions/consent, real bank-document handling, live Telegram delivery or real
speech recognition. All applicable required local behavior groups now pass;
only real-provider/server/manual external evidence remains outstanding.
No merge/deploy approval follows from this artifact.

## Preflight and environment

- Full isolated clone, clean initial worktree, only root AGENTS.md found.
- Approved design/task and applicable storage, archive, period, membership,
  confirmation, Product Truth, migration and evaluation owners inspected.
- Companion `docs/llm/Conversation_Acceptance_Proof_Contract.md` is absent at the
  baseline; the existing Evaluation standard remains the canonical owner.
- Class 5 deterministic integration. No new canonical action, slot, FSM,
  confirmation, phrase dictionary, model or self-learning write.
- Explicit trusted `Config.storage_dir` injection; workspace membership and a
  syntactically correct path suffix alone do not authorize source access.
- User authorized isolated installation of existing requirements plus pytest
  and pytest-asyncio. Requirements files were not changed. Python 3.12.14,
  pypdf 4.3.1 (the repository's >=4,<5 range), pytest 9.2.0,
  pytest-asyncio 1.4.1, aiogram 3.31.0; pip check reports no broken requirements.
- Local temporary SQLite/storage only. No real IDs or secrets added to source.
  Verification performed no server, production data/config or Google/Telegram
  writes. GitHub publication is a separate explicitly authorized handoff step.

## Executed checks

- Coordinated 19-file focused regression batch: **483 passed in 11.04s**.
  Covers Gmail period/collector/archive/scheduler/config, accounting archive,
  workspace isolation/intake, jobs/worker, legacy provider, Product Truth,
  InfoHelp, voice/state/tenant/attachment routing and decision callbacks.
- `pytest -q tests/test_archive_delivery_v1.py tests/test_archive_delivery_edge_cases.py tests/test_archive_delivery_public_journeys.py tests/test_gmail_statement_scheduler.py tests/test_info_help.py`:
  **169 passed in 8.08s**.
- After final Slovak Drive-copy synchronization: `pytest -q tests/test_info_help.py`:
  **106 passed in 0.46s**.
- Earlier full run: **2972 passed, 7 subtests passed in 106.70s**, exit0.
- Final `.venv/bin/python -m pytest -q` after local gap closure:
  **2996 passed, 7 subtests passed in 97.25s**, exit0.
- Follow-up local gap batch (recovery + edge): **39 passed in 8.16s**.
- Final `.venv/bin/python -m pytest -q tests/test_archive_delivery_v1.py tests/test_archive_delivery_edge_cases.py tests/test_archive_delivery_public_journeys.py tests/test_archive_delivery_recovery.py`: **80 passed in 11.04s**.
  Recovery adds actual concurrent reservations, child-process SIGKILL/restart,
  real work-time/invoice FSM preservation and calendar-edge continuation.
- Existing pdftoppm renders of synthetic protected original and password-free
  payload have identical PNG SHA-256 at 72 dpi; page/text/media-box invariants
  and unchanged source bytes are also asserted with repo-pinned pypdf 4.3.1.
- Parent independently checked scoped routing, foreign-tree rejection, 403
  classification, authorized notices and read-only audit/unchanged DB hashes.
  Parent also executed the post-send/pre-ack fault-injection trace in row17;
  the new recovery suite additionally terminates real synthetic child processes
  with SIGKILL before and after acknowledgement.
- Final compileall and whitespace checks: passed (commands below).
- pytest emits the existing unset asyncio fixture-loop-scope deprecation
  warning; no unrelated configuration change was made.

Final static checks: `.venv/bin/python -m compileall -q bot tests` and
`git diff --check`.

## Public-entry observed traces

Evidence owners: `tests/test_archive_delivery_public_journeys.py` and
`tests/test_archive_delivery_recovery.py`. The real
production HandlerObjects, filters and router order are installed into isolated
Router containers in a real aiogram Dispatcher. Actual authorization and active
FSM middleware and MemoryStorage execute. Telegram BaseSession/downloads,
LMM classification, metadata extraction, bounded decision model and STT are
synthetic. These are public-handler local journeys, not live Telegram evidence.

Common precondition: authorized synthetic actor 900001 belongs to
`synthetic-zevs`; configured company root is `synthetic-company-root`; empty
local document/queue store. The model-provided issue_date `2026-09-15` transfers
through existing Python validation into local path and frozen route context.
The approved scenario's October sample is tested with September instead; the
same generic month contract applies. No new resolver action or slot is added.

| Trace / scenario IDs | Exact inputs and state before each | Guards / resolver / Python owner | Observed effects and final UX |
|---|---|---|---|
| P1 / 1,3 | IDLE: `/add_blocek`; waiting_upload: synthetic photo; waiting_preview_decision: `uložiť s kategóriou` or `✅ Uložiť s kategóriou` | Authorized; active FSM wins; existing receipt preview decision `save_with_category`; accounting_document_intake shared confirmed-save helper | Before approval jobs/context=0/0; after=1/1; final IDLE; ReplyKeyboardRemove; local-save + background-upload wording; actual owner provider with fake Drive verifies `Zevs_2026/blocky/2026-09`, one file |
| P2 / 2 | Same command/photo; preview: voice with STT transcript `uložiť s kategóriou` | Actual voice/state handler converges to same preview helper and canonical decision | Same one save/job, IDLE and keyboard removal as P1; STT itself is fake |
| P3 / 4 | IDLE: photo; attachment proposal: `áno`; preview: `uložiť s kategóriou` | Actual OfficeFlow attachment router → existing intake; proposal bounded yes=`ano` | No persisted document/job before preview approval; then P1 result/target/cleanup |
| P4 / 22,23 | Existing preview: `neviem`, `❌ Zrušiť`, `/cancel` in separate tests | Existing unknown/cancel/state-control owners; no idle fallback | Unknown retains preview and existing keyboard; cancel clears to IDLE/removes keyboard; no originals/jobs/context written |
| P5 / 21 | Unauthorized actor900002, IDLE: `/add_blocek`, photo or voice separately | Actual authorization middleware rejects before STT/LMM/download/business handling | No AI call, download, storage delta, job or context; unauthorized message |
| P6 / 26 | IDLE text, or voice transcript: `Vieš zbierať bankové výpisy z Gmailu bez hesla?` | Existing InfoHelp capability owner; no execution action | Honest partial/setup answer with conditional password-free copy; IDLE, jobs/context=0/0, no payload; no false absolute prohibition |
| P7 / 19 | P1 inputs; enqueue owner raises a synthetic exception | Confirmed local save already succeeded; shared save owner catches bounded failure | Original remains; jobs/context=0/0; IDLE/keyboard removed; immediate truthful enqueue-error answer; durable background notice has no markup or raw exception |
| P8 / 24 | Earlier failed job; user currently in another receipt preview | Actual background notice delivery while real active state/data/reply keyboard captured | Same state, data and keyboard afterward; separate no-markup notice with five attempts; no new upload/job |
| P9 / 20 | P1 save; persisted active profile switched to synthetic-second before worker | Actual WorkspaceContextService switch; worker uses original immutable snapshot and current original membership | Upload remains original workspace/root; active selection remains second; no retarget |
| P10 / 40 | `/add_blocek`; photo with issue_date=None; text `31.12.2026`; corrected photo; `uložiť s kategóriou` | Existing Python intake validation rejects incomplete candidate; waiting_upload consumes continuation; real job clock frozen January1,2027 | No write until corrected file and confirmation; then one job/context, route2026-12 despite2027 enqueue; IDLE/ReplyKeyboardRemove; one verified file/no2027 tree |
| P11 / 24 | IDLE: `Vytvor výkaz za december 2026` (fake bounded action=generate_work_time_report, period month2026-12), or `/invoice`; then background notice, then `/cancel` | Actual work-time report setup/InvoiceStates.waiting_input reached through public router; actual state control owns cancel | Notice keeps state/data unchanged, no markup/edit; work-time inline keyboard retained; cancel subsequently reaches IDLE and removes owned inline markup |

## Design-to-code map

Mapping status: `design_matches_runtime` **for implemented local branches only**;
this is not a second acceptance verdict and does not assert external runtime.
No material architecture deviation was introduced. Observed fixture variations and external gaps are
listed explicitly in the scenario matrix.

| Requirement | Owner | Named executable evidence |
|---|---|---|
| Strict optional private config, generic year | archive_delivery.configured_route / make_snapshot | annual_routing_is_document_based_for_2026_2027_2028; route_config_invalid_never_becomes_legacy |
| Trusted source, frozen route, atomic enqueue | archive_delivery.make_snapshot / ArchiveJobService.enqueue_job | external_tree_with_valid_workspace_suffix_is_rejected; snapshot_job_insert_is_atomic_and_duplicate_is_stable; P1/P9 |
| Private decrypted copy, unchanged source, terminal cleanup | prepare_payload / _unsigned_pdf / cleanup_payload / ArchiveWorker.process_one | encrypted_payload_original_and_period_preserved; rendered_statement_page_is_identical; terminal_failure_cleans_decrypted_payload_and_retains_original |
| Annual children, reservation, pagination | archive_delivery_drive._folder / _target | concurrent_annual_type_month_reservations_create_one_tree; each_folder_timeout_recovers_persisted_id_in_new_worker; folder_pagination_reuses_existing_id |
| Same-ID verified upload and bounded HTTP errors | upload_routed_file / _verify_file / _retryable | timeout_reconciles_same_file_without_duplicate; remote_mismatch_fails_worker_without_overwrite; 403_rate_limit_differs_from_permission_failure |
| Unsupported providers fail closed | ArchiveWorker + legacy provider capability checks | legacy_provider_cannot_report_routed_success; context_probe_does_not_create_missing_database |
| Five attempts, authoritative terminal jobs | ArchiveWorker / archive_failure_notices.reconcile | missing_provider_exhausts_exactly_five_attempts; notice_restart_delivery_retry_and_no_keyboard |
| Gmail prequeue/password safety | gmail_statement_scheduler._run_tick + collector | real_gmail_tick_secret_failure_or_verified_upload[missing/wrong/valid/plaintext/ambiguous/unsupported/no_text] |
| Independent authorized durable notices | archive_failure_notices / google_drive_archive_scheduler | notice_scheduler_runs_while_upload_disabled; revoked_member_cannot_receive_notice; actual_forbidden_error_blocks_delivery_without_upload_retry; P7/P8 |
| Missing source and transient authority failure | notice ownership checks | missing_gmail_pointer_is_not_silently_lost; missing_source_worker_notifies_without_false_retention; transient_authority_lookup_retries_instead_of_blocking |
| Truth and unchanged surrounding flows | product_truth / info_help / existing handlers | P6; drive_capability_explains_configured_annual_route_and_async_failures; focused legacy suites |
| Rollout safety | archive_delivery_audit / rollout runbook | rollout_audit_is_read_only_and_blocks_legacy_jobs; unchanged DB hash, no absent-DB creation |

## All 40 approved scenarios

`V1`, `E`, `P` below denote the new v1, edge_cases and public_journeys test
modules. `old` denotes the named existing regression suite in the focused/full
run. All observed tests use synthetic DB/storage and fake external boundaries.
`R` denotes test_archive_delivery_recovery.py. OS-process termination is real
only for those synthetic child processes; it sends no external message.
For background rows entry is the exact job/tick/provider event below; there is
no LLM action, new slot, FSM transition or keyboard. Current workspace
membership and trusted source gates execute; original ownership is retained.
Q denotes the real archive job status, N the durable notice status. Public rows
inherit the exact inputs, guards, states, owner, outputs and counts from P1–P10.
A narrower observed boundary is never a claim that the unrun case passed.

| # | Exact event / evidence | Observed effect / final state / result |
|---|---|---|
| 1 | P1 receipt command/photo/reply approval | pass local; one verified file; IDLE/keyboard removed |
| 2 | P2 voice preview confirmation | pass local; same owner/one save/cleanup |
| 3 | P1 typed and reply-button variants | pass local; same target/count/exit |
| 4 | P3 idle attachment proposal/approval | pass local; no premature persistence |
| 5 | E real_gmail_tick_secret_failure_or_verified_upload[valid], synthetic encrypted September2026 header | pass local scheduler→collector→job→owner provider; source unchanged, payload unencrypted and cleaned, direct `Zevs_2026/Vypisy` |
| 6 | E actual `_run_tick` plaintext2027 with no secret file + unencrypted payload test | pass; validated byte-identical unencrypted PDF uploaded to direct `Zevs_2027/Vypisy`; unnecessary secret is not required |
| 7 | E actual `_run_tick` with missing/wrong secret; V1 wrong_secret_worker_notifies_without_upload | pass local; original retained, no upload, bounded notice, no leaked synthetic password |
| 8 | E actual `_run_tick` conflicting December2026/January2027 PDF and no-text PDF | pass; original stored, zero job/upload, bounded period_ambiguous/text_unavailable notice; no guessed year/month |
| 9 | V1 signed fail-closed; E corrupt transform and actual unsupported-encryption `_run_tick` fixture (`/V 9`) | pass bounded review errors; no misleading transformed upload; unsupported source retained and safe pdf_unreadable notice delivered |
| 10 | V1 missing_provider_exhausts_exactly_five_attempts | pass; Q retry_wait×4→failed on fifth, retained source, no sixth attempt; notice reconciliation tested separately |
| 11 | R two_transient_file_errors_then_third_verified_success | pass; fresh workers see two retry_wait outcomes then uploaded; all3 file-create attempts use identical reserved ID/bytes, one remote file, no false failure notice; existing attempts counter correctly records2 failures |
| 12 | R enabled_provider_builder_none_has_bounded_lifecycle_and_notice | pass actual builder catches TokenCryptoError→None; five executions terminate, original retained and one authorized no-markup notice |
| 13 | V1 timeout_reconciles_same_file_without_duplicate | pass; remote create timeout reconciles same reserved ID; one file |
| 14 | E remote_mismatch_fails_worker_without_overwrite[parent/size/ref/md5] | pass; failed/archive_remote_mismatch, no overwrite, original retained |
| 15 | V1 failed-job restart scanner/repeated reconciliation; R real child restart tests | pass persisted failed-job recovery/dedupe plus separate real-process lease recovery; one ordinary event, no lost notice |
| 16 | Same V1 timeout→successful send→later ticks | pass N retry_wait→sent, sent_at only after success, no later ordinary send/upload retry |
| 17 | R actual_child_sigkill_notice_restarts_without_upload_retry[before_ack/after_ack] | pass real synthetic child SIGKILL after fsynced fake send. Before ack: row sending/sent_at NULL; new process +1min no send, +6min identical resend/ack, +12min no send (2 total). After ack: sent survives kill, no resend (1 total). Same event/reference; upload remains pending/attempts0. No live Telegram. |
| 18 | V1 revoked_member_cannot_receive_notice; E actual_forbidden_error_blocks_delivery_without_upload_retry | pass; delivery_blocked, no alternative recipient, no upload retry |
| 19 | P7 confirmed save then enqueue exception | pass; local original/IDLE/keyboard cleanup, truthful exit and durable notice |
| 20 | P9 actual active-profile switch after public save | pass; immutable original workspace/company root |
| 21 | P5 unauthorized public inputs; V1 foreign-tree/wrong-root tests | pass; no unauthorized external/storage effects; correct-key foreign tree rejected |
| 22 | P4 `neviem`; old unknown preview tests | pass; preview/keyboard retained, no saved original/job |
| 23 | P4 cancel; old category-back and expired preview/voice tests | pass existing handlers; no save/enqueue; intended terminal/return states and cleanup |
| 24 | P8 and P11/R public work-time report and invoice flows | pass actual different receipt, work-time inline-choice and invoice waiting-input FSM state/data/keyboard unchanged by no-markup notice; subsequent cancel still works and cleans owned UI |
| 25 | old accounting intake incoming save; workspace isolation; legacy owner/service-account tests | pass unchanged route/owner contracts for nonoverridden types/workspaces |
| 26 | P6 text/voice question; final Slovak Drive-copy regression | pass truthful partial/setup/no-side-effect boundaries |
| 27 | V1 annual2027 receipt creation + E actual plaintext2027 statement tick/provider | pass first verified `Zevs_2027/blocky/2027-01` and direct `Zevs_2027/Vypisy`; no2026 destination for2027 data |
| 28 | V1 atomic/duplicate enqueue; old Gmail source/content and archive dedup suites | pass stable original/job/context identity; no retarget |
| 29 | V1 repeated schema bootstrap + old archive schema idempotence | pass additive repeated initialization and preserved legacy rows; production migration not run |
| 30 | V1 read-only activation audit with pending legacy routed job | pass blocker detected; DB hash unchanged; no raw IDs; absent path not created |
| 31 | E remote mismatch parameter matrix | pass parent/size/reference/checksum rejection; Q never uploaded for mismatched remote file |
| 32 | V1 terminal cleanup/original retention + old worker/local deletion tests | pass local original/metadata retention on pending/failed; private payload only removed |
| 33 | E missing_source_worker_notifies_without_false_retention + V1 absent Gmail pointer | pass no upload; notice says original unavailable, uses persisted ownership |
| 34 | V1 December2026 period ingested January2027 + E frozen-year retry | pass document-period route remains2026; original identity unchanged |
| 35 | E clock2026-12-31T23:55Z→2027-01-01T00:10Z retry; R actual January1 enqueue after corrected December file | pass frozen2026 context and destination; one file, no2027 tree |
| 36 | V1 same_folder_reused + E pagination | pass verified existing children reused; second file no duplicate tree |
| 37 | R concurrent_annual_type_month_reservations + each_folder_timeout_recovers_persisted_id_in_new_worker | pass two real worker threads compete before each of3 reservations; SQLite selects one ID/key, one tree/two distinct files. Annual/type/month remote-create timeout variants each recover same persisted ID in fresh worker, no duplicate folders |
| 38 | V1 duplicate annual/403 tests; R cached_folder_lineage_or_permission_change_fails_closed (3levels×parent/trashed/capability) | pass no first-match/fallback/overwrite; changed cached lineage or denied create capability blocks before new remote create and retains source |
| 39 | V1 annual_routing…2028 | pass same generic templates; no yearly code edit |
| 40 | P10/R actual public missing-date→text retry→corrected-file confirmation at January1; E conflicting New-Year statement `_run_tick` | pass invalid values never default to now; file continuation stays with intake; corrected December receipt goes to2026-12, ambiguous statement gets review notice/no job |

## Evaluation record and remaining gate

Declared maturity: deterministic integration proposal; Product Truth remains
`partial`. Unit, public-handler integration, voice-transcript, keyboard,
tenant/no-side-effect, PDF render and read-only audit evidence is local only.
No layout redesign was made. Manual real-document visual review was not run.

All required local behavior groups pass, including the previously unproven
retry, concurrency, process termination, unsupported encryption, cached lineage,
provider-builder, other active FSM,2027 statement and calendar continuation
boundaries. Tests use fake external transports; this is local readiness evidence,
not an additional verdict or a claim of live acceptance.

Real server backup/audit/schema apply/rollback, Google OAuth consent, production
image execution (Dockerfile uses Python3.11), real bank-document visual review
and actual Drive/Telegram/STT smoke remain **not_run**. They require the reviewed
operational procedure in `docs/ZEVS_Archive_Rollout_Runbook.md`, which includes
pinned source/integration, private inputs, read-only audit, offline rehearsal,
backup-before-bootstrap, explicit apply/activation, smoke and compatible rollback.

No historical retarget, original deletion, live external operation or automatic
activation occurred. The full-suite result does not remove those limitations.
