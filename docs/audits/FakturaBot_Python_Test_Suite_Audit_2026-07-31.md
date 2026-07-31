# FakturaBot Python Test Suite Audit And Consolidation Plan

Date: 2026-07-31
Baseline: `origin/main` commit `4a69b31`
Branch: `audit/fakturabot-test-suite`
Scope: audit and documentation only

## 1. Executive summary
## Implementation follow-up

The approved taxonomy and high-confidence consolidation slice was implemented
on 2026-07-31 on branch test/fakturabot-taxonomy-phase1. Its exact old-to-new
node mapping and validation evidence are recorded in
docs/testing/FakturaBot_Test_Taxonomy_Phase1_Evidence_2026-07-31.md. The
baseline findings and recommendation totals below remain the audit snapshot.


The current suite contains **2,433 pytest-collected tests in 101 Python test
files**. Two clean full runs passed: 467.17 seconds and 485.03 seconds. Pytest
also reported seven passing `unittest` subtests; those are not additional
collected pytest node IDs. Collection itself is healthy at 6.09 seconds.

The suite is large chiefly because several valuable bounded contract matrices
are parametrized. `tests/test_decision_resolver.py` contributes 663 cases but
takes only 3.395 seconds, and `tests/test_invoice_intent_prerouter.py`
contributes 227 cases. Raw test count is therefore not evidence of waste.

The strongest protection is around deterministic parsing, DecisionResolver,
invoice state transitions, real temporary SQLite databases, multi-workspace
isolation, migration rollback, access control, archive recovery, and bounded
external-service contracts. These areas should remain contract-critical.

The clearest maintenance opportunities are:

- seven files contain high- or medium-confidence scenario shells suitable for
  parametrization while preserving named scenario IDs;
- three literally identical Google Drive Product Truth tests should have one
  canonical owner;
- repeated source-import boundary checks can share one architecture-test
  harness without dropping any module-specific scenario;
- voice dispatch coverage is extensive but heavily patched, so it proves
  routing more strongly than complete public user journeys;
- the old service-account Drive cases require a Product Truth/deployment
  decision before they can be retired or isolated.

No test is classified `DELETE_CANDIDATE`. No coverage reduction is recommended.

File-level recommendation totals (a status identifies work in a file, not a
license to remove the file):

| Recommendation | Files |
|---|---:|
| KEEP | 10 |
| KEEP_CRITICAL | 78 |
| CONSOLIDATE | 3 |
| PARAMETRIZE | 7 |
| INVESTIGATE | 2 |
| REWRITE | 0 |
| OBSOLETE_CANDIDATE | 1 |
| DELETE_CANDIDATE | 0 |

The complete per-file evidence inventory is in
[`FakturaBot_Python_Test_File_Inventory_2026-07-31.md`](FakturaBot_Python_Test_File_Inventory_2026-07-31.md).

## 2. Audit preflight and constraints

Read before analysis: `AGENTS.md`, `README.md`, `pytest.ini`, Product Doctrine,
AI implementation standards, Product Truth contracts, Self-Learning,
Evaluation and Smoke Test Standards, Product UX Eval Artifacts, TZ, canonical
DecisionResolver, top-level/subflow architecture, action/response registries,
workspace/storage/migration contracts, current Google Drive/Gmail architecture
and acceptance artifacts, the keyboard lifecycle audit, recent
`PROJECT_LOG.md`, and relevant Git history.

Extracted constraints:

- Python owns truth, validation, authorization, tenant scope and side effects.
- Text, voice and callbacks are not duplicates when they protect distinct
  reachable channels or state ownership.
- Active FSM, stale callback, confirmation, keyboard cleanup, workspace,
  migration and prior-bug cases remain critical until equivalent protection is
  demonstrated.
- Component tests do not by themselves prove a public conversation journey.
- External-service fakes must be reported as mocked evidence, not live runtime
  proof.

Touched scope: product/testing documentation and `PROJECT_LOG.md` only. No
confirmation, routing, LLM, STT, LMM, FSM, storage, DB, access, server,
PDF/layout, production code, test, dependency or CI behavior changed.

Current status: the Python suite is `implemented`; test taxonomy and execution
tiering are `partial`; external Gmail acceptance and several server/live
smokes are `runtime_not_proven`. AI maturity is unchanged. Self-learning hooks
were reviewed only as test obligations; no learning behavior or data changed.

