# Acceptance Scenarios

Task ID: `RUNTIME_ISSUE_INTAKE_AND_AUTOREPAIR_V1`

Status: target acceptance contract only. Future implementation must prove the
public journeys under the real “Conversation Acceptance Proof” section of
`docs/Evaluation_and_Smoke_Test_Standards.md`, plus focused and adjacent
deterministic tests. No test in this repository currently implements these
scenarios.

Target Slovak copy is illustrative until product approval. Every issue-intake
scenario applies the slot, privacy, idempotency, and workspace contracts in
`01_ARCHITECTURE_DESIGN_PROOF.md` and
`04_DATA_STATUS_AND_AGENT_INTERFACE_CONTRACT.md`.

## A. Intake and routing

### 1. Idle text `/issue`

- **Precondition:** Authorized administrator, no active FSM, trusted workspace
  `W1`, clean issue store, trusted Telegram identifiers.
- **Input/event:** `/issue Po stlačení Uhradená sa nezobrazilo potvrdenie.`
- **Expected canonical action/classification:** `report_runtime_issue`;
  maintenance classification remains unset.
- **State sequence:** idle → ephemeral capture call → idle.
- **Side effect/no-side-effect:** One `new` SQLite issue with original sanitized
  description, derived title, actor/workspace/text source, null FSM, trusted
  IDs/build status, privacy metadata, and dedup key; one acknowledgement. No
  invoice/callback/code/deploy effect.
- **Expected final state:** Idle; no issue-intake pending state.
- **User-visible outcome:** `Problém som uložil ako IR-…. Aktuálna akcia bota
  zostala nezmenená.` No new keyboard.
- **Evidence/future test owner:** Proposed issue handler/service tests;
  `bot/handlers/invoice.py::process_invoice_text` and
  `bot/services/authorization.py` are adjacent owners.

### 2. Idle voice issue

- **Precondition:** Authorized administrator, idle, STT available, trusted
  workspace `W1`.
- **Input/event:** Voice transcript equivalent to “Chyba: po uložení zostala
  klávesnica.”
- **Expected canonical action/classification:** Bounded resolver returns
  `report_runtime_issue`; no maintenance classification at intake.
- **State sequence:** idle → general authorization → STT → admin guard →
  bounded issue resolution → capture → idle.
- **Side effect/no-side-effect:** Same one issue row and acknowledgement as text,
  with `source_channel=voice`; no parallel voice store, replay, or FSM change.
- **Expected final state:** Idle.
- **User-visible outcome:** Same stored acknowledgement; no claim that the
  problem is confirmed or fixed.
- **Evidence/future test owner:** New voice convergence test adjacent to
  `tests/test_voice_state_routing.py`; current `bot/handlers/voice.py` must call
  the shared canonical owner.

### 3. Active FSM preservation

- **Precondition:** Authorized administrator is in an invoice/customer FSM with
  state `S`, business data `D`, and activity metadata `A`.
- **Input/event:** `/issue Po výbere kontaktu sa nezobrazila ďalšia otázka.`
- **Expected canonical action/classification:** `report_runtime_issue`.
- **State sequence:** `(S,D,A)` → shared global issue branch → capture →
  `(S,D,A)`.
- **Side effect/no-side-effect:** One issue record contains only allowlisted
  snapshot fields; no `clear`, `set_state`, `update_data`, activity touch,
  business write, or replay.
- **Expected final state:** State, business FSM data, and protected activity
  metadata equal their pre-event values.
- **User-visible outcome:** Stored acknowledgement says current action was not
  cancelled; the existing business keyboard/message remains governed by its
  owner.
- **Evidence/future test owner:** New preservation tests adjacent to
  `tests/test_active_fsm_guard.py::test_active_text_pass_through_is_not_swallowed_and_stamps_after_handler`
  and `tests/test_state_control.py`.

### 4. Bare `/issue`

- **Precondition:** Authorized administrator, idle or in any active business
  FSM.
- **Input/event:** `/issue` with whitespace only.
- **Expected canonical action/classification:** Usage outcome; no
  `report_runtime_issue` persistence and no classification.
- **State sequence:** Exact pre-state → validation → exact pre-state.
- **Side effect/no-side-effect:** No issue row, pending state, next-message
  capture, business effect, or activity stamp; usage send only.
