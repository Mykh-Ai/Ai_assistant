# Runtime Issue Autorepair Workshop Log

Append-oriented sanitized workshop log. Receipts, evidence, findings, repairs,
and production events appear here only after they are verified.

## ARL-20260730-001 - Durable source receipt

- Issue: `IR-20260730-5FA71FDFFCDE`
- Handoff: `RH-20260730-E60821130D35`
- Received at: `2026-07-30T17:55:23.486934+00:00`
- Sanitized observation: the bot did not understand the preceding request to
  record an issue; the underlying reported problem was in the preceding STT
  interaction.
- Recorded context: text intake, no active FSM, bounded Stage 1 context only.
- Manifest digest:
  `sha256:e3f6f93aa6b6f0b44914e498dedbc7f4ee8b5ee9f5bfef0f78512c8548130760`
- Repository main SHA: `715c5941076f9f952f000daeae19a119bf4679d5`
- Deployed SHA: `632e9b08dcf8ac5583ec98632ff1a89417972cab`
- Finding creation: deferred until bounded evidence-based diagnosis.
- Code changed: no.
- Production changed: no.

## ARL-20260730-002 - Finding and repair ready for review

- Finding: `IR-20260730-5FA71FDFFCDE-F01`
- Parent issue: `IR-20260730-5FA71FDFFCDE`
- Classification: `confirmed_low_risk_defect`
- Status: `patch_ready_for_review`
- Owner scope: code.
- Sanitized evidence: an explicit noisy/Cyrillic customer reference reached
  outgoing-invoice analytics without a canonical tenant-scoped customer
  identity bridge. The current exact/confirmed-alias lookup did not match that
  spoken form, while the tenant contact existed under its canonical name.
- Root cause: analytics passed the raw question directly to the planner and did
  not reuse a bounded current-tenant contact selection before filtering.
- Repair: bounded customer selection now receives only unique current-tenant
  contact names plus `unknown`; Python prefilters the sanitized dataframe by
  trusted `contact_id`. Planner validation rejects a second raw customer-name or
  contact-id filter after that prefilter.
- Self-learning: no alias was saved because a read-only analytics result is not
  explicit confirmation of a reusable contact alias.
- Repair branch:
  `autorepair/IR-20260730-5FA71FDFFCDE-F01-invoice-analytics-customer`
- Repair commit: `0f061d2035b3fad93c48ecda4267d8a052be7103`
- Draft PR: `https://github.com/Mykh-Ai/Ai_assistant/pull/54`
- Verification: 54 focused tests passed; 469 adjacent analytics/Product
  Truth/InfoHelp/voice tests passed; full repository suite passed with 2376
  tests and 7 subtests; compileall and diff-check passed.
- Manual/live acceptance: not run; production observation was used only as
  bounded diagnostic evidence.
- Code changed: yes, in the review branch only.
- Production changed: no.
- Merge/deploy: not performed.
- Next action: human review of Draft PR #54.

## ARL-20260730-003 - Correction: missed routing defect and incomplete repair scope

- Correction trigger: the user explicitly pointed out that the first word of
  the recorded STT was the Ukrainian word for "Problem" and that the bot
  launched analytics instead of recognizing a problem report.
- Original-session failure: despite the user's earlier emphasis that the
  preceding STT produced an unusual situation, the repair agent misread the
  entire STT as an analytics request. It diagnosed only the defect described
  inside the report and incorrectly marked the source issue `resolved`.
- Bounded log evidence subsequently verified this sequence:
  1. `invoice_stt_result` contained a report beginning with the Ukrainian word
     for "Problem";
  2. the immediately following `top_level_intent_resolved` event selected
     `invoice_analytics` for that complete report text.
- The user was reporting a problem. The embedded phrase describing "when I ask
  the bot" referred to an earlier analytics interaction; it was not the
  current request to run analytics.

### Finding IR-20260730-5FA71FDFFCDE-F02

- Classification: `insufficient_evidence`.
- Status: `needs_more_diagnostics`.
- Observed defect: a voice problem report was routed to `invoice_analytics`
  instead of the implemented problem-report/intake boundary.
- What is proven: STT preserved the problem-report wording, and the top-level
  resolver selected the wrong action immediately afterward.
