# FakturaBot Data Migration Runbook

## Purpose

This runbook defines how to handle changes that affect persisted FakturaBot data.

It applies to DB rows, invoice PDF references, accounting document originals, metadata JSON sidecars, tenant workspace keys, file paths, backup/cleanup routines, and future database-engine changes.

The goal is to prevent a repeat of the tenant-scope rollout gap where existing files remained valid on disk but new runtime routing no longer looked in their legacy location.

## Current Incident: Tenant Workspace Repair

Observed on 2026-05-06:

- supplier profile data remained available because it is stored in SQLite and scoped by `telegram_id`;
- confirmed accounting documents were not shown by `/blocek` because older metadata/originals are under `storage/workspaces/mykhailo-szco/...`;
- current tenant-scoped recent-document routing reads `storage/workspaces/telegram-{supplier_telegram_id}/...`;
- invoice DB rows exist, but some old `invoice.pdf_path` values point to local Windows paths and are invalid on the Linux server;
- data was not lost, but storage routing and persisted paths need a controlled repair.

This is a migration/repair problem, not an LLM, STT, Telegram, or supplier-profile-edit problem.

## Data Shapes

### Supplier profile

Source of truth:

```text
SQLite supplier table
key: telegram_id
```

### Outgoing invoices

Source of truth:

```text
SQLite invoice and invoice_item tables
key: supplier_telegram_id
invoice.pdf_path points to the generated PDF
```

Current target PDF path:

```text
storage/invoices/{supplier_telegram_id}/{invoice_number}.pdf
```

Legacy or problematic paths can include:

```text
storage/invoices/{invoice_number}.pdf
D:\AI_Model\Ai_assistant\storage\invoices\{invoice_number}.pdf
```

### Accounting documents / bločky

Source of truth for the recent `/blocek` view:

```text
storage/workspaces/<workspace>/years/*/expenses/*/<receipts|incoming_invoices>/metadata/*.json
```

Each confirmed accounting document consists of:

```text
originals/<file>
metadata/<same-stem>.json
```

The metadata JSON may contain storage fields such as:

```json
{
  "storage": {
    "workspace_key": "telegram-...",
    "supplier_telegram_id": 123,
    "original_path": "...",
    "metadata_path": "..."
  }
}
```

Legacy owner data may exist under:

```text
storage/workspaces/mykhailo-szco/
```

Current tenant-scoped runtime reads:

```text
storage/workspaces/telegram-{supplier_telegram_id}/
```

## Required Workflow

### 1. Read-only audit

Before any repair or migration:

- count supplier profiles;
- count invoice rows per supplier;
- count invoice rows with `pdf_path`;
- classify `pdf_path` values:
  - existing server path,
  - missing file,
  - Windows/local path,
  - flat legacy path,
  - tenant path;
- count PDF files on disk under `storage/invoices`;
- count accounting metadata JSON files per workspace;
- count accounting original files per workspace;
- validate that each metadata JSON parses;
- validate that each metadata `storage.original_path` points to an existing file or report it as missing;
- do not print real Telegram IDs in public docs or chat.

### 2. Backup

Before server-side writes:

- back up SQLite DB;
- back up `storage/invoices`;
- back up `storage/workspaces`;
- record timestamp;
- record deployed commit SHA;
- keep rollback instructions next to the backup.

### 3. Dry-run repair plan

The dry run must show:

- files that would be copied or moved;
- metadata JSON fields that would be rewritten;
- DB `invoice.pdf_path` rows that would be updated;
- files or rows that cannot be matched safely;
- counts before and expected counts after.

The dry run must not write files, change DB rows, restart services, or clean old data.

### 4. Apply only after explicit approval

Server-side apply may proceed only after the user approves the dry-run result.

For current tenant workspace repair:

- copy confirmed accounting originals and metadata from `mykhailo-szco` to the correct `telegram-{supplier_telegram_id}` workspace;
- update metadata `storage.workspace_key`, `storage.supplier_telegram_id`, `storage.original_path`, and `storage.metadata_path` if they are present or needed;
- keep the legacy workspace until validation passes and deletion is separately approved;
- update invoice `pdf_path` only when the matching PDF is found unambiguously;
- do not alter supplier profiles, contacts, invoice numbers, invoice rows, or business amounts.

