# Top-Level And Subflow Architecture Design Proof Contract

## Purpose

This contract defines the architect-owned proof that must exist before an
implementation prompt is written for a new or materially changed top-level
action, canonical in-FSM control, subflow, preview, confirmation flow, callback
flow, or state-aware voice/text route in OfficeFlow / FakturaBot.

It exists because project history repeatedly showed a false-completion pattern:
a canonical token, handler, registry row, and focused tests were present, but
the complete user journey was not designed or proven. Missing slot transfer,
wrong FSM transitions, voice bypasses, nearby-action collisions, unsafe
`unknown` defaults, stale callbacks, and Product Truth drift then appeared in
live smoke.

This document moves those decisions to the architecture stage. The
implementation agent must implement an approved design; it must not invent the
missing product or conversation architecture while coding.

## Normative Status

This is a mandatory pre-handoff contract for work that adds or materially
changes any of the following:

- a canonical top-level action;
- a top-level alias or semantic action boundary;
- a structured action slot or slot group;
- an in-FSM canonical decision or control;
- a multi-step subflow;
- a preview / approve / edit / cancel flow;
- a callback that can execute or authorize a side effect;
- text/voice/button convergence;
- active-FSM navigation, stale-state recovery, or safe switching;
- a new user-visible Product Truth / InfoHelp capability that starts or
  controls a business workflow.

It is normally not required for a pure internal refactor with no user-visible
route, no state change, no new semantic input, and no side-effect boundary
change. The task must explicitly say why the contract is not applicable.

Companion contracts:

- `docs/Implementation_Agent_Checklist.md`;
- `docs/Code_Agent_Handoff_Contract.md`;
- `docs/Evaluation_and_Smoke_Test_Standards.md`;
- `docs/llm/New_Action_Design_Checklist.md`;
- `docs/llm/Conversation_Acceptance_Proof_Contract.md`;
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`;
- `docs/Canonical_Decision_Resolver_Contract.md`;
- `docs/llm/Canonical_Action_Registry.md`;
- `docs/llm/In_Action_Response_Registry.md`.

## Core Rule

No implementation handoff may be written until the architect can show the
complete intended route:

```text
user input
-> entry mode
-> authorization / active-FSM ownership
-> bounded semantic resolution
-> canonical action + structured slots
-> Python handler / service owner
-> FSM transition or immediate completion
-> decision / callback boundary where applicable
-> validated side effect or explicit no-side-effect
-> final state and user-facing response
-> Product Truth / InfoHelp explanation
```

A list of files to edit is not architecture proof. A canonical token is not
architecture proof. A handler sketch is not architecture proof.

## Responsibility Split

### Product owner / requester

Provides:

- the business need;
- desired user outcome;
- explicit constraints and priorities;
- approval for the scoped change.

### Architect / prompt author

Owns:

- capability classification;
- top-level versus subflow decision;
- semantic boundaries and nearby-action separation;
- structured slot contract;
- route and convergence design;
- FSM graph and recovery behavior;
- side-effect ownership;
- Product Truth / InfoHelp target state;
- negative-space and acceptance scenarios;
- explicit unresolved gaps and out-of-scope boundaries.

The architect must inspect current docs, code owners, tests, and relevant
`PROJECT_LOG.md` history before producing the proof.

### Implementation agent

Owns:

- read-only verification of the design against the repository;
- the smallest safe implementation that follows the approved design;
- tests, evals, docs synchronization, and exact evidence;
- reporting any design-to-runtime contradiction before inventing a new
  architecture;
- producing the post-implementation Conversation Acceptance Proof.

### Reviewer / human approval gate

Owns:

- accepting or rejecting design deviations;
- accepting the Conversation Acceptance Proof;
- merge, deploy, migration, and server approval where applicable.

## Evidence Standard

Every material design claim must cite current evidence using at least one of:

- current file and symbol;
- current test and test name;
- canonical registry row;
- active contract section;
- relevant recent `PROJECT_LOG.md` entry;
- explicit statement that no current owner/evidence exists.

Preferred notation:

```text
Evidence:
- bot/handlers/work_time.py::handle_generate_report
- bot/services/semantic_action_resolver.py::resolve_top_level_action
- tests/test_work_time_routing.py::test_...
- PROJECT_LOG.md — 2026-07-10 OfficeFlow Work-Time Report Period Slots
```

Do not use archived docs as current implementation evidence.

## Gate 1 — Classify The Change Before Naming An Action

The architect must decide which class applies:

1. **New top-level business intent** — the user starts a distinct standalone
   business operation.
2. **Extension of an existing top-level action** — same business intent, new
   slot, mode, supported object, period, filter, or outcome.
3. **Sub-action / in-FSM control** — meaningful only inside an active workflow.
4. **Structured slot only** — the action already exists; natural language must
   provide another bounded value.
5. **Deterministic internal strategy / fast-path** — not a public canonical
   action.
6. **Product Truth / InfoHelp only** — informational behavior, no executable
   action.
7. **Reserved / planned capability** — contract marker only; no executable
   runtime owner.

A new top-level action is forbidden unless the proof explains why classes 2–6
do not fit.

Examples of wrong top-level creation:

- a report action for one particular period when the existing analytics action
  should accept a period slot;
- a separate action for one object field inside an existing edit flow;
- a public action for an internal deterministic strategy;
- a token exposed as `implemented` before a Python runtime owner exists.

## Gate 2 — Required Architecture Design Proof

The proof must contain every applicable section below.

### 1. Task Identity And Product Need

```text
Task id / name:
Business need:
User-visible outcome:
Current Product Truth status:
Target Product Truth status:
Risk level:
Architect:
Date:
```

State what user problem is solved without describing implementation first.

### 2. Architecture Classification

```text
Chosen class:
Why this is / is not a new top-level action:
Existing action or flow extended, if any:
Existing runtime owner:
Evidence:
```

### 3. Canonical Action Contract

For a top-level or canonical in-FSM action:

```text
canonical_token:
status: implemented | partial | reserved | planned | unclear
plain-language meaning:
runtime owner:
allowed_actions contexts:
entry modes:
```

If status is `reserved` or `planned`, it must not be exposed in executable
`allowed_actions` as if it were implemented.

### 4. Semantic Boundary Matrix

List the closest neighboring actions. Do not limit this to actions that share
the same verb; include actions that share the same business noun, object, or
user phrasing.

| User meaning / example | Expected action | Why | Must not become |
|---|---|---|---|
| positive example | new/changed action | semantic reason | nearby action |
| negative-space example | existing action | separation reason | new action |
| ambiguous example | clarification / unknown | missing evidence | write action |

For every ambiguous action hint, define:

```text
meaning:
positive_examples:
not_this:
```

Examples are semantic context, not a Python phrase whitelist.

### 5. Structured Slot Contract

Every value supplied together with the action must be designed before coding.

| Slot | Type / allowed values | Source | Required | Default owner | Invalid behavior | Precision boundary |
|---|---|---|---|---|---|---|
| period.month | integer 1-12 | bounded LLM | no | Python business date | clarification / fail loud | voice allowed if validated |

Required decisions:

- which values the bounded LLM extracts;
- which values Python derives deterministically;
- which values Python validates;
- which missing values receive explicit business defaults;
- which invalid/ambiguous values require clarification;
- which values are typed/file-only and may not be filled by voice;
- whether a no-LLM compatibility fallback exists and why it is non-primary.

Python must not become the primary multilingual dictionary for months, dates,
periods, customer/service wording, or other variable business slots.

### 6. Public Route And Convergence Map

Define each reachable entry mode and the exact convergence point.

| Entry mode | Public entry | Guards before AI/business logic | Resolver/helper | Shared Python handler | Result |
|---|---|---|---|---|---|
| text | idle message router | authorization, active FSM | top-level resolver | handler symbol | state/action |
| command | command handler | authorization | deterministic action | same handler/helper | state/action |
| voice | voice handler after STT | authorization before STT, active FSM after STT | same resolver/state helper | same handler/helper | state/action |
| button | callback router | authorization, expected state, expiry | canonical token | same handler/helper | state/action |

Rules:

- active FSM must be checked before idle top-level execution;
- `voice.py` must not own a parallel business architecture or phrase
  dictionary;
- text, voice transcript, and buttons must converge into the same state-aware
  Python helper where they represent the same decision;
- informational questions must not execute the action;
- public-entry routing must happen exactly once.

### 7. FSM Graph And State Ownership

Provide the state graph, not only a state list.

```text
IDLE
  -> action entry
  -> waiting_<missing_slot>
      -> valid input -> preview / next state
      -> ambiguous input -> remain in same state
      -> cancel -> safe exit
      -> back -> previous recoverable state
      -> stale -> clear/cleanup + bounded recovery
  -> waiting_preview_decision
      -> approve -> side effect -> final state
      -> edit -> edit subflow
      -> cancel -> cleanup -> final state
