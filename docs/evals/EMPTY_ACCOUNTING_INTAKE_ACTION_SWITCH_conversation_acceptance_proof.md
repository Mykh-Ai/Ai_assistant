# Empty Accounting Intake Action Switch — Conversation Acceptance Proof

Initial evaluation: 2026-10-16, local working tree based on main
`0df00f2`; subsequent deployment is recorded below. Design:
`docs/architecture/EMPTY_ACCOUNTING_INTAKE_ACTION_SWITCH_ARCHITECTURE_DESIGN_PROOF.md`.
Design verification: design_matches_runtime. Status/maturity: partial intake
recovery using bounded canonicalization; no new AI maturity or learning domain.

## Public-entry traces

`test_empty_receipt_wait_switches_through_one_primary_bundle` injects the first
wrong primary result for `Запиши мне приход.` at the public text middleware /
process_invoice_text entry. It observes add_receipt -> waiting_upload -> asks
for photo/PDF, with no accounting artifact. Shared activity metadata is real.
The next update uses public text middleware or public voice.handle_voice.

| Next input / branch | Observed state/effect | Result |
|---|---|---|
| `Відкрий робочий день о 07:07.` / text and voice | one primary call for that update, open_work_day -> explicit 07:07 preview; no day before approval | pass |
| `schvalit` after that preview | real shared DecisionResolver -> one open 07:07 row and one event; idle | pass |
| `zrusit` after that preview | real shared DecisionResolver -> idle, zero day/event | pass |
| `Відкрий робочий день зараз.` / text and voice | same existing no-time owner -> one 08:00 row at controlled business clock; idle | pass |
| `Покажи табель за вересень 2026.` | primary period slots {month:9,year:2026} reach existing report handler after source clear | pass |

Each accepted handoff first sends Slovak navigation copy with
ReplyKeyboardRemove. The target shows its own preview or completion. No
receipt workspace or leftover voice file exists. Other actor has no work-day
row. The source false classification and new action each use one primary
bundle, with original utterance preserved; there is no primary probe/replay.

Boundaries: OpenAI primary output and STT audio are synthetic; actual prompt
serialization, primary output validation, public dispatch, guard, FSM, shared
decision resolution, clock and SQLite owners run locally. The report trace
fixtures the final report handler and proves slot handoff, not Excel output;
existing report tests cover generation. Initial authorized handler entry is
assumed in these traces; separate tests exercise authorization rejection.
No real model/audio/Telegram/API was called.

## Negative space, race and access evidence

- `test_empty_upload_unresolved_or_nonexecutable_bundle_preserves_source`:
  unknown, capability/how-to, contextual help, same add_receipt, reserved
  send/edit, local fallback and out-of-bound token -> no source clear, answer,
  target or business effect. Original state/data remain equal.
- `test_empty_upload_model_outage_does_not_use_local_action`: real resolver
  wrapper receives an unavailable fake client; even a locally recognized
  open-day request cannot discard the source.
- `test_nonempty_upload_never_calls_primary_or_clears`: candidate, empty path,
  upload marker, session expiry and unrecognized key all block the exception.
- `test_empty_upload_changed_during_primary_is_not_discarded`: processing
  starts during resolution; final snapshot check rejects handoff.
- `test_empty_upload_claim_serializes_with_upload_across_fsm_contexts`: two
  real FSMContext instances, same MemoryStorage/StorageKey. Concurrent upload
  waits for claim/clear, then sees absent source and performs no download.
  A different actor/storage key is unaffected.
- `test_upload_started_before_candidate_blocks_empty_claim`: once upload
  entry marks processing, no candidate is needed to reject the old snapshot.
- `test_empty_upload_interrupt_still_requires_authorization`: actual access
  middleware rejects unauthorized text/voice before guard/STT/primary/owner;
  only existing access-rejection FSM cleanup occurs.
- Existing guard tests cover ordinary active input, other FSM ownership,
  exact/semantic cancel/menu/start, stale mutation rejection and navigation.
- Existing upload, work-time, DecisionResolver and callback tests cover target
  confirmation/state/expiry/keyboard behavior and old journeys. No callback
  token, markup ownership or precision boundary changed in this slice.

No new buttons/confirmations: extra switch-confirmation scenarios are not
applicable because source has no draft and the new explicit executable request
authorizes leaving it. Target confirmation is still required where previously
required. General fresh-FSM suspension/restoration is explicitly unsupported.

## Product Truth and no overclaim

`test_add_receipt_how_to_renders_partial_guidance` checks `Ako pridám bloček?`:
partial status, photo/PDF, empty-wait alternative and cancel after upload starts.
Product Truth registry adds the same bounded limitation and forbids claiming
silent replacement of any draft/in-flight upload. Work-time remains partial;
saved-time correction and the October 16 report/open model defect are not
fixed by this change. Informational results do not start a target action.

