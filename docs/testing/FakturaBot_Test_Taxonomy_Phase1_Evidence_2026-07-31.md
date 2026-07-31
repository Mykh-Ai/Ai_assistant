# FakturaBot Test Taxonomy Phase 1 Evidence

Date: 2026-07-31
Baseline: origin/main 4a69b312226b7c4254427f3c3c1b0a99243647c8
Branch: test/fakturabot-taxonomy-phase1
Status: implemented and locally validated; not merged or deployed

## Scope and result

This phase registers the approved pytest taxonomy, documents execution tiers,
parametrizes only the six high-confidence groups approved by the audit, moves
three literal Product Truth copies to one canonical owner, and centralizes ten
equivalent source import-boundary checks.

No production code, Product Truth value, application behavior, database
schema, dependency, runtime configuration, CI workflow, server, credential,
or production data was changed.

Pre-change collection was 2,433 nodes. Post-change collection is 2,431 nodes.
The two-node reduction is exactly the consolidation of three literal Product
Truth copies into one canonical node. The 38 approved parametrized scenarios
and ten architecture-boundary scenarios remain individually collected. The
suite therefore retains 2,431 unique logical protections before and after this
phase.

## Marker registration

Registered markers: unit, contract, integration, acceptance, server_smoke,
external, regression, migration, workspace, callback, and slow.

Marker registration does not change default selection. Classification remains
partial and is applied in this phase only to the changed tests where the level
or regression status is high-confidence.

## Preservation accounting

| Group | Old collected nodes | New collected nodes | Unique behaviors before / after |
| --- | ---: | ---: | ---: |
| Pay by Square invalid fields | 5 | 5 | 5 / 5 |
| Service-term normalization | 3 | 3 | 3 / 3 |
| Work-time top-level routing | 4 | 4 | 4 / 4 |
| Contact normalization | 4 | 4 | 4 / 4 |
| Invoice analytics resolver phrases | 16 | 16 | 16 / 16 |
| Customization admin middleware | 6 | 6 | 6 / 6 |
| Google Drive Product Truth literal copies | 3 | 1 | 1 / 1 |
| Architecture import boundaries | 10 | 10 | 10 / 10 |
| Total touched | 51 | 49 | 49 / 49 |

## Exact old-to-new node mapping

### Pay by Square

| Old node ID | New node ID | Protected behavior |
| --- | --- | --- |
| tests/test_pay_by_square.py::PayBySquareTests::test_invalid_iban_raises | tests/test_pay_by_square.py::test_invalid_payment_field_raises[invalid-iban] | INVALID IBAN raises PayBySquareValidationError. |
| tests/test_pay_by_square.py::PayBySquareTests::test_invalid_currency_raises | tests/test_pay_by_square.py::test_invalid_payment_field_raises[invalid-currency] | EURO currency raises PayBySquareValidationError. |
| tests/test_pay_by_square.py::PayBySquareTests::test_invalid_variable_symbol_raises | tests/test_pay_by_square.py::test_invalid_payment_field_raises[invalid-variable-symbol] | Alphanumeric variable symbol raises PayBySquareValidationError. |
| tests/test_pay_by_square.py::PayBySquareTests::test_empty_beneficiary_name_raises | tests/test_pay_by_square.py::test_invalid_payment_field_raises[empty-beneficiary-name] | Whitespace beneficiary name raises PayBySquareValidationError. |
| tests/test_pay_by_square.py::PayBySquareTests::test_invalid_amount_raises | tests/test_pay_by_square.py::test_invalid_payment_field_raises[invalid-amount] | Zero amount raises PayBySquareValidationError. |

### Service-term normalization

| Old node ID | New node ID | Protected behavior |
| --- | --- | --- |
| tests/test_service_term_normalizer.py::test_normalize_opravy | tests/test_service_term_normalizer.py::test_normalize_service_term[slovak-plural-opravy] | Slovak plural opravy normalizes to oprava. |
| tests/test_service_term_normalizer.py::test_normalize_remont_ru | tests/test_service_term_normalizer.py::test_normalize_service_term[russian-remont] | Russian `\\u0440\\u0435\\u043c\\u043e\\u043d\\u0442` normalizes to oprava. |
| tests/test_service_term_normalizer.py::test_normalize_montazh_ru | tests/test_service_term_normalizer.py::test_normalize_service_term[russian-montazh] | Russian `\\u043c\\u043e\\u043d\\u0442\\u0430\\u0436` normalizes to `mont\\u00e1\\u017e`. |

