# New Canonical Action Implementation Guide

## Purpose

This is the canonical implementation gate for adding or materially changing a
top-level action, structured action slot, canonical in-FSM control, subflow,
preview/confirmation flow, callback flow, or state-aware text/voice/button
route in FakturaBot / OfficeFlow.

It exists because project history repeatedly showed the same failures: action
tokens without a reachable runtime owner, weak nearby-action boundaries,
Python phrase dictionaries replacing bounded semantic extraction, lost slots,
clarification without a continuation state, voice bypasses, local confirmation
parsers, stale callbacks, unsafe `unknown` defaults, and green component tests
without a proven user journey.

## Mandatory Architecture Gate

Before an implementation prompt is written, the architect must complete
`docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md` and a
task-specific Architecture Design Proof with verdict `ready_for_handoff`.

The proof must decide, before coding:

- new top-level versus extension, subflow, slot, internal strategy, or InfoHelp;
- action meaning and neighboring-action negative space;
- structured slots, defaults, validation, and precision boundaries;
- text/command/voice/button convergence;
- FSM graph, continuation, back/cancel, stale behavior, and exit state;
- DecisionResolver/callback contract;
- side-effect and tenant ownership;
- Product Truth / InfoHelp target;
- exact acceptance scenarios and out-of-scope gaps.

Do not use this guide to invent architecture. The implementation agent
implements an approved design and reports a contradiction instead of silently
redesigning it.

## Required Reading

Before editing, read:

1. `AGENTS.md`;
2. the approved task-specific Architecture Design Proof;
3. `docs/Product_Doctrine_2030.md`;
4. `docs/AI_Layer_Implementation_Standards.md`;
5. `docs/Product_Truth_Layer.md`;
6. `docs/Info_Help_Guidance_Layer.md`;
7. `docs/Evaluation_and_Smoke_Test_Standards.md`;
8. `docs/Implementation_Agent_Checklist.md`;
9. `docs/Code_Agent_Handoff_Contract.md`;
10. `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`;
11. `docs/Canonical_Decision_Resolver_Contract.md`;
12. `docs/llm/Canonical_Action_Registry.md`;
13. `docs/llm/In_Action_Response_Registry.md`;
14. `docs/llm/Bounded_Resolver_Prompt_Template.md`;
15. relevant domain, storage, access, migration, PDF, and recent
    `PROJECT_LOG.md` evidence.

## Read-Only Design Verification

Before code, verify the approved design against current code, docs, registries,
and tests. Report one status:

- `design_matches_runtime`;
- `minor_nonsemantic_variance` — symbol/file placement changed but approved
  semantics and ownership remain intact;
- `material_design_variance` — the current runtime contradicts action
  classification, slots, route, FSM, side-effect, safety, or Product Truth
  assumptions.

For `material_design_variance`, stop implementation and report the exact
contradiction plus the minimum architecture decision needed. Do not invent a
replacement architecture.

## Definition Of Done

A token or handler is not a completed action. Every applicable item must hold:

- [ ] Approved Architecture Design Proof exists and still matches runtime.
- [ ] Canonical token/status/meaning and Python runtime owner are explicit.
- [ ] A reserved/planned token is not exposed as implemented or placed in
      executable `allowed_actions` without a safe runtime owner.
- [ ] Nearby actions, `positive_examples`, and `not_this` boundaries are tested.
- [ ] Structured slots reach the runtime owner and are validated by Python.
- [ ] Missing/invalid/ambiguous input enters or remains in a recoverable state;
      `unknown` never defaults to a write.
- [ ] Text, command, voice transcript, and buttons converge into shared
      state-aware Python owners where semantically equivalent.
- [ ] Active FSM wins over idle top-level routing.
- [ ] Precision-sensitive values and destructive exact confirmations enforce
      typed/file-only boundaries where required.
- [ ] Confirmation-like decisions use `bot/services/decision_resolver.py`.
- [ ] Callback authorization, state/context, expiry, stale/legacy behavior, and
      idempotency are fail-closed.
