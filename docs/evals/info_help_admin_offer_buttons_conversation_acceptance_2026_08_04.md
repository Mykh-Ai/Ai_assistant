# InfoHelp Admin-Offer Buttons Conversation Acceptance — 2026-08-04

Status: `deployed_renderer_smoke_passed_pending_live_telegram_retest`

## Scope

This proof covers only the bounded handoff from an exact unsupported
Contextual InfoHelp result to the existing customization-request preview or the
existing main menu. It adds no canonical top-level action, Product Truth
capability, DB schema, admin notification, or business side effect.

## Acceptance journeys

| Journey | Input / choice | Expected route and visible result | State / effects | Automated evidence |
|---|---|---|---|---|
| Unsupported receipt deletion | `Видалити чек` or `Видалити останній чек` (text or STT), including `intent_complete=false` | Truthful unsupported answer plus `Požiadať správcu` and `Hlavné menu`; no model-generated document clarification | `waiting_admin_offer_decision`; zero saved requests; no receipt/invoice deletion | `test_receipt_delete_execution_request_checks_exact_support_before_missing_slots`; `test_receipt_delete_capability_question_blocks_false_invoice_delete`; `test_correction_negates_invoice_and_blocks_delete_flow` |
| Ask admin | `Požiadať správcu` callback | Existing Slovak request preview with `Schváliť / Upraviť / Zrušiť` | `waiting_preview_decision`; zero saved requests | `test_info_help_admin_offer_button_opens_existing_preview_without_saving` |
| Return to menu | `Hlavné menu` callback or active `/menu` | Existing `MENU_MESSAGE` owner | FSM cleared; zero saved requests; owned offer markup removed | `test_info_help_main_menu_button_clears_offer_and_uses_existing_menu`; `test_info_help_offer_menu_control_removes_owned_inline_keyboard` |
| Wrong actor/state | callback without the owning FSM context | Stale-choice alert | no save; no state change; foreign/unproven markup is not edited | `test_info_help_offer_wrong_state_cannot_clear_another_users_keyboard` |
| Stale/cleanup failure | expired owned callback or Telegram edit failure | fail closed or continue the already selected safe route | no premature save; cleanup failure logged; route not rolled back | `test_stale_info_help_offer_expires_without_saving_and_removes_owned_keyboard`; cleanup-failure tests |
| Supported neighboring action | `Видалити фактуру 10` | Existing invoice owner and deletion confirmation | no InfoHelp offer; no deletion before confirmation | `test_supported_invoice_delete_reaches_existing_owner_once_without_infohelp` |

## Persistence boundary

Building the offer stores only a redacted, owner-bound draft in FSM state.
Clicking `Požiadať správcu` still does not write a request. The existing
preview's separate `Schváliť` decision remains the only entry to
`CustomizationRequestService.create_confirmed_customization_request(...)`.

## Pending evidence

A live Telegram smoke must confirm both visible buttons, opening the
existing preview without creating a row, and returning to the current main menu
without creating a row. Until then the runtime status is
`deployed_pending_live_smoke`.

## Automated verification

- Regression repair focused suite on 2026-08-05: `271 passed`. This proves
  text/voice execution requests with the production-observed
  `intent_complete=false` shape are classified against the exact registry
  before missing-slot clarification. Deployment and repeated live Telegram
  smoke remain pending.
- Full repository verification for the final regression repair and shared
  unsupported-business-feature copy: `2535 passed, 7 subtests passed in
  498.68s`. `python -m compileall -q bot` and
  `git diff --check` also passed; only expected Windows line-ending warnings
  were reported.
- Focused routing/callback/FSM suite: `53 passed`.
- Expanded neighboring InfoHelp, voice, customization, and invoice-confirmation
  suite: `291 passed, 7 subtests passed` before the final message-ownership
  case was added; that case passed in the focused rerun.
- Full repository suite on the final code: `2486 passed, 7 subtests passed in
  465.19s`.

## Delivery and deployment evidence

### 2026-08-05 unsupported-routing regression repair

- Runtime commit `4cddb9353931d1951f1a5ee2a9a73e9c921b3053` was
  published through GitHub API PR `#98` and merged to `main` as
  `f09cdb7601e73bb18e1a1075b292c0270bbf4e04`.
- Before deployment, `/bot/repo` was clean at `328d1b7`. A timestamped SQLite
  and `.env` backup was created under
  `/bot/backups/infohelp-v2-routing-20260805T080320Z` with mode `0600` files;
  both source and backup databases returned `PRAGMA quick_check=ok`.
- Production fast-forwarded to the exact merge SHA and rebuilt successfully.
  `fakturabot` and `fakturabot-cloudflared` are `Up`, FakturaBot restart count
  is `0`, and logs show `FakturaBot starting`, `Start polling`, and
  `Run polling for bot` without a Telegram polling conflict.
- In-container `python -m compileall -q /app/bot` passed. The production image
  intentionally has no pytest package, so server pytest was not available;
  repository verification remains the final full suite of `2535 passed, 7
  subtests passed`.
- A deterministic renderer smoke inside the deployed container for
  `receipt + delete` returned the exact unsupported, no-substitute,
  business-feature, administrator-request, and save-only-after-confirmation
  wording. It made no LLM call and no business/storage write.
- Post-deploy live SQLite returned `quick_check=ok`; the server checkout is
  clean at the deployed merge SHA. No environment, DB/schema, storage layout,
  access, or persisted business data was changed by this deployment.
- A repeated human Telegram message is still required to close transport/UI
  acceptance for the originally observed journey.

- Runtime commit: `feda8fb04290f050e8b6657c7397662e2041f011`.
- PR: `#83`, exact head merged to `main`.
- Merge/deployed code SHA:
  `0ab1197fa90e3e24d63cee89dd57290a93f4d7c5`.
- Production `/bot/repo` was clean and fast-forwarded with `--ff-only`.
- Production compose rebuild succeeded; bot and tunnel containers are `Up`,
  bot restart count is `0`, startup/polling logs are healthy, and no Telegram
  polling conflict was observed.
- In-container `python -m compileall -q /app/bot` passed.
- No `.env`, DB/storage, or unrelated server-project change was made.
