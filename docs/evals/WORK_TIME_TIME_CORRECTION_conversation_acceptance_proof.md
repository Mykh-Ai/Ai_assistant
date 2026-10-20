# Newer Explicit Work-Time Boundary — Conversation Acceptance Proof

Initial local evaluation on 2026-10-16, based on main 0df00f2 plus the separate
empty-accounting-intake recovery patch. Design: section 19 of
WORK_TIME_EXPLICIT_OPEN_AND_OPEN_DURATION_CLOSE_ARCHITECTURE_DESIGN_PROOF.md.
Design verification: design_matches_runtime. Status: partial. No new AI
maturity/learning domain; Python validates and commits user-confirmed values.

## Public-entry traces

`test_public_new_explicit_time_supersedes_stored_boundary` starts at
process_invoice_text or public voice.handle_voice, with temporary SQLite,
synthetic actor1001, controlled Bratislava business time 16 October 18:00.
Primary and slot OpenAI calls/STT are fixtures; real prompt serialization,
bounded output validation, routing, FSM, shared DecisionResolver and DB owners
execute. Authorization is assumed before those handlers; a separate middleware
test proves denied access before the owner. No real model/API/audio is used.

| Precondition / input | Observed route and effect | Result |
|---|---|---|
| Open 06:47; Oprav dnes prichod na 06:54 | open_work_day/open_at_time -> waiting_open_preview_confirm -> old/new reply preview -> shared Schváliť -> same open row06:54 | pass |
| Closed 06:47-15:39; same arrival correction | same preview; no pre-approval write; approve preserves15:39 and closed status; gross525/net495 with lunch30 | pass |
| Closed 06:47-15:39; Oprav dnes odchod na15:20 | close_work_day/close_at_time -> waiting_close_preview_confirm -> approve changes end only and recalculates | pass |
| Open06:47; explicit end15:39 | same close owner -> preview -> approve closes same row; one audit event | pass |

Each scenario runs both text and voice entry, checks exactly one primary
bundle, Python-provided correction slot flag, unchanged original before
approval, one resulting row/id, retained other clock and no other-actor row.
Confirmation uses real shared resolver text Schváliť. Preview creates a reply
keyboard; terminal success removes it and clears FSM. No voice file remains.
Voice confirm-state dispatch remains the existing tested shared route; no
voice phrase parser or new callback family is introduced.

## Historical dates and math

- `test_historical_end_correction_preserves_explicit_date_over_open_day`:
  explicit9.9.2026 changes only that stored end to13:10, while a separate open
  October16 row remains exactly equal.
- `test_historical_arrival_edit_keeps_bound_date`: September9 start correction
  -> Edit -> date-less07:15 reply -> new preview -> approval changes only the
  historical start; no October16 row is created.
- `test_duration_override_is_explicitly_replaced_by_confirmed_range`:
  07:10-13:40 with360 confirmed net and lunch30 -> explicit13:10 correction ->
  gross360/net330, explicit_end and no fixed-duration override. Current lunch
  is retained; correcting a clock alone never implicitly disables lunch.
- Old explicit range/duration/report tests retain their previous arithmetic.

## Safety, transactions and UI

- `test_correction_controls_and_final_reply_keyboard`: unknown repeats frozen
  preview; cancel clears/no-write; edit removes reply keyboard and enters
  expected input. All preserve the original business row until approval.
- `test_invalid_reverse_future_boundary_never_proposes_write`: invalid order
  and future clocks return no correction; original row remains exact.
- `test_stale_snapshot_and_duplicate_approval_cannot_overwrite`: changed row
  or lunch after preview rejects old approval; applied preview cannot repeat;
  a fresh equal-value confirmation is unchanged with no extra event.
- `test_audit_failure_rolls_back_and_other_workspace_cannot_apply`: scoped
  workspace/legacy mismatch cannot apply; injected SQLite event failure rolls
  back the preceding row update.
- `test_no_time_repeat_and_fresh_preview_conflict_do_not_rewrite`: omitted
  arrival leaves old clock; a fresh-open preview cannot claim success when a
  same-day row already appeared.
- `test_closed_now_without_new_explicit_clock_does_not_overwrite`: now on a
  closed day asks for an exact clock and never revises departure automatically.