### 5. Post-repair validation

After apply:

- run the read-only audit again;
- verify `/blocek` shows the expected confirmed documents for the owner tenant;
- verify invoice PDF lookup/send/edit flows can resolve existing PDFs;
- verify no cross-tenant fallback is introduced;
- run relevant tests locally before committing code changes, if code changes were made.

## Future Migration Governance

Any future change to DB engine, schema, storage layout, tenant scoping, path format, metadata schema, or cleanup rules must be treated as migration-sensitive.

Examples:

- SQLite to PostgreSQL or another DB;
- DB schema changes;
- tenant/workspace key changes;
- moving PDF files;
- changing `invoice.pdf_path` semantics;
- moving accounting document originals or metadata JSON;
- changing JSON metadata schema;
- switching from absolute paths to storage-relative paths;
- archive/delete/cleanup behavior changes.

Required before implementation:

- current shape;
- proposed shape;
- affected existing data;
- migration or no-migration rationale;
- read-only audit plan;
- backup and rollback plan;
- dry-run plan;
- explicit user approval before write/apply;
- `PROJECT_LOG.md` entry;
- `docs/TZ_FakturaBot.md` or runbook update when runtime behavior or architecture changes.

Do not implement cross-tenant fallback reads as a substitute for migration.

### Outgoing invoice Drive annual-folder migration

The current outgoing-invoice Drive target is
`<workspace.drive_folder_name>/<YYYY>/faktury`. A migration from the earlier
monthly shape must inventory every uploaded `invoice_pdf` job and remote file,
prove its workspace/profile and issue year from SQLite, reject duplicate-name
conflicts, back up SQLite and local invoice originals, and then move the remote
file by adding the verified annual folder parent and removing only its verified
monthly parent. Update only the matching archive-job target and folder id.

Delete an old month folder only after Drive readback proves it is inside the
expected profile/year `faktury` folder and contains no remaining files or
subfolders. Never recursively delete a non-empty or unverified Drive folder.

## Multi-Workspace Business Profiles V1 Tooling

Current local implementation provides read-only audit/dry-run planning and an explicitly gated apply/rollback path:

python -m bot.multi_workspace_migration --mode audit --db-path <db-path> --storage-root <storage-root>
python -m bot.multi_workspace_migration --mode dry-run --db-path <db-path> --storage-root <storage-root>

The report:

- opens SQLite with mode=ro;
- redacts Telegram/workspace tenant values into stable report-local references;
- inventories table columns, row counts, tenant groups, and indexes;
- classifies persisted invoice PDF paths without printing paths;
- counts accounting workspace directories, metadata, and originals without printing tenant-derived directory names;
- lists required workspace-column backfills and uniqueness rebuilds;
- preserves existing valid invoice.pdf_path values and plans no PDF moves.
- derives public_profile_switch_ready from persisted state instead of a deployment-stage constant:
  - every required business table and workspace_id column is present;
  - every workspace-owned row is backfilled;
  - the migration planner reports zero ownership/ambiguity blockers;
  - workspace, membership, and active-selection foundation references are valid.

For an already migrated healthy database, dry-run reports public_profile_switch_ready=true, migration_required=false, apply_available=false, and apply_block_reason=database_already_migrated. A broken foundation, null ownership, missing workspace columns, or planner blocker keeps readiness false.

For already migrated databases, ownership validation uses the persisted workspace_id together with the legacy actor field and canonical supplier/workspace mapping. Multiple supplier profiles for one actor are therefore valid when each row remains bound to one of that actor's workspaces. The audit still fails closed for null or unknown workspaces, actor/workspace mismatches, and cross-workspace invoice/contact, follow-up, confirmed-alias, work-time-event, or customization relations. Legacy pre-migration databases continue to require an unambiguous Telegram-to-workspace mapping.

Apply and rollback tooling is implemented and fixture-tested. Production migration for exact SHA 7408399239eba8cb221ba7b6e7267ccf1d60a867 completed on 2026-07-13 after a frozen read-only baseline, verified host backup, fingerprint-pinned apply, post-apply audit, and bounded read-only smoke. The rollback backup remains retained at:

    /var/backups/fakturabot/20260713T173948Z_7408399
