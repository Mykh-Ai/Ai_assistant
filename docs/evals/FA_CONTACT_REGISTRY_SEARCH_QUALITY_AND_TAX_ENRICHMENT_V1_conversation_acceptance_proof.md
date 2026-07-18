# FA_CONTACT_REGISTRY_SEARCH_QUALITY_AND_TAX_ENRICHMENT_V1 Conversation Acceptance Proof

Verdict: `safe_to_review`

This is the final local evidence record for the user-authorized implementation slice. Search quality, fake-backed tax/FSM behavior, and the exact production Financial Administration schema mapping are proven. `safe_to_review` is not permission to commit, push, migrate, restart, enable, or deploy.

## Evidence boundary

- Architecture: `docs/architecture/FA_CONTACT_REGISTRY_SEARCH_QUALITY_AND_TAX_ENRICHMENT_V1_ARCHITECTURE_DESIGN_PROOF.md`; verdict `ready_for_handoff`.
- Baseline before this task: `main` at `692eebb89e17937f032d13f87e3e833bf700d472` with protected local modifications in `PROJECT_LOG.md` and `tests/test_access_workspace_reactivation.py`.
- Runtime changes: deterministic RPO ranking/filtering; exact-vs-suggested candidate metadata; strict suggestion selection; disabled tax config; async tax provider/aggregation owner; detail enrichment/fallback; bounded source metadata.
- Automated tests use synthetic RPO/tax payloads and local temporary SQLite only. They do not call the internet.
- An authorized key was installed securely in `/bot/repo/.env`. After correcting a one-character local transfer corruption, authenticated `/api/lists`, list-detail, exact-IČO, current DPH-page, and no-result calls completed without printing the key or raw taxpayer values. `verified_financna_sprava_schema()` now binds the audited mappings.
- During implementation proof no production Telegram, DB/storage, migration, restart, code deployment, feature activation, commit, or push action occurred. A later explicitly approved post-handoff deployment is recorded below.

## Scenario 1: exact Zevs search

- Public entry: shared `start_add_contact_intake` -> `contact_name_hint`.
- Input: `Zevs s.r.o.`.
- Fake RPO response: exact `Zevs s. r. o.` below four observed surname/substring rows.
- Observed owner: `SlovakCompanyRegistry.search` normalizes/ranks/filters; handler receives one `match_kind=exact_name` result and loads detail.
- State: `name_hint` -> `registry_detail_preview`.
- Output: only Zevs official name, IČO `56055552`, and `Bratislava - mestská časť Rača`; no candidate noise.
- Side effect: zero contact rows before confirmation.
- Evidence: `test_exact_zevs_search_suppresses_noise_and_opens_detail_without_write`; pass.

## Scenario 2: bounded non-exact suggestions

- Inputs: `Empbau` and `ZE VS`.
- Observed: `Empbau` retains both `Empebau` and `Empe bau` as `suggested`; `ZE VS` may retain `Zevs` as `suggested`.
- Exactness: compact spacing/one-edit similarity never upgrades a suggestion to identity.
- State: one suggestion remains `registry_candidates`; detail is not fetched until its bounded button is selected.
- Negative space: `zevs` inside `Klimaszevská` is rejected; all weak results use the existing no-result/manual fallback.
- Evidence: service ranking tests and `test_soft_single_result_requires_selection_but_two_exact_names_remain_listed`; pass.

## Scenario 3: ambiguous exact name

- Input: `Same Name sro`.
- Fake response: two exact normalized active legal entities.
- State: `name_hint` -> `registry_candidates`; no auto-selection.
- Output: both names with IČO and municipality.
- Side effect: no detail/tax/DB call before selection.
- Evidence: `test_two_exact_name_companies_remain_selectable_active_first` and handler scenario; pass.

## Scenario 4: fake-backed DIČ enrichment

- Precondition: existing registry/pilot gate enabled; tax feature enabled in synthetic config; injected tax fake.
- Selected RPO identity: IČO `56055552`.
- Tax result: exact same IČO with validated DIČ `2122222222`, no VAT row.
- State/output: combined detail preview shows DIČ, IČ DPH `-`, and `slovak_rpo + financna_sprava`; `supplement` skips `registry_required_dic` and enters optional email.
- Persistence: zero rows through preview; final shared confirmation writes once with `source_type=registry` and `source_note=slovak_rpo+financna_sprava`.
- Rate/idempotency: one tax lookup for the selected IČO; save/final confirmation does not repeat it.
- Evidence: `test_tax_enrichment_skips_typed_dic_and_does_not_repeat_on_save`; pass with fake provider.

## Scenario 5: no VAT result

- Income list fake returns exact validated DIČ; VAT list fake returns no row.
- Output: DIČ retained, IČ DPH null, `is_vat_registered=None`.
- Forbidden behavior: no `SK + DIČ` creation and no non-VAT overclaim.
- Evidence: `test_missing_vat_result_keeps_ic_dph_null_without_inference`; pass.

## Scenario 6: tax provider failure