- `test_expired_correction_removes_reply_keyboard_without_write` and
  `test_correction_global_navigation_removes_reply_keyboard`: expiry,
  /cancel, /menu and /start clear the pending correction and remove UI.
- `test_work_time_help_exit_removes_correction_keyboard_and_does_not_write`:
  /dochadzka clears pending state, removes reply UI and explains correction
  examples without changing the stored day.
- `test_old_inline_card_cannot_approve_or_remove_correction_ui`: an old generic
  inline card cannot confirm the new snapshot or edit an unproven message.
  Owned correction inline-card cleanup is not applicable: none is created.
- `test_cleanup_send_failure_does_not_rollback_or_repeat_committed_change`:
  Telegram reply/cleanup failure is logged after one committed change/event;
  FSM is clear and data is not rolled back or replayed.
- `test_denied_actor_cannot_confirm_and_reply_keyboard_is_removed`: access
  middleware rejects before handler/model, clears its pending state/UI and
  leaves business data unchanged. Membership failures use existing revalidation
  with reply-keyboard cleanup; no access eligibility changed.
- `test_conflicting_close_slots_are_unknown_not_partial_corrections` rejects
  conflicting start/end/duration fields and now-plus-explicit-time shapes;
  Python does not silently apply just part of a contradictory model result.

## Product Truth / guidance

Registry and Slovak copy explain confirmed dated start/end correction, other
clock preservation, current lunch and explicit-range replacement of a fixed
duration. Status remains partial and payroll/multi-shift/automatic-clock
claims remain forbidden. `test_product_truth_explains_correction_without_executing`
uses the existing known capability question Vie bot evidovat odpracovane
hodiny? and checks correction examples with no business mutation. /dochadzka
also exposes them. The initial test phrase Ako pouzivat dochadzku? is outside
the legacy static fast-path; arbitrary help-language coverage is not claimed
fixed. Existing contextual InfoHelp remains rollout-bound and partial.

## Validation and limits

- Preliminary unchanged work-time/service/routing/voice/callback slice:
  205 passed. First new correction slice:22 passed.
- Expanded intermediate slice:286 passed. A later slice exposed only the
  guidance test's unsupported static-fast-path phrasing (305 passed/1 failed);
  the corrected guidance/access tests passed2/2 separately.
- Full `python -m pytest -q`:2782 passed,7 subtests passed in721.04s.
  This run predates the final read-only /dochadzka keyboard cleanup and the
  final strict raw forbidden-slot validation; those deltas are covered below.
- Final focused correction/work-time/service/voice/navigation/access/callback/
  Product Truth/InfoHelp suite:421 passed in146.62s.
- After help cleanup: correction/public-routing slice97 passed in109.48s.
- After strict raw-field validation (including invalid non-null unused
  fields): public text/voice, historical and slot slice16 passed in14.42s;
  all seven conflicting-slot cases passed separately in7.37s, including open
  mode with an invalid non-null departure. Valid routes remain unchanged.
- An earlier full attempt was intentionally interrupted to add final
  conflicting-slot validation; the final full run supersedes that attempt.
- Focused compileall and git diff --check passed.
- Scoped unified diff passed git apply --reverse --check and excludes the
  earlier empty-intake patch, prior incident edits and unrelated Google work.
- Real model interpretation of new correction examples, real STT, interactive
  Telegram, deployment and production write: not run. Prior nine arrival probes
  are not acceptance for this new payload or correction journey.

Verdict: runtime_not_proven for live semantic/Telegram acceptance; the local
deterministic implementation is evaluated with disclosed model/STT fixtures.
No production deployment, data repair or notification is implied. The report
to opening model defect and general draft switching remain separate gaps.

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

## Real persisted open-day correction — 2026-10-17

User explicitly authorized saving and retaining a test day after clarifying
that preview editing alone did not prove saved-time correction. Same current
Telegram actor/workspace, today17.10.2026 Europe/Bratislava; no prior row.
Backup and private full records/logs/rollback note:
/bot/backups/telegram-saved-time-smoke-20261017T153220Z.

