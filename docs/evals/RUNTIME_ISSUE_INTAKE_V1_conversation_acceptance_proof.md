# Runtime Issue Intake V1 — Conversation Acceptance Proof

Task: `RUNTIME_ISSUE_INTAKE_V1`

Approved Architecture Design Proof:
`docs/features/runtime_issue_autorepair_v1/01_ARCHITECTURE_DESIGN_PROOF.md`

Authoritative implementation handoff:
`docs/features/runtime_issue_autorepair_v1/06_IMPLEMENTATION_HANDOFF.md`

Evidence state: PR #50 correction worktree on
`feat/runtime-issue-intake-v1`, based on implementation commit
`2f08f3faf5b0500e119aae434061a5c2413c23c0`. No production, server,
deployment, or production-database boundary was used.

## Environment and evidence boundaries

Real boundaries exercised:

- public Python command handler `cmd_runtime_issue`;
- public idle text owner `semantic_top_level_input` and
  `process_invoice_text`;
- public voice handler `handle_voice`;
- shared active-FSM text/voice guard;
- explicit admin authorization owner;
- read-only workspace resolver;
- shared capture handler, deterministic sanitizer, and title derivation;
- real temporary-file SQLite bootstrap, schema audit, transactions,
  deduplication, rollback, reads, and row mapping;
- Product Truth and InfoHelp Python registries;
- unchanged callback, authorization, workspace, state-control, invoice
  pre-router, follow-up, text, and voice suites.

Mocked boundaries:

- bounded LLM action decisions use deterministic async fakes that return only
  an allowed canonical token and expose the actual allowed-action/hint payload;
- STT returns a controlled transcript;
- Telegram file download and message delivery use local fakes;
- Telegram `Update.update_id` is supplied as the trusted aiogram dispatcher
  dependency. Read-only design verification inspected the installed supported
  aiogram dispatcher source and confirmed that `feed_update` injects the
  original `event_update`; no ID is synthesized from content;
- external OpenAI, Telegram, and provider networks are disabled.

Tests not run: no manual Telegram acceptance and no production migration,
deployment, restart, server smoke, or external-service smoke. None is required
to prove this repository-only Stage 1 change. Stage 2 scenarios B–D were not
run or implemented.

## Public-entry traces

### Command

- Precondition: configured administrator, trusted Telegram update/message/chat,
  idle or active business state.
- Input: `/issue Po potvrdení sa správa vôbec nezobrazila.`
- Route:
  `runtime_issue.router` → `cmd_runtime_issue` → tri-state explicit admin
  guard → `handle_runtime_issue_capture` → protected read-only workspace
  resolver → `RuntimeIssueService.capture`.
- Result: one sanitized `new` row, stable `IR-…` ID, truthful Slovak response,
  no keyboard, no issue state, no business mutation.
- Technical admin-check or workspace-read failure: no row, truthful Slovak
  failure, handled command, and unchanged protected FSM state/data. The
  technical result is not converted to `not_admin` or `no_active_workspace`.
- Evidence:
  `test_exact_command_and_bare_command_use_same_message_only`,
  `test_handler_uses_trusted_read_only_active_workspace`,
  `test_idle_exact_command_admin_check_failure_is_truthful_and_preserves_state`,
  `test_active_exact_command_admin_check_failure_is_handled_without_business_fallthrough`,
  `test_idle_workspace_read_failure_is_truthful_and_preserves_state`, and
  `test_active_workspace_read_failure_is_handled_without_business_fallthrough`.

### Idle natural text

- Precondition: configured administrator and idle state.
- Input: `Po uložení bločku zostala stará klávesnica; ulož to ako problém.`
- Route:
  `semantic_top_level_input` → administrator-only `top_level_action` candidate
  `report_runtime_issue` → shared capture owner and service.
- Resolver boundary: mocked canonical token; real candidate allowlist, trusted
  slot transfer, handler, sanitizer, transaction, response, and final state.
- Result: one text-source row and idle final state.
- Evidence: `test_idle_natural_text_public_route_converges_on_shared_capture`,
  `test_bounded_issue_resolver_contract_has_negative_space`.

### Idle voice

- Precondition: generally authorized administrator, idle, trusted update.
- Input: controlled STT transcript `Nahlás chybu: po potvrdení sa správa
  nezobrazila.`
