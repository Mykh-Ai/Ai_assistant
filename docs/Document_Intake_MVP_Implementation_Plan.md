# Document Intake MVP Implementation Plan

**Document role:** docs-first implementation plan for Phase 1 of the future OfficeFlow Document Intake module.

This document does not implement runtime behavior. It defines the first safe runtime slice to implement later, after separate approval.

Related docs:
- `docs/architecture/OfficeFlow_Architecture_Framing.md`
- `docs/architecture/OfficeFlow_Storage_Model_Proposal.md`
- `docs/Document_Intake_Module_Proposal.md`

---

## 1. Phase 1 Scope

Phase 1 covers a narrow intake flow for two accounting document families:
- receipt / bloček,
- incoming invoice / prijatá faktúra.

Accepted user inputs:
- Telegram photo of a receipt or incoming invoice,
- Telegram PDF document of a receipt or incoming invoice.

Phase 1 does not change the existing FakturaBot outgoing invoice flow. It does not move existing invoice PDFs, does not change `pdf_path`, and does not change current supplier/profile runtime.

---

## 2. Target User Flow

Planned Telegram flow:

1. User sends a photo or PDF and indicates it is an expense/incoming document, or enters a future bounded intake command/action.
2. Python stores the original file in a temporary intake area.
3. Python classifies the document as one of:
   - `receipt`,
   - `incoming_invoice`,
   - `unknown`.
4. If classification is `unknown`, bot asks the user to choose the type.
5. LMM extracts candidate metadata into the approved JSON contract.
6. Python validates the candidate fields and detects missing/high-risk values.
7. Bot shows a Slovak preview to the user.
8. User chooses:
   - `schvalit`,
   - `upravit`,
   - `zrusit`.
9. On `schvalit`, Python saves confirmed metadata and keeps the original file link.
10. On `upravit`, bot enters bounded field correction.
11. On `zrusit`, bot discards the draft and does not save metadata.

Authority rule:

```text
Python orchestrates -> LMM extracts/drafts -> Python validates -> user confirms -> system saves
```

---

## 3. Document Classification

Phase 1 classifier outputs:

```json
{
  "document_type": "receipt|incoming_invoice|unknown",
  "confidence": "high|medium|low",
  "reason": "short human-auditable reason"
}
```

Classification rules:
- `receipt`: cash register receipt, block, small purchase receipt, or similar proof of purchase.
- `incoming_invoice`: supplier invoice received by the user/business for payment or accounting.
- `unknown`: unsupported, unreadable, ambiguous, or not enough evidence.

Python must not auto-save based on classification alone.

If confidence is not `high`, Python should ask bounded clarification before extraction or before final confirmation.

---

## 4. LMM Extraction JSON Contract

LMM output must be strict JSON. It is candidate metadata only.

Top-level shape:

```json
{
  "document_type": "receipt|incoming_invoice|unknown",
  "source": {
    "input_type": "photo|pdf",
    "original_filename": "string|null"
  },
  "business": {
    "vendor_name": "string|null",
    "vendor_ico": "string|null",
    "document_number": "string|null",
    "issue_date": "YYYY-MM-DD|null",
    "tax_date": "YYYY-MM-DD|null",
    "due_date": "YYYY-MM-DD|null",
    "total_amount": 0.0,
    "currency": "EUR|null",
    "vat_amount": 0.0,
    "iban": "string|null",
    "variable_symbol": "string|null",
    "payment_method": "cash|card|bank_transfer|unknown|null",
    "purchase_subject": "string|null"
  },
  "quality": {
    "readability": "good|partial|poor",
    "missing_fields": ["field_name"],
    "warnings": ["short warning"]
  },
  "trace": {
    "raw_visible_text_excerpt": "short excerpt|null"
  }
}
```

Document-type field expectations:

Receipt:
- required candidate fields: `vendor_name`, `issue_date`, `total_amount`, `currency`.
- usually absent: `due_date`, `iban`, `variable_symbol`.

Incoming invoice:
- required candidate fields: `vendor_name`, `document_number`, `issue_date`, `total_amount`, `currency`.
- preferred when visible: `due_date`, `iban`, `variable_symbol`.

