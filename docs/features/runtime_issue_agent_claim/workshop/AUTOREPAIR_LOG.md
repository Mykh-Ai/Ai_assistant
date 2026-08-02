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

## ARL-20260731-006 - F02 merged and deployed

### Publication

- PR #57 was moved from draft to ready and merged after its head SHA was
  verified as `3964046e80cd368d46e2d5c4036b08a644183c37`.
- Merge and deployed SHA:
  `4a69b312226b7c4254427f3c3c1b0a99243647c8`.
- Production repository is clean on `main` and matches `origin/main`.
- Standard production compose rebuild recreated and started `fakturabot`.
- The running image is
  `sha256:0c37c9aa7278667769628fb1c20a40a6ac1d10bcf91645e8f56d25a1efa0e27b`.

### Production verification

- Container state: running, restart count zero.
- Runtime log confirms `FakturaBot starting`, aiogram polling, invoice
  follow-up scheduler, Google Drive archive scheduler, and the fourteen-day
  Contact Registry monitor all started.
- The runtime image intentionally does not include the pytest development
  dependency, so repository tests were not rerun inside production.
- Pre-merge verification remains: 47 focused tests; 553 adjacent tests plus
  7 subtests; 2433 full tests plus 7 subtests; compileall and diff-check passed.
- A real Telegram voice acceptance was not automated and remains the only
  stated acceptance gap.

### Change boundary

- Code and production runtime changed: yes.
- DB schema, persisted business data, environment configuration, and storage
  paths changed: no.
- Source issue `IR-20260730-5FA71FDFFCDE` is resolved by deployed findings F01
  and F02.

## ARL-20260801-007 - Resolved source handoff redelivery reconciliation

### Receipt

- Source issue: `IR-20260730-5FA71FDFFCDE`.
- Handoff: `RH-20260730-E60821130D35`.
- Manifest digest: `sha256:e3f6f93aa6b6f0b44914e498dedbc7f4ee8b5ee9f5bfef0f78512c8548130760`.
- Received again at `2026-08-01T19:01:17.4746261Z` after Agent Claim was
  deployed at repository SHA `465df389c1b0c6ad3281733fe7888f5b49122c1d`.
- Existing Workshop truth already classifies both findings as resolved and
  deployed. No duplicate source receipt or new finding was created.

### Reconciliation

- The same handoff ID and manifest were redelivered, proving the previous V1
  delivery record was not terminal in production.
- Next action: claim this exact live handoff through the deployed Agent Claim
  interface, then request the next pending source issue.
- Code changed: no.
- Production business data changed: no.
- Diagnosis changed: no.

### Claim result

- Delivery state: `accepted_by_agent`.
- Acknowledged at: `2026-08-01T19:02:45.695883Z`.
- The source remains resolved; no finding or diagnosis was reopened.

## ARL-20260801-008 - Runtime issue received for diagnosis

### Source receipt

- Source issue: `IR-20260801-78B6680F2D16`.
- Handoff: `RH-20260801-7CFAEACC0695`.
- Manifest digest: `sha256:178037449f5875bfc6d83d923bd6857e204d1f9a5264fe3eb6a2410047bf23e1`.
- Source channel: voice.
- Received at: `2026-08-01T19:03:10.817879Z`.
- Repository and deployed SHA: `465df389c1b0c6ad3281733fe7888f5b49122c1d`.
- Active FSM state at report capture: none.

### Observed behavior (not diagnosis)

- The user asked how to add information to a billed service/item.
- The bot directed the user to provide an invoice number.
- After the user replied `05`, the bot asked for a concrete business service
  instead of continuing the expected context.
- The report explicitly points to the preceding STT and subsequent bot reply
  as the required evidence. Those logs have not yet been collected.

### Pre-diagnosis state

- Status: `received_for_diagnosis`.
- Candidate classes are not final: routing/FSM continuity and invoice/service
  domain behavior.
- Findings created: none.
- Code changed: no.
- Production business data changed: no.

### Claim result

- Delivery state: `accepted_by_agent`.
- Acknowledged at: `2026-08-01T19:04:11.620147Z`.
- Diagnosis and repair status remain unchanged.

## ARL-20260801-009 - Diagnosis: lost invoice-reference continuation

### Canonical documents used