- **Expected final state:** Exact pre-state/data.
- **User-visible outcome:** `Opíšte problém v tej istej správe: /issue po
  stlačení ...` and `Aktuálnu akciu bota som nezrušil.`
- **Evidence/future test owner:** Proposed command validation tests plus active
  FSM preservation suite.

### 5. Unauthorized text

- **Precondition:** Telegram actor is unauthorized or authorized but not an
  administrator.
- **Input/event:** `/issue <complete description>` or equivalent natural text.
- **Expected canonical action/classification:** No executable issue action.
- **State sequence:** Outer authorization or admin guard → fail closed.
- **Side effect/no-side-effect:** No issue row, resolver/LLM call where the
  admin guard can precede it, log lookup, FSM change, or business effect.
- **Expected final state:** No issue-owned state; existing unauthorized flow
  only.
- **User-visible outcome:** Existing access response/policy; no issue ID.
- **Evidence/future test owner:** `tests/test_access_request_flow.py`,
  `tests/test_tenant_safety.py`, and new admin issue tests against
  `TelegramUserAuthorizationMiddleware`/`is_admin_telegram_user`.

### 6. Unauthorized voice

- **Precondition:** Actor is not generally authorized.
- **Input/event:** Voice containing an issue observation.
- **Expected canonical action/classification:** None.
- **State sequence:** Outer authorization → fail closed before STT.
- **Side effect/no-side-effect:** No STT, issue resolver, persistence, log
  lookup, or FSM/business effect.
- **Expected final state:** Unchanged.
- **User-visible outcome:** Existing access response/policy.
- **Evidence/future test owner:** `tests/test_tenant_safety.py` unauthorized
  before LLM/business; new voice authorization test.

For a generally authorized non-admin actor, current architecture may require
STT before semantic admin intent is knowable. A separate test must prove the
post-STT admin guard prevents issue resolver/persistence/log access. Product
approval of this precise limitation is required.

### 7. Ambiguous normal business text

- **Precondition:** Authorized admin is idle or in an FSM expecting free text.
- **Input/event:** `Chyba v názve zákazníka Tech Company` without an explicit
  request to record a runtime observation.
- **Expected canonical action/classification:** Existing business/state owner,
  clarification, or `unknown`; not `report_runtime_issue`.
- **State sequence:** Existing routing/state sequence only.
- **Side effect/no-side-effect:** No issue row unless the administrator sends a
  later complete explicit report; no write default.
- **Expected final state:** Existing owner’s state.
- **User-visible outcome:** Existing business clarification/response.
- **Evidence/future test owner:** Semantic boundary tests adjacent to
  `semantic_action_resolver.py`, invoice top-level tests, and active FSM tests.

### 8. Capability question

- **Precondition:** Authorized administrator, any safe state.
- **Input/event:** `Vieš nahlásiť chybu?`
- **Expected canonical action/classification:** Product Truth/InfoHelp question.
- **State sequence:** Existing informational route → same/owned state.
- **Side effect/no-side-effect:** No issue row or maintenance action.
- **Expected final state:** Existing state preserved.
- **User-visible outcome:** Current truth says the capability is unavailable
  until implemented; target truth explains `/issue` without executing it.
- **Evidence/future test owner:** Product Truth/InfoHelp evals and top-level
  semantic negative tests.

### 9. Issue persistence failure

- **Precondition:** Authorized administrator; issue-store transaction fails.
- **Input/event:** Complete valid `/issue ...`.
- **Expected canonical action/classification:** Action recognized; persistence
  result failed, no classification.
- **State sequence:** Pre-state → capture attempt → transaction rollback →
  identical pre-state.
- **Side effect/no-side-effect:** No partial issue or false stored status; no
  business/FSM mutation. Error response send is allowed.
- **Expected final state:** Exact pre-state/data/activity.
- **User-visible outcome:** Truthful “problem could not be stored; retry later,”
  with no issue ID.
- **Evidence/future test owner:** Proposed `RuntimeIssueService` transaction
  failure test and active-FSM failure-preservation test.

### 10. Deduplicated Telegram delivery

- **Precondition:** First delivery stored as `IR-1`; Telegram redelivers the
  same trusted update/message.
