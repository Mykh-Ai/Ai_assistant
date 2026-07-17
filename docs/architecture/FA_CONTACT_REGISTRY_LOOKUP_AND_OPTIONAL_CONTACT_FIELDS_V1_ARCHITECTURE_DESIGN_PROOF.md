# FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1 Architecture Design Proof

## 1. Task identity and product need

- Task: `FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1`
- Date / architect: 2026-07-17 / Codex implementation agent acting under the user-approved task package
- Business need: reduce transcription errors while creating Slovak company contacts without removing the existing manual and document-assisted paths.
- User-visible outcome: an authorized user in an active workspace may enter a company name or eight-digit IČO, choose an official RPO result, review official values, type any required or optional local values, and save only after explicit confirmation.
- Current Product Truth: contact creation is supported manually and from text/PDF; official company-registry lookup and contact IBAN are not implemented.
- Target Product Truth: registry-assisted contact creation is supported only when the disabled-by-default feature is enabled for the active workspace; manual/document fallback remains supported.
- Risk: high for persisted-data and tenant/callback integrity; medium for read-only external availability.
- AI maturity: no new AI authority. Registry lookup is deterministic Python. Existing document extraction remains a draft-only bounded extraction path; Product Truth/InfoHelp remains the capability-aware explanation owner.

## 2. Architecture classification

Primary class: **extension of an existing top-level action**.

The canonical action remains `add_contact`. Registry lookup is an internal deterministic strategy and selection subflow of the existing contact FSM. It is not a new top-level business intent, not an LLM slot resolver, not a second contact router, and not a standalone Product Truth capability. `/add_kontakt` is only a command alias converging on the current handler.

## 3. Canonical action contract

- Token: `add_contact`
- Status before/after: implemented; extended with an optional feature-gated registry strategy
- Meaning: create or update a workspace-scoped customer/contact after a visible preview and confirmation
- Runtime owner: `bot/handlers/contacts.py::start_add_contact_intake` and `ContactStates`
- Storage owners: legacy `ContactService`, workspace `WorkspaceContactService`, and a dedicated registry transaction owner
- Entry modes: `/contact`, `/contact_add`, `/add_kontakt`, semantic text, voice start, and the existing document-assisted entry
- Precision boundary: voice may start `add_contact`; company query, IČO, DIČ, IČ DPH, email, and IBAN are text/file-only

## 4. Semantic boundary matrix

| Exact meaning/input | Expected action/status | Why | Must not become |
|---|---|---|---|
| "Pridaj kontakt" | `add_contact` | Existing business intent | `search_company` |
| "Nájdi firmu podľa IČO a ulož ju ako kontakt" | `add_contact` then registry strategy | Search is subordinate to contact creation | automatic save |
| "Vieš vyhľadať firmu v registri?" | InfoHelp/Product Truth | Informational question | starting an FSM or external call |
| invoice customer lookup | existing invoice contact lookup | Reads saved contacts for an invoice | registry search |
| idle contract/PDF attachment for a contact | existing attachment/contact intake | Existing file-assisted draft | registry overwrite |
| unknown or ambiguous top-level text | `unknown`/clarification | No write default | contact creation |

Positive examples for `add_contact` remain the canonical resolver examples. `not_this`: view/edit supplier profile, create invoice, invoice-customer lookup, accounting-document intake, capability questions, or unsupported internet discovery.

## 5. Structured slot contract

