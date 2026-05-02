# Document Intake Module Proposal

**Document role:** docs-first proposal for a future OfficeFlow Document Intake module.

This document distinguishes three runtime layers:
- the old narrow `bot/services/document_intake.py` contract/contact helper,
- the implemented accounting Document Intake Phase 1 flow,
- the shared OfficeFlow idle attachment router foundation above both intake families.

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
- accounting Document Intake Phase 1 exists for `/doklad`, `/expense`, and `/intake`:
  - accepts photo/PDF while the accounting intake FSM state is active,
  - classifies only receipts and incoming invoices,
  - extracts candidate metadata through a bounded LMM wrapper,
  - validates in Python,
  - shows a Slovak preview,
  - saves to confirmed accounting storage only after explicit user approval.
- shared idle attachment router foundation exists/planned as the layer above accounting intake and contact/contract intake:
  - runs only when no FSM state is active,
  - stages photo/PDF originals in neutral temporary storage,
  - classifies `receipt`, `incoming_invoice`, `contract`, `contact_source`, or `unknown`,
  - maps document type to a Python-owned proposal,
  - asks before entering accounting or contact processing.

Current behavior is not:
- bank statement parsing,
- receipt OCR,
- general document classification beyond the bounded idle attachment document types listed above,
- accounting export.

Important module boundary:
- `bot/services/document_intake.py` remains the old contract/contact PDF helper.
- Accounting intake remains in `bot/handlers/accounting_document_intake.py` and `bot/services/accounting_document_*`.
- The shared attachment router must not stuff receipt/incoming-invoice behavior into `document_intake.py`.
- The shared router is an idle pre-router, not confirmed business storage.

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
- purchase subject / factual item or service description,
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
- purchase subject / factual item or service summary,
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

Current shared idle staging uses neutral temporary storage such as:

```text
storage/uploads/attachment_intake/<id>/original.<ext>
```

This is not confirmed accounting storage and not contract archive storage.

Temporary intake sessions currently have a narrow inactivity policy:
- OfficeFlow idle attachment routing states and accounting document preview expire after 5 minutes of user inactivity.
- On expiry, only temporary upload staging paths under `storage/uploads/attachment_intake/` or `storage/uploads/accounting_intake/` may be cleaned.
- Confirmed accounting storage under `storage/workspaces/...`, outgoing invoice PDFs under `storage/invoices/`, and contract files under `storage/contracts/` are excluded.
- A separate filesystem orphan cleanup helper may remove old upload-staging directories as a safety net; this is not Google Drive sync and not confirmed archive management.

---

## 7. Integration Points

Future integration points:
- top-level action registry for `document_intake` or more specific bounded actions,
- FSM states for document type clarification,
- validation services per document type,
- storage service for original files and confirmed metadata,
- optional category dictionary service,
- later accounting export/package service.

Runtime integration now starts with a shared idle attachment router foundation, while the broader module remains incremental. The router is intentionally above the existing accounting intake and contact/contract helper and must preserve active FSM state ownership.

---

## 8. Explicit Non-Goals

Do not implement in this step:
- bank statement runtime,
- document category DB schema,
- automatic saving of AI output,
- Zevs s.r.o. profile,
- changes to outgoing invoice flow,
- changes to existing `storage/invoices` or `pdf_path`.
