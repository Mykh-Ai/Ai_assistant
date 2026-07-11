# Conversation Acceptance Proof Contract

## Purpose

This contract defines the post-implementation proof required before a new or
materially changed top-level action, structured slot, canonical in-FSM control,
subflow, preview/confirmation flow, callback flow, or state-aware text/voice
route may be called ready for commit or human review.

The proof exists to prevent false-green completion. Passing resolver, handler,
or service unit tests does not prove that a real user message reaches the
correct action, carries the correct slots, enters the correct state, continues
after clarification, executes only the intended side effect, and exits in the
correct state across text, voice, and buttons.

The correct term is **Conversation Acceptance Proof** because the artifact
proves the complete stateful user conversation. It is not a conversion metric
and not merely a list of tests.

## Normative Status

This proof is mandatory after implementing or materially changing:

- a top-level action or semantic alias boundary;
- a structured top-level slot;
- an in-FSM control or decision family;
- a multi-turn user journey;
- voice/text/button convergence;
- preview, approval, edit, cancel, save, delete, pay, send, or mark-paid flows;
- active-FSM navigation or stale-state behavior;
- callbacks that can authorize or execute side effects.

For a stateless internal refactor with no public route or behavior change, the
implementation summary may mark this contract not applicable and explain why.

Companion contracts:

- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`;
- the task-specific approved Architecture Design Proof;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/Implementation_Agent_Checklist.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`.

## Core Rule

The implementation agent must prove the route from the real public entrypoint,
not only by directly calling the final helper.

Required proof shape:

```text
exact user input
-> actual public entry mode
-> guards and current state
-> actual resolver result
-> canonical action + structured slots
-> actual handler/helper symbol
-> observed FSM transitions
-> canonical decision token where applicable
-> observed side effect or explicit no-side-effect
-> observed final state
-> observed user-facing response / keyboard
```

A direct unit test of the final handler may support the proof, but it cannot
replace a journey test or smoke trace that starts at the public route.

## Proof Verdicts

Use exactly one final verdict:

- `safe_to_commit` — every required scenario passes, no material design
  deviation remains, and runtime behavior is proven to the declared scope;
- `needs_revision` — implementation defects or missing required evidence remain;
- `blocked_by_design_gap` — the approved architecture is incomplete or
  contradicted by runtime and requires an architecture decision;
- `runtime_not_proven` — code may exist, but required journey/server/manual
  evidence was not run or is insufficient.

`safe_to_commit` is not merge or deploy approval.

## Artifact Location

Recommended path:

```text
docs/evals/<task_id>_conversation_acceptance_proof.md
```

The proof may live in a PR/task artifact only when the repository convention
explicitly allows it, but it must remain reviewable and linked from the final
agent output and `PROJECT_LOG.md` where appropriate.

## Evidence Rules

Evidence must be exact and reproducible.

Allowed evidence:

- automated test name and exact command/result;
- deterministic integration test beginning at the public route;
- server/container smoke with exact input and observed output;
- manual Telegram smoke with exact input, account/setup state, observed state
  or logs, and pass/fail;
- focused logs that show route/action/slot/state without secrets or personal
  data;
- rendered artifact/manual review where the journey produces a file.

Every trace must disclose:

- whether LLM/STT/external services were real, mocked, stubbed, or bypassed;
- whether the route began at the real public handler/router;
- whether the side effect used a temporary/test store or production-like store;
- whether server smoke was in scope and actually run.

Forbidden evidence shortcuts:

- “all tests passed” without naming the relevant scenarios;
- model confidence or code inspection alone;
- direct final-handler calls presented as full conversation proof;
- positive-path evidence with no nearby-action regression;
- hidden manual assumptions about slots, state, or callback context;
- omitting tests/evals not run.

## Required Proof Sections

### 1. Identity And Declared Scope

```text
Task:
Branch / commit or working-tree reference:
Approved Architecture Design Proof:
Declared implementation status:
Declared Product Truth status:
Agent:
Date:
Final verdict:
```

### 2. Design-To-Code Mapping

Map each material architecture requirement to the implementation owner and
evidence.

| Design requirement | Implemented owner | Test/eval evidence | Status |
|---|---|---|---|
| canonical action + slots | file::symbol | test name | pass/fail |
| clarification continuation state | file::state/handler | journey test | pass/fail |
| voice convergence | file::helper | voice route test | pass/fail |

