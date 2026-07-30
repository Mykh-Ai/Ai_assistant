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