Out of scope: executing any cleanup phase, changing markers/configuration,
running live Telegram/Google/provider calls, touching production data, or
deploying. The proving journey for this audit is exact collection, two clean
full runs, focused repetition, reverse-order probing, static file-by-file
inspection, contract comparison and Git-history review.

## 3. Exact inventory and suite map

`pytest.ini` contains only:

```ini
[pytest]
testpaths = tests
```

There is no `conftest.py`, shared test-helper/factory module, registered custom
marker, `pyproject.toml` pytest section, or `.github/workflows` directory on the
audited baseline. Fixtures, dummy Telegram objects, fake clients and database
builders are local to test files. This improves local readability but repeats
substantial setup and makes cross-file conventions implicit.

### Map by product domain

Times are the sum of JUnit testcase times from the second full run; suite time
was 484.668 seconds and testcase time summed to 479.712 seconds.

| Domain | Files | Cases | Testcase seconds |
|---|---:|---:|---:|
| DecisionResolver/callback UI | 2 | 684 | 14.409 |
| Invoice creation/edit/routing | 7 | 381 | 110.861 |
| Accounting intake/archive | 13 | 219 | 13.504 |
| Google Drive/OAuth | 8 | 166 | 22.750 |
| Product Truth/InfoHelp | 2 | 128 | 0.065 |
| Admin runtime issue/handoff | 7 | 127 | 64.196 |
| Customization/admin review | 2 | 87 | 57.585 |
| Work time/reporting | 2 | 75 | 26.638 |
| Voice/STT routing | 2 | 67 | 3.216 |
| Contact registry/tax | 6 | 67 | 15.341 |
| Invoice analytics sandbox | 4 | 60 | 5.890 |
| Contacts/aliases | 4 | 48 | 31.791 |
| Archive outbox/worker | 2 | 43 | 5.992 |
| Idle attachment routing | 2 | 39 | 0.639 |
| Invoice follow-up/archive | 3 | 37 | 28.207 |
| Gmail/OAuth collector | 9 | 33 | 1.753 |
| Access/authorization | 2 | 28 | 20.411 |
| Accounting analytics | 4 | 21 | 0.475 |
| Invoice PDF/Pay by Square | 3 | 18 | 0.055 |
| Multi-workspace migration | 2 | 18 | 21.897 |
| FSM navigation/cancel | 2 | 18 | 1.452 |
| Business profiles/workspaces | 3 | 16 | 10.615 |
| Service aliases/normalization | 3 | 16 | 8.551 |
| Supplier onboarding/profile | 3 | 13 | 3.988 |
| Destructive account deletion | 1 | 9 | 6.389 |
| Tenant isolation | 1 | 7 | 2.902 |
| Temporary intake lifecycle | 1 | 5 | 0.101 |
| Document text intake | 1 | 3 | 0.039 |

### Map by current inferred test level

Levels are inferred from entrypoint and assertion behavior because the suite
has no declared markers.

| Level | Files | Cases | Testcase seconds |
|---|---:|---:|---:|
| Unit/regression | 53 | 954 | 269.316 |
| Contract/unit | 10 | 896 | 7.006 |
| FSM/subflow/regression | 17 | 383 | 119.891 |
| Integration/regression | 11 | 98 | 64.941 |
| Callback/regression | 4 | 59 | 15.247 |
| Integration/contract | 3 | 25 | 3.256 |
| Unit/smoke | 3 | 18 | 0.055 |

The level totals show the central ambiguity: many tests use real SQLite and
filesystem effects but fake Telegram or external transports. They are stronger
than pure unit tests but do not constitute live integration or acceptance
proof.

## 4. Execution and duration profile

### Full-run observations

| Run | Result | Time |
|---|---|---:|
| Collection | 2,433 collected | 6.09s |
| Full run with 100 durations | 2,433 passed, 7 subtests passed | 467.17s |
| Full run with JUnit evidence | 2,433 passed, 7 subtests passed | 485.03s |

The 17.86-second difference between full runs is 3.8% and does not indicate a
failure or clear flaky test. The slowest individual call was 2.48 seconds.
The total cost is distributed across many SQLite/bootstrap-heavy cases.

### Slowest modules

