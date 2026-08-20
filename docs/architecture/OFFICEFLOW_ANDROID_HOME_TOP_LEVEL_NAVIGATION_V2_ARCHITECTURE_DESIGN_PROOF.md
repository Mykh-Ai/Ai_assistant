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

Approved domain/sublevel map:

- `Faktúry`
  - `Vytvoriť faktúru` -> existing canonical `create_invoice` (not executable in C1)
  - `Existujúce faktúry` -> existing Stage A read list/detail/PDF path (executable in C1)
  - `Upraviť faktúru` -> existing canonical `edit_existing_invoice` (not executable in C1)
  - `Označiť ako uhradenú` -> existing canonical `mark_existing_invoice_paid` (not executable in C1)
  - `Vymazať faktúru` -> existing canonical `delete_existing_invoice` (not executable in C1)
- `Bločky`
  - `Pridať bloček` -> existing canonical `add_receipt` (not executable in C1)
  - `Existujúce bločky` -> existing canonical recent-accounting-document read capability (not executable in C1 because Stage A has no Bločky read route)
- `Kontakty`
  - `Existujúce kontakty` -> existing Stage A read contacts path (executable in C1)
  - `Pridať kontakt` -> existing canonical `add_contact` (not executable in C1)
- `Pracovný čas`
  - `Začať pracovný deň` -> existing canonical `open_work_day` (not executable in C1)
  - `Ukončiť pracovný deň` -> existing canonical `close_work_day` (not executable in C1)
  - `Pridať čas` -> existing canonical `add_work_time_entry` (not executable in C1)
  - `Mesačný report` -> existing canonical `generate_work_time_report` (not executable in C1)
  - `Nastavenie prestávky` -> existing canonical `update_work_time_lunch_break` (not executable in C1)
  - `Vymazať mesiac` -> existing canonical `delete_work_time_month` (not executable in C1)
- `Analytika`
  - `Faktúry` -> existing canonical `invoice_analytics` (not executable in C1)
  - `Bločky` -> existing canonical `accounting_document_analytics` (not executable in C1)
- `InfoHelp`
  - informational/help entry only; conversation execution belongs to C2 and later

`Hlas / Chat` is a universal OfficeFlow interaction affordance and not another top-level domain. In C1 it may be shown only as an explicitly unavailable/coming-later control with zero microphone permission request, zero STT/LLM call and zero business effect. Functional text/voice interaction belongs exclusively to `OFFICEFLOW_CROSS_CHANNEL_CONVERSATION_RUNTIME_V1`.

## 4. Semantic boundaries
Home/domain taps are local navigation only and must never execute a business write. `InfoHelp` is informational and must not execute an action. Unsupported Android sublevels show a truthful unavailable state with zero hidden side effect. Profile change selects local Android scope only and must not mutate Telegram `active_workspace_selection`.

A disabled/unavailable sublevel must not call Telegram handlers, Stage A business-read routes unrelated to that sublevel, STT, LLM, or any mutation. It may only show bounded local copy explaining that the function is not yet available in Android.

## 5. Slots
C1 adds no LLM/business slots. Deterministic context is selected workspace, domain destination, and explicit sublevel tap. Workspace must be present in the latest `/v1/workspaces` result before reuse.

## 6. Route/convergence
C1 adds no API routes. Existing Stage A read routes remain. Navigation is local. Voice/text conversation belongs to `OFFICEFLOW_CROSS_CHANNEL_CONVERSATION_RUNTIME_V1`.

Allowed C1 network use remains limited to the already-approved Stage A routes needed for session/workspace, invoice list/detail/PDF and contacts.

## 7. State graph
`APP_START -> SESSION_VALIDATION -> WORKSPACE_RESOLUTION -> HOME`.

From Home:
`HOME -> Faktúry | Bločky | Kontakty | Pracovný čas | Analytika | InfoHelp`.

Invoice read chain:
`HOME -> Faktúry -> Existujúce faktúry -> list -> detail -> PDF`.

Contacts read chain:
`HOME -> Kontakty -> Existujúce kontakty -> list`.

Unsupported C1 sublevel:
`domain -> unavailable state -> back to domain` with zero business/network side effect beyond any already-completed navigation state.

Back:
`PDF -> detail -> list -> Faktúry -> Home`.

Profile change from any domain:
`current screen -> workspace picker -> Home(new workspace)` and clears old workspace/domain object state.

App restart with a valid stored session and still-valid remembered workspace:
`APP_START -> SESSION_VALIDATION -> WORKSPACE_RESOLUTION -> HOME`; never auto-open an old domain/detail route.

## 8. Confirmations/callbacks
No new business confirmation or Telegram callback. Existing sign-out confirmation remains. Unsupported-operation taps require no confirmation and create zero effect.

## 9. Side effects
Allowed: local navigation, validated local workspace preference, existing read-only API calls. Forbidden in C1: new business mutations, Telegram FSM mutation, LLM/STT/LMM side effects, microphone recording, file/document upload, work-time changes, analytics execution, InfoHelp runtime execution.