- What is not yet diagnosed: the exact resolver/precedence mechanism that
  allowed embedded invoice-analytics language to override the report speech
  act, the correct existing owner to reuse, and the smallest safe repair.
- Required next action: inspect the top-level problem-report route, canonical
  action bounds, resolver hints, voice convergence, and focused tests; add a
  failing regression for this exact report shape before any code change.
- Code changed: no.
- Production changed: no.

### Scope correction for IR-20260730-5FA71FDFFCDE-F01 / Draft PR #54

- Required flow stated by the report: extract the customer reference from an
  ordinary analytics request, pass it through the same controlled contact
  resolution chain used by invoice creation (exact, normalized, confirmed
  alias, fuzzy where allowed, then bounded LLM/unknown), obtain canonical
  `contact_id`, and only then run invoice analytics.
- Draft PR #54 implements only part of this flow: bounded selection among
  current-tenant canonical contact names followed by Python `contact_id`
  prefiltering and a planner re-filter guard.
- Draft PR #54 does not currently reuse the full existing exact/normalized/
  confirmed-alias/fuzzy contact-resolution chain. It must not be described as
  complete fulfillment of the reported requirement without revision and new
  acceptance evidence.

### Canonical documents used but omitted from the original report

- `AGENTS.md`;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`;
- `docs/llm/Invoice_Analytics_Runtime_Contract.md`;
- `docs/llm/Safe_Data_Analyst_Runtime_Checklist.md`;
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/TZ_FakturaBot.md`.

- Corrected source status: `partially_resolved`.
- Merge/deploy: not performed.

## ARL-20260730-004 - F01 corrected, merged, and deployed; F02 remains deferred

### What the reported analytics defect meant

The actionable F01 requirement was not to treat the whole STT transcript as a
contact identity and not to let the analytics planner guess a company from raw
speech. For an ordinary invoice-analytics question that contains a company
name, the correct path is:

1. voice is transcribed by STT into the complete text;
2. Python-owned top-level routing selects `invoice_analytics`;
3. a bounded extractor returns only the minimal explicit company/customer
   reference or `null`;
4. Python reuses the invoice-generation tenant-scoped contact resolver:
   exact name -> normalized name -> confirmed contact alias ->
   high-confidence fuzzy match;
5. only if that chain is unresolved, bounded LLM selection receives
   Python-provided current-tenant contact candidates;
6. Python obtains the canonical `contact_id` and prefilters `invoices_df`;
7. the analytics planner runs only on that trusted scope and cannot apply a
   second raw-name/contact-id filter.

### Why the first repair was incomplete

Draft PR #54 originally formed the tenant dataframe and then asked a bounded
LLM to choose a canonical contact directly from the full analytics question.
That was tenant-scoped, but it bypassed the confirmed-alias and deterministic
contact-resolution chain already used by invoice generation. The confirmed
alias regression was made to fail against that implementation before the
correction.

### Final F01 repair

- Added strict JSON extraction of `customer_reference` only; the extractor
  does not see the contact list, choose a saved contact, or write an alias.
- Reused `ScopedInvoiceRuntime.resolve_contact_lookup()` through the existing
  invoice handler owner, preserving exact/normalized/confirmed-alias/fuzzy
  order.
- Kept `_resolve_customer_candidate_bounded()` only as the final fallback.
- A confirmed alias now resolves before any bounded fallback.
- An explicit unresolved customer now receives a clarification and stops before
  planner execution; it cannot silently become analytics over all invoices.
- General questions whose extractor returns `null` remain unscoped within the
  active tenant.
- No contact, alias, invoice, PDF, DB schema, storage, or historical data was
  changed by the analytics flow.

### Canonical documents used

- `AGENTS.md`;
- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Product_Truth_Registry_MVP_Design.md`;
- `docs/Self_Learning_Layer.md`;
- `docs/Confirmed_Semantic_Alias_Learning_Contract.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/Product_UX_Eval_Artifacts.md`;
- `docs/TZ_FakturaBot.md`;
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`;
- `docs/llm/Invoice_Analytics_Runtime_Contract.md`;
- `docs/llm/Safe_Data_Analyst_Runtime_Checklist.md`;
- `docs/local-only/FakturaBot_Server_Agent_Context.md`;
- `Skils/OfficeFlow_Interactive_Repair_SKILL.md`.

