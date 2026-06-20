# Invoice Analytics Runtime Contract

Status: partial runtime pilot as of 2026-06-16.

This contract follows `docs/llm/Safe_Data_Analyst_Runtime_Checklist.md`.

This contract defines the bounded runtime for canonical top-level action
`invoice_analytics`.

The action is a read-only, AI-assisted analysis surface over already saved
outgoing invoice rows for the currently authorized supplier. It is not a full
accounting analytics engine, not tax advice, not a receipt/incoming-invoice
report, and not a write surface.

## Authority Split

Python owns:

- authorization and supplier identity;
- tenant-scoped DB reads;
- dataframe construction and column selection;
- current runtime date injection;
- allowed dataset catalog;
- LLM plan validation;
- AST validation and restricted code execution;
- final side-effect decision: no writes are allowed;
- user-facing fallback when planning or execution fails.

LLM may:

- draft a short Python analysis plan over Python-provided data bounds;
- select filters, groupings, counts, sums, comparisons, and list projections;
- draft final wording from Python-computed results.

LLM must not:

- query SQLite or run SQL;
- read or write files;
- import modules;
- access network/system resources;
- mutate invoices, status, PDFs, contacts, receipts, or accounting documents;
- invent facts not present in the computed result;
- claim support for incoming invoices, receipts, bank matching, VAT/tax advice,
  accounting export, or external storage.

## Canonical Action

`invoice_analytics` is a top-level action only when Python includes it in
`allowed_actions`.

It owns:

- an internal deterministic yearly count/total fast path for current,
  previous, or explicit calendar year questions;
- `show_existing_invoice`: read-only view of one persisted outgoing invoice;
- `edit_existing_invoice`: persisted invoice edit FSM;
- `delete_existing_invoice`: confirmation-gated persisted invoice deletion.

`invoice_period_summary` is no longer a competing user-facing top-level
resolver action. The yearly period summary remains supported as an internal
strategy under `invoice_analytics`; month-specific, multi-month, comparison,
customer, status, grouping, list, and average questions must stay in the safe
analytics runtime instead of falling into yearly-only guidance.

Before using the internal yearly fast path, Python must establish that the
question is exactly a whole-calendar-year count/total summary. This gate must
not depend on a partial dictionary of month or quarter names. When an LLM is
available, Python should use a bounded strategy decision with outputs such as
`whole_calendar_year_summary`, `safe_analytics_runtime`, and `unknown`.
Questions about months, quarters, custom date ranges, customers, statuses,
comparisons, lists, averages, top rankings, or ambiguous periods must choose
`safe_analytics_runtime`.

## Dataset Boundary

The runtime builds one dataframe: `invoices_df`.

Scope:

- current authorized supplier only;
- `invoice.supplier_telegram_id = current user id`;
- contact join is also supplier-scoped;
- missing DB means an empty dataframe, not DB creation.

Columns exposed:

| Column | Meaning |
|---|---|
| `invoice_id` | Internal invoice id from the current supplier dataset. |
| `invoice_number` | Invoice number string. |
| `issue_date` | Issue date as ISO date string. |
| `delivery_date` | Delivery date as ISO date string. |
| `due_date` | Due date as ISO date string. |
| `total_amount` | Numeric total amount. |
| `currency` | Currency code. |
| `invoice_status_raw` | Raw invoice lifecycle status stored on the invoice row; it is not payment truth. |
| `payment_status_canonical` | Python-normalized bot payment state: `pending_payment`, `paid`, `overdue`, or `unknown`. |
| `payment_status_label` | Human-readable label for `payment_status_canonical`. |
| `payment_status_source` | Source of the normalized payment status, such as `invoice_followup_state`, `derived_missing_followup_state`, `missing_payment_status`, `missing_due_date`, or `invoice_followup_state_unknown`. |
| `customer_name` | Supplier-scoped contact display name or fallback. |
| `contact_id` | Current supplier contact id or null. |
| `has_pdf` | Boolean flag that a PDF path exists. |

The runtime must not expose `pdf_path` or absolute storage paths to generated
analysis code.

`payment_status_canonical` is the only column generated analytics code should
use for paid, pending-payment, and overdue questions. Python derives it from
`invoice_followup_state.payment_status`, `due_date`, and the injected
`current_date`: paid follow-up state becomes `paid`; not-paid invoices before
today become `overdue`; not-paid invoices due today or later become
`pending_payment`; missing or inconsistent required fields become `unknown`.
Missing follow-up rows are treated as a legacy not-paid state and are labelled
with source `derived_missing_followup_state`. This is the bot's stored/derived
payment state, not bank-confirmed settlement; bank reconciliation is not
implemented in this pilot.

## Current Date

Python injects `current_date` and sends `current_date_iso` to the planner.

Generated code must use `current_date` for "today", "this month", "this year",
and relative comparisons. It must not rely on model memory or training-time
date assumptions.

## Planner Output

The planner returns strict JSON only:

```json
{
  "analysis_code": "df = invoices_df.copy()\nresult = {...}",
  "answer_language": "sk",
  "reasoning_summary": "short bounded explanation"
}
```