- **Input/event:** Identical delivery identifiers and source.
- **Expected canonical action/classification:** Same issue action, idempotent
  duplicate.
- **State sequence:** Pre-state → dedup lookup/unique insert conflict → same
  pre-state.
- **Side effect/no-side-effect:** No second row and no status reset; bounded
  acknowledgement may repeat with `IR-1`.
- **Expected final state:** Pre-state unchanged.
- **User-visible outcome:** Same truthful issue ID, no “stored another issue”
  claim.
- **Evidence/future test owner:** Proposed unique-key service test; adjacent
  idempotency patterns in `tests/test_archive_job_service.py` and
  `tests/test_customization_request_admin.py`.

### 11. Workspace isolation

- **Precondition:** Admin is a member of `W1`, not `W2`; description says
  `workspace_id=W2`.
- **Input/event:** `/issue workspace_id=W2, tlačidlo nefunguje`.
- **Expected canonical action/classification:** `report_runtime_issue` only for
  trusted `W1` context; untrusted field remains observation text or is redacted,
  never authority.
- **State sequence:** Read-only trusted resolution → capture in `W1`.
- **Side effect/no-side-effect:** At most one `W1` issue; no `W2` lookup/write or
  data disclosure.
- **Expected final state:** Existing state unchanged.
- **User-visible outcome:** Generic stored acknowledgement without exposing
  workspace internals.
- **Evidence/future test owner:** `tests/test_workspace_context.py`,
  `tests/test_tenant_safety.py`, and proposed issue-service scope tests.

### 12. Secret redaction

- **Precondition:** Admin accidentally includes a token-like value.
- **Input/event:** `/issue API zlyhalo, token=...`.
- **Expected canonical action/classification:** Action may be captured only
  after approved sanitizer treatment; intake does not classify cause.
- **State sequence:** Pre-state → redaction/validation → capture or safe reject
  → pre-state.
- **Side effect/no-side-effect:** Secret value never enters canonical
  description, title, manifest, logs, notification, Git, or public project log.
  If safe redaction cannot be guaranteed, no issue row.
- **Expected final state:** Unchanged.
- **User-visible outcome:** Stored acknowledgement with no echo of the secret,
  or truthful resubmission request with no stored claim.
- **Evidence/future test owner:** New sanitizer property/unit tests and manifest,
  result, and outbox serialization tests.

## B. Claim, diagnosis, and classification

### 13. Claim lease and interrupted run

- **Precondition:** `IR-1` is `new`; run `R1` atomically claims it and then
  stops before external work is recorded.
- **Input/event:** Lease expires; run `R2` requests a claim.
- **Expected canonical action/classification:** Maintenance claim recovery; no
  diagnosis yet.
- **State sequence:** `new -> claimed(R1) -> lease expired ->
  new/audited reclaim -> claimed(R2)`.
- **Side effect/no-side-effect:** One canonical issue; new claim token and
  incremented attempt; stale `R1` result rejected. No code/Git/deploy effect.
- **Expected final state:** `claimed(R2)` or `insufficient_evidence` after
  approved retry cap.
- **User-visible outcome:** No duplicate diagnosis notification; later result
  only.
- **Evidence/future test owner:** Proposed maintenance service tests modeled on
  `tests/test_archive_job_service.py` active lease/expiry/reclaim and
  `tests/test_archive_worker.py`.

### 14. Insufficient evidence

- **Precondition:** Issue is claimed; build SHA or correlating event is missing
  and deterministic reproduction fails.
- **Input/event:** Daily diagnosis reaches the evidence gate.
- **Expected canonical action/classification:** `insufficient_evidence`.
- **State sequence:** `new -> claimed -> insufficient_evidence`.
- **Side effect/no-side-effect:** Result/evidence metadata and notification
  only; no patch, branch, commit, merge, or deploy.
- **Expected final state:** `insufficient_evidence`, lease released.
- **User-visible outcome:** Concise missing-evidence explanation and explicit
  “code and production were not changed.”
- **Evidence/future test owner:** Result transition/outbox tests and policy
  classification fixtures.

### 15. External failure

- **Precondition:** Claimed issue correlates with bounded provider status/error
  evidence; current bot handled it according to current contract.
