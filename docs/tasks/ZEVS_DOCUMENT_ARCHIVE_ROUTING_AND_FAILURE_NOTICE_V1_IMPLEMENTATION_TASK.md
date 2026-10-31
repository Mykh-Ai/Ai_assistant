# ZEVS Document Archive — Approved Implementation Task

Task ID: `ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1`
Status: `approved_for_agent` — implementation proposal, tests and reviewable patch only.
Created: 2026-10-31 (Europe/Berlin).
Created by: Codex, at the product owner's request.
Approved by: product owner, explicitly in the project conversation on 2026-10-31: “В принципі дизайн приймаю”.
Source request ID: no persisted customization request ID exists; this is a directly approved project-owner task. Do not fabricate a request row.
Repository baseline inspected: `d25a4431c7b923d055b225229e0c563953600bca`.
Docs publication branch: `docs/zevs-archive-handoff-20261031`. These task/design files are not assumed to be on main. Fetch and inspect this branch, then create an isolated implementation branch from the reviewed docs commit. If main has materially changed, verify the approved design against current owners before proceeding; do not silently redesign it.
Risk: high — external storage, financial documents, tenant boundaries and additive persistence.
Target maturity: deterministic archive integration; retain partial Product Truth and existing capability-aware guidance. No new autonomous AI level.
Security review required: yes, within patch review.
External credentials required: existing owner Drive OAuth and existing Gmail/opening-password setup; no credential creation is authorized.

## Binding design and permission boundary

Read `docs/architecture/ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1_ARCHITECTURE_DESIGN_PROOF.md` first. Verdict: `ready_for_handoff`; approval and annual-folder clarification are recorded in revision 3.

Implement that approved design. You are not authorized to redesign the architecture, create a new canonical action/FSM, choose a different tenant model, alter retry policy, bypass confirmations, or substitute your own routing/retention/security scheme. Ordinary module/function names are implementation details; material design changes require an explicit design variance and owner approval.

This task authorizes an isolated repository implementation proposal and its local tests. It does not authorize production access, server configuration changes, real uploads/messages, DB migration against production, historical repair, merge or deploy. Prepare the production audit/dry-run/backup/activation/rollback procedure as reviewable text or tools; do not execute it.

No agent has been started by publishing this task. Do not claim the work is assigned, implemented, merged, deployed or runtime-proven merely because this file exists.

## Product outcome

1. A supported ZEVS bank statement is archived as a PDF that opens without a password. Preserve the original source bytes locally.
2. ZEVS Drive paths follow validated document periods:
   - statement: `<approved_company_root>/Zevs_YYYY/Vypisy/<file>.pdf`;
   - receipt: `<approved_company_root>/Zevs_YYYY/blocky/YYYY-MM/<file>`.
3. Reuse existing annual/type/month folders; create missing ones on demand inside the configured company root.
4. After the allowed upload attempts fail, notify the original authorized user in Telegram. Wrong password and other permanent failures produce an honest notice without pointless upload retries.
5. Never conflate local save, queue insertion, verified Drive upload and confirmed Telegram send.

The owner's supplied 2026 URLs identify the intended existing tree, not a hardcoded year or a requirement to configure a fresh child-folder ID annually. Current 2026 documents must reuse the existing 2026 tree. A 2026 document received in January 2027 stays in 2026; a retry spanning New Year keeps its frozen target. The same rule must work for 2027, 2028 and later years without a code edit or annual configuration change.

Preserve the existing local storage layout and its validated year/month rules. Do not introduce a second business-date parser or change local paths to match the new Drive route.

## Required preflight

Before editing, record:
- current branch/HEAD, AGENTS files and any working-tree changes; preserve unrelated work;
- design revision and approval, docs/contracts read, extracted constraints and touched scopes;
- runtime status versus planned behavior and actual AI maturity;
- exact scope/out-of-scope, tenant keys and accepted public journeys;
- migration-sensitive data and rollback obligations;
- self-learning decision: none; routes, years, passwords and destructive confirmations must not be learned;
- current code owners and any divergence from the pinned baseline.

