# Safe Data Analyst Runtime Checklist

Status: reusable implementation checklist for read-only LLM-generated
analytics runtimes.

This checklist preserves the lessons from the first deployed
`invoice_analytics` pilot and should be used before adding any future
analytics domain such as invoice analytics, receipt/blocek analytics, incoming
invoice analytics, bank movement analytics, customer/contact analytics, or
broader business analytics.

## 3.1 Purpose

Use this checklist when:

- users ask arbitrary natural-language analytical questions;
- an LLM generates bounded Python/pandas analysis code;
- Python provides sanitized dataframe(s);
- Python validates and executes code in an isolated sandbox;
- an LLM writes the final human answer only from Python-computed facts.

This is read-only analytics. It is not a write/action runtime.

## 3.2 Authority Split

Python owns:

- authorization;
- tenant, user, and workspace scope;
- top-level action boundaries before analytics starts;
- unsupported-domain detection before analytics planning;
- execution strategy selection for deterministic fast path vs safe runtime;
- DB reads;
- dataframe construction;
- data catalog;
- current date injection;
- planner prompt;
- planner validation;
- code normalization;
- AST validation;
- process-isolated execution;
- timeout and terminate/kill behavior;
- result truncation;
- fallback behavior;
- final answer language policy.

LLM may:

- select only Python-provided bounded actions/options;
- interpret the user question;
- generate bounded analysis code over provided dataframe(s);
- count, sum, group, filter, compare, and list bounded rows;
- draft final wording from Python-computed facts.

LLM must not:

- read the DB;
- run SQL;
- access files;
- access network or system resources;
- import modules;
- mutate data;
- execute product actions;
- decide that an unsupported domain is supported;
- decide whether a deterministic fast path is eligible;
- invent facts;
- decide Product Truth;
- decide tenant identity;
- decide final business language policy.

## 3.3 Dataset/Data Catalog Checklist

Each analytics domain needs a curated data catalog. Every field must define:

- column name;
- type;
- business meaning;
- source table or service;
- tenant scope rule;
- whether it is visible to the LLM;
- whether it is raw/internal or normalized/business-safe;
- whether it is derived by Python;
- user-facing limitations.

Never expose raw DB schema directly to the LLM. Expose curated analytics
dataframe(s).

## 3.4 Business Semantics / Status Checklist

Raw status fields are not automatically business truth.

For every domain, separate:

- lifecycle/document status;
- business status;
- payment/settlement status;
- review/approval status;
- derived status;
- source of truth;
- confidence and limitations.

Invoice example:

- `invoice_status_raw` is raw lifecycle/document status.
- `payment_status_canonical` is Python-normalized payment state.
- `payment_status_source` explains the source.
- Payment status is bot stored/derived truth, not bank-confirmed settlement.

Receipt/blocek future example:

- OCR confidence is not accounting approval.
- Document type classification is not category confirmation.
- Uploaded file presence is not processed/accepted accounting evidence.
- Tax deductibility must not be inferred unless explicitly implemented and
  validated later.

## 3.5 Receipt/Blocek Analytics Prerequisite

Receipt/blocek analytics must not be implemented before receipt categorization
exists.

Required steps before `receipt_analytics`:

1. define receipt category taxonomy;
2. implement LLM/LMM category suggestion;
3. Python validates allowed categories;
4. user or deterministic rule confirms category when needed;
5. store category and category source/confidence;
6. expose only normalized category fields to analytics;
7. only then build `receipt_analytics`.

Do not jump directly from raw OCR or extracted receipt rows to broad analytics.

## 3.6 Current Date / Temporal Logic Checklist

Every analytics runtime must:

- inject `current_date` from Python;
- forbid reliance on model memory for dates;
- resolve phrases such as today, this month, this year, and last month through
  the injected date;
- route open-ended period language such as month names, quarters, seasons,
  relative ranges, and cross-language date phrases through the safe analytics
  runtime instead of finite dictionaries;
- allow deterministic period fast paths only after a bounded strategy gate
  proves the request is exactly the supported narrow case;
- test relative-date behavior;
- include relative-date queries in server smoke tests.

## 3.7 Planner Prompt Checklist

The planner prompt must explicitly say:

- first normalize the user request into the product's canonical business
  semantics and answer-language policy;
- identify the requested analysis kind, period, date column, metric, grouping,
  row filters, and required dataframe columns before writing code;
- available dataframe names;
- available columns;
- `pd` is already available if pandas is allowed;
- `current_date` is already available;
- do not import pandas;
- do not import datetime;
- do not redefine `current_date`;
- do not use SQL;
- do not access files, network, or system resources;
- start from a dataframe copy, for example `df = invoices_df.copy()`;
- assign the final JSON-serializable dict to `result`;
- keep result bounded;
- self-check that the generated code can answer the normalized question;
- use any Python-provided repair feedback to fix the same question instead of
  changing the scope;
