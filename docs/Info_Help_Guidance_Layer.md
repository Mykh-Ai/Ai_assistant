# FakturaBot Info Help Guidance/Navigation Layer (Docs-First Spec)

**Status:** planned (docs-first)  
**Date:** 2026-04-19  
**Scope:** product/architecture contract for new `info_help` capability

---

## 1) Purpose of this document

This document defines the planned `info_help` guidance/navigation/recovery layer for FakturaBot.

`info_help` is **not** a duplicate of the existing action system and **not** a generic free-form chatbot mode.

Its purpose is to help users:
- understand what the bot can do,
- understand how to perform supported tasks,
- navigate to correct actions,
- recover when confused or stuck,
- return to a clean “new task” state,
- receive truthful implemented/planned/unsupported capability answers.

---

## 2) Contract precedence: `docs/llm` is governing law

All bot↔LLM interactions for `info_help` remain governed by the existing bounded Python→LLM contract documented in `docs/llm`.

Normative rules:
- All `info_help` interactions **MUST** follow the bounded Python→LLM contract defined in `docs/llm`.
- No `info_help` flow may bypass or weaken those constraints.
- Python remains source of truth for workflow state, allowed outputs, validation, and side effects.
- LLM does not own business logic, side effects, persistence, or final execution decisions.
- `info_help` does not introduce free-form reasoning/execution mode.
- Bounded prompts and bounded outputs remain mandatory.

---

## 3) Product role of `info_help`

`info_help` is a service layer with three product functions:
1. information,
2. navigation/handoff toward valid actions,
3. recovery/reset support.

It does not replace direct actions and does not redefine existing top-level routing.

Future direction (Phase 2/3): `info_help` may expand into a controlled runtime explainability layer where Python supplies bounded runtime/debug facts and LLM converts them into clear user-facing guidance.

---

## 4) Scope and non-goals

### In scope
- informational bot-usage questions,
- capability explanation,
- navigation toward existing actions,
- linked handoff into existing actions/subtargets,
- reset/start-over/new-task handling,
- planned-feature notices,
- structured logging of all info-layer usage.

### Out of scope
- open-ended assistant behavior,
- hidden mutation from informational requests,
- fake support/ticketing systems (unless explicitly implemented),
- arbitrary uncontrolled document retrieval.

---

## 5) Core routing contract

Routing order:

A. Run top-level action resolution first.  
B. Enter `info_help` only if top-level resolution returns `unknown`.  
C. If `info_help` also cannot resolve safely, use bounded fallback response.

Question form does **not** block direct action routing.

Examples:
- “How do I create a new invoice?” may resolve directly to `create_invoice`.
- “How do I add a new contact?” may resolve directly to `add_contact`.

If the request matches an existing top-level action, bot should use action path directly.

---

## 6) Practical classification rules

Operational classes:
- direct action request,
- informational/guidance request,
- recovery/reset request.

Execution rule remains:
- top-level action first,
- `info_help` only on top-level miss.

Recovery/reset requests can be handled as controlled `info_help` service behavior when top-level resolution misses.

---

## 7) Internal structure of `info_help`

Internal service submodes (not new top-level actions by default):
- `faq_topic`
- `state_guidance`
- `action_offer_or_handoff`
- `restart_or_reset_request`
- `support_escalation`

These are internal `info_help` categories used for bounded policy decisions.

---

## 8) Action layer vs guidance layer

Rules:
- direct actions remain direct,
- `info_help` may explain action usage,
- `info_help` may offer navigation into action,
- `info_help` must not duplicate existing actions.

Example (`change_email`):
- user: “How do I change my email?”
- top-level action match: `unknown`
- `info_help` topic resolves to supplier profile update guidance
- linked action: `edit_supplier` (planned canonical naming for supplier update path)
- linked target: `email`
- bot explains flow first
- bot offers to proceed
- action starts only after explicit user confirmation.

Note: this example defines target behavior for `info_help`; it does not claim a new standalone `change_email` top-level action.

---

## 9) Capability status model

Each guidance topic/capability carries status:
- `implemented`
- `planned`
- `unsupported`

Response rules:
- `implemented` → explain current usage, optionally offer linked action.
- `planned` → truthfully state planned/not yet available.
- `unsupported` → bounded fallback, no fake promise.

Examples:
- delete old invoice history entry → planned/unsupported until runtime feature exists.
- send invoice by email → planned/unsupported until runtime implementation is confirmed.

---

## 10) Controlled knowledge source

`info_help` must run on a bounded help/capability registry, not arbitrary free-form doc search.

Recommended registry shape:
- `topic_id`
- `title`
- `status`
- `guidance_text`
- `linked_action` (optional)
- `linked_target` (optional)
- `planned_note` (optional)
- `support_note` (optional)
- `safe_reset_available` (optional)

---

## 11) LLM interaction model (planned)

### Stage A: top-level resolution
- Python sends bounded top-level action request.
- LLM returns one allowed action or `unknown`.

### Stage B: `info_help` topic resolution (only if Stage A = `unknown`)
- Python sends bounded help topic registry/context.
- LLM returns one topic id or `unknown`.