| Actual sequence | Independent evidence | Verdict |
|---|---|---|
| Відкрий сьогодні робочий день з07:07. ->preview->Schvalit button | Bot saved-open message; RO row open07:07/endnull and one open event | pass: actually saved |
| Виправ сьогоднішній час відкриття робочого дня на06:54. | Old07:07/new06:54 preview; complete saved row/events unchanged while pending | pass: no pre-approval write |
| Typed Schvalit | Same row id open06:54/endnull; one time_correction audit old07:07/new06:54; initial event intact; terminal reply keyboard removed | pass: persisted correction |

Exactly one new day and two new events relative to before snapshot. All old
days/events globally identical; settings unchanged, integrity ok. Origin/note/
other totals fields retained; no end clock or lunch setting invented. Final
17.10.2026 test day deliberately remains OPEN from06:54 per user instruction.

Both real primary routes were llm_bundle/business_action/open_work_day:
fdcaac93-c4b7-44be-9838-c4b5d2370a0f/message3678 and
be4c5fc6-51a0-44ba-bd25-4bb11137468a/message3681. Real Telegram/model/
slot/confirmation/FSM/SQLite owners; no synthetic update or direct SQL write.
Screenshot saved outside Git with bot-chat-only crop.

Verdict: real text/button persisted open-day arrival correction PASSED. This
supersedes the earlier pending verdict for that specific journey. Closed-day,
historical/end corrections and voice were not exercised here; noisy report/open
semantic safety and report-setup global-cancel markup defect remain open.
No new runtime change, redeploy or redundant unit/full suite run.

## Explicit close-now text — 2026-10-17

User requested closing the actual retained test day with no numeric end time
and wanted to know whether confirmation would be asked. Private before/after
DB/log evidence: /bot/backups/telegram-close-now-20261017T154315Z.

Actual input: Закрий зараз робочий день. The very next bot response was
Pracovny den je uzavrety,17.10.2026:06:54-17:43(10:49). No intermediate
question/preview or second user approval was sent. Final scoped RO row was
closed with end17:43, gross649/total649; same arrival/id, one new close event.
All prior events/other days/settings unchanged; integrity ok. No lunch setting
was supplied/changed, so the retained existing zero deduction applied.

Primary: close_work_day via llm_bundle, trace
2faba61c-acbe-4f67-8de1-58e1190ad303/message3685. Screenshot outside Git.
Test day now remains CLOSED. Verdict: PASS for explicit close-now text with an
existing open day and no exact clock supplied. No voice or unspecified-now
inference is claimed. Registry wording was repaired to match existing direct
close_now code; no runtime patch, deploy or redundant suite run.

## Production voice recurrence — 2026-10-19, read-only audit

Actual deployed sources match server checkout3183439; whisper-1 STT/gpt-4o,
Europe/Bratislava. Same incident actor as October16 verified privately. No
customer/workspace identifiers published; no raw audio replay or business write.

| Local time | Actual STT text | Actual primary / persisted result |
|---|---|---|
|07:05:30-32|Відкрив мені працьовний день зараз.|open_work_day -> one day opened07:05|
|16:08:58-16:09:00|Запиши меню отход, будь ласка.|open_work_day WRONG for reported departure; no extra open/close event|
|16:09:25-27|Закрий мені працьовний день.|close_work_day -> same day closed16:09|

All primary choices were real llm_bundle/business_action. First departure
trace:d5862254-5c19-4b34-bf40-9a1222eb617e/message3689; repeat:
8fdc133e-3424-4fbb-8fd9-5da0ba218b18/message3691. Opening trace:
58e753e4-a1ce-4393-95b5-6560315d7fa2/message3687. Independent scoped DB
readback: exactly one closed19.10.2026 row07:05-16:09, gross544/net514 with
lunch30, its open/close events only, integrity ok. All three updates handled,
provider calls200 OK; no traceback/polling conflict in bounded daily logs.
Secondary slot output/outgoing replies are not logged; do not invent them.

Verdict: FAIL for shorthand departure recognition; explicit repeat close PASS.
This is fresh production evidence of the unresolved semantic selection gap,
not proof that recent correction/recovery work failed to deploy. Existing
same-day idempotency prevented a duplicate open row; it did not close the day.
No new model/STT fixtures or runtime change/tests were run. The exact noisy
transcript must enter future public-entry evaluation; accept recovered close
or safe unknown/clarification, never an opposite opening action. Original
spoken wording and sole STT-error cause remain unknown without audio replay.

