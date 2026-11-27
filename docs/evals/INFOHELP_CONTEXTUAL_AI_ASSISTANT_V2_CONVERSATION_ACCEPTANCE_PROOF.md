# InfoHelp Contextual AI Assistant V2 Conversation Acceptance Proof

## Verdict

`implemented_pending_interactive_acceptance`

Initial audited base: `3cd85de54015a8bf5b8de01bcd24a5544db7af79`. Final refreshed delivery base: `4ab8f5bde30104b817d2cdfeca15d7f89044828b`.
Rollout default: `disabled`. No deployment, migration, persistent chat history, or production access occurred.

## Regression-first evidence

Before production code, the focused command:

```text
python -m pytest -q tests/test_info_help_contextual_v2.py tests/test_invoice_reference_continuation_v2.py
```

failed during collection with two expected errors: the new bounded InfoHelp contract and `InvoiceReferenceContinuationStates` did not exist. After implementation, the expanded contextual journey set passed (`19 passed in 6.36s` at the first green checkpoint).

## Public-entry trace

```text
authorization
-> known command / active FSM ownership
-> existing top-level resolver
-> rollout + conditional V2 gate
-> exactly one contextual InfoHelp JSON call
-> Python parser + exact semantic registry + Product Truth lookup
-> answer / clarification / existing owner / invoice-reference continuation
-> existing confirmation and side-effect guard
```

Text and voice use the same `process_invoice_text` and invoice-reference owner. Unknown commands enter only after known command routers. Active FSM help does not clear or replace the state.

## Mandatory journey matrix

| # | Journey | Automated evidence | Effect/state result |
|---|---|---|---|
| 1 | Ukrainian receipt-delete capability question | `test_receipt_delete_capability_question_blocks_false_invoice_delete` | unsupported exact intent; no state/effect/invoice prompt |
| 1a | Ukrainian receipt-delete execution request with `intent_complete=false`, including `Видалити останній чек` | `test_receipt_delete_execution_request_checks_exact_support_before_missing_slots` for text and voice | exact support is checked before missing-slot clarification; unsupported offer; model clarification is not shown; no saved request or deletion |
| 1b | Other explicit unsupported triples across contacts, incoming invoices, and supplier profiles with incomplete/missing-slot model output | `test_any_exact_unsupported_action_is_checked_before_completeness_slots` | the same registry-first invariant applies across domains; no phrase/object-specific runtime exception, saved request, or business effect |
| 2 | English `delete receipt` | exact-registry/parser and unsupported journey coverage | no nearest delete action; narrow unsupported response |
| 3 | correction: receipt, not invoice | `test_correction_negates_invoice_and_blocks_delete_flow` | negated invoice blocks invoice delete |
| 4 | delete invoice without reference, then `10` | `test_supported_invoice_delete_without_reference_enters_continuation_after_v2`; continuation tests | waiting reference; next input state-owned; confirmation still required |
| 5 | direct invoice reference | existing invoice intent tests plus shared `_execute_invoice_reference_action` | same lookup/preview owner |
| 6 | edit contact | `test_contact_edit_never_becomes_supplier_profile_edit` | unsupported; supplier edit not called |
| 7 | own profile vs contact address | exact semantic registry and contact/profile negative-space tests | only exact supplier-profile edit is eligible |
| 8 | incomplete contact intent | bounded incomplete-intent response policy | contact-only clarification; no unrelated actions |
| 9 | `/contat` | command payload/route tests | probable known command suggestion; no execution |
| 10 | Cyrillic unknown command | same bounded command route; interactive language quality pending | no silence/invoice route |
| 11 | explicit Telegram reply | `test_info_help_explicit_reply_v2.py`; payload test | same-chat our-bot quote included independently of TTL |
| 12 | active action status | active descriptor/guard tests | state unchanged; real action/step; main-menu control |
| 13 | expected input question | `test_active_fsm_help_keeps_state_and_calls_contextual_assistant_once` | state unchanged; actual expected input |
| 14 | ordinary continuation value | `test_next_reference_is_consumed_by_continuation_owner` | passes to state owner; no idle fallback |
| 15 | vague destructive input | `test_vague_delete_is_clarified_without_destructive_route` | clarification; no destructive state/effect |
| 16 | real callback actor | `test_callback_message_adapter_uses_human_actor_and_source_chat` | actor is `callback.from_user`; chat/sends use source message |
| 17 | stale/forged callback | existing decision callback stale/invalid suites | fail closed; no effect |
| 18 | explicit overview | existing InfoHelp overview tests | broad overview only when requested |
| 19 | genuinely unclear | parser/fallback tests | short fallback; no catalogue/buttons/effect |
| 20 | one-call proof | `test_resolver_makes_exactly_one_enhanced_infohelp_call` | exactly one enhanced call; no retry/second recovery |