Any deviation from the approved design must be listed explicitly:

```text
design requirement:
implemented difference:
reason:
risk:
architect approval status:
```

An unapproved material deviation prevents `safe_to_commit`.

### 3. Environment And Evidence Boundary

Record:

```text
Python/runtime version:
Test command environment:
LLM: real | mocked | disabled
STT: real | mocked | transcript injection | disabled
External APIs: real | mocked | disabled
Database/storage: temporary | fixture | local real | server
Authorization account/setup:
Server/container smoke: run | not run
```

### 4. Public Journey Trace Format

Use one trace per scenario.

```text
Scenario id and name:
Purpose:
Precondition / account state:
Entry mode: text | command | voice | button | file
Exact user input(s):
State before each input:
Observed guard result:
Observed resolver result:
Observed canonical action:
Observed structured slots:
Observed handler/helper:
Observed state transition(s):
Observed canonical decision token, if any:
Expected side effect:
Observed side effect or explicit no-side-effect:
Observed final state:
Observed user-facing response / keyboard behavior:
Evidence references:
Result: pass | fail | not_applicable
Notes / mocked boundaries:
```

A multi-turn scenario must list every user input and every state transition in
order. Do not collapse the middle of the conversation into “then it works”.

### 5. Mandatory Scenario Matrix

Apply every relevant row. Marking `not_applicable` requires a reason.

| Scenario | Required proof |
|---|---|
| Primary text happy path | Starts from real public text route and reaches intended result |
| Action plus slots in one message | Resolver returns correct action and structured slots; handler receives them |
| Missing slot | Enters explicit pending state and asks for only the missing information |
| Invalid/ambiguous slot | Fails safe, remains recoverable, and does not execute a write default |
| Clarification continuation | Next message is consumed by the intended state handler, not idle top-level routing |
| Command path | Command converges into the same owner or documented equivalent path |
| Voice path | Voice transcript passes active-FSM/state routing and reaches the same business helper |
| Voice exclusion | Precision/destructive state rejects voice as designed, preferably before STT where required |
| Button/text/voice convergence | Equivalent decisions produce one canonical token and shared execution path |
| Active FSM ownership | Existing state wins over idle top-level routing for ordinary continuation input |
| Navigation/cancel/back | Shared guard or designed state behavior exits/returns safely |
| Post-success exit | Correct final state, keyboard removal/showing, and next-step message |
| Unknown | Bounded recovery with no hidden side effect and no useful-state loss unless designed |
| Nearby-action negative space | Representative old/neighbor inputs still route to their original actions |
| Informational capability question | Product Truth / InfoHelp answer occurs without action execution or writes |
| Wrong-state callback | Fails closed with no business side effect |
| Stale/expired/legacy callback | Fails closed with no business side effect |
| Duplicate callback / idempotency | No duplicate write/send/delete/pay effect where applicable |
| Unauthorized user | No STT/LLM/LMM/temp/storage/DB/business side effect before rejection |
| Tenant isolation | Lookups/writes remain scoped to the current user/workspace |
| Persisted-data/file output | Correct object/file is created or modified; failure path is safe |
| Existing regression journey | At least one old full journey on the shared layer remains correct |

### 6. Semantic Boundary Proof

For each nearby action defined in the Architecture Design Proof, provide at
least one exact input and observed result.

| Exact input | Expected action/status | Observed action/status | Side effect | Result |
|---|---|---|---|---|

The proof must include:

- positive examples for the changed action;
- `not_this` examples;
- shared verbs and shared business nouns;
- read-only versus write/destructive cases;
- top-level versus in-FSM meanings;
- ambiguous input expected to clarify or return `unknown`.

### 7. Slot Transfer And Validation Proof

For every new or changed slot, prove:

| Slot case | Resolver output | Python validation/default | Handler received | Result |
|---|---|---|---|---|
| valid supplied | structured value | accepted | exact value | pass/fail |
| missing defaultable | missing | explicit business default | default value | pass/fail |
| missing required | missing | clarification | no write | pass/fail |
| invalid | invalid/out of range | reject/clarify | no unsafe fallback | pass/fail |
| no-LLM fallback | unavailable | documented narrow fallback | value/result | pass/fail/N/A |