| Slot | Source/type | Required | Validation/default | Invalid behavior | Voice boundary |
|---|---|---:|---|---|---|
| registry query | typed company name or 8-digit IČO | yes for registry path | trim; deterministic search normalization only | retry/manual/document fallback | text-only |
| RPO subject id | bounded callback index into FSM candidate list | yes after selection | nonce, index, age, actor, state, workspace/profile | stale message, no effect | button only |
| official name/IČO/address/status | official RPO JSON | yes except status | deterministic current-value mapping; unknown stays `None` | manual fallback if unusable | not user supplied |
| DIČ | official provider if later configured, otherwise typed text | yes | existing `validate_dic` | remain in clarification state | text-only |
| IČ DPH | official confirmed source or typed value | no | existing validation; default empty | reject invalid; never infer | text-only |
| email | typed/document draft | no | existing validation; `-` skips | remain in field state | text-only |
| IBAN | typed/document draft | no | canonical uppercase/no spaces plus contact-specific checksum validation; `-` skips | remain in field state | text-only |
| contact person | typed/document draft | no | trimmed; `-` skips | remain in field state | text-only |

No LLM selects, ranks, modifies, or fills official registry data. The document parser may extract IBAN as a draft only; Python validates it and the final preview exposes it.

## 6. Public route and convergence map

| Entry | Public entry | Guards | Resolver/helper | Shared owner | Result |
|---|---|---|---|---|---|
| command | `/contact`, `/contact_add`, `/add_kontakt` | authorization middleware, active workspace/profile binding | none | `start_add_contact_intake` | registry query or legacy manual path |
| semantic text | existing `add_contact` route | authorization and idle/active-FSM guard | bounded semantic resolver | same start owner | same FSM |
| voice | existing `add_contact` transcript route | authorization before STT; active FSM after STT | bounded semantic resolver | same start owner | starts flow only; exact values rejected/routed to typed instruction |
| file | current contact document intake | authorization, no unrelated active FSM | existing document intake/parser | existing contact intake owner | draft preview, never auto-save |
| candidate button | `contact_registry_pick:<nonce>:<index>` | actor state, workspace membership/profile, nonce/index/age | deterministic callback parser | registry detail helper | detail preview, no DB write |
| registry action button | `contact_registry_action:<nonce>:<action>` | same guards and bounded action set | deterministic callback parser | contact FSM helper | supplement/save/manual/cancel transition |

## 7. FSM graph and state ownership

```text
idle
  -> name_hint (query prompt)
      feature disabled/outside pilot/no active workspace -> existing source_after_name/manual path
      registry enabled -> registry_search
        zero/error/timeout/unusable -> registry_fallback
        multiple -> registry_candidates -> registry_detail_preview
        one -> registry_detail_preview
          missing DIČ -> registry_required_dic
          supplement -> registry_optional_email -> registry_optional_iban -> registry_optional_contact_person
          save with complete required fields -> registry_final_confirm
          manual -> source_after_name/ico according to original query
          cancel -> idle
        registry_final_confirm -> transactional insert/update or conflict response -> idle/safe recovery

existing manual: name_hint -> source_after_name -> dic -> ic_dph -> address -> email -> iban -> contact_person -> confirm -> idle
existing document: source/intake -> intake_missing (including IBAN validation when present) -> intake_confirm -> idle
```

All contact states use the current five-minute contact-session expiry plus the shared active-FSM guard. `/menu`, `/start`, `/cancel`, and shared cancel wording use the existing state-control owner. Ordinary unrelated top-level text remains owned by the active contact FSM; no draft switching/restoration is added.

State rules:

| State | Accepted input | Side effects | Success | Invalid/stale/manual fallback |
|---|---|---|---|---|
| `name_hint` | typed name/IČO | bind scope; optional external GET after binding | search or existing manual source step | retry; `/menu` cancels safely |
| `registry_candidates` | bounded candidate callback | detail GET only | preview | stale/wrong callback no effect; manual fallback |
| `registry_detail_preview` | bounded action callback | none | supplement/final/manual/cancel | stale no effect |
| `registry_required_dic` | typed DIČ | FSM draft only | preview/supplement | retry; manual/cancel available |
| optional email/IBAN/person | typed value or `-` | FSM draft only | next field/preview | retry; no DB write |
| `registry_final_confirm` | shared yes/no decision/button | registry transaction only on yes | clear FSM + success | unknown stays; no clears; stale no write |