### Work-time routing

| Old node ID | New node ID | Protected behavior |
| --- | --- | --- |
| tests/test_work_time_routing.py::test_top_level_work_time_open_routes_from_slovak_text | tests/test_work_time_routing.py::test_top_level_work_time_action_routes_from_text[open-slovak-text] | Slovak open-day text resolves to open_work_day. |
| tests/test_work_time_routing.py::test_top_level_work_time_close_routes_from_slovak_text | tests/test_work_time_routing.py::test_top_level_work_time_action_routes_from_text[close-slovak-text] | Slovak close-day text resolves to close_work_day. |
| tests/test_work_time_routing.py::test_top_level_work_time_manual_range_routes_from_text | tests/test_work_time_routing.py::test_top_level_work_time_action_routes_from_text[manual-range-slovak-text] | Manual time range resolves to add_work_time_entry. |
| tests/test_work_time_routing.py::test_top_level_work_time_report_routes_from_month_request | tests/test_work_time_routing.py::test_top_level_work_time_action_routes_from_text[report-month-slovak-text] | Month report request resolves to generate_work_time_report. |

### Contact normalization

| Old node ID | New node ID | Protected behavior |
| --- | --- | --- |
| tests/test_contact_lookup_normalization.py::test_legal_suffix_sro_variant_match | tests/test_contact_lookup_normalization.py::test_normalized_contact_variant_match[legal-suffix-sro] | Saved name, query variant, normalized_match state, and exact saved name are preserved. |
| tests/test_contact_lookup_normalization.py::test_legal_suffix_spaced_variant_match | tests/test_contact_lookup_normalization.py::test_normalized_contact_variant_match[legal-suffix-spaced] | Spaced legal suffix resolves to the exact saved contact. |
| tests/test_contact_lookup_normalization.py::test_separator_insensitive_match_hyphen | tests/test_contact_lookup_normalization.py::test_normalized_contact_variant_match[separator-hyphen] | Hyphen-insensitive query resolves to the exact saved contact. |
| tests/test_contact_lookup_normalization.py::test_separator_insensitive_match_spaces | tests/test_contact_lookup_normalization.py::test_normalized_contact_variant_match[separator-spaces] | Space-separated query resolves to the exact saved contact. |

### Invoice analytics intent phrases

Old yearly node prefix:
tests/test_invoice_intent_prerouter.py::test_yearly_invoice_summary_resolves_to_invoice_analytics_top_level_action

Old general node prefix:
tests/test_invoice_intent_prerouter.py::test_invoice_analytics_resolves_as_read_only_top_level_action

All replacements use:
tests/test_invoice_intent_prerouter.py::test_invoice_analytics_resolves_as_read_only_top_level_action