- return strict JSON only.

## 3.8 Planner Normalization Checklist

The normalizer may strip only exact harmless boilerplate already supplied by
Python.

Allowed examples:

- exact or whitespace-variant `import pandas as pd`;
- exact or whitespace-variant `from datetime import datetime`;
- redundant `current_date = datetime.strptime(...)` when Python already injects
  `current_date`.

Do not strip broad imports. These must remain visible and be rejected:

- `import os`;
- `import sys`;
- `import sqlite3`;
- `from pathlib import Path`;
- `from subprocess import run`;
- `import pandas`;
- `import pandas as something_else`;
- `from datetime import date`;
- `from datetime import timedelta`.

Principle: the normalizer must not hide unsafe code.

## 3.9 Safe Executor Checklist

The executor must:

- AST-validate before execution;
- reject imports;
- reject function and class definitions;
- reject lambdas, `global`, and `nonlocal`;
- reject dunder access;
- reject forbidden builtins: `eval`, `exec`, `compile`, `open`, `input`,
  `globals`, `locals`, `vars`, `dir`, `getattr`, `setattr`, `delattr`, and
  `__import__`;
- reject forbidden modules/names: `os`, `sys`, `subprocess`, `socket`,
  `requests`, `pathlib`, `sqlite3`, and `shutil`;
- reject pandas write/export methods: `to_sql`, `to_pickle`, `to_csv`,
  `to_excel`, and `to_json`;
- reject loops or comprehensions if the current policy forbids them;
- execute in an isolated child process;
- enforce a hard timeout;
- terminate/kill the child process on timeout;
- limit output size;
- return a safe fallback on failure.

## 3.10 Runtime/Production Timeout Checklist

Local unit tests are not enough. Every analytics runtime needs:

- local mock smoke;
- server/container mock smoke;
- real Telegram smoke where relevant;
- production OS/container child-process mode verification;
- realistic Docker/Linux timeout verification;
- proof that hung code is still killed;
- proof that simple analytics does not hit timeout;
- proof that heavy or hung analytics is stopped safely.

Invoice pilot lesson:

- the early 2-second timeout was too low for Docker/Linux child process plus
  pandas startup;
- `spawn` was slow/unstable in the server handler path;
- `fork` worked better in Linux/Docker;
- timeout was increased to 10 seconds;
- terminate/kill remained required.

## 3.11 Final Answer Language Policy

For end-user business flows, final answers must use Slovak business language
by default.

Input may be Slovak, Ukrainian, Russian, or mixed/STT-noisy. The final
business answer must be Slovak, professional, and business-toned. Do not use
Ukrainian or Russian unless a future explicit admin/dev/debug mode or
workspace language setting is implemented.

Python owns final answer language policy. The LLM planner must not freely
choose final business language.

Implementation guidance:

- remove or ignore LLM-selected `answer_language` for final user-facing
  business answers;
- pass Python-controlled `final_answer_language = "sk"` to the answerer;
- prompt the final answer LLM with "Answer in Slovak business language.";
- test that Ukrainian input can produce Slovak output.

## 3.12 Product Truth Checklist

Every analytics runtime must define Product Truth status:

- `partial`;
- `supported`;
- `planned`;
- `unsupported`;
- `unknown`.

Pilots default to `partial`. Unsupported domains must be listed clearly.

Invoice pilot unsupported:

- receipts/bloceky;
- incoming invoices;
- bank matching;
- tax/VAT advice;
- write operations.

Receipt future warning: do not claim receipt category analytics until category
taxonomy, storage, confirmation, and tests exist.

## 3.13 Write-Operation Boundary Checklist

Analytics runtimes must never execute write actions.

If the user asks to mark paid, edit, delete, send, archive, upload, sync to
Drive, create a document, or change status, analytics must refuse or route to
a separate Python-owned write flow with preview and confirmation.

## 3.14 Testing Checklist

Dataset tests:

- tenant scope;
- no raw paths;
- empty dataset safe behavior;
- normalized business status fields;
- source/limitation fields.

Planner tests:

- valid strict JSON accepted;
- harmless boilerplate stripped;
- dangerous imports remain rejected;
- SQL rejected;
- filesystem/network/system attempts rejected;
- current date instructions present;
- final language policy not controlled by LLM.

Executor tests:

- count/sum/group/compare works;
- forbidden imports rejected;
- forbidden calls rejected;
- timeout kills child process;
- result bounded/truncated.

Handler tests:

- top-level routing;
- unsupported-domain guard before planning;
- deterministic fast-path eligibility and non-eligibility;
- nearby top-level actions that must not be captured by analytics;
- voice reachability if supported;
- old action compatibility;
- no side effects;
- safe fallback;
- repair loop behavior and sanitized stop-reason logging;
- final answer language is Slovak business language.

Product UX smoke:

- real natural-language questions;
- unseen phrasings not used while implementing the feature;
- unsupported domain request;
- nearby read/write object actions, for example show/edit/delete by explicit
  object number;
- write request refusal;
- server/container smoke;
- Telegram smoke.

## 3.15 Required Implementation Order For Future Analytics Domains

Before coding:

1. define domain and dataset;
2. define category/status/business semantics;
3. define Product Truth status;
4. define unsupported boundaries;
5. define top-level routing boundaries and nearby actions that analytics must
   not steal;
6. define deterministic fast paths, if any, and their bounded eligibility gate;
7. define repair-loop and sanitized logging behavior;
8. define final answer language policy;
9. define planner prompt;
10. define executor policy;
11. define tests and smoke checklist.

For bloceky specifically:

1. category taxonomy first;
2. category suggestion/confirmation;
3. category storage;
4. category Product Truth;
5. only then analytics runtime.

During coding:

1. dataset builder;
2. planner;
3. normalizer;
4. executor;
5. answerer;
6. handler route;
7. Product Truth/InfoHelp;
8. tests;
9. docs/logs.

Before commit:

1. full tests;
2. security audit;
3. diff check;
4. no untracked files;
5. Product Truth honest.

Before deploy:

1. build before restart;
2. dependency check;
3. startup logs;
4. server mock smoke;
5. Telegram smoke with unseen analytics phrasings;
6. Telegram smoke for nearby top-level actions that share vocabulary with
   analytics.

## 3.16 Failure Register And Repair Playbook

Every analytics runtime must keep an incident-style failure register. Do not
only document the final design. Record:

- user-visible symptom;
- root cause;
- implemented repair;
- prevention rule for future analytics domains;
- tests or smoke that prove the repair.

### 3.16.1 Invoice Pilot Failures Before 2026-06-20

1. Status semantics:
   raw invoice status was treated too close to payment status.
   Fix: split `invoice_status_raw`, `payment_status_canonical`,
   `payment_status_label`, and `payment_status_source`.
   Prevention: every analytics domain must define business-safe derived status
   fields before exposing status to planner code.

2. LLM boilerplate imports:
   the planner generated `import pandas as pd` and
   `from datetime import datetime`.
   Fix: prompt tightening plus a narrow normalizer for harmless boilerplate
   only.
   Prevention: prompt must say which objects are already injected, while the
   executor must still reject remaining imports.

3. Runtime timeout/process mode:
   Docker/Linux execution hit timeout and `spawn` was unstable/slow.
   Fix: realistic timeout plus Linux/Docker forked process while preserving
   terminate/kill.
   Prevention: every new analytics runtime needs server/container smoke, not
   only local unit tests.

4. Final answer language:
   LLM mirrored Ukrainian input and answered in Ukrainian.
   Fix: Python-owned final answer language policy with Slovak business output
   by default.
   Prevention: planner metadata must never own final user-facing business
   language.

### 3.16.2 Invoice Analytics Failures Fixed On 2026-06-20

1. Unsupported-domain guard implied an active confirmation without always
   entering a confirmation state.
   Symptom: receipt/expense analytics wording could show plain guidance that
   sounded like a pending admin-review confirmation step.
   Fix: safe unsupported business analytics requests now start the existing
   customization request preview flow with approve/edit/cancel controls; no
   request is saved before approval.
   Prevention: if copy says the user can approve or submit a request, Python
   must already be in the matching confirmation state. Otherwise the wording
   must not imply an active confirmation.

2. Yearly invoice summary fast path was too broad.
   Symptom: month or multi-month invoice questions could be captured by a
   deterministic yearly summary path or return misleading "whole year only"
   wording.
   Fix: `invoice_period_summary` was demoted from the public top-level routing
   surface. Simple whole-calendar-year summaries are now an internal fast path
   inside `invoice_analytics`.
   Prevention: fast paths must be internal optimizations only after a bounded
   decision proves the request is exactly the supported narrow case.

3. Period handling relied on partial word lists.
   Symptom: adding names for March/May would still leave holes such as other
   months, quarters, seasons, relative ranges, or mixed-language period
   wording.
   Fix: Python now asks a bounded execution-strategy decision:
   `whole_calendar_year_summary` or `safe_analytics_runtime`. Any month,
   quarter, custom date range, comparison, customer/status/list/top/average, or
   ambiguous-period request must reach the safe analytics runtime instead of a
   finite period dictionary.
   Prevention: do not solve open-ended temporal analytics with language
   dictionaries. Use a bounded strategy gate, then let the planner interpret
   the period inside the safe runtime.