## Privacy, ownership, and negative-space evidence

- Context is in-process only, 3+3 turns, ten-minute TTL, user/chat/workspace isolated, restart-loss by construction.
- Capture occurs only inside authorized runtime routes; voice is captured once after non-empty STT through the shared route; only V2 user-visible bot replies are recorded.
- Explicit reply requires same chat, bot author, and this bot's ID when available.
- Product Truth is derived from the existing registry and checked again by Python.
- `receipt/delete`, `contact/edit`, capability questions, negated objects/operations, vague destructive input and account deletion offers fail closed.
- No PR #63 recovery handler/service, generic callback, action-label dispatch, RAG, vector store, log reconstruction or DB chat-history schema exists.

## Production pilot evidence and fail-closed repair

PR #70 was deployed disabled-first and enabled for `admin_pilot` after a verified backup. The first server live-LLM case failed closed because an enum description was copied as a value and an untrusted primary invoice diagnostic displaced the exact receipt object. Rollout returned immediately to `disabled`; the bot and database remained healthy and no business side effect occurred. The contract repair replaces prose placeholders with literal allowed values and explicitly makes the primary result diagnostic-only. Production acceptance remains pending until the repaired server suite and real Telegram journeys pass.

Focused repair verification: `156 passed in 7.14s`; this is repository evidence, not replacement for interactive Telegram acceptance.

A subsequent server batch proved cases 1-4 and then failed closed when the model dropped explicit numeric reference `10`; rollout again returned to `disabled` with the database unchanged. The follow-up contract adds paired absent/present invoice-reference examples. This remains pending evidence until the complete repaired batch passes.

The next throttled batch proved cases 1-10 and then found that the model could omit an already proven explicit-reply boolean. Python now preserves validated same-bot reply ownership and `active_fsm_help` state context after parsing. The attempt rolled back to `disabled` with the database unchanged; full repaired batch evidence remains pending.

On merge SHA `59d52e7`, combined server batches passed cases 1-20 with zero DB writes and zero Telegram business effects; DB integrity/counts stayed unchanged. A qualitative audit then rejected the result as final because the quoted-message journey would still hit generic unclear copy and the vague-delete assertion did not prove primary/exact mismatch safety. The pilot returned to `disabled`; targeted handler repairs and acceptance tests now own those two gaps. Real Telegram interactive acceptance remains pending.

Final repair PR #79 deployed at `4de87cb` disabled-first. Targeted production handler smoke then proved useful quoted-message explanation and no continuation/dispatch for vague destructive input; rollout was restored only to `admin_pilot`. Combined server evidence covers cases 1-20 with no DB write or Telegram business effect, and the final DB guard remained `quick_check=ok` with unchanged supplier/invoice counts. Repository verification ended at `162 passed` focused and `2473 passed, 7 subtests passed` full.

This closes the server harness acceptance for the controlled admin pilot, not real Telegram UI/transport acceptance. No human Telegram message was sent by the harness, and the production pilot must not be described as generally enabled.

## Pending interactive acceptance

After review and a deliberate `admin_pilot` configuration change, an authorized administrator must run the 20 journeys in real Telegram, with special attention to Ukrainian/Russian/mixed STT quality, old quoted-message behavior, visible keyboard lifecycle, invoice ambiguity/not-found retries and callback actor/workspace identity. Production acceptance must not be claimed before that pilot passes.

## Final repository verification

- Regression-first run: two expected collection errors for missing V2 contracts.
- First green contextual checkpoint: `19 passed in 6.36s`.
- Final focused InfoHelp/Product Truth/continuation run: `155 passed in 8.13s`.
- Adjacent invoice/Product Truth compatibility run: `254 passed in 41.98s`.
- Consolidated adjacent invoice/voice/FSM/contact/profile/callback/access/workspace/state/customization run: `502 passed, 7 subtests passed in 173.70s`.
- Final full suite on refreshed base: `2463 passed, 7 subtests passed in 751.20s`; no skipped tests were reported.
- `python -m compileall -q bot`: passed.
- `git diff --check`: passed (line-ending conversion warnings only).

## 2026-08-05 primary-bundle regression amendment

The production-observed voice question
`На яку суму я виставив фактур цього року?` now proves this order:

1. STT output enters `process_invoice_text`.
2. The top-level LLM bundle runs with `llm_first=True` and returns
   `invoice_analytics` + `business_action`.
3. Python validates the action and routes to the read-only analytics owner.
4. Contextual InfoHelp is not called and cannot return an unclear fallback.

