# INFOHELP_CONTEXTUAL_RECOVERY_V1 Architecture Design Proof

Verdict: approved_ready_for_handoff

Status: rolled_back_after_interactive_regression

## Scope and baseline

- Baseline: `origin/main` at `465df389c1b0c6ad3281733fe7888f5b49122c1d`.
- Product need: recover honestly from ambiguous authorized text, unknown slash commands, and confusion inside an active FSM without bypassing deterministic Python owners.
- Current status: the V1 implementation was deployed and later rolled back after confirmed interactive production regressions. This artifact is retained as historical design evidence and is superseded for any future implementation.
- Target maturity: a bounded extension of Level 2 capability-aware guidance. This change does not implement broad conversational memory, a new business capability, autonomous action execution, or Level 3 customization storage beyond reuse of the existing confirmed customization-request preview.
- User journey: an authorized user can ask what is happening in an active flow, recover from a plausible typo or ambiguous request through bounded buttons, or receive a short honest fallback while the existing FSM and side-effect gates remain authoritative.

## Contract preflight

Read before implementation: `AGENTS.md`; `docs/Product_Doctrine_2030.md`; `docs/AI_Layer_Implementation_Standards.md`; `docs/Product_Truth_Layer.md`; `docs/Product_Truth_Registry_MVP_Design.md`; `docs/Self_Learning_Layer.md`; `docs/Evaluation_and_Smoke_Test_Standards.md`; `docs/Product_UX_Eval_Artifacts.md`; `docs/TZ_FakturaBot.md`; `docs/User_Access_Model_Roadmap.md`; the active InfoHelp, customization, semantic-alias, code-agent, implementation, decision-resolver, top-level-subflow, canonical-action, in-action, resolver-template, and orchestrator contracts.

Extracted constraints:

- authorization remains before context capture, STT/LLM/LMM, handlers, storage, or callbacks;
- Python provides and validates all actions, candidates, Product Truth metadata, state descriptions, callback ownership, and dispatch;
- a model may classify only within those bounds and may never execute a side effect or produce final user-facing capability truth;
- active FSM state owns the conversation, stale recovery precedes state description, and contextual help does not clear or switch the flow;
- exact commands keep deterministic owners; the unknown slash route is last;
- conversation context is process-local, tenant/workspace-safe, TTL-bounded, and contains no persisted or raw Telegram/media data;
- selection callbacks are actor/chat/TTL/index bounded and converge on existing Python owners;
- keyboard lifecycle, stale/forbidden ownership, and cleanup behavior require tests.

Touched scopes: routing, LLM classification boundary, post-STT transcript capture, FSM navigation/help, callback handling, access/middleware ordering, Product Truth/InfoHelp documentation, and UX evaluation artifacts. Untouched scopes: LMM, DB/schema, persisted storage, server, deployment, PDF/layout, billing, public signup, and production history.

Persisted-data impact: none. No migration, repair, backup, production write, or server action is authorized or required.

Self-learning: considered and intentionally excluded. Ephemeral recent turns and recovery records are not learned aliases, do not survive process restart, and never modify a canonical registry.

User-facing claims are backed by current code, the Product Truth registry, this design proof, focused tests, and the conversation-acceptance artifact. Product doctrine is direction only, not implementation evidence.

## Runtime order and authority

```text
authorization
  -> bounded conversation capture
  -> exact command/runtime-issue owner
  -> active-FSM navigation controls
  -> stale recovery
  -> active-FSM help/contextual recovery
  -> current state input
  -> idle primary resolver
  -> contextual recovery after unknown
  -> narrow final fallback
```

The active navigation resolver is bounded to `cancel_current_flow`, `show_main_menu`, `resume_start_status`, `describe_active_flow`, `describe_expected_input`, `contextual_recovery`, and `pass_through`. Resolver failure is `pass_through`. Help wording is not a shortcut dictionary.

## Conversation context contract

- Key: `(telegram_user_id, chat_id)` with workspace metadata on every turn; data from different workspaces is never combined.
- Bounds: at most three user and three bot turns, chronological, ten-minute TTL, process memory only.
- User channels: `text`, `command`, `voice_stt`, `callback`. Bot capture includes sent text plus visible inline-button labels only.
- Forbidden: files, images, PDFs, raw callback data, Telegram updates, tokens, database rows, prompt bodies, API diagnostics, or logs containing the captured turns.
- Clear after completed `/start`, `/menu`, `/cancel`, workspace switch, stale recovery, and full user deletion. Ordinary FSM transitions do not clear it.
- Message capture runs only after authorization. Voice is captured once after non-empty STT and before routing. Outgoing capture uses request-local authorized inbound context and accepts only same-chat `SendMessage` calls; background and cross-chat sends are ignored.

## State and recovery contracts

Every reachable `StatesGroup` has a Python-owned descriptor containing action id/label, current step, expected input, expected-input kind, and allowed navigation. Python renders:

```text
Teraz vykonávate: <action>.
Aktuálny krok: <step>.
<expected>
```

with a `Hlavné menu` button. Merely showing help never mutates state. `navigation:show_main_menu` revalidates the authorized actor, safely clears the current flow, removes the owned inline keyboard, and calls the existing menu owner.

The separate contextual-recovery classifier returns strict JSON in `recovery_outcome`, with one of `resolved_action`, `clarify_candidates`, `describe_active_flow`, `describe_expected_input`, `unsupported_capability`, `new_business_feature_request`, or `genuinely_unclear`. Its `failure_cause` is limited to the approved failure taxonomy and `refers_to_active_flow` is boolean. It can name only Python-provided canonical actions/capabilities, at most four candidates, bounded domain/operation metadata, confidence, and a clarification flag. One no-retry contextual call is allowed per update; parsing, scope filtering, Product Truth status, rendering, and dispatch remain in Python.

The configured OpenAI transport receives only the current input, normalized channel, up to six sanitized recent visible turns, the active descriptor when present, and bounded Python registries. No raw update, workspace identifier, token, log, file, or hidden diagnostic is included.

Idle recovery never automatically executes a write or starts an FSM. It offers bounded buttons. `infohelp:<opaque token>:<index>` records are process-local, single-actor, single-chat, workspace-bound, index-bounded, single-use, and expire within ten minutes. A valid click revalidates Product Truth and converges on the existing owner. Unsupported capabilities use Product Truth. A new business feature request reuses the existing customization preview and confirmation flow. A genuinely unclear message renders only:

```text
Tejto správe som nerozumel.
Skúste prosím stručne napísať, čo chcete urobiť.
```

Inside an active FSM, contextual recovery preserves the FSM and explains the current flow or mismatch; it never switches to another action.

## Negative space and acceptance

No new canonical top-level action, persistence table, broad memory, retry loop, phrase whitelist for help, AI-authored capability truth, automatic business write, fresh-FSM switching, server write, deploy, or merge is in scope. Exact-value voice restrictions, DecisionResolver confirmations, authorization, tenant isolation, current command owners, and keyboard cleanup remain unchanged.

Regression proof covers context bounds/TTL/isolation/clears/capture, active-flow descriptors and no-mutation behavior, deterministic known commands, terminal unknown slash recovery, recovery-result validation/fail-closed behavior, actor/chat/workspace/TTL/index callback guards, Product Truth rendering, existing-owner convergence, customization preview reuse, no unauthorized AI/STT/context capture, and unchanged normal FSM journeys. Focused, adjacent, full-suite, compile, and diff checks passed before publication.

## Deployment acceptance update (2026-08-02)

- PR `#63` was merged to `main` as `ec7c5696ec6b73b6e0a90c38ce3a1a1a5f8bae89` and deployed to `/bot/repo`.
- `docker compose ... up -d --build` rebuilt and recreated `fakturabot`; the process remained `running` with restart count `0`.
- Startup evidence showed scheduler startup, Telegram polling startup, and polling for `@officeflow_sk_bot` without a polling conflict or startup exception.
- Production-image `python -m compileall -q bot` passed.
- A bounded in-container runtime smoke passed router ordering, context bounds, workspace isolation, state descriptor/navigation rendering, payload sanitization, and strict result parsing.
- One configured live OpenAI call with synthetic unknown input returned the valid bounded outcome `clarify_candidates`; no business side effect or persisted-data write was exercised.
- The production image intentionally lacks the development-only `pytest` package, so the complete automated suite remains the pre-merge evidence recorded in the conversation acceptance proof.
- No schema, migration, storage rewrite, or production business-data mutation occurred.
- Interactive acceptance is still pending for a real authorized Telegram text message, voice/STT update, recovery-button click, and resulting keyboard lifecycle. Those actions were not simulated or attributed to a user.

## Superseding rollback decision (2026-08-02)

Interactive production use confirmed that the V1 architecture was unsafe despite its automated and bounded deployment smoke:

1. Receipt-deletion wording could produce unrelated destructive suggestions for invoice deletion and complete user-database deletion.
2. Recovery callbacks passed the bot-authored `callback.message` to business handlers as though it were the human actor, producing false workspace/profile failures.
3. The invoice-edit recovery path dispatched a synthetic Slovak action label into `process_invoice_text()`; it prompted for an invoice number without establishing a continuation FSM state, so the reply returned to idle routing.
4. Telegram `reply_to_message` / quoted-message context was not captured even though the feature relied on recent context.

The runtime introduced by PR `#63` is therefore rolled back to the pre-PR63 owners. This document remains historical evidence only and must not be used to claim that Contextual InfoHelp Recovery V1 is active or safe.

A V2 is out of scope. It requires a revised Architecture Design Proof, explicit owner approval, corrected actor/callback modeling, complete continuation-state and quoted-message contracts, regression-first tests using real Telegram callback semantics, and interactive acceptance before implementation can be considered.