LMM must not:
- claim that a document was saved,
- invent IDs, paths, or DB references,
- choose accounting, tax, or bookkeeping category,
- infer category from the document,
- execute side effects,
- silently convert an unsupported document into a supported type.

---

## 5. Python Validation Rules

Python must validate after LMM extraction and before user preview/save.

General validation:
- `document_type` must be one of the allowed Phase 1 values.
- `total_amount` must be positive and parseable as a decimal.
- `currency` defaults to `EUR` only if the document context clearly supports Slovak/EUR use; otherwise ask clarification.
- dates must be valid ISO dates.
- future dates beyond a reasonable window require user confirmation.
- `vendor_name` must be non-empty for save.
- `readability = poor` requires user confirmation or manual correction.

Receipt validation:
- require `issue_date`, `vendor_name`, `total_amount`, `currency`.
- `document_number` may be missing.
- `payment_method` may be `unknown`.

Incoming invoice validation:
- require `issue_date`, `vendor_name`, `document_number`, `total_amount`, `currency`.
- `due_date` may be missing but should be highlighted in preview.
- if `iban` is present, validate basic IBAN format.
- if `variable_symbol` is present, validate numeric/simple symbol format.

Purchase subject validation:
- `purchase_subject` is a raw factual description of what was purchased.
- It is not an accounting category and must not be used as tax/bookkeeping classification.
- If unclear, preview should show the value as unknown/missing rather than inventing a category.

Save gate:
- no metadata is saved before explicit user confirmation.
- invalid required fields block save and trigger bounded correction.

---

## 6. File Naming

Phase 1 target naming should be deterministic and collision-resistant.

Proposed normalized filename format:

```text
{YYYYMMDD}_{document_type}_{vendor_slug}_{amount}_{file_unique_id}.{ext}
```

Examples:

```text
20260501_receipt_tesco_24-90_ABCD1234.jpg
20260501_incoming_invoice_stredoslovenska-energetika_118-42_EFGH5678.pdf
```

Rules:
- date uses extracted `issue_date` when valid; otherwise upload date.
- `document_type` is `receipt` or `incoming_invoice`.
- `vendor_slug` is lowercase ASCII-safe slug from vendor name; fallback `unknown_vendor`.
- amount uses dot/comma normalized filename-safe form, e.g. `24-90`.
- `file_unique_id` or equivalent Telegram identifier is appended to avoid collisions.
- extension reflects original file type after validation.
- original Telegram filename should be stored in metadata when available.

---

## 7. Yearly/Monthly Storage Target

Phase 1 should follow the OfficeFlow storage proposal without migrating current FakturaBot storage.

Proposed target:

```text
storage/
  workspaces/
    mykhailo-szco/
      years/
        2026/
          expenses/
            05/
              receipts/
                originals/
                metadata/
              incoming_invoices/
                originals/
                metadata/
```

Routing rules:
- year/month derive from validated `issue_date`.
- if `issue_date` is missing or invalid, keep file in temporary intake storage until corrected.
- receipts go to `expenses/<MM>/receipts/`.
- incoming invoices go to `expenses/<MM>/incoming_invoices/`.
- confirmed metadata should live next to the original or in DB with a stable original file path.

This is a future target. Current runtime must not create or migrate these folders until implementation is approved.

---

## 8. Telegram Preview / Confirm Flow

Preview should be Slovak and compact.

Receipt preview example:

```text
Náhľad dokladu
Typ: Bloček
Dodávateľ: Tesco
Dátum: 01.05.2026
Suma: 24,90 EUR
DPH: 4,15 EUR
Platba: karta
Predmet nákupu: Kancelárske potreby

Schváliť, upraviť alebo zrušiť?
```

Incoming invoice preview example:

```text
Náhľad prijatej faktúry
Dodávateľ: Stredoslovenská energetika
Číslo dokladu: 202605001
Dátum vystavenia: 01.05.2026
Splatnosť: 15.05.2026
Suma: 118,42 EUR
IBAN: SK...
Variabilný symbol: 202605001
Predmet nákupu: Dodávka elektrickej energie

Schváliť, upraviť alebo zrušiť?
```

