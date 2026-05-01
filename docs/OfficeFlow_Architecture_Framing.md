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

Current confirmed runtime concepts:
- one supplier profile stored in the `supplier` table,
- contacts scoped to the current supplier/user context,
- service aliases scoped to supplier id,
- outgoing invoice records in SQLite,
- generated invoice PDFs under the configured `storage/invoices/` folder,
- uploaded contract documents under the configured `storage/contracts/` folder,
- bounded LLM orchestration where Python owns validation and side effects.

Current runtime does **not** provide:
- OfficeFlow umbrella module routing,
- workspace runtime,
- multiple supplier profiles inside one workspace,
- yearly storage folders,
- expense/incoming document processing,
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

Planned module framing:
- **FakturaBot / Outgoing Invoices**: current module, implemented.
- **Document Intake**: future module for incoming documents and long-living document capture, not implemented as an expenses runtime.

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

### Document Intake module: future intake layer

Planned responsibility:
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

This module must follow the same authority split:
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

The current runtime stores invoices and contracts in flat storage folders. That remains the current behavior until an explicit migration plan exists.

---

## 6. Non-Runtime Status

This document does not authorize:
- DB schema changes,
- moving existing invoice PDFs,
- changing `pdf_path`,
- adding workspace runtime,
- adding Zevs s.r.o. runtime profile,
- adding expenses or bank statement runtime,
- adding OCR/LLM extraction runtime for a general Document Intake module.

Any runtime migration must be planned separately with backup, compatibility, and regression tests for the existing invoice flow.