## Candidate arrival/departure prompt repair — 2026-10-19

Design: existing architecture proof section20, ready_for_handoff before code;
implementation matches that narrow semantic scope. Capability stays partial;
existing bounded canonicalization maturity and Python owners are unchanged.
Candidate is local/uncommitted, not the deployed3183439 runtime. No new action,
mode, regex/phrase router, learning table, confirmation or DB schema change.

Runtime changes: symmetric primary hints for personal arrival versus departure;
bounded close slots accept a clear performative current departure with no
clock/duration as existing close_now. STT receives a compact multilingual
attendance vocabulary only; no canonical actions, rewriting or model migration.
Exact clocks/durations and saved/historical correction gates remain existing.
Product Truth/help explain departure terminology, exclusions and immediate
current-departure closing. Broad report/open safety and cancel-markup gaps
remain outside scope and unresolved.

### Public text/voice fixture journeys

New parametrized test_arrival_departure_public_entry_preserves_event_direction
covers13 phrases through both public text and voice entry (26 cases). Each
uses temporary SQLite with one open07:05 day, lunch30 and business16:09.
Primary and STT outputs are fixtures; actual prompt serialization/validation,
work-time slot call, router/FSM and service owners execute. The departure
fixture normalizes close_now; same row closes16:09/net514 with one close audit.
Arrival is idempotent; finance, waste, prohibition, contradiction and bare-label
unknown fixtures leave the entire original day unchanged. One primary call,
original text, actor isolation, no invoices/accounting artifacts and temporary
voice cleanup are checked. This proves Python boundaries, not model accuracy.

STT request tests inspect attendance spellings and retained verbatim/no-invented-
words constraints; no actual speech is transcribed by those tests. Guidance
checks partial truth, departure example/exclusions and no-extra-confirmation
wording for a clear current departure. Existing scopes retain their tests.

### Real candidate model probes, no business dispatch

Captured the exact local public-entry primary request before execution with a
synthetic actor and no DB. In an isolated process of the production container,
used configured GPT-4o with that complete allowed-action/hint envelope and the
candidate slot function. Running bot modules/credentials/config were not
changed; there was no business dispatch, Telegram send or real audio call.

Initial primary candidate:13/16 expected actions matched, while prohibition,
capability question and a bare departure label incorrectly selected closing.
Slots8/8 passed. Tightened the primary semantic negative space with explicit
prohibition/question/bare-label examples and precedence. Re-captured the exact
request; final18/18 primary cases and8/8 slot cases passed, including new
wordings absent from examples. One sampled pass is not a quality guarantee.

Final primary evidence includes:

| Meaning / sample | Actual candidate result |
|---|---|
| Запиши меню отход, будь ласка.; Запиши мені отходи.; Внеси мій одход. | close_work_day/business_action |
| Запиши мне приход.; Зафіксуй мій прихід на роботу. | open_work_day/business_action |
| Money, production waste, negated departure, uncertain arrival/departure, bare Отход. | unknown |
| Чи вмієш записувати відхід?; Можеш пояснити як записати одход? | unknown/capability_or_howto |
| Existing work-time report and receipt requests | generate_work_time_report / add_receipt |

Final slot evidence: incident and short personal departure ->close_now;
explicit15:39 ->close_at_time;8worked hours ->close_with_duration; prohibition,
question, ambiguous event and closed-day missing-clock correction ->unknown.
No date/time value was supplied to the incident request or inferred as a
correction to a closed day.

### Real-provider public handler / temporary SQLite

Separate isolated process over existing public process_invoice_text patched
only the two candidate hint objects and candidate slot function (including its
already-imported handler reference). Real primary and slot model calls then
ran with a synthetic actor/temp SQLite and fake Telegram message:

- incident input ->one primary close_work_day ->same07:05 row closed16:09,
  net514, one close event and terminal FSM;
- short arrival input ->one primary open_work_day ->same open07:05 row,
  no duplicate/event, terminal FSM.