| Module | Cases | Seconds |
|---|---:|---:|
| `test_invoice_state_decisions.py` | 73 | 41.328 |
| `test_invoice_intent_prerouter.py` | 227 | 36.696 |
| `test_customization_request_admin.py` | 52 | 35.779 |
| `test_invoice_phase2_ai_layer.py` | 68 | 25.128 |
| `test_customization_requests.py` | 35 | 21.806 |
| `test_multi_workspace_migration_apply.py` | 13 | 19.054 |
| `test_runtime_issue_handoff.py` | 33 | 18.805 |
| `test_runtime_issue_routes.py` | 33 | 18.013 |
| `test_work_time_routing.py` | 37 | 14.708 |
| `test_runtime_issue_evidence.py` | 24 | 14.110 |
| `test_access_request_flow.py` | 18 | 13.389 |
| `test_contact_intake_semantic_flow.py` | 21 | 13.122 |

### Slowest individual calls

| Test | Time | Assessment |
|---|---:|---|
| `test_handlers_do_not_define_local_confirmation_parsers` | 2.48s | Slow source scan, but contract-critical |
| `test_generic_dry_run_fails_closed_for_broken_workspace_foundation` | 2.06s | Real migration safety; keep |
| `test_menu_does_not_bypass_access_control_for_unauthorized_users` | 2.05s | Access boundary; keep |
| `test_remote_verifier_leaves_project_unchanged_for_tip_ancestor_and_unrelated` | 1.89s | Git/subprocess recovery boundary; keep |
| `test_already_migrated_two_profiles_use_workspace_owned_audit` | 1.89s | Migration/workspace safety; keep |
| `test_apply_backup_post_audit_and_rollback_round_trip` | 1.86s | Destructive-path rollback proof; keep |
| `test_post_swap_fingerprint_failure_restores_original_database` | 1.86s | Emergency restore proof; keep |

The right optimization target is repeated database/bootstrap scaffolding and
focused feedback selection, not removal of slow risk scenarios.

## 5. Critical contracts and regression history that must remain

| Protection | Named evidence that must survive |
|---|---|
| Shared confirmation authority | `test_handlers_do_not_define_local_confirmation_parsers`, context matrices and multilingual/STT cases in `test_decision_resolver.py` |
| Invoice creation/edit/follow-up | `test_waiting_confirm_accepts_multilingual_yes_and_generates_pdf`, `test_preview_failure_db_cleanup_happens_even_when_unlink_fails`, `test_workspace_callback_uses_invoice_workspace_not_active_selection`, mark-paid stale/confirmation cases |
| Accounting intake | duplicate no-save/save gates, preview confirmation, expired staging cleanup, archive enqueue idempotency and workspace-target tests in `test_accounting_document_intake_flow.py` and archive suites |
| Work time | Bratislava time boundaries, lunch net/gross regressions, preview confirmation, delete-month isolation and voice state routing |
| Workspace/tenant safety | every `test_workspace_*`, `test_tenant_safety.py`, authorization-before-AI/storage tests, active workspace switch-after-start cases |
| Persistence/migration | all dry-run/apply/rollback/fingerprint/lock/storage-drift/emergency-restore cases in `test_multi_workspace_migration*.py`, contact IBAN and legacy SMTP migrations |
| Contacts | exact/normalized/fuzzy ambiguity, registry disabled/error/manual fallback, no save before confirmation, alias isolation, monitor revalidation |
| State/navigation/UI | active FSM ownership, global cancel, stale/legacy callbacks, forbidden no-edit, terminal keyboard removal, cleanup-failure logging |
| External boundaries | OAuth state/nonce/token redaction, Gmail readonly/no-mutation, Drive retry/local-retention, tax fail-closed fake contracts |
| Runtime issue intake | administrator-only routing, active-FSM preservation, evidence redaction, leases/redelivery/idempotency and remote verification |
| Slovak UX | Slovak Product Truth/InfoHelp, recovery and analytics answers; these are product contracts, not cosmetic snapshots |

Recent Git history shows these tests were added in response to concrete work:
multi-workspace migration and reactivation, Bratislava timezone and work-time
safety, invoice analytics scoping, Google owner OAuth, contact registry search
and monitoring, keyboard lifecycle repairs, runtime issue leases, and Gmail
collector foundations. Similar setup or a shared production function does not
make those regressions redundant.

## 6. Safe parametrization candidates

All replacements must use explicit `pytest.param(..., id=...)` so scenario
identity remains visible. Counts below describe current collected cases, not a
target reduction.

