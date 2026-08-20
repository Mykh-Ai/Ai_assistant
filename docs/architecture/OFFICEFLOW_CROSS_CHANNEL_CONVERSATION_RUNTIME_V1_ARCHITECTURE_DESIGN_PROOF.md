# OfficeFlow Cross-Channel Conversation Runtime V1 — Architecture Design Proof

Verdict: `ready_for_handoff`
Approval date: 2026-08-20
Task id: `OFFICEFLOW_CROSS_CHANNEL_CONVERSATION_RUNTIME_V1`
Governance: `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`

## 1. Product need
OfficeFlow must support text/voice interaction from Android without copying Telegram business logic into Kotlin or routing Android through Telegram handlers. Telegram and Android are clients of one OfficeFlow core. The target is channel parity through shared Python-owned semantic resolution, flow state, validation, confirmations and business services.

## 2. Classification
Primary class: `reserved/planned capability`. This is platform-neutral conversation infrastructure, not a new user-facing business intent.

## 3. Canonical action contract
No `android_*` business actions. Existing canonical actions remain authoritative, including invoice, Bločky, contact, work-time, analytics and InfoHelp actions. Product Truth may add Android to `supported_channels` only after each action's Android acceptance proves parity.

## 4. Semantic boundaries
Android text and Android voice transcript must converge on the same canonical action/slot resolution as other supported channels. `Hlas / Chat` is an interaction channel, not a Home domain. Informational InfoHelp questions must not execute business actions. Ambiguous/unknown input must not become a write default.

## 5. Structured slots
The shared resolver may extract only Python-provided bounded schemas/options. Python owns defaults, derivation and validation. Precision-sensitive fields remain text/file-only where current contracts require it. Voice never weakens exact-value or destructive-confirmation boundaries.

## 6. Public route/convergence map
Target conceptual API surface:
- `POST /v1/conversations`
- `GET /v1/conversations/{id}`
- `POST /v1/conversations/{id}/turns`
- `POST /v1/conversations/{id}/voice`
- `POST /v1/conversations/{id}/decisions`
- `DELETE /v1/conversations/{id}`

Exact route names may only change through approved architecture revision; implementation agent must not invent a generic `/v1/action`.

Convergence:
Android text -> auth/workspace guard -> shared Conversation Engine.
Android voice -> auth/workspace guard -> bounded temp audio -> STT -> same shared text turn path.
Telegram remains an adapter and must progressively delegate shared business routing rather than remain the permanent owner of conversation semantics.

## 7. FSM/state graph
Telegram conversation state and Android conversation state are independent instances; unfinished Android work must not become Telegram aiogram state automatically.

Shared server conversation shape:
`IDLE -> ACTION_ACTIVE`.
From ACTION_ACTIVE:
- missing value -> `WAITING_VALUE`
- ambiguity -> `WAITING_CLARIFICATION`
- preview -> `WAITING_CONFIRMATION`
- read-only immediate result -> `COMPLETE -> IDLE`

WAITING_CONFIRMATION:
- approve -> validated execution -> `COMPLETE -> IDLE`
- edit -> return to owning action state
- cancel -> cleanup -> `IDLE`

Android UI navigation must not silently erase a pending business conversation. A pending flow may be surfaced as continue/cancel.

## 8. Decision/callback contract
Android decision buttons must not send a bare semantic `yes` as authority. Server issues an opaque decision token bound to at least: principal, session/device, workspace, conversation id, expected state, state version, decision and expiry. Wrong-state, stale, expired, duplicate or foreign tokens fail closed before side effects. Destructive/exact confirmation exclusions remain intact; e.g. whole-database final exact confirmation cannot become voice-approved.

## 9. Side-effect ownership
STT/LLM/mobile UI never owns business effects. Shared Python flow owners call existing business services only after authorization, tenant/state/slot validation and required confirmation. DB/files/PDF/upload/work-time writes remain owned by existing Python services. Temporary voice files are bounded, authorized-before-create, and removed after use/failure.

## 10. Authorization/tenant/precision
Authorization must precede STT, LLM, temp-file creation and business lookups. Conversation is bound to principal + API session/device + workspace. Every object lookup/write is workspace-scoped. Cross-tenant state/token reuse fails closed. Exact identifiers, tax IDs, invoice numbers, sensitive values and destructive confirmations keep their existing precision boundaries.

## 11. User-facing response/exit contract
Conversation turns return structured server-owned state plus user-facing copy and allowed decisions/required input type. Android renders; it does not reinterpret business meaning. Terminal success/cancel returns the conversation to idle and removes obsolete decision controls. Retryable network errors must not fabricate completion.

## 12. Product Truth/InfoHelp
Target infrastructure capability may be represented as partial until one accepted Android conversation slice is live. Existing business capability channel truth is updated action-by-action. Forbidden claims include: `Android can already do everything Telegram can`, `voice can confirm any exact/destructive action`, `Android contains its own OfficeFlow business logic`, and `an unsupported Android action is executed secretly through Telegram`.

## 13. Negative space/regression
Do not duplicate Telegram `voice.py` routing in Android/Kotlin. Do not expose direct OpenAI calls from Android. Do not use Android direct DB access. Do not share unfinished conversation state cross-channel in V1. Do not weaken existing Telegram active-FSM ownership, precision rules, tenant boundaries or stale-decision safety during extraction to shared owners.

## 14. Acceptance scenarios
1. Authorized Android text starts one existing read-only/help action through shared engine.
2. Authorized Android voice is transcribed server-side and reaches the same owner as equivalent text.
3. Unauthorized voice causes no STT/temp/LLM/business effect.
4. Missing required slot enters explicit continuation state.
5. Ambiguous/invalid slot fails safe with no write.
6. Button/text/voice confirmation converge where voice is allowed.
7. Voice exclusion remains enforced for exact/destructive steps.
8. Stale/wrong-workspace/duplicate decision token causes zero effect.
9. Android pending flow survives local UI navigation without becoming Telegram FSM.
10. Cancel cleans pending state and performs no business write.
11. Product Truth/InfoHelp question does not execute the named action.
12. Existing Telegram journey through an extracted shared owner remains unchanged.
13. Cross-tenant conversation id/token access fails closed.
14. Server-side temp voice material is removed after success/failure.
15. Android `supported_channels` is added only for capabilities with proven parity.

## 15. Out of scope
Shared unfinished conversation continuation between Telegram and Android; public multi-device handoff; background voice; always-listening assistant; Android direct AI; automatic migration of all Telegram FSMs in one PR; Play Store release; broad new business capabilities.

## 16. Evidence and verdict
Evidence: `bot/handlers/voice.py` shows current Telegram-specific aiogram FSM routing; Product Truth model already contains `supported_channels`/`unsupported_channels`; canonical action registry defines current business actions; Stage A provides principal/session/workspace API authority; Android Stage B proves first-party HTTPS client/session foundation.

Verdict: `ready_for_handoff`.
Implementation must be sliced: C2 builds the shared conversation foundation and a safe first Android text/voice slice; later C3/C4 migrate specific business flows with their own parity acceptance.