4. Planner failure produced a user-facing stop without enough repair context.
   Symptom: users saw "Analyticky vypocet som zastavil..." while operators did
   not get a clear enough reason or the model did not get a chance to repair
   safe generated code.
   Fix: planning, validation, and execution failures are logged with sanitized
   reason, stage, attempt, source channel, and row count. Python sends
   structured `repair_feedback` back to the planner before showing final
   fallback.
   Prevention: every LLM-generated analytics code runtime needs at least one
   bounded repair attempt and durable sanitized logs for stop reasons.

5. Existing-invoice actions conflicted with analytics.
   Symptom: `show invoice 04` / `покажи фактуру 04` could be interpreted as
   invoice analytics because the words "show" and "invoice" looked analytical.
   Fix: explicit existing-invoice number references now prioritize
   show/edit/delete existing-invoice flows before analytics. Plain four-digit
   years such as `2026` are not treated as invoice numbers.
   Prevention: nearby write/read actions must have smoke tests next to
   analytics tests. Analytics must not steal explicit object-reference actions.

6. Real Telegram smoke exposed behavior that unit-only checks missed.
   Symptom: deployed behavior around multi-period questions and safety-stop
   answers differed from the intended architecture.
   Fix: added local smoke tests with unseen natural-language analytics
   questions, explicit show/edit invoice references, and unsupported expense
   analytics wording.
   Prevention: every future analytics layer needs smoke queries that were not
   used during implementation, plus nearby top-level action smokes.

## 3.17 Current Analytics Layer Model As Of 2026-06-20

The current model for read-only LLM-generated analytics is:

1. Top-level routing:
   Python provides bounded canonical actions. LLM may select only from those
   actions or `unknown`.

2. Unsupported-domain guard:
   before analytics planning, Python checks for domains that are not supported
   by the current runtime, such as receipt/expense, incoming invoice, bank,
   cashflow, VAT, and tax analytics. Safe unsupported business analytics starts
   customization request preview; dangerous or unsupported writes do not enter
   analytics.

3. Execution strategy gate:
   Python decides whether the request is the narrow deterministic whole
   calendar-year summary case or must use safe analytics runtime. The gate is
   bounded to:
   - `whole_calendar_year_summary`;
   - `safe_analytics_runtime`;
   - `unknown`.

4. Deterministic fast path:
   only exact whole-calendar-year count/total of saved outgoing invoices may use
   the deterministic invoice period summary. It is an internal optimization,
   not a general period resolver.

5. Planner runtime:
   for all other supported invoice analytics, the planner must first normalize
   the user request into Slovak FakturaBot product semantics, identify the
   requested period and metric, choose dataframe columns and filters, generate
   bounded pandas code, and self-check that the code can answer the normalized
   question.

6. Python validation and execution:
   Python validates the plan, normalizes only known harmless boilerplate,
   AST-validates the code, executes it in an isolated timeout-controlled
   process, bounds the result, and prevents DB, file, network, system, import,
   and write access.

7. Repair loop:
   if planning, validation, or execution fails, Python logs the sanitized stop
   reason and gives the planner structured repair feedback. Only after repair
   attempts are exhausted does the user see a safe fallback.

8. Final answer:
   final user-facing business answers are Slovak by Python policy. The final
   answer LLM may verbalize only Python-computed facts and limitations.

9. Side effects:
   analytics remains read-only. It must not create, edit, delete, send, archive,
   save, sync, or mutate any business object.

## 3.18 Future Analytics Layer Prevention Rules

When implementing a similar analytics layer:

1. Do not begin with phrase dictionaries for open-ended natural-language
   periods. Start with a bounded execution strategy and a planner contract.

2. Do not add a deterministic shortcut unless its exact eligibility is proven
   before it runs and tested against nearby non-eligible requests.

3. Do not let analytics capture explicit object actions such as show/edit/delete
   invoice by number.

4. Do not show confirmation-like wording unless the corresponding confirmation
   state and keyboard are active.

5. Do not stop at "safe fallback" logging. Log sanitized reason, stage, attempt,
   source channel, and row count, then provide repair feedback to the planner.

6. Do not mark the layer ready until tests include:
   - unseen analytics phrasings;
   - unsupported-domain guard phrasings;
   - nearby top-level actions;
   - empty dataset behavior;
   - real or mock server/container smoke;
   - Telegram smoke for the production interface when the bug was found there.