- `AGENTS.md`.
- `Skils/OfficeFlow_Interactive_Repair_SKILL.md`.
- `docs/Product_Doctrine_2030.md`.
- `docs/AI_Layer_Implementation_Standards.md`.
- `docs/Product_Truth_Layer.md`.
- `docs/Product_Truth_Registry_MVP_Design.md`.
- `docs/Info_Help_Guidance_Layer.md`.
- `docs/Evaluation_and_Smoke_Test_Standards.md`.
- `docs/TZ_FakturaBot.md`.
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`.
- `docs/llm/New_Action_Design_Checklist.md`.
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`.
- `docs/llm/Canonical_Action_Registry.md`.
- `docs/llm/In_Action_Response_Registry.md`.
- `docs/llm/Bounded_Resolver_Prompt_Template.md`.

### Runtime and owner evidence

- The source report identifies the bot prompt asking for the invoice number and
  the follow-up text `05`.
- `bot/handlers/invoice.py::process_invoice_text` emits the unique prompt
  `Napíšte číslo faktúry, ktorú chcete upraviť.` only for
  `edit_existing_invoice` with a missing invoice reference.
- That branch returns without setting an FSM state or storing pending action
  context. The next user message therefore re-enters idle top-level routing.
- `bot/services/info_help.py::classify_info_help_triage` deterministically
  classifies `05` as `spam_or_abuse`; local reproduction returned the exact
  user-facing reply asking for a concrete business task.
- No focused test covers missing-reference continuation for
  `edit_existing_invoice`. Existing tests cover direct action-plus-reference
  and later edit states only.

### Evidence availability

- The production evidence CLI returned `source_error` when invoked inside the
  container because Docker logs are not available there.
- The same bounded service invoked on the host returned all categories
  `unavailable`. The issue predates the deployment container recreation and
  no mounted application log file exists.
- Therefore the exact preceding STT and exact resolver diagnostics cannot be
  recovered in this session. They are not reconstructed from memory.

### Findings

#### IR-20260801-78B6680F2D16-F01

- Classification: `complex_or_high_risk_defect`.
- Causal mechanism: clarification text was emitted without the required
  continuation FSM. The numeric reply was processed as a fresh top-level
  message and fell into InfoHelp noise handling.
- Repair boundary: add a state-aware, text-only invoice-reference
  continuation that reuses the current scoped lookup and edit owner.
- A new/materially changed FSM route requires an Architecture Design Proof and
  explicit owner approval before implementation.
- Code changed: no. Production business data changed: no.

#### IR-20260801-78B6680F2D16-F02

- Classification: `insufficient_evidence`.
- Question: why the exact preceding voice/STT was resolved as
  `edit_existing_invoice`, and whether that selection matched the full user
  meaning.
- The exact STT and resolver event are unavailable after container recreation.
  The issue summary alone is insufficient to repair semantic hints safely.
- No routing prompt, alias, precedence, or Product Truth behavior is changed.

### Next action

Prepare a task-specific Architecture Design Proof for F01 with verdict
`ready_for_handoff`, then request explicit owner approval before code repair.

## ARL-20260801-010 - F01 architecture design published

- Finding: `IR-20260801-78B6680F2D16-F01`.
- Architecture Design Proof verdict: `ready_for_handoff`.
- Branch: `codex/invoice-reference-continuation-design`.
- Commit: `72598445148d2636dd3f1da7052fbcb85752319d`.
- Draft PR: `https://github.com/Mykh-Ai/Ai_assistant/pull/62`.
- Runtime implementation: not started; waiting for explicit owner approval.
- F02 remains `insufficient_evidence`; semantic routing was not changed.
- Validation: documentation diff check and `python -m compileall -q bot` passed.
- Production Agent Claim deployment was verified; no production business data
  was changed by diagnosis or design work.

## ARL-20260802-011 - Source issue closed as not current

- Source issue: `IR-20260801-78B6680F2D16`.
- Owner decision: mark the source issue and both findings as not current.
- Reason: the report explicitly depended on the exact preceding STT, but that
  evidence is no longer available after the production container recreation.
- `IR-20260801-78B6680F2D16-F01`: closed as `closed_not_current`; the published
  design remains historical evidence only and will not be implemented from
  this source issue.
- `IR-20260801-78B6680F2D16-F02`: closed as `closed_not_current`; the missing
  STT and resolver event are not reconstructed or guessed.
- Draft PR #62 was closed without merge at `2026-08-02T06:45:32Z` because
  its implementation handoff is no longer requested.
- If the behavior happens again, it must enter the Workshop as a new source
  issue with preserved STT and routing evidence.
- Code changed: no.
- Production changed: no.
- Production business data changed: no.