## 8. Decision and callback contract

- Final save uses the existing `yes_no` DecisionResolver family with context `contact_registry_confirm`; button tokens converge on the same helper.
- Candidate/action buttons are bounded navigation choices, not localized confirmation parsers.
- Candidate callback data contains only nonce/index. Action callback data contains only nonce/bounded action.
- Registry session data in FSM contains actor id, bound workspace id, active supplier/profile identity, created/expiry timestamp, nonce, original query, mapped candidates, and selected draft.
- Wrong state, nonce, actor, workspace, active profile, index, missing context, expiry, duplicate/repeated callback, and post-cancel callbacks fail closed without DB or external writes.
- Candidate/action keyboards are cleared after a successfully consumed callback where possible.
- Final transaction is idempotent by rechecking workspace + IČO and workspace + exact name immediately before mutation.

## 9. Side-effect and ownership map

| Effect | Trigger | Python owner | Gate | Failure/rollback |
|---|---|---|---|---|
| official RPO GET | valid query/selection | `SlovakCompanyRegistry` | feature flag, pilot, active workspace; timeout/size/status/JSON limits | manual fallback; no retry loop |
| FSM candidate/draft data | successful mapping | contact handler | bounded sanitized fields only | expiry/cancel clears through existing guard |
| contact schema add | local `init_db()` on supported old shape | DB bootstrap | exact supported shape only | SQLite transaction; unknown shape refuses |
| contact insert/update | explicit final yes | dedicated registry save service | transaction rechecks workspace/name/IČO conflicts and required fields | rollback on conflict/error |
| manual/document save | existing final yes | existing contact services | existing behavior plus nullable IBAN | existing semantics retained |

No raw RPO body is logged or stored. `source_type='registry'` and a bounded provider identifier are stored.

## 10. Authorization, tenant, precision, and migration boundaries

- Existing authorization middleware remains before handlers, STT, LLM/LMM, storage, and RPO calls.
- Registry is available only with a resolved active workspace; legacy/no-workspace sessions use manual/document flow.
- Every external request occurs only after `_bind_contact_scope`; every callback and write re-resolves membership and active profile.
- Exact identifiers, tax values, email, and IBAN are text/file-only.
- Current shape: contact has no `iban`; both legacy Telegram-scoped and workspace-aware supported schemas exist.
- Proposed shape: one nullable `iban TEXT` column in both supported shapes.
- Migration: exact old supported shape receives one `ALTER TABLE contact ADD COLUMN iban TEXT`; fresh DB includes it; repeat bootstrap is a no-op; incompatible shapes still fail closed. IDs and invoice `contact_id` values are untouched.
- Server backup/rollback requirement before later deployment: copy SQLite DB (including WAL/SHM handling per runbook), record SHA/commit, dry-run schema audit, stop writers for apply, and restore the verified backup on failure. No server or production write is part of this task.

## 11. User-facing responses and exits

- First prompt: `Zadajte názov firmy alebo IČO.` plus the existing visible `/menu` recovery hint.
- Multiple results: at most five official name/IČO/municipality summaries with inline buttons.
- Detail preview: official name, IČO, DIČ/`-`, confirmed IČ DPH/`-`, address, activity status when available, and source/freshness note.
- `Uložiť` is shown/accepted only when required fields validate. `Doplniť údaje`, `Zadať ručne`, and `Zrušiť` remain bounded actions.
- No result/outage/malformed response: explain the registry is unavailable and offer retry/manual/document continuation without losing workspace scope.
- Success clears FSM and confirms create/update. Conflict cases perform no write and explain manual resolution is required.

## 12. Product Truth and InfoHelp contract