| Old prefix and exact input | New scenario ID | Protected behavior |
| --- | --- | --- |
| yearly source index 0 (`YEARLY_INVOICE_ANALYTICS_INPUTS[0]`) | yearly-sk-total-current-year | Exact preserved Slovak current-year-total input routes read-only to invoice_analytics. |
| yearly source index 1 (`YEARLY_INVOICE_ANALYTICS_INPUTS[1]`) | yearly-sk-count-current-year | Exact preserved Slovak current-year-count input. |
| yearly source index 2 (`YEARLY_INVOICE_ANALYTICS_INPUTS[2]`) | yearly-sk-summary-explicit-year | Exact preserved Slovak explicit-year-summary input. |
| yearly source index 3 (`YEARLY_INVOICE_ANALYTICS_INPUTS[3]`) | yearly-uk-total-current-year | Exact preserved Ukrainian current-year-total input. |
| yearly source index 4 (`YEARLY_INVOICE_ANALYTICS_INPUTS[4]`) | yearly-uk-count-current-year | Exact preserved Ukrainian current-year-count input. |
| yearly source index 5 (`YEARLY_INVOICE_ANALYTICS_INPUTS[5]`) | yearly-uk-total-already-current-year | Exact preserved Ukrainian already-issued current-year-total input. |
| yearly source index 6 (`YEARLY_INVOICE_ANALYTICS_INPUTS[6]`) | yearly-ru-total-current-year | Exact preserved Russian current-year-total input. |
| yearly source index 7 (`YEARLY_INVOICE_ANALYTICS_INPUTS[7]`) | yearly-be-total-current-year | Exact preserved Belarusian current-year-total input. |
| general source index 0 (`GENERAL_INVOICE_ANALYTICS_INPUTS[0]`) | general-uk-show-month | Exact preserved Ukrainian month query. |
| general source index 1 (`GENERAL_INVOICE_ANALYTICS_INPUTS[1]`) | general-uk-total-two-months | Exact preserved Ukrainian two-month-total input. |
| general source index 2 (`GENERAL_INVOICE_ANALYTICS_INPUTS[2]`) | general-sk-count-two-months | Exact preserved Slovak two-month-count input. |
| general source index 3 (`GENERAL_INVOICE_ANALYTICS_INPUTS[3]`) | general-sk-compare-two-months | Exact preserved Slovak month-comparison input. |
| general source index 4 (`GENERAL_INVOICE_ANALYTICS_INPUTS[4]`) | general-uk-total-by-month | Exact preserved Ukrainian totals-by-month input. |
| general source index 5 (`GENERAL_INVOICE_ANALYTICS_INPUTS[5]`) | general-uk-compare-same-month-two-years | Exact preserved Ukrainian year-over-year comparison input. |
| general source index 6 (`GENERAL_INVOICE_ANALYTICS_INPUTS[6]`) | general-sk-unpaid-count | Exact preserved Slovak unpaid-count input. |
| general source index 7 (`GENERAL_INVOICE_ANALYTICS_INPUTS[7]`) | general-sk-top-customers-by-total | Exact preserved Slovak top-customers-by-total input. |

### Customization admin authorization

| Old node ID | New node ID | Protected behavior |
| --- | --- | --- |
| tests/test_customization_request_admin.py::test_bootstrap_admin_command_passes_middleware_without_user_access | tests/test_customization_request_admin.py::test_bootstrap_admin_customization_command_passes_middleware_without_user_access[list] | Bootstrap admin list command passes middleware; no denial reply. |
| tests/test_customization_request_admin.py::test_bootstrap_admin_detail_command_passes_middleware_without_user_access | tests/test_customization_request_admin.py::test_bootstrap_admin_customization_command_passes_middleware_without_user_access[detail] | Bootstrap admin detail command passes independently. |
| tests/test_customization_request_admin.py::test_bootstrap_admin_reply_command_passes_middleware_without_user_access | tests/test_customization_request_admin.py::test_bootstrap_admin_customization_command_passes_middleware_without_user_access[reply] | Bootstrap admin reply command passes independently. |
| tests/test_customization_request_admin.py::test_unauthorized_user_is_blocked_by_middleware_for_customization_requests | tests/test_customization_request_admin.py::test_unauthorized_user_is_blocked_by_middleware_for_customization_command[list] | Unknown list actor is blocked, state cleared, and one denial is sent. |
| tests/test_customization_request_admin.py::test_unauthorized_user_is_blocked_by_middleware_for_customization_request_detail | tests/test_customization_request_admin.py::test_unauthorized_user_is_blocked_by_middleware_for_customization_command[detail] | Unknown detail actor is independently blocked. |
| tests/test_customization_request_admin.py::test_unauthorized_user_is_blocked_by_middleware_for_customization_request_reply | tests/test_customization_request_admin.py::test_unauthorized_user_is_blocked_by_middleware_for_customization_command[reply] | Unknown reply actor is independently blocked. |

### Google Drive Product Truth

| Old node ID | Canonical replacement | Protected behavior |
| --- | --- | --- |
| tests/test_google_drive_oauth_callback_service.py::test_google_drive_product_truth_is_partial_service_account_not_oauth | tests/test_product_truth.py::test_google_drive_invoice_storage_product_truth_is_partial_owner_oauth | Capability exists, status is partial, runtime owner exists, and English guidance exists. |
| tests/test_google_drive_oauth_state_service.py::test_google_drive_product_truth_is_partial_service_account_not_oauth | tests/test_product_truth.py::test_google_drive_invoice_storage_product_truth_is_partial_owner_oauth | Literal same four assertions and same failure modes. |
| tests/test_google_drive_setup_commands.py::test_google_drive_product_truth_is_partial_service_account_not_oauth | tests/test_product_truth.py::test_google_drive_invoice_storage_product_truth_is_partial_owner_oauth | Literal same four assertions and same failure modes. |

