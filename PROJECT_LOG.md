# PROJECT_LOG

## 2026-04-19 — Session 045 — TZ alignment with planned `info_help` guidance layer

### Goal
Align `docs/TZ_FakturaBot.md` with the newer docs-first `info_help` architecture at high-level product/requirements level, without duplicating the detailed focused spec.

### Changes
- updated `docs/TZ_FakturaBot.md` (section 5) with a surgical high-level `info_help` alignment block:
  - clarified `info_help` as bounded guidance/navigation/recovery layer (not free-form chat, not direct-action duplicate);
  - fixed routing precedence: top-level action first, question form does not block direct actions, `info_help` only on top-level `unknown`;
  - added concise contract-precedence note: `info_help` remains subordinate to existing bounded `docs/llm` rules;
  - added capability status model (`implemented` / `planned` / `unsupported`) and truthfulness requirement;
  - added structured logging requirement for all `info_help` entries as product signals;
  - added Phase 2/3 future-direction note (state-aware guidance, reset/new-task support, bounded runtime explainability);
  - explicitly prohibited arbitrary source-code/raw-log reading by LLM in this layer;
  - preserved caution for unconfirmed flows (contact edit, old-invoice deletion, send-invoice/send-email, support escalation);
  - added explicit reference to detailed spec `docs/Info_Help_Guidance_Layer.md`.

### Scope boundary
- Docs-only alignment patch.
- No runtime code changes.
- No upgrade of unsupported/planned behavior to implemented.

## 2026-04-19 — Session 044 — Refinement: Phase 2/3 runtime explainability for `info_help` spec

### Goal
Extend the docs-first `info_help` specification with forward-looking runtime explainability/debug-aware guidance rules for later phases, while preserving strict bounded `docs/llm` contract precedence.

### Changes
- updated `docs/Info_Help_Guidance_Layer.md` with targeted additions:
  - future-direction note: controlled runtime explainability in Phase 2/3;
  - new subsection for bounded Python-prepared runtime/debug context (`FSM state`, flow, next actions, reset availability, STT failure count, error category, fallback reason, API/quota status, sanitized summary);
  - explicit prohibitions against arbitrary source-code/raw-log reading by LLM and against leaking secrets/internal traces/paths;
  - added worked examples for repeated STT failure and model/API or quota/credits failure;
  - extended logging rationale with runtime-explainability signals;
  - extended Phase 2/3 rollout bullets with debug-aware guidance and optional admin reliability summaries.

### Scope boundary
- Docs-only refinement.
- No runtime code changes.
- No new implementation claims beyond planned behavior.

## 2026-04-19 — Session 043 — Docs-first spec for `info_help` guidance/navigation layer

### Goal
Add a dedicated docs-first architecture/spec for planned `info_help` capability, explicitly subordinate to existing bounded `docs/llm` contract, without runtime implementation changes.

### Changes
- added new spec document: `docs/Info_Help_Guidance_Layer.md`
  - defines purpose/scope/non-goals for controlled guidance/navigation/recovery layer;
  - fixes routing rule: top-level action resolution first, `info_help` only on top-level miss;
  - defines internal `info_help` submodes (`faq_topic`, `state_guidance`, `action_offer_or_handoff`, `restart_or_reset_request`, `support_escalation`);
  - defines capability status model (`implemented`, `planned`, `unsupported`) with truthful response rules;
  - defines bounded knowledge-registry shape and staged LLM interaction contract;
  - defines safety requirements (no hidden mutation, explicit confirmation for handoff/reset);
  - defines mandatory structured logging fields for all info-layer requests;
  - includes worked examples and explicit truthfulness boundaries for unconfirmed flows;
  - includes phased rollout and docs-alignment checklist.

### Scope boundary
- Docs-only change.
- No runtime code changes.
- No behavior claimed as implemented beyond confirmed current runtime.

## 2026-04-19 — Session 042 — Invoice date edit expansion (issue/delivery/due) with voice-first bounded LLM contract

### Goal
Expand `upraviť faktúru` invoice-level date editing from one narrow `edit_invoice_date` path to full three-date support (`vystavenia`, `dodania`, `splatnosti`) and make value capture voice/text parity via bounded LLM normalization contract.