Read the current applicable versions of:
- `AGENTS.md`;
- `docs/Product_Doctrine_2030.md`;
- `docs/Implementation_Agent_Checklist.md`;
- `docs/Code_Agent_Handoff_Contract.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`, especially Conversation Acceptance Proof;
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
- the approved task-specific proof;
- `docs/FakturaBot_Data_Migration_Runbook.md`;
- `docs/AI_Layer_Implementation_Standards.md`, `docs/Product_Truth_Layer.md`, `docs/Product_Truth_Registry_MVP_Design.md`;
- `docs/Info_Help_Guidance_Layer.md`, `docs/Customization_Request_Layer.md`, `docs/Self_Learning_Layer.md`;
- `docs/architecture/OfficeFlow_Architecture_Framing.md`, `docs/architecture/OfficeFlow_Storage_Model_Proposal.md`;
- `docs/Document_Intake_Module_Proposal.md`, `docs/Document_Intake_MVP_Implementation_Plan.md`;
- `docs/Google_Drive_Faktury_Bloceky_Storage_Policy.md`;
- `docs/Google_Gmail_Statement_Collector_Setup_Runbook.md`;
- existing Gmail protected-period and accounting-workspace-isolation architecture proofs;
- `docs/TZ_FakturaBot.md` and relevant recent `PROJECT_LOG.md` entries;
- canonical actions/in-action registries and LLM/DecisionResolver contracts to preserve public routing and confirmations;
- PDF/layout guidance as relevant to preservation/visual verification; outgoing-invoice layout is out of scope.

Known documentation gap at the inspected baseline: `docs/llm/Conversation_Acceptance_Proof_Contract.md` is referenced by the architecture contract but GitHub returned 404 for it. Do not invent its contents or create a substitute contract. Use the existing detailed Conversation Acceptance Proof requirements in `docs/Evaluation_and_Smoke_Test_Standards.md`, record the missing companion, and stop for clarification only if a material requirement cannot be determined from current authoritative sources.

Do not read a public example runbook as live server truth. The private operational context is supplied separately by the owner; do not publish it, passwords, credentials, folder IDs or Telegram IDs.

## Current owners to inspect

- `bot/handlers/accounting_document_intake.py`:
  `_save_accounting_document_from_state`, `_enqueue_archive_after_confirmed_save`, bound workspace/preview helpers.
- `bot/services/accounting_document_storage.py`: original/metadata and validated canonical paths.
- `bot/services/accounting_document_archive_service.py` and `accounting_document_archive_path.py`.
- `bot/services/archive_job_service.py`: enqueue/dedup/lease/transitions.
- `bot/services/archive_worker.py`: retry, upload and retention.
- `bot/services/google_drive_archive_scheduler.py`: provider wiring, batch and asynchronous scheduler.
- `bot/services/google_drive_owner_oauth_client.py`: scoped Drive lookup/create/upload; preserve existing OAuth boundary.
- `bot/services/google_drive_service_account_client.py`: compatibility only; do not enable personal My Drive service-account mode.
- `bot/services/gmail_statement_collector.py`, `gmail_statement_period.py`, `gmail_statement_archive_path.py`, `gmail_statement_scheduler.py`.
- `bot/services/google_gmail_config.py`: file-backed opening secret.
- `bot/services/db.py`: archive tables and existing folder cache.
- `bot/services/workspace_context.py`: exact workspace and membership.
- `bot/main.py`, `bot/config.py`: only necessary dependency/config wiring.
- `bot/services/product_truth.py`: existing Gmail/Drive capabilities.

New narrowly scoped deterministic route, payload and failure-notice helpers are allowed as owners for the approved design. Do not add generic plugin/workflow infrastructure.

## Implementation sequence and invariants

### 1. Admin route configuration

Implement the approved `GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE` contract, disabled/legacy behavior when absent, strict file/schema validation when configured, exact workspace/type lookup, one configured company-root ID and bounded `Zevs_{YYYY}` / Vypisy / blocky templates.

Real installation values stay in private deployment configuration. Public fixtures use unmistakably synthetic IDs. Existing 2026 anchors are optional verified bootstrap hints; they are neither Python constants nor a fixed-year gate.

Derive year/month once from existing validated document/statement logic. Unknown dates/periods do not default to the machine's current year.

### 2. Immutable delivery context and additive persistence

Implement `archive_delivery_context` and `archive_failure_notices` as designed. No destructive or historical rewrite.

Insert a new job's scope/route snapshot atomically with that job. Preserve original local paths and metadata. Include approved root, validated year, bounded folder templates, payload mode and source hash; resolve destination IDs once with lineage verification.

Reuse `google_drive_folder_cache` in a new scoped namespace for folder reservations. Do not rewrite existing cache rows. Reserved IDs are not proof of remote existence. All retries and restarts must reuse the persisted winning reservation.

