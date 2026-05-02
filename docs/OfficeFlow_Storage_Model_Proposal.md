# OfficeFlow Storage Model Proposal

**Document role:** non-runtime proposal for future OfficeFlow storage organization.

This document is intentionally docs-only. It does not change the current `STORAGE_DIR`, existing folders, invoice PDF paths, DB schema, or runtime behavior.

---

## 1. Current Storage Baseline

Current FakturaBot storage is configured by `STORAGE_DIR`.

Current runtime-created folders:

```text
storage/
  fakturabot.db
  invoices/
  contracts/
  uploads/
```

Current meanings:
- `storage/invoices/`: generated outgoing invoice PDFs.
- `storage/contracts/`: original contract files uploaded for contact extraction.
- `storage/uploads/`: temporary upload area.
- `storage/fakturabot.db`: SQLite database.

The invoice table stores `pdf_path` pointing to the generated PDF location. Existing paths must remain valid until an explicit migration is designed and executed.

---

## 2. Target Principles

Future OfficeFlow storage should:
- separate master data from year-bound accounting documents,
- keep outgoing invoice artifacts grouped by accounting year,
- keep incoming expenses grouped by accounting year and month,
- keep bank statements grouped by accounting year and month,
- keep contracts as long-living workspace documents rather than forcing them into one year,
- preserve original uploaded files,
- avoid silent file moves that break DB references.

---

## 3. Proposed Folder Model

Suggested future shape:

```text
storage/
  workspaces/
    mykhailo-szco/
      master_data/
        supplier_profiles/
          mykhailo_alieksieienko.json
        contacts/
        service_aliases/
        categories/
        contracts/
          active/
          archived/
      years/
        2026/
          outgoing_invoices/
            pdf/
            metadata/
          expenses/
            01/
              receipts/
              incoming_invoices/
            02/
              receipts/
              incoming_invoices/
          bank_statements/
            01/
            02/
          exports/
          accountant_package/
      uploads/
        tmp/
```

This is not the runtime structure today.

---

## 4. Master Data Area

`master_data/` is for data that should not reset or move with each accounting year.

Proposed contents:
- `supplier_profiles/`: persistent supplier profile definitions.
- `contacts/`: customer/contact master data.
- `service_aliases/`: supplier-specific service naming dictionaries.
- `categories/`: future expense/document categories.
- `contracts/`: long-living contracts and reference documents.

Notes:
- Contacts and aliases currently live in SQLite, not files.
- The folder names above define future storage semantics, not an immediate file-backed implementation.
- Contracts may be linked to contacts, suppliers, or future intake records, but should not be treated as ordinary one-year expenses by default.

---

## 5. Year Area

`years/<YYYY>/` is for accounting documents belonging to one year.

Proposed contents:
- `outgoing_invoices/`: generated outgoing invoice artifacts.
- `expenses/`: receipts and incoming invoices grouped by month.
- `bank_statements/`: bank statements grouped by month.
- `exports/`: generated reports/exports.
- `accountant_package/`: handoff bundle for accounting review.

For 2026 examples:

```text
years/2026/outgoing_invoices/pdf/20260001.pdf
years/2026/expenses/04/receipts/
years/2026/expenses/04/incoming_invoices/
years/2026/bank_statements/04/
```

---

## 6. Future Google Drive Sync Rules

Future Google Drive sync must treat confirmed accounting storage as the source tree to mirror, not as a place for ad hoc path interpretation.

Required path model:
- confirmed accounting metadata must keep stable storage-relative paths;
- sync code must resolve files as `STORAGE_ROOT + relative_path`;
- host-only paths such as `/bot/repo/data/storage/...` must not be used as canonical sync keys;
- runtime container paths such as `/bot/data/storage/...` may be stored for diagnostics, but they are not the canonical sync key.

Future Drive mirroring scope:
- mirror confirmed accounting storage under the workspace/year/month accounting document structure;
- do not mirror neutral temp upload staging as a confirmed accounting archive;
- files under `storage/uploads/`, including `storage/uploads/attachment_intake/<id>/original.<ext>`, must never be synced as confirmed accounting documents.

This section documents a future requirement only. It does not implement Google Drive sync.

Confirmed accounting metadata is also the source for Document Intake duplicate warnings. Filenames are not duplicate truth because they include a unique upload-derived suffix. Duplicate checks must scan only confirmed accounting metadata under workspace/year/month expenses folders and must not scan temporary uploads, `storage/invoices/`, or `storage/contracts/`.

---

## 7. Migration Rules For Later

Any future migration from the current flat storage must follow these rules:
- backup DB and files first,
- keep existing `pdf_path` valid or migrate it explicitly,
- do not move invoice PDFs without updating and verifying DB references,
- preserve invoice numbering and approval/edit lifecycle behavior,
- keep a rollback plan,
- run invoice flow regression tests before and after migration,
- document the migration in `PROJECT_LOG.md`.

---

## 8. Explicit Non-Goals

This proposal does not implement:
- workspace runtime,
- DB schema changes,
- new storage folders in runtime,
- file migration,
- expense processing,
- bank statement processing,
- OCR/LLM extraction,
- category persistence,
- Google Drive sync,
- Zevs s.r.o. profile.
