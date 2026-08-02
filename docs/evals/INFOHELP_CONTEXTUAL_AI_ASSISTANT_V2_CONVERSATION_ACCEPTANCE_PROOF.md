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