Legacy jobs without delivery context remain on their existing route. Provide a read-only inventory/dry-run for outstanding ZEVS legacy jobs; deployment must resolve their disposition before activation. Do not silently retarget or requeue them.

### 3. Password-free statement payload

Use the existing known opening-password secret. Never accept a password via Telegram, log it, persist it in DB/sidecars, send it to AI, or attempt recovery/bruteforce.

Keep the original bytes/hash unchanged. Prepare the approved private per-job archive payload; clone all supported PDF pages without encryption; reopen without a password; validate page count, header/period and preservation evidence. Reject signed/unsupported/corrupt cases as specified instead of producing a misleading document.

Use restrictive permissions and atomic writes. Persist exact payload bytes/hash/size before upload and reuse them for retries. Clean only scoped temporary/payload files under the approved lifecycle. Do not delete the immutable bank source.

An unreadable secret file must become a bounded setup/review failure, not an uncaught tick that silently loses the notice. Preserve a valid downloaded source where possible.

### 4. Scoped annual folders and idempotent upload

Use the existing owner OAuth provider. Do not change the global root, account/scopes, connection commands or token model.

Only direct-child lookups under the approved root/tree are allowed; paginate. Reuse one exact matching folder; create the missing folder with a persisted pre-generated ID. Verify name, parent, folder MIME and trashed state. Duplicate-name ambiguity and wrong lineage fail closed.

Reserve a remote file ID before create/upload. Retry the same ID and exact payload after timeout. Reconcile 409 with readback. Never use a new ID to hide an indeterminate successful create.

Mark uploaded only after parent/content/reference verification. A nonempty create response ID alone is insufficient for the new branch. Keep all other document types/workspaces on their existing routes.

### 5. Bounded failures and durable Telegram notices

Retain default 5 total failed upload executions, separated by at least 15 minutes. Do not change this to 6 attempts, retry forever, or reset exhausted jobs.

Fix the enabled-provider-unavailable noop hole for the approved lifecycle. An explicitly disabled integration must be described as local-only, not successful Drive archiving.

Permanent errors (including invalid password or an unsafe target) fail closed and create the correct notice without claiming that five attempts occurred.

Create/deduplicate notices for terminal common archive jobs after a persisted rollout cutoff. Add prequeue failure handling so receipt/Gmail archive enqueue failures are not only log warnings.

Use a durable outbox, restart reconciliation, delivery leases, independent Telegram retry, recipient membership checks and bounded sanitized content. Original actor/workspace owns the notice; do not fall back to another user's chat or the current selected profile.

Inject Bot at the scheduler boundary. Do not call Telegram from PDF/Drive workers. Do not send real messages in local verification.

Set sent_at only after confirmed send. Respect Telegram retry_after and distinguish temporary from blocked/forbidden. Do not claim exactly-once delivery; include a stable short reference for the documented crash-after-send window.

A failure notice has no keyboard/callback and must not clear FSM or remove another active flow's keyboard. Check source presence before claiming the original is retained. If remote outcome is indeterminate, say that Drive saving could not be confirmed, not that the file definitely does not exist.

### 6. Product Truth, docs and operational plan

Keep Gmail/Drive capabilities partial/requires_setup/admin/external_credentials. Update only claims supported by the implementation and distinguish local-tested behavior from unproven production setup.

Update:
- `bot/services/product_truth.py`;
- `docs/Product_Truth_Layer.md`, `docs/Info_Help_Guidance_Layer.md`;
- Gmail setup runbook and protected-PDF proof's previous no-decrypted-copy rule with the narrow approved archive-payload exception;
- Drive storage policy, relevant TZ/README sections;
- `PROJECT_LOG.md`, `CHANGELOG.md`;
- new acceptance proof and migration/rollout runbook.

Prepare read-only audit and dry-run mapping, online SQLite/storage/config/image backup plan, exact activation cutoff/flags, writer-freeze/schema apply checks, independent readback and rollback plan. Never put real identities or tokens in the proposed runbook.

Rollback must pause new-context jobs before an older worker could consume them through legacy routing. Do not restore an old full DB over later business activity or delete already-created remote files automatically.

## Explicit no-go / out of scope