A resolver test that returns slots is insufficient if no route test proves the
slots reach the runtime owner.

### 8. FSM And Recovery Proof

Provide the observed transition table:

| Scenario | State before | Input | State after | Side effect allowed/executed | Result |
|---|---|---|---|---|---|

Prove where applicable:

- entry into the correct pending state;
- continuation after clarification;
- remain-in-state behavior for unknown input;
- return to the correct parent/preview state after a sub-action;
- cleanup on cancel;
- final clear/next state after success;
- stale-state recovery;
- no resurrection of stale state data;
- fresh active-FSM safe switching only if the approved architecture supports
  and proves restoration/cleanup.

### 9. Decision And Callback Safety Proof

Record:

- DecisionResolver family;
- canonical tokens from text, voice transcript, and buttons;
- shared state-aware helper;
- authorization and expected-state checks;
- timestamp/nonce/pending-context checks;
- expiry;
- wrong-state, stale, legacy, and duplicate behavior;
- exact destructive typed-confirmation behavior where applicable.

Any ambiguous input that executes a write action is an automatic failure.

### 10. Side-Effect Proof

For every declared side effect, provide:

| Side effect | Expected trigger | Observed only after validation/confirmation | Failure/rollback behavior | Evidence | Result |
|---|---|---|---|---|---|

Also prove at least one applicable no-side-effect path:

- informational question;
- `unknown`;
- invalid slot;
- cancel;
- wrong-state/stale callback;
- unauthorized user.

### 11. Product Truth And InfoHelp Proof

Show exact capability/how-to questions and observed status/answer behavior.

Required checks:

- status matches implemented maturity;
- supported subset is described accurately;
- limitations and setup/admin/external-credential requirements are explicit;
- forbidden claims are absent;
- asking a question does not execute the business action;
- direct executable requests still route before InfoHelp where designed.

### 12. Test And Eval Record

List exact commands and results:

```text
Focused tests:
- <command> -> <result>

Journey/integration tests:
- <command> -> <result>

Full suite:
- <command> -> <result or not run and why>

Manual/server smoke:
- <scenario> -> <result or not run and why>
```

A full-suite pass is useful regression evidence but does not replace the named
journey scenarios.

### 13. Documentation And Registry Synchronization

Record status for:

- Canonical Action Registry;
- In-Action Response Registry;
- Product Truth;
- InfoHelp;
- TZ / focused runtime contract;
- Evaluation artifact;
- README/navigation where public surfaces changed;
- CHANGELOG;
- PROJECT_LOG.

### 14. Remaining Gaps And Honest Completion Boundary

List:

- unimplemented branches;
- voice exclusions;
- server/deploy work not performed;
- migrations not performed;
- real external-service smoke not performed;
- known architecture gaps;
- follow-up tasks that are evidence-backed, not invented backlog.

### 15. Final Verdict

Provide:

```text
Verdict: safe_to_commit | needs_revision | blocked_by_design_gap | runtime_not_proven

Reason:
- <load-bearing evidence>

Blocking failures, if any:
- <exact scenario and failure>

Non-blocking limitations:
- <declared boundary>
```

## False-Green Rejection Rules

The proof is rejected when any of these occurs:

- the agent proves only resolver and final-handler units but not the route
  between them;
- the action is recognized but structured slots are not proven to reach the
  handler;
- a clarification message is shown but the continuation state is not proven;
- text is proven but reachable voice falls through another router;
- buttons are proven but text/voice use different business logic;
- positive examples pass but nearby actions are not checked;
- the final side effect succeeds but the post-success state/keyboard is wrong
  or unproven;
- ambiguous/unknown input can execute a write default;
- stale or wrong-state callbacks can execute business side effects;
- Product Truth/InfoHelp claims exceed runtime evidence;
- tests not run are hidden;
- a material design deviation lacks architect approval.

## Agent No-Go Rules

The implementation agent must not:

- create this proof before actually running the cited evidence;
- copy expected results from the architecture design and present them as
  observed results;
- call a mocked resolver/STT/external service real;
- omit the public-entry boundary;
- omit exact inputs or state transitions;
- summarize a failed mandatory scenario as a non-blocking note;
- use `safe_to_commit` while a required journey is failing or unproven;
- claim merge, deploy, migration, or production verification that did not
  occur.
