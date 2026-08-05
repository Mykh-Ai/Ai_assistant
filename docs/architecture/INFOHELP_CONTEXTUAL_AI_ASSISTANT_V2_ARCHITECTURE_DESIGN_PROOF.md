# InfoHelp Contextual AI Assistant V2 Architecture Design Proof

Current routing amendment (2026-08-05) supersedes the earlier V2 gate and the
2026-08-04 supported-only amendment: authorized idle natural language runs the
top-level LLM bundle before local fallback; its bounded `routing_kind`
distinguishes business execution from capability/how-to and contextual help.
Every validated non-`unknown` action, including a Product Truth `partial`
action, routes directly to its Python owner. Contextual InfoHelp is recovery
only and model confidence has no routing authority.

## 1. Task Identity And Product Need

- Task: `INFOHELP_CONTEXTUAL_AI_ASSISTANT_V2`.
- Initial audited base: `origin/main` at `3cd85de54015a8bf5b8de01bcd24a5544db7af79` on 2026-08-02; final delivery base was refreshed to `4ab8f5bde30104b817d2cdfeca15d7f89044828b` after `main` advanced during implementation. V2 was transplanted as one clean commit without force-push or unrelated branch work.
- Need: prevent object-confused recovery (for example receipt deletion becoming invoice or account deletion), replace broad unknown guidance with context-aware assistance, and make missing invoice references continue in an owned FSM.
- Current status: existing InfoHelp is `partial`; contextual V2 is `planned` before this change.
- Target status: `partial` Level 2 contextual assistant behind a disabled-by-default rollout gate, pending interactive Telegram acceptance.
- Risk: high because the gate precedes mutating/destructive routes.

## 2. Architecture Classification

Primary class: extension and material replacement of the existing Product Truth / InfoHelp contract. It also extends structured intent slots, active-FSM informational controls, and continuation for existing invoice-reference actions. It is not a new public business action: no `contextual_recovery`, `infohelp_recovery`, or AI-assistant canonical action is introduced.

Approved route:

```text
authorized input
-> exact command / active-FSM ownership
-> existing top-level resolver
-> conditional single contextual InfoHelp assistant call
-> Python Product Truth + exact semantic validation
-> answer / clarification / existing owner / continuation / request preview
-> existing confirmation and side-effect guards
```

## 3. Canonical Action Contract

V2 adds no canonical public action. It uses a Python-owned semantic view of existing actions. The initially executable/continuable subset is `show_existing_invoice`, `edit_existing_invoice`, `delete_existing_invoice`, `mark_existing_invoice_paid`, `edit_supplier`, `add_contact`, `add_receipt`, and existing read-only/profile owners proven by the canonical registry and runtime. `delete_user_database` is explicitly not InfoHelp-offer eligible.

## 4. Semantic Boundary Matrix

| Exact meaning | Expected result | Must not become |
|---|---|---|
| delete receipt | unsupported exact feature / request preview | delete invoice; delete account |
| delete invoice | existing invoice delete owner, reference continuation, then confirmation | receipt delete; immediate deletion |
| edit contact | unsupported exact feature | edit supplier profile; edit invoice |
| edit own supplier profile | existing supplier-profile edit owner | edit contact |
| capability question about a mutation | Product Truth answer only | action execution or state entry |
| vague `delete` | narrow clarification | any destructive action |

Verb similarity never bridges different `domain_id + object_kind + operation_id` triples. Explicit correction and negation override prior interpretations.

## 5. Structured Slot Contract

The bounded assistant returns: intent kind, speech act, domain, object, operation, optional target reference, proposed registered action/capability/command, completeness and missing slots, correction/negation fields, active/reply references, confidence, and short non-factual Slovak acknowledgement/clarification text. Python bounds every enum, identifier, list, free-text length, and confidence. `invoice_reference` is precision-sensitive: voice may start or continue lookup only where the existing flow already permits it; destructive confirmation remains separately owned.

## 6. Public Route And Convergence Map

| Entry | Guard | Resolver | Owner/result |
|---|---|---|---|
| known command | authorization, router order | deterministic command router | unchanged owner |
| unknown command | authorization, final command route | single V2 assistant | suggestion/clarification only |
| idle text | authorization, no active FSM | top-level resolver then conditional V2 | Python-validated existing owner or answer |
| idle voice | authorization before STT | shared text route after one transcript capture | same owner as text |
| active text/voice | active FSM first | bounded active-FSM control resolver; contextual V2 only for help token | FSM unchanged or pass-through |
| existing decision button | callback authorization/state/age | existing callback adapter | existing confirmation owner |

## 7. FSM Graph And State Ownership

```text
IDLE
-> exact supported invoice-reference action
   -> reference present -> shared action lookup/preview owner
   -> reference missing -> InvoiceReferenceContinuationStates.waiting_reference
      -> one match -> shared action lookup/preview owner
      -> no match / ambiguity -> remain and ask narrowly
      -> /cancel or /menu -> existing state-control owner
      -> stale -> clear safely
```

Continuation data is an allowlisted action, workspace binding, source channel, start time, and optional bounded original text. Active-flow help never changes the state. Ordinary values pass through to the state handler.

## 8. Decision, Confirmation, And Callback Contract

Invoice delete and mark-paid keep the existing `yes_no` DecisionResolver and `decision:*` buttons. Customization requests keep the existing `approve_edit_cancel` preview. The callback actor is `callback.from_user`; the adapter chat and send methods come from `callback.message`. Existing stale/expired handling fails closed and clears only owned markup. V2 creates no arbitrary-action callback dispatcher and accepts no model-returned callback data.