- No new public action, command, FSM, retry button/callback or voice dictionary.
- No automatic contact creation or receipt save before existing confirmation.
- No LLM-owned folder/date/credential/side-effect decisions.
- No changes to incoming-invoice/outgoing-invoice destinations, other workspaces, mark-paid, invoice numbering/layout or local original/metadata paths.
- No historical Drive moves, backfill, mass decrypt/reupload, job repair or cleanup.
- No OAuth/permission/account changes, service-account migration or dependency installation without separate authorization.
- No transaction parser, payment reconciliation, accounting conclusions or generalized PDF editor.
- No production SSH, live DB/config writes, actual cloud upload/send, merge or deployment under this task.
- No false claim that mock success proves real Drive/Telegram operation.

The known stale Gmail import archive_status is not authoritative for completed uploads. Read archive_jobs/accounting archive state; do not use this task to rewrite historical summary rows.

## Acceptance, tests and evaluation

Implement and prove all 40 scenarios in section 14 of the approved proof. Every requirement needs actual file/symbol and named test/eval evidence; do not replace the matrix with a list of passing unit tests.

Priority cases:
- public receipt command/attachment → preview → equivalent text/voice/button confirmation → one queue job → correct exit/keyboard;
- unknown/cancel/back/stale/unauthorized/other-workspace paths have no archive side effect;
- supported encrypted PDF produces an unencrypted copy, while original bytes and metadata identity remain unchanged;
- wrong/missing secret, signed/corrupt PDF, unknown period and enqueue failure produce honest bounded notices;
- 2026 existing-tree reuse, first 2027 create, existing 2027 reuse, late 2026 document in 2027, retry across New Year, generic 2028, missing/ambiguous date;
- folder-create and upload timeout/409/restart reconciliation, duplicate folders and checksum/parent mismatch;
- exactly 5 total transient failures, success before exhaustion, provider unavailable, source retention;
- outbox restart recovery, successful-send marking, temporary delivery retry, blocked actor, no cross-tenant send, active FSM/keyboard preservation;
- additive schema twice on legacy fixture DB, unchanged legacy rows/paths/cache and safe rollback;
- InfoHelp text/voice capability questions with zero business writes;
- unchanged outgoing/incoming/other-workspace regression journeys.

Run focused existing suites and meaningful new tests, then the repository-required checks. Use `python -m pytest`, not bare pytest. Focused baseline files include:
- tests/test_gmail_statement_period.py
- tests/test_gmail_statement_collector.py
- tests/test_gmail_statement_archive.py
- tests/test_gmail_statement_scheduler.py
- tests/test_google_gmail_config.py
- tests/test_accounting_document_archive_service.py
- tests/test_accounting_document_drive_workspace_isolation.py
- tests/test_accounting_document_intake_flow.py
- tests/test_archive_job_service.py
- tests/test_archive_worker.py
- tests/test_google_drive_service_account_archive.py (existing owner-provider coverage too)
- tests/test_product_truth.py and relevant InfoHelp/voice/state/callback/access tests.

Use controlled clocks, fake provider/Telegram and synthetic PDFs/IDs for local tests. Do not deliberately break real credentials or write real bank documents to cloud folders to test a failure.

Perform PDF preservation/visual QA on synthetic fixtures; real financial-document smoke remains a separately approved private operational step.

Record exact commands, pass/fail/skip totals and any limitations. Run compile/diff checks and the full suite as required by the current AGENTS/checklists. No runtime tests are needed merely for this initial docs-only task package; those checks are required for the future implementation.

## Required deliverables and handoff stop

1. Scoped implementation patch on an isolated branch.
2. Current preflight + design-to-code mapping; any material contradiction reported before architectural changes.
3. Focused/new/full checks and exact results.
4. `docs/evals/ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1_CONVERSATION_ACCEPTANCE_PROOF.md` with all 40 applicable traces and explicit no-side-effect/keyboard observations.
5. Synchronized Product Truth/docs/log/changelog.
6. Reviewable migration/audit/dry-run/backup/activation/rollback procedure; no production execution.
7. Final concise summary, diff, risks, unverified live conditions and owner approval steps.

Use exactly one acceptance-proof verdict from `docs/Evaluation_and_Smoke_Test_Standards.md`: `safe_to_commit`, `needs_revision`, `blocked_by_design_gap` or `runtime_not_proven`, with its exact contract meaning. Record design-to-code agreement separately; `design_matches_runtime` is not an additional acceptance verdict. Distinguish proven local scope from unperformed live verification. Do not claim safe_to_merge/deploy or production success solely from local tests. If a material approved requirement is missing, the patch is not complete.

Stop with a concrete reviewable result. The user separately approves merge, deployment, live migration/upload/notification tests and any historical repair. Do not ask again for approval of routine local work that is already covered by this approved task.

