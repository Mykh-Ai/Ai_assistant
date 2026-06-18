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
- test relative-date behavior;
- include relative-date queries in server smoke tests.

## 3.7 Planner Prompt Checklist

The planner prompt must explicitly say:

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
- voice reachability if supported;
- old action compatibility;
- no side effects;
- safe fallback;
- final answer language is Slovak business language.

Product UX smoke:

- real natural-language questions;
- unsupported domain request;
- write request refusal;
- server/container smoke;
- Telegram smoke.

## 3.15 Required Implementation Order For Future Analytics Domains

Before coding:

1. define domain and dataset;
2. define category/status/business semantics;
3. define Product Truth status;
4. define unsupported boundaries;
5. define final answer language policy;
6. define planner prompt;
7. define executor policy;
8. define tests and smoke checklist.

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
5. Telegram smoke.

## 3.16 Known Invoice Pilot Failure Cases

1. Status semantics:
   Raw invoice status was not payment status. Fix: split `invoice_status_raw`
   and `payment_status_canonical`.

2. LLM boilerplate imports:
   LLM generated `import pandas as pd` and `from datetime import datetime`.
   Fix: prompt tightening plus a narrow normalizer for harmless boilerplate
   only.

3. Runtime timeout/process mode:
   Docker/Linux execution hit timeout and `spawn` was unstable/slow. Fix:
   realistic timeout plus Linux/Docker forked process while preserving
   terminate/kill.

4. Final answer language:
   LLM mirrored Ukrainian input and answered in Ukrainian. Required fix:
   Python-owned final answer language policy with Slovak business output by
   default.