### Changes
- invoice-level action surface (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - added canonical operations:
    - `edit_invoice_issue_date`
    - `edit_invoice_delivery_date`
    - `edit_invoice_due_date`
  - kept `edit_invoice_date` as clarification-only umbrella intent (`upraviť dátum` -> ask which date).
- user prompts/messages (`bot/handlers/invoice.py`):
  - updated invoice-level edit menu to list all three concrete date actions;
  - added clarification prompt:
    - `Ktorý dátum chcete upraviť: vystavenia, dodania alebo splatnosti?`
  - added exact value prompts:
    - `Napíšte alebo nadiktujte nový dátum vystavenia... DD.MM.RRRR`
    - `Napíšte alebo nadiktujte nový dátum dodania... DD.MM.RRRR`
    - `Napíšte alebo nadiktujte nový dátum splatnosti... DD.MM.RRRR`
  - success messages split per field:
    - `Dátum vystavenia bol upravený.`
    - `Dátum dodania bol upravený.`
    - `Dátum splatnosti bol upravený.`
- bounded LLM date normalization contract (`bot/services/semantic_action_resolver.py`, `bot/handlers/invoice.py`):
  - added `resolve_invoice_date_normalization(...)` that enforces bounded output:
    - JSON `{ "normalized_date": "DD.MM.RRRR" }` or `{ "normalized_date": "unknown" }`;
  - invoice date value handler now uses this contract for both text and voice/STT input;
  - Python side only performs strict format/date validation and applies persistence/reject logic.
- validation and persistence (`bot/handlers/invoice.py`, `bot/services/invoice_service.py`):
  - added `update_invoice_delivery_date(...)` and `update_invoice_due_date(...)`;
  - enforced invariant reject:
    - `Dátum splatnosti nemôže byť skôr ako dátum vystavenia. Zadajte prosím správny dátum.`
  - also prevents issue-date update that would violate `due_date >= issue_date`.
- tests (`tests/test_invoice_state_decisions.py`):
  - updated issue-date success path to new explicit action;
  - added routing clarification test for generic `upraviť dátum`;
  - added success coverage for delivery-date edit;
  - added invariant reject coverage for due-date earlier than issue-date;
  - added voice-style natural-language date input test with mocked bounded normalization result.

### Scope boundary
- Item-level edit flow was not changed.
- No hidden auto-fix behavior added; all invariant conflicts remain fail-loud with explicit user-facing reject.

## 2026-04-19 — Session 041 — Hardening `nový opis položky` isolation from alias mappings

### Goal
Close pre-merge risk check: ensure `nový opis položky` mutates only invoice item fields and has no side effects on supplier service-alias DB state.

### Changes
- invoice item mutation path isolation (`bot/services/invoice_service.py`, `bot/handlers/invoice.py`):
  - added explicit `update_item_main_description(...)` method in `InvoiceService`;
  - switched `replace_main_description` handler path from `update_item_service(...)` to `update_item_main_description(...)` to make intent/scope explicit (invoice item only).
- regression coverage (`tests/test_invoice_state_decisions.py`):
  - added test `test_novy_opis_updates_only_invoice_item_without_alias_db_side_effects` that verifies:
    - main item description is replaced exactly (no appended tail),
    - item details are untouched,
    - service-alias mappings remain identical before/after action.

### Scope boundary
- Minimal change only for isolation/clarity.
- No changes to `zmeniť službu` runtime branch.
- No confirmation-flow or FSM redesign changes.

## 2026-04-19 — Session 040 — UX wording cleanup for `upraviť faktúru` item-level edit flow

### Goal
Align item-level edit naming/messages with real runtime semantics without changing confirmation architecture or broad FSM design.

### Changes
- user-facing prompt cleanup (`bot/handlers/invoice.py`):
  - removed `kontakt` from top-level `upraviť faktúru` scope prompt (`faktúra` now shows only `číslo/dátum`);
  - replaced item-action menu wording with explicit four actions:
    - `zmeniť službu`
    - `nový opis položky`
    - `pridať detaily k položke`
    - `vymazať detaily položky`
- item edit action routing/messages (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - split bounded item-action semantics into:
    - `replace_service`
    - `replace_main_description`
    - `add_item_details`
    - `clear_item_details`
  - updated input prompts to match action semantics:
    - main description replacement prompt explicitly states replacement;
    - details prompt explicitly asks for details;
    - clear-details action executes immediately and returns clear-details-specific feedback.
- success-message precision (`bot/handlers/invoice.py`):
  - `Služba položky bola zmenená.`
  - `Opis položky bol nahradený novým textom.`
  - `Detaily položky boli doplnené.`
  - `Detaily položky boli vymazané.`
  - empty-clear case: `Položka nemá žiadne detaily na vymazanie.`
- tests (`tests/test_invoice_state_decisions.py`):
  - updated item-level flow assertions to new user-facing action names and success copy;
  - added state assertion for `nový opis položky` action mode;
  - updated detail-flow expectations to additive details semantics and new messages.

### Scope boundary
- No redesign of confirmation-flow.
- No breaking changes for working `zmeniť službu` branch semantics.
- No large FSM refactor; only minimal routing/message touch for item-level UX fidelity.

## 2026-04-19 — Session 039 — LLM contract rewrite for bounded confirmation/decision normalization

### Goal
Fix unstable `unknown` outcomes in bounded confirmation steps by rewriting only the LLM prompt/instruction contract (no Python routing/fallback expansion).

### Changes
- bounded resolver prompt rewrite (`bot/services/semantic_action_resolver.py`):
  - replaced overly literal/conservative system prompt with explicit intent-normalization policy;
  - added stepwise policy in system prompt: semantic intent inference -> canonical normalization -> `unknown` only for true ambiguity/non-decision/garbage;
  - explicitly documented `yes_no_confirmation` behavior (user not required to answer exact `ano`/`nie`);
  - explicitly documented `postpdf_decision` normalization (`approve/confirm/save` -> `schvalit`, `edit/change/correct` -> `upravit`, `delete/cancel/remove/discard` -> `zrusit`) with destructive-safety guard for unclear intent.
- bounded resolver user payload contract (`bot/services/semantic_action_resolver.py`):
  - added `normalization_contract` object to reinforce semantic-intent-first behavior and context-specific mapping expectations.
- tests (`tests/test_invoice_intent_prerouter.py`):
  - added LLM-path contract tests (mocked `AsyncOpenAI`) for multilingual/noisy confirmation inputs in `invoice_preview_confirmation`;
  - added LLM-path contract tests for multilingual delete/cancel/remove/discard intents in `invoice_postpdf_decision`;
  - assertions verify model path usage (`fallback_used=False`) and presence of new instruction contract fields in prompt/payload.

### Scope boundary
- No FSM/routing changes.
- No fallback keyword/synonym expansion in Python.
- Fix is implemented through LLM contract only.

## 2026-04-18 — Session 038 — Contract-correction pass for edit FSM (item target bounded resolver + runtime contact removal)

### Goal
Finalize previous clean FSM rewrite without redesigning again: align remaining gaps with docs/llm contract by moving multi-item target selection to bounded semantic resolution and removing `edit_invoice_contact` from runtime edit surface.

### Changes
- item-target contract correction (`bot/handlers/invoice.py`):
  - added bounded resolver helper `_resolve_item_target_index_bounded(...)` with dedicated context `invoice_edit_item_target_selection`;
  - `waiting_edit_item_target` no longer relies on local `isdigit()` gate as primary selector;
  - handler now resolves canonical target via bounded resolver first, then Python validates range (`1..N`) and performs fail-loud clarification with state preserved.
- runtime contact edit removal (`bot/handlers/invoice.py`, `bot/services/semantic_action_resolver.py`):
  - removed `edit_invoice_contact` from invoice-level runtime allowed actions;
  - removed contact wording from invoice-level user prompts;
  - removed invoice-action runtime branch for contact edit;
  - removed fallback mapping for `edit_invoice_contact` in context `invoice_edit_invoice_action`.
- fallback support (`bot/services/semantic_action_resolver.py`):
  - added fallback context `invoice_edit_item_target_selection` for deterministic non-LLM fallback (`1/2/3`, basic ordinal/cardinal forms).
- tests (`tests/test_invoice_state_decisions.py`, `tests/test_voice_state_routing.py`):
  - added multi-item target coverage for numeric and spoken ordinal selection;
  - added ambiguous target + out-of-range fail-loud/state-preserved coverage;
  - added runtime-surface tests proving invoice action prompt no longer offers contact edit and contact text is treated as unknown;
  - added extra voice invoice-action routing check for date phrase.

### Scope boundary
- No new architecture redesign from scratch.
- Kept prior clean state split and value executors unchanged.
- Kept text-only policy for final description value state unchanged.

## 2026-04-18 — Session 037 — Clean FSM/orchestrator redesign for `upraviť faktúru` edit subflow

### Goal
Replace legacy mixed item/invoice edit routing with clean bounded orchestrator states and state-scoped semantic resolution, including voice parity for edit-flow control states.

### Changes
- invoice edit FSM/orchestrator rewrite (`bot/handlers/invoice.py`):
  - replaced mixed `waiting_edit_operation` contract with explicit state split:
    - `waiting_edit_scope`
    - `waiting_edit_invoice_action`
    - `waiting_edit_item_target`
    - `waiting_edit_item_action`
    - value states (`waiting_edit_service_value`, `waiting_edit_invoice_number_value`, `waiting_edit_invoice_date_value`, `waiting_edit_description_value`)
  - replaced heuristic `_detect_edit_operation(...)` primary routing with bounded state-scoped semantic resolvers:
    - scope resolver (`invoice_edit_scope_selection`)
    - invoice action resolver (`invoice_edit_invoice_action`)
    - item action resolver (`invoice_edit_item_action`)
  - removed invoice-level action handling from item-target state; item-target now handles only item index selection.
  - rewrote edit entrypoint from legacy `_start_invoice_item_edit_flow(...)` to clean `start_invoice_edit_flow(...)` with explicit scope selection first.
  - kept integrity rules and reuse of existing executors (`update_item_service`, `update_item_description`, `update_invoice_number`, `update_invoice_issue_date`, PDF rebuild/post-edit prompt helpers).
  - kept `waiting_edit_description_value` as text-only final precision state; number/date states now support voice/text with fail-loud exact-text fallback prompts on invalid/ambiguous input.
- semantic fallback support (`bot/services/semantic_action_resolver.py`):
  - added deterministic fallback contexts for new bounded edit states (`invoice_edit_scope_selection`, `invoice_edit_invoice_action`, `invoice_edit_item_action`) for non-LLM test/runtime fallback paths.
- voice routing parity (`bot/handlers/voice.py`):
  - removed text-only guards for edit-flow selection/control states; STT text now routes through the same edit handlers as text input for:
    - scope
    - invoice action
    - item target
    - item action
    - service value
    - invoice number/date value
  - retained text-only guard only for final item-description value state.
- tests (`tests/test_invoice_state_decisions.py`, `tests/test_voice_state_routing.py`):
  - updated edit-flow tests for clean state graph transitions (scope -> branch-specific states).
  - added explicit routing coverage for `upraviť opis položky` -> description branch and `zmeniť službu` -> service branch.
  - updated single-item and multi-item flow assertions to new orchestrator steps.
  - updated invoice-level branch tests to use `waiting_edit_invoice_action` before number/date value states.
  - expanded voice routing coverage for edit scope, invoice action, item target, item action, service value, and number/date value handler routing.
  - strengthened regression by asserting FSM transition to correct final input state before final handlers (removes prior false-green pattern).

### Scope boundary
- Clean redesign of bounded `upraviť` subflow only (post-PDF in-action model).
- No standalone top-level `edit_invoice` executor added.
- `edit_invoice_contact` remains planned/future-ready (not implemented value persistence).

## 2026-04-17 — Session 036 — Fix post-edit return for `edit_item_description` approval stage

### Goal
Fix narrow runtime bug where successful item description edit inside `upraviť` could return user into edit-loop context instead of reliably staying in post-PDF approval stage.

### Changes
- invoice edit success return hardening (`bot/handlers/invoice.py`):
  - added `_send_post_edit_approval_prompt(...)` helper for post-edit success responses;
  - helper explicitly enforces FSM state `waiting_pdf_decision` before sending approval prompt;
  - wired helper into all successful edit handlers (`replace_service`, `edit_item_description`, `edit_invoice_number`, `edit_invoice_date`) after successful PDF rebuild.
- regression coverage (`tests/test_invoice_state_decisions.py`):
  - extended `replace_service` test with explicit state + approval prompt assertions;
  - extended `edit_item_description` success path test with explicit state + approval prompt assertions;
  - existing invoice number/date tests continue asserting post-edit approval state/prompt behavior.

### Scope boundary
- Narrow runtime bugfix only.
- No edit architecture redesign.
- No expansion to unrelated actions/flows.

## 2026-04-16 — Session 035 — Semantic seam migration batch 1 (bounded service alias contract)

### Goal
Migrate remaining Python-first semantic service resolution seams (invoice parse + service clarification + invoice edit service change) to bounded LLM orchestration with DB-driven allowed sets, while keeping deterministic cleaning/validation unchanged.

### Changes
- invoice parser contract hardening (`bot/services/llm_invoice_parser.py`):
  - removed dictionary/normalizer-based service canonicalization from payload validation;
  - kept deterministic shape checks and safe string normalization only (`strip`, non-empty constraints);
  - service term is now treated as bounded semantic output to be resolved in runtime against allowed aliases.
- invoice runtime bounded resolution (`bot/handlers/invoice.py`):
  - added supplier-scoped bounded service alias resolver that:
    - fetches active alias options from DB,
    - keeps deterministic text cleaning for direct exact/normalized match,
    - otherwise calls bounded semantic resolver with allowed values + per-option description,
    - accepts only one alias from allowed set (or unknown).
  - migrated create-preview item service resolution to this bounded alias contract;
  - migrated service slot clarification (`waiting_service_clarification`) to bounded alias contract;
  - migrated invoice edit `replace_service` path to bounded alias contract;
  - removed old bridge-form/dictionary semantic fallback usage from these paths.
- focused tests (`tests/test_invoice_phase2_ai_layer.py`):
  - updated parser expectations to deterministic-only service-field repair behavior (no dictionary semantic rewrite),
  - added tests for bounded alias resolution (deterministic direct match + bounded LLM canonical selection),
  - adjusted multi-item preview fixture coverage to include alias set required by bounded contract.

### Scope boundary
- Deterministic cleaning/validation/FSM/persistence logic kept in Python.
- No giant synonym dictionaries introduced.
- No architecture expansion beyond bounded service-semantic seams targeted in this batch.

## 2026-04-16 — Session 034 — Pre-merge audit fixes for Phase 1 multi-item `create_invoice`

### Goal
Apply only merge-blocking safety fixes discovered during pre-merge audit of Phase 1 multi-item `create_invoice` runtime patch.

### Changes
- item-boundary ambiguity hardening (`bot/handlers/invoice.py`):
  - strengthened `_looks_like_item_boundary_split(...)` with numeric-token count check against expected item count;
  - prevents silent acceptance of two-item candidate splits when raw text contains only one amount token (e.g. conjunction phrase with one number).
- aggregate total invariant hardening:
  - in confirmation save path, added explicit guard that draft aggregate total equals sum of persisted item totals before DB insert;
  - in `InvoiceService.create_invoice_with_items(...)`, added fail-loud invariant check (`invoice total == sum(item totals)`).
- docs consistency:
  - removed contradictory `single-item` status line in orchestrator contract section 6.2 so runtime status markers are internally consistent.
- focused regression tests:
  - added ambiguity regression for multi-item candidate with conjunction but single amount token (must clarify, not save silently);
  - added save-path regression proving total mismatch is rejected fail-loud and invoice is not persisted.

### Scope boundary
- No architecture redesign.
- No scope expansion to delete/edit-contact/unrelated flows.
- Only targeted merge-safety fixes for bounded Phase 1 behavior.

## 2026-04-16 — Session 033 — Phase 1 runtime multi-item support for `create_invoice` intake

### Goal
Implement the smallest safe runtime path for Phase 1 multi-item invoice intake in `create_invoice` flow, while preserving backward-compatible singleton behavior and Python-owned validation/side effects.

### Changes
- prompt contract (`prompts/invoice_draft_prompt.txt`):
  - extended invoice draft prompt with optional bounded `biznis_sk.items[]` candidate shape;
  - preserved singleton fields as mandatory backward-compatible shape;
  - documented Phase 1 bound `items[]` max size = 3 and no open-ended extraction.
- parser/validator (`bot/services/llm_invoice_parser.py`):
  - added optional dual-shape validation for `biznis_sk.items[]`;
  - implemented fail-safe payload errors for invalid items shape, count overflow, and unresolved item service terms;
  - preserved legacy singleton validation path and cleanup behavior.
- runtime normalization/build (`bot/handlers/invoice.py`):
  - intake extraction now always provides internal `items[]` normalized draft shape (singleton auto-wrap);
  - preview builder now supports single-item and bounded multi-item normalization with safe checks:
    - max items bound,
    - boundary ambiguity guard,
    - per-item quantity/unit_price/amount coherence via existing deterministic semantics;
  - added bounded clarification slot for item-split/financial ambiguity (`items`);
  - preview text formatting now renders item lines when draft has multiple items.
- persistence (`bot/services/invoice_service.py`):
  - added `CreateInvoiceItemPayload` and `create_invoice_with_items(...)`;
  - kept `create_invoice_with_one_item(...)` as compatibility wrapper over new multi-item insert path.
- save/confirm path (`bot/handlers/invoice.py`):
  - `process_invoice_preview_confirmation(...)` now persists all normalized draft items when present;
  - singleton save behavior remains compatible.
- service normalization (`bot/services/service_term_normalizer.py`):
  - added Slovak `montáž/montaz` variants to deterministic canonical mapping.
- tests:
  - expanded Phase 2 parser/preview tests with dual-shape extraction, bounds rejection, multi-item preview total, and ambiguous multi-item clarification;
  - added state-decision regression ensuring confirmation persists multiple `invoice_item` rows.

### Scope boundary
- Added: Phase 1 multi-item support for create-invoice intake/runtime path.
- Not added: delete/cancel flow redesign, advanced layout redesign, or unrelated edit-flow redesign.
- LLM remains bounded candidate extractor; Python remains validator/workflow/persistence owner.

## 2026-04-16 — Session 032 — Docs-first dual-shape `create_invoice` intake contract for future multi-item support

### Goal
Define a safe docs-first contract evolution for `create_invoice`/Phase 2 invoice intake so future runtime can support both one item and multiple items without breaking bounded architecture or current single-item behavior.

### Changes
- orchestrator contract (`docs/FakturaBot_LLM_Orchestrator_Contract.md`):
  - added dedicated docs-first section for planned `create_invoice` dual-shape intake;
  - documented backward-compatible strategy:
    - keep existing singleton `biznis_sk` item fields,
    - add optional bounded `biznis_sk.items[]`;
  - fixed authority split for segmentation:
    - LLM may return bounded candidate item segmentation only,
    - Python remains final validator/workflow/persistence owner;
  - documented Phase 1 bounds:
    - `items[]` max size = 3,
    - no open-ended extraction;
  - documented candidate item shape (service term + qty/unit/unit_price/amount + optional detail),
  - documented split semantics examples and fail-safe clarification triggers.
- product spec (`docs/TZ_FakturaBot.md`):
  - added subsection under invoice draft section with same dual-shape decisions, bounds, ambiguity/fallback rules, and future runtime follow-up areas.
- in-action registry (`docs/llm/In_Action_Response_Registry.md`):
  - added docs-first contract-tracking row for `create_invoice` Phase 2 dual-shape intake;
  - added explicit note that runtime remains single-item until follow-up patches.

### Scope boundary
- Docs-first only.
- No runtime implementation in this patch.
- No prompt implementation in this patch.
- Current create flow remains single-item until follow-up parser/runtime/prompt patches.

## 2026-04-15 — Session 031 — Runtime `edit_invoice_date` inside bounded `upraviť` flow

### Goal
Implement runtime support for invoice-date edit (`edit_invoice_date`) inside existing bounded `edit_invoice`/`upraviť` flow, without expanding to contact edit or item numeric/unit/price edits.

### Changes
- invoice edit runtime:
  - extended bounded edit operation detection with invoice-level operation `edit_invoice_date`;
  - added bounded FSM state for invoice-date value input;
  - wired selection path from existing `upraviť` flow (single-item and multi-item invoices) to invoice-date edit state;
  - added bounded Slovak prompts for strict date input:
    - entry: `Aktuálny dátum faktúry je {current_date}. Napíšte nový dátum textom vo formáte DD.MM.RRRR.`
    - invalid: `Neplatný dátum. Zadajte prosím dátum vo formáte DD.MM.RRRR.`
- validation/safety:
  - added strict Phase 1 parser helper `parse_strict_date_dd_mm_yyyy(...)`;
  - accepts only `DD.MM.RRRR`;
  - rejects non-matching format and impossible dates (e.g. `31.02.2026`);
  - no natural-language parsing, no silent reinterpretation, no best-guess date conversion.
- persistence/service:
  - added invoice service helper `update_invoice_issue_date(...)`;
  - on valid input, updates `invoice.issue_date` with normalized ISO value used by current storage model.
- rebuild flow:
  - after successful invoice-date update, runtime rebuilds updated PDF and returns to `waiting_pdf_decision`;
  - previous PDF cleanup path remains aligned with existing edit rebuild behavior.
- voice guard:
  - added text-only guard for invoice-date edit state in voice handler:
    - `Pre dátum faktúry použite textový vstup vo formáte DD.MM.RRRR.`

### Invariant decision for this patch
- Chosen behavior: **B**.
- Editing invoice date is allowed while invoice number remains unchanged in this patch.
- No auto-renumbering is introduced.

### Tests
- added runtime tests for:
  - successful invoice-date edit to valid strict value (+ persistence + PDF rebuild + post-edit state),
  - invalid format rejection with bounded Slovak prompt and preserved old value/state,
  - impossible date rejection with safe retry prompt and preserved old value/state,
  - voice precision-safe guard for invoice-date edit state.
- existing `upraviť položku` and `upraviť číslo faktúry` runtime tests remain in suite as regression coverage.

### Scope boundary
- This runtime patch adds only `edit_invoice_date`.
- Still out of scope (not implemented here):
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`

## 2026-04-15 — Session 030 — Runtime `edit_invoice_number` inside bounded `upraviť` flow

### Goal
Implement runtime support for invoice-number edit (`edit_invoice_number`) inside existing bounded `edit_invoice`/`upraviť` flow, without expanding to other invoice-level or item numeric/date/contact edits.

### Changes
- invoice edit runtime:
  - extended bounded edit operation detection with invoice-level operation `edit_invoice_number`;
  - added bounded FSM state for invoice-number value input;
  - wired selection path from existing `upraviť` flow (single-item and multi-item invoices) to invoice-number edit state;
  - added precision-safe prompts for text-only final invoice-number input;
- validation/safety:
  - added runtime invoice-number validation for project format (`RRRRNNNN`) with issue-year consistency check;
  - added application-level uniqueness check before save;
  - duplicate detection returns bounded Slovak prompt and keeps edit state:
    - `Číslo faktúry už existuje. Zadajte prosím iné číslo.`
  - no overwrite, no auto-rename, no best-guess correction;
- persistence/service:
  - added invoice service helpers:
    - `is_invoice_number_available(...)`
    - `update_invoice_number(...)` with DB-level integrity fallback handling;
  - kept DB unique constraints as final guard (no schema weakening);
- rebuild flow:
  - after successful invoice-number update, runtime rebuilds updated PDF and returns to `waiting_pdf_decision`;
  - previous PDF file path cleanup is attempted when invoice number change produces a different PDF path;
- voice guard:
  - added text-only guard for invoice-number edit state in voice handler.

### Tests
- added runtime tests for:
  - successful invoice-number edit to free value (+ persistence + PDF rebuild + post-edit state),
  - duplicate invoice-number rejection with required bounded Slovak prompt and preserved old value/state,
  - invalid invoice-number rejection with safe retry prompt and preserved old value/state,
  - voice precision-safe guard for invoice-number edit state.
- preserved and reran existing `upraviť položku` regression coverage.

### Scope boundary
- This runtime patch adds only `edit_invoice_number`.
- Still out of scope (not implemented here):
  - `edit_invoice_date`
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`

## 2026-04-15 — Session 029 — Docs-first full `edit_invoice` / `upraviť` scope map

### Goal
Document one unified planned edit surface for `edit_invoice` so future runtime patches follow a single contract (invoice-level + item-level) instead of separate mini-flows.

### Changes
- updated orchestrator contract to formalize full bounded `edit_invoice` subflow map:
  - invoice-level operations:
    - `edit_invoice_number`
    - `edit_invoice_date`
    - `edit_invoice_contact`
  - item-level operations:
    - `replace_service`
    - `edit_item_description`
    - `edit_item_quantity`
    - `edit_item_unit`
    - `edit_item_unit_price`
- documented required decisions:
  - `edit_invoice` remains reserved top-level token with bounded in-action/subflow runtime;
  - invoice-level and item-level fields are documented separately;
  - precision-sensitive item fields require item targeting;
  - single-item invoices may default to first item;
  - multi-item invoices require explicit selection or bounded clarification;
  - precision-sensitive fields are text-first where ambiguity risk is high;
  - destructive/integrity-sensitive edits fail safe (no silent auto-fix).
- updated in-action registry to split `edit_invoice` map into:
  - `edit_invoice:invoice_level` (planned),
  - `edit_invoice:item_level` (partial: implemented + planned).
- updated TZ section 4.7 to align product-level contract with the same full map and explicit status markers.

### Notes
- Docs-only session; no runtime code changes.
- Newly mapped operations are not runtime-implemented yet:
  - `edit_invoice_number`
  - `edit_invoice_date`
  - `edit_invoice_contact`
  - `edit_item_quantity`
  - `edit_item_unit`
  - `edit_item_unit_price`
- Existing runtime coverage remains:
  - `replace_service`
  - `edit_item_description`

## 2026-04-15 — Session 028 — Runtime Phase 1 item edit inside `upraviť faktúru`

### Goal
Implement runtime Phase 1 item-edit subflow under post-PDF `upraviť` decision, including separate operations (`replace_service`, `edit_item_description`), `item_description_raw` persistence, bounded validation, and PDF rebuild.

### Changes
- DB/schema:
  - added `invoice_item.item_description_raw` column to bootstrap schema;
  - added backward-compatible bootstrap migration path (`ALTER TABLE ... ADD COLUMN item_description_raw`) for legacy local DB shape;
- service layer:
  - extended `InvoiceItemRecord` with `item_description_raw`;
  - added item update methods:
    - `update_item_service(...)`
    - `update_item_description(...)`
  - added `ContactService.get_by_id(...)` for rebuild path;
- invoice runtime flow:
  - replaced post-PDF `upraviť` placeholder cancel path with real item-edit subflow entry;
  - added bounded states for item-edit:
    - target item selection (future-ready multi-item),
    - operation selection (`replace_service` vs `edit_item_description`),
    - service update input,
    - description text input;
  - single-item invoices default to first item target;
  - multi-item invoices require bounded item index clarification;
  - `replace_service` reuses existing alias dictionary resolution path and does not mutate `item_description_raw`;
  - `edit_item_description` supports `set/replace/clear`, does not mutate canonical service fields;
  - added bounded overlength guard (max 2 rendered detail lines) with Slovak shorten prompt;
  - successful edits rebuild and resend updated PDF, then return to `waiting_pdf_decision`;
- voice guard:
  - in precision-sensitive description state, voice no longer writes final detail; bot requests text input;
  - added text-only guard prompts for other edit subflow precision states;
- PDF/render:
  - `PdfInvoiceItem` now supports optional `detail`;
  - PDF item rendering outputs main service title with optional detail line(s) below;
  - added render-fit helper `validate_item_detail_render_fit(...)` used by runtime validator.

### Tests
- added runtime tests for:
  - replace service with description preserved + PDF rebuild,
  - set/replace/clear description with canonical service preserved,
  - reject too-long description with bounded Slovak prompt and unchanged stored value,
  - single-item default targeting,
  - multi-item missing target clarification,
  - voice text-only guard for description state.

### Notes
- add-item flow remains out of scope.
- Runtime now supports Phase 1 item edit only (replace service, edit description).

## 2026-04-15 — Session 027 — Docs cleanup pass for Phase 1 item edit contract

### Goal
Cleanup docs after initial Phase 1 item-edit patch: remove naming drift, make clear semantics explicit, and document minimal machine-safe bounded output shape for `edit_invoice:item_edit`.

### Changes
- unified canonical operation names across docs for item edit:
  - `replace_service`
  - `edit_item_description`
  - `unknown`
- explicitly fixed description mutation semantics for `edit_item_description`:
  - `set`
  - `replace`
  - `clear`
- documented minimal bounded output shape for planned `edit_invoice:item_edit` in docs:
  - `target_item_index`
  - `operation`
  - `value`

### Notes
- Docs cleanup pass completed.
- Runtime implementation is still not included.

## 2026-04-15 — Session 026 — Docs-first Phase 1 item edit contract inside `upraviť faktúru`

### Goal
Introduce documentation-only source-of-truth contract for Phase 1 `upraviť položku` as in-action edit subflow within future `edit_invoice`, before any runtime patch.

### Changes
- updated orchestrator/docs contracts to formalize that:
  - `upraviť položku` is in-action (not top-level action),
  - Phase 1 item edit supports two distinct operations:
    - service replacement (canonical service identity),
    - free-text detail edit via separate `item_description_raw`;
- recorded render/preview rule:
  - main title from service alias/service DB,
  - optional `item_description_raw` rendered below title with max 2-line limit,
  - no silent truncation; bot must request shorter text in bounded Slovak prompt;
- documented precision-sensitive input rule:
  - `item_description_raw` is text-first/text-only safe in Phase 1,
  - voice must not freely guess long detail text into stored value;
- documented future-ready item-targeting contract:
  - current single-item default may target first item,
  - future multi-item invoices require explicit selection or bounded clarification.

### Notes
- Runtime implementation is not included in this session.
- Key decision: keep canonical service semantics separate from optional free-text item detail (`item_description_raw`).
- Add-item flow remains out of scope for this docs patch.

## 2026-04-14 — Session 025 — `add_service_alias` top-level semantic+voice runtime wiring

### Goal
Make existing manual `/service` flow reachable as canonical top-level action `add_service_alias` from text semantics and voice (top-level), without introducing a second service architecture.

### Changes
- runtime routing:
  - added canonical top-level action `add_service_alias` to top-level bounded resolver branch in `process_invoice_text(...)`;
  - routed semantic `add_service_alias` into the existing `/service` flow entry (shared supplier handler intake), no new service flow created;
- bounded resolver hints:
  - added optional runtime `action_hints` support to resolver payload;
  - used compact hints selectively for `add_service_alias` (ambiguous action) and minimal separation hint for `create_invoice`;
- voice:
  - top-level voice keeps current STT -> top-level semantic path; `add_service_alias` now reaches existing `/service` flow via that path;
  - added explicit voice rejection in service precision-sensitive states:
    - short alias: `Napíšte krátky názov položky textom.`
    - full title: `Napíšte plný názov služby textom.`
- tests:
  - top-level semantic resolution coverage for `add_service_alias`;
  - top-level semantic routing test into shared `/service` flow entry;
  - voice top-level pass-through coverage for `add_service_alias` path;
  - voice rejection coverage for service short/full text-only states;
  - manual `/service` command flow regression test (2-step save flow persists mapping).

### Notes
- Python remains execution authority.
- Bot-facing replies added/updated in runtime are Slovak-only.
- Precision-sensitive service fields remain text-only; no STT guessing for these steps.

## 2026-04-13 — Session 024 — `add_service_alias` ambiguous-action documentation prep

### Goal
Prepare docs before runtime work so `add_service_alias` can be introduced as a canonical ambiguous top-level action (manual flow exists now, semantic/voice invoke later).

### Changes
- updated orchestrator contract with optional semantic action hints section for ambiguous actions;
- added `docs/llm/Bounded_Resolver_Prompt_Template.md` with optional `action_hints` format and compact examples for `create_invoice` and `add_service_alias`;
- added `docs/llm/New_Action_Design_Checklist.md` with ambiguity/hints/canonical-vs-noisy wording checklist items;
- updated canonical action registry to explicitly mark `add_service_alias` as ambiguous, manual implemented, voice top-level invoke not yet, and hint support recommended for future bounded resolution;
- updated TZ with concise optional-hints requirement and canonical-vs-noisy wording separation rule;
- updated README doc pointers.

### Notes
- semantic action hints are documented as optional and selective (not mandatory for every action);
- no runtime code changes were made.

## 2026-04-13 — Session 023 — Canonical action audit repair (manual `/service` flow included)

### Goal
Repair canonical action audit after detecting that previous inventory missed at least one already implemented manual user-facing flow (`add_service_alias` via `/service`).

### Changes
- created `docs/llm/Canonical_Action_Registry.md` with corrected evidence-based inventory:
  - top-level user-facing actions,
  - bootstrap/admin flows,
  - explicit reserved placeholders (`send_invoice`, `edit_invoice`),
  - explicit correction note for implemented manual `/service` flow;
- created `docs/llm/In_Action_Response_Registry.md` with bounded in-action groups, deterministic confirmations, and slot-clarification groups;
- updated `docs/FakturaBot_LLM_Orchestrator_Contract.md` with registry linkage discipline;
- updated `README.md` with pointers to new audit registries.

### Audit correction note
`/service` flow is implemented-manual (command + in-flow text) and persists service alias mappings.  
It is not part of top-level semantic resolver list, but it is still a real user-facing action and must be tracked in canonical action audit.

## 2026-04-13 — Session 022 — Quantity/unit-price clarification semantics broadened

### Goal
Broaden existing bounded slot `quantity_unit_price_pair` from pair-only handling to natural clarification semantics:
- accept quantity + unit-price forms,
- accept price-only fallback (`quantity=1`),
while keeping current architecture and FSM flow unchanged.

### Changes
- `bot/handlers/invoice.py`:
  - updated Slovak clarification prompt to explicitly allow either:
    - quantity + unit price,
    - or price-only when quantity is 1.
- `bot/services/semantic_action_resolver.py`:
  - expanded bounded resolver instruction for `resolve_quantity_unit_price_pair(...)` to support:
    - pair input,
    - single-number input (maps to `quantity=1`);
  - expanded deterministic fallback parser to support additional natural forms:
    - `3 1500`, `3 * 1500`, `3 po 1500`, `3x po 1500`,
    - `три kusy по 1500`, `dva krát po 1500`,
    - `množstvo 3, cena za kus 1500`,
    - `количество 3, цена 1500`,
    - single-number price fallback (`1500` -> `1 × 1500`).
- tests:
  - added/extended slot-clarification tests for pair forms and price-only fallback;
  - kept existing pair regressions and voice routing regression.

### Constraints preserved
- Same slot token (`quantity_unit_price_pair`) and same FSM state (`waiting_slot_clarification`).
- No contact-flow changes, no service-slot repair changes, no generalized slot-clarification redesign.
- Python remains execution authority and source of truth.

## 2026-04-13 — Session 021 — Bounded quantity × unit_price slot clarification in invoice flow

### Goal
Add a dedicated bounded clarification path for missing financial breakdown in invoice flow (`quantity × unit_price`) without architecture redesign and without touching contact/service flows.

### Changes
- `bot/handlers/invoice.py`:
  - added dedicated slot `quantity_unit_price_pair` (reusing existing `waiting_slot_clarification` FSM state);
  - when financial breakdown is unresolved, clarification now targets this dedicated slot;
  - added slot-specific Slovak clarification prompt: `Uveďte množstvo a cenu za jednotku, napr. 2x po 1500.`;
  - wired bounded quantity/unit-price resolver in slot continuation path and update of partial draft fields (`quantity`, `unit_price`) only.
- `bot/services/semantic_action_resolver.py`:
  - added bounded resolver `resolve_quantity_unit_price_pair(...)` with strict structured output contract:
    - `{"canonical":"quantity_unit_price_pair","quantity":...,"unit_price":...}`
    - or `{"canonical":"unknown"}`;
  - LLM request now includes clarification context, `expected_reply_type=quantity_times_unit_price`, and supported languages `uk/ru/sk`;
  - deterministic fallback parser supports multilingual examples including numeric and small-number-word variants.
- tests:
  - added text clarification coverage for:
    - `2 крат по 1500`,
    - `два крат по 1500`,
    - `dva krát po 1500`;
  - added voice routing assertion that STT transcript in `waiting_slot_clarification` is passed unchanged to slot clarification path;
  - added regression for explicit-total-only invoice semantics (`1 × total`) to remain stable;
  - kept/updated existing generalized clarification expectations for the new dedicated financial slot prompt.

### Constraints preserved
- No new FSM state for clarification.
- No contact flow changes.
- Service-slot repair behavior preserved.
- Python remains source of truth for validation, draft update, amount computation, and preview lifecycle.

## 2026-04-12 — Session 020 — Generalized invoice slot clarification + project-wide partial-draft contract

### Goal
Expand already-merged service-slot clarification pattern to other critical invoice slots and formalize slot-level clarification/partial-draft retention as a structured workflow principle.

### Changes
- `bot/handlers/invoice.py`:
  - generalized unresolved-slot handling for invoice draft build with partial retention in FSM (`invoice_partial_draft`);
  - added slot-specific clarification prompts (Slovak-only) for customer, delivery date, due days, quantity, and unit price;
  - added unified continuation path for slot clarification replies that updates one slot and resumes preview build;
  - preserved existing service clarification behavior and compatibility state;
  - improved debug transparency for recoverable unresolved-slot cases.
- `bot/services/llm_invoice_parser.py`:
  - customer-candidate payload failures now emit recoverable `customer_unresolved` with partial payload snapshot.
- tests:
  - added focused invoice clarification coverage for customer/date/due-days/amount slot continuation;
  - preserved service-slot regression path and fatal payload fail-loud behavior checks.
- docs:
  - updated orchestrator contract + TZ + README + CHANGELOG for project-level slot clarification principle.

### Architectural decision
For structured workflows, fail one slot—not whole workflow:
- preserve partial state,
- clarify only unresolved slot,
- continue from current step,
- reserve full reset for fatal errors only.

## 2026-04-12 — Session 019 — AI orchestration contract shift to bounded canonicalization

### Goal
Record architecture milestone: transition from narrow draft/token-routing model to unified semantic resolver contract.

### Decision
- Adopt **Bounded Semantic Canonicalization** as the AI orchestration contract baseline.
- Introduce a unified **Semantic Action Resolver** concept for:
  - top-level action resolution,
  - in-state reply resolution,
  - value/slot canonicalization.
- Keep Python as the only execution authority for validation, context checks, and side effects.

### Notes
- LLM role is semantic canonicalization within Python-defined bounds (allowed set + context), returning one canonical token or `unknown`.
- This is a documentation/architecture alignment milestone; execution authority boundaries remain fail-loud on Python side.

## 2026-04-12 — Session 018 — Post-PDF fail-loud guard + cleanup-order hardening

### Goal
Close two correctness gaps in deterministic post-PDF lifecycle:
- fail loud when post-PDF FSM state misses `last_invoice_id`;
- prioritize invoice-number release by running DB cleanup before PDF-file cleanup.

### Changes
- `bot/handlers/invoice.py`:
  - `process_invoice_postpdf_decision(...)` now validates `last_invoice_id` at start and fails loud (`Návrh faktúry už nie je dostupný...`) instead of claiming success;
  - post-PDF `upraviť`/`zrušiť` cleanup order reversed to DB-first then file-unlink, with isolated error handling so unlink failure no longer blocks DB cleanup;
  - preview-confirm failure cleanup path (after invoice insert) now also does DB cleanup first and performs file cleanup in a separate guarded block.
- `tests/test_invoice_state_decisions.py`:
  - added regression for missing `last_invoice_id` in post-PDF state (no fake success);
  - added regression for unlink failure on post-PDF cancel ensuring invoice row is still deleted;
  - added regression for preview-confirm failure path with unlink failure ensuring invoice row is still deleted.

## 2026-04-12 — Session 017 — Deterministic post-PDF decision FSM + voice state routing

### Goal
Implement deterministic state-based command handling after invoice preview and after PDF send, while keeping existing top-level invoice pre-router unchanged.

### Changes
- `bot/handlers/invoice.py`:
  - kept top-level pre-router as-is (`_normalize_intent_token`, `_detect_invoice_intent`);
  - added deterministic preview parser for `InvoiceStates.waiting_confirm` (`confirm_preview` / `cancel_preview` / `unknown`) with SK/UA/RU yes-no coverage;
  - added deterministic post-PDF parser for `InvoiceStates.waiting_pdf_decision` (`approve_pdf_invoice` / `edit_pdf_invoice` / `cancel_pdf_invoice` / `unknown`) with SK/UA/RU command coverage;
  - extracted reusable handlers:
    - `process_invoice_preview_confirmation(...)`
    - `process_invoice_postpdf_decision(...)`
  - after PDF send, FSM now stores `last_invoice_id`, `last_invoice_number`, `last_pdf_path`;
  - added cleanup on PDF generation/send failure after invoice insert: remove PDF (if exists), delete invoice items + invoice row, clear FSM.
- `bot/handlers/voice.py`:
  - after STT, routes command deterministically by current FSM state:
    - `waiting_confirm` -> preview confirmation processor,
    - `waiting_pdf_decision` -> post-PDF decision processor,
    - otherwise -> existing generic invoice text flow.
- `bot/services/invoice_service.py`:
  - added lifecycle helpers:
    - `update_invoice_status(invoice_id, status)`
    - `delete_invoice_with_items(invoice_id)`
  - cleanup path now fully deletes invoice items + invoice row so invoice number is freed for reuse on `upraviť` / `zrušiť`.
- `tests/`:
  - extended parser tests for required multilingual preview/post-PDF commands;
  - added state-flow tests for preview confirm and post-PDF approve/edit/cancel behaviors, including cleanup and number release;
  - added voice routing tests to verify FSM-aware deterministic dispatch.

### Constraints preserved
- Top-level create/edit/send pre-router behavior remains unchanged.
- LLM still only drafts invoice payload; state command interpretation is deterministic Python.
- User-facing replies introduced/changed in this session are Slovak-only.

## 2026-04-12 — Session 016 — Delivery-date anchor follow-up (UA months + local year scope)

### Goal
Harden delivery-date year anchoring after review:
- add Ukrainian month forms for day/month-without-year detection;
- avoid disabling anchoring when an unrelated year appears elsewhere in the same message.

### Changes
- `bot/handlers/invoice.py`:
  - added Ukrainian month forms and common short forms to date phrase detection (`січня...грудня`, plus short forms);
  - added `_has_explicit_year_near_day_month(...)` and narrowed explicit-year detection to a local span around matched day+month phrase;
  - anchoring is now kept active when a year is present outside the local delivery-date phrase.
- `tests/test_invoice_phase2_ai_layer.py`:
  - added regression for unrelated-year-in-message case (anchoring must still apply);
  - added regression for Ukrainian month form (`4 квітня`);
  - added regression for explicit local year near day+month (anchoring must be disabled and explicit year respected).

### Constraints preserved
- Deterministic behavior only (no fuzzy parsing, no silent heuristics beyond explicit local-span rule).
- Fail-loud behavior unchanged for inconsistent explicit day/month vs payload date.

---

## 2026-04-11 — Session 015 — Invoice Phase 2 delivery-date year anchoring guardrail

### Goal
Stop LLM-induced wrong-year drift for delivery dates when user says only day+month (no explicit year), e.g. `4 апреля` incorrectly becoming `2023-04-04`.

### Changes
- `prompts/invoice_draft_prompt.txt`:
  - hardened instruction for `datum_dodania`: for explicit day+month without year, use current invoice-flow year (issue-date year), and do not invent arbitrary past/future year.
- `bot/handlers/invoice.py`:
  - added deterministic day+month-without-year detector (SK/RU month forms and common short forms);
  - added `_resolve_delivery_date(...)` guardrail:
    - anchors such inputs to `issue_date.year`,
    - corrects mismatched LLM year when month/day match but year drifts,
    - fails loud on inconsistent day/month mismatch between user input and LLM payload.
  - wired preview build flow to use the new guardrail and clear state on fail-loud date inconsistency.
- `tests/test_invoice_phase2_ai_layer.py`:
  - added regression tests for:
    - `4 апреля` → `2026-04-04`,
    - `4 apríla` → `2026-04-04`,
    - mixed voice-like multilingual input without year,
    - explicit year input remains respected.

### Constraints preserved
- Deterministic Python remains source of truth for final invoice draft normalization.
- No schema changes.
- No hidden auto-fix outside deterministic date anchoring rules.

---

## 2026-04-11 — Session 014 — PDF row alignment + supplier VAT wording follow-up

### Goal
Polish two remaining PDF output seams without redesign:
- visually align item description with numeric columns in item rows;
- improve supplier VAT fallback wording when supplier is not VAT registered.

### Changes
- `bot/services/pdf_generator.py`:
  - added `_item_row_description_first_baseline(...)` and used it for item description drawing so single-line descriptions share baseline alignment with quantity/unit/unit-price/total columns, while wrapped descriptions stay centered in the row block;
  - extracted `_format_supplier_ic_dph_line(...)` and changed supplier fallback from `IČ DPH: -` to `IČ DPH: Nie je platiteľ DPH`.
- `tests/test_pdf_generator_layout_wrapping.py`:
  - added regression checks for description baseline behavior (single-line parity with numeric baseline and wrapped text staying inside row bounds);
  - added regression checks for supplier VAT fallback wording.

### Constraints preserved
- No PDF redesign.
- Amount semantics in preview/save/PDF path unchanged.
- Current preview/save flow unchanged.

---

## 2026-04-11 — Session 013 — Invoice service display title regression guard

### Goal
Fix invoice runtime regression where service display title could fall back to raw multilingual text despite existing supplier alias mapping under a deterministic related form.

### Regression shape
- Raw item input: `ремонт`
- Internal canonical term: `oprava`
- Supplier alias stored only as: `opravy -> <full Slovak display title>`
- Previous runtime checked only raw alias key and then fell back to raw text in preview/PDF.

### Root cause
Cross-layer bridge was incomplete: internal canonicalization and supplier alias mapping are separate deterministic layers, but invoice runtime used only raw `service_short_name` for final alias lookup.

### Decision
Keep supplier alias mapping as source of truth for final preview/PDF title and implement deterministic, explicit lookup cascade in invoice handler:
1. raw alias (`service_short_name`)
2. canonical internal term alias (`service_term_internal`)
3. deterministic bridge forms (`oprava -> opravy`)
4. raw fallback as last resort

No fuzzy search, no LLM, no DB/schema changes, no auto-creation of aliases.

### Safeguard
Added regression tests to lock behavior:
- bridge-form resolution (`ремонт -> oprava -> opravy`)
- raw alias priority over fallback stages
- raw fallback when no deterministic alias matches

---


Р В РІР‚вЂњР РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р В Р’В°Р В Р’В» Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР РЋРЎвЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ.
Р В Р’В¤Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В Р’Вµ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’Вµ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРЎвЂњ Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРЎвЂњ, Р В Р’В° Р В РІвЂћвЂ“ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРЎвЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р РЋР Р‰, Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ, scope Р РЋРІР‚С™Р В Р’В° Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚В Р В Р’ВµР В РЎвЂ”Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.

---

## 2026-04-06 вЂ” Session 012 вЂ” PDF wrapping polish (items + identity blocks + Slovak glyph coverage)

### Р¦С–Р»СЊ

Р—Р°РєСЂРёС‚Рё Р·Р°Р»РёС€РєРѕРІС– seam-Рё PDF СЂРµРЅРґРµСЂР° Р±РµР· СЂРµРґРёР·Р°Р№РЅСѓ:
- РїРµСЂРµРЅРѕСЃ РґРѕРІРіРёС… РЅР°Р·РІ РїРѕР·РёС†С–Р№ Сѓ С‚Р°Р±Р»РёС†С–;
- РґРёРЅР°РјС–С‡РЅС– РІРёСЃРѕС‚Рё СЂСЏРґРєС–РІ/identity block-С–РІ;
- СЃС‚Р°Р±С–Р»СЊРЅРёР№ СЂРµРЅРґРµСЂ СЃР»РѕРІР°С†СЊРєРёС… СЃРёРјРІРѕР»С–РІ (РІРєР»СЋС‡РЅРѕ Р· `Дѕ`, `ЕҐ`) Сѓ РїСЂР°РєС‚РёС‡РЅРёС… С‚РµРєСЃС‚Р°С….

### Р©Рѕ Р·РјС–РЅРµРЅРѕ

- `bot/services/pdf_generator.py`:
  - РґРѕРґР°РЅРѕ helper `_wrap_text_lines(...)` РЅР° Р±Р°Р·С– `pdfmetrics.stringWidth(...)` РґР»СЏ word-wrap РІ РѕР±РјРµР¶РµРЅС–Р№ С€РёСЂРёРЅС–;
  - РґРѕРґР°РЅРѕ helper `_measure_party_block_height(...)` РґР»СЏ СЂРѕР·СЂР°С…СѓРЅРєСѓ РґРёРЅР°РјС–С‡РЅРѕС— РІРёСЃРѕС‚Рё identity block;
  - `_draw_party_block(...)` РѕРЅРѕРІР»РµРЅРѕ:
    - РїС–РґС‚СЂРёРјСѓС” wrapped multi-line lines,
    - РїРѕРІРµСЂС‚Р°С” С„Р°РєС‚РёС‡РЅСѓ РІРёСЃРѕС‚Сѓ Р±Р»РѕРєСѓ;
  - СЃРµРєС†С–СЋ `DodГЎvateДѕ` / `OdberateДѕ` РїРµСЂРµРІРµРґРµРЅРѕ РЅР° СЃРїС–Р»СЊРЅРёР№ baseline:
    - РЅРёР¶РЅСЏ РјРµР¶Р° РЅР°СЃС‚СѓРїРЅРѕРіРѕ Р±Р»РѕРєСѓ СЂР°С…СѓС”С‚СЊСЃСЏ РІС–Рґ `max(height_left, height_right)`,
    - РїСЂРёР±СЂР°РЅРѕ СЂРёР·РёРє РІС–Р·СѓР°Р»СЊРЅРѕРіРѕ overlap РјС–Р¶ Р±Р»РѕРєР°РјРё;
  - items table РѕРЅРѕРІР»РµРЅРѕ:
    - `poloЕѕka` РїРµСЂРµРЅРѕСЃРёС‚СЊСЃСЏ РїРѕ СЃР»РѕРІР°С… РІ РјРµР¶Р°С… РєРѕР»РѕРЅРєРё,
    - РІРёСЃРѕС‚Р° row РґРёРЅР°РјС–С‡РЅРѕ Р·СЂРѕСЃС‚Р°С” РїСЂРё 2+ СЂСЏРґРєР°С… РѕРїРёСЃСѓ,
    - С‡РёСЃР»РѕРІС– РєРѕР»РѕРЅРєРё (`mnoЕѕstvo`, `m.j.`, `cena za m.j.`, `spolu`) Р·Р°Р»РёС€РµРЅС– С„С–РєСЃРѕРІР°РЅРёРјРё С‚Р° РІРµСЂС‚РёРєР°Р»СЊРЅРѕ РІРёСЂС–РІРЅСЏРЅС– РїРѕ С†РµРЅС‚СЂСѓ СЂСЏРґРєР°.
- РґРѕРґР°РЅРѕ regression-С‚РµСЃС‚Рё `tests/test_pdf_generator_layout_wrapping.py`:
  - РїРµСЂРµРІС–СЂРєР°, С‰Рѕ РґРѕРІРіРёР№ description СЂРµР°Р»СЊРЅРѕ СЂРѕР·Р±РёРІР°С”С‚СЊСЃСЏ РЅР° РєС–Р»СЊРєР° СЂСЏРґРєС–РІ;
  - РїРµСЂРµРІС–СЂРєР°, С‰Рѕ РІРёСЃРѕС‚Р° identity block Р·Р±С–Р»СЊС€СѓС”С‚СЊСЃСЏ РґР»СЏ РґРѕРІРіРѕС— Р°РґСЂРµСЃРё.

### Р РµР·СѓР»СЊС‚Р°С‚

- РґРѕРІРіС– РЅР°Р·РІРё РїРѕР·РёС†С–Р№ Р±С–Р»СЊС€Рµ РЅРµ РІвЂ™С—Р¶РґР¶Р°СЋС‚СЊ Сѓ РєРѕР»РѕРЅРєСѓ `mnoЕѕstvo`;
- Р°РґСЂРµСЃРЅС– СЂСЏРґРєРё РІ `DodГЎvateДѕ`/`OdberateДѕ` РїРµСЂРµРЅРѕСЃСЏС‚СЊСЃСЏ РІ РјРµР¶Р°С… Р±Р»РѕРєСѓ;
- РІРёСЃРѕС‚Рё Р±Р»РѕРєС–РІ С– СЂСЏРґРєС–РІ Р°РґР°РїС‚РёРІРЅС–, Р±РµР· Р·РјС–РЅРё Р·Р°РіР°Р»СЊРЅРѕС— СЃС‚СЂСѓРєС‚СѓСЂРё one-page invoice;
- Unicode TTF С€Р»СЏС… С‡РµСЂРµР· ReportLab (`Vera.ttf`, `VeraBd.ttf`) Р»РёС€Р°С”С‚СЊСЃСЏ Р±Р°Р·РѕРІРёРј РјРµС…Р°РЅС–Р·РјРѕРј СЂРµРЅРґРµСЂР° СЃР»РѕРІР°С†СЊРєРёС… РґС–Р°РєСЂРёС‚РёРє.

---

## 2026-04-06 вЂ” Session 011 вЂ” PDF polish (Unicode font + payment block spacing)
## 2026-04-06 РІР‚вЂќ Session 011 РІР‚вЂќ PDF polish (Unicode font + payment block spacing)

### Р В¦РЎвЂ“Р В»РЎРЉ

Р вЂ™Р С‘Р С—РЎР‚Р В°Р Р†Р С‘РЎвЂљР С‘ Р В°РЎР‚РЎвЂљР ВµРЎвЂћР В°Р С”РЎвЂљР С‘ Р Р† PDF-РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚РЎвЂ“ Р В±Р ВµР В· РЎР‚Р ВµР Т‘Р С‘Р В·Р В°Р в„–Р Р…РЎС“: РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”РЎвЂ“ Р Т‘РЎвЂ“Р В°Р С”РЎР‚Р С‘РЎвЂљР С‘Р С”Р С‘, РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…РЎвЂ“РЎРѓРЎвЂљРЎРЉ payment Р В±Р В»Р С•Р С”РЎС“ РЎвЂљР В° Р С”Р С•Р Р…РЎРѓР С‘РЎРѓРЎвЂљР ВµР Р…РЎвЂљР Р…РЎвЂ“РЎРѓРЎвЂљРЎРЉ РЎвЂћРЎвЂ“Р Р…Р В°Р В»РЎРЉР Р…Р С•РЎвЂ” Р Р…Р В°Р В·Р Р†Р С‘ Р С—Р С•Р В·Р С‘РЎвЂ РЎвЂ“РЎвЂ”.

### Р В©Р С• Р В·Р СРЎвЂ“Р Р…Р ВµР Р…Р С•

- `bot/services/pdf_generator.py`:
  - Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎР‚Р ВµРЎвЂќРЎРѓРЎвЂљРЎР‚Р В°РЎвЂ РЎвЂ“РЎР‹ Unicode TTF-РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљРЎвЂ“Р Р† РЎвЂЎР ВµРЎР‚Р ВµР В· ReportLab (`Vera.ttf`, `VeraBd.ttf` РЎвЂ“Р В· Р С—Р В°Р С”Р ВµРЎвЂљР В° `reportlab`);
  - РЎС“РЎРѓРЎвЂ“ Р Р†Р С‘Р Т‘Р С‘Р СРЎвЂ“ РЎвЂљР ВµР С”РЎРѓРЎвЂљР С•Р Р†РЎвЂ“ `setFont(...)` Р С—Р ВµРЎР‚Р ВµР Р†Р ВµР Т‘Р ВµР Р…РЎвЂ“ Р Р…Р В° РЎвЂ РЎвЂ“ РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР С‘ (Р В·Р В°Р СРЎвЂ“РЎРѓРЎвЂљРЎРЉ Helvetica), РЎвЂ°Р С•Р В± Р С”Р С•РЎР‚Р ВµР С”РЎвЂљР Р…Р С• РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚Р С‘РЎвЂљР С‘ РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”РЎвЂ“ РЎРѓР С‘Р СР Р†Р С•Р В»Р С‘;
  - payment block Р С—Р ВµРЎР‚Р ВµРЎР‚Р С•Р В±Р В»Р ВµР Р…Р С• РЎС“ Р В±РЎвЂ“Р В»РЎРЉРЎв‚¬ РЎвЂЎР С‘РЎвЂљР В°Р В±Р ВµР В»РЎРЉР Р…Р С‘Р в„– stacked layout:
    - `IBAN` РЎвЂ“ `SWIFT/BIC` РЎС“ Р В»РЎвЂ“Р Р†РЎвЂ“Р в„– Р С”Р С•Р В»Р С•Р Р…РЎвЂ РЎвЂ“ Р Р…Р В° РЎР‚РЎвЂ“Р В·Р Р…Р С‘РЎвЂ¦ РЎР‚РЎРЏР Т‘Р С”Р В°РЎвЂ¦;
    - `SpР“Т‘sob Р“С”hrady` Р Р†Р С‘Р Р…Р ВµРЎРѓР ВµР Р…Р С• Р С•Р С”РЎР‚Р ВµР СР С• Р Р† Р С—РЎР‚Р В°Р Р†РЎС“ РЎвЂЎР В°РЎРѓРЎвЂљР С‘Р Р…РЎС“ Р В±Р ВµР В· Р С—Р ВµРЎР‚Р ВµРЎвЂљР С‘Р Р…РЎС“;
  - Р Р†Р С‘РЎРѓР С•РЎвЂљРЎС“ payment block Р В·Р В±РЎвЂ“Р В»РЎРЉРЎв‚¬Р ВµР Р…Р С• Р С—Р С•Р СРЎвЂ“РЎР‚Р Р…Р С• (`18mm` РІвЂ вЂ™ `24mm`) Р Т‘Р В»РЎРЏ РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…Р С•Р С–Р С• spacing.
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• regression-РЎвЂљР ВµРЎРѓРЎвЂљ `tests/test_invoice_service_item_normalized.py`:
  - Р С—Р ВµРЎР‚Р ВµР Р†РЎвЂ“РЎР‚РЎРЏРЎвЂќ, РЎвЂ°Р С• `description_normalized` РЎР‚Р ВµР В°Р В»РЎРЉР Р…Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† `invoice_item` РЎвЂ“ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С‘Р в„– Р Т‘Р В»РЎРЏ PDF/fallback Р В»Р С•Р С–РЎвЂ“Р С”Р С‘.

### Р В Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ

PDF Р В»Р С‘РЎв‚¬Р С‘Р Р†РЎРѓРЎРЏ Р Р† Р С—Р С•РЎвЂљР С•РЎвЂЎР Р…РЎвЂ“Р в„– РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ“ (Р В±Р ВµР В· major redesign), Р В°Р В»Р Вµ РЎРѓРЎвЂљР В°Р Р† РЎРѓРЎвЂљР В°Р В±РЎвЂ“Р В»РЎРЉР Р…РЎвЂ“РЎв‚¬Р С‘Р С Р Р† РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚РЎвЂ“:
- РЎРѓР В»Р С•Р Р†Р В°РЎвЂ РЎРЉР С”Р С‘Р в„– РЎвЂљР ВµР С”РЎРѓРЎвЂљ РЎР‚Р ВµР Р…Р Т‘Р ВµРЎР‚Р С‘РЎвЂљРЎРЉРЎРѓРЎРЏ Unicode-РЎв‚¬РЎР‚Р С‘РЎвЂћРЎвЂљР С•Р С;
- payment block Р Р…Р Вµ РЎРѓРЎвЂљР С‘Р С”Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р С—Р С• Р С—Р С•Р В»РЎРЏРЎвЂ¦;
- РЎвЂћРЎвЂ“Р Р…Р В°Р В»РЎРЉР Р…Р В° canonical Р Р…Р В°Р В·Р Р†Р В° Р С—Р С•Р В·Р С‘РЎвЂ РЎвЂ“РЎвЂ” Р В·Р В°Р В»Р С‘РЎв‚¬Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р В·Р В±Р ВµРЎР‚Р ВµР В¶Р ВµР Р…Р С•РЎР‹ Р Р† persistence-РЎв‚¬Р В°РЎР‚РЎвЂ“ Р Т‘Р В»РЎРЏ Р Р†Р С‘Р С”Р С•РЎР‚Р С‘РЎРѓРЎвЂљР В°Р Р…Р Р…РЎРЏ Р Р† PDF.

---

## 2026-04-06 РІР‚вЂќ Session 010 РІР‚вЂќ Optional SMTP in supplier onboarding/storage

### Р В¦РЎвЂ“Р В»РЎРЉ

Р вЂ”Р Р…РЎРЏРЎвЂљР С‘ Р В±Р В»Р С•Р С”РЎС“РЎР‹РЎвЂЎРЎС“ Р Р†Р С‘Р СР С•Р С–РЎС“ SMTP host/user/pass РЎС“ supplier onboarding Р Т‘Р В»РЎРЏ MVP, РЎвЂ°Р С•Р В± Р С—РЎР‚Р С•РЎвЂћРЎвЂ“Р В»РЎРЉ Р С—Р С•РЎРѓРЎвЂљР В°РЎвЂЎР В°Р В»РЎРЉР Р…Р С‘Р С”Р В° Р СР С•Р В¶Р Р…Р В° Р В±РЎС“Р В»Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂљР С‘ Р В±Р ВµР В· email-Р С”Р С•Р Р…РЎвЂћРЎвЂ“Р С–РЎС“РЎР‚Р В°РЎвЂ РЎвЂ“РЎвЂ”.

### Р В©Р С• Р В·Р СРЎвЂ“Р Р…Р ВµР Р…Р С•

- `supplier` schema Р Р† `bot/services/db.py` Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•: `smtp_host`, `smtp_user`, `smtp_pass` РЎвЂљР ВµР С—Р ВµРЎР‚ nullable (`TEXT` Р В±Р ВµР В· `NOT NULL`);
- `SupplierProfile` Р Р† `bot/services/supplier_service.py` Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С• Р Р…Р В° optional SMTP-Р С—Р С•Р В»РЎРЏ (`str | None`);
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·Р В°РЎвЂ РЎвЂ“РЎР‹ optional SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ РЎС“ service layer:
  - Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“/whitespace Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏ Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎР‹РЎвЂљРЎРЉРЎРѓРЎРЏ РЎРЏР С” `NULL`,
  - РЎвЂЎР С‘РЎвЂљР В°Р Р…Р Р…РЎРЏ РЎРѓРЎвЂљР В°РЎР‚Р С‘РЎвЂ¦ РЎР‚РЎРЏР Т‘Р С”РЎвЂ“Р Р† Р В· Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“Р СР С‘ SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏР СР С‘ Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·РЎС“РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Т‘Р С• `None`;
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎРЏР Р†Р Р…Р С‘Р в„– Р С”Р С•Р Р…РЎвЂљРЎР‚Р В°Р С”РЎвЂљ helper `SupplierService.has_complete_smtp_config(profile)`:
  - email send Р С—Р С•Р Р†Р С‘Р Р…Р ВµР Р… Р В·Р В°Р С—РЎС“РЎРѓР С”Р В°РЎвЂљР С‘РЎРѓРЎРЉ РЎвЂљРЎвЂ“Р В»РЎРЉР С”Р С‘ Р С”Р С•Р В»Р С‘ Р Р†РЎРѓРЎвЂ“ 3 SMTP Р С—Р С•Р В»РЎРЏ Р В·Р В°Р Т‘Р В°Р Р…РЎвЂ“;
- onboarding flow (`bot/handlers/onboarding.py`) Р С•Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С•:
  - SMTP Р С”РЎР‚Р С•Р С”Р С‘ Р СР В°РЎР‹РЎвЂљРЎРЉ РЎвЂљР ВµР С”РЎРѓРЎвЂљ `voliteР”С•nР“В©, "-" alebo /skip pre preskoР”РЊenie`,
  - `-`, `/skip` РЎвЂ“ Р С—Р С•РЎР‚Р С•Р В¶Р Р…РЎвЂ“ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р Р…РЎРЏ Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·РЎС“РЎР‹РЎвЂљРЎРЉРЎРѓРЎРЏ РЎРЏР С” `None`,
  - summary Р С—Р С•Р С”Р В°Р В·РЎС“РЎвЂќ `-` Р Т‘Р В»РЎРЏ Р Р†РЎвЂ“Р Т‘РЎРѓРЎС“РЎвЂљР Р…РЎвЂ“РЎвЂ¦ SMTP Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ.
- Р Т‘Р С•Р Т‘Р В°Р Р…Р С• РЎвЂљР ВµРЎРѓРЎвЂљР С‘ `tests/test_supplier_smtp_optional.py`:
  - save/load supplier Р В±Р ВµР В· SMTP;
  - save/load supplier Р В· SMTP;
  - Р Р…Р С•РЎР‚Р СР В°Р В»РЎвЂ“Р В·Р В°РЎвЂ РЎвЂ“РЎРЏ skip token/empty Р В·Р Р…Р В°РЎвЂЎР ВµР Р…РЎРЉ.

### Р В Р ВµР В·РЎС“Р В»РЎРЉРЎвЂљР В°РЎвЂљ

`/supplier` Р СР С•Р В¶Р Вµ Р В·Р В°Р Р†Р ВµРЎР‚РЎв‚¬Р С‘РЎвЂљР С‘РЎРѓРЎРЏ Р В±Р ВµР В· SMTP Р Р…Р В°Р В»Р В°РЎв‚¬РЎвЂљРЎС“Р Р†Р В°Р Р…РЎРЉ; Р С—РЎР‚Р С•РЎвЂћРЎвЂ“Р В»РЎРЉ РЎС“РЎРѓР С—РЎвЂ“РЎв‚¬Р Р…Р С• Р В·Р В±Р ВµРЎР‚РЎвЂ“Р С–Р В°РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ РЎвЂ“ Р Р†Р С‘Р С”Р С•РЎР‚Р С‘РЎРѓРЎвЂљР С•Р Р†РЎС“РЎвЂќРЎвЂљРЎРЉРЎРѓРЎРЏ Р Р† invoice/PDF flow Р В±Р ВµР В· Р В·Р СРЎвЂ“Р Р… Р С”РЎР‚Р С‘РЎвЂљР С‘РЎвЂЎР Р…Р С•Р С–Р С• MVP РЎв‚¬Р В»РЎРЏРЎвЂ¦РЎС“.

---

## 2026-04-06 РІР‚вЂќ Session 009 РІР‚вЂќ Service alias list cleanup (inactive hidden by default)
## 2026-04-06 Р Р†Р вЂљРІР‚Сњ Session 009 Р Р†Р вЂљРІР‚Сњ Service alias list cleanup (inactive hidden by default)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РЎСџР РЋР вЂљР В РЎвЂР В Р’В±Р РЋР вЂљР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚вЂњ alias mappings Р В Р’В·Р РЋРІР‚вЂњ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РўвЂР В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў `/service` Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂќР РЋРЎвЂњ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂ UX flow.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- `ServiceAliasService.list_mappings(...)` Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - default Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р РЋРІР‚С™Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В РЎвЂќР В РЎвЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂ (`is_active = 1`);
  - Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂўР В РЎвЂќ Р РЋР С“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В РЎвЂў (`canonical_title`, `alias`);
  - Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В РЎвЂ”Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `include_inactive=True` Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ;
- `/service` handler Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В РЎвЂР В Р вЂ Р РЋР С“Р РЋР РЏ Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂў Р В Р вЂ Р В РЎвЂР В РЎвЂќР В Р’В»Р В РЎвЂР В РЎвЂќР РЋРЎвЂњ Р РЋРІР‚вЂњ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’Вµ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ alias;
- Р РЋРІР‚С™Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В РЎвЂўР В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ `deactivate_mapping` Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р Р†Р вЂљРІвЂћСћР РЋР РЏР В Р вЂ Р В Р’В»Р РЋР РЏР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРЎвЂњ default list;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ alias Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  list;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В°, Р РЋРІР‚В°Р В РЎвЂў `resolve_alias` Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ alias;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В° `include_inactive=True`.

### Р В Р’В Р В Р’ВµР В Р’В·Р РЋРЎвЂњР В Р’В»Р РЋР Р‰Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™

Normal `/service` list Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР РЋРІР‚В¦Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ mappings, Р В Р’В° Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ invoice Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р В РўвЂР В Р’ВµР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚вЂњ alias.

---

## 2026-04-06 Р Р†Р вЂљРІР‚Сњ Session 008 Р Р†Р вЂљРІР‚Сњ Service alias Р Р†РІР‚В РІР‚в„ў canonical invoice title normalization

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РўвЂР В Р’ВµР РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ normalization layer Р В РўвЂР В Р’В»Р РЋР РЏ invoice item:
alias (Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В Р’В° spoken/text Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В°) Р Р†РІР‚В РІР‚в„ў canonical full title, Р В РЎвЂќР В Р’ВµР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В РЎвЂўР В РЎВ.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ persistence-Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР вЂ№ `supplier_service_alias`:
  - Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋР РЏ `id`, `supplier_id`, `alias`, `canonical_title`, `is_active`, `created_at`;
  - `alias` Р В Р’В· case-insensitive Р РЋРЎвЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р РЋР вЂ№ Р В Р вЂ  Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р РЋРІР‚В¦ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В° (`UNIQUE(supplier_id, alias)` + `COLLATE NOCASE`);
  - bootstrap/schema-check Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В Р вЂ  `init_db` Р В Р’В· fail-loud Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР В РўвЂР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂќР В РЎвЂўР РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ Р В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В¦Р В Р’ВµР В РЎВР РЋРІР‚вЂњ;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/service_alias_service.py`:
  - `create_mapping`,
  - `list_mappings`,
  - `resolve_alias` (exact + trimmed + case-insensitive),
  - `deactivate_mapping` (MVP-safe optional helper);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў supplier-side chat flow `/service` (`bot/handlers/supplier.py`):
  - Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂќР РЋРЎвЂњ alias mappings,
  - Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ 1: Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ alias,
  - Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ 2: Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ canonical title,
  - Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р В РЎвЂ”Р В РЎвЂР РЋР С“Р В РЎвЂўР В РЎвЂќ;
- invoice flow (`bot/handlers/invoice.py`) Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ `item_name_raw`,
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂ preview/save/PDF Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ deterministic alias resolution Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· Python/SQLite,
  - Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ match Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ canonical title Р РЋР РЏР В РЎвЂќ `item_name_final`,
  - Р В РЎвЂ”Р РЋР вЂљР В РЎвЂ miss Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ fallback Р В Р вЂ¦Р В Р’В° raw text;
- preview Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў: Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР РЋРІР‚Сњ `raw` Р РЋРІР‚вЂњ `finР вЂњР Р‹lna` Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р РЋРЎвЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ;
- save/PDF Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў:
  - Р РЋРЎвЂњ `invoice_item.description_normalized` Р В Р’В·Р В Р’В°Р В РЎвЂ”Р В РЎвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚С›Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р В Р’В° (canonical Р В Р’В°Р В Р’В±Р В РЎвЂў fallback raw),
  - PDF Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚Сњ Р РЋРІР‚С›Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРЎвЂњ Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ Р РЋРЎвЂњ (`description_normalized` Р В Р’В· fallback Р В Р вЂ¦Р В Р’В° `description_raw`);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С™Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ `tests/test_service_alias_service.py`:
  - alias resolution success,
  - fallback when alias not found,
  - case-insensitive + trimmed match.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- fuzzy matching;
- auto-canonicalization Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· LLM;
- Р РЋР С“Р В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ admin/settings UI Р В РўвЂР В Р’В»Р РЋР РЏ mappings.

### Р В Р’В Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

Final service/item title Р В РўвЂР В Р’В»Р РЋР РЏ invoice preview/save/PDF Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р В Р вЂ Р В РЎвЂР В Р’В·Р В Р вЂ¦Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’ВµР РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў
Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· supplier-defined mapping Р РЋРЎвЂњ Python/storage, Р В Р’В° Р В Р вЂ¦Р В Р’Вµ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· LLM paraphrasing.

---

## 2026-04-03 Р Р†Р вЂљРІР‚Сњ Session 007 Р Р†Р вЂљРІР‚Сњ Phase 4: invoice draft Р Р†РІР‚В РІР‚в„ў confirm Р Р†РІР‚В РІР‚в„ў PDF preview

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ invoice flow Р В РўвЂР В Р’В»Р РЋР РЏ text/voice input:
draft Р Р†РІР‚В РІР‚в„ў local contact resolution Р Р†РІР‚В РІР‚в„ў preview Р Р†РІР‚В РІР‚в„ў confirm Р Р†РІР‚В РІР‚в„ў save Р Р†РІР‚В РІР‚в„ў PDF preview.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў persistence Р В РўвЂР В Р’В»Р РЋР РЏ faktР вЂњРЎвЂќr:
  - Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР РЏ `invoice`,
  - Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р РЋР РЏ `invoice_item`,
  - fail-loud schema compatibility checks Р В Р’В±Р В Р’ВµР В Р’В· auto-drop;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/invoice_service.py`:
  - Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР В РЎВР В Р’ВµР РЋР вЂљР РЋРЎвЂњ `RRRRNNNN`,
  - save faktР вЂњРЎвЂќry Р В Р’В· Р В РЎвЂўР В РўвЂР В Р вЂ¦Р В РЎвЂР В РЎВ Р РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂќР В РЎвЂўР В РЎВ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ,
  - get by id/number,
  - save `pdf_path`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/pdf_generator.py` (reportlab + qrcode):
  - one-page business invoice layout,
  - DodР вЂњР Р‹vateР вЂќРЎвЂў/OdberateР вЂќРЎвЂў block,
  - meta/dates block,
  - payment block,
  - items table,
  - strong `Na Р вЂњРЎвЂќhradu` block,
  - QR block;
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/invoice.py`:
  - `/invoice` text entry point,
  - preview Р РЋР С“Р В Р’В»Р В РЎвЂўР В Р вЂ Р В Р’В°Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂќР В РЎвЂўР РЋР вЂ№,
  - confirm (`ano`/`nie`),
  - PDF decision step (`schvР вЂњР Р‹liР вЂўРўС’`/`upraviР вЂўРўС’`);
- voice flow Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРЎвЂњ Р РЋРІР‚С™Р В РЎвЂўР В РІвЂћвЂ“ Р РЋР С“Р В Р’В°Р В РЎВР В РЎвЂР В РІвЂћвЂ“ invoice path:
  - STT text Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ Р В РЎвЂўР В Р’В±Р РЋР вЂљР В РЎвЂўР В Р’В±Р В Р’В»Р РЋР РЏР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· Р РЋР С“Р В РЎвЂ”Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Phase 4 flow;
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў local contact-only resolution:
  - exact match,
  - case-insensitive exact match;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў date semantics Р В Р вЂ  Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРІР‚вЂњ:
  - `issue_date` = auto today,
  - Р В РўвЂР В Р’В°Р РЋРІР‚С™Р В Р’В° Р В Р’В· input Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ `delivery_date`,
  - Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋР РЏ Р Р†Р вЂљРІР‚Сњ `delivery_date = issue_date`,
  - `due_date = issue_date + due_days`.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- email send;
- external lookup / FinStat;
- contract extraction;
- fuzzy matching;
- multi-item UI;
- advanced edit workflow;
- migration framework.

### Follow-up note (QR scope honesty)

- Phase 4 merge Р В Р вЂ¦Р В Р’Вµ Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· QR subsystem.
- Р В РЎСџР В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ QR block Р РЋРЎвЂњ PDF Р В Р вЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РЎВ placeholder-Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ Р В РўвЂР В Р’В»Р РЋР РЏ payment QR.
- Р В РЎвЂєР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќ:
  - Р В РўвЂР В РЎвЂўР РЋР С“Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В РЎвЂР РЋРІР‚С™Р В РЎвЂ/Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В¶Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Pay by Square payload generator;
  - Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р РЋР Р‰ payload Р РЋРІР‚вЂњР В Р’В· Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВ Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ.

---


## 2026-04-03 Р Р†Р вЂљРІР‚Сњ Session 006 Р Р†Р вЂљРІР‚Сњ PDF Layout Spec (docs-only)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРЎвЂњ docs-only Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р В Р вЂ Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ PDF-Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р’В°.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р В РўвЂР В РЎвЂўР В РЎвЂќР РЋРЎвЂњР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™ `docs/FakturaBot_PDF_Layout_Spec.md`;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў purpose PDF Р РЋР РЏР В РЎвЂќ Р РЋРІР‚РЋР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В РЎвЂ wow-Р В Р’ВµР РЋРІР‚С›Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ;
- Р В РЎвЂўР В РЎвЂ”Р В РЎвЂР РЋР С“Р В Р’В°Р В Р вЂ¦Р В РЎвЂў design principles (clean, restrained, readability-first);
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў color principles Р В Р’В· Р В Р вЂ Р В РЎвЂР В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР РЋР вЂ№ Р В РўвЂР В Р вЂ Р В РЎвЂўР РЋРІР‚В¦ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР РЋРІР‚СњР В РЎВР В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ Р РЋРІР‚С›Р В РЎвЂўР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В¦ Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ¦Р РЋРІР‚вЂњР В Р вЂ  Р В Р’В±Р В Р’ВµР В Р’В· Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРІР‚С™Р В Р’В°Р В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ;
- Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂўР В РЎвЂќ Р В РЎвЂўР В Р’В±Р В РЎвЂўР В Р вЂ Р Р†Р вЂљРІвЂћСћР РЋР РЏР В Р’В·Р В РЎвЂќР В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В¦ layout-Р В Р’В±Р В Р’В»Р В РЎвЂўР В РЎвЂќР РЋРІР‚вЂњР В Р вЂ :
  header, DodР вЂњР Р‹vateР вЂќРЎвЂў/OdberateР вЂќРЎвЂў, meta/dates, payment, items table, total, QR, footer;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў date semantics Р В РўвЂР В Р’В»Р РЋР РЏ `DР вЂњР Р‹tum vystavenia`, `DР вЂњР Р‹tum dodania`, `DР вЂњР Р‹tum splatnosti`;
- Р В Р’В·Р В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў preview/approval rule (`schvР вЂњР Р‹liР вЂўРўС’` / `upraviР вЂўРўС’`);
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў typography/spacing guidelines Р РЋРІР‚С™Р В Р’В° Р РЋР С“Р В Р’ВµР В РЎвЂќР РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р Р†Р вЂљРЎС™Do notР Р†Р вЂљРЎСљ.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ Р РЋР С“Р РЋР РЏ PDF generator;
- Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋР вЂ№Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂўР РЋР С“Р РЋР РЏ Р В РЎС›Р В РІР‚вЂќ;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋРІР‚С›Р РЋРІР‚вЂњР РЋРІР‚РЋР РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В Р’В° Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р В РЎВР В РЎвЂ layout specification.

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 004 Р Р†Р вЂљРІР‚Сњ Phase 2: supplier onboarding (chat-based)

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding Р В Р’В±Р В Р’ВµР В Р’В· fancy UI, Р В Р’В±Р В Р’ВµР В Р’В· Р РЋР С“Р В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ FSM-Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ,
Р РЋР РЏР В РЎвЂќ Р В Р’В±Р В Р’В°Р В Р’В·Р РЋРЎвЂњ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ invoice phases.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў SQLite schema `supplier` Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В°;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/supplier_service.py` Р В Р’В· Р В РЎвЂўР В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏР В РЎВР В РЎвЂ:
  - create or replace profile,
  - get by `telegram_id`,
  - update profile (Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· upsert);
- Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/onboarding.py` Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ chat flow:
  12 Р В РЎвЂ”Р В РЎвЂўР В Р’В»Р РЋРІР‚вЂњР В Р вЂ  Р Р†РІР‚В РІР‚в„ў summary Р Р†РІР‚В РІР‚в„ў confirm (`yes/no`) Р Р†РІР‚В РІР‚в„ў save;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў MVP-Р РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р’ВµР В Р вЂ¦Р РЋР Р‰ Р В Р вЂ Р В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В РўвЂР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РўвЂР В Р’В»Р РЋР РЏ IР вЂќР Р‰O/DIР вЂќР Р‰/IР вЂќР Р‰ DPH/email/IBAN/days_due;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў UX-Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ, Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р РЋРЎвЂњР В Р’В¶Р В Р’Вµ Р РЋРІР‚вЂњР РЋР С“Р В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚Сњ, Р В Р’В· Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚СњР РЋР вЂ№ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РІвЂћвЂ“Р РЋРІР‚С™Р В РЎвЂ flow Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р вЂ¦Р В РЎвЂў.

### Р В РІР‚ВР В Р’ВµР В Р’В·Р В РЎвЂ”Р В Р’ВµР В РЎвЂќР В Р’В° / Р В РЎвЂўР В Р’В±Р В РЎВР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ

- SMTP Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР Р‰ Р В Р вЂ¦Р В Р’Вµ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ;
- Р РЋРЎвЂњ summary Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР Р‰ Р В РЎВР В Р’В°Р РЋР С“Р В РЎвЂќР РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ (`********`);
- Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ SMTP Р В РЎвЂ”Р В Р’В°Р РЋР вЂљР В РЎвЂўР В Р’В»Р РЋР РЏ Р В Р вЂ  Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р РЋРІР‚вЂњ Р В Р’В»Р В РЎвЂР РЋРІвЂљВ¬Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ plain-text Р РЋРЎвЂњ SQLite (Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂў, Р В РўвЂР В Р’В»Р РЋР РЏ MVP);
- production-grade secure credential storage Р РЋРІР‚В°Р В Р’Вµ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- contact onboarding;
- invoice save flow;
- PDF/email send;
- contract extraction;
- lookup API;
- Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ settings center.

### Р В Р’В Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

Phase 2 Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В° Р РЋРІР‚С™Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р’В° Р В Р вЂ  Р В РЎВР В Р’ВµР В Р’В¶Р В Р’В°Р РЋРІР‚В¦ simple chat-based supplier onboarding.
Fancy UI Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў.
Supplier profile Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ  Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РЎВ persistence-Р РЋРІвЂљВ¬Р В Р’В°Р РЋР вЂљР В РЎвЂўР В РЎВ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ invoice phases.

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 003 Р Р†Р вЂљРІР‚Сњ Phase 1: voice-to-draft preview flow

### Р В Р’В¦Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰

Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ wow-flow: Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“ Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў AI draft preview Р В Р вЂ  Р РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р РЋРІР‚вЂњ.
Р В РІР‚ВР В Р’ВµР В Р’В· save Р В Р вЂ  Р В РІР‚ВР В РІР‚Сњ, Р В Р’В±Р В Р’ВµР В Р’В· PDF, Р В Р’В±Р В Р’ВµР В Р’В· email, Р В Р’В±Р В Р’ВµР В Р’В· supplier/contact persistence.

### Р В Р’В©Р В РЎвЂў Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў

- `bot/services/speech_to_text.py` Р Р†Р вЂљРІР‚Сњ STT Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· OpenAI Audio API (Whisper)
- `bot/services/llm_invoice_parser.py` Р Р†Р вЂљРІР‚Сњ LLM draft parsing Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· OpenAI Chat API
- `bot/handlers/voice.py` Р Р†Р вЂљРІР‚Сњ voice message handler: download Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў parse Р Р†РІР‚В РІР‚в„ў preview
- `prompts/invoice_draft_prompt.txt` Р Р†Р вЂљРІР‚Сњ Р РЋР С“Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’ВµР В РЎВР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎВР В РЎвЂ”Р РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ Р В РЎвЂР РЋРІР‚С™Р РЋР РЏР В РЎвЂ“Р РЋРЎвЂњ invoice draft
- `bot/config.py` Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `openai_stt_model`, `openai_llm_model`
- `bot/main.py` Р Р†Р вЂљРІР‚Сњ config Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  polling workflow data
- `requirements.txt` Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `openai>=1.30`

### Р В РЎвЂ™Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р вЂ¦Р РЋРІР‚вЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ

- STT Р РЋРІР‚вЂњ LLM parsing Р Р†Р вЂљРІР‚Сњ Р В РўвЂР В Р вЂ Р В Р’В° Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРІР‚вЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р РЋРІР‚вЂњР РЋР С“Р В РЎвЂ, Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В»Р В РЎвЂР РЋРІР‚С™Р РЋРІР‚вЂњ Р В Р вЂ  Р В РЎвЂўР В РўвЂР В РЎвЂР В Р вЂ¦
- Р РЋРІР‚С™Р В РЎвЂР В РЎВР РЋРІР‚РЋР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋРІР‚С›Р В Р’В°Р В РІвЂћвЂ“Р В Р’В»Р В РЎвЂ Р В Р вЂ Р В РЎвЂР В РўвЂР В Р’В°Р В Р’В»Р РЋР РЏР РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РЎвЂўР В РўвЂР РЋР вЂљР В Р’В°Р В Р’В·Р РЋРЎвЂњ Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р В РЎвЂўР В Р’В±Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂќР В РЎвЂ (try/finally)
- Р РЋР РЏР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў `OPENAI_API_KEY` Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР РЋР С“Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р Р†Р вЂљРІР‚Сњ app Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚Сњ Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂў, voice handler
  Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚Сњ Р В Р’В·Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР В Р’В»Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В±Р В Р’ВµР В Р’В· Р В РЎвЂ”Р В Р’В°Р В РўвЂР РЋРІР‚вЂњР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ
- graceful error handling Р В РўвЂР В Р’В»Р РЋР РЏ STT Р РЋРІР‚вЂњ LLM failure Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂў

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- save draft Р РЋРЎвЂњ Р В РІР‚ВР В РІР‚Сњ
- PDF Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ
- email
- supplier/contact persistence
- contract extraction
- FSM / multi-step dialog

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Phase 2: Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding (chat-based, sequential)

---

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 002 Р Р†Р вЂљРІР‚Сњ Phase 0 implementation skeleton

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- docs bootstrap Р В Р вЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РЎВ;
- Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ  Phase 0 implementation skeleton;
- Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ deploy Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў;
- Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р Р†Р вЂљРІР‚Сњ Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В Р’В»Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ runnable Р В РЎвЂќР В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р РЋР С“ Р В Р’В±Р В Р’ВµР В Р’В· feature-Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР РЋРЎвЂњ `bot/`, `prompts/`, `storage/`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `config.py` Р В Р’В· Р РЋРІР‚РЋР В РЎвЂР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏР В РЎВ `.env`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў SQLite bootstrap Р В Р’В· Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂќР В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂ№ Р РЋРІР‚С™Р В Р’В°Р В Р’В±Р В Р’В»Р В РЎвЂР РЋРІР‚В Р В Р’ВµР РЋР вЂ№ `supplier`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ `/start` handler Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В°Р В РЎвЂ”Р РЋРЎвЂњР РЋР С“Р В РЎвЂќ aiogram polling;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `.env.example`, `requirements.txt`, `Dockerfile`, `docker-compose.yml`.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ voice / Whisper / LLM draft / PDF / email / contract extraction;
- Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ Р РЋР С“Р РЋР РЏ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ deploy;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ internet lookup, SaaS/multi-tenant Р В Р’В°Р В Р’В±Р В РЎвЂў Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІвЂљВ¬Р РЋРІР‚вЂњ Р В РЎВР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р РЋРІР‚вЂњ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В Р’В° Phase 0.

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Р В Р вЂ¦Р В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р Р†Р вЂљРІР‚Сњ Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ voice/draft flow;
- Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р Р†Р вЂљРІР‚Сњ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ onboarding Р РЋРІР‚С™Р В Р’В° contacts Р РЋРЎвЂњ chat-based Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р’В»Р РЋРІР‚вЂњ.

---

## 2026-03-30 Р Р†Р вЂљРІР‚Сњ Session 001 Р Р†Р вЂљРІР‚Сњ Р В РЎв„ўР В РЎвЂўР В Р вЂ¦Р РЋРІР‚В Р В Р’ВµР В РЎвЂ”Р РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р В РЎСџР В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚В Р РЋРІР‚вЂњР В Р вЂ¦Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РЎВР В Р’В°Р РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ SaaS Р В Р вЂ¦Р В Р’В° Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРІР‚вЂњ Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В РЎвЂР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂў.
- Р В РЎСџР В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р РЋР С“ Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР С“Р В Р’В°Р В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В Р’В°.
- FakturaBot Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В Р’В»Р РЋР РЏР В РўвЂР В Р’В°Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В Р’В° Р В РўвЂР В Р’ВµР В РЎВР В РЎвЂўР В Р вЂ¦Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р РЋРІР‚вЂњР РЋРІР‚С™Р РЋР вЂљР В РЎвЂР В Р вЂ¦Р В Р’В°.
- Р В РЎСџР РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™ Р В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ Р РЋРІР‚РЋР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В Р’В° Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚вЂќ Р В РЎВР В РЎвЂўР В РўвЂР В Р’ВµР В Р’В»Р РЋРІР‚вЂњ:
  Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ“Р В РЎвЂўР РЋР вЂљР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р РЋРІР‚вЂњР В Р вЂ  Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р В Р’В·Р В Р’В°Р В РўвЂР В Р’В°Р РЋРІР‚РЋР РЋРІР‚вЂњ Р В РЎВР В Р’В°Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р’В±Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРЎвЂњ.

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР В РЎвЂР РЋРІР‚С™Р РЋР Р‰ Р РЋРЎвЂњ MVP v1.0

- Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™
- Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР В РІвЂћвЂ“
- Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР В РІвЂћвЂ“
- Whisper STT
- AI invoice draft
- Р РЋР вЂљР РЋРЎвЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding
- Р РЋР вЂљР РЋРЎвЂњР РЋРІР‚РЋР В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В°
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В Р’В° Р В Р’В· Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРЎвЂњ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· AI
- Р В Р’В»Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В Р’В°Р В РўвЂР РЋР вЂљР В Р’ВµР РЋР С“Р В Р вЂ¦Р В Р’В° Р В РЎвЂќР В Р вЂ¦Р В РЎвЂР В РЎвЂ“Р В Р’В°
- Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂўР РЋР вЂљР В РЎвЂР В РЎвЂ“Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’В°Р В Р’В»Р РЋРЎвЂњ Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРЎвЂњ
- PDF-Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р’В°
- QR Pay by Square
- email-Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В РЎвЂќР В Р’В°
- Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљ
- Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“Р В РЎвЂ
- SQLite
- Docker deploy

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў

- lookup Р В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРІР‚С™Р РЋР вЂљР В Р’В°Р В РЎвЂ“Р В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р РЋРІР‚вЂњР В Р вЂ  Р В Р’В· Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™Р РЋРЎвЂњ
- FinStat
- ORSR Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ
- Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ OCR pipeline
- Google Drive
- billing
- multi-tenant Р В Р’В°Р РЋР вЂљР РЋРІР‚В¦Р РЋРІР‚вЂњР РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В Р’В°
- Р В РЎвЂќР В Р’В°Р В Р’В±Р РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’В°

### Р В РЎв„ўР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В РЎвЂўР В Р вЂ Р РЋРІР‚вЂњ Р РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В РЎвЂ”Р В РЎвЂў AI

- AI Р В Р вЂ¦Р В Р’Вµ Р РЋРІР‚Сњ Р В РўвЂР В Р’В¶Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В»Р В РЎвЂўР В РЎВ Р РЋРІР‚вЂњР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р вЂ¦Р В РЎвЂ.
- Р В Р в‚¬Р РЋР С“Р РЋРІР‚вЂњ Р В РЎвЂќР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р РЋРІР‚вЂњ Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР РЋРІР‚вЂќ Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋР вЂ№Р РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰ Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· draft + validation + confirmation.
- Р В РІР‚СњР В Р’В»Р РЋР РЏ Р В РўвЂР В РЎвЂўР В РЎвЂ“Р В РЎвЂўР В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР В Р вЂ  Р В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎВР В РЎвЂўР В РўвЂР В Р’ВµР В Р’В»Р РЋР Р‰:
  Python orchestrates Р Р†РІР‚В РІР‚в„ў AI extracts Р Р†РІР‚В РІР‚в„ў Python validates Р Р†РІР‚В РІР‚в„ў user confirms.
- AI Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В РўвЂР В Р’В»Р РЋР РЏ Р В Р вЂ¦Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р В Р’В¶Р В РЎвЂР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РўвЂР В РЎвЂР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р В Р’В° Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂќР В РЎвЂР РЋРІР‚В¦ Р В Р вЂ¦Р В Р’В°Р В Р’В·Р В Р вЂ  Р РЋР вЂљР В РЎвЂўР В Р’В±Р РЋРІР‚вЂњР РЋРІР‚С™.

### Р В РЎСџР РЋР вЂљР В РЎвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂ Р В Р вЂ Р В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋР С“Р РЋРІР‚В Р В Р’ВµР В Р вЂ¦Р В Р’В°Р РЋР вЂљР РЋРІР‚вЂњР РЋР вЂ№

Р В РІР‚СљР В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ input Р РЋРІР‚С™Р В РЎвЂР В РЎвЂ”Р РЋРЎвЂњ:
Р Р†Р вЂљРЎС™Р В РЎС›Р В Р’ВµР РЋР С“Р В Р’В»Р В Р’В° Р В Р Р‹Р В Р’В»Р В РЎвЂўР В Р вЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚вЂњР РЋР РЏ Р В Р’В·Р В Р’В° Р В РЎвЂўР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В РЎвЂ Р В РЎвЂўР В РўвЂР В РЎвЂР В Р вЂ¦ Р В РЎвЂќР РЋРЎвЂњР РЋР С“ Р РЋРІР‚С™Р В Р’В°Р В РЎВ 2000 Р РЋРІР‚СњР В Р вЂ Р РЋР вЂљ, Р В РўвЂР В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР В РЎВ Р В Р вЂ Р В РЎвЂР РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ 30 Р В РЎВР В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В Р’В° 2026, Р РЋР С“Р В РЎвЂ”Р В Р’В»Р В Р’В°Р РЋРІР‚С™Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™ 30 Р В РўвЂР В Р вЂ¦Р РЋРІР‚вЂњР В Р вЂ Р Р†Р вЂљРЎСљ

Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР РЋР вЂ№Р В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋР С“Р РЋР Р‰ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р РЋРЎвЂњ invoice draft-Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р вЂ¦Р В Р’ВµР РЋРІР‚С™Р В РЎвЂќР РЋРЎвЂњ.

### Р В РІР‚в„ўР В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р В Р’В° Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РўвЂР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В° Р РЋРІР‚вЂњР В РўвЂР В Р’ВµР РЋР РЏ

FakturaBot Р Р†Р вЂљРІР‚Сњ Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р В Р’В±Р В РЎвЂўР РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљ.
Р В Р’В¦Р В Р’Вµ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂР В РЎвЂќР В Р’В»Р В Р’В°Р В РўвЂ Р В РЎвЂќР В Р’В°Р РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Telegram-Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В Р’В° Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В Р’В±Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’ВµР РЋР С“-Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚В Р В Р’ВµР РЋР С“.

### Р В РІР‚СњР В РЎвЂўР В РЎвЂќР РЋРЎвЂњР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™Р В РЎвЂ

Р В РЎвЂ™Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎС›Р В РІР‚вЂќ:
`docs/TZ_FakturaBot.md`

### Р В РЎСљР В Р’В°Р РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В РЎвЂ”Р В Р вЂ¦Р РЋРІР‚вЂњ Р В РЎвЂќР РЋР вЂљР В РЎвЂўР В РЎвЂќР В РЎвЂ

- Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњ Р РЋР С“Р РЋРІР‚С™Р РЋР вЂљР РЋРЎвЂњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР РЋРЎвЂњ Р РЋР вЂљР В Р’ВµР В РЎвЂ”Р В РЎвЂўР В Р’В·Р В РЎвЂР РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР РЋР вЂ№
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ README
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ AGENTS
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р РЋРІР‚С™Р В РЎвЂ CHANGELOG
- Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’Вµ Р В РЎС›Р В РІР‚вЂќ Р РЋРЎвЂњ docs
- Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂќР В Р’В°Р РЋР вЂљР В РЎвЂќР В Р’В°Р РЋР С“ MVP

## 2026-03-31 Р Р†Р вЂљРІР‚Сњ Session 003 Р Р†Р вЂљРІР‚Сњ Phase 1 voice-to-draft preview

### Р В Р’В©Р В РЎвЂў Р В Р вЂ Р В РЎвЂР РЋР вЂљР РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Phase 1 Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ¦Р В Р’Вµ Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂР В РІвЂћвЂ“ voice Р Р†РІР‚В РІР‚в„ў text smoke test, Р В Р’В° Р РЋР РЏР В РЎвЂќ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ wow-flow:
  **voice Р Р†РІР‚В РІР‚в„ў STT Р Р†РІР‚В РІР‚в„ў AI draft preview**
- Р В РЎСљР В Р’В° Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р РЋРІР‚вЂњ Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В РЎВР В РЎвЂў:
  - save Р РЋРЎвЂњ Р В РІР‚ВР В РІР‚Сњ
  - PDF
  - email
  - supplier/contact persistence
- STT Р РЋРІР‚вЂњ LLM parsing Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РўвЂР РЋРІР‚вЂњР В Р’В»Р В Р’ВµР В Р вЂ¦Р РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’В° Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР РЋРІР‚вЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р РЋРІР‚вЂњР РЋР С“Р В РЎвЂ.
- Р В Р’В Р В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРІР‚вЂњ API Р В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’Вµ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР РЋРІР‚вЂњР В РЎвЂ“Р В Р’В°Р РЋР вЂ№Р РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р вЂ  repo; Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ `.env`.

### Р В Р’В©Р В РЎвЂў Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В Р’ВµР В Р вЂ¦Р В РЎвЂў

- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР РЋРІР‚С™Р РЋР вЂљР В РЎвЂР В РЎВР В РЎвЂќР РЋРЎвЂњ `OPENAI_STT_MODEL` Р РЋРІР‚вЂњ `OPENAI_LLM_MODEL` Р РЋРЎвЂњ config;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/speech_to_text.py`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/llm_invoice_parser.py`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў prompt `prompts/invoice_draft_prompt.txt`;
- Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/handlers/voice.py`;
- Р В РЎвЂ”Р РЋРІР‚вЂњР В РўвЂР В РЎвЂќР В Р’В»Р РЋР вЂ№Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В РЎвЂў voice router;
- Phase 1 flow Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ:
  Telegram voice Р Р†РІР‚В РІР‚в„ў local temp file Р Р†РІР‚В РІР‚в„ў OpenAI transcription Р Р†РІР‚В РІР‚в„ў OpenAI draft parsing Р Р†РІР‚В РІР‚в„ў preview in chat.

### Р В РІР‚в„ўР В Р’В°Р В Р’В¶Р В Р’В»Р В РЎвЂР В Р вЂ Р РЋРІР‚вЂњ Р В РўвЂР РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В Р РЋРІР‚вЂњ / Р РЋРЎвЂњР РЋР вЂљР В РЎвЂўР В РЎвЂќР В РЎвЂ

- Р В РЎСљР В Р’В° Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋР вЂљР РЋРІР‚С™Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚СњР В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР РЋР РЏР РЋРІР‚С™Р В РЎвЂ, Р РЋРІР‚В°Р В РЎвЂў `.env` Р В Р вЂ Р В Р вЂ¦Р В Р’ВµР РЋР С“Р В Р’ВµР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРЎвЂњ `.gitignore`.
- Р В РЎвЂєР В РўвЂР В РЎвЂР В Р вЂ¦ `OPENAI_API_KEY` Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋРІР‚вЂњ Р В РўвЂР В Р’В»Р РЋР РЏ STT, Р РЋРІР‚вЂњ Р В РўвЂР В Р’В»Р РЋР РЏ LLM parsing.
- Р В РЎСџР В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂР В РІвЂћвЂ“ voice-flow Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В РЎвЂў Р РЋР вЂљР В РЎвЂўР В Р’В·Р В РЎвЂ”Р РЋРІР‚вЂњР В Р’В·Р В Р вЂ¦Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™, Р В Р’В° Р РЋР С“Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В Р’В±Р РЋРЎвЂњ Р В Р’В·Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРЎвЂњР В РЎВР РЋРІР‚вЂњР РЋРІР‚С™Р В РЎвЂ Р В Р вЂ¦Р В Р’В°Р В РЎВР РЋРІР‚вЂњР РЋР вЂљ Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’В°.
- Preview Р В Р вЂ¦Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В РЎвЂР В Р вЂ¦Р В Р’ВµР В Р вЂ¦ Р В РЎвЂ”Р В РЎвЂўР В РЎвЂќР В Р’В°Р В Р’В·Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂќР РЋР вЂљР В РЎвЂР В Р вЂ Р РЋРІР‚вЂњ Р В Р’В·Р В Р вЂ¦Р В Р’В°Р РЋРІР‚РЋР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р В РЎвЂР В РЎвЂ”Р РЋРЎвЂњ `Р Р†Р вЂљРІР‚Сњ Р Р†Р вЂљРІР‚Сњ`; Р РЋРІР‚С›Р В РЎвЂўР РЋР вЂљР В РЎВР В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В РЎвЂўР В РўвЂР РЋР вЂљР В Р’В°Р В Р’В·Р РЋРЎвЂњ Р РЋРІР‚РЋР В РЎвЂР РЋР С“Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ.
- Р В Р вЂЎР В РЎвЂќР РЋРІР‚В°Р В РЎвЂў STT Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ  Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР В РЎвЂўР В Р’В¶Р В Р вЂ¦Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР В РЎвЂќР РЋР С“Р РЋРІР‚С™, Р В Р вЂ¦Р В Р’Вµ Р В РЎВР В РЎвЂўР В Р’В¶Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂ”Р РЋР вЂљР В Р’В°Р В Р вЂ Р В Р’В»Р РЋР РЏР РЋРІР‚С™Р В РЎвЂ Р В РІвЂћвЂ“Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ  LLM Р Р†Р вЂљРІР‚Сњ Р РЋРІР‚С™Р РЋР вЂљР В Р’ВµР В Р’В±Р В Р’В° Р В Р’В·Р РЋРЎвЂњР В РЎвЂ”Р В РЎвЂР В Р вЂ¦Р РЋР РЏР РЋРІР‚С™Р В РЎвЂ flow Р РЋРІР‚вЂњ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋР С“Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р В РЎвЂўР В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ“Р В РЎвЂўР В Р’В»Р В РЎвЂўР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’Вµ.

### Р В Р’В©Р В РЎвЂў Р РЋР С“Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В РЎВР В РЎвЂў Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В Р’В»Р В РЎвЂўР РЋР С“Р РЋР Р‰

- Р В Р вЂ¦Р В Р’Вµ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В РЎвЂўР В Р вЂ Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В РЎвЂР РЋР С“Р РЋР Р‰ supplier onboarding, contacts, PDF, email, contract extraction;
- Р В Р вЂ¦Р В Р’Вµ Р В РўвЂР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В°Р РЋР С“Р РЋР Р‰ Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В Р’В° save draft;
- Р В Р вЂ¦Р В Р’Вµ Р В Р’В±Р РЋРЎвЂњР В Р’В»Р В РЎвЂў Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р вЂ Р В Р’ВµР РЋР вЂљР В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў deploy;
- internet lookup / FinStat Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р РЋРІР‚В¦Р В РЎвЂўР В РўвЂР РЋР РЏР РЋРІР‚С™Р РЋР Р‰ Р РЋРЎвЂњ Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ flow.

### Р В Р Р‹Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“ Р РЋРІР‚С›Р В Р’В°Р В Р’В·Р В РЎвЂ

Phase 1 Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В Р’ВµР В Р вЂ¦Р В Р’В° Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ Р В РЎвЂќР В РЎвЂўР В РўвЂР РЋРЎвЂњ.
Р В РІР‚вЂњР В РЎвЂР В Р вЂ Р В РЎвЂР В РІвЂћвЂ“ runtime test Р В Р’В· Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВ `BOT_TOKEN` Р РЋРІР‚вЂњ `OPENAI_API_KEY` Р РЋРІР‚В°Р В Р’Вµ Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р’ВµР В Р вЂ¦.

### Р В Р’В©Р В РЎвЂў Р В РўвЂР В Р’В°Р В Р’В»Р РЋРІР‚вЂњ

- Phase 2 Р Р†Р вЂљРІР‚Сњ Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ supplier onboarding Р РЋРЎвЂњ chat-based Р РЋР С“Р РЋРІР‚С™Р В РЎвЂР В Р’В»Р РЋРІР‚вЂњ;
- Р В Р’В±Р В Р’ВµР В Р’В· fancy UI;
- Р РЋРІР‚В Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰: Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂ Р РЋРІР‚вЂњ Р В Р’В·Р В Р’В±Р В Р’ВµР РЋР вЂљР В Р’ВµР В РЎвЂ“Р РЋРІР‚С™Р В РЎвЂ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰ Р В РЎвЂ”Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚РЋР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎвЂќР В Р’В°, Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎВР В Р’В°Р В РІвЂћвЂ“Р В Р’В±Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚В¦ invoice flows.
## 2026-04-01 - Session 005 - Phase 3: manual contact creation

### Goal
Implement minimal manual customer contact creation required for next invoice phases.

### Implemented
- SQLite bootstrap extended with `contact` table (fail-loud compatibility check, no auto-drop/migrations).
- Added `bot/services/contact_service.py` with repository-style operations:
  - `ContactProfile`
  - `get_all_by_supplier(telegram_id)`
  - `get_by_name(telegram_id, name)`
  - `create_contact(...)`
  - `create_or_replace(...)`
- Implemented `bot/handlers/contacts.py` as a simple chat-based flow:
  1. company name
  2. ICO
  3. DIC
  4. optional IC DPH (`-`)
  5. address
  6. email
  7. optional contact person (`-`)
  8. summary
  9. confirm `yes`/`no`
  10. save
- Added exact-name duplicate check per supplier; existing name is warned and confirmed overwrite saves via upsert.
- Added supplier-profile guard: contact flow is blocked until `/supplier` onboarding is completed.

### Explicitly not included in this phase
- contract-based contact extraction
- contact search UI
- invoice save flow
- PDF generation
- email send
- external lookup API / FinStat
- complex dedup/fuzzy matching

### Decision
Phase 3 remains intentionally simple and chat-based; contract extraction and external lookup stay deferred to later phases.

### Follow-up note (language consistency)
- Text confirmation in supplier onboarding aligned to Slovak: `ano / nie` instead of `yes / no`.
- Text confirmation in manual contact flow aligned to Slovak: `ano / nie` instead of `yes / no`.
- User-facing language consistency improved across `/start`, voice preview, supplier onboarding, and manual contact flow.
- Why this matters:
  - bot is oriented to a Slovak interface;
  - mixed-language confirmations create product inconsistency;
  - language consistency is better fixed early while flows are still small.
## 2026-04-03 - Session 006 - Research spike: real PAY by square integration path

### Goal
Р В РЎСџР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’ВµР РЋР С“Р РЋРІР‚С™Р В РЎвЂ technical research spike Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ PAY by square QR Р РЋРЎвЂњ FakturaBot Р В Р’В±Р В Р’ВµР В Р’В· blind implementation.

### Implemented
- Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РІвЂћвЂ“ research artifact: `docs/PayBySquare_Research_Spike.md`.
- Р В РІР‚вЂќР РЋРІР‚вЂњР В Р’В±Р РЋР вЂљР В Р’В°Р В Р вЂ¦Р В РЎвЂў Р РЋРІР‚С™Р В Р’В° Р В РЎвЂ”Р В РЎвЂўР РЋР вЂљР РЋРІР‚вЂњР В Р вЂ Р В Р вЂ¦Р РЋР РЏР В Р вЂ¦Р В РЎвЂў Р В РўвЂР В Р’В¶Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В»Р В Р’В°:
  - Р В РЎвЂўР РЋРІР‚С›Р РЋРІР‚вЂњР РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“Р В Р вЂ¦Р В Р’В° Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ PAY by square 1.2.0,
  - by square API docs,
  - Python package `pay-by-square`,
  - Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњ non-Python implementation repos (TS/Go/PHP) Р РЋР РЏР В РЎвЂќ Р РЋР вЂљР В Р’ВµР РЋРІР‚С›Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ¦Р РЋР С“Р В РЎвЂ.
- Р В РІР‚вЂќР В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎвЂ”Р РЋР вЂљР В Р’В°Р В РЎвЂќР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІР‚С™Р В Р’ВµР РЋРІР‚В¦Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р В Р вЂ Р В Р’ВµР РЋР вЂљР В РўвЂР В РЎвЂР В РЎвЂќР РЋРІР‚С™ Р В РўвЂР В Р’В»Р РЋР РЏ repo:
  - Р РЋР вЂљР В Р’ВµР В РЎвЂќР В РЎвЂўР В РЎВР В Р’ВµР В Р вЂ¦Р В РўвЂР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ Р РЋРІвЂљВ¬Р В Р’В»Р РЋР РЏР РЋРІР‚В¦: Р В Р вЂ Р В Р’В»Р В Р’В°Р РЋР С“Р В Р вЂ¦Р В Р’В° Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Python-Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋРІР‚вЂњР В Р’В·Р В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР РЏ payload encoder (spec-driven),
  - Р В Р’В±Р В Р’ВµР В Р’В· Р В Р вЂ Р В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р В Р’В·Р В РЎвЂўР В Р вЂ Р В Р вЂ¦Р РЋРІР‚вЂњР РЋРІвЂљВ¬Р В Р вЂ¦Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў SaaS Р РЋР РЏР В РЎвЂќ Р В РЎвЂќР РЋР вЂљР В РЎвЂР РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂўР РЋРІР‚вЂќ Р В Р’В·Р В Р’В°Р В Р’В»Р В Р’ВµР В Р’В¶Р В Р вЂ¦Р В РЎвЂўР РЋР С“Р РЋРІР‚С™Р РЋРІР‚вЂњ,
  - Р В Р’В±Р В Р’ВµР В Р’В· cross-runtime Р В Р’В°Р В РўвЂР В Р’В°Р В РЎвЂ”Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В Р’В° Р РЋР РЏР В РЎвЂќ Р В Р’В±Р В Р’В°Р В Р’В·Р В РЎвЂўР В Р вЂ Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р РЋРІвЂљВ¬Р В Р’В»Р РЋР РЏР РЋРІР‚В¦Р РЋРЎвЂњ.
- Р В РІР‚вЂќР В Р’В°Р РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР РЋР С“Р В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ required payload Р РЋРІР‚вЂњ field constraints Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р В РЎвЂўР РЋРІР‚вЂќ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.
- Р В РЎСџР РЋРІР‚вЂњР В РўвЂР В РЎвЂ“Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў implementation recommendation Р В РўвЂР В Р’В»Р РЋР РЏ Р В РЎВР В Р’В°Р В РІвЂћвЂ“Р В Р’В±Р РЋРЎвЂњР РЋРІР‚С™Р В Р вЂ¦Р РЋР Р‰Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂўР В РЎвЂ“Р В РЎвЂў PR (Р В Р’В±Р В Р’ВµР В Р’В· Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ runtime Р В Р’В»Р В РЎвЂўР В РЎвЂ“Р РЋРІР‚вЂњР В РЎвЂќР В РЎвЂ Р РЋРЎвЂњ Р РЋРІР‚В Р РЋРІР‚вЂњР В РІвЂћвЂ“ Р РЋР С“Р В Р’ВµР РЋР С“Р РЋРІР‚вЂњР РЋРІР‚вЂќ).

### Explicitly not included in this session
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Р В Р’В·Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦ Р РЋРЎвЂњ `bot/services/pdf_generator.py`.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ production integration patch Р В РўвЂР В Р’В»Р РЋР РЏ PAY by square.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Р РЋР вЂљР В РЎвЂўР В Р’В·Р РЋРІвЂљВ¬Р В РЎвЂР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ scope Р В Р вЂ¦Р В Р’В° email / external bank API / Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІвЂљВ¬Р РЋРІР‚вЂњ Р В РЎВР В РЎвЂўР В РўвЂР РЋРЎвЂњР В Р’В»Р РЋРІР‚вЂњ.

### Decision
Р В Р Р‹Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚РЋР В Р’В°Р РЋРІР‚С™Р В РЎвЂќР РЋРЎвЂњ Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’ВµР РЋР вЂљР РЋРІвЂљВ¬Р РЋРЎвЂњР РЋРІР‚СњР В РЎВР В РЎвЂў research + decision record, Р В РЎвЂ”Р РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ Р РЋРІР‚РЋР В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В РЎвЂўР В РЎвЂќР РЋР вЂљР В Р’ВµР В РЎВР В РЎвЂР В РЎВ PR Р РЋР вЂљР В РЎвЂўР В Р’В±Р В РЎвЂР В РЎВР В РЎвЂў Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚вЂњР В РЎВР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р РЋРЎвЂњ production Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋР вЂ№ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў PAY by square payload Р РЋРЎвЂњ PDF flow.


## 2026-04-03 - Session 007 - Implementation: real PAY by square payload in PDF flow

### Goal
Р В РІР‚вЂќР В Р’В°Р В РЎВР РЋРІР‚вЂњР В Р вЂ¦Р В РЎвЂР РЋРІР‚С™Р В РЎвЂ QR placeholder Р РЋРЎвЂњ Phase 4 Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РІвЂћвЂ“ PAY by square payload generator Р В РўвЂР В Р’В»Р РЋР РЏ invoice payment use case.

### Implemented
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў `bot/services/pay_by_square.py` Р В Р’В· internal spec-driven encoder pipeline:
  1) mapping paymentorder Р В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦,
  2) CRC32,
  3) LZMA raw compression (LZMA1),
  4) header/length prepend,
  5) Base32hex payload output.
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў strict validation: IBAN, amount, currency, VS, due date, beneficiary name (fail-loud Р РЋРІР‚РЋР В Р’ВµР РЋР вЂљР В Р’ВµР В Р’В· `PayBySquareValidationError`).
- `bot/services/pdf_generator.py` Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р В Р’ВµР В РўвЂР В Р’ВµР В Р вЂ¦Р В РЎвЂў Р В Р’В· placeholder Р РЋР вЂљР РЋР РЏР В РўвЂР В РЎвЂќР В Р’В° `PAYBYSQUARE|...` Р В Р вЂ¦Р В Р’В° Р В Р вЂ Р В РЎвЂР В РЎвЂќР В Р’В»Р В РЎвЂР В РЎвЂќ `build_pay_by_square_payload(...)`.
- Р В РІР‚СњР В РЎвЂўР В РўвЂР В Р’В°Р В Р вЂ¦Р В РЎвЂў unit tests:
  - deterministic payload vector,
  - validation failures,
  - PDF integration smoke (QR payload looks encoded and PDF still written).
- Р В РЎвЂєР В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В РЎвЂў `README.md`, `docs/TZ_FakturaBot.md`, `CHANGELOG.md` Р В РўвЂР В Р’В»Р РЋР РЏ Р РЋРІР‚РЋР В Р’ВµР РЋР С“Р В Р вЂ¦Р В РЎвЂўР В РЎвЂ“Р В РЎвЂў Р В Р вЂ Р РЋРІР‚вЂњР В РўвЂР В РЎвЂўР В Р’В±Р РЋР вЂљР В Р’В°Р В Р’В¶Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р РЋРІР‚С™Р РЋРЎвЂњР РЋР С“Р РЋРЎвЂњ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ“Р РЋР вЂљР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ.

### Explicitly not included
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ external SaaS generation path.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ Node/Go/PHP sidecar adaptation.
- Р В РЎСљР В Р’ВµР В РЎВР В Р’В°Р РЋРІР‚Сњ email/bank API scope expansion.

### Manual verification status
- Р В Р в‚¬ Р РЋРІР‚В Р РЋР Р‰Р В РЎвЂўР В РЎВР РЋРЎвЂњ Р РЋР С“Р В Р’ВµР РЋР вЂљР В Р’ВµР В РўвЂР В РЎвЂўР В Р вЂ Р В РЎвЂР РЋРІР‚В°Р РЋРІР‚вЂњ Р В Р вЂ¦Р В Р’Вµ Р В Р вЂ Р В РЎвЂР В РЎвЂќР В РЎвЂўР В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р’В»Р В Р’В°Р РЋР С“Р РЋР Р‰ Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В Р’В° Р В РЎвЂ”Р В Р’ВµР РЋР вЂљР В Р’ВµР В Р вЂ Р РЋРІР‚вЂњР РЋР вЂљР В РЎвЂќР В Р’В° Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ QR Р В Р’В±Р В Р’В°Р В Р вЂ¦Р В РЎвЂќР РЋРІР‚вЂњР В Р вЂ Р РЋР С“Р РЋР Р‰Р В РЎвЂќР В РЎвЂР В РЎВР В РЎвЂ Р В РЎВР В РЎвЂўР В Р’В±Р РЋРІР‚вЂњР В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР В РЎВР В РЎвЂ Р В Р’В°Р В РЎвЂ”Р В РЎвЂќР В Р’В°Р В РЎВР В РЎвЂ.
- Р В РЎСџР РЋРІР‚вЂњР РЋР С“Р В Р’В»Р РЋР РЏ deploy Р В РЎвЂ”Р В РЎвЂўР РЋРІР‚С™Р РЋР вЂљР РЋРІР‚вЂњР В Р’В±Р В Р вЂ¦Р В Р’В° manual verification Р В Р вЂ¦Р В Р’В° Р РЋР вЂљР В Р’ВµР В Р’В°Р В Р’В»Р РЋР Р‰Р В Р вЂ¦Р В РЎвЂР РЋРІР‚В¦ SK banking clients.
### Follow-up note (Р РЋР С“Р В Р’ВµР В РЎВР В Р’В°Р В Р вЂ¦Р РЋРІР‚С™Р В РЎвЂР В РЎвЂќР В Р’В° Р В РўвЂР В Р’В°Р РЋРІР‚С™ Р РЋРЎвЂњ faktР вЂњРЎвЂќre)
- Р В РЎСџР В Р’В»Р РЋРЎвЂњР РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В Р вЂ¦Р РЋРЎвЂњ Р В РЎВР РЋРІР‚вЂњР В Р’В¶ `DР вЂњР Р‹tum vystavenia` Р РЋРІР‚вЂњ `DР вЂњР Р‹tum dodania` Р РЋРЎвЂњ Р РЋР С“Р В РЎвЂ”Р В Р’ВµР РЋРІР‚В Р В РЎвЂР РЋРІР‚С›Р РЋРІР‚вЂњР В РЎвЂќР В Р’В°Р РЋРІР‚В Р РЋРІР‚вЂњР РЋРІР‚вЂќ Р РЋРЎвЂњР РЋР С“Р РЋРЎвЂњР В Р вЂ¦Р РЋРЎвЂњР РЋРІР‚С™Р В РЎвЂў.
- Р В РІР‚СњР В Р’В°Р РЋРІР‚С™Р В Р’В°, Р В Р вЂ Р В РЎвЂќР В Р’В°Р В Р’В·Р В Р’В°Р В Р вЂ¦Р В Р’В° Р В РЎвЂќР В РЎвЂўР РЋР вЂљР В РЎвЂР РЋР С“Р РЋРІР‚С™Р РЋРЎвЂњР В Р вЂ Р В Р’В°Р РЋРІР‚РЋР В Р’ВµР В РЎВ Р РЋРЎвЂњ voice/text input, Р РЋРІР‚С™Р В Р’ВµР В РЎвЂ”Р В Р’ВµР РЋР вЂљ Р РЋРІР‚вЂњР В Р вЂ¦Р РЋРІР‚С™Р В Р’ВµР РЋР вЂљР В РЎвЂ”Р РЋР вЂљР В Р’ВµР РЋРІР‚С™Р РЋРЎвЂњР РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р РЋР РЏР В РЎвЂќ `DР вЂњР Р‹tum dodania`.
- `DР вЂњР Р‹tum vystavenia` Р В Р’В·Р В Р’В°Р В Р вЂ Р В Р’В¶Р В РўвЂР В РЎвЂ Р В Р вЂ Р РЋР С“Р РЋРІР‚С™Р В Р’В°Р В Р вЂ¦Р В РЎвЂўР В Р вЂ Р В Р’В»Р РЋР вЂ№Р РЋРІР‚СњР РЋРІР‚С™Р РЋР Р‰Р РЋР С“Р РЋР РЏ Р В Р’В±Р В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В РЎВ Р В Р’В°Р В Р вЂ Р РЋРІР‚С™Р В РЎвЂўР В РЎВР В Р’В°Р РЋРІР‚С™Р В РЎвЂР РЋРІР‚РЋР В Р вЂ¦Р В РЎвЂў Р В Р вЂ  Р В РЎВР В РЎвЂўР В РЎВР В Р’ВµР В Р вЂ¦Р РЋРІР‚С™ Р РЋР С“Р РЋРІР‚С™Р В Р вЂ Р В РЎвЂўР РЋР вЂљР В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋР РЏ Р РЋРІР‚С›Р В Р’В°Р В РЎвЂќР РЋРІР‚С™Р РЋРЎвЂњР РЋР вЂљР В РЎвЂ.

## 2026-04-03 - Session 008 - Verification support: PAY by square manual scan checklist

### Goal
Prepare a local verification-task plan for manual validation of the real PAY by square QR after merge, without runtime code changes.

### Implemented
- Added a short verification artifact: `docs/PayBySquare_Manual_Verification_Checklist.md`.
- Documented the local verification flow:
  - how to generate a PDF invoice locally;
  - where to find the generated PDF;
  - which fields must be checked after scanning in a banking app.
- Added expected outcomes:
  - success,
  - partial success,
  - fail.
- Added a short record checklist for the post-test note so follow-up patch decisions are explicit.

### Explicitly not included
- No runtime code changes.
- No new feature work.
- No email flow changes.
- No Phase 5 work.

### Decision
Before PAY by square production sign-off, a separate manual scan verification in a real banking mobile app must be completed and recorded in `PROJECT_LOG.md`.



## 2026-04-06 - Session 009 - Local env support for FakturaBot

### Goal
Allow FakturaBot to run locally from a dedicated repo-root `faktura.env` file without breaking existing `.env`-based startup.

### Implemented
- `bot/config.py` now loads `faktura.env` first when it exists.
- If `faktura.env` is absent, startup falls back to `.env`.
- Added repo-root `faktura.env` with empty/default placeholders only.
- Added `faktura.env` to `.gitignore` while keeping `.env` ignore intact.

### Explicitly not included
- No config field renames.
- No secret values.
- No runtime behavior changes beyond env-file selection.
- `.env.example` left unchanged.

### Decision
Local FakturaBot setup now supports a dedicated non-committed `faktura.env` file while preserving `.env` compatibility.

## 2026-04-08 - Session 010 - Docs ownership split: Implementation Plan vs LLM Contract

### Goal
Remove overlap risk between planning and contract docs by clarifying document ownership.

### Implemented
- `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md` kept as rollout document (phase scope/order/risks/acceptance) and Phase 2 detail reduced to planning-level with explicit reference to LLM contract.
- `docs/FakturaBot_LLM_Orchestrator_Contract.md` marked as detailed Phase 2 AI contract and cross-referenced back to the implementation plan for sequencing.
- `README.md` docs structure updated with concise role distinction for both docs.

### Scope
- Docs-only clarification; no code changes.

## 2026-04-08 - Session 011 - Phase 1 implementation: deterministic contact lookup + service-term canonicalization

### Goal
Implement Phase 1 Python-side canonicalization only (no AI/orchestrator changes).

### Implemented
- Added deterministic contact lookup normalization in `ContactService` with structured states:
  - `exact_match`, `normalized_match`, `multiple_candidates`, `no_match`.
- Added lookup-only company normalization for case/punctuation/separator/legal-form variants.
- Added conservative legal-form support (token-boundary):
  - `s.r.o.` variants (`sro`, `s r o`, `s. r. o.`),
  - `a.s.` variants (`as`, `a s`),
  - conservative `spol` + `sro` / `s r o` tail variants.
- Integrated invoice flow with lookup-state branching:
  - continue on exact/normalized,
  - explicit fail-loud message on multiple candidates,
  - explicit non-assumptive guidance on no match (retry or `/contact`, no auto-create).
- Added deterministic internal service-term normalizer:
  - `opravy -> oprava`, `ремонт -> oprava`, `монтаж -> montáž`.
- Kept alias precedence unchanged: supplier alias mapping remains source of truth for final preview/PDF title.

### Tests
- Added `tests/test_contact_lookup_normalization.py`.
- Added `tests/test_service_term_normalizer.py`.
- Added `tests/test_invoice_contact_lookup_feedback.py`.
- Full test suite passes with `PYTHONPATH=. pytest -q`.

### Scope
- No DB migration.
- No LLM/prompt/orchestrator schema changes.

## 2026-04-08 - Session 012 - Test runner expectation clarified (pytest)

### Goal
Remove ambiguity between legacy unittest habits and current pytest workflow.

### Implemented
- Added explicit test-runner note in `README.md`:
  - canonical runner is `pytest`,
  - command: `PYTHONPATH=. pytest -q`,
  - unittest is not the default expected workflow.
- Added minimal `pytest.ini` with `testpaths = tests` as repo tooling baseline.

### Scope
- Docs/tooling only; no runtime code changes.
---

## 2026-04-06 - Session 013 - Windows-safe SQLite connection closing in tests

### Goal
Eliminate Windows test-suite failures during `TemporaryDirectory` cleanup by ensuring SQLite connections are explicitly closed after each DB access path.

### Implemented
- Added `managed_connection(...)` in `bot/services/db.py` to guarantee `connection.close()` in `finally`.
- Switched SQLite usage in `bot/services/supplier_service.py`, `bot/services/service_alias_service.py`, `bot/services/invoice_service.py`, `bot/services/contact_service.py`, and DB bootstrap in `bot/services/db.py` from direct `sqlite3.connect(...)` context usage to the shared managed helper.
- Preserved existing transaction behavior (`commit()` remains where it already existed).
- Preserved `row_factory = sqlite3.Row` behavior on read paths.
- Verified with `python -m unittest discover -s tests -p "test_*.py" -v`: 18 tests passed on Windows, including the previously affected temp SQLite DB cleanup paths.

### Explicitly not included
- No schema changes.
- No business logic changes.
- No test behavior changes beyond the connection lifecycle fix.

### Decision
SQLite connection lifetime in services/bootstrap is now treated as an explicit resource lifecycle concern, not only a transaction context concern, to remain Windows-safe for temporary DB files.

---

## 2026-04-06 - Session 014 - PDF Slovak glyph completion (ľ, ť)

### Goal
Finish PDF glyph coverage for the remaining Slovak characters (`ľ`, `ť`) without changing the existing layout.

### Implemented
- Confirmed that bundled ReportLab `Vera.ttf` / `VeraBd.ttf` do not contain `ľ` and `ť`.
- Updated `bot/services/pdf_generator.py` to resolve a Unicode-capable font pair from installed Windows fonts first (`arial.ttf` / `arialbd.ttf`, with fallbacks), and only use a fallback font if it actually covers the required Slovak glyphs.
- Normalized visible Slovak PDF literals in `bot/services/pdf_generator.py` to proper Unicode text so headers and labels render correctly with the selected font.
- Added a regression test to verify the selected regular and bold PDF fonts cover `ľ` and `ť`, while keeping existing wrapping/layout tests intact.
- Re-verified the full test suite after the font-selection change.

### Explicitly not included
- No layout redesign.
- No payment block or table layout refactor.
- No schema or business logic changes.

### Decision
PDF rendering now depends on an explicitly validated Unicode font path instead of assuming bundled ReportLab Vera fonts are sufficient for Slovak invoice text.

---

## 2026-04-07 - Session 015 - Manual PAY by square banking-app verification passed for one local FakturaBot flow

### Goal
Record the completed local end-to-end FakturaBot verification session for the currently tested PAY by square PDF flow.

### Verified
- Local supplier -> contact -> invoice flow completed successfully.
- A PDF invoice artifact was generated successfully and reviewed.
- Latest local generated PDF artifact present at `storage/invoices/20260006.pdf` (timestamp observed locally before this log update: 2026-04-07 18:45).
- The PAY by square QR from the tested PDF was scanned successfully in a real banking mobile app.
- Manual user confirmation states the bank-app recipient account data matched the expected recipient account data.
- Manual user confirmation states the amount was populated correctly.
- Manual user confirmation states the due date (`datum splatnosti`) was populated correctly.

### Scope note
- This log entry records one successful real local end-to-end verification case for the currently tested FakturaBot flow.
- This closes the previously pending manual scan verification milestone for that tested flow.
- This does not claim universal compatibility across all banking apps or full production sign-off.

### Decision
The PAY by square PDF flow now has at least one recorded successful real banking-app verification milestone in addition to local code/test validation.


## 2026-04-10 — Session 016 — Service naming terminology audit + safe refactor

### Goal
Align service naming wording in `/service` and related code to user-friendly Slovak and consistent internal English names.

### Audit findings
- User-facing texts still used technical wording `alias` / `canonical názov` in `/service` flow and README.
- Internal Python naming mixed old terms (`alias`, `canonical_title`, `item_name_final`) with business semantics.
- Persistence schema used `supplier_service_alias(alias, canonical_title)` and related bootstrap checks.
- Tests reflected old naming (`test_alias_resolution_*`, `entry.alias`).

### What changed
- User-facing Slovak wording in `/service` and invoice preview now uses:
  - `krátky názov služby`
  - `plný názov služby`
- Internal naming in service/handlers moved to:
  - `service_short_name`
  - `service_display_name`
- Service layer added explicit method `resolve_service_display_name(...)`; kept compatibility wrapper `resolve_alias(...)`.
- README `/service` command description updated to new wording.
- Tests renamed/updated to new internal naming.

### Compatibility / DB
- DB schema intentionally left unchanged (`alias`, `canonical_title` stay as storage columns in `supplier_service_alias`).
- No migration introduced.

## 2026-04-10 — Session 013 — Phase 2 minimal AI layer (invoice draft only)

### Goal
- Added minimal Phase 2 AI entrypoint for invoice draft flow only.
- LLM now returns Slovak-facing business payload (`vstup`, `zamer`, `biznis_sk`, `stopa`) and Python continues deterministic truth flow.

### What changed
- Updated `prompts/invoice_draft_prompt.txt` to require strict JSON payload for Phase 2 invoice-only schema.
- Reworked `bot/services/llm_invoice_parser.py`:
  - added strict payload validator `validate_invoice_phase2_payload(...)`;
  - added explicit error `LlmInvoicePayloadError` for malformed payload;
  - added `parse_invoice_phase2_payload(...)` that fails loud on shape violations.
- Updated `bot/handlers/invoice.py`:
  - integrated new parser path before deterministic preview flow;
  - mapped Phase 2 `biznis_sk` into existing Python invoice draft fields;
  - preserved original text from `vstup.povodny_text` in preview context;
  - added clear retry message when AI payload is invalid or key fields are missing.
- Added `tests/test_invoice_phase2_ai_layer.py` covering:
  - multilingual/mixed payload validation path,
  - original text preservation,
  - malformed payload handling,
  - preview flow still using Python truth for contact lookup and service display mapping,
  - missing amount handling with clean retry message.

### Notes
- Scope is intentionally invoice-flow only (no contact onboarding redesign, no supplier/document AI expansion).
- No DB migration required.

## 2026-04-10 — Session 017 — Temporary structured debug transparency for voice → STT → Phase 2 invoice flow

### Goal
- Add temporary, env-flagged structured debug trace to identify where customer name is lost/corrupted across STT, validated LLM payload, and deterministic Python contact lookup.

### What changed
- Added `DEBUG_INVOICE_TRANSPARENCY` config flag in `bot/config.py` (default off).
- Added JSON debug event in voice handler after successful STT with:
  - `request_id`
  - `telegram_update_id`
  - `telegram_message_id`
  - `stt_text`
- Added JSON debug event in invoice flow right after validated Phase 2 payload with:
  - `vstup.povodny_text`
  - `biznis_sk.odberatel_kandidat`
  - `biznis_sk.polozka_povodna`
  - `biznis_sk.termin_sluzby_sk`
- Added JSON debug events around deterministic contact lookup:
  - before lookup (`lookup_raw_input`, `lookup_normalized_input`),
  - after lookup (`lookup_state`, `matched_contact_id`, and candidate metadata when multiple matches).
- Added JSON debug event before preview/save handoff with final resolved contact and service title fields.
- `request_id` is propagated across voice STT → Phase 2 parse → lookup → preview path.

### Safety / constraints
- No business logic, fallback behavior, or contact auto-fix/auto-create behavior changed.
- Lookup debug normalization reuses existing `ContactService.normalize_lookup_forms(...)` (no duplicate debug-only normalization logic).

## 2026-04-10 — Session 018 — Phase 2 odberateľ candidate contract hardening

### Goal
- Harden invoice Phase 2 AI contract so `biznis_sk.odberatel_kandidat` is canonical, lookup-ready, and fail-loud if raw/noisy fragments leak from multilingual voice/STT input.

### What changed
- Prompt (`prompts/invoice_draft_prompt.txt`) now explicitly requires lookup-ready canonical candidate in `biznis_sk.odberatel_kandidat`:
  - disallows cyrillic/raw inflected fragments and preposition/filler phrases,
  - keeps original multilingual input only in `vstup.povodny_text`,
  - allows raw extraction notes only in trace (`stopa`),
  - adds multilingual voice-like examples (RU/mixed, s.r.o./sro, imperfect STT).
- Validator (`bot/services/llm_invoice_parser.py`) now fail-loud rejects non lookup-ready candidates:
  - empty/whitespace values,
  - obvious raw phrase fragments (`на техкомпании`, `для компании`, `pre firmu`, `kompanii`),
  - cyrillic-only values,
  - preposition-start and too noisy candidates for deterministic lookup.
- Tests (`tests/test_invoice_phase2_ai_layer.py`) extended for:
  - rejection of Cyrillic/raw candidate variants,
  - acceptance of valid Latin/Slovak lookup-ready candidate,
  - preservation of original multilingual text in `vstup.povodny_text`.

### Notes
- No DB migrations, no contact auto-create, no fuzzy matching.
- Existing Python source-of-truth preview/contact flow remains unchanged for valid payloads.

## 2026-04-11 — Session 014 — Invoice Phase 2 regression fixes (amount semantics + SK text boundary + PDF row alignment)

### Bug shape
- Voice/text phrases with multiplier semantics (e.g. `2 razy po 1500`) could be persisted as `quantity=2`, `total=1500`, causing wrong unit price derivation in PDF.
- `biznis_sk` service short text could still contain raw Cyrillic (`ремонт`) and leak into preview short title.
- PDF item rows with wrapped descriptions looked visually split because numeric columns sat too high relative to multiline description blocks.

### Root cause
- Amount pipeline had only one numeric `suma` path and derived `unit_price` as `total/quantity` without deterministic multiplier normalization.
- Invoice preview trusted `polozka_povodna` too directly, so multilingual/raw text could pass through instead of canonical Slovak term.
- Item-row vertical baseline used a static offset tuned for single-line rows.

### Decision
- Add optional invoice-only payload field `biznis_sk.cena_za_jednotku`, keep Python as numeric source of truth, and enforce deterministic normalization for `N × unit-price` phrases.
- Make preview short title prefer Slovak-normalized term (`termin_sluzby_sk` / deterministic canonical map), with fail-loud validation when `biznis_sk` text fields contain Cyrillic.
- Keep PDF design unchanged and fix only row measurement + numeric baseline helper logic for wrapped rows.

### Tests added/updated
- Amount semantics tests for:
  - `2 razy po 1500`
  - `2 kusy po 1500 eur`
  - `2x 1500`
  - `2 krát po 1500 eur`
  and fail-loud path for ambiguous multiplier hints.
- Service text normalization tests proving `biznis_sk` Cyrillic rejection and Slovak short-title in preview while preserving original multilingual `vstup.povodny_text`.
- PDF layout helper tests for wrapped row height expansion and numeric baseline staying inside row block.

## 2026-04-12 — Session 019 — Deterministic top-level create-invoice pre-router

### Goal
- Add deterministic pre-routing before current invoice Phase 2 parsing so create-invoice starts are recognized reliably from multilingual/noisy action verbs.
- Reserve edit-intent verbs for future branching without implementing edit flow now.

### What changed
- Added top-level deterministic intent detector in `bot/handlers/invoice.py`:
  - normalizes first action tokens (Latin diacritics-safe + Cyrillic-safe),
  - maps supported Slovak/Ukrainian/Russian create verbs to single intent `create_invoice`,
  - recognizes reserved edit placeholders (`upraviť/upravit/управить/исправь/отредактируй`) as `edit_invoice`.
- Inserted pre-router guard at the start of `process_invoice_text(...)`:
  - `edit_invoice` is explicitly blocked from entering current create flow,
  - current create Phase 2 flow is kept unchanged after routing.
- Added focused tests in `tests/test_invoice_intent_prerouter.py` covering required mixed/noisy create examples and ensuring edit-like verbs are not misrouted into create.

### Notes
- No invoice parsing logic moved into intent layer.
- No edit flow implemented; only placeholder recognition for future branching.

## 2026-04-12 — Session 020 — Intent pre-router final minimal verb set (create/edit/send)

### Goal
- Extend deterministic top-level invoice intent pre-router to explicitly separate create/edit/send starts before Phase 2 parsing.

### What changed
- Added deterministic `send_invoice` placeholder intent and `unknown` fallback return in `_detect_invoice_intent(...)`.
- Extended create verb set with required `сделать` and ensured all required create/edit/send verbs are normalized and recognized.
- Updated pre-routing in `process_invoice_text(...)` so both reserved `edit_invoice` and `send_invoice` are blocked from entering current create flow.
- Extended focused tests to cover required create/edit/send examples plus misrouting guards proving edit/send verbs never call Phase 2 parser.

### Notes
- No edit flow or send flow implementation added.
- Existing create flow after routing remains unchanged.

## 2026-04-12 — Session 021 — Unified bounded semantic resolver + contact intake with contract PDF branch

### Goal
- Align runtime with documented LLM orchestrator contract: one bounded semantic resolution layer for top-level action, in-state decisions, and reusable value canonicalization contract.
- Add `add_contact` runtime path for text/voice and document-assisted intake while preserving Python execution authority and fail-loud behavior.

### What changed
- Added reusable semantic resolver service (`bot/services/semantic_action_resolver.py`):
  - bounded API: `context_name` + `allowed_actions/values` + user text + optional context,
  - structured output contract (`canonical_action` or `unknown`),
  - runtime guard: Python validates/executes, LLM only canonicalizes,
  - minimal deterministic fallback for resilience when LLM is unavailable.
- Integrated semantic resolver into invoice runtime:
  - top-level routing now resolves `create_invoice` / `add_contact` / `send_invoice` / `edit_invoice` / `unknown`,
  - preview confirmation now semantic `ano` / `nie`,
  - post-PDF decision now semantic `schvalit` / `upravit` / `zrusit`.
- Added top-level semantic text entry handler (non-command text in idle state) to route through unified runtime path.
- Added contact intake runtime extensions in `bot/handlers/contacts.py`:
  - new intake states for missing-fields clarification and confirmation,
  - Slovak fail-loud prompts for missing critical fields,
  - semantic yes/no confirmation before DB save,
  - reuse of existing `ContactService.create_or_replace(...)` persistence.
- Added document intake service (`bot/services/document_intake.py`):
  - detects and downloads Telegram attachment,
  - handles text-PDF extraction path,
  - distinguishes scan-PDF (no text layer) and returns explicit fallback status,
  - unsupported type handling.
- Added contact field extraction service (`bot/services/llm_contact_parser.py`):
  - bounded structured extraction target for company/contact fields,
  - optional role-ambiguity signal,
  - deterministic fallback parser for critical fields.
- Extended voice routing (`bot/handlers/voice.py`) so voice also routes in contact intake states (`missing`, `confirm`) and does not leak back into invoice flow.

### OCR/vision note
- Scan-PDF branch is implemented as explicit detection + fail-loud user message + pluggable fallback point.
- Full OCR runtime is not wired in this session due current project constraints/tooling baseline.

### Tests
- Added/updated tests for:
  - semantic top-level action resolver and in-state mapping,
  - voice routing into contact clarification state,
  - contact intake with missing email/address clarification,
  - document intake branches: text-PDF, scan-PDF detection, unsupported type,
  - invoice post-PDF cleanup regressions retained in focused suite.

## 2026-04-12 — Session 022 — Stabilization fixes for unified semantic/contact intake patch

### Goal
- Close concrete correctness gaps before merge without redesigning architecture.

### Fixes
- Tightened top-level fallback priority in semantic resolver:
  - reserved `edit/send` stay higher priority than generic invoice nouns,
  - `create_invoice` keeps precedence over `add_contact` when invoice evidence is present,
  - `add_contact` now requires explicit add/store verb + contact/company target evidence.
- Prevented accidental contact import from random idle documents:
  - document intake now starts only when caption/intent semantically resolves to `add_contact`,
  - otherwise bot responds with bounded Slovak guidance and does not guess side effects.
- Preserved explicit company hint path:
  - added deterministic hint extraction from text/caption,
  - passed hint into contact draft extraction.
- Fixed deterministic `ic_dph` extraction bug:
  - extractor now returns actual VAT value token (e.g. `SK1234567890`) instead of label fragment.
- Extended focused regression tests for:
  - fallback top-level create/edit/send/unknown behavior with `api_key=None`,
  - create-vs-add_contact misroute guard when company token is present,
  - idle document rejection (no implicit contact intake),
  - company_hint propagation path,
  - deterministic `ic_dph` extraction correctness.

## 2026-04-12 — Session 023 — Contact wizard step-1 dual input (text or PDF)

### Goal
- Reuse existing `/contact` onboarding UX naturally for semantic `add_contact` while allowing contract PDF as an alternative input at step 1.

### What changed
- `start_add_contact_intake(...)` now enters the existing contact wizard at step 1 instead of launching separate intake UX.
- Step 1 prompt changed to dual-input Slovak wording:
  - `1/7 Zadajte názov firmy odberateľa alebo pošlite zmluvu/PDF.`
- Added dual-step handler (`ContactStates.name_or_document`) so first input can be:
  - text company name -> continue existing 2/7..7/7 manual wizard,
  - PDF/document -> branch into extraction draft flow, then missing-fields/confirm path.
- Kept idle-document safety guard: document is only imported when semantic intent resolves to `add_contact`; otherwise bounded guidance is returned.
- Updated focused tests to cover wizard entry behavior and preserved document extraction regressions.

## 2026-04-12 — Session 024 — Contact onboarding order fix: manual company name first

### Goal
- Correct add-contact onboarding sequence so company name is entered manually first, then user chooses source via next input (PDF or IČO), while preserving semantic/document safety improvements.

### What changed
- Contact flow state order updated to `name_hint -> source_after_name -> (PDF extraction branch OR manual ICO branch)`.
- `start_add_contact_intake(...)` now only enters onboarding and sends:
  - `V poriadku, vytvoríme nový kontakt. Najprv napíšte názov firmy.`
- Company hint is stored from manual text (`contact_company_hint`) and reused for PDF extraction even when PDF has no caption.
- After company name step bot prompts:
  - `Pošlite zmluvu/PDF alebo zadajte IČO.`
- In `source_after_name`:
  - text is treated as IČO (validated), then manual wizard continues from DIČ,
  - document goes through existing intake/extraction flow.
- Voice safety tightened:
  - `name_hint` and `source_after_name` reject voice with bounded Slovak messages,
  - existing invoice and intake_missing/intake_confirm voice routing preserved.
- Role ambiguity path now preserves partial extracted draft in FSM state instead of dropping extracted fields.

### Tests
- Added/updated focused tests for:
  - semantic add-contact entry to `name_hint`,
  - name-hint transition and company-hint storage,
  - source-after-name manual IČO path valid/invalid,
  - source-after-name PDF path with no caption using saved company hint,
  - role-ambiguity partial draft retention,
  - voice restrictions in `name_hint` and `source_after_name`.

## 2026-04-12 — Session 025 — Invoice Phase 2 service-slot repair and clarification retention

### Goal
- Fix Phase 2 invoice payload handling so noisy/non-Slovak `biznis_sk.polozka_povodna` does not drop full draft when service meaning is recoverable, and add slot-level clarification path when only service term is unresolved.

### What changed
- Added deterministic service-slot repair in `validate_invoice_phase2_payload(...)`:
  - canonical service term is now resolved primarily from `biznis_sk.termin_sluzby_sk` (fallback to `polozka_povodna`),
  - when canonical term is recognized, payload is repaired in-place (`termin_sluzby_sk` canonical, safe Slovak `polozka_povodna`) instead of fail-loud on Cyrillic/noisy item text,
  - when service term remains unresolved after repair attempt, validator raises structured `LlmInvoicePayloadError` with `error_code=service_term_unresolved` and partial payload for continuation.
- Improved Phase 2 invalid-payload observability in invoice handler:
  - added focused debug log event `invoice_phase2_payload_invalid` with raw/repaired service fields and structured error code.
- Added slot-level clarification FSM branch:
  - new state `InvoiceStates.waiting_service_clarification`,
  - when parser returns `service_term_unresolved`, bot preserves partial draft (`invoice_partial_draft`) and asks Slovak-only clarification: `Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.`,
  - clarification reply is normalized via existing service normalizer and flow continues directly to preview build without restarting full invoice input.

### Tests
- Updated focused tests to cover:
  - repair path for noisy/Cyrillic-like service item tokens (`ремонт`, `управы`, `оправы`) with recognized service concept,
  - unresolved service slot structured error behavior,
  - partial draft retention + clarification prompt path in `process_invoice_text`,
  - continuation from clarification reply to preview build without full restart.

## 2026-04-14 — Session 026 — Audit-only map for confirmation/decision resolver paths

### Goal
Produce a code-evidenced audit map for bounded short in-action confirmations/decisions (invoice preview, post-PDF decision, contact confirms, related deterministic confirms), including voice/STT routing and contract gaps before any runtime patch.

### Changes
- added audit document `docs/llm/Confirmation_Decision_Audit_2026-04-14.md` with:
  - resolver/prompt inventory,
  - voice call map,
  - contract-gap notes against bounded template,
  - STT-noise production-risk lens,
  - test coverage note and likely repair surface pointers.

### Notes
- Audit-only session: no runtime behavior changes.
- No architecture redesign introduced.

## 2026-04-14 — Session 027 — Conservative bounded resolver for short in-action confirmations/decisions

### Goal
Implement targeted runtime hardening for short confirmation/decision states so noisy/ambiguous STT transcripts resolve to `unknown` (retry), with no architecture redesign.

### Changes
- `bot/services/semantic_action_resolver.py`:
  - added dedicated strict resolver `resolve_bounded_confirmation_reply(...)` for short in-action confirmations/decisions;
  - resolver payload now explicitly includes:
    - `context_name`,
    - `expected_reply_type`,
    - `supported_input_languages=['sk','uk','ru']`,
    - `allowed_canonical_outputs`,
    - `user_input_text`;
  - added conservative deterministic fallback for bounded short replies:
    - accepts only clear one-token canonical equivalents,
    - ambiguous/noisy/off-target inputs return `unknown`;
  - left existing generic resolver and slot quantity/unit-price resolver intact.
- `bot/handlers/invoice.py`:
  - preview confirmation now uses strict bounded resolver (`yes_no_confirmation`);
  - post-PDF decision now uses strict bounded resolver (`postpdf_decision`);
  - existing retry UX/messages preserved.
- `bot/handlers/contacts.py`:
  - semantic intake confirm now uses strict bounded resolver (`yes_no_confirmation`);
  - existing retry UX/message preserved.
- tests:
  - added noisy transcript regressions (`Ah, não.`) for preview confirmation, post-PDF decision, and contact semantic confirm;
  - added guard that post-PDF noisy input does not trigger destructive cleanup;
  - added positive regression tests for strict bounded resolver canonical outputs.

### Notes
- No STT model/transport changes.
- No top-level action routing changes.
- No invoice amount semantics or service-alias flow changes.

## 2026-04-16 — Session 028 — Invoice service/customer bounded candidate migration batch

### Goal
Finish coherent migration of invoice slot resolution to bounded LLM contract for service/customer slots (including clarification and edit-replace service path), while keeping deterministic Python validation/state/side effects.

### Changes
- `bot/handlers/invoice.py`:
  - added bounded customer candidate resolver helper that:
    - builds allowed contact candidate set from supplier contacts,
    - includes deterministic normalized/compressed direct-match shortcut,
    - then uses bounded resolver (`resolve_semantic_action`) with strict allowed candidates and metadata,
    - returns exact contact or unresolved.
  - preview build path now applies bounded customer candidate selection when deterministic contact lookup is not exact/normalized single-match:
    - for `multiple_candidates`: bounded candidate set from lookup candidates,
    - for `no_match`: bounded candidate set from supplier contacts,
    - unresolved continues to slot clarification with bounded customer choices.
  - customer slot clarification now uses bounded candidate resolver (reusing bounded candidate set saved in FSM partial draft) instead of raw phrase heuristics as final chooser.
  - service slot clarification/edit service replacement continue using supplier alias bounded candidate contract (exact allowed alias or unknown).
- `bot/services/semantic_action_resolver.py`:
  - aligned resolver payload envelope with docs/llm template fields for bounded action/value resolution:
    - `context_name`,
    - `current_state` (when present in auxiliary context),
    - `supported_languages`,
    - `allowed_actions`,
    - `user_input_text`,
    - `expected_output`,
    - `auxiliary_context`,
    - `action_hints`.
- `bot/services/service_term_normalizer.py`:
  - marked as legacy migration helper (fallback/support only; not primary runtime resolver).
- tests:
  - added regression for DB alias `stavebné práce` with noisy input `stavbné práce` resolved through bounded allowed alias selection;
  - added coverage that noisy customer candidate resolves via bounded contact candidate set;
  - added coverage that customer clarification reuses bounded candidates from FSM partial payload.

### Notes
- Deterministic Python responsibilities preserved: cleaning/normalization, DB lookup, validation, FSM/state transitions, numbering/PDF and side effects.
- No hidden concept changes: migration keeps existing invoice workflow architecture and fail-loud behavior for unresolved slots.

## 2026-04-17 — Session 029 — Final cleanup of parser legacy customer gate + clarification seam

### Goal
Complete remaining cleanup seams from invoice service/customer bounded migration before merge readiness check.

### Changes
- `bot/services/llm_invoice_parser.py`:
  - removed legacy semantic phrase/prefix/blocklist customer gating in parser validation;
  - parser customer candidate validation now keeps only structural sanity checks (type, non-empty, max length, alphanumeric presence) and no longer rejects phrase-like candidates as semantic decision logic.
- `bot/handlers/invoice.py`:
  - removed dead duplicate `_SLOT_CUSTOMER` branch from `_apply_slot_clarification(...)`;
  - customer clarification runtime path remains single canonical bounded path via `process_invoice_slot_clarification(...)` + `_resolve_customer_candidate_bounded(...)`.
- `tests/test_invoice_phase2_ai_layer.py`:
  - updated parser tests to match new contract:
    - reject only structurally invalid customer candidates,
    - accept noisy phrase-like customer candidates for later bounded runtime resolution.

### Notes
- No architecture redesign.
- Service/customer runtime bounded resolution paths remain unchanged for create/clarify/edit.

## 2026-04-18 — Session 030 — Approval-step diagnostic trace for waiting_pdf_decision

### Goal
Add transparent runtime diagnostics for the post-PDF approval step (`waiting_pdf_decision`) and add narrow tests that expose bounded contract behavior and potential mismatch risks, without changing edit-flow or create/edit/PDF business logic.

### Changes
- `bot/handlers/voice.py`:
  - added diagnostic log `approval_voice_routing` for `waiting_pdf_decision` voice routing path with:
    - `request_id`,
    - `current_state`,
    - `recognized_text`,
    - `telegram_message_id`.
- `bot/handlers/invoice.py` (`process_invoice_postpdf_decision`):
  - added diagnostic request/response logs around bounded resolver call:
    - `approval_resolver_request`,
    - `approval_resolver_response`;
  - added branch decision log before each final branch:
    - `approval_branch_decision` with `branch_taken` in `{schvalit, upravit, zrusit, unknown}`;
  - added explicit unknown-gap log event:
    - `approval_unknown_contract_gap` with full resolver/branch context.
- `bot/services/semantic_action_resolver.py`:
  - extended `resolve_bounded_confirmation_reply(...)` with optional `diagnostics` payload output (backward compatible);
  - diagnostics include:
    - `raw_model_output`,
    - `normalized_output`,
    - `fallback_used`,
    - `fallback_output`;
  - fallback/exception path now populates diagnostics deterministically for traceability.
- tests:
  - `tests/test_invoice_intent_prerouter.py`:
    - added post-PDF bounded synonym matrix assertions (canonical + multilingual/noisy variants).
  - `tests/test_invoice_state_decisions.py`:
    - added runtime branch regression for multilingual destructive synonyms (`отменить`, `delete`);
    - added unknown-contract-gap logging regression (`unknown` does not auto-cancel).
  - `tests/test_voice_state_routing.py`:
    - added voice parity regression for `waiting_pdf_decision` to confirm STT text pass-through and `approval_voice_routing` logging.

### Notes
- This session is diagnostic-only and keeps existing runtime behavior unchanged.
- No hidden concept changes, no edits to invoice edit subflows or PDF generation logic.