| Exact tests | Current behavior and equivalence | Replacement protection | Risk / confidence |
|---|---|---|---|
| `test_invalid_iban_raises`, `test_invalid_currency_raises`, `test_invalid_variable_symbol_raises`, `test_empty_beneficiary_name_raises`, `test_invalid_amount_raises` in `test_pay_by_square.py` | Each changes one `PayBySquarePayment` field and asserts the same `PayBySquareValidationError`; equivalent exception failure mode | One five-row invalid-field matrix with field/value IDs | Low risk / high |
| `test_normalize_opravy`, `test_normalize_remont_ru`, `test_normalize_montazh_ru` in `test_service_term_normalizer.py` | Same pure function and equality assertion; only input/expected changes | One multilingual normalization table preserving three IDs | Low / high |
| `test_top_level_work_time_open_routes_from_slovak_text`, `...close...`, `...manual_range...`, `...report...` in `test_work_time_routing.py` | Same `_resolve(input) == action` shell; distinct actions remain distinct rows | One action-routing matrix with action-specific IDs | Low / high |
| `test_legal_suffix_sro_variant_match`, `test_legal_suffix_spaced_variant_match`, `test_separator_insensitive_match_hyphen`, `test_separator_insensitive_match_spaces` in `test_contact_lookup_normalization.py` | Each stores one contact, resolves a spelling/separator variant, and asserts `normalized_match` plus exact saved name | One saved-name/query/expected-name matrix; keep exact, case-insensitive and fuzzy tests separate because their states differ | Low / high |
| `test_yearly_invoice_summary_resolves_to_invoice_analytics_top_level_action` and `test_invoice_analytics_resolves_as_read_only_top_level_action` in `test_invoice_intent_prerouter.py` | Bodies are AST-identical and both expect `invoice_analytics`; datasets protect yearly multilingual versus broader analytics phrases | One combined matrix with `yearly-*` and `general-*` IDs; keep downstream fast-path and no-side-effect tests | Low / high |
| The three bootstrap-admin tests and three unauthorized middleware tests for list/detail/reply in `test_customization_request_admin.py` | Within each trio, setup, call and assertions are identical except command text | Two command matrices (bootstrap allowed; unknown blocked) preserving list/detail/reply IDs | Low / high |
| Nine `test_delivery_date_*` success cases from line 1558 onward in `test_invoice_phase2_ai_layer.py` | Same `_resolve_delivery_date` shell, but cases encode explicit-year, local-year, stale/future and multilingual distinctions | One success-case table with raw text, issue date, LLM value and expected ISO; keep rejection tests separate | Medium: dense regression semantics / medium |

## 7. Safe consolidation candidates

| Exact tests | Overlap / equivalence | Surviving protection | Risk / confidence |
|---|---|---|---|
| `test_google_drive_product_truth_is_partial_service_account_not_oauth` in `test_google_drive_oauth_callback_service.py`, `test_google_drive_oauth_state_service.py`, and `test_google_drive_setup_commands.py` | The three bodies are literally AST-identical: same English question and same four assertions. Their failure modes are equivalent and do not exercise their containing OAuth/setup modules | Move the exact four-assertion contract to `test_product_truth.py`; retain the stronger Slovak/`owner OAuth` assertions in connection/callback-app tests | Low / high |
| `test_accounting_archive_service_has_no_google_or_network_imports`, `test_cleanup_service_has_no_google_or_network_imports`, `test_archive_job_service_has_no_google_or_network_imports`, `test_archive_worker_has_no_google_or_network_runtime_imports`, `test_google_drive_connection_service_has_no_google_or_network_imports`, `test_oauth_state_service_has_no_google_or_network_imports`, `test_oauth_callback_service_has_no_google_or_network_imports`, `test_google_drive_setup_commands_have_no_google_api_or_network_imports`, `test_token_exchanger_module_has_no_google_client_or_drive_upload_imports`, `test_token_crypto_has_no_google_or_network_imports` | They protect different modules, so none is redundant. The duplicated source-inspection machinery and inconsistent forbidden lists are the consolidation target | A centralized parametrized architecture-import-boundary test with one ID and explicit forbidden set per module; every current module remains a row | Medium: import-time policy may differ per module / medium |

## 8. Obsolete or legacy candidates requiring Product Truth confirmation

No obsolete behavior is proven safe to remove. The following group is an
`OBSOLETE_CANDIDATE`, not deletion approval.