The multi-profile audit repair and contact.iban additive deployment completed on 2026-07-17 at runtime commit 997d3e7. Pre- and post-deploy canonical dry-runs reported public_profile_switch_ready=true, blocker_count=0, migration_required=false, and writes_performed=false. The verified pre-schema SQLite rollback snapshot is retained at:

    /var/backups/fakturabot/20260717T190725Z_997d3e7_contact_registry

Its manifest records source/backup integrity ok, SHA-256 587ccd95596bb5aad651d79f8df2d23435bb44be1274c08a532c2268625aeab4, four contact rows, nine invoice rows, and absence of contact.iban before startup. Post-deploy verification found the nullable column exactly once, all pre-existing contact IBAN values null, full table-count parity, no orphan invoice contacts, and database integrity ok.

The migrated runtime is ready for public profile operations. Full conversation acceptance remains partial until one authorized Telegram actor creates a second profile through /profily and exercises text/voice switching and lightweight cross-profile object isolation without production-only synthetic fixtures.

### Production-safe server sequence

1. Run only the read-only server report first. Do not stop or restart Docker and do not write the DB:

    python -m bot.multi_workspace_migration --mode dry-run --db-path <server-db-path> --storage-root <server-storage-root>

The report must be retained and presented before approval. It contains a redacted logical database fingerprint, candidate/ownership counts, blocker codes, and apply_available; it must not expose Telegram IDs or tenant paths. writes_performed must be false.

2. If apply_available is not true, stop. Resolve blockers with a new reviewed plan. Never force apply.

3. After explicit approval for the reported server snapshot, stop every SQLite writer. Re-run dry-run after stop and use only that final fingerprint. Apply requires a backup directory outside storage/invoices and storage/workspaces:

    python -m bot.multi_workspace_migration --mode apply --db-path <server-db-path> --storage-root <server-storage-root> --expected-fingerprint <final-dry-run-fingerprint> --backup-dir <external-backup-root> --confirm APPLY_MULTI_WORKSPACE_V1 --service-stopped

Apply refuses a changed fingerprint, an active SQLite lock, ambiguous/orphan ownership, an already migrated database, insufficient backup capacity, or an unsafe backup destination.

4. Apply creates a consistent SQLite backup, copies raw DB/WAL/SHM evidence when present, snapshots invoice/workspace storage, verifies DB integrity and logical fingerprint, and verifies content-hashed storage inventories. It builds and audits a separate target DB before an atomic same-directory replacement. Existing non-empty invoice.pdf_path and accounting paths are preserved; managed storage is not rewritten.

5. Retain manifest_path and post_apply_fingerprint from the apply report. A successful post-apply audit requires SQLite integrity, source row-count parity, no unresolved workspace ownership, zero migration blockers, and workspace/membership foundation rows.

6. Do not restart Docker merely because apply passed. Restart and server smoke require the explicit approval that follows the presented server dry-run report. Smoke must verify authorization, active profile, profile switching, contacts, invoices/PDF, accounting documents, work-time, and cross-workspace isolation.

7. Before restart, rollback remains available while the current DB fingerprint and content-hashed storage inventory still match the apply manifest:

    python -m bot.multi_workspace_migration --mode rollback --db-path <server-db-path> --storage-root <server-storage-root> --expected-fingerprint <post-apply-fingerprint> --manifest-path <manifest-path> --confirm ROLLBACK_MULTI_WORKSPACE_V1 --service-stopped

Rollback verifies manifest state/version, current DB identity, backup SHA-256, backup integrity, and unchanged storage before atomic restore. It refuses rollback if DB or storage drifted. If post-swap target fingerprint verification fails during apply, apply performs an emergency restore from the verified pre-apply snapshot and records the failure status in the manifest.

### Local proof coverage

tests/test_multi_workspace_migration_apply.py covers legacy-schema dry-run/apply/post-audit/rollback, path and storage preservation, backup artifacts, orphan ownership, confirmation/fingerprint/service-stop gates, SQLite lock refusal, unsafe backup destination, storage-drift rollback refusal, mixed foundation preservation, repeated-apply refusal, empty datasets, and fault-injected emergency restore.
### Transitional supplier schema

