# Accounting Document Analytics Runtime Contract

Status: partial runtime pilot as of 2026-06-21.

This contract follows `docs/llm/Safe_Data_Analyst_Runtime_Checklist.md`.

This contract defines the bounded runtime for canonical top-level action
`accounting_document_analytics`.

The action is a read-only, AI-assisted analysis surface over already confirmed
accounting Document Intake metadata for the current authorized workspace. It
covers receipts/bloceky and incoming invoices/prijate faktury as expense-side
documents. It is not outgoing invoice analytics, not bank matching, not tax or
VAT advice, not accounting export, and not a write surface.

## Domain Split

The product must keep these domains separate:

- `invoice_analytics`: saved outgoing invoices / vystavene faktury / income.
- `accounting_document_analytics`: saved receipts and incoming invoices /
  bloceky + prijate faktury / expense documents.
- bank, cashflow, VAT, tax, and full accounting analytics: unsupported unless a
  separate runtime contract and implementation prove otherwise.

The words "faktura" and "invoice" are ambiguous. Runtime routing must use
business meaning:

- "vystavene faktury", "fakturoval som", "odoslane faktury" belong to
  `invoice_analytics`;
- "prijate faktury", "dodavatelske faktury", "naklady", "vydavky", "minul
  som" belong to `accounting_document_analytics`;
- "blocek", "blocky", "uctenka", "receipt" belong to
  `accounting_document_analytics`.

## Authority Split

Python owns:

- authorization and workspace identity;
- tenant-scoped metadata scanning;
- dataframe construction and column selection;
- current runtime date injection;
- allowed dataset catalog, including allowed category ids and category aliases;
- unsupported-domain guard before planning;
- LLM plan validation;
- AST validation and restricted code execution;
- final side-effect decision: no writes are allowed;
- user-facing fallback when planning or execution fails.

LLM may:

- draft a short Python analysis plan over Python-provided data bounds;
- select filters, groupings, counts, sums, averages, comparisons, and bounded
  lists;
- draft final wording from Python-computed results.

LLM must not:

- query SQLite or run SQL;
- read or write files;
- import modules;
- access network/system resources;
- mutate accounting documents, categories, invoices, storage, DB rows, or FSM
  state;
- create categories or category ids;
- infer tax deductibility, VAT treatment, accounting approval, bank settlement,
  or export readiness;
- invent facts not present in the computed result.

## Canonical Action

`accounting_document_analytics` is a top-level action only when Python includes
it in `allowed_actions`.

It owns read-only analytical questions over confirmed accounting metadata, such
as:

- totals and counts by period, vendor, category, document type, or currency;
- comparisons between periods;
- bounded matching lists of receipts/incoming invoices.

Nearby actions that must win before analytics:

- `add_receipt`: adding/uploading a new receipt or incoming invoice;
- `show_recent_accounting_documents`: read-only recent-document list;
- invoice show/edit/delete by explicit outgoing invoice reference;
- any write request such as delete, edit, mark paid, export, sync, or upload.

No deterministic shortcut is implemented for this first slice. All supported
analytics questions use the safe analytics runtime.

## Dataset Boundary

The runtime builds one dataframe: `accounting_documents_df`.

Scope:

- current authorized workspace only;
- workspace key is derived by Python from the Telegram supplier id;
- source files are confirmed metadata JSON sidecars under
  `storage/workspaces/<workspace>/years/*/expenses/*/<receipts|incoming_invoices>/metadata/*.json`;
- missing workspace means an empty dataframe, not workspace creation.

Columns exposed:

| Column | Meaning |
|---|---|
| `document_id` | Stable metadata-stem id inside the current workspace dataset. |
| `document_type` | `receipt` or `incoming_invoice`. |
| `document_type_label` | Human-readable Slovak label. |
| `issue_date` | Document issue date as ISO date string. |
| `tax_date` | Tax/delivery date as ISO date string when present. |
| `due_date` | Due date as ISO date string when present. |
| `vendor_name` | Vendor/supplier name from confirmed metadata or fallback. |
| `document_number` | Incoming invoice/document number when present. |
| `total_amount` | Numeric total amount. |
| `currency` | Currency code. |
| `vat_amount` | Numeric visible VAT amount when present; not VAT reporting truth. |
| `payment_method` | `cash`, `card`, `bank_transfer`, `unknown`, or blank-derived unknown. |
| `purchase_subject` | Short factual purchase subject from metadata. |
| `category_id` | Confirmed category id or Python-derived `uncategorized`. |
| `category_label` | Category label snapshot or `Bez kategorie`. |
| `category_source` | Category source or Python-derived `missing_category`. |
| `category_review_required` | Boolean flag copied/derived from confirmed category metadata. |
| `line_item_count` | Count of stored line items in metadata. |