- Fake provider outcome: `tax_registry_unavailable` (timeout/status failures are separately unit-mapped).
- Observed: selected RPO detail remains; source stays `slovak_rpo`; DIČ/IČ DPH remain empty; `supplement` enters `registry_required_dic`.
- Side effect: zero DB writes; no stack trace/raw response/key in output.
- Evidence: `test_tax_failure_retains_rpo_and_enters_typed_dic`; pass.

## Provider and safety matrix

Fake-backed passing coverage includes:

- exact IČO DIČ and official IČ DPH;
- no VAT result and no inference;
- name-only/wrong-IČO rejection;
- invalid/conflicting DIČ or IČ DPH fail closed;
- disabled, missing key, and missing verified schema make zero calls;
- 401/403 -> unauthorized, 429 -> rate-limited, 500/503/timeout -> unavailable;
- malformed JSON, oversized body, unexpected envelope/row shape, and truncated pagination fail closed;
- key appears only in the request header and not error/log text;
- aggregator preserves RPO on tax failure;
- exact RPO IČO is the only tax lookup key.

## Regression evidence

The task run executed the existing registry/contact completion suite, broad contact/workspace/invoice/callback/voice/state/migration/Product Truth regression, full `python -m pytest -q`, compileall, and diff checks. Manual/PDF fallback, access/tenant guards, stale/wrong callback behavior, and migration invariants remain unchanged by design.

## Local verification completed

- `python -m pytest -q tests\test_contact_registry_flow.py tests\test_contact_registry_services.py tests\test_slovak_tax_registry.py tests\test_contact_registry_truth.py tests\test_contact_iban_migration.py tests\test_contact_intake_semantic_flow.py tests\test_workspace_contact_service.py tests\test_contact_lookup_normalization.py tests\test_invoice_contact_lookup_feedback.py` -> final post-audit result `108 passed in 36.44s`.
- Broad contact/workspace/invoice/callback/voice/state/migration/Product Truth regression command recorded in the task report -> `803 passed in 181.15s`.
- Expanded exact command: `python -m pytest -q tests\test_access_workspace_reactivation.py tests\test_accounting_document_drive_workspace_isolation.py tests\test_contact_iban_migration.py tests\test_contact_intake_semantic_flow.py tests\test_contact_lookup_normalization.py tests\test_contact_registry_flow.py tests\test_contact_registry_services.py tests\test_contact_registry_truth.py tests\test_decision_callbacks.py tests\test_google_drive_oauth_callback_app.py tests\test_google_drive_oauth_callback_service.py tests\test_google_drive_oauth_state_service.py tests\test_info_help.py tests\test_invoice_analytics_answerer.py tests\test_invoice_analytics_dataset.py tests\test_invoice_analytics_planner.py tests\test_invoice_contact_lookup_feedback.py tests\test_invoice_followup_handler.py tests\test_invoice_followup_service.py tests\test_invoice_intent_prerouter.py tests\test_invoice_phase2_ai_layer.py tests\test_invoice_service_display_resolution.py tests\test_invoice_service_item_normalized.py tests\test_invoice_state_decisions.py tests\test_multi_workspace_migration.py tests\test_multi_workspace_migration_apply.py tests\test_product_truth.py tests\test_state_control.py tests\test_voice_state_routing.py tests\test_workspace_contact_service.py tests\test_workspace_context.py tests\test_workspace_invoice_followup_service.py tests\test_workspace_invoice_service.py tests\test_workspace_profile_service.py` -> `858 passed, 1 failed in 203.41s`; the sole failure and successful isolated rerun are explained below.
- A later expanded explicit 34-file broad rerun reached `858 passed` and one pre-existing Windows filesystem-lock failure in `test_apply_backup_post_audit_and_rollback_round_trip` (`os.replace`, `WinError 5`); the exact isolated rerun `python -m pytest -q tests\test_multi_workspace_migration_apply.py::test_apply_backup_post_audit_and_rollback_round_trip` then passed (`1 passed in 1.52s`).
- `python -m pytest -q` -> final post-audit result `2244 passed, 7 subtests passed in 338.16s`.
- `python -m compileall -q bot` -> pass.
- Automated tests remain fake/local. The separate bounded live read-only audit returned 200 for authenticated metadata and observed exact matches, 404 for no-result searches in both approved lists, and confirmed direct official IČ DPH representation without logging raw values.

Post-handoff deployment completed at commit `e63127b`: clean fast-forward, verified DB/env/storage/image rollback point, `CONTACT_TAX_LOOKUP_ENABLED=1`, timeout 5, container rebuild/restart, healthy polling, exact runtime config/mapping checks, live tax lookup with validated DIČ/no inferred IČ DPH, live exact RPO search/detail, zero log errors, SQLite integrity `ok`, and unchanged counts (3 contacts, 9 invoices, 3 workspaces). The controlled parent workspace gate remains active. Telegram conversation acceptance is still pending, so this remains `safe_to_review` evidence rather than a general `safe_to_deploy` claim.
