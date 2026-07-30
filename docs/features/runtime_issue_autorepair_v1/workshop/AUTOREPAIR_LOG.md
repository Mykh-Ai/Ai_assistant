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
