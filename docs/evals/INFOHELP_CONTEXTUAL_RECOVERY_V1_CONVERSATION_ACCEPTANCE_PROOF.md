# INFOHELP_CONTEXTUAL_RECOVERY_V1 Conversation Acceptance Proof

Status: `automated_local_and_deployed_runtime_smoke_passed`

Runtime acceptance: `interactive_telegram_journey_pending`

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

The feature remains partial Level 2. Production process/polling, bounded runtime, and configured live-LLM smoke passed, but no real authorized user update was fabricated. A real Telegram text message, voice/STT update, recovery-button click, and terminal keyboard lifecycle still require interactive acceptance before the feature can be described as fully production-accepted.