Both passed. An initial harness attempt failed because it retained the handler's
old imported slot-function reference; after binding the candidate reference it
passed. That failed harness was not counted as valid candidate acceptance.
No customer row, production FSM, model configuration or daemon was modified.

### Validation / limits

- Focused tests:371 passed in102.90s; this predates only the final primary
  negative-example emphasis. The final full suite covers that finished state.
- Full suite for final runtime code, repeated2026-10-20: 2814 passed, 7 subtests passed in 674.70s (0:11:14).
  Durable log/JUnit: departure-full-tests-2026-10-20.log/.xml outside Git.
- Initial sandbox runs were interrupted before useful async execution: Windows
  asyncio socketpair blocked in socket.accept. A25-second faulthandler trace
  identified the loopback restriction; approved elevated reruns worked. No
  dependency/event-loop-policy change was needed.
- Compileall and whitespace checks pass; final diff checks run after docs.
- Raw probe JSON and scripts live outside Git in the task artifact directory:
  departure-live-probes-2026-10-19-v1.json (disclosed initial failures),
  departure-live-probes-2026-10-19.json (final18+8), and
  departure-live-journeys-2026-10-19.json (two handler journeys).
- Real Whisper/audio recognition, interactive Telegram with the candidate,
  deployment, commit/push and production business writes: not performed.

Verdict: local deterministic boundaries and sampled real candidate LLM/handler
journeys pass; real-audio/Telegram/deployed runtime_not_proven. No universal
noisy-input fix or product-maturity upgrade is claimed. Existing feature/gate
source owners, documentation and honest partial guidance remain authoritative.

Official OpenAI references consulted2026-10-19:
https://developers.openai.com/api/docs/guides/speech-to-text (Whisper prompt
has limited vocabulary control/224-token limit, not general instruction
following) and https://developers.openai.com/api/docs/guides/prompt-engineering
(diverse input/output examples). These references do not prove this repair's
recognition quality; measured evidence above does.

Capability completion check for this local candidate: runtime prompts changed;
existing canonical-action hints/registry updated, no token added; Product Truth
and Slovak InfoHelp updated with partial status; public text/voice fixture and
real candidate model/handler evidence recorded;28 regression cases added;
forbidden perfect-recognition/payroll/waste/income/automatic-learning claims
checked; PROJECT_LOG updated; maturity unchanged bounded canonicalization.
Full-suite final result is recorded above when complete. No deployment or
real-audio acceptance is inferred from these checks.


## Authorized release and deployed verification — 2026-10-20

User requested finishing the started work following earlier explicit
commit/push/deploy instructions. October19 candidate-only statements above
describe that original stage; this section records the subsequent release.

- Runtime commit:62b1046e6f28f1ca7063c92c0adbc3e3cba3be27, published directly
  to main (no separate PR merge). Server clean before/after fast-forward.
- Final full suite repeated with durable artifacts:2814 passed,7 subtests
  passed in674.70s. The earlier process result was unavailable, never inferred
  from its partial output. No runtime source changed after this successful run.
- Backup:/bot/backups/arrival-departure-deploy-20261020T065245Z, private
  consistent DB/logs/manifest and old-image rollback. Captured another frozen
  snapshot after stopping only bot; rebuilt/recreated only bot. No schema,
  migration, repair, customer attendance write or notification.
- New image:sha256:b899086274f9f999a8450eda799630318cc8ca453a8fe8146149cbe2cfc3b85c.
  All146 tracked bot Python files match checkout/container; running, restarts0,
  polling/getMe successful, no startup traceback/ERROR/polling conflict.
  Existing .env hash and cloudflared container unchanged. Models remain
  GPT-4o/Whisper-1; no competing polling process was started.
- Read-only frozen/live comparison:integrity ok, identical schema and all
  work-time hashes. The only table difference was existing Google binding
  check timestamps (last_attempt_at,last_successful_check_at,updated_at),
  verified separately with identical row identities/count; no credential or
  business-data change was inferred from those scheduled checks.
- Actual deployed prompts were captured before dispatch from container source,
  then the real model client restored. No candidate hint/function injection:
  all18 primary and8 slot cases passed with configured GPT-4o. Incident text
  selected close_work_day and close_now; personal arrival selected opening;
  negative neighbors remained unknown/question-only. One sampled run does
  not guarantee universal noisy-input safety.