- Route:
  authorization middleware contract → `handle_voice` → STT →
  `process_invoice_text(input_channel='voice')` → administrator-only bounded
  action → the same shared capture owner and service.
- Result: one voice-source row; trusted actor/update/message/chat values come
  from the Telegram event, not the transcript; final state idle.
- Evidence: `test_admin_idle_voice_converges_on_shared_capture`,
  `test_trusted_slots_cannot_be_supplied_by_report_text`.

### Active-FSM text and voice

- Precondition: an invoice or contact FSM with protected state and business
  data.
- Inputs: exact command or bounded explicit issue report.
- Route:
  `ActiveFsmMessageMiddleware`/`handle_active_fsm_text_update` intercepts before
  business dispatch → explicit admin guard → command or bounded issue decision
  → the same shared capture owner.
- Result: handled once; no `clear`, `set_state`, issue-owned `update_data`,
  replay, idle dispatch, callback, or keyboard. Protected state/data are byte-
  for-byte equivalent at the test boundary. Existing technical activity
  metadata remains governed only by the existing middleware lifecycle.
- Evidence:
  `test_active_fsm_capture_duplicate_bare_and_failure_preserve_protected_state`,
  `test_admin_active_fsm_voice_preserves_state_and_data`,
  `test_persistence_failure_is_truthful_and_preserves_active_fsm`,
  `test_acknowledgement_failure_keeps_committed_issue_and_fsm`, and the
  unchanged `tests/test_active_fsm_guard.py`.

## Section A acceptance matrix

| Section A scenario | Result | Evidence |
|---|---|---|
| 1. Idle text `/issue` | pass | Exact command plus trusted-workspace handler tests; real SQLite row and Slovak acknowledgement |
| 2. Idle voice issue | pass | Public voice handler, fake STT, bounded token, shared real capture/service |
| 3. Active FSM preservation | pass | Active text and voice compare protected state/data and assert zero issue-owned mutations |
| 4. Bare `/issue` | pass | Idle and active command tests prove usage only, no row/state |
| 5. Unauthorized text | pass | Non-admin candidate and command tests plus access/tenant regression suites |
| 6. Unauthorized voice | pass | Outer middleware blocks handler/STT; authorized non-admin reaches ordinary STT but never issue candidate/store |
| 7. Ambiguous normal business text | pass | Parameterized business/ambiguous/keyword-only negative-space tests create no row |
| 8. Capability question | pass | Exact capability/how-to questions render Product Truth/InfoHelp and create no row |
| 9. Issue persistence failure | pass | Forced service failure returns truthful failure and preserves FSM; trigger test proves rollback |
| 9a. Admin/workspace technical read failure | pass | Forced SQLite/OSError failures in idle and active exact-command paths return truthful failure, create no row, preserve state/data, and active paths do not fall through |
| 10. Deduplicated Telegram delivery | pass | Same trusted delivery returns original ID and one row; distinct delivery with same description creates another ID |
| 11. Workspace isolation | pass | Report text cannot select workspace; trusted resolver stores `trusted-workspace`; actor/workspace-scoped read negatives pass |
| 12. No active workspace | pass | Public command and service store null workspace with `no_active_workspace` |
| 13. Additive schema compatibility | pass | Fresh/repeated bootstrap, unknown optional column, missing/type/constraint failures, and full business snapshot equality |
| 14. Secret redaction | pass | Token/password/auth header/private path removed before title/store; unsafe environment dump creates no partial row |
| 15. Existing callback invariants | pass | Full named decision-callback and invoice-followup handler regression suites |

## General acceptance matrix

- Primary text, first-message complete description, command convergence and
  voice convergence: applicable and pass.
- Missing description: bare command returns same-message usage; a continuation
  state is intentionally not applicable because the approved design forbids an
  issue FSM or next-message capture.
- Invalid/unsafe description: pass, truthful safe rejection with no write.
- Buttons/decision tokens/callbacks: intentionally not applicable to this
  one-message action; existing callbacks are unchanged and fully regressed.
- Active-FSM ownership, navigation, stale recovery and old continuation input:
  pass in `test_active_fsm_guard.py`, `test_state_control.py`, and
  `test_voice_state_routing.py`.
- Product-owner-approved exact-text/button voice restrictions remain unchanged
  for `DeleteUserDatabaseStates.waiting_exact_confirmation` and the restricted
  contact-registry states. Runtime issues can be reported after those FSMs are
  no longer active.
