# OfficeFlow Architecture Framing

**Document role:** docs-first framing for the planned OfficeFlow umbrella architecture.

This document is a proposal and terminology baseline. It does not describe runtime behavior that already exists unless explicitly marked as current.

---

## 1. Purpose

OfficeFlow is the planned umbrella system for small-business document and office workflows.

The current working product remains **FakturaBot**:
- current module scope: outgoing invoices,
- current supplier profile: SZCO Mykhailo Alieksieienko,
- current runtime: existing Telegram invoice flow, contacts, service aliases, PDF generation, and approval/edit lifecycle.

This framing exists to prepare a docs-first transition from standalone FakturaBot wording to a modular OfficeFlow architecture without breaking the existing invoice flow.

---

## 2. Current Baseline

Current FakturaBot is implemented as a Telegram-first MVP for creating outgoing invoices from text, voice, and contract-derived contact data.

The outgoing invoice module remains unchanged by Document Intake Phase 1:
- generated invoice PDFs still use the existing `storage/invoices/` folder,
- persisted invoice rows still use the existing `pdf_path` behavior,
- existing invoice PDFs are not migrated.

Current confirmed runtime concepts:
- one supplier profile stored in the `supplier` table,
- contacts scoped to the current supplier/user context,
- service aliases scoped to supplier id,
- outgoing invoice records in SQLite,
- generated invoice PDFs under the configured `storage/invoices/` folder,
- uploaded contract documents under the configured `storage/contracts/` folder,
- accounting Document Intake Phase 1 for receipts and incoming invoices,
- neutral idle attachment staging before routing,
- bounded LLM orchestration where Python owns validation and side effects.

Accounting Document Intake Phase 1 currently supports:
- `/doklad`, `/expense`, and `/intake` for state-scoped receipt/incoming-invoice uploads,
- shared idle attachment pre-routing for idle photo/PDF uploads,
- Python-owned validation and user approval before confirmed accounting storage,
- confirmed accounting document storage under:

```text
storage/workspaces/mykhailo-szco/years/<YYYY>/expenses/<MM>/<receipts|incoming_invoices>/<originals|metadata>/
```

Neutral idle attachment staging currently uses:

```text
storage/uploads/attachment_intake/<id>/original.<ext>
```

This neutral staging area is temporary and is not confirmed business storage.

Current runtime does **not** provide:
- OfficeFlow umbrella module routing,
- workspace runtime,
- multiple supplier profiles inside one workspace,
- yearly storage folders,
- full workspace runtime despite the implemented accounting storage folder shape,
- expense/incoming document processing beyond Accounting Document Intake Phase 1 for receipts and incoming invoices,
- bank statement processing,
- document category persistence,
- Zevs s.r.o. runtime supplier profile.

---

## 3. Target Terminology

### OfficeFlow

OfficeFlow is the umbrella product/system name for a modular document workflow environment.

OfficeFlow may contain multiple modules over time, but the current codebase should not claim those modules are implemented until runtime exists and is documented.

### Workspace

A workspace is the logical container for one business context and its data.

Proposed meaning:
- owns master data,
- owns accounting-year folders,
- owns module configuration,
- may contain one or more supplier profiles in the future.

Initial docs assumption:
- one workspace for the current SZCO use case,
- no runtime multi-workspace implementation yet.

### Supplier Profile

A supplier profile is the business/legal entity that issues outgoing documents.

Current implementation:
- represented by the existing `supplier` table and `SupplierService`,
- one active SZCO profile is in scope.

Future framing:
- supplier profiles are persistent master data,
- additional profiles such as Zevs s.r.o. may be introduced later only through a separate docs/runtime decision.

### Module

A module is a bounded business capability within OfficeFlow.

Planned/current module framing:
- **FakturaBot / Outgoing Invoices**: current module, implemented.
- **Accounting Document Intake Phase 1**: current incremental runtime for receipts and incoming invoices.
- **Shared idle attachment router**: current idle pre-router above accounting intake and contact/contract intake.
- **Broader Document Intake**: future module for additional incoming documents and long-living document capture.

---