Confirm decisions:
- `schvalit`: save confirmed metadata and original file path.
- `upravit`: ask which field to edit, then revalidate and show preview again.
- `zrusit`: discard draft and do not save metadata.

Voice-originated edits for precision fields should be converted to bounded text confirmation before save.

---

## 9. DB / Storage Integration Options

Phase 1 implementation can choose one of these options after separate approval.

### Option A: JSON sidecar metadata first

Store one metadata JSON file next to each confirmed original.

Pros:
- minimal DB migration risk,
- easy backup/inspection,
- aligns with docs-first storage model.

Cons:
- harder querying/reporting,
- needs later DB migration for richer workflows.

### Option B: SQLite table first

Add a dedicated table, for example `document_intake_record`.

Possible fields:
- `id`,
- `workspace_key`,
- `supplier_profile_id` or current supplier scope,
- `document_type`,
- `issue_date`,
- `vendor_name`,
- `document_number`,
- `total_amount`,
- `currency`,
- `purchase_subject`,
- `original_path`,
- `metadata_json`,
- `status`,
- `created_at`,
- `updated_at`.

Pros:
- better querying and future accounting package generation,
- clearer status lifecycle.

Cons:
- requires schema migration,
- requires compatibility guardrails and tests.

### Option C: Hybrid

Store original + sidecar JSON and add SQLite index table later.

Recommended for Phase 1 unless query/reporting requirements are already urgent.

---

## 10. Tests Needed

Docs-to-runtime test plan for future implementation:

Classification tests:
- receipt photo -> `receipt`,
- receipt PDF -> `receipt`,
- incoming invoice PDF -> `incoming_invoice`,
- unsupported/ambiguous document -> `unknown`.

Extraction contract tests:
- LMM JSON parser accepts valid Phase 1 shape,
- rejects non-JSON,
- rejects unsupported `document_type`,
- rejects extra side-effect claims if represented in output.

Validation tests:
- receipt missing total blocks save,
- receipt missing vendor blocks save,
- incoming invoice missing document number blocks save,
- invalid date blocks save,
- invalid IBAN triggers warning/block according to field criticality,
- negative/zero amount blocks save.

Storage tests:
- filename slugging is deterministic,
- collision-resistant suffix is included,
- year/month path derives from issue date,
- missing date keeps draft in temporary intake state.

Telegram flow tests:
- upload -> classification -> preview,
- `schvalit` saves only after validation,
- `upravit` mutates only selected field and revalidates,
- `zrusit` saves nothing,
- no impact on existing `/invoice` flow.

Regression tests:
- existing outgoing invoice flow still passes,
- existing contract contact intake still behaves as before,
- existing `storage/invoices` and `pdf_path` behavior unchanged.

---

## 11. Explicit Out Of Scope For Phase 1

Not in Phase 1:
- bank transaction matching,
- bank statement parsing,
- Google Drive sync,
- Zevs s.r.o. runtime profile,
- multi-workspace runtime,
- multi-supplier runtime,
- accounting category inference or automatic category creation,
- accounting reports,
- accountant package export,
- changes to outgoing invoice numbering,
- changes to `storage/invoices`,
- changes to `pdf_path`,
- changes to current FakturaBot DB schema unless a separate implementation decision selects a DB-backed option.
## 2026-05-02 Tenant-Scoped Runtime Addendum

Accounting Document Intake now runs inside the controlled two-user dry-run boundary. Runtime temp staging, confirmed storage, duplicate checks, and recent-document views must be scoped to the requesting Telegram user via a workspace key such as `telegram-{supplier_telegram_id}`. Unauthorized Telegram users must be blocked before any temp file creation or LMM call.

This addendum supersedes older statements that Document Intake does not change invoice PDF paths: outgoing invoice PDFs are now tenant-scoped under `storage/invoices/{supplier_telegram_id}/{invoice_number}.pdf` for the controlled dry run, while `pdf_path` remains the persisted pointer.