Inspection proof: the canonical replacement directly asserts
ProductTruthStatus.PARTIAL and a non-null runtime owner. An intentionally
incorrect status value therefore fails the equality assertion. No temporary
Product Truth or production-code mutation was used or committed.

### Architecture import boundaries

Every replacement is a row of
tests/test_architecture_import_boundaries.py::test_module_import_boundary.

| Old node ID | New scenario ID | Protected module / boundary |
| --- | --- | --- |
| tests/test_accounting_document_archive_service.py::test_accounting_archive_service_has_no_google_or_network_imports | accounting-archive-service | bot.services.accounting_document_archive_service; original five-token set. |
| tests/test_accounting_original_cleanup_service.py::test_cleanup_service_has_no_google_or_network_imports | accounting-original-cleanup-service | bot.services.accounting_original_cleanup_service; original six-token set. |
| tests/test_archive_job_service.py::test_archive_job_service_has_no_google_or_network_imports | archive-job-service | bot.services.archive_job_service; original five-token set. |
| tests/test_archive_worker.py::test_archive_worker_has_no_google_or_network_runtime_imports | archive-worker | bot.services.archive_worker; original six-token set plus required claim_next_runnable_job token. |
| tests/test_google_drive_connection_service.py::test_google_drive_connection_service_has_no_google_or_network_imports | google-drive-connection-service | bot.services.google_drive_connection_service; original six-token set. |
| tests/test_google_drive_oauth_state_service.py::test_oauth_state_service_has_no_google_or_network_imports | google-drive-oauth-state-service | bot.services.google_drive_oauth_state_service; original six-token set. |
| tests/test_google_drive_oauth_callback_service.py::test_oauth_callback_service_has_no_google_or_network_imports | google-drive-oauth-callback-service | bot.services.google_drive_oauth_callback_service; original six-token set. |
| tests/test_google_drive_setup_commands.py::test_google_drive_setup_commands_have_no_google_api_or_network_imports | google-drive-setup-commands | bot.handlers.settings; original six-token set. |
| tests/test_google_oauth_token_exchanger.py::test_token_exchanger_module_has_no_google_client_or_drive_upload_imports | google-oauth-token-exchanger | bot.services.google_oauth_token_exchanger; original module-specific five-token set. |
| tests/test_token_crypto.py::test_token_crypto_has_no_google_or_network_imports | token-crypto | bot.services.token_crypto; original six-token set. |

The centralized failure message identifies the module and exact violating
tokens. No forbidden set was broadened or weakened.

Independent source contracts were not merged: local-confirmation-parser,
callback-runtime-wiring, work-time phrase-dictionary, Product Truth/InfoHelp
runtime-side-effect, and other module-specific source assertions remain in
their owners because their semantics are not equivalent.

## Validation

| Command | Result |
| --- | --- |
| python -m pytest --collect-only -q, before | 2,433 collected in 7.00s |
| python -m pytest -q --durations=25, before | 2,433 passed, 7 subtests passed in 490.38s |
| changed-file focused set | 431 passed in 116.83s |
| DecisionResolver/InfoHelp/Google/OAuth/crypto/archive adjacent set | 949 passed in 26.84s |
| FSM/voice/work-time/contact/workspace/access adjacent set | 210 passed, 7 subtests passed in 72.40s |
| python -m pytest --collect-only -q, after | 2,431 collected in 3.67s on the final tree |
| python -m pytest -q -m unit or contract | 49 passed, 2,382 deselected in 9.39s |
| python -m pytest -q --durations=25, after | 2,431 passed, 7 subtests passed in 490.10s |

## Deferred and unchanged

- Delivery-date parametrization in tests/test_invoice_phase2_ai_layer.py remains
  unchanged for a dedicated review of date, local-year, stale/future, and
  multilingual regression semantics.
- Legacy service-account tests in
  tests/test_google_drive_service_account_archive.py remain unchanged. No
  retirement or Product Truth decision was inferred.
- No high-confidence approved candidate was left unimplemented.
- No acceptance, external, or server-smoke completeness is claimed.

Rollback is one test-maintenance commit: revert it to restore every prior node
shape. No data or runtime rollback is applicable.