| Exact tests | Current behavior | Product Truth mismatch/question | Surviving/replacement protection | Risk / confidence |
|---|---|---|---|---|
| `test_google_drive_config_parses_owner_run_service_account_env`, `test_missing_service_account_config_sets_not_configured_and_keeps_original`, `test_service_account_provider_creates_stable_folder_path_and_uploads_file`, `test_worker_deletes_original_only_after_uploaded_state_and_keeps_metadata`, `test_worker_applies_incoming_invoice_retention_only_after_uploaded_state`, `test_paid_invoice_pdf_archive_upload_keeps_local_pdf_and_updates_followup_state` in `test_google_drive_service_account_archive.py` | Exercise the legacy `service_account` config/provider and use it to prove upload/retention/follow-up behavior | Current Product Truth says owner OAuth is the partial supported path and service accounts are unsupported for personal My Drive. Code still exposes service-account mode, so deployment compatibility is unknown | Owner-OAuth provider tests protect current upload/config failure behavior. Retention and worker effects must be re-expressed with an owner-OAuth/fake-provider seam before any legacy test removal | High risk if any Shared Drive/old deployment still uses it / low |

The misleading test name
`test_google_drive_product_truth_is_partial_service_account_not_oauth` appears
in five files even though current assertions and Product Truth say owner OAuth.
The behavior remains useful; rename/relocation is a future clarity rewrite, not
an obsolete behavior finding.

Legacy schema, stale callback, old path and migration tests are **not** obsolete
candidates. They protect persisted-data compatibility and previously fixed
production risks. Retirement requires a read-only production inventory and an
approved data-support horizon.

## 9. Flaky, order-dependent and environment-dependent candidates

No failure reproduced in this audit.

- Two complete runs passed.
- 123 stateful migration/handoff/OAuth-state/archive/work-time cases passed in
  three fresh processes: 57.67s, 58.58s and 57.74s.
- The same 123 cases passed in reverse file order in 57.65s.

Candidates to monitor:

| Test | Evidence | Recommendation |
|---|---|---|
| `test_apply_backup_post_audit_and_rollback_round_trip` | `PROJECT_LOG.md` records one earlier Windows `os.replace` access-denied failure in the migration rollback area followed by an immediate pass; current audit passed repeatedly | INVESTIGATE OS file-lock telemetry; do not weaken rollback assertions |
| `test_business_profile_cancel_removes_reply_keyboard` | Earlier monolithic run recorded one transient failure followed by immediate isolated pass; both current full runs passed | INVESTIGATE only if it recurs; capture exact assertion/global state |
| `test_llm_info_help_triage_timeout_is_safe_unknown` | Uses a one-second sleeping fake with a 1ms timeout; deterministic now but scheduler load could expose cancellation cleanup | Keep; consider an awaitable controlled by an event instead of wall time |
| `test_preview_uses_explicit_issue_date_for_delivery_window_and_due_date` and onboarding year cases | Use `date.today()`; logically current-year aware but not hermetic at year boundaries | Freeze/inject date in future rewrite while preserving boundary cases |
| Repository-source/import checks | Depend on running from repository root and exact module source shape | Keep contract intent; centralize path resolution and stable AST/import assertions |

External network calls are mocked or disabled in the ordinary suite. Live
credentials, provider availability and production callback deployment are not
sources of local flakiness because they are not tested here; they are coverage
gaps reported below.

## 10. Over-mocked and implementation-coupled tests

### Over-mocked

- `test_voice_state_routing.py` has 65 collected cases and a very high fake/
  patch density. It strongly proves dispatch and precision exclusions, but
  patched business handlers mean many cases would stay green if the downstream
  handler later stopped producing the right SQLite/FSM/keyboard effect.
- `test_invoice_intent_prerouter.py` and
  `test_accounting_document_intake_flow.py` mix real SQLite with many patched
  AI/PDF/storage seams. This is appropriate for deterministic handler tests,
  but representative public-route acceptance tests must cross more real seams.
- Gmail, Google Drive, tax registry, STT and LMM tests deliberately use fake
  transports. They prove validation, redaction and fail-closed contracts, not
  real provider compatibility.

Recommendation: keep the existing fast cases. Add a small acceptance layer
that starts at the real dispatcher/router, uses real temporary SQLite and
storage, and patches only the network boundary. Do not replace hundreds of
bounded unit scenarios with a few broad end-to-end tests.

### Implementation-coupled