## 9. Side-Effect And Ownership Map

| Effect | Owner | Gate |
|---|---|---|
| contextual LLM call | existing `info_help_resolver.py` | authorized user and rollout gate |
| ephemeral turns | process-memory context service | same user/chat/workspace, bounded TTL |
| FSM continuation metadata | invoice handler/FSM | exact eligible action and workspace |
| invoice view/edit/delete/paid | existing invoice owners | scoped lookup; existing confirmation where required |
| customization request row | existing request service | preview plus explicit approval |

The LLM owns no DB, file, callback, FSM, tenant, confirmation, or business effect.

## 10. Authorization, Tenant, And Precision Boundaries

Authorization precedes STT and contextual capture/calls. Context key is Telegram user + chat + workspace. Invoice lookup uses the existing supplier/workspace-scoped runtime and revalidates the stored workspace binding. No raw DB rows, paths, secrets, tokens, logs, files, binary data, or hidden prompts enter context. Exact destructive confirmation remains typed/button bounded by existing contracts.

## 11. User-Facing Response And Exit Contract

- Supported information: Python-grounded Product Truth; idle state.
- Supported action with complete slots: existing owner and its normal final state.
- Missing invoice reference: narrow prompt and continuation state.
- Unsupported exact intent: acknowledge exact object/operation, state unsupported, offer existing request preview; no unrelated buttons.
- Active help: factual state/expected-input description plus main-menu control; FSM unchanged.
- Invalid model result or genuinely unclear input: short narrow fallback, no catalogue/buttons/effect.
- Overview: broad Product Truth overview only when explicitly requested.

## 12. Product Truth And InfoHelp Contract

The compact assistant view is derived from the existing Product Truth registry and contains only safe status, limitations, owners, actions, commands, next steps, setup flags, danger, and channel metadata. Python repeats the final registry lookup after model validation. Exact unsupported object-operation requests never inherit another object's supported capability.

## 13. Negative-Space And Regression Contract

Preserve known commands, authorization, active-FSM ownership, voice precision exclusions, existing invoice/contact/profile/document/work-time behavior, DecisionResolver confirmation, tenant isolation, and PR #63/#65 rollback history. Do not restore PR #63 recovery handlers/services, generic action labels, generic callbacks, nearest-action selection, account-deletion suggestions, RAG/vector storage, persistent transcripts, log-derived context, self-learning, DB migration, deployment, or production access.

## 14. Acceptance Scenario Contract

The implementation must prove the 20 prompt journeys: receipt-delete capability and execution requests; correction/negation; invoice delete continuation/direct convergence; contact/profile distinction; incomplete contact intent; Latin/Cyrillic unknown commands; explicit reply; active-flow and expected-input questions; ordinary continuation value; vague destructive input; real Telegram callback actor; stale/forged callback; explicit overview; genuinely unclear input; and exactly one enhanced InfoHelp call. Each no-effect journey asserts no mutation, no unrelated state, and no destructive suggestion.

## 15. Out Of Scope And Known Architecture Gaps

No merge/deploy/production access, migration, persistent history, broad learning, RAG, embeddings, nested/suspended FSM, new receipt-delete/contact-edit action, account-specific adaptive workflows, or production acceptance. Process-memory context is intentionally lost on restart. Live admin-pilot Telegram acceptance remains required after review.

## 16. Evidence Index And Handoff Verdict

- Design contract: `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`.
- Current route: `bot/handlers/invoice.py::process_invoice_text`.
- Existing triage: `bot/services/info_help.py::resolve_info_help_triage_result_with_llm` and `bot/services/info_help_resolver.py::resolve_info_help_triage_with_llm`.
- Current broad fallback: `bot/services/info_help.py::build_top_level_unknown_guidance`.
- Product Truth: `bot/services/product_truth.py`.
- Active-state owner: `bot/services/active_fsm_guard.py` and `bot/services/decision_resolver.py::resolve_active_fsm_navigation`.
- Callback actor adapter: `bot/handlers/decision_callbacks.py::_CallbackMessageAdapter`.
- Rollback evidence: `PROJECT_LOG.md` and `CHANGELOG.md` entries dated 2026-08-02.
- Regression-first evidence will be appended after the initial failing run; final conversation evidence lives in the task-specific eval proof.

Handoff verdict: `ready_for_handoff`.

Implementation status: `implemented_pending_interactive_acceptance`.

Regression-first evidence: before production code, `python -m pytest -q
tests/test_info_help_contextual_v2.py tests/test_invoice_reference_continuation_v2.py`
failed during collection with two expected missing-contract imports:
`INFO_HELP_INTENT_GENUINELY_UNCLEAR` and `InvoiceReferenceContinuationStates`.

## 17. 2026-08-05 Runtime Repair Amendment

The production-observed outgoing-invoice analytics question proved two
architecture defects: Python's local analytics match returned before the
top-level LLM call, while punctuation then forced the already-resolved partial
action into InfoHelp. A malformed but semantically useful InfoHelp enum was
subsequently presented as user ambiguity.

The repaired convergence is:

```text
authorized voice -> STT -> top-level LLM bundle -> Python validation
                                          | validated business action
                                          v
                                  deterministic Python owner

top-level bundle help/unknown -> one Contextual InfoHelp call ->
Product Truth answer / command hint / clarification / bounded recovery
```

Active FSM remains a separate first owner: its navigation resolver decides
whether the input is normal step data or help/confusion; only the latter runs
the context-rich InfoHelp call, whose validated command hint or active-step
classification now contributes to the deterministic response instead of being
discarded. No DB, storage, access, callback, confirmation, or side-effect
authority moved to either model.