- **Input/event:** Diagnosis proves a provider/network failure.
- **Expected canonical action/classification:** `external_failure`.
- **State sequence:** `new -> claimed -> external_failure`.
- **Side effect/no-side-effect:** Store diagnosis and enqueue result; no
  speculative product patch/deploy.
- **Expected final state:** `external_failure`.
- **User-visible outcome:** External cause is stated only with evidence and
  code/production unchanged.
- **Evidence/future test owner:** Classification schema/outbox tests; future
  approved sanitized integration evidence owner.

### 16. Feature request is not a confirmed bug

- **Precondition:** Report says `/issue pridajte automatické mesačné faktúry`;
  Product Truth does not support that capability.
- **Input/event:** Daily classification compares report with current truth.
- **Expected canonical action/classification:** Intake action was valid;
  maintenance classification `feature_request`.
- **State sequence:** `new -> claimed -> feature_request`.
- **Side effect/no-side-effect:** No repair branch, commit, merge, deploy, or
  Product Truth edit; bounded handoff suggestion only.
- **Expected final state:** `feature_request`.
- **User-visible outcome:** Truthfully says it is a feature request, not a
  confirmed defect, and code/production were not changed.
- **Evidence/future test owner:** Product Truth comparison fixtures and result
  transition/notification tests.

### 17. Complex/high-risk defect

- **Precondition:** Evidence suggests an invoice-tax calculation or workspace
  authorization defect requiring architecture or data change.
- **Input/event:** Daily policy evaluation hits forbidden scope.
- **Expected canonical action/classification:**
  `complex_or_high_risk_defect`.
- **State sequence:** `new -> claimed -> blocked_high_risk`.
- **Side effect/no-side-effect:** Sanitized evidence, owner/test list, and stop
  reason only; no patch, speculative branch, commit, merge, deploy, migration,
  or data repair.
- **Expected final state:** `blocked_high_risk`.
- **User-visible outcome:** Concise blocked report, required separate proof or
  review, and explicit no code/production change.
- **Evidence/future test owner:** Forbidden-scope policy fixtures and transition
  tests.

### 18. Diagnostic logging only

- **Precondition:** The symptom cannot be causally resolved, but a bounded
  structured diagnostic gap is identified; evidence is insufficient to prove
  that adding an event would repair the reported behavior.
- **Input/event:** Daily diagnosis completes.
- **Expected canonical action/classification:** `insufficient_evidence`, with a
  diagnostic recommendation; not a confirmed repair.
- **State sequence:** `new -> claimed -> insufficient_evidence`.
- **Side effect/no-side-effect:** Store bounded recommendation and notification
  only. No logging patch, branch, commit, merge, or deploy under insufficient
  root-cause proof.
- **Expected final state:** `insufficient_evidence`.
- **User-visible outcome:** Diagnosis limitation and explicit statement that
  neither behavior nor production was changed.
- **Evidence/future test owner:** Classification-policy fixtures; a separately
  proven missing structured event can be evaluated later under the low-risk
  allowlist with its own regression test.

## C. Repair, gates, deployment, and result truth

### 19. Allowed low-risk repair

- **Precondition:** Claimed issue proves a missing callback acknowledgement in
  an existing owner at an exact deployed SHA; current callback contract and a
  failing regression test establish the defect; no forbidden scope applies.
- **Input/event:** Approved repair workflow evaluates the candidate.
- **Expected canonical action/classification:**
  `confirmed_low_risk_defect`.
- **State sequence:** `new -> claimed -> repair_validating ->
  repair_ready_to_deploy`; after separately approved controlled deployment and
  every verification, `fixed_deployed`.
- **Side effect/no-side-effect:** One minimal marked repair branch/commit and
  tests; merge/deploy only with current required human approval or a future
  approved authority revision.
- **Expected final state:** `repair_ready_to_deploy` while awaiting approval, or
  `fixed_deployed` only after exact production proof.
- **User-visible outcome:** Before deploy, “candidate ready for review,” not
  fixed. After proof, exact commit/deployed SHA and smoke result.
- **Evidence/future test owner:** `tests/test_decision_callbacks.py`, callback
  owner test, broader regression, service transition, and notification tests.

### 20. Failed test gate