- Capability id: existing `contacts`; no new canonical action/capability id.
- Status: `partial`: manual/document intake remains available, while registry lookup is disabled by default, pilot-gated, and dependent on external official-source availability.
- Can you do this?: yes, in enabled workspaces the bot can search official Slovak RPO data by name or IČO, let the user choose, and prepare a contact; missing tax/optional fields remain manual and saving always needs confirmation.
- How?: start `/contact`, type company name/IČO, choose a result, review/complete fields, then confirm save.
- Forbidden claims: real-time guarantee, DIČ/IČ DPH inference, commercial scraping, automatic IBAN/email/person discovery, background synchronization, or save without confirmation.

## 13. Negative space and regression contract

Must remain unchanged: manual `/contact` and `/contact_add`; semantic and voice start of `add_contact`; text-only exact values; PDF/contract intake; `/menu` and cancellation; inactivity timeout; active-FSM ownership; workspace/profile isolation; invoice contact lookup and aliases; invoice/contact foreign keys; supplier onboarding/IBAN; document intake; shared decision callbacks; unauthorized fail-closed behavior. Manual `create_or_replace` semantics are not converted into registry merge semantics.

## 14. Acceptance scenarios

The implementation and Conversation Acceptance Proof must cover task scenarios A-J plus: command alias convergence, semantic/voice start with exact-value voice exclusion, feature flag/pilot fallback, official mapping without DIČ/IČ DPH fabrication, candidate callback ownership/expiry/idempotency, optional field normalization/skip, new/update/name-collision/split-row conflict transaction cases, migration freshness/idempotency/row and invoice reference preservation, Product Truth question no-effect, and an unchanged supplier-IBAN journey.

## 15. Out of scope and known gaps

- No commercial provider, scraping, FinStat/Valida, browser automation, background sync, foreign registry, Mini App, CRM, automatic IBAN/email/person discovery, production migration, deployment, commit, or push.
- Official RPO REST data is documented as updated daily and may lag source RPO changes by up to 24 hours.
- RPO does not provide DIČ or IČ DPH in its public entity schema. The Financial Administration information-list API requires separate API-key setup and exact list searches; it is not added to this slice. DIČ is typed and validated; IČ DPH is typed/empty and never inferred.
- Cache is deferred; it is optional, not canonical storage, and unnecessary for correctness.

## 16. Evidence index and verdict

- Baseline main HEAD: `f4415cdf71bedf370aa5f141c7abee8efff80cb4`
- Current owners: `bot/handlers/contacts.py`, `bot/services/contact_service.py`, `bot/services/workspace_contact_service.py`, `bot/services/db.py`, `bot/services/validation.py`, `bot/services/llm_contact_parser.py`, `bot/handlers/decision_callbacks.py`, `bot/services/active_fsm_guard.py`, `bot/services/workspace_context.py`
- Current tests: `tests/test_contact_intake_semantic_flow.py`, `tests/test_workspace_contact_service.py`, `tests/test_contact_lookup_normalization.py`, `tests/test_decision_callbacks.py`, `tests/test_voice_state_routing.py`, `tests/test_state_control.py`, multi-workspace migration tests
- Contracts: `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`, `docs/llm/New_Action_Design_Checklist.md`, `docs/Code_Agent_Handoff_Contract.md`, `docs/Implementation_Agent_Checklist.md`, `docs/Evaluation_and_Smoke_Test_Standards.md`, `docs/Canonical_Decision_Resolver_Contract.md`, `docs/FakturaBot_Data_Migration_Runbook.md`, active Product Truth/InfoHelp/LLM/TZ docs
- Official source evidence: RPO public UI links its REST API documentation; production base `https://api.statistics.sk/rpo/v1/`; documented `/search` and `/entity/{id}`; full-text name and exact IČO filters; `onlyActive`; maximum 500 provider results; daily refresh; CC-BY 4.0. Live read-only audit returned HTTP 200 for search and detail on 2026-07-17.
- Existing dirty working-tree files before task: `PROJECT_LOG.md`, `tests/test_access_workspace_reactivation.py`; they are not baseline-clean evidence and must be preserved.

ready_for_handoff
