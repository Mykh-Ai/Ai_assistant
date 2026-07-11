# Evaluation And Smoke Test Standards

## Purpose

This contract defines how OfficeFlow / FakturaBot proves that a product or AI
change works for a real user. Unit tests are necessary, but they do not prove a
complete conversation, truthful Product Truth, safe state handling, or absence
of hidden side effects.

Use this contract for AI/LLM behavior, Product Truth and InfoHelp, FSM flows,
voice/text/button parity, callbacks, destructive or sensitive actions,
authorization and tenant boundaries, document intake, storage/migrations, PDF
layout, and deployment smoke.

Companion contracts include `AGENTS.md`,
`docs/Implementation_Agent_Checklist.md`,
`docs/Code_Agent_Handoff_Contract.md`,
`docs/Canonical_Decision_Resolver_Contract.md`,
`docs/llm/New_Action_Design_Checklist.md`, and, for new or materially changed
top-level/subflow/FSM work,
`docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md` plus the
approved task-specific Architecture Design Proof.

## Core Rule

A change is not complete until the evidence matches the claimed maturity and
scope. Do not call a fallback an AI layer, a partial route supported, or a set
of component tests a proven user journey.

## Evaluation Layers

### Unit tests

Use for deterministic parsing, validation, registries, services, exact values,
and fail-safe branches.

### Handler and integration tests

Use for public routing, FSM transitions, DecisionResolver, callbacks,
authorization, tenant scoping, DB/file effects, and text/voice convergence.

### Product UX smoke

Use realistic user inputs to prove discoverability, truthful answers, recovery,
next steps, and no hidden action execution. Automate when practical; otherwise
record an explicit manual smoke.

### Visual and layout evaluation

For PDF/layout changes, verify rendered output, wrapping, long values,
multi-item cases, QR/Pay by Square placement, footer placement, and regressions.
Code compilation alone is not evidence.

### Migration, server, and external-service smoke

When persisted data, paths, credentials, external services, or deployment are
in scope, record backup/rollback readiness, tenant isolation, failure behavior,
post-deploy checks, and whether the evidence used a real or mocked service.

## Conversation Acceptance Proof

This section is the canonical owner of post-implementation acceptance evidence
for new or materially changed top-level actions, structured slots, canonical
in-FSM controls, subflows, previews/confirmations, callbacks, active-FSM
navigation, and state-aware text/voice/button routes. Do not create a parallel
acceptance-proof contract.

### Verdict

Use exactly one:

- `safe_to_commit` — all applicable required scenarios pass, no unapproved
  material design deviation remains, and the declared runtime scope is proven;
- `needs_revision` — an implementation defect or required evidence gap remains;
- `blocked_by_design_gap` — the approved architecture is incomplete or is
  materially contradicted by current runtime and needs an architect/user
  decision;
- `runtime_not_proven` — code may exist, but required journey, manual, server,
  or external-service evidence was not run or is insufficient.

`safe_to_commit` is not merge or deploy approval.

### Artifact

Prefer:

```text
docs/evals/<task_id>_conversation_acceptance_proof.md
```

The artifact must reference the approved Architecture Design Proof and record
branch/commit or working-tree state, environment, mocked versus real
boundaries, tests/evals not run, and the final verdict.

### Public-entry trace

At least one applicable trace must start at the real public router/handler, not
at a final helper. For every scenario record:

```text
scenario id and purpose
precondition / user / workspace state
entry mode: text | command | voice | button | file
exact user input(s)
state before each input
authorization / active-FSM / callback guard result
observed resolver action and structured slots
observed Python handler/service owner
observed FSM transitions
observed canonical decision token, if any
expected and observed side effect or explicit no-side-effect
idempotency / rollback result where applicable
observed final state
observed user-facing response and keyboard behavior
evidence reference; real/mocked/disabled boundaries
result: pass | fail | not_applicable
```

### Required scenario matrix

Apply every relevant case; `not_applicable` requires a reason:

1. Primary text happy path from the public entrypoint.
2. Action plus structured slots in the first message.
3. Missing required slot enters an explicit continuation state.
4. Invalid or ambiguous slot fails safe and does not default to a write.
5. Clarification reply is consumed by the intended state handler, not idle
   top-level routing.
6. Command path converges into the same owner where applicable.
7. Voice reaches the same state-aware business helper after STT, or an exact
   value/destructive exclusion is explicitly tested.
8. Equivalent buttons, text, and voice map to one canonical decision and shared
   execution helper.