- **Precondition:** Proven allowlisted candidate and minimal patch; an adjacent
  callback/FSM/workspace or broader test fails.
- **Input/event:** Required test phase.
- **Expected canonical action/classification:**
  `confirmed_low_risk_defect`, outcome `repair_failed_no_deploy`.
- **State sequence:** `claimed -> repair_validating ->
  repair_failed_no_deploy`.
- **Side effect/no-side-effect:** No successful-fix commit claim, merge, or
  deploy; no unrelated test repair. Any uncommitted candidate is discarded by
  the isolated workflow according to approved safe cleanup.
- **Expected final state:** `repair_failed_no_deploy`.
- **User-visible outcome:** Test gate failed; code was not deployed and
  production was unchanged.
- **Evidence/future test owner:** Maintenance orchestration gate tests with
  simulated focused/adjacent/broad failure.

### 21. Failed production smoke and rollback

- **Precondition:** Candidate passed all pre-deploy and approval gates; rollback
  reference exists; controlled deploy completes but issue-specific smoke fails.
- **Input/event:** Production smoke failure.
- **Expected canonical action/classification:**
  `deployment_failed_rolled_back` if rollback verification passes, otherwise
  `deployment_failed_rollback_risk`.
- **State sequence:** `repair_ready_to_deploy -> deploy verification failed ->
  rollback -> deployment_failed_rolled_back` or
  `deployment_failed_rollback_risk`.
- **Side effect/no-side-effect:** Execute only the approved private rollback;
  stop all further issue processing on unresolved risk.
- **Expected final state:** Verified rollback status or frozen rollback-risk
  status; never `fixed_deployed`.
- **User-visible outcome:** Truthful failed-deploy and rollback result, exact
  verified SHA/reference where safe, and no success claim.
- **Evidence/future test owner:** Maintenance deployment state-machine tests;
  private production proof required before deployment.

### 22. Truthful fixed/deployed notification

- **Precondition:** `IR-1` has exact repair commit, approved merge, exact
  production SHA, health, issue-specific smoke, error scan, and final SHA
  verification.
- **Input/event:** Result transaction enqueues and worker sends notification.
- **Expected canonical action/classification:**
  `confirmed_low_risk_defect`, status `fixed_deployed`.
- **State sequence:** `repair_ready_to_deploy -> fixed_deployed`; outbox
  `pending -> sending -> sent`.
- **Side effect/no-side-effect:** One idempotent notification; no second deploy
  or diagnosis on delivery retry.
- **Expected final state:** Issue `fixed_deployed`, outbox `sent`.
- **User-visible outcome:** Exact issue ID, commit/deployed SHA, tests/smoke
  result, and bounded repair summary; no guarantee beyond proven result.
- **Evidence/future test owner:** Result validation, trusted-SHA verification,
  outbox idempotency/retry, and production acceptance proof.

### 23. Truthful complex/blocked notification

- **Precondition:** Issue is `blocked_high_risk`.
- **Input/event:** Outbox worker sends terminal result.
- **Expected canonical action/classification:**
  `complex_or_high_risk_defect`.
- **State sequence:** Issue remains `blocked_high_risk`; outbox
  `pending -> sending -> sent`.
- **Side effect/no-side-effect:** Notification only; no repair branch, commit,
  merge, deploy, or new business action.
- **Expected final state:** Blocked status and delivered notification.
- **User-visible outcome:** Stop reason, relevant owner/review needed, and
  explicit “code and production were not changed.”
- **Evidence/future test owner:** Result template and outbox transition tests.

## D. Existing-business invariants and motivating examples

### 24. Existing business callback invariants

- **Precondition:** A current invoice/contact/follow-up callback is valid,
  stale, wrong-state, duplicate, legacy, or unauthorized.
- **Input/event:** Existing callback delivery, with or without a prior issue
  report describing a callback problem.
- **Expected canonical action/classification:** Existing callback owner; never
  `report_runtime_issue` from callback data.
- **State sequence:** Existing callback state/context/expiry contract.
- **Side effect/no-side-effect:** Exactly the current acknowledgement and
  bounded business effect; stale/wrong/unauthorized fail closed. An issue report
  never executes or replays the callback.