Source-inspection tests include the no-local-parser meta-test, legacy-token
branch scan, no-network-import scans, `test_bot_main_has_no_callback_app_wiring`,
`test_callback_runtime_is_not_wired_to_real_token_exchanger`,
`test_voice_router_has_no_work_time_phrase_dictionary`,
`test_info_help_service_has_no_runtime_side_effect_imports`, and
`test_product_truth_module_has_no_runtime_side_effect_imports`.

These are valuable architecture guards but can fail during harmless refactors
or miss dynamic imports. Preserve the contract while gradually moving to
stable import-graph/AST rules plus behavior-level no-call/no-side-effect tests.
`test_handlers_do_not_define_local_confirmation_parsers` remains
`KEEP_CRITICAL`; its 2.48-second cost is justified until an equivalent static
architecture check exists.

## 11. Important coverage gaps

1. **No declared execution taxonomy.** There are no custom markers, shared
   fixtures, or CI workflows. A developer cannot reliably select integration,
   acceptance, external or server-smoke tests by contract.
2. **Public dispatcher journeys are sparse.** Many handler tests invoke helpers
   with dummy messages. The canonical evaluation standard requires public
   entry, authorization, state transitions, side effects and final keyboard in
   one trace.
3. **Keyboard lifecycle remains open.** The existing keyboard audit is
   `needs_revision`: contact lookup and contact monitor lack full owned-stale/
   expired versus forbidden cleanup and cleanup-failure evidence.
4. **Gmail runtime is not externally proven.** Its acceptance proof explicitly
   marks handler smoke, scheduler integration, malformed-attachment isolation,
   real callback deployment, real OAuth consent and controlled mailbox smoke as
   incomplete.
5. **External contracts are fake-only.** Google Drive/Gmail/tax/STT/LMM tests do
   not verify current provider schemas, authentication, timeout behavior or
   production configuration. Live tests must be opt-in and credential-safe.
6. **PDF visual acceptance is missing.** Unit/layout assertions and a PDF smoke
   exist, but the planned `docs/evals/pdf_layout_manual_review.md` artifact is
   absent. Rendered long-name/item/multi-page/QR/footer evidence is not part of
   automated pytest.
7. **Access/tenant product smoke artifact is absent.** The eval README lists it,
   while strong component tests exist. A realistic unauthorized-to-approved
   journey and no-AI/no-storage proof should be captured as acceptance evidence.
8. **Cross-domain unchanged journeys are manual.** Shared router changes should
   prove at least one unchanged invoice, accounting, contact and work-time path
   through the real public owner.
9. **No measured coverage report.** This audit did not install a coverage plugin;
   path/test evidence identifies contract gaps, but line/branch coverage remains
   unknown.
10. **Server smoke is documentary, not a suite tier.** Production evidence exists
    in logs/eval artifacts, but there is no safe, redacted, opt-in server-smoke
    harness with a stable result format.

## 12. Proposed pytest markers and execution tiers

Markers should describe test level and risk, not duplicate every product
domain. Proposed registered markers:

```text
unit              deterministic isolated logic
contract          bounded schema/registry/authority contract
integration       real temporary DB/files/process or several real components
acceptance        public-entry user journey with final state/effect/keyboard
server_smoke      opt-in deployed-runtime read-only/bounded smoke
external          opt-in real third-party boundary; never ordinary PR default
regression        named previously fixed failure
migration         persisted-data compatibility/apply/rollback
workspace         authorization or tenant/workspace isolation
callback          callback ownership/stale/idempotency lifecycle
slow              measured threshold, proposed >= 1.0s call or costly group
```

Proposed tiers:

| Tier | Purpose | Selection |
|---|---|---|
| Focused | Changed component during development | Exact file/node IDs documented beside component ownership |
| Adjacent | Neighboring router/FSM/service/Product Truth regressions | Maintained adjacency map in testing docs; explicit file list |
| Full Python | Mandatory PR validation | `python -m pytest -q` |
| Integration | Real temp SQLite/files/process boundaries | `python -m pytest -q -m integration` |
| Acceptance | Public-route deterministic user journeys | `python -m pytest -q -m acceptance` |
| External | Controlled provider contract smoke | `python -m pytest -q -m external`; opt-in credentials and redaction |
| Server smoke | Post-deploy bounded checks | `python -m pytest -q -m server_smoke`; never run against production by default |