- [ ] Side effects are Python-owned, scoped, validated, and tenant-safe.
- [ ] Post-success, cancel, back, no-result, and error states/keyboards are
      correct.
- [ ] Product Truth, InfoHelp, registries, focused docs, and logs are synchronized.
- [ ] The Conversation Acceptance Proof required by
      `docs/Evaluation_and_Smoke_Test_Standards.md` has an honest verdict.

If a required mode or branch is intentionally absent, mark the capability
`partial`, `reserved`, or explicitly not applicable. Do not call it implemented.

## Action Classification And Identity

Before adding a token, prove why the change is a distinct standalone business
intent rather than:

- an extension of an existing action;
- a structured slot or mode;
- an in-FSM control;
- an internal deterministic strategy/fast-path;
- Product Truth / InfoHelp only;
- a reserved/planned capability.

For a canonical action define:

```text
canonical token
status: implemented | partial | reserved | planned | unclear
plain-language product meaning
runtime owner
allowed-action contexts
entry modes
```

## Semantic Boundary

List the closest neighboring actions, including shared verbs, nouns, business
objects, and top-level versus in-FSM meanings. Every ambiguous action needs:

```text
meaning
positive_examples
not_this
```

These examples are semantic context, not a Python phrase whitelist. Tests must
prove both the new/changed action and representative old neighboring routes.

## Structured Slot Gate

For each slot define:

```text
name and type / allowed values
source: bounded LLM | Python deterministic | callback | typed text | file
required or optional
Python-owned default, if any
validation and invalid behavior
precision/voice boundary
continuation state for missing or ambiguous values
```

Rules:

- The bounded LLM may extract variable natural-language business slots only
  within Python-provided schema/options.
- Python validates, applies explicit business defaults, and executes.
- Python must not become the primary multilingual dictionary for months, dates,
  periods, customers, services, or other variable business semantics.
- Strict structural parsers or documented no-LLM compatibility fallbacks may
  exist, but they are non-primary and must fail safely.
- A resolver test is insufficient unless a public-route test proves the slots
  reach the handler/service.

## Public Route And Voice Gate

For each entry mode identify the public router, authorization and active-FSM
guards, resolver/helper, shared Python owner, and result.

Rules:

- authorization happens before STT/LLM/LMM/temp/storage/business work;
- active FSM is checked before idle top-level routing;
- `voice.py` remains transport/STT/state routing and does not own business phrase
  dictionaries or duplicate execution;
- unhandled active-FSM voice input does not fall through to idle routing;
- text, command, voice transcript, and callbacks route exactly once;
- capability/how-to questions go to Product Truth / InfoHelp without executing
  the action.

Voice may select bounded actions/options where safe. It must not fill
precision-sensitive exact values such as legal/tax identifiers, IBAN/email,
invoice references, prices/quantities/totals, long final descriptions, or exact
destructive confirmation where the flow requires typed input.

## FSM And Recovery Gate

For every state define entry condition, accepted inputs, unknown behavior,
allowed side effects, success state, back/cancel, stale behavior, and keyboard.

Prove:

- immediate completion versus pending-state entry;
- explicit continuation state after missing/invalid input;
- return to the correct parent/preview state after each sub-action;
- cleanup of obsolete state data;
- shared active-FSM navigation/stale-state guard;
- post-success final state and next step;
- fresh unrelated-FSM switching only when preservation/restoration is designed
  and tested; otherwise document the gap.

Showing clarification copy without setting the matching state is a failure.

## Decision And Callback Gate

All confirmation-like replies use `bot/services/decision_resolver.py` unless an
explicit exact typed sensitive-action exception is documented.

- [ ] Define decision family and canonical outputs.
- [ ] Buttons emit canonical tokens, not localized business logic.
- [ ] Text, voice transcript, and button callback converge into one state-aware
      helper.
