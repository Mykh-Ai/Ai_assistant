# Top-Level And Subflow Architecture Design Proof Contract

## Purpose

This contract defines the architect-owned proof required before an
implementation prompt is written for a new or materially changed top-level
action, structured slot, canonical in-FSM control, subflow,
preview/confirmation flow, callback flow, or state-aware text/voice/button
route in OfficeFlow / FakturaBot.

It exists because project history repeatedly showed false completion: a token,
handler, registry row, and component tests existed, while slot transfer, FSM
continuation, voice parity, neighboring-action safety, callback expiry, final
state, or Product Truth remained undefined.

The implementation agent must receive an approved design. It must not invent
missing product or conversation architecture while coding.

## Scope And Ownership

Use this contract before designing or materially changing:

- canonical top-level actions and aliases;
- structured action slots or modes;
- canonical in-FSM decisions/controls;
- multi-step subflows and previews;
- callbacks that authorize or execute a business effect;
- text/command/voice/button convergence;
- active-FSM navigation, stale recovery, or safe switching;
- user-visible Product Truth / InfoHelp behavior that starts or controls a
  business workflow.

A pure internal refactor with no public route, semantic boundary, FSM, or
side-effect change may state why this proof is not applicable.

Responsibilities:

- **Product owner/user:** business need, desired outcome, constraints, approval.
- **Architect/prompt author:** classification, semantic boundary, slots, route,
  FSM, decisions/callbacks, side effects, negative space, Product Truth, and
  acceptance scenarios.
- **Implementation agent:** read-only verification, implementation of the
  approved design, tests/evals, and design-variance reporting.
- **Reviewer:** accepts design changes, evidence, merge, deployment, and
  migration decisions.

Companion owners:

- implementation gate: `docs/llm/New_Action_Design_Checklist.md`;
- task handoff/prompt: `docs/Code_Agent_Handoff_Contract.md`;
- post-implementation proof: the Conversation Acceptance Proof section of
  `docs/Evaluation_and_Smoke_Test_Standards.md`.

Do not create parallel contracts for those responsibilities.

## Core Rule

No implementation prompt may be written until the architect can show the
complete intended route:

```text
user input
-> entry mode
-> authorization / active-FSM ownership
-> bounded semantic resolution
-> canonical action + structured slots
-> Python handler/service owner
-> FSM transition or immediate completion
-> decision/callback boundary where applicable
-> validated side effect or explicit no-side-effect
-> final state and user-facing response
-> Product Truth / InfoHelp explanation
```

A list of files, token, or handler sketch is not an Architecture Design Proof.

## Evidence Standard

Every material claim must cite current evidence such as:

- file and symbol;
- test and test name;
- canonical registry row;
- active contract section;
- recent relevant `PROJECT_LOG.md` entry;
- explicit statement that no current owner/evidence exists.

Do not use archived docs as current implementation evidence.

## Required Design Proof

Create a task-specific artifact, preferably:

```text
docs/architecture/<task_id>_architecture_design_proof.md
```

It must contain every applicable section below.

### 1. Task Identity And Product Need

```text
task id / name
business need
user-visible outcome
current Product Truth status
target Product Truth status
risk level
date / architect
```

Describe the user problem before proposing implementation.

### 2. Architecture Classification

Choose exactly one primary class:

1. new top-level business intent;
2. extension of an existing top-level action;
3. sub-action / canonical in-FSM control;
4. structured slot or mode;
5. deterministic internal strategy / fast-path;
6. Product Truth / InfoHelp only;
7. reserved/planned capability.

State why the other plausible classes do not fit. A new top-level action is
forbidden when an existing action plus slot/subflow/internal strategy owns the
same business intent.

### 3. Canonical Action Contract

Where applicable define:

```text
canonical token
status: implemented | partial | reserved | planned | unclear
plain-language meaning
runtime owner
allowed-action contexts
entry modes
```

Reserved/planned tokens must not be exposed as executable implemented actions.

### 4. Semantic Boundary Matrix

List the closest neighboring actions, including shared verbs, nouns, business
objects, and top-level versus in-FSM meanings.

| Exact user meaning/input | Expected action/status | Why | Must not become |
|---|---|---|---|

For ambiguous actions include:

```text
meaning
positive_examples
not_this
```

Define when ambiguity becomes clarification or `unknown`; it must never become
a write default.

### 5. Structured Slot Contract

For each slot define:

| Slot | Type/allowed values | Source | Required | Default owner | Invalid behavior | Voice/precision boundary |
|---|---|---|---|---|---|---|

Explicitly decide:

- what the bounded LLM extracts within Python-provided schema/options;
- what Python derives deterministically;
- what Python validates;
- explicit defaults;
- clarification state for missing/invalid/ambiguous values;
- typed/file-only fields;
- any narrow non-primary no-LLM fallback.

Do not leave the handler to independently re-parse the full request or turn
Python into a multilingual business-phrase dictionary.

### 6. Public Route And Convergence Map

For every applicable entry mode define:

| Entry mode | Public entry | Guards | Resolver/helper | Shared Python owner | Result |
|---|---|---|---|---|---|
| text | | authorization, active FSM | | | |
| command | | | | | |
| voice | | authorization before STT, state guard after STT | | | |
| button | | authorization, state/context, expiry | | | |