## Validation

- Initial broad focused run: 1121 passed (before final two access tests and
  full two-message trace refinement).
- Final focused guard/routing/Product Truth/InfoHelp run: 222 passed.
- Full `python -m pytest -q`: 2746 passed, 7 subtests passed in 626.39s.
- Focused runtime compileall and git diff --check passed. The standalone
  unified diff excludes pre-existing Google work and earlier incident edits;
  git apply --reverse --check passed without changing the worktree.
- Real audio transcription, actual new-payload model recognition, interactive
  Telegram and deployed smoke: not run; no deployment was requested for this
  local slice. Synthetic model results do not establish live semantic quality.

Verdict: runtime_not_proven for live semantic/Telegram acceptance; local
deterministic recovery evidence passes. No commit, push, deploy or production
data write is implied.

## Authorized deployment follow-up — 2026-10-16

Runtime deployed: `5a3f3f8c4d59165aa60ad45e7e7929e411b13e3f`. Source verification matched all146 tracked
bot Python files. Backup and frozen SQLite/log evidence: `/bot/backups/work-time-recovery-deploy-20261016T202649Z`.
Bot-only rebuild/recreation; cloudflared and env unchanged. Polling/getMe passed,
no startup error/conflict; schema and all work-time data unchanged, integrity ok.
Incident interval readback:06:54-15:39, closed, gross525/net495 minutes.

Actual configured GPT-4o passed three synthetic-actor/temporary-SQLite journeys
in the deployed container with actual primary/slot calls: closed arrival edit
06:47->06:54 approve; closed end15:20 preview/cancel; fresh empty receipt wait
->arrival06:55 preview/cancel. Python FSM, confirmation and keyboard owners
executed. This is live provider/handler evidence, not Telegram conversation.

Eight exact-primary-payload probes:7 clear correction/arrival/report cases
matched. Noisy incident text Зароби мені, будь ласка, працівний вікас. again
returned open_work_day, not the desired unknown. The semantic safety defect
remains reproduced; recovery capability does not prevent every false opening.

Interactive Telegram and real audio: pending. Telegram Web requires QR login;
user was asked to sign in and the page was left open. No customer notification
or synthetic inbound getUpdates/polling was used. Verdict: deployed_partial,
live provider/handler journeys pass; interactive Telegram runtime_not_proven.

## Real Telegram follow-up — 2026-10-17

Owner logged into the existing Edge Telegram Web session. Actual authorized
chat: @officeflow_sk_bot, deployed runtime5a3f3f8 (no new code/deploy).
Selected workspace contained no work-time rows. Private RO audit/snapshot and
logs: /bot/backups/telegram-recovery-smoke-20261017T152454Z.

| Actual input / operation | Observed result | Scope verdict |
|---|---|---|
| /add_blocek -> Відкрий сьогодні робочий день з 07:07. | Empty wait ended explicitly;17.10.2026 arrival07:07 preview, no save | pass |
| Upraviť ->06:54 ->Zrušiť | New06:54 preview; cancellation; preview buttons removed | pass for unsaved preview only |
| Покажи робочий виказ за жовтень 2026. | generate_work_time_report; first-report lunch question, no day opened | pass for route/setup only |
| /cancel at lunch question | Returned idle, but Ano/Nie inline buttons remained | FAIL: terminal UI cleanup incomplete |
| Old Ano clicked once after cancel | Stale-decision alert, markup removed, no settings saved | pass for stale rejection/cleanup |

Primary server traces were real llm_bundle/business_action: opening request
13b4eb4c-c3c2-4d2d-9e1e-6793e9c981c4/message3667; report request
4e3cf654-f7bd-4097-9223-c3eed39839da/message3674. No synthetic inbound update,
fake STT/model or secondary polling. Final alert dismissed; bot idle, old
preview/lunch markup gone. Global hashes of work_time_days/events/settings
match before exactly; integrity ok, no runtime traceback/polling conflict.
Screenshot evidence is outside Git and cropped to the bot conversation.

Verdict: real text/button Telegram recovery and clear report routing observed;
not full conversation acceptance. No production existing-row correction save,
closed/historical correction, Excel completion or real voice was exercised.
No production fixture was inserted. The previously reproduced noisy report/open
semantic failure remains unresolved. Report-setup global-cancel keyboard
cleanup also remains open; do not label the entire UI lifecycle passing.

Subsequent explicit authorization also allowed creating and retaining a real
test work day, then confirming a saved start07:07->06:54 correction. That
separate persisted journey passed; see WORK_TIME_TIME_CORRECTION acceptance
proof, Real persisted open-day correction section. It does not resolve the
report-setup cancel-markup defect recorded above.