The request-correlated `top_level_bundle_result` event records the direct
route's validated action, `routing_kind`, resolution source, and bounded raw
bundle JSON only under debug transparency, so bypassing InfoHelp does not hide
the first model response.

Additional automated evidence proves that a capability question is converted
by the primary bundle to `unknown` + `capability_or_howto`, then one InfoHelp
call answers `invoice_analytics` directly from Product Truth even though that
action is absent from the narrower InfoHelp execution registry. Validated
InfoHelp recovery behaves identically at model confidence `0.0`; no confidence
threshold remains. Active-FSM help keeps the state and now uses the second
call's bounded expected-input/command-typo result instead of discarding it.

Status remains `partial` Level 2 pending a repeated real Telegram smoke after
deployment. No persistence, tenant, authorization, confirmation, or business
side-effect contract changed.

Repository evidence for this amendment: focused adjacent suite `370 passed in
46.93s`; complete suite `2528 passed, 7 subtests passed in 491.83s`;
`python -m compileall -q bot` passed.

After adding direct primary-bundle observability, the exact final code was
reverified: focused route suite `264 passed in 43.48s`; complete suite `2528
passed, 7 subtests passed in 492.83s`; compileall and diff checks passed.

PR `#95` merged the exact tested head as
`7e3d0556c235ce8b5c99cacc2493ad4f0502ba23`. Production was rebuilt on that
SHA with both compose services up, bot restart count `0`, in-container compile
success, and active Telegram polling. Runtime status is
`deployed_pending_live_smoke`; the repeated real voice question remains the
final interactive acceptance step.

## 2026-11-15 voice acceptance set

The ZIP contains 15 numbered Higgsfield clips converted to Ogg/Opus. The
runtime STT was exercised directly with the clips and replacements. Telegram
voice delivery remains open. The live text results are recorded below.
Project-history prompts include paraphrases of the recorded journeys.

| Clip | Source | Spoken input | Expected visible outcome |
| --- | --- | --- | --- |
| 1 | New | Можу я дати бухгалтеру доступ, щоб він бачив тільки чеки мого профілю? | Explain the actual accountant/access options without granting access. |
| 2 | New | Як ти вибираєш категорію для чека, якщо там є і пальне, і кава? | Explain how category selection works without changing receipt data. |
| 3 | New | Що буде, якщо я випадково надішлю той самий чек двічі? | Describe the duplicate warning and any user confirmation. |
| 4 | New | Коли я позначаю фактуру оплаченою, ти перевіряєш, чи гроші надійшли в банк? | Explain that the bot's paid mark records a local status. |
| 5 | New | Чи можу я тут налаштувати графік поливу теплиці? | Answer the out-of-domain question without starting a workflow. |
| 6 | Current conversation | Скажи, у моєму активному профілі чеки йдуть на Google Диск? | Say whether the active profile archives receipts, using profile and upload evidence. |
| 7 | Current conversation | Всі мої чеки вже завантажені на Google Диск? | Give verified counts for the active profile or identify missing coverage. |
| 8 | Current conversation | Ako počítaš mesačné výdavky? Povedz mi vzorec a ukáž príklad. | Explain the month filter, document totals, currencies, and a worked example. |
| 9 | Current conversation | Що нового у ФактураБоті? Які функції додали останнім часом? | Give recent changes from the current build's user-facing release notes. |
| 10 | Project history | Скільки фактур ми виставили від початку цього року? | Count saved outgoing invoices issued in the calendar year. No deletion or PDF display. |
| 11 | Project history | На яку загальну суму я виставив фактури цього року? | Sum saved outgoing invoices for the year by currency. No deletion or PDF display. |
| 12 | Current conversation | Покажи мені останню фактуру. | Show the latest saved outgoing invoice for the active profile. No aggregate or delete. |
| 13 | Project history | Чи можу я видалити чек? | Explain the exact receipt deletion capability. Do not open invoice deletion. |
| 14 | Project history | Vymaž vystavenú faktúru číslo desať. | Only open the usual exact-invoice confirmation if the invoice exists. Cancel afterward. |
| 15 | Project history | Можеш зробити даньове признання на основі фактур і блочків? | Explain the tax-return boundary without creating an invoice or filing anything. |

The delete probe stops at the preview and then cancels. Record the deployed
version, exact input, STT transcript, visible response, fact source and
business/FSM outcome for each run. Do not score the fixture result as live.

### Live Telegram text results, deployed `3425a6d`

The 15 scenarios ran in the authorized Zevs s.r.o. chat. Scenario 7 was
verified in the preceding live dialogue. For scenario 14, the target was the
actual invoice `20260004`, and `/cancel` ended the flow without deletion.