Marker addition must not deselect tests from the full default suite. CI design
is a future decision because no workflow exists on this baseline.

## 13. Recommended phased cleanup plan

### Phase 1 — taxonomy and documentation only

- register markers and document focused/adjacent ownership;
- add a shared duration/JUnit command and baseline artifact convention;
- do not change test behavior or collected count.

### Phase 2 — high-confidence parametrization

- implement only the high-confidence matrices in section 6;
- preserve scenario IDs in pytest output;
- compare pre/post node inventory and require every old behavior to map to a
  new row.

### Phase 3 — isolate legacy/unclear coverage

- obtain the owner decision on service-account Drive mode and legacy schema
  support horizons;
- label legacy tests; do not remove them yet;
- collect read-only deployment evidence before declaring compatibility dead.

### Phase 4 — rewrite brittle implementation coupling

- centralize architecture import rules;
- add behavior-level no-network/no-side-effect assertions;
- add representative dispatcher acceptance tests before reducing patched
  routing shells.

### Phase 5 — approved obsolete removal only

- remove only behavior explicitly declared unsupported and unused;
- identify the exact surviving test or replacement first;
- run focused, adjacent, full, integration and applicable acceptance tiers;
- record Product Truth, migration and rollback decisions.

## 14. Risks and rollback strategy

Consolidation can accidentally erase language, state, callback, workspace,
error-path or historical-bug identity even when code bodies look similar.
Parametrization can make failures harder to diagnose if IDs are weak. Shared
fixtures can leak mutable globals or make setup too magical. Moving source
guards can weaken architecture enforcement. Removing legacy tests can strand
persisted deployments.

For each future phase:

1. capture `pytest --collect-only -q` before and after;
2. map every removed node ID to a parametrized ID or explicit replacement;
3. keep a baseline JUnit timing artifact;
4. commit one candidate group at a time;
5. run focused and adjacent sets, then the full suite;
6. revert the phase commit if behavior mapping or runtime evidence is unclear;
7. never combine Product Truth retirement, migration and test deletion in an
   unreviewable patch.

This audit itself is documentation-only and rolls back by reverting its single
documentation commit.

## 15. Commands used and observed results

| Command | Result |
|---|---|
| `git fetch origin main` | Fetched latest `origin/main` |
| `git worktree add -b audit/fakturabot-test-suite ... origin/main` | Isolated branch at `4a69b31` |
| `python -m pytest --collect-only -q` | 2,433 collected in 6.09s |
| collection grouped by file | 101 files; every `test_*.py` collected at least one case |
| `python -m pytest -q --durations=100 --durations-min=0.01` | 2,433 passed, 7 subtests passed in 467.17s |
| `python -m pytest -q --junitxml=...` | 2,433 passed, 7 subtests passed in 485.03s |
| three repeats of five stateful modules | 123 passed each in 57.67s, 58.58s, 57.74s |
| same five modules in reverse file order | 123 passed in 57.65s |
| AST exact/constant-normalized body comparison | Found exact Google Product Truth triplicate and candidate scenario shells; every recommendation manually compared |
| `git log ... -- tests` and focused `PROJECT_LOG.md` searches | Established recent regression provenance and two historical transient candidates |

No package was installed. No live external service, Telegram, server,
production database, storage, deployment or CI job was touched.

## 16. Unresolved product-owner questions

1. Is `GOOGLE_DRIVE_MODE=service_account` still supported for any current
   Shared Drive/legacy deployment, or may it be formally retired from Product
   Truth and runtime in a separate approved task?
2. What is the support horizon for pre-workspace, pre-IBAN, SMTP-not-null and
   legacy callback/state data? Tests cannot be retired without that decision
   and a read-only production inventory.
3. Should contact lookup/monitor keyboard lifecycle gaps be repaired before any
   test-structure cleanup?
4. Where should CI live, and must the full 8-minute suite run on every PR?
5. Which controlled environment may run real Gmail OAuth/callback/mailbox and
   Google Drive smoke, and who owns credentials and redaction review?
6. Should PDF visual review become a required checked artifact or remain a
   manual release gate?
7. What small set of public dispatcher journeys should become mandatory
   acceptance tests across invoice, accounting, contact and work-time domains?
8. Is an 8-minute local full-suite budget acceptable, or should a future phase
   optimize repeated SQLite bootstrap while keeping full PR validation?

Until these questions are answered, legacy and externally unproven tests stay
protected rather than deleted.
