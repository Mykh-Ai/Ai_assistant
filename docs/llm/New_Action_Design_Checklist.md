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

8. **Ownership and docs sync**
   - [ ] Identify Python owner: handler/FSM/service entry points.
   - [ ] Update `docs/llm/Canonical_Action_Registry.md`.
   - [ ] Update `docs/FakturaBot_LLM_Orchestrator_Contract.md` if contract scope changed.
   - [ ] Update `docs/TZ_FakturaBot.md` for product-level requirements (if affected).
   - [ ] Add session note to `PROJECT_LOG.md`.

9. **Tests for runtime task (next step)**
   - [ ] Top-level resolver routing coverage.
   - [ ] State/entry-mode routing coverage (text/command/voice where applicable).
   - [ ] Fail-loud behavior checks for unsupported states/ambiguous input.
