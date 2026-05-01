# New Canonical Action Design Checklist

Purpose: practical checklist before introducing/upgrading a canonical top-level action.

## Checklist

1. **Action identity**
   - [ ] Define canonical action name.
   - [ ] Define status: implemented / reserved / partial.

2. **Existing manual flow audit**
   - [ ] Verify whether this action already exists as manual/command flow.
   - [ ] If yes, document current command entry and handler owner.

3. **Ambiguity decision**
   - [ ] Decide whether action is semantically ambiguous in multilingual/noisy input.
   - [ ] If ambiguous, decide whether optional `action_hints` are needed.

4. **Wording discipline**
   - [ ] Define canonical UI wording (product-facing phrasing).
   - [ ] Define noisy input examples separately (runtime/noise examples only).
   - [ ] Ensure noisy examples are not presented as canonical bot wording.

5. **Nearby-action separation**
   - [ ] Define which nearby actions must be separated via `not_this` guidance.
   - [ ] Validate separation against at least neighboring actions in same context.

6. **Entry modes and precision boundaries**
   - [ ] Mark entry modes: text / command / voice / mixed.
   - [ ] Explicitly mark if voice top-level invoke is supported now or later.
   - [ ] List slots/steps that remain text-only after top-level invoke.

7. **Bounded resolver contract**
   - [ ] Update allowed-actions list for relevant context.
   - [ ] If used, add compact `action_hints` (`meaning`, optional `positive_examples`, optional `not_this`).
   - [ ] Keep output schema strict: one canonical token or `unknown`.

8. **DecisionResolver gate**
   - [ ] Check whether the new action/subflow asks the user to confirm, reject, approve, edit, cancel, save, delete, route, or choose a bounded next step.
   - [ ] If yes, reuse an existing `bot/services/decision_resolver.py` family or define a new bounded family there.
   - [ ] Do not add handler-local confirmation parsing (`text.lower()`, `in {"ano", "nie"}`, regex synonyms, etc.).
   - [ ] Do not add flow-specific yes/no or approve/cancel word lists in lower resolver layers when the behavior belongs to an existing family.
   - [ ] Handler code must receive and branch only on canonical family outputs (`yes` / `no` / `unknown`, `approve` / `edit` / `cancel` / `unknown`, or a documented new family).
   - [ ] Add tests that verify the handler calls the shared resolver and does not contain a local confirmation parser.
   - [ ] Add noisy/multilingual/STT-like tests at the resolver-family level, not by duplicating word lists in the flow.

9. **Ownership and docs sync**
   - [ ] Identify Python owner: handler/FSM/service entry points.
   - [ ] Update `docs/llm/Canonical_Action_Registry.md`.
   - [ ] Update `docs/llm/In_Action_Response_Registry.md` for any in-action response or decision family.
   - [ ] Update `docs/Canonical_Decision_Resolver_Contract.md` if a new decision family or resolver rule is introduced.
   - [ ] Update `docs/FakturaBot_LLM_Orchestrator_Contract.md` if contract scope changed.
   - [ ] Update `docs/TZ_FakturaBot.md` for product-level requirements (if affected).
   - [ ] Add session note to `PROJECT_LOG.md`.

10. **Tests for runtime task (next step)**
   - [ ] Top-level resolver routing coverage.
   - [ ] State/entry-mode routing coverage (text/command/voice where applicable).
   - [ ] Fail-loud behavior checks for unsupported states/ambiguous input.
   - [ ] Confirmation/route decision tests prove canonical outputs drive behavior; no business branch should depend on raw user words.

## Note: behavior changes that are not new top-level actions

- [ ] Confirm whether requested behavior is a top-level action or an in-action/subflow contract update.
- [ ] For invoice item edits, explicitly separate service identity replacement from free-text detail editing (`item_description_raw`).
- [ ] Capture item-targeting rules (current single-item default vs future multi-item explicit selection/clarification) before runtime implementation.
- [ ] Mark precision-sensitive fields as text-first where voice guessing is unsafe.