```

For every state define:

| State | Entry condition | Accepted inputs | Unknown behavior | Side effects allowed | Success state | Back/cancel | Stale behavior |
|---|---|---|---|---|---|---|---|

The proof must explicitly cover:

- immediate completion versus pending-state entry;
- clarification state after invalid or incomplete input;
- return state after every sub-action;
- old state-data cleanup;
- active-FSM navigation guard;
- whether fresh active-FSM safe switching is supported or remains a documented
  architecture gap.

Showing a clarification message without setting the matching pending state is
not a valid design.

### 8. Decision, Confirmation, And Callback Contract

For every confirmation-like reply:

```text
decision family:
canonical outputs:
text path:
voice path:
button token:
state/context required:
expiry / timestamp / nonce:
idempotency behavior:
wrong-state / stale behavior:
```

Rules:

- use `bot/services/decision_resolver.py` for confirmation-like decisions;
- no local multilingual yes/no parser;
- ambiguous input must not become a write-side default;
- callbacks must fail closed when unauthorized, stale, legacy, expired,
  mismatched, or missing pending context;
- destructive exact-typed exceptions must be explicit and must reject voice
  before STT when the current contract requires typed text.

### 9. Side-Effect And Ownership Map

| Side effect | Trigger | Python owner | Validation before effect | Rollback / fail-safe | Idempotency |
|---|---|---|---|---|---|

Include:

- DB writes;
- file writes, moves, deletes, and cleanup;
- external API calls;
- emails/sends/uploads;
- invoice/contact/accounting/work-time mutations;
- FSM clears and persistent pending metadata.

LLM/STT/LMM/callback payloads may select bounded values; they do not own side
effects.

### 10. Authorization, Tenant, And Precision Boundaries

State:

- where authorization happens;
- whether authorization occurs before STT/LLM/LMM/temp files/storage;
- tenant/workspace keys used by every lookup/write;
- exact values forbidden through voice;
- destructive and cross-tenant fail-closed behavior.

### 11. User-Facing Response And Exit Contract

For each terminal and non-terminal outcome define:

- exact purpose of the response;
- whether a keyboard is shown or removed;
- next valid user action;
- resulting FSM state;
- whether the user returns to menu, previous preview, or another subflow;
- behavior after success, cancel, back, no-result, unsupported edit, and error.

A business operation is not complete if the data changed but the user is left
in the wrong state or with the wrong keyboard.

### 12. Product Truth And InfoHelp Contract

Define:

```text
capability_id:
status after implementation:
what the bot can truthfully say it does:
limitations:
setup/admin/external-credential requirements:
forbidden claims:
safe next steps:
answer to "Can you do this?":
answer to "How do I use this?":
```

Capability questions must not execute the action or create hidden side effects.

### 13. Negative-Space And Regression Contract

List old behavior the change must not steal or alter.

Minimum categories:

- closest canonical actions;
- top-level versus active-FSM behavior;
- read-only versus write/destructive behavior;
- outgoing invoice versus receipt/incoming-document behavior;
- current draft versus persisted object behavior;
- informational question versus executable request;
- text versus voice precision boundary;
- callbacks from stale or wrong flows;
- unauthorized and cross-tenant attempts.

### 14. Acceptance Scenario Contract

The architect must define the scenarios that the implementation agent will
later prove in the Conversation Acceptance Proof.

At minimum, where applicable:

1. primary text happy path from the public entrypoint;
2. primary voice path or explicit tested voice exclusion;
3. command/button path and convergence;
4. action with slots supplied in the first message;
5. missing/invalid/ambiguous slot clarification and continuation;
6. active-FSM ownership;
7. cancel and back;
8. post-success exit state;
9. nearby-action negative space;
10. `unknown` fail-safe with no side effect;
11. stale/wrong-state callback;
12. unauthorized/tenant isolation;
13. Product Truth / InfoHelp capability question with no execution;
14. old regression journey that must remain unchanged.

Each scenario must state:

```text
precondition
exact input(s)
expected canonical action and slots
expected state sequence
expected side effect or no-side-effect
expected final state
expected user-visible outcome
```

### 15. Out Of Scope And Known Architecture Gaps

Name every deferred behavior. Do not hide it inside implementation notes.

Examples:

- safe switch from a fresh unrelated FSM is not supported;
- voice cannot fill exact prices;
- edit branch remains unsupported;
- no server deploy in this task;
- no data migration;
- no broad alias self-learning.

### 16. Handoff Readiness Verdict

Use exactly one verdict:

- `ready_for_handoff` — all applicable sections are complete and evidence-backed;
- `needs_architecture_revision` — design choices are incomplete or internally
  inconsistent;
- `blocked_by_missing_evidence` — current repository/product truth cannot prove
  the required owner or boundary.

The implementation prompt may be written only for `ready_for_handoff`.

## Required Design Proof Artifact Template

Store the completed artifact in a task-specific location, for example:

```text
docs/architecture/<task_id>_architecture_design_proof.md
```

Template:

```text
# <Task> — Architecture Design Proof