| Scenario | Result | Visible evidence |
| --- | --- | --- |
| 1 | Failed | Generic processing error and `/menu` suggestion. Production diagnostics show an invalid `object_kind` in the contextual response. |
| 2 | Passed | Category suggestions appear during preview and need confirmation. |
| 3 | Incomplete | The reply mentioned separate confirmation and omitted the duplicate warning already implemented in intake. |
| 4 | Passed | Correctly distinguished the bot's local paid status from bank verification. |
| 5 | Outside-scope routing gap | Declined greenhouse scheduling but opened a proposal for administrator review. |
| 6 | Passed | Confirmed ZEVS receipt uploads and the last recorded date, 1 November 2026. |
| 7 | Passed | Reported 12 of 13 uploaded, one failure, zero pending and unknown. Matched the archive journal. |
| 8 | Passed | Explained month and currency grouping and gave `20 € + 30 € = 50 €`. |
| 9 | Stale content | Read the bundled 20 October note. It did not mention the November release. |
| 10 | Passed | Counted four 2026 outgoing invoices, matching the ZEVS database. |
| 11 | Passed | Reported EUR 12,981.00 for those invoices, matching the ZEVS database. |
| 12 | Incorrect heading | Displayed the correct latest invoice `20260004` and sent its PDF without asking for a number. The view began with “for editing”. |
| 13 | Passed | Clearly said receipt deletion is unsupported and did not open invoice deletion. |
| 14 | Cleanup failed | Asked for confirmation. `/cancel` acknowledged cancellation, and the invoice remained in the database. The previous inline `Vymazať` and `Zrušiť` buttons remained visible. |
| 15 | Passed | Declined to prepare a tax return and distinguished read-only document analytics. |

After the separate question about identifying the failed receipt, the
administrator offer consumed three new questions and repeated its buttons.
Its displayed `Hlavné menu` button returned a stale-decision message. Sending
`/menu` restored idle, and the three questions then received substantive
answers. No administrator request was saved during the test.

The local regression checks that two typed replies retain the original offer
message and its working menu button. The reminder has no inline markup. The
original menu callback clears the state and the inline keyboard without
saving a request. Live rechecking of the local repair remains open.

Real configured-model probes on an isolated local input path selected
`invoice_analytics` for `Koľko vystavených faktúr mám za tento rok?`,
`show_existing_invoice` with `invoice_selector=latest` for
`Покажи мені останню фактуру.`, and `delete_existing_invoice` for
`Удали выставленную фактуру номер 10.` The probes stopped before dispatch.
Selected audio transcripts also reached the local help routes. The original
deletion audio's unreliable transcription reached invoice viewing; the exact
text reached deletion. These runs provide routing evidence only.

### Google Drive receipt-folder sharing follow-up

Live on `3425a6d`, the question “Можу я дати бухгалтеру доступ до мого Google
Drive, щоб він бачив тільки чеки мого профілю?” received Slovak invoice archive
setup instructions. The reply omitted folder sharing, the Viewer role, and
the scope of existing permissions. This is a separate question from scenario 1,
which asks for access inside the bot.

The local handler regression sends the exact question through text and the STT
transcript entry and verifies a Ukrainian answer, folder-specific Viewer
instructions, the parent-access caveat, no offer buttons, idle FSM, and
byte-identical test SQLite. Four configured `gpt-4o` probes selected the
sharing topic and the correct Slovak, Ukrainian, Russian, or English locale.
Three contrast probes distinguished whether uploads run, all-receipt coverage,
and sharing inside the bot. The inside-bot probe verified routing only.
The external guide is [Google Drive Help](https://support.google.com/drive/answer/7166529).
An interactive Telegram check of the repaired build remains open.

### Product scope before action or review

The deployed greenhouse query used the capability-question branch without a
known product domain or capability and opened an administrator offer. The
local route separates scope and intent and requires an in-scope result before
idle action recovery or a review offer. Older payloads with no scope and
unmatched capability questions end in clarification.

The local configured-model journey sent questions through the primary
resolver, InfoHelp and the actual handler with test messages and test state.
Weather, irrigation, sports reservations, and an aquarium question carried
as an STT transcript received scoped declines with no keyboard or draft.
Google Drive folder sharing produced the expected steps. A concrete monthly
receipt-report delivery request produced the confirmation-gated review offer.
The first pass exposed an invoice how-to incorrectly entering invoice creation.
After correcting primary intent precedence, two invoice how-to phrasings
returned the verified `/invoice` step without opening a flow.

After deployment, repeat with fresh multilingual inputs selected at test
time, including a genuine action using the same subject as a how-to question,
an out-of-domain request that mentions a product term, an eligible feature
proposal, and an active-state navigation request. Verify the actual Telegram
text and voice journeys and that declined queries create no buttons or draft.