The runtime must not expose `original_path`, `metadata_path`, absolute storage
paths, raw OCR text, file ids, or full metadata JSON to generated analysis
code.

`category_id` and `category_label` are confirmed/intake metadata labels only.
They are not tax deductibility, accounting approval, VAT classification, or
export mapping.

For category questions, Python must provide an `allowed_categories` catalog with
active `category_id` values, display labels, and safe aliases. Python may also
provide `category_filter_hints` resolved from the user question, for example
`pálne` / `palivo` / `fuel` / `pohonné látky` / `пальне` ->
`vehicle_fuel`. Generated code must filter categories primarily by `category_id`
signaled by this Python-provided catalog. LLM must not invent translated category labels
or filter by guessed labels such as `pohonné látky` when the catalog contains
`vehicle_fuel` / `Palivo`.

## Current Date

Python injects `current_date` and sends `current_date_iso` to the planner.

Generated code must use `current_date` for "today", "this month", "this year",
and relative comparisons. It must not rely on model memory or training-time
date assumptions.

## Planner Output

The planner returns strict JSON only:

```json
{
  "analysis_code": "df = accounting_documents_df.copy()\nresult = {...}",
  "answer_language": "sk",
  "reasoning_summary": "short bounded explanation"
}
```

`answer_language` is metadata only. Python owns final user-facing answer
language.

`analysis_code` must assign a JSON-serializable dict to variable `result`.

Required `result` shape:

```json
{
  "summary": {},
  "tables": {},
  "warnings": [],
  "answer_hints": []
}
```

Allowed analysis patterns:

- count documents;
- sum totals by currency;
- filter by issue/tax/due date;
- compare periods;
- group by vendor, Python-provided category_id, document type, currency, month, or year;
- bounded list of matching receipts/incoming invoices;
- average/top-N style read-only summaries.

Write requests such as edit, delete, export, sync, upload, create category,
mark paid, or create a report file should produce a refusal in
`warnings` / `answer_hints` and no side effect.

## Planner Repair Loop

If the first generated plan fails parsing, AST validation, or sandbox
execution, Python may send structured repair feedback back to the planner. The
planner must return a complete replacement `analysis_code` for the same user
question. Python still validates and executes the repaired code through the
same safe executor.

Logs should include sanitized stop reason, stage, attempt number, source
channel, and row count. Logs must not expose cross-tenant data, storage paths,
secrets, raw OCR text, or broad raw persisted content.

## Final Answer Language

Final accounting document analytics answers use Slovak business language by
default.

The final answer LLM must use only Python-computed facts and safe dataset
metadata. It must not mirror Ukrainian, Russian, or mixed user input.

## Safe Executor

The runtime reuses the safe analytics executor policy:

- no imports;
- no SQL/DB access;
- no file/network/system calls;
- no write/export pandas methods;
- no function/class/lambda/loop/comprehension policy violations;
- isolated child-process execution with timeout;
- bounded output size.

Allowed initial names:

- `accounting_documents_df`;
- `pd`;
- `current_date`;
- limited pure builtins.

## User-Facing Status

Product Truth status: `partial`.

Supported:

- read-only analysis of confirmed receipts and incoming invoices;
- current workspace only;
- text and voice top-level entry through the existing resolver path;
- empty dataset handling without workspace creation;
- deterministic safe fallback when planning/execution fails.

Unsupported:

- outgoing invoice analytics in this action;
- bank statements, cashflow, VAT/tax advice, tax deductibility, bank matching,
  accounting export, or full accounting analytics;
- editing, deleting, creating categories, syncing, uploading, or writing files;
- cross-tenant analysis;
- direct user-provided SQL or uploaded spreadsheets.

## Evaluation Requirements

Tests/evals must prove:

- workspace scoping;
- no path/raw OCR exposure;
- old metadata without category or line items remains readable;
- missing workspace is safe and read-only;
- common accounting-document analytics questions resolve to
  `accounting_document_analytics`;
- outgoing invoice analytics questions remain in `invoice_analytics`;
- add/show receipt actions are not stolen by analytics;
- voice can reach the top-level analytics action;
- generated code rejects imports, SQL/DB access, file/network/system calls,
  and write-style operations;
- multilingual category wording resolves through Python-provided category ids,
  not invented translated category labels;
- Product Truth and InfoHelp report the capability as partial, not full
  accounting analytics.
