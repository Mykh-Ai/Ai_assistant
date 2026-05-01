# Document Intake Module Proposal

**Document role:** docs-first proposal for a future OfficeFlow Document Intake module.

This document does not describe an implemented expenses/incoming-documents runtime. Current code contains a narrow document intake helper for contract attachments in the contact flow; that helper is not the full module described here.

---

## 1. Purpose

Document Intake is the planned OfficeFlow module for receiving, preserving, classifying, and preparing incoming business documents for user-confirmed storage and later accounting handoff.

The module should complement, not replace, the current FakturaBot outgoing invoice flow.

---

## 2. Current Baseline

Current implemented behavior:
- contract PDF attachments can be accepted in the contact intake path,
- original files are saved under `storage/contracts/`,
- text-based PDFs can be read,
- scan-PDF OCR branch fails loud / remains pluggable,
- extracted contact data is candidate-only and must be confirmed before save.

Current behavior is not:
- expense intake,
- receipt OCR,
- incoming invoice processing,
- bank statement parsing,
- general document classification,
- accounting export.

---

## 3. Target Document Types

Future Document Intake may support:
- receipts / blocky,
- incoming invoices / prijate faktury,
- contracts / zmluvy,
- bank statements / bankove vypisy,
- other business documents only after explicit scope approval.

Each type should have a bounded intake contract and a user confirmation step before persistence.

---

## 4. Proposed Intake Lifecycle

Target lifecycle:

1. User uploads a file or forwards a document.
2. Python stores the original file in a safe intake area.
3. Python determines candidate document type or asks for bounded clarification.
4. AI may extract/draft candidate metadata only within the Python-provided schema.
5. Python validates required fields and risk rules.
6. User reviews, edits, and confirms.
7. System saves the confirmed record and keeps the original file link.

Authority rule:

```text
Python orchestrates -> AI extracts/drafts -> Python validates -> user confirms -> system saves
```

---

## 5. Candidate Metadata By Type

### Receipt / block

Candidate fields:
- document date,
- supplier/vendor name,
- total amount,
- currency,
- VAT amount if visible,
- category candidate,
- payment method if visible,
- original file path.

### Incoming invoice / prijata faktura

Candidate fields:
- supplier/vendor name,
- invoice number,
- issue date,
- due date,
- delivery/tax date if visible,
- total amount,
- currency,
- IBAN if visible,
- variable symbol if visible,
- category candidate,
- original file path.

### Bank statement / bankovy vypis

Candidate fields:
- bank/account identifier,
- statement period,
- currency,
- transaction list candidate,
- original file path.

### Contract / zmluva

Candidate fields:
- parties,
- role interpretation,
- effective date,
- related contact candidate,
- long-living contract status,
- original file path.

Contracts should be treated as long-living reference documents unless a later rule explicitly links them to a yearly accounting package.

---

## 6. Storage Semantics

Future storage should follow `docs/OfficeFlow_Storage_Model_Proposal.md`.

High-level rule:
- incoming accounting documents belong under `years/<YYYY>/`,
- contracts belong under workspace master data unless explicitly copied or referenced from a yearly package,
- categories and supplier/contact dictionaries belong to master data.

No current files should be moved as part of this proposal.

---

## 7. Integration Points

Future integration points:
- top-level action registry for `document_intake` or more specific bounded actions,
- FSM states for document type clarification,
- validation services per document type,
- storage service for original files and confirmed metadata,
- optional category dictionary service,
- later accounting export/package service.

These are planning points only. No runtime action should be added until a separate docs contract is approved.

---

## 8. Explicit Non-Goals

Do not implement in this step:
- expenses runtime,
- bank statement runtime,
- OCR/LLM extraction runtime,
- document category DB schema,
- automatic saving of AI output,
- Zevs s.r.o. profile,
- changes to outgoing invoice flow,
- changes to existing `storage/invoices` or `pdf_path`.