## 4. Module Boundaries

### FakturaBot module: outgoing invoices

Current responsibility:
- create outgoing invoice drafts,
- resolve contacts and service aliases,
- validate invoice data,
- generate PDF invoices,
- support approval/edit/cancel lifecycle,
- persist outgoing invoices and invoice items.

Non-goals for this module:
- expense bookkeeping,
- bank statement parsing,
- document category management,
- long-term accounting package export.

### Accounting Document Intake Phase 1: implemented intake layer

Current responsibility:
- receive receipt and incoming-invoice photo/PDF uploads in the accounting intake FSM flow,
- classify and extract bounded candidate metadata through LMM wrappers,
- validate candidate metadata in Python,
- show a Slovak preview,
- save confirmed originals and metadata only after explicit user approval.

Current confirmed storage:

```text
storage/workspaces/mykhailo-szco/years/<YYYY>/expenses/<MM>/<receipts|incoming_invoices>/<originals|metadata>/
```

This storage path is implemented for the current `mykhailo-szco` accounting intake runtime, but it does not mean full OfficeFlow workspace runtime is implemented.

### Shared idle attachment router: implemented pre-router foundation

Current responsibility:
- run only when no FSM state is active,
- stage idle photo/PDF originals under neutral temporary storage,
- classify document type as `receipt`, `incoming_invoice`, `contract`, `contact_source`, or `unknown`,
- map the document type to a Python-owned action proposal,
- ask the user before entering accounting or contact/contract processing.

Current neutral staging:

```text
storage/uploads/attachment_intake/<id>/original.<ext>
```

The idle router is not a top-level business module and does not save confirmed accounting documents, create contacts, or archive contracts by itself.

### Document Intake module: broader future intake layer

Broader planned responsibility:
- receive and classify incoming business documents,
- keep original files,
- prepare candidate metadata for user review,
- support later accounting handoff.

Future document types:
- receipts / blocky,
- incoming invoices / prijate faktury,
- contracts / zmluvy,
- bank statements / bankove vypisy,
- other incoming documents if explicitly added later.

The broader module must follow the same authority split:
- Python orchestrates,
- AI extracts or drafts candidate metadata,
- Python validates,
- user confirms,
- system saves.

---

## 5. Master Data vs Accounting-Year Documents

OfficeFlow should separate persistent master data from yearly accounting documents.

Persistent master data:
- supplier profiles,
- contacts,
- service aliases,
- document categories,
- long-living contracts and reference documents.

Yearly accounting documents:
- outgoing invoices for a year,
- incoming invoices for a year,
- receipts/expenses for a year,
- bank statements for a year,
- accountant exports/packages for a year.

The current outgoing invoice runtime stores invoice PDFs in the flat `storage/invoices/` folder and keeps DB `pdf_path` behavior unchanged. Existing invoice PDFs are not migrated by Accounting Document Intake Phase 1.

Contracts still use the existing contract/contact helper path under `storage/contracts/` where that older flow applies.

Accounting Document Intake Phase 1 is the current exception to the previously purely flat runtime storage: confirmed receipts and incoming invoices are now stored under the implemented workspace/year/month accounting path for `mykhailo-szco`.

See also:
- `docs/Document_Intake_Module_Proposal.md`
- `docs/OfficeFlow_Storage_Model_Proposal.md`, including the future Google Drive sync rule that confirmed accounting metadata should use storage-relative paths resolved from `STORAGE_ROOT`, not host-only absolute paths.

---

## 6. Non-Runtime Status

This document does not authorize:
- DB schema changes,
- moving existing invoice PDFs,
- changing `pdf_path`,
- adding workspace runtime,
- adding Zevs s.r.o. runtime profile,
- adding bank statement runtime,
- treating Accounting Document Intake Phase 1 as full OfficeFlow workspace runtime,
- migrating outgoing invoices into the workspace/year folder model,
- adding OCR/LLM extraction runtime for a general Document Intake module beyond the currently implemented bounded receipt/incoming-invoice intake.

Any runtime migration must be planned separately with backup, compatibility, and regression tests for the existing invoice flow.