### Stage C: Python response policy
Python decides final response mode:
- `inform_only`
- `offer_linked_action`
- `offer_reset`
- `planned_feature_notice`
- `unsupported_fallback`

Python remains final execution authority for all behavior.

### 11.1) Controlled runtime introspection context (Phase 2/3 planned)

For runtime-problem explanations, Python may provide a bounded/sanitized runtime context to `info_help`, and LLM may translate it into plain user language.

Examples of allowed Python-provided facts:
- current FSM state,
- current flow identifier,
- allowed next actions,
- reset availability,
- recent STT failure count,
- last known error category,
- recent fallback reason,
- whether manual text input remains available,
- whether external model/API call failed,
- whether capability is currently blocked by quota/credits/API availability,
- short sanitized debug summary prepared by Python.

This remains a bounded contract interaction: LLM explains only provided structured facts and does not become a free investigator.

---

## 12) Safety and behavior rules

Mandatory behavior:
- informational request is not authorization for mutation,
- linked action launch requires explicit user confirmation,
- destructive reset requires explicit confirmation where applicable,
- responses must come from controlled knowledge entries,
- no hallucinated instructions,
- no bypass around business validation/invariants,
- no arbitrary source-code reading by LLM as a primary information path,
- no arbitrary raw-log reading by LLM as a primary information path,
- no exposure of secrets, tokens, stack traces, internal filesystem paths, or hidden internals in user-facing explanations,
- only sanitized, bounded Python-prepared summaries may be used for runtime/debug explainability.

---

## 13) Reset / new-task behavior

Product goal: help confused users return to clean starting point safely.

Planned behavior:
1. detect reset/start-over intent in `info_help`,
2. require confirmation if transition is destructive,
3. clear current flow/session state as appropriate,
4. return to idle/waiting-for-new-task state,
5. explicitly inform user that previous scenario was reset.

Current limitation to keep explicit:
- no claim of universal “step back” support across all flows unless implemented.

---

## 14) Logging and analytics (mandatory)

Every `info_help` entry must be logged as a structured product signal.

Minimum fields:
- timestamp,
- user/chat/session id,
- current FSM state,
- raw user input,
- resolved topic,
- capability status,
- linked action / linked target,
- response mode,
- accepted handoff (yes/no),
- accepted reset (yes/no).

Rationale:
- repeated questions indicate missing features/docs,
- repeated confusion indicates UX pain points,
- repeated planned-feature requests inform roadmap priority,
- repeated runtime failure signals (STT failures, unresolved intents, API/LLM error categories, repeated reset-after-failure) can guide reliability improvements,
- admin notifications/summaries may be future enhancement, but structured logging is required in first implementation phase.

---

## 15) Worked examples

### Example A: direct action despite question form
Input: “How do I create a new invoice?”  
Expected: top-level resolver maps to `create_invoice`, action path starts directly.

### Example B: info→action navigation
Input: “How do I change my email?”  
Expected: top-level miss → `info_help` topic → supplier email guidance → offer linked action (`edit_supplier`, target `email`) → launch only after explicit confirmation.

### Example C: planned capability answer
Input: “How do I delete an old invoice?”  
Expected: truthful planned/not-yet-implemented response (no fake execution path).

### Example D: recovery/reset
Input: “I am confused, start over.”  
Expected: `info_help` reset intent → confirmation if destructive → clear relevant state → return to new-task state.

### Example E: repeated voice/STT failures (runtime explainability)
Input: user sends several voice commands, then asks “Why is this not working?”  
Expected: Python reports repeated STT failures in bounded debug context; `info_help` explains that voice recognition is currently unreliable and suggests safe fallback to text input for continuation.

### Example F: external model/API failure or quota/credits block
Input: “What happened? Why are you not responding?”  
Expected: Python reports a bounded error category (e.g., temporary model/API unavailability or quota/credits issue); `info_help` returns safe plain-language explanation and next safe action (retry later, continue with available path, or contact admin if applicable).

---

## 16) Confirmed vs unconfirmed flow truthfulness

Must not be overstated as implemented unless runtime confirms:
- dedicated end-to-end contact-details edit flow,
- historical old-invoice deletion as user-facing capability,
- send-email/send-invoice runtime capability,
- support/ticket escalation workflow.

This spec is docs-first and does not alter runtime truth.

---

## 17) Phase rollout proposal

### Phase 1
- top-level-first routing (existing pattern retained),
- basic `info_help` layer,
- bounded topic registry,
- capability statuses,
- structured logging.

### Phase 2
- state-aware guidance,
- explicit reset/new-task flow,
- linked action handoff with explicit confirmation,
- controlled runtime explainability using bounded Python-prepared debug context.

### Phase 3
- broader topic coverage,
- richer analytics/admin summaries,
- advanced guidance coverage for more flows,
- richer debug-aware user guidance and optional admin-facing reliability summaries.

---

## 18) Required documentation alignment after acceptance

After accepting this spec, follow-up alignment should be planned for:
- `docs/TZ_FakturaBot.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/llm/Bounded_Resolver_Prompt_Template.md`
- `docs/llm/In_Action_Response_Registry.md`
- `README.md` (small note only if appropriate)
- `PROJECT_LOG.md`

This document is subordinate to existing `docs/llm` contract law and does not rewrite it.