- Two actual deployed public-handler journeys with real primary/slot models,
  synthetic actor1001 and temporary SQLite passed: departure closes one07:05
  day at synthetic16:09/net514 after30-minute lunch; arrival preserves the
  existing open row. No real Telegram send/customer DB access in these probes.
- Browser Telegram account/session was available after reopening its tab.
  RO preflight found an existing open actor row, so the proposed live departure
  smoke was deliberately not sent. Sent only /dochadzka; received partial
  attendance/help instructions. Before/after actor snapshot:6 days/35 events,
  identical content hash; existing October17 closed06:54-17:43 row preserved.
  Real Telegram transport/help passed; interactive attendance execution for
  this new prompt repair remains unproven. No actual Whisper audio replay.

Private server evidence in the backup folder:manifest.json,frozen-prestart.db,
verification.json,binding-diff.json,telegram-before/after.json and smoke logs.
Outside-Git task artifacts:departure-full-tests-2026-10-20.log/.xml,
departure-probe-2026-10-20.json (18+8),departure-journey-2026-10-20.json (two),
telegram-deployment-help-2026-10-20.png. Public docs contain no actor/workspace
identifiers or credentials. Unrelated local Google/Gmail changes excluded.

Completion:runtime/hints/registries, partial Product Truth and InfoHelp,
tests/UX evidence, forbidden-claim review, existing contract/TZ/log are current;
AI maturity unchanged. This scoped release is complete. Universal noisy
report/open selection safety and report-cancel inline cleanup remain open.

## Report lunch-card cancellation repair — 2026-10-20 local acceptance

Design: existing architecture proof section21, ready_for_handoff before code.
Scope is deterministic UI ownership/lifecycle; work_time_tracking stays partial,
AI maturity unchanged, no semantic/model/action/slot/schema migration change.
This follow-up addresses the reproduced cancel-markup defect; earlier failure
records remain historical evidence. No report/open semantic-safety fix implied.

Public entry: process_invoice_text -> fixture primary report action/month slot
-> real start_generate_work_time_report -> temporary SQLite with an existing
July2 duration row and unconfigured lunch -> actual MemoryStorage FSM initial
lunch-choice state -> one bot-authored inline message. Telegram methods and
STT are fixtures; canonical text yes/no/global-cancel resolvers execute. The
callback actor is human and the callback source author is the bot.

| Scenario / exact continuation | Observed outcome | Evidence |
|---|---|---|
| /cancel command, скасувати text and public voice/STT | idle, old inline removed, ReplyKeyboardRemove, no settings/report/day change | test_report_public_entry_cleanup_on_exit |
| /menu, /start, /dochadzka help | owned card removed before replacing the flow, no business save | same parametrized test |
| expired ano and stale reset/new request | expiry/idle transition removes card, no hidden save | same test through ActiveFsmMessageMiddleware |
| ano / nie via text, voice and decision:yes/no | card consumed once; yes waits for minutes with no save; no saves disabled lunch and sends existing report | test_report_choice_channels_remove_card_and_keep_existing_effect |
| unknown, cancel, new report, old no card | unknown retains one card; old card cannot answer the new request | test_unknown_retains_one_card_and_new_session_rejects_old_card |
| foreign actor/chat | no effect and no markup edit | test_report_callback_guards_and_owned_cleanup |
| missing reference / changed workspace / legacy / expired | no business effect; only proven private stale card removed, expiry/legacy exits | same guard matrix |
| malformed decision:invalid on current card | current card retained, no business effect | same guard matrix |
| Telegram edit failure during cancel/yes/no | logged failure, safe intended state/effect; subsequent owned stale click retries cleanup without saving again | test_cleanup_failure_logs_without_reversing_state_or_effect |

The initial focused run found missing ReplyKeyboardRemove on menu/start
(2 failed,97 passed). Repaired those exits; subsequent focused run across new
UI matrix, existing work-time routing, callbacks, state control and active-FSM
guard:185 passed in95.31s. Added guidance/partial-truth cancellation check.
Full final suite: 2840 passed, 7 subtests passed in 701.04s (0:11:41). Durable log/JUnit outside Git:
keyboard-full-tests-2026-10-20.log/.xml. Runtime source unchanged during run.

