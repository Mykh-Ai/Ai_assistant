# INFOHELP_CONTEXTUAL_RECOVERY_V1 Conversation Acceptance Proof

Status: `interactive_acceptance_failed_and_runtime_rolled_back`

Runtime acceptance: `failed_with_confirmed_production_regressions`

Date: 2026-08-02

Baseline: `origin/main` at `465df389c1b0c6ad3281733fe7888f5b49122c1d`

## Architecture and privacy evidence

- Authorization is registered before incoming conversation capture; automated middleware-order and unauthorized-input tests pass.
- Context is process memory only, keyed by Telegram user/chat with workspace metadata, limited to three user and three bot turns, and expired after ten minutes.
- Context contains visible text, normalized channel, and visible inline-button labels only. Raw callback payloads, updates, files, media, database rows, tokens, logs, prompts, and external API responses are excluded.
- Outgoing capture requires an active authorized inbound turn and matching chat; background and cross-chat sends are excluded.
- Voice/STT text is captured once after successful non-empty transcription and before the shared active/idle routing owners.
- Completed start/menu/cancel, workspace switch, stale recovery, and full user deletion clear the relevant context.

## Conversation path evidence

| Path | Automated evidence | Accepted local behavior |
| --- | --- | --- |
| Text | `test_contextual_info_help_recovery.py`, `test_info_help_recovery_handlers.py`, `test_invoice_intent_prerouter.py` | Primary `unknown` makes at most one bounded recovery call and Python renders candidates, Product Truth, request preview, or the short fallback. |
| Voice/STT | `test_conversation_context.py`, `test_voice_state_routing.py` | Successful STT is stored once as `voice_stt` and converges on the same contextual owner without debug-log dependence. |
| Unknown command | `test_info_help_recovery_handlers.py`, `test_active_fsm_contextual_help.py` | Known commands retain priority; the last router catches unmatched slash commands; active unmatched commands are not consumed as business values. |
| Recovery button | `test_info_help_recovery_handlers.py`, `test_contextual_info_help_recovery.py` | Opaque token/index records validate actor, chat, workspace, TTL, single use, and Product Truth before existing-owner dispatch. |
| Active FSM help | `test_active_fsm_contextual_help.py`, `test_active_fsm_guard.py` | Bounded control tokens use Python state descriptors, preserve a fresh FSM, include `Hlavné menu`, and keep stale-state recovery first. |
| Unsupported/new request | `test_info_help_recovery_handlers.py`, `test_info_help.py` | Python renders current Product Truth or reuses the existing confirmation-gated customization preview; the model cannot claim support or save. |

## Model boundary evidence

The OpenAI call receives the current input, normalized channel, up to six sanitized visible recent turns, active descriptor when present, canonical action metadata, neighboring actions, Product Truth metadata, and explicit no-execution rules. The strict output fields are `recovery_outcome`, `failure_cause`, `action_id`, `candidate_action_ids`, `capability_id`, `object_domain`, `operation`, `refers_to_active_flow`, `confidence`, and `needs_clarification`.

Python rejects unknown enums/IDs, cross-domain candidates, more than four candidates, invalid JSON, timeouts, and transport failures. The call has a timeout, no retry loop, and no user-facing free-text output.

## Verification results

- Focused contextual/context/FSM/handler tests: `43 passed in 4.10s`.
- Adjacent routing/FSM/voice/InfoHelp/Product Truth/callback/state/workspace tests: `508 passed in 66.29s (0:01:06)`.
- Complete Python suite: `2467 passed, 7 subtests passed in 503.47s (0:08:23)`.
- `python -m compileall -q bot`: passed.
- `git diff --check`: passed (Git emitted only an LF-to-CRLF working-copy warning for this Windows worktree).

## Deployed runtime verification

- PR `#63` merged at `ec7c5696ec6b73b6e0a90c38ce3a1a1a5f8bae89`; `/bot/repo` was clean and synchronized to that exact SHA before deployment.
- The production compose build and recreate completed successfully; `fakturabot` reported `running` and restart count `0`.
- Startup logs showed FakturaBot startup, scheduler startup, Telegram polling startup, and polling for `@officeflow_sk_bot`, with no polling conflict or startup exception in the observed window.
- Production-image compile smoke: `python -m compileall -q bot` passed.
- In-container bounded runtime smoke: `infohelp_runtime_smoke=ok`.
- The runtime smoke checked final-router placement, 3-user/3-bot context bounds, workspace metadata isolation, active-flow descriptor plus `Hlavné menu`, sanitized payload exclusion of workspace ID, and strict parsing of a bounded known action.
- Configured live-LLM smoke: `infohelp_live_llm_smoke=ok outcome=clarify_candidates` for synthetic `/invoce` input with no recent turns and no business side effect.
- The slim production image does not install `pytest`; the complete pre-merge suite above is therefore the automated regression evidence rather than an in-container rerun.
- Temporary smoke scripts were removed from both host and container after the checks.
- No DB/schema migration, storage rewrite, or production business-data mutation occurred.

## Remaining acceptance boundary

The historical automated suite and deployed runtime smoke did not prove real Telegram behavior. Interactive acceptance subsequently failed, and the V1 runtime is rolled back. This artifact is retained as failed/superseded evidence and cannot support an active-production claim.

## Confirmed interactive failure classes and containment

1. Receipt-deletion wording surfaced unrelated destructive invoice-deletion and complete-database-deletion suggestions.
2. Callback tests modeled `callback.message.from_user` as the human, while Telegram makes that message author the bot; the runtime then passed the bot-authored message to business owners.
3. Synthetic invoice action-label dispatch prompted for an invoice number without creating a continuation FSM state, so the next value was consumed by idle routing.
4. Quoted/replied Telegram context was absent from recent context capture.

Rollback containment restores the pre-PR63 route and removes contextual suggestion buttons, `infohelp:*` callbacks, the generic recovery dispatcher, unmatched-command recovery, recent-turn middleware/capture, and feature-only active-FSM contextual behavior. Existing known commands, active-FSM navigation/stale recovery, DecisionResolver callbacks, Product Truth, and customization requests remain under their prior owners.

## Rollback verification results

- Rollback-only containment tests: `5 passed in 2.84s`.
- Focused InfoHelp/routing/callback/FSM tests: `400 passed in 53.83s`.
- Adjacent voice/invoice/workspace/contact/state-control tests: `264 passed in 118.99s (0:01:58)`.
- Complete Python suite: `2429 passed, 7 subtests passed in 488.94s (0:08:08)`.
- `python -m compileall -q bot`: passed.
- `git diff --cached --check`: passed.
- Runtime owners changed by PR `#63` match the recorded pre-PR63 baseline after the rollback; only the retained historical artifacts and the new containment proof intentionally differ.

No schema, migration, storage rewrite, or business-data mutation is required. V2 is not part of this task and requires a revised Architecture Design Proof plus explicit owner approval.