### Verification and publication

- Repair commit: `7d6f43f603a2661ed6d50a8244b20284a680d30e`.
- PR: `https://github.com/Mykh-Ai/Ai_assistant/pull/54`.
- Merge/deployed SHA: `2379869c6f609624082fc36eb1e088174e554154`.
- Focused/adjacent suite: 546 passed.
- Full 92-file inventory: 2385 passed and 7 subtests passed.
- Compileall and diff-check passed.
- Pre-deploy DB backup:
  `/var/backups/fakturabot/20260730T211228Z_pre_pr54_invoice_analytics_alias/`.
- Active and backup SQLite SHA-256 matched exactly; `integrity_check` returned
  `ok`.
- Production container is running with restart count zero; polling started and
  no matching error/traceback marker was present.
- Production-image temporary-DB smoke proved Cyrillic confirmed-alias lookup
  and strict customer-reference parsing. A real Telegram voice acceptance was
  not automated.

### Deferred F02

Finding `IR-20260730-5FA71FDFFCDE-F02` remains exactly
`needs_more_diagnostics`. No top-level/runtime-issue routing code, hint,
precedence, action registry, or test was changed in this repair. The source
issue therefore remains `partially_resolved`.

### Post-deploy documentation publication

- Post-deploy truth was committed as
  `822852f67ca65232026eb1be9e1c46217b5c47fc`, merged through docs-only PR #55
  as `d106150ab943fba481d90b4468fb8ef96e993e56`, and fast-forwarded to the
  clean server repository without rebuilding or restarting the already healthy
  runtime container. Repository `main` is therefore `d106150...`; the running
  application image remains the verified F01 runtime from `2379869...`.

## ARL-20260731-005 - F02 diagnosed and repaired for review

### Finding

- Finding: `IR-20260730-5FA71FDFFCDE-F02`.
- Classification: `confirmed_low_risk_defect`.
- Status: `patch_ready_for_review`.
- Owner scope: code.
- Code changed: yes.
- Production changed: no.

### Diagnosis

The recorded `invoice_stt_result` preserved the first problem-report word, but
idle voice then entered the generic `top_level_action` resolver. The complete
report contained invoice/company/analytics language, so the current report
speech act competed with the business actions described inside it. The idle
route had no deterministic first-token support boundary, and its tests mocked
the resolver instead of exercising this collision.

### Repair

- Added an exact first-meaningful-token boundary for `проблема`, `помилка`,
  `баг`, `chyba`, `problem`, `bug`, and `error`.
- Authorized administrators bypass the business resolver and reuse the existing
  sanitized runtime issue capture.
- Active administrator FSM state/data remain unchanged.
- Authorized non-admin idle users reuse the existing confirmation-gated
  admin-review request preview; no row is saved before approval.
- Active non-admin FSM ownership remains unchanged; no nested/suspended FSM
  architecture was introduced.
- A bare marker requests a complete description. Embedded or alphanumeric
  occurrences such as `Error123` do not trigger the boundary.
- No self-learning hook was added because these are deterministic support
  control markers, not learned business aliases.

### Canonical documents used

- `AGENTS.md`;
- `Skils/OfficeFlow_Interactive_Repair_SKILL.md`;
- `docs/Product_Doctrine_2030.md`;
- `docs/AI_Layer_Implementation_Standards.md`;
- `docs/Product_Truth_Layer.md`;
- `docs/Product_Truth_Registry_MVP_Design.md`;
- `docs/Info_Help_Guidance_Layer.md`;
- `docs/Customization_Request_Layer.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/TZ_FakturaBot.md`;
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/llm/Bounded_Resolver_Prompt_Template.md`.

### Verification and publication

- Regression first: 8 F02 cases failed before the repair.
- Focused: 47 passed.
- Adjacent: 553 passed plus 7 subtests.
- Full suite: 2433 passed plus 7 subtests.
- Compileall and diff-check passed.
- Repair commit: `3964046e80cd368d46e2d5c4036b08a644183c37`.
- Draft PR: `https://github.com/Mykh-Ai/Ai_assistant/pull/57`.
- Merge, deployment, restart, migration, and production data writes: not run.