Design-to-code: work_time.py tracks serializable chat/message/actor/workspace
in FSM and owns cleanup; state_control and active_fsm_guard pass current
message before clear/navigation/expiry; decision_callbacks validates current
report card and restricts unbound stale cleanup to private bot messages owned
by the callback actor. Existing exact invoice-edit/InfoHelp owner guards retain
their cleanup authority. Shared callback regression fixture now models a real
bot-authored private message, rather than identifying its author as the human.
No business execution/confirmation owner or canonical decision token changed.

Product Truth and Slovak InfoHelp explain /cancel during pending report lunch
setup. In_Action registry and existing architecture/TZ/README/log updated;
forbidden all-keyboards-fixed, payroll, perfect-STT and new-learning claims
not added. Only this report card is tracked; cleanup is reactive on next update,
not a new background timeout service. Existing pre-repair/restart orphan cards
have no saved reference and can only be cleaned on a proven owned stale click.
Telegram API failure can leave visible buttons; the failed cleanup is logged
and must not reverse a completed business effect or claim success.

Predeployment verdict: runtime_not_proven for live Telegram/deployment;
local public-entry deterministic journeys passed. Superseded by the following
authorized deployment/live verification, without erasing the original evidence.


### Report-card deployment and real Telegram acceptance — 2026-10-20

Runtime commit d3a05eec45ac176d49acbb71c09fceb3e1985ec8 committed/pushed directly
to main and deployed. Image:
sha256:ef2e4cc29f5a20d9a359885ac3d78a55c7633a8ad57eccf694883858888dac34.
Full final runtime suite:2840 passed,7 subtests passed in701.04s. Source stayed
unchanged during the run. Existing unrelated Google/Gmail work excluded.

Private backup:/bot/backups/keyboard-cleanup-deploy-20261020T072321Z contains
consistent original/frozen-prestart SQLite, logs, manifest and image rollback.
Recreated only bot, preserved .env/cloudflared. All146 tracked bot Python files
match checkout/container; restarts0, polling/getMe passed, no startup error or
conflict. Schema/work-time hashes identical to frozen snapshot. Only existing
Google-binding check timestamps changed (last_attempt_at,
last_successful_check_at,updated_at), with stable row identities/count.

Real browser Telegram, same previously authorized account/profile:

| Step | Actual input / response | State/UI/effect |
|---|---|---|
| RO preflight | active prior workspace, lunch_configured=false | No settings reset required |
| 09:34 local request | Покажи робочий виказ за жовтень 2026. | Real primary generate_work_time_report; question Chcete odpočítavať obednú prestávku? with visible Áno/Nie |
| 09:35 cancellation | /cancel | Rozpracovaná akcia bola zrušená. Bot je v režime čakania.; both inline buttons removed without clicking them |
| independent before/after audit |6 actor days,35 events,1 existing setting row across actor scopes | Identical full row-content digest for days/events/settings; integrity ok; no lunch setting or attendance changed |
| smoke logs | request8a4d84f5-1d27-4b41-8f0a-091b44ce3aeb,message3697,generate_work_time_report | No cleanup failure, traceback, ERROR or polling conflict |

Screenshots outside Git:report-buttons-before-cancel-2026-10-20.png and
report-buttons-after-cancel-2026-10-20.png. Private server telegram-before.db,
telegram-before/after.json and telegram-smoke.log preserve audit/trace details;
no real actor/workspace identifiers copied into repository evidence.

Final verdict:safe_to_commit; deployment and actual report ->cancel UI journey
passed. Global command cancellation is live-proven; voice/yes/no/menu/start/
expiry/forbidden/failure variants use disclosed fixtures and real handlers,
not a claim of additional live voice or exhaustive Telegram testing.
Runtime, existing decision registry, partial Product Truth/InfoHelp, current
docs/log/tests and this acceptance proof agree. AI maturity unchanged.
Pre-repair/restart orphan cards remain reference-free and can be cleaned only
on a proven owned stale callback; Telegram API failure remains logged/bounded.
Broader noisy report/open semantic selection remains unresolved and outside
this UI repair. No migration, business-time repair or new learning feature.
