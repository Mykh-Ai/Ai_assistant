# OfficeFlow Android Home Top-Level Navigation V2 — Architecture Design Proof

Verdict: `ready_for_handoff`
Approval date: 2026-08-20
Task id: `OFFICEFLOW_ANDROID_HOME_TOP_LEVEL_NAVIGATION_V2`
Governance: `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`

## 1. Product need
The current Android pilot opens invoices immediately after profile selection. The approved target is a scalable OfficeFlow Home. After session restore and profile selection, Home shows exactly: `Faktúry`, `Bločky`, `Kontakty`, `Pracovný čas`, `Analytika`, `InfoHelp`. `Hlas / Chat` is a universal interaction channel, not a business domain. Android Product Truth remains `partial` until channel parity is proven.

## 2. Classification
Primary class: `reserved/planned capability`. This is product-shell/navigation architecture, not a new canonical business action.

## 3. Canonical action contract
No new Android business tokens. Existing actions remain authoritative under their domains, e.g. invoice actions under Faktúry, receipt/accounting-document actions under Bločky, contact actions under Kontakty, work-time actions under Pracovný čas, analytics actions under Analytika. The canonical Android section label is exactly `Bločky`; do not rename it `Doklady` or `Bločky/Doklady`.

## 4. Semantic boundaries
Home/domain taps are local navigation only and must never execute a business write. `InfoHelp` is informational and must not execute an action. Unsupported Android sublevels show a truthful unavailable state with zero hidden side effect. Profile change selects local Android scope only and must not mutate Telegram `active_workspace_selection`.

## 5. Slots
C1 adds no LLM/business slots. Deterministic context is selected workspace, domain destination, and explicit sublevel tap. Workspace must be present in the latest `/v1/workspaces` result before reuse.

## 6. Route/convergence
C1 adds no API routes. Existing Stage A read routes remain. Navigation is local. Voice/text conversation belongs to `OFFICEFLOW_CROSS_CHANNEL_CONVERSATION_RUNTIME_V1`.

## 7. State graph
`APP_START -> SESSION_VALIDATION -> WORKSPACE_RESOLUTION -> HOME`.
From Home: Faktúry | Bločky | Kontakty | Pracovný čas | Analytika | InfoHelp.
Invoice read chain: `HOME -> Faktúry -> existing invoice list -> detail -> PDF`.
Back: `PDF -> detail -> list -> Faktúry -> Home`.
Profile change from any domain: `current screen -> workspace picker -> Home(new workspace)` and clears old workspace/domain object state.

## 8. Confirmations/callbacks
No new business confirmation or Telegram callback. Existing sign-out confirmation remains. Unsupported-operation taps require no confirmation and create zero effect.

## 9. Side effects
Allowed: local navigation, validated local workspace preference, existing read-only API calls. Forbidden in C1: new business mutations, Telegram FSM mutation, LLM/STT/LMM side effects.

## 10. Authorization/tenant/precision
Stage A session remains authority. Android workspace is local read scope only. Server validates every read. Cross-tenant fallback is forbidden. C1 changes no destructive or precision-sensitive rules.

## 11. UI/exit contract
Home shows active profile separately from compact app-bar controls. Layout must survive long company/contact text and increased Android font scale. Content must not be hidden by system bars, app bars, or bottom navigation. Unsupported operations return a bounded Android-unavailable message and no network business effect.

## 12. Product Truth/InfoHelp
Capability: `first_party_android_client`; status remains `partial`. Truth after C1: controlled Android pilot is active over approved HTTPS; enrollment/session/workspace/Home plus currently proven read-only invoice/contact paths are supported. Do not claim full Android parity or that Android replaces Telegram.

## 13. Negative space/regression
Do not alter Stage A route set, session semantics, Telegram handlers/FSM/voice, `active_workspace_selection`, canonical action semantics, work-time/Bločky/analytics business owners, or DB schema. `Bločky` is the approved Home label.

## 14. Acceptance scenarios
1. Stored valid session -> Home, not automatic invoice list.
2. Multiple workspaces -> picker -> Home.
3. Home shows exactly the six approved domains.
4. No `Doklady` or `Bločky/Doklady` Home label.
5. Faktúry -> list -> exact detail -> PDF -> correct back chain.
6. Current real-device invoice-detail failure is diagnosed/fixed; success renders, bounded errors give retry/back.
7. Kontakty read path remains functional.
8. Unsupported sublevel produces zero business effect.
9. Profile switch clears old domain/object state and returns Home.
10. Restart restores session/validated local profile then Home.
11. Large-font and long-text device checks show no overlap/unreachable controls.
12. Existing Telegram journeys remain unchanged.
13. Product Truth stays evidence-matched and partial.

## 15. Out of scope
Cross-channel conversation engine, Android STT/text assistant, new Android mutations, Bločky upload, work-time writes, analytics execution, InfoHelp conversation runtime, cross-device shared unfinished flows, Play Store release.

## 16. Evidence and verdict
Evidence: current Stage B proof; `android/.../ui/OfficeFlowApp.kt`; `OfficeFlowViewModel.kt`; canonical action registry; real Samsung pilot evidence from 2026-08-20; active Stage A HTTPS pilot.

Verdict: `ready_for_handoff`.
C1 implementation may use this proof only for the bounded Home/navigation/UI/detail-fix scope; cross-channel conversation must follow its separate proof.