# Runtime Issue Intake V1 — Implementation Notes

Task: `RUNTIME_ISSUE_INTAKE_V1`

Design verification verdict: `design_matches_runtime`

These notes record the migration-sensitive implementation pre-work required by
`06_IMPLEMENTATION_HANDOFF.md`. They describe reviewed code and temporary-test
database behavior only. They do not authorize a production migration,
deployment, Stage 2 processing, or removal of persisted data.

## Current relevant database shape

`bot/services/db.py::init_db` opens the configured SQLite database, bootstraps
the existing business and infrastructure tables, creates additive indexes and
columns for their current owners, and commits once. The approved baseline has
no runtime-issue table or runtime-issue columns in any business table.

Existing business tables and rows are outside this feature. In particular,
supplier, contact, invoice, invoice item, invoice follow-up, accounting
document, archive, workspace, access, customization, and work-time schemas
must not be rebuilt, copied, transformed, or updated by this feature.

## Dedicated Stage 1 table

Table: `runtime_issues`

Schema version: `1`

| Column | SQLite shape | Approved ownership |
|---|---|---|
| `issue_id` | `TEXT PRIMARY KEY` | Service-generated stable issue ID |
| `schema_version` | `INTEGER NOT NULL DEFAULT 1 CHECK (schema_version = 1)` | Dedicated schema compatibility |
| `intake_status` | `TEXT NOT NULL DEFAULT 'new' CHECK (intake_status = 'new')` | Stage 1 intake truth only |
| `description` | `TEXT NOT NULL`, length check 10–2000 | Sanitized observation |
| `short_title` | `TEXT NOT NULL`, length check 1–120 | Python-derived after sanitization |
| `reported_at` | `TEXT NOT NULL` | Trusted UTC intake time |
| `actor_telegram_id` | `INTEGER NOT NULL` | Trusted actor |
| `telegram_update_id` | `INTEGER NOT NULL` | Trusted aiogram `event_update.update_id` |
| `telegram_message_id` | `INTEGER NOT NULL` | Trusted Telegram message |
| `telegram_chat_id` | `INTEGER NOT NULL` | Trusted Telegram chat |
| `workspace_id` | `TEXT NULL` | Trusted active workspace or null |
| `workspace_resolution_reason` | `TEXT NOT NULL`, enum check | `active_workspace` or `no_active_workspace` |
| `source_channel` | `TEXT NOT NULL`, enum check | `text` or `voice` |
| `active_fsm_state` | `TEXT NULL` | Bounded trusted state name |
| `active_fsm_context_summary_json` | `TEXT NOT NULL` | Versioned bounded allowlist summary, never raw FSM data |
| `reported_build_sha` | `TEXT NULL`, 40-hex/null check | Trusted build source only |
| `build_sha_status` | `TEXT NOT NULL`, enum check | `known`, `unavailable`, or `stale` |
| `privacy_metadata_json` | `TEXT NOT NULL` | Bounded redaction/truncation metadata |
| `deduplication_key` | `TEXT NOT NULL UNIQUE` | Versioned trusted-delivery digest |
| `record_version` | `INTEGER NOT NULL DEFAULT 1 CHECK (record_version = 1)` | Stage 1 record version |
| `created_at` | `TEXT NOT NULL` | Service-owned UTC timestamp |
| `updated_at` | `TEXT NOT NULL` | Service-owned UTC timestamp |

Index:

- `idx_runtime_issues_actor_workspace_reported_at` on
  `(actor_telegram_id, workspace_id, reported_at)`.

The unique constraint on `deduplication_key` owns Telegram delivery
idempotency. No description-similarity deduplication is permitted.

Every column maps mechanically to the approved Stage 1 slot or service-owned
metadata contract. There are no Stage 2 classifications, processing statuses,
claims, leases, runs, manifests, evidence, results, repair, deployment, or
notification fields.

## Compatibility and additive bootstrap

Classification: additive, review-pending schema code.

Bootstrap sequence:

1. execute `CREATE TABLE IF NOT EXISTS runtime_issues`;
2. inspect required owned columns by name;
3. validate owned SQLite types, nullability, primary-key ownership, defaults,
   and required CHECK/UNIQUE constraints;
4. tolerate unknown additional columns;
5. fail safely on a missing or incompatible required owned column/constraint;
6. create the narrow index with `CREATE INDEX IF NOT EXISTS`;
7. commit through the existing `init_db` transaction.

The implementation must not use `DROP`, table rebuild, data copy, or automatic
repair of an incompatible table.

## Temporary-database proof

Tests must cover:

- fresh empty database;
- current pre-issue database shape with representative business rows;
- repeated idempotent bootstrap;
- all required columns plus one unknown optional column;
- missing required column;
- incompatible required type;
- incompatible required constraint;
- unchanged existing business table SQL, indexes, identifiers, row counts, and
  row values before and after bootstrap.

All service SQL uses explicit named columns and `sqlite3.Row` name access.

## Backup and rollback boundary

Before any future production startup or deployment that can create this table,
the operator must take and verify a consistent SQLite backup under the normal
deployment runbook. This implementation task does not create that backup and
does not run a production migration.

Before production deployment, rollback must be defined as restoring the
verified pre-deployment SQLite backup together with the reviewed prior runtime
SHA. Dropping `runtime_issues` is not an automatic runtime rollback and must
not be performed by startup code. Any later removal of the table or retained
issue data requires separate approval, retention review, backup, and a
dedicated migration plan.

## Runtime Issue Workshop Bridge Phase 1

Task: `RUNTIME_ISSUE_WORKSHOP_BRIDGE_PHASE1`

Design verdict: `ready_for_handoff`

Phase 1 adds `runtime_issue_handoffs` without changing `runtime_issues`.
Bootstrap is additive and validates owned columns, types, nullability, primary
and unique ownership, exact defaults/checks, and the two owned indexes.
Unknown optional columns are tolerated; incompatible owned schema fails closed.

Executable statuses are `leased`, `expired_unacknowledged`, and
`acknowledged`. `reconciled` is schema-reserved and unreachable in Phase 1.
Leases last 60 minutes. Redelivery preserves the handoff ID and canonical
receipt digest, rotates the raw 256-bit token, and increments `attempt_count`.

The bridge exposes only bounded internal JSON CLIs for `take-next`, stdin-only
`ack`, evidence collection, and idempotent workshop bootstrap. Evidence reads a
fixed 30-minute window centered on trusted `reported_at`, caps raw input at 500
lines/256 KiB, returns at most 20 items with 500-character sanitized excerpts,
and reports missing facts as unavailable. No active provider/STT/network probe
exists.

All migration proof is performed against temporary SQLite files. Production
still requires a verified backup, prior deployed SHA, reviewed rollback plan,
and separate deployment approval.