Fresh local schemas now support nullable UNIQUE(workspace_id) supplier ownership while retaining telegram_id only as actor compatibility data. Legacy deployed supplier schemas remain accepted by init_db and are not automatically converted to workspace ownership. Workspace-aware supplier writes fail closed with workspace_supplier_schema_migration_required on a legacy schema.

The explicit migration apply must backfill supplier.workspace_id and remove the legacy UNIQUE(telegram_id) constraint before additional profile creation can be enabled on persisted data.
### Transitional contact schema

Fresh local schemas support nullable contact.workspace_id and UNIQUE(workspace_id, name), allowing the same customer name in separate business profiles. Existing deployed contact schemas remain accepted and are not automatically rebuilt. Workspace contact writes require the target schema; legacy Telegram-scoped reads/writes fail closed once a Telegram actor owns multiple supplier profiles.

Migration apply must backfill contact.workspace_id from validated supplier ownership and rebuild the old UNIQUE(supplier_telegram_id, name) constraint before public switching.
### Transitional confirmed alias schema

Fresh local schemas support nullable confirmed_semantic_alias.workspace_id and workspace-scoped alias uniqueness. Contact aliases can resolve independently in separate workspaces. Legacy deployed alias schemas remain accepted and are not automatically rebuilt; legacy single-profile contact/service alias writes use compatibility upserts only while scope is unambiguous.

Migration apply must backfill alias workspace ownership from the validated target contact or supplier service mapping and rebuild the old Telegram-derived uniqueness constraint before public profile switching.
### Transitional invoice and numbering schema

Fresh local schemas support nullable invoice.workspace_id with UNIQUE(workspace_id, invoice_number) and nullable invoice_number_settings.workspace_id with UNIQUE(workspace_id, issue_year). Workspace services validate contact ownership and maintain independent numbering per business profile, including the same invoice number in separate workspaces.

Legacy deployed invoice and numbering schemas remain accepted and are not automatically rebuilt. Legacy single-profile writes remain supported while scope is unambiguous, and duplicate invoice numbers are explicitly rejected in Python for workspace_id NULL compatibility rows.

Migration apply must backfill invoice and numbering workspace ownership, validate every invoice contact belongs to the same workspace, preserve valid invoice.pdf_path values, and rebuild Telegram-derived uniqueness constraints before public switching.
### Transitional invoice follow-up, analytics, and PDF ownership

Fresh local schemas support nullable invoice_followup_state.workspace_id. Workspace follow-up writes validate the invoice workspace, callbacks resolve membership from the invoice workspace rather than the interactive active selection, and background scans iterate persisted workspace ids. Legacy follow-up and invoice analytics readers are restricted to workspace_id NULL invoice rows so they cannot merge additional profiles owned by the same Telegram actor.

Migration apply must backfill invoice_followup_state.workspace_id from the owning invoice, reject orphan or mismatched follow-up rows, and create the workspace reminder index. Background delivery requires an active authorized supplier owner membership for each workspace and must not consult active_workspace_selection.

New PDF targets use storage/invoices/<workspace.storage_key>/<invoice_number>.pdf. Existing non-empty invoice.pdf_path values are preserved and resolved as stored; migration does not move or rewrite those files automatically. Any later path move requires a separate backed-up dry run and rollback plan.

## Accounting-document Google Drive target deployment gate

Before deploying workspace-specific accounting-document Drive targets, run:

```text
python -m bot.accounting_document_drive_audit --db-path <server-db-path>
```

The command opens SQLite with `mode=ro` and `PRAGMA query_only`, reports only
aggregate counts, blocker categories, and before/after database SHA-256 values,
and performs no repair or backfill. Exit code `0` means the audited active jobs
are deployment-ready. Exit code `2` blocks deployment.

The audit covers non-terminal receipt/incoming-invoice jobs in `pending`,
`uploading`, and `retry_wait`. Blockers include:

- missing workspace context;
- missing `target_folder_path`;
- unsafe or inconsistent local/metadata/target paths;
- a persisted target that does not match the workspace folder, document type,
  year, and month derived from canonical persisted state.

Do not deploy while `blocker_count` is non-zero. Prepare and approve a separate
dry-run repair plan; this command has no apply mode. Do not rewrite uploaded
jobs, move remote files, or run a startup backfill. The normal deployment
backup/rollback discipline remains mandatory, and rollback preserves DB rows,
local originals, metadata, and remote files.