9. Active FSM wins over idle top-level routing for ordinary continuation input.
10. Back, cancel, navigation, stale recovery, and post-success exit state.
11. Nearby-action and `not_this` negative space.
12. `unknown` has no hidden side effect or accidental useful-state loss.
13. Product Truth / InfoHelp questions do not execute the action.
14. Wrong-state, stale, expired, legacy, and duplicate callbacks fail closed.
15. Unauthorized users cannot trigger STT/LLM/LMM, temp files, DB/storage, or
    business effects.
16. Tenant/workspace isolation.
17. Persisted-data/file-output success and failure safety where applicable.
18. At least one unchanged old journey through every modified shared layer.

### Design-to-code and slot evidence

Map every material Architecture Design Proof requirement to a file/symbol and a
named test/eval. For any difference record the design requirement, implemented
difference, reason, risk, and architect/user approval status. An unapproved
material difference prevents `safe_to_commit`.

For each changed slot prove, where applicable: valid supplied value, missing
value with an explicit Python-owned default, missing required value,
invalid/out-of-range value, precision boundary, and documented no-LLM fallback.
Resolver output alone is insufficient; prove that the public route transfers
the slot to the Python owner and Python validates it.

### Side-effect and Product Truth evidence

For each side effect prove that it happens only after authorization, state and
slot validation, and required confirmation. Also prove at least one applicable
no-side-effect path such as capability question, `unknown`, invalid input,
cancel, stale callback, or unauthorized user.

Show exact capability/how-to questions and verify Product Truth status,
limitations, setup/admin/external-credential requirements, forbidden claims,
and safe next steps. Informational questions must not execute the action.

### False-green rejection

Reject the proof when any of these is true:

- only resolver, service, or final-handler tests are shown;
- action recognition is proven but slot transfer is not;
- clarification copy is shown without a proven continuation state;
- text works but reachable voice follows another business route;
- buttons, text, and voice duplicate business logic instead of converging;
- positive examples pass but neighboring actions are not checked;
- the data mutation works but final FSM state or keyboard is wrong/unproven;
- ambiguous or `unknown` input executes a write default;
- stale/wrong-state/duplicate callbacks can repeat a business effect;
- Product Truth or InfoHelp claims exceed runtime evidence;
- tests/evals not run are hidden;
- a material design deviation lacks approval.

## Baseline Product Smoke Set

For user-facing changes, select relevant scenarios from this baseline:

- unknown, approved, and ready users through `/start` and `/menu`;
- arbitrary capability and how-to questions with truthful Product Truth status;
- plausible unsupported request with a safe next step and no false promise;
- confused input inside active FSM with state-aware recovery and cancel path;
- sensitive/destructive action with deterministic confirmation and voice
  precision boundary;
- unauthorized and cross-tenant attempts with no AI/storage/business effect;
- customization draft/edit/approve/cancel and no save before confirmation;
- self-learning confirmed write, rejection no-write, tenant isolation, and no
  Product Truth/canonical-action mutation;
- document intake classification, preview approval, unknown type, and active-FSM
  ownership;
- PDF long-text, multi-item, QR, footer, and manual/snapshot review;
- code-agent handoff package with approved design, tests/evals, no-go rules, and
  human review before merge/deploy.

## Evaluation Record

Record:

```text
feature_or_layer
declared_maturity_level
product_truth_status
touched_scopes
unit_tests
handler_integration_tests
product_ux_evals
conversation_acceptance_proof
visual_layout_evals
migration_server_external_smoke
manual_checks
known_gaps
not_run_and_why
decision
```

The record may live in `PROJECT_LOG.md`, a task/PR summary, or the dedicated
eval artifact.

## Commands And Manual Evidence

Default full test command from repository root:

```powershell
python -m pytest -q
```

Focused commands are allowed during development. If the full suite or required
manual/server/external smoke was not run, state exactly why.

Manual evidence must state setup, exact input, expected behavior, observed
behavior, pass/fail, artifacts/screenshots where relevant, and remaining risk.

## Completion Language

Use evidence-matched wording such as:

- `Level 1 fallback implemented and tested.`
- `Docs-first contract added; runtime not implemented.`
- `Partial support implemented for text only.`
- `Runtime supports X; Y requires setup.`

Do not say a layer, integration, or phase is complete when the required Product
Truth, journey proof, visual review, migration/server smoke, or external setup
is missing.

## No-Go Rules

Do not:

- accept unit/component tests alone for a public stateful journey;
- replace evals with model confidence;
- hide tests, smoke, or external checks not run;
- skip nearby-action, active-FSM, authorization, tenant, or no-side-effect
  evidence;
- ignore visual review for layout changes;
- ignore migration/server checks when persisted data or deployment is touched;
- create another standalone Conversation Acceptance Proof contract.