Text, command, voice transcript, and buttons must converge where they represent
the same decision. `voice.py` must not own parallel business routing or
execution. Capability questions must not execute the action.

### 7. FSM Graph And State Ownership

Provide the graph, not only a state list. For every state define:

| State | Entry condition | Accepted input | Unknown behavior | Side effects allowed | Success/parent state | Back/cancel | Stale behavior |
|---|---|---|---|---|---|---|---|

Cover:

- immediate completion versus pending-state entry;
- continuation after missing/invalid input;
- return state after each sub-action;
- cleanup of old state data;
- active-FSM navigation and stale recovery;
- success, cancel, back, error, and no-result exits;
- keyboard removal/showing and next valid action;
- fresh unrelated-FSM switching only if preservation/restoration is designed
  and testable; otherwise declare the gap.

A clarification response without the matching pending state is invalid.

### 8. Decision And Callback Contract

For every confirmation/decision define:

```text
DecisionResolver family and canonical outputs
text path
voice path or exclusion
button token
required state/pending context
timestamp/nonce/expiry
wrong-state/stale/legacy/duplicate behavior
idempotency
```

Ambiguity, stale state, missing context, or unauthorized input must fail closed
before business effects.

### 9. Side-Effect And Ownership Map

| Side effect | Trigger | Python owner | Validation/confirmation before effect | Failure/rollback | Idempotency |
|---|---|---|---|---|---|

Include DB/files/storage/external calls, sends/uploads, business mutations, and
FSM/pending metadata. LLM/STT/LMM/callback payloads never own effects.

### 10. Authorization, Tenant, And Precision Boundaries

State:

- authorization point and whether it precedes STT/LLM/LMM/temp/storage;
- tenant/workspace keys for every lookup/write;
- exact values not allowed through voice;
- destructive/sensitive confirmation boundary;
- cross-tenant and unauthorized fail-closed behavior.

### 11. User-Facing Response And Exit Contract

For each terminal/non-terminal outcome define the response purpose, keyboard,
next valid user action, resulting FSM state, and destination: menu, parent
preview, next subflow, or safe recovery.

A correct data mutation with the wrong final state or keyboard is not a correct
design.

### 12. Product Truth And InfoHelp Contract

Define:

```text
capability id
status after implementation
truthful supported behavior
limitations and setup/admin/external-credential requirements
forbidden claims
safe next steps
answer to “Can you do this?”
answer to “How do I use this?”
```

Informational questions must not trigger the business action.

### 13. Negative-Space And Regression Contract

List old behavior the change must not steal or alter, including:

- closest canonical actions;
- top-level versus active-FSM behavior;
- read-only versus write/sensitive behavior;
- outgoing invoice versus external accounting document behavior;
- draft versus persisted object behavior;
- information question versus executable request;
- text versus voice precision boundaries;
- stale/wrong callbacks;
- unauthorized and cross-tenant attempts.

### 14. Acceptance Scenario Contract

Define exact scenarios that the implementation agent must prove under
`docs/Evaluation_and_Smoke_Test_Standards.md`.

For each scenario state:

```text
precondition
exact input(s)
expected canonical action and slots
expected state sequence
expected effect or explicit no-effect
expected final state
expected user-visible response/keyboard
```

At minimum, where applicable, cover text, voice or exclusion, command/button
convergence, action-plus-slots, clarification continuation, active-FSM
ownership, cancel/back, post-success exit, neighboring actions, `unknown`,
stale/wrong callbacks, authorization/tenant isolation, Product Truth/InfoHelp,
and an unchanged old journey.

### 15. Out Of Scope And Known Architecture Gaps

Name deferred behavior explicitly, including unsupported branches, voice
exclusions, safe switching gaps, migrations, server/deployment, external
credentials, or broader learning. Do not hide these inside implementation notes.

### 16. Evidence Index And Verdict

List all files/symbols/tests/contracts/log entries that support the design.

Use exactly one verdict:

- `ready_for_handoff` — all applicable decisions are complete and evidence-backed;
- `needs_architecture_revision` — decisions are incomplete or inconsistent;
- `blocked_by_missing_evidence` — current truth cannot prove the required owner
  or boundary.

The implementation prompt may be written only for `ready_for_handoff`.

## Handoff Rule

The prompt is created under `docs/Code_Agent_Handoff_Contract.md` and must
reference the exact approved proof. It must transfer, without reinterpretation:
classification, action boundary, slots, route, FSM graph, decision/callback
rules, side-effect ownership, negative space, Product Truth target, acceptance
scenarios, and out-of-scope gaps.

The implementation agent performs a read-only design verification under
`docs/llm/New_Action_Design_Checklist.md`. A material contradiction blocks
implementation; the agent does not redesign silently.

## Architect No-Go Rules

The architect/prompt author must not:

- delegate top-level versus slot/subflow/internal-strategy classification to the
  coding agent;
- create a new action because a new handler is easier;
- specify only positive examples;
- omit slot ownership or continuation states;
- make Python the primary natural-language business parser;
- design ambiguity or `unknown` as a write default;
- create separate text/voice/button business logic;
- omit stale/wrong callback behavior;
- mark a capability implemented without a reachable Python owner;
- write the implementation prompt before `ready_for_handoff`;
- accept component tests in place of the Conversation Acceptance Proof owned by
  `docs/Evaluation_and_Smoke_Test_Standards.md`;
- create duplicate handoff or acceptance-proof contracts.
