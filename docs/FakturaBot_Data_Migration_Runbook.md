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
