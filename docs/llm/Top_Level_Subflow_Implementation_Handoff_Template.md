# Top-Level And Subflow Implementation Handoff Template

## Purpose

This is the architect-facing template for writing an implementation-agent task
for a new or materially changed top-level action, canonical in-FSM control,
subflow, slot contract, preview/confirmation flow, or callback-driven business
journey.

The template may be used only after an Architecture Design Proof exists with
verdict `ready_for_handoff` under
`docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`.

The prompt must not ask the implementation agent to invent missing product or
conversation architecture. The agent begins with a read-only audit to verify
that the approved design still matches the repository. If current code
contradicts the design in a material way, the agent must report a design
variance instead of silently choosing a new architecture.

## Copy-Paste Task Template

```text
Task: <TASK_ID_AND_NAME>

Project:
Ai_assistant / FakturaBot / OfficeFlow.

Mode:
Implementation task. Start with a read-only audit.

Approved architecture design proof:
<PATH_TO_TASK_ARCHITECTURE_DESIGN_PROOF>
Verdict: ready_for_handoff

Goal:
<ONE_CLEAR_USER_OR_PRODUCT_OUTCOME>

Why this change exists:
<BUSINESS_NEED_AND_CURRENT_FAILURE_OR_GAP>

Architecture classification:
<NEW_TOP_LEVEL | EXISTING_ACTION_EXTENSION | SUBFLOW | STRUCTURED_SLOT |
 INTERNAL_STRATEGY | PRODUCT_TRUTH_INFOHELP_ONLY>

Canonical action / in-FSM contract:
- token: <TOKEN_OR_NOT_APPLICABLE>
- status after this task: <IMPLEMENTED | PARTIAL | RESERVED>
- runtime owner expected: <HANDLER_SERVICE_SYMBOL>
- allowed-action contexts: <CONTEXTS_OR_NOT_APPLICABLE>

Mandatory contracts to read before editing:
- AGENTS.md
- docs/Product_Doctrine_2030.md
- docs/AI_Layer_Implementation_Standards.md
- docs/Product_Truth_Layer.md
- docs/Info_Help_Guidance_Layer.md
- docs/Evaluation_and_Smoke_Test_Standards.md
- docs/Implementation_Agent_Checklist.md
- docs/Code_Agent_Handoff_Contract.md
- docs/FakturaBot_LLM_Orchestrator_Contract.md
- docs/Canonical_Decision_Resolver_Contract.md
- docs/llm/Canonical_Action_Registry.md
- docs/llm/In_Action_Response_Registry.md
- docs/llm/New_Action_Design_Checklist.md
- docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md
- docs/llm/Conversation_Acceptance_Proof_Contract.md
- <FOCUSED_DOMAIN_CONTRACTS>
- <APPROVED_ARCHITECTURE_DESIGN_PROOF>
- PROJECT_LOG.md recent relevant entries

Read-only audit required before code:
1. Verify every evidence reference and expected runtime owner from the approved
   architecture design proof.
2. Identify the safest shared insertion points for text, command, voice,
   callback, FSM, service, Product Truth, and InfoHelp paths.
3. Confirm whether the repository still supports the approved route and state
   graph.
4. Inspect existing tests for the full public journey and nearby-action
   regression surface.
5. Report one of:
   - design_matches_runtime;
   - minor_nonsemantic_variance;
   - material_design_variance.
6. For material_design_variance, do not invent a replacement architecture.
   Stop implementation and report exact contradictory files/symbols plus the
   minimum design decision needed.

Implementation scope:
<EXACT_BOUNDED_SCOPE_FROM_DESIGN_PROOF>

Required route behavior:
<PASTE_OR_SUMMARIZE_PUBLIC_ROUTE_AND_CONVERGENCE_MAP>

Required structured slots:
<PASTE_SLOT_SCHEMA_DEFAULTS_VALIDATION_AND_INVALID_BEHAVIOR>

Required FSM behavior:
<PASTE_STATE_GRAPH_ENTRY_CONTINUATION_SUCCESS_BACK_CANCEL_STALE_EXIT>

Required semantic boundaries:
<PASTE_MEANING_POSITIVE_EXAMPLES_NOT_THIS_AND_NEARBY_ACTIONS>

Required decision/callback behavior:
<PASTE_DECISION_FAMILY_CANONICAL_TOKENS_STATE_EXPIRY_FAIL_CLOSED_RULES>

Required side-effect ownership:
<PASTE_SIDE_EFFECT_OWNER_VALIDATION_IDEMPOTENCY_AND_FAIL_SAFE_RULES>

Authorization / tenant / precision boundaries:
<PASTE_REQUIRED_GATES_AND_TYPED_ONLY_FIELDS>

Product Truth / InfoHelp target:
<PASTE_STATUS_LIMITATIONS_FORBIDDEN_CLAIMS_AND_SAFE_NEXT_STEPS>

Negative-space behavior that must not regress:
<PASTE_ADJACENT_ACTIONS_AND_OLD_JOURNEYS>

Explicitly out of scope:
<PASTE_OUT_OF_SCOPE_AND_KNOWN_ARCHITECTURE_GAPS>

Implementation priorities:
1. Preserve existing ownership and shared routing layers.
2. Implement the approved public route and structured slot transfer.
3. Implement or update the FSM graph exactly as designed.
4. Make text, voice transcript, and buttons converge into shared state-aware
   Python helpers where semantically equivalent.
5. Keep Python as validator/executor and the bounded LLM as semantic
   canonicalizer/extractor within Python-provided bounds.
6. Fail safe on unknown, invalid, stale, unauthorized, or wrong-state input.
7. Update Product Truth, InfoHelp, registries, focused docs, changelog/project
   log as required by the design proof.
8. Add full public-entry journey tests and nearby-action regression tests, not
   only direct helper tests.
9. Produce the required post-implementation Conversation Acceptance Proof.

Mandatory tests/evals:
<PASTE_ACCEPTANCE_SCENARIOS_FROM_DESIGN_PROOF>

At minimum, prove where applicable:
- text public-entry happy path;
- voice public-entry path or explicit tested exclusion;
- command/button convergence;
- action plus slots in one request;
- clarification continuation after missing/invalid/ambiguous slot;
- active-FSM ownership;
- post-success final state and keyboard behavior;
- cancel/back behavior;
- nearby-action negative space;
- unknown with no side effect;
- stale/wrong-state callback with no side effect;
- authorization and tenant isolation;
- Product Truth / InfoHelp question with no action execution;
- unchanged old regression journey.

No-go constraints:
- Do not create another top-level action, token, state, module, parser, or
  fallback not authorized by the architecture design proof.
- Do not replace bounded semantic slot extraction with broad multilingual
  Python phrase dictionaries.
- Do not put business routing dictionaries or duplicate business execution in
  voice.py.
- Do not add local yes/no/approve/edit/cancel parsers.
- Do not let unknown or ambiguity default to a write action.
- Do not expose reserved/planned tokens as implemented runtime actions.
- Do not weaken active-FSM, authorization, tenant, precision, stale-state, or
  callback guards.
- Do not modify unrelated flows or perform broad dispatcher rewrites.
- Do not silently deviate from the approved architecture.
- Do not claim completion from unit/focused tests alone.
- Do not commit, push, deploy, migrate, or change server state unless the task
  explicitly authorizes it.

Post-implementation acceptance artifact:
Create:
<PATH, RECOMMENDED docs/evals/<TASK_ID>_conversation_acceptance_proof.md>

It must follow:
docs/llm/Conversation_Acceptance_Proof_Contract.md

Required final verdict:
- safe_to_commit;
- needs_revision;
- blocked_by_design_gap;
- runtime_not_proven.

Expected final output:
- audit verdict and design variance status;
- docs/contracts read;
- files changed;
- design-to-code mapping;
- implementation summary;
- tests/evals and exact results;
- tests/evals not run and why;
- Product Truth / InfoHelp status;
- Conversation Acceptance Proof path and verdict;
- known limitations and remaining gaps;
- migration/rollback/server notes if relevant;
- git status;
- no merge/deploy claim unless actually performed and verified.
```

## Architect Completion Check Before Sending The Prompt

The prompt is not ready until all of these are true:

- [ ] The Architecture Design Proof exists and says `ready_for_handoff`.
- [ ] The prompt references that exact artifact.
- [ ] The task classification is explicit.
- [ ] The action token and status are explicit or marked not applicable.
- [ ] The slot contract is included.
- [ ] The route and convergence map is included.
- [ ] The FSM graph, continuation states, and exit behavior are included.
- [ ] Nearby-action negative space is included.
- [ ] Unknown/ambiguous behavior is fail-safe.
- [ ] Voice precision boundaries are included.
- [ ] Decision/callback/stale-state rules are included.
- [ ] Side effects and Python owners are included.
- [ ] Product Truth / InfoHelp target is included.
- [ ] Out-of-scope gaps are explicit.
- [ ] Acceptance scenarios are concrete and use exact inputs.
- [ ] The required Conversation Acceptance Proof path and verdict model are
      included.

If a field is unknown, the architect must finish the design or mark the task
blocked. Do not send a vague implementation prompt and delegate architecture
completion to the coding agent.