- [ ] No local multilingual yes/no/approve/edit/cancel parser.
- [ ] Authorization and expected state/pending context are checked before effects.
- [ ] Timestamp/nonce/expiry is checked where available.
- [ ] Stale, legacy, missing, mismatched, and duplicate callbacks fail closed.
- [ ] Reply and inline keyboard lifecycles are specified separately.
- [ ] Every terminal success/cancel/no/error/timeout exit has an asserted final keyboard state.
- [ ] Non-terminal retry/edit/back explicitly retains, replaces, or removes the old keyboard.
- [ ] Owned stale/expired inline callbacks remove obsolete markup.
- [ ] Forbidden or unproven-ownership callbacks do not alter another user's message.
- [ ] Reply keyboard cleanup uses `ReplyKeyboardRemove`; `one_time_keyboard=True` is not treated as cleanup.
- [ ] Telegram markup-edit failures are logged and do not roll back a committed business effect.
- [ ] Public-wrapper tests assert keyboard cleanup, not only canonical token dispatch.
- [ ] Ambiguity never executes a write.

## Side Effects, Authorization, And Tenant Safety

List every DB/file/storage/external/FSM side effect and its Python owner.

- LLM/STT/LMM and callback payloads select bounded values only.
- Python validates preconditions and tenant/workspace scope.
- Queries/writes use the current user/workspace keys.
- No unauthorized AI call, temp file, directory, DB row, invoice, contact,
  supplier profile, or accounting document.
- DB/storage/path/schema changes require migration audit, backup, rollback, and
  approved server work.
- Cleanup is restricted to known temporary or tenant-owned paths.

## Product Truth And InfoHelp Gate

For the capability define status, supported subset, limitations,
setup/admin/external-credential requirements, forbidden claims, safe next steps,
and answers to “Can you do this?” and “How do I use this?”.

Executable requests must still route before InfoHelp where designed, but an
informational question must not mutate data or start the business action.

## Required Tests And Acceptance Evidence

Run focused tests, then the full suite when feasible:

```powershell
python -m pytest -q
```

Minimum relevant coverage:

- resolver token, slots, `unknown`, multilingual/noisy input, and nearby actions;
- public text/command route;
- voice reachability or tested exclusion;
- active-FSM ownership and clarification continuation;
- exact-value voice rejection;
- DecisionResolver family and no local parser;
- callback authorization/state/stale/expiry/idempotency;
- unauthorized and tenant isolation;
- side-effect, rollback, cleanup, and no-side-effect branches;
- Product Truth / InfoHelp capability questions;
- old journeys through modified shared layers;
- full Conversation Acceptance Proof from public entrypoints under
  `docs/Evaluation_and_Smoke_Test_Standards.md`.

If evidence is not run, state why and do not claim completion.

## Implementation Handoff And Final Output

The implementation prompt is owned by
`docs/Code_Agent_Handoff_Contract.md`. It must reference the exact approved
Architecture Design Proof and carry forward its classification, slots, route,
FSM graph, semantic negative space, decision/callback rules, side-effect
ownership, Product Truth target, acceptance scenarios, and out-of-scope gaps.
Do not create a parallel handoff contract or ask the coding agent to decide
these points.

The agent’s final output must report:

```text
docs/contracts read
design verification status
files changed
design-to-code mapping and deviations
implementation summary
tests/evals run and exact results
tests/evals not run and why
Product Truth / InfoHelp status
Conversation Acceptance Proof path and verdict
known limitations, migration/rollback/server notes
git status; no merge/deploy claim unless actually performed
```

## No-Go Rules

Do not:

- create a token or module to avoid extending the correct existing owner;
- expose planned/reserved behavior as implemented;
- replace bounded semantics with multilingual Python phrase dictionaries;
- re-parse the whole request independently after action/slot resolution;
- show clarification without a continuation state;
- put business routing/execution in `voice.py`;
- add local confirmation parsers;
- let `unknown` or ambiguity default to a write;
- weaken authorization, tenant, precision, active-FSM, stale-state, or callback
  guards;
- silently deviate from the approved Architecture Design Proof;
- treat passing component tests as proof of the complete user journey;
- create separate implementation-handoff or conversation-acceptance contracts
  that duplicate the existing owners.