- Nearby actions, ambiguous input and `unknown`: pass with no issue write.
- Unauthorized and tenant/workspace isolation: pass.
- Persistence success, duplicate, rollback and acknowledgement failure: pass.
- Unchanged old journeys through every modified shared layer: pass through the
  complete named shared-layer set below.

## Slot and owner evidence

| Material value | Python owner | Evidence |
|---|---|---|
| `description` | versioned deterministic sanitizer | length, truncation, secret/path redaction, unsafe rejection tests |
| `short_title` | sanitizer after redaction | derived-title assertion and 120-character bound |
| `reported_at` | service UTC clock | insert/read service test; no `occurred_at` exists |
| actor/update/message/chat IDs | public route trusted event objects | command/voice trusted-slot assertions; transcript/text override negatives |
| `workspace_id` and reason | `resolve_for_user_readonly` | active trusted workspace and null-workspace tests |
| `source_channel` | text/voice route | public idle and active route assertions |
| FSM state/context | shared active guard plus allowlist summarizer | state preservation and no raw FSM-value assertions |
| build SHA/status | Python trusted context | null plus `unavailable`; content cannot supply it |
| privacy metadata | sanitizer | bounded version/category/count/truncation assertions |
| deduplication key | service SHA-256 over versioned trusted delivery identity | duplicate and distinct-delivery tests |
| service metadata | `RuntimeIssueService` | stable ID, schema 1, status `new`, record 1, UTC timestamps |

No LLM supplies or validates an exact trusted slot. The LLM boundary can select
only `report_runtime_issue` or `unknown` in an explicitly administrator-
authorized context.

## Persistence and migration evidence

The dedicated table and index are documented in
`docs/features/runtime_issue_autorepair_v1/07_IMPLEMENTATION_NOTES.md`.
`bot/services/db.py` performs only additive `CREATE TABLE IF NOT EXISTS` and
`CREATE INDEX IF NOT EXISTS`, then audits owned columns, types, nullability,
primary key, defaults, constraints, schema version, and deduplication
uniqueness. Unknown optional columns are tolerated. Missing or incompatible
required ownership fails closed. Service SQL names every column and reads
`sqlite3.Row` values by name.

The temporary migration test snapshots every existing non-issue table's
`sqlite_master` SQL and rows before bootstrap and proves exact equality after
bootstrap. No production database was opened or migrated.

## Product Truth and InfoHelp evidence

`runtime_issue_intake` is `supported`, `requires_admin=true`, with supported
channels `command`, `text`, and `voice`. Slovak copy states that one report is
stored, the active business action remains unchanged, and storage does not
confirm, diagnose, repair, promise timing, merge, or deploy. `Vieš nahlásiť
problém?` and `Ako nahlásim problém?` return guidance without executing or
writing. Autorepair remains unavailable.

## Commands and results

```text
/tmp/runtime-issue-review-venv/bin/python -m pytest -q \
  tests/test_runtime_issue_service.py tests/test_runtime_issue_routes.py \
  tests/test_runtime_issue_voice.py tests/test_info_help.py \
  tests/test_product_truth.py
171 passed in 7.22s

/tmp/runtime-issue-review-venv/bin/python -m pytest -q \
  tests/test_runtime_issue_service.py tests/test_runtime_issue_routes.py \
  tests/test_runtime_issue_voice.py tests/test_active_fsm_guard.py \
  tests/test_voice_state_routing.py tests/test_state_control.py \
  tests/test_invoice_intent_prerouter.py tests/test_decision_callbacks.py \
  tests/test_invoice_followup_handler.py tests/test_access_request_flow.py \
  tests/test_tenant_safety.py tests/test_workspace_context.py \
  tests/test_product_truth.py tests/test_info_help.py
535 passed in 21.13s

/tmp/runtime-issue-review-venv/bin/python -m pytest -q
2287 passed, 7 subtests passed in 72.64s
```

No required repository suite was omitted.

## Stage boundary

Only section A is implemented and claimed. No finding decomposition,
diagnosis, classification, claim/lease, maintenance run, manifest, evidence
collector, repair/remediation, contact refresh, document deletion/quarantine,
result writer, notification outbox, repair branch, automatic merge, deployment,
restart, rollback, or `AUTOREPAIR_LOG.md` exists in this change.

## Verdict

`safe_to_commit`

This verdict is repository implementation evidence only. It is not merge,
migration, deployment, activation, or production approval.