`answer_language` is retained only as planner metadata/legacy shape. It must
not control the final user-facing business answer language.

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

Before writing `analysis_code`, the planner prompt must require an internal
workflow:

1. normalize the user request into Slovak FakturaBot business semantics;
2. identify the analysis kind, such as sum, count, list, comparison, grouping,
   average, or payment-status analysis;
3. identify the exact period, such as explicit year, current year, month or
   months, date range, relative period, or `unknown`;
4. choose the date column: `issue_date` by default for issued invoices,
   `delivery_date` for delivery/service-date wording, and `due_date` for
   due-date/splatnost wording;
5. identify row filters such as customer, currency,
   `payment_status_canonical`, month numbers, years, or date range;
6. identify only the required `invoices_df` columns from the data catalog;
7. write sandbox-safe pandas code;
8. self-check that the code answers the normalized question and returns the
   facts required for the final Slovak business answer.

The planner may record the concise normalized plan in `reasoning_summary`, but
the final user-facing answer is still generated only after Python validates
and executes the code.

Allowed analysis patterns:

- count invoices;
- sum totals by currency;
- filter by issue/delivery/due date;
- compare periods;
- group by customer, currency, `payment_status_canonical`, month, or year;
- count or sum invoices by `pending_payment`, `paid`, `overdue`, or `unknown`;
- list a bounded number of matching outgoing invoices.

Write requests such as mark paid, edit, delete, send, archive, upload, or
generate should produce a refusal in `warnings` / `answer_hints` and no side
effect.

## Planner Repair Loop

If the first generated plan fails parsing, AST validation, or sandbox
execution, Python should not immediately show the user a generic failure when a
bounded repair attempt remains available.

Python may send structured repair feedback back to the planner:

```json
{
  "stage": "planning|execution",
  "error_type": "InvoiceAnalyticsPlanError|AnalyticsCodeValidationError|AnalyticsExecutionError",
  "error_reason": "short validator/runtime reason",
  "previous_analysis_code": "previous generated code when available"
}
```

The planner must return a complete replacement `analysis_code` for the same
user question. Python still validates and executes the repaired code through
the same safe executor. Only after the configured repair attempts are exhausted
may the handler show a safe fallback to the user.

Server/runtime logs should include the stop reason, error type, attempt number,
channel, and sanitized dataset row count. Logs must not expose cross-tenant
data, PDF paths, DB paths, secrets, or broad raw persisted content.

## Final Answer Language

Final invoice analytics answers use Slovak business language by default.

The user may ask in Slovak, Ukrainian, Russian, or mixed/STT-noisy language.
The planner may understand multilingual input, but it must not choose the
final business language. Python owns the final answer language policy and
passes a controlled Slovak setting to the answerer.

The final answer LLM must be instructed to answer in Slovak business language
and to use only the Python-computed result plus safe dataset metadata. Planner
`answer_language` values such as `uk`, `ru`, or `mixed` must not override the
Slovak business-answer policy.

## Safe Executor

The safe executor validates generated code with Python AST checks before
execution.

Forbidden:

- imports;
- function or class definitions;
- lambda/global/nonlocal;
- dunder attributes or calls;
- `eval`, `exec`, `compile`, `open`, `input`, `globals`, `locals`, `vars`,
  `dir`, `getattr`, `setattr`, `delattr`, `__import__`;
- `os`, `sys`, `subprocess`, `socket`, `requests`, `pathlib`, `sqlite3`,
  `shutil`;
- pandas write-style calls such as `to_sql`, `to_pickle`, `to_csv`,
  `to_excel`, and `to_json`;
- while loops and context managers.

Allowed initial names:

- `invoices_df`;
- `pd`;
- `current_date`;
- limited pure builtins such as `len`, `int`, `float`, `str`, `bool`, `round`,
  `min`, `max`, `sum`, `list`, `dict`, `set`, `tuple`, `sorted`, and `range`.

Execution is time-limited. Oversized results are truncated to a bounded output
shape before final answer generation.

## User-Facing Status

Product Truth status: `partial`.

Supported:

- read-only analysis of saved outgoing invoices;
- current supplier only;
- text and voice top-level entry through the existing resolver path;
- empty dataset handling without DB creation;
- deterministic safe fallback when planning/execution fails.

Unsupported:

- incoming invoices and receipts analytics;
- bank statements, cashflow, accounting export, VAT/tax advice;
- editing, deleting, marking paid, sending, archiving, or PDF generation;
- cross-tenant analysis;
- direct user-provided SQL or uploaded spreadsheets.

## Evaluation Requirements

Tests/evals must prove:

- supplier scoping;
- no PDF path exposure;
- missing DB is safe and read-only;
- common analytics questions resolve to `invoice_analytics`;
- yearly summary wording routes to `invoice_analytics` and may use the internal deterministic yearly fast path;
- voice can reach the top-level analytics action;
- generated code rejects imports, SQL/DB access, file/network/system calls, and
  write-style operations;
- Product Truth and InfoHelp report the capability as partial, not supported
  full accounting analytics.