Verdict: ready_for_handoff | needs_architecture_revision | blocked_by_missing_evidence

## 1. Task Identity And Product Need
...

## 2. Architecture Classification
...

## 3. Canonical Action Contract
...

## 4. Semantic Boundary Matrix
...

## 5. Structured Slot Contract
...

## 6. Public Route And Convergence Map
...

## 7. FSM Graph And State Ownership
...

## 8. Decision, Confirmation, And Callback Contract
...

## 9. Side-Effect And Ownership Map
...

## 10. Authorization, Tenant, And Precision Boundaries
...

## 11. User-Facing Response And Exit Contract
...

## 12. Product Truth And InfoHelp Contract
...

## 13. Negative-Space And Regression Contract
...

## 14. Acceptance Scenario Contract
...

## 15. Out Of Scope And Known Architecture Gaps
...

## 16. Evidence Index
...
```

## Architect No-Go Rules

The architect / prompt author must not:

- ask an implementation agent to decide whether a behavior is a top-level
  action, slot, subflow, or internal strategy without first doing the
  architecture classification;
- create a new canonical action only because a handler is easier to write;
- specify only positive examples and omit nearby-action negative space;
- omit structured slots and expect the handler to re-parse the full natural
  language request independently;
- make Python the primary multilingual phrase dictionary for bounded business
  semantics;
- design a clarification response without a continuation state;
- design an ambiguous/unknown branch that defaults to a write action;
- create separate text, voice, and button business logic;
- omit stale-state/callback behavior from a pending decision flow;
- mark a capability `implemented` without a reachable Python runtime owner;
- write an implementation prompt before the design proof verdict is
  `ready_for_handoff`;
- accept passing component tests as a substitute for the required
  post-implementation Conversation Acceptance Proof.