## 10. Authorization/tenant/precision
Stage A session remains authority. Android workspace is local read scope only. Server validates every read. Cross-tenant fallback is forbidden. C1 changes no destructive or precision-sensitive rules.

## 11. UI/exit contract
Home shows active profile separately from compact app-bar controls. Layout must survive long company/contact text and increased Android font scale. Content must not be hidden by system bars, app bars, bottom navigation, gesture/navigation insets, or fixed-size controls.

C1 must remove the current flat `Faktúry | Kontakty` bottom navigation as the primary product architecture. Product navigation is Home -> domain -> sublevel. A compact persistent Home/back affordance may be used if it does not duplicate domain logic or obscure system navigation.

Unsupported operations return a bounded Android-unavailable message and no network business effect.

## 12. Product Truth/InfoHelp
Capability: `first_party_android_client`; status remains `partial`.

Truth after C1: controlled Android pilot is active over approved HTTPS; enrollment/session/workspace/Home plus currently proven read-only invoice/contact paths are supported. Home may display other OfficeFlow domains/sublevels as product structure, but those sublevels must be explicitly unavailable until separately implemented and accepted.

Do not claim full Android parity, functional Android voice/chat, Android Bločky upload, Android work-time operations, Android analytics, Android InfoHelp conversation runtime, or that Android replaces Telegram.

## 13. Negative space/regression
Do not alter Stage A route set, session semantics, Telegram handlers/FSM/voice, `active_workspace_selection`, canonical action semantics, work-time/Bločky/analytics business owners, DB schema, Cloudflare pilot endpoint, enrollment/session storage model or server deployment.

`Bločky` is the approved Home/domain label. Do not introduce `Doklady` or `Bločky/Doklady` as the Android domain label.

Do not make unavailable buttons deep-link into Telegram or call hidden mutations in C1.

## 14. Acceptance scenarios
1. Stored valid session -> Home, not automatic invoice list.
2. Multiple workspaces -> picker -> Home.
3. Home shows exactly six business domains: Faktúry, Bločky, Kontakty, Pracovný čas, Analytika, InfoHelp.
4. `Hlas / Chat` is visually separate from business domains and in C1 cannot start recording/STT/LLM/business action.
5. No `Doklady` or `Bločky/Doklady` Home/domain label.
6. Faktúry shows exactly the approved invoice sublevels and only `Existujúce faktúry` is executable in C1.
7. Faktúry -> Existujúce faktúry -> list -> exact detail -> PDF -> correct back chain.
8. Current real-device invoice-detail failure is diagnosed to a concrete root cause and fixed; successful detail renders; bounded errors expose retry/back without losing workspace/session.
9. Kontakty shows exactly `Existujúce kontakty` and `Pridať kontakt`; only the existing-contact read path is executable in C1.
10. Bločky shows the approved two sublevels and both are unavailable in C1 with zero business/network effect.
11. Pracovný čas shows all six approved sublevels and all are unavailable in C1 with zero business/network effect.
12. Analytika shows `Faktúry` and `Bločky`; both are unavailable in C1 with zero analytics/business effect.
13. InfoHelp entry is present but conversation execution is unavailable in C1 with zero business effect.
14. Profile switch clears old domain/list/detail/PDF/contact state and returns Home for the new workspace.
15. Restart restores session, revalidates remembered workspace, then returns Home.
16. Large-font and long-text device checks show no overlap, clipping, unreachable controls, content-under-system-bars, or bottom-nav obstruction.
17. Long workspace/contact/customer names wrap/truncate intentionally without covering actions.
18. Existing contact read path remains functional.
19. Existing sign-out confirmation semantics remain unchanged.
20. Existing Telegram journeys remain unchanged.
21. Product Truth stays evidence-matched and `partial`.
22. No new Stage A routes, DB/schema changes, server deploy, Cloudflare changes, enrollment issuance, STT/LLM calls or Android business mutations occur in C1.

## 15. Out of scope
Cross-channel conversation engine, functional Android STT/text assistant, new Android mutations, Bločky upload/read API, work-time writes/read API, analytics execution, InfoHelp conversation runtime, cross-device shared unfinished flows, Play Store release, release signing, server/API deployment changes.

## 16. Evidence and verdict
Evidence: current Stage B proof; `android/.../ui/OfficeFlowApp.kt`; `OfficeFlowViewModel.kt`; `OfficeFlowApiClient.kt`; Stage A `officeflow_read_service.py`; canonical action registry; Product Truth registry; real Samsung pilot evidence from 2026-08-20; active Stage A HTTPS pilot; `OFFICEFLOW_CROSS_CHANNEL_CONVERSATION_RUNTIME_V1_ARCHITECTURE_DESIGN_PROOF.md` for deferred text/voice runtime.

Verdict: `ready_for_handoff`.

C1 implementation may use this proof only for the bounded Home/domain/sublevel navigation, responsive UI and invoice-detail defect scope. Cross-channel conversation must follow its separate proof.