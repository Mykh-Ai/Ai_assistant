# Runtime Issue Workshop Bridge Phase 1 — Acceptance Proof

Verdict: `safe_to_review`

Baseline: `026ed15b5eeec9d65182164cba734e78b11b17ff`

Branch: `feat/runtime-issue-workshop-bridge-phase1`

Approved Architecture Design Proof:
`docs/features/runtime_issue_autorepair_v1/01_ARCHITECTURE_DESIGN_PROOF.md`
(`ready_for_handoff`).

## Scope and boundaries

Real repository boundaries exercised:

- additive SQLite bootstrap and strict owned-schema audit;
- atomic SQLite lease/redelivery/ack transitions;
- canonical UTF-8 JSON digest;
- workshop queue/log filesystem bootstrap.

Mocked boundaries:

- remote workshop branch/commit verification;
- bounded Docker log source;
- recorded STT/network/provider facts.

Not run or not authorized:

- production database migration;
- SSH/server access;
- real Docker, GitHub, Telegram, OpenAI, STT, provider, or Internet smoke;
- nightly Work scheduling;
- diagnosis, findings, repair branches, notifications;
- merge, deploy, restart, rollback, or production data mutation.

## Acceptance mapping

| Contract area | Named evidence |
|---|---|
| additive/idempotent schema and strict compatibility | `test_additive_idempotent_schema_and_unknown_optional_column`, `test_incompatible_owned_schema_fails_closed`, `test_incompatible_default_or_unique_constraint_fails_closed`, `test_missing_or_incompatible_owned_index_fails_closed` |
| migration immutability | `test_bootstrap_preserves_existing_schema_rows_and_identifiers`, `test_bootstrap_preserves_all_preexisting_objects_and_rows` |
| oldest-first, bounded atomic lease | `test_take_next_oldest_first_limit_empty_and_no_stage1_mutation`, `test_limit_is_hard_bounded`, `test_concurrent_workers_do_not_lease_same_issue` |
| crash/redelivery/stable receipt | `test_redelivery_stable_receipt_new_token_and_old_token_cannot_ack` |
| canonical digest | `test_canonical_digest_contract` |
| verified/idempotent/fail-closed ack | `test_ack_requires_verified_receipt_and_is_idempotent`, `test_ack_rejections_fail_without_canonical_mutation`, `test_conflicting_repeat_and_reserved_reconciled_unreachable` |
| bounded remote receipt verification | `test_fixed_remote_verifier_uses_bounded_exact_branch_read`, `test_fixed_remote_verifier_fails_closed_when_remote_is_unavailable` |
| null/active/read-failed FSM evidence | `test_fsm_status_null_active_and_read_failed` |
| stdin-only token and bounded JSON CLI | `test_ack_parser_has_no_argv_token_value_option`, `test_stdin_token_is_strict_and_error_never_exposes_value`, `test_ack_output_never_contains_raw_token`, `test_take_next_stdout_is_only_json` |
| bounded truthful evidence | `test_collects_correlated_categories_and_global_docker_fact`, `test_missing_evidence_is_truthful_and_null_workspace_is_valid`, `test_source_error_is_bounded`, `test_unacknowledged_and_cross_issue_fail_closed`, `test_excerpt_item_and_input_limits` |
| idempotent fail-closed workshop bootstrap | `test_absent_directory_creates_exact_empty_seed_and_repeats_idempotently`, `test_valid_nonempty_workshop_is_preserved`, `test_incompatible_file_fails_closed_without_overwrite` |

## Migration and immutability proof

Temporary tests create a fresh database, repeat bootstrap, tolerate an unknown
optional column, reject missing/type/default/check/unique/index
incompatibility, and preserve all pre-existing table/index/trigger definitions,
identifiers, row counts, and row values. Handoff tests compare all Stage 1 rows
before and after selection.
There is no drop, rebuild, copy, backfill, business-data update, or production
database access.

## Public conversation proof

`not_applicable`: Phase 1 creates no Telegram action, route, FSM, callback,
confirmation, button, or user-facing capability. Existing Stage 1 conversation
proof remains authoritative. Product Truth and InfoHelp are intentionally
unchanged because the bridge is neither deployed nor activated and no nightly
or notification path exists.

## Verification record

- Focused bridge suites:
  `python -m pytest -q tests/test_runtime_issue_handoff.py
  tests/test_runtime_issue_bridge_cli.py tests/test_runtime_issue_evidence.py
  tests/test_runtime_issue_workshop.py` -> `45 passed in 3.43s`.
- Required adjacent set -> `282 passed in 12.06s`.
- Full repository suite -> `2332 passed, 7 subtests passed in 81.97s`.
- `python -m compileall -q bot` -> passed.
- `git diff --check` -> passed.
- Repository-internal Markdown link check -> passed, zero missing targets.
- Canonical queue schema and workshop queue JSON parsing -> passed.
- Final diff secret/private-path scan -> passed; only explicit synthetic
  redaction fixtures are present in tests.
- Real server/external smoke was not run and is not authorized. Remote Git and
  Docker boundaries are fake-tested; STT/network/provider facts use recorded
  fake sources.

Design-to-code variance: `none_identified`.

Final implementation verdict: `safe_to_review`. This is not a deployment,
activation, migration, scheduling, diagnosis, repair, or notification verdict.