- **Expected final state:** Current callback contract’s state/keyboard.
- **User-visible outcome:** Current callback response; no issue acknowledgement
  unless a separate explicit issue message was sent.
- **Evidence/future test owner:** `tests/test_decision_callbacks.py` and
  `tests/test_invoice_followup_handler.py` full adjacent regression.

### 25. Paid-invoice callback motivating example

- **Precondition:** Administrator reports that after `Uhradená`, the spinner
  continued and terminal message was absent; exact event correlates to a
  proven successful mark-paid mutation but missing callback acknowledgement or
  terminal response.
- **Input/event:** Claimed issue diagnosis at the exact deployed SHA.
- **Expected canonical action/classification:** Intake was
  `report_runtime_issue`; maintenance may classify
  `confirmed_low_risk_defect` only after callback evidence proves the precise
  missing acknowledgement/message mechanism.
- **State sequence:** `new -> claimed -> repair_validating`; then the same gate
  outcomes as scenarios 19–21.
- **Side effect/no-side-effect:** A candidate may alter only the existing
  acknowledgement/terminal UI owner and add regression coverage. It must not
  mark the invoice paid again, change settlement truth, replay the callback,
  change amounts, or redesign callback architecture.
- **Expected final state:** Existing invoice/callback state contract; issue
  status reflects actual gate outcome.
- **User-visible outcome:** Diagnosis/fix result never claims a second payment
  mutation; deployment success only with exact SHA and smoke.
- **Evidence/future test owner:** `bot/handlers/decision_callbacks.py`,
  `bot/handlers/invoice_followup.py`,
  `tests/test_decision_callbacks.py`, and
  `tests/test_invoice_followup_handler.py`.

If evidence instead implicates bank settlement truth, data repair, callback
architecture, or ambiguous Product Truth, classify
`complex_or_high_risk_defect` and stop without a patch.

### 26. Contact resolver / analytics motivating example

- **Precondition:** Analytics for invoices issued to “Тех Компані” misses
  stored contact “Tech Company s. r. o.”; current voice/contact creation already
  proves canonical exact/normalized/alias/legal-suffix/bounded-fuzzy resolution;
  datasets expose trusted `contact_id`.
- **Input/event:** Claimed issue diagnosis and deterministic analytics
  reproduction in workspace `W1`.
- **Expected canonical action/classification:** Intake was
  `report_runtime_issue`; `confirmed_low_risk_defect` only if evidence proves
  the analytics path alone failed to reuse the approved resolver and identity
  filter.
- **State sequence:** `new -> claimed -> repair_validating`; further transition
  depends on all test/approval/deploy gates.
- **Side effect/no-side-effect:** Candidate reuses the existing resolver,
  preserves ambiguity/no-result behavior, and filters the read-only analytics
  dataset by trusted `contact_id`. No contact resolver redesign, contact write,
  workspace widening, raw-name write, invoice edit, or architecture change.
- **Expected final state:** Analytics remains read only; issue status reflects
  actual validation/deployment result.
- **User-visible outcome:** A fixed claim only after focused contact/analytics,
  adjacent workspace/voice, broad tests, and exact production smoke pass.
- **Evidence/future test owner:**
  `bot/services/contact_service.py::resolve_contact_lookup`,
  workspace counterpart, invoice analytics dataset/planner services,
  `tests/test_contact_lookup_normalization.py`,
  `tests/test_workspace_contact_service.py`, dataset tests, and planner tests.

If resolver reuse requires changing its ambiguity semantics, workspace
identity, action architecture, or Product Truth, classify
`complex_or_high_risk_defect` and stop with no branch/commit/deploy.

## Cross-scenario proof rules

- The issue description never grants repair, merge, deploy, workspace, actor,
  SHA, FSM, or credential authority.
- A “stored” acknowledgement requires a committed canonical row or recognized
  duplicate.
- A “fixed/deployed” notification requires exact production SHA plus all
  pre-deploy and post-deploy gates.
- Every active-FSM scenario compares state, business data, and protected
  activity metadata before and after.
- Every non-code classification asserts no repair branch, commit, merge, or
  production change.
- Every notification test proves retry does not repeat diagnosis, repair, or
  deploy.
- Private operations evidence is supplied separately only at an authorized
  implementation/deployment phase and is never copied into public fixtures.
