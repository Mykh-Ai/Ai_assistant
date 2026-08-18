# Invoice Edit Direct Action Conversation Acceptance Proof

- Architecture proof: `docs/architecture/invoice_edit_direct_action_architecture_design_proof.md`
- Working state: feature commit `4460650`, merged into `main` as `63a20c9` on 2026-08-18.
- Environment: local pytest with mocked STT/LLM/PDF boundaries where named, followed by production container deployment health verification; no DB migration.
- Declared AI maturity: existing bounded semantic canonicalization; no new Product Truth maturity level.
- Product Truth: `edit_existing_invoice` remains `supported` with precision/setup limitations.

## Public-entry traces

### IE-DIRECT-001 — preview edit, direct delivery date text

- Entry: invoice preview decision `upraviť`.
- Exact next input: `Датом додання`.
- Resolver result: `edit_invoice_delivery_date` from the unified allowed operation set.
- State sequence: `waiting_confirm -> waiting_edit_scope -> waiting_edit_invoice_date_value -> waiting_confirm`.
- Date input: `15 августа`, bounded normalization to `15.08.2026`, Python storage normalization to `2026-08-15`.
- Effect: draft only; no invoice row/PDF before final approval.
- Evidence: `test_preview_edit_direct_delivery_date_text_skips_scope_loop_and_returns_updated_preview`.
- Result: pass.

### IE-DIRECT-002 — operation matrix

- Entry: unified draft edit state.
- Inputs: every registered invoice field and existing-item field canonical operation.
- Result: each concrete operation enters its exact shared value owner without a mandatory scope/action submenu.
- Evidence: `test_edit_scope_direct_operations_cover_every_supported_sublevel`, `test_edit_scope_direct_clear_item_details_completes_without_extra_submenu`.
- Result: pass.

### IE-DIRECT-003 — multi-item continuation

- Entry: direct `edit_item_quantity` with two draft items.
- State sequence: `waiting_edit_scope -> waiting_edit_item_target -> waiting_edit_item_numeric_value`.
- Python preserves the operation while asking only for the target.
- Evidence: `test_direct_multi_item_operation_asks_only_for_target_then_continues`, `test_invoice_edit_item_target_button_continues_preserved_operation`.
- Result: pass.

### IE-DIRECT-004 — voice convergence

- Entry: authorized STT while `waiting_edit_scope`.
- Transcript: `Датом додання`.
- Result: the same invoice scope handler and operation owner enter `waiting_edit_invoice_date_value`; `voice.py` owns no business phrase dictionary.
- Evidence: `test_voice_waiting_edit_scope_direct_delivery_date_skips_scope_loop`.
- Result: pass.

### IE-DIRECT-005 — button convergence and lifecycle

- Entry: owned inline callback from the current edit prompt.
- Result: canonical delivery-date button reaches the same operation owner; item-target button resumes the preserved operation; Back returns to the unified menu; Cancel clears state.
- Lifecycle: handled and owned stale callbacks remove markup; wrong actor retains markup and has no effect.
- Evidence: `test_invoice_edit_delivery_date_button_uses_shared_operation_owner`, `test_invoice_edit_item_target_button_continues_preserved_operation`, `test_invoice_edit_back_button_returns_to_unified_menu`, `test_invoice_edit_cancel_button_clears_state_and_owned_markup`, `test_invoice_edit_owned_stale_callback_clears_state_and_markup`, `test_invoice_edit_callback_wrong_actor_keeps_keyboard_and_state`.
- Result: pass.

### IE-DIRECT-006 — unknown and old journeys

- Unknown edit input retains the active edit state, re-renders the bounded menu, and performs no write.
- Generic `faktúra`/`položka` compatibility routing remains available.
- Existing draft/persisted edits, voice routes, DecisionResolver callbacks, Product Truth and InfoHelp tests remain green.
- Evidence: focused regression suite listed below.
- Result: pass.

## Evidence summary

- Focused invoice/voice/callback regression: `173 passed` before the final callback-matrix additions; the added invoice-edit callback subset then passed `7 passed`.
- Product Truth + InfoHelp + invoice/voice/callback regression: `308 passed in 63.96s`.
- Full repository suite: `2556 passed, 7 subtests passed in 497.69s`.
- Production deployment health: pass at merge SHA `63a20c9`; container running with restart count `0`, and startup/polling logs present.
- Production Telegram journey smoke: not run; no synthetic invoice or business write was created during deployment verification.

## Design-to-code mapping

- Unified bounded resolver: `bot/handlers/invoice.py::_resolve_invoice_edit_scope`.
- Shared operation dispatch: `invoice_edit_scope`, `invoice_edit_invoice_action`, `invoice_edit_item_action`, `invoice_edit_item_target`.
- Inline keyboards: `bot/keyboards/invoice_edit.py`.
- Callback ownership/lifecycle: `bot/handlers/decision_callbacks.py::invoice_edit_callback`.
- Voice convergence: `bot/handlers/voice.py` routes STT into the same handlers.
- Global cancel/stale cleanup: `bot/services/active_fsm_guard.py`, `bot/handlers/state_control.py`.
- Product Truth/InfoHelp: existing `edit_existing_invoice` record/copy updated without status change.

## Verdict

`deployed_pending_interactive_smoke`. Automated coverage and production startup/polling health pass; the exact owner journey in Telegram remains the final interactive acceptance step.
