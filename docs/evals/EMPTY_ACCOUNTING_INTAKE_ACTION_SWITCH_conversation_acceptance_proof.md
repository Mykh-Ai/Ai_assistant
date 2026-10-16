# Empty Accounting Intake Action Switch — Conversation Acceptance Proof

Date: 2026-10-16. Environment: local uncommitted working tree based on main
`0df00f2`; no server operation. Design:
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
