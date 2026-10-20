# Work-Time Explicit Open And Open-Day Duration Close — Architecture Design Proof

## 1. Task identity and product need

- Task: repair the 2026-09-09 work-time failure.
- Business need: an authorized user who states an arrival time must get that
  time recorded, while an omitted time continues to mean the current
  Bratislava business time. If a day is already open, a duration-only request
  for that day must close that open row with the stated net worked duration.
- User-visible outcome: `zapíš príchod o 7:10` previews an open day from
  `07:10`; `zapíš/uzavri dnes 6 odpracovaných hodín` closes the existing open
  day through the existing close preview and confirmation.
- Current and target Product Truth: `work_time_tracking` remains `partial`.
- Risk: medium; future workspace-scoped SQLite writes change, but no schema,
  storage layout, or existing row is rewritten.
- Date / architect: 2026-09-09 / Codex, from explicit user direction and live
  server evidence.

## 2. Architecture classification

Primary class: extension of existing top-level actions, with one structured
slot mode (`open_at_time`) and reuse of the existing close-duration subflow.
This is not a new canonical action: `open_work_day`, `close_work_day`, and
`add_work_time_entry` already own the relevant business intents. It is not an
InfoHelp-only change or a new storage domain.

## 3. Canonical action contract

- `open_work_day` remains `partial`, owned by
  `bot.handlers.work_time.start_open_work_day` and `WorkTimeService.open_day`.
  Entry modes remain authorized text and voice/STT. An omitted start time uses
  current business time; an explicit start time is preview-confirmed.
- `close_work_day` remains `partial`, owned by the existing close input and
  preview handlers plus `WorkTimeService.close_open_day`.
- `add_work_time_entry` remains `partial`. When its resolved duration refers to
  a currently open same-workspace day, Python reuses the close-duration owner
  instead of attempting a conflicting second same-day row.

## 4. Semantic boundary matrix

| User meaning/input | Expected action/runtime strategy | Must not become |
|---|---|---|
| Start work now, no time supplied | `open_work_day`, immediate current local time | guessed historic time |
| Record today's arrival at `07:10` | `open_work_day` + `open_at_time`, preview | current-time open or standalone closed row |
| Close the open day with six net hours | `close_work_day` + `close_with_duration` | second same-day row |
| “Record six worked hours today” while today is open | `add_work_time_entry`, then Python state-aware close-duration strategy | same-day conflict |
| Standalone six-hour day with no open row | `add_work_time_entry` + `manual_duration` | open/close inference |
| Full start/end range | `add_work_time_entry` + `manual_range` | start-only open |
| Capability/how-to question | Product Truth / InfoHelp | any DB write |

Action hints must describe those meanings and negative space. Examples are LLM
context, never a Python alias list. Ambiguous or invalid explicit values enter
or stay in a clarification state and never default to a write.

## 5. Structured slot contract

| Slot | Type/source | Required/default | Validation | Voice boundary |
|---|---|---|---|---|
| `mode` | bounded LLM enum | `open_at_time` only for explicit-time open; omitted time defaults in Python to current time | disallowed modes fail closed | allowed after STT |
| `date` | `YYYY-MM-DD` | current business date | explicit-open must equal current business date | allowed, then Python validation |
| `start_time` | `HH:MM` | required for `open_at_time` | valid clock value and not later than current business time | allowed only through preview confirmation |
| `duration_minutes` | positive integer | required for duration close | 1..1440; existing close service remains final validator | allowed only through preview confirmation |

The bounded work-time slot extractor receives an explicit operation context.
Python owns structural numeric fallback (`H:MM`/`H.MM`), dates, current-time
default, workspace lookup, validation, preview, and execution.

## 6. Public route and convergence map

| Entry | Public owner | Guards | Shared result |
|---|---|---|---|
| text | `process_invoice_text` | authorization then active-FSM routing | existing work-time handlers |
| voice | `handle_voice` -> STT -> same text route/state handler | authorization before STT; active FSM first | same candidates/previews/services |
| button | shared decision callback | actor-scoped FSM state and active-state expiry | same confirm handler |
| `/dochadzka` | help only | authorization | examples/guidance, no write |

`voice.py` remains transport/state dispatch only and receives no business phrase
dictionary.

## 7. FSM graph and state ownership

```text
open_work_day + no explicit time -> WorkTimeService.open_day -> clear
open_work_day + explicit time -> waiting_open_preview_confirm
waiting_open_preview_confirm --approve--> open explicit time -> clear
waiting_open_preview_confirm --edit--> waiting_open_input
waiting_open_preview_confirm --cancel--> clear/no write
waiting_open_input --valid--> waiting_open_preview_confirm
waiting_open_input --invalid--> waiting_open_input/no write

add_work_time_entry + matching open day + duration
  -> waiting_close_preview_confirm
  -> existing approve/edit/cancel close graph
```

Unknown preview replies repeat the preview. Stale/missing candidate state clears
safely. Existing active-FSM ownership, global cancel/navigation, and inactivity
expiry remain unchanged.

## 8. Decision and callback contract

Both previews use the existing `approve_edit_cancel` family with canonical
`approve`, `edit`, `cancel`, `unknown`. Text and voice go through
`DecisionResolver`; buttons use `decision:*` and dispatch to the same handlers.
Only `approve` may write. The shared callback wrapper removes handled inline
markup; non-terminal edit replaces the valid input expectation. The current
generic decision callback has state/expiry protection but no per-card nonce;
that pre-existing broader hardening gap is not expanded in this repair.

## 9. Side-effect and ownership map

| Effect | Trigger/owner | Gate | Failure/idempotency |
|---|---|---|---|
| Insert open day/event | approved explicit preview or existing no-time open; `WorkTimeService.open_day` | authorization, workspace membership, same-day/open conflict validation | existing one-row-per-day behavior |
| Close open row/event | approved duration preview; `WorkTimeService.close_open_day` | bound open row, candidate validation, confirmation | no open row/no candidate fails without write |
| FSM metadata | work-time handlers | current actor/chat FSM | cleared on terminal outcomes |

No LLM, STT, callback payload, or InfoHelp layer performs a DB write.

## 10. Authorization, tenant, precision boundaries

Authorization precedes STT/LLM through existing middleware. Every lookup/write
uses Telegram actor plus the FSM-bound active `workspace_id`; membership is
revalidated before later writes. Exact start time and duration may arrive by
voice because this existing work-time flow previews and requires confirmation.
No cross-workspace fallback is introduced.

## 11. User-facing response and exit contract

- Explicit start: full Slovak preview with date and arrival time, inline
  approve/edit/cancel keyboard, pending open-preview state.
- Missing/invalid correction: Slovak prompt for a valid arrival time; state is
  retained and no write occurs.
- Approve: open-day summary and cleared state.
- Cancel: explicit no-change response and cleared state.
- Duration on open day: existing close preview shows derived departure and net
  hours; approve closes, edit asks for corrected departure/duration, cancel
  clears without changing the row.

## 12. Product Truth and InfoHelp contract

- Capability: `work_time_tracking`; status stays `partial`.
- Truthful subset: simple workspace-scoped open/close/manual entries and monthly
  report; explicit arrival and duration closing are preview-confirmed.
- Limitations: one row per day; no payroll/legal HR/multi-employee attendance;
  no broad editing of already closed rows.
- Forbidden claims remain unchanged. “Can you do this?” may answer yes only for
  the bounded subset. “How?” gives natural-language examples without executing
  an informational question.

## 13. Negative-space and regression contract

Do not change invoice/document routes, report periods, lunch calculation,
month deletion, closed-row conflict behavior, previous-open-day choices,
authorization, workspace isolation, global cancel, or exact destructive
confirmation. A full manual range must not be collapsed into a start-only open;
an open-at-time request must not become a closed duration row.

## 14. Acceptance scenarios

1. No open row; text/voice transcript `Zapíš príchod na prácu o 7.10.` ->
   `open_work_day`, `open_at_time=07:10`, open preview, no pre-approval write,
   approve inserts open `07:10`, state clears.
2. No open row; `Začínam pracovný deň.` -> immediate open at controlled current
   business time, unchanged behavior.
3. Open row at `07:10`; `Zapíš mi dnes 6 odpracovaných hodín.` resolves as
   `add_work_time_entry` but enters close preview; approve closes with 360 net
   minutes and no second row.
4. Open row; direct `Uzavri dnes 6 hodín.` -> existing close preview and same
   persistence result.
5. Explicit future/invalid start -> no write and recoverable open-input state.
6. Cancel/edit/unknown preview decisions preserve their documented effects and
   final states for text, voice, and button dispatch.
7. Standalone duration with no open row remains manual-entry preview.
8. Product Truth stays `partial`; capability question causes no write.
9. Workspace A open row is never read or closed from workspace B.

## 15. Out of scope and known gaps

No repair of the live erroneous 2026-09-09 row, migration, deployment, schema
change, closed-row editing, multiple shifts per day, payroll logic, broad action
learning, or generic callback nonce redesign. Production data repair requires a
separate backup/dry-run/approval gate.

## 16. Evidence index and verdict

- Live logs and read-only DB audit, 2026-09-09: STT preserved `7.10`, router
  selected `open_work_day`, DB stored only open `13:25`, and no close event.
- `bot/handlers/work_time.py`: current open/manual/close FSM owners.
- `bot/services/work_time.py`: current clock, slot extraction, and DB owners.
- `bot/handlers/invoice.py`: bounded action hints and public dispatch.
- `bot/handlers/voice.py`, `bot/handlers/decision_callbacks.py`: convergence.
- `tests/test_work_time_service.py`, `tests/test_work_time_routing.py`,
  `tests/test_voice_state_routing.py`: current regression base.
- Governing contracts listed in `AGENTS.md` and the task preflight.

Implementation evidence: focused service/routing/DecisionResolver coverage passed
(`829 passed`), and voice/callback/top-level-routing coverage passed (`335
passed`). Full repository evidence is recorded in the acceptance proof and
`PROJECT_LOG.md`.

Post-implementation operational note: after separate explicit approval, PR
#115 was merged and deployed as `32dd682`. The single incident row was repaired
under its own stopped-bot backup, exact-precondition, transaction, event-audit,
and readback gates; this does not expand the general runtime capability.

Verdict: `implemented_and_deployed`.

## 17. 2026-10-14 scoped arrival-versus-receipt semantic repair

Task: prevent the observed `Запиши мне приход.` -> `add_receipt` misroute.
The user explicitly authorized strengthening this semantic boundary. This is
an extension/quality repair of existing `open_work_day` and `add_receipt`,
not a new action, slot, FSM control, deterministic fast-path, or AI maturity
upgrade. Work-time and document intake remain `partial`; risk is bounded to
primary idle semantic selection and guidance. Current design matches the
invoice action hints, voice convergence and existing domain owners.

| Meaning / representative input | Expected primary result | Must not become |
|---|---|---|
| Personal arrival: `Запиши мне приход.`, `Запиши мені приход.`, `Запиши прихід.`, `Zapíš mi príchod.` | `open_work_day`, current business time when omitted | receipt upload or money receipt |
| Explicit arrival: `Запиши приход на роботу в 7.10` | `open_work_day`, existing explicit-time preview | current-time substitution |
| Explicit source document: `Додай чек`, `Добавь чек`, `Pridaj bloček` | `add_receipt`, existing photo/PDF waiting state | work-day opening |
| Financial receipt only: `Запиши приход денег`, `Zaznamenaj príjem peňazí` | `unknown` when no existing allowed action owns the requested financial operation | attendance or inferred document upload |
| Genuinely unclear arrival/income request | existing `unknown`/clarification route, no guessed write | inferred invoice, receipt or work day |

Change only the two primary `action_hints`: explain personal arrival shorthand,
provide illustrative SK/UK/RU examples and symmetric financial/document
negative space. These are meaning examples, never Python aliases or phrase
dictionaries. The existing LLM-first bundle and Python allowed-action
validation remain authoritative; no second classifier or InfoHelp veto follows
a valid action.

Sections 5-11 above continue to own slots, entry/authorization, FSM, shared
decisions, tenant isolation and effects. No-time open invokes the existing
workspace-bound service and clears the state; explicit time uses existing
preview confirmation; receipt intake waits for an attachment and never saves
on this utterance alone. Active FSM still wins; safe switching and old draft
restoration remain out of scope. No new keyboard/callback lifecycle is added.

Product Truth / InfoHelp retain `work_time_tracking=partial` and explain
arrival shorthand as attendance, never bank/cashflow recording or automatic
time detection. Exact-time confirmation and all earlier forbidden claims
remain. Broad action-alias learning is not implemented; this prompt repair
does not store transcripts, aliases or new business data.

Acceptance: inspect actual outbound primary payload from public text/voice
entrypoints; prove original utterance transfer, allowed actions, both semantic
boundaries, LLM-first routing and unchanged owner/side effects. Mocked model
outputs must be disclosed: they prove payload plumbing and Python execution,
not real GPT-4o recognition. Include genuine receipt and financial negative
cases, existing explicit-time and active-FSM safety tests, Product Truth/help
checks, and full repository tests. Live model/Telegram acceptance is a separate
not-yet-proven gate. No DB/schema/storage migration or production data repair
is needed; rollback restores these hints/guidance only, with no data rewrite.

Design verdict for this authorized scope: `ready_for_handoff`.

Local implementation follows this design (`design_matches_runtime`): focused
537-test and full 2720-test/7-subtest runs passed. The conversation proof's
2026-10-14 addendum records fixture versus real boundaries and the honest
`runtime_not_proven` live/deployment verdict.

Deployment follow-up: after explicit user approval, the scoped repair was
committed/pushed as `f5f605e` and deployed on 2026-10-14. SQLite backup and
rollback image were retained, post-start schema/table counts were preserved,
and all three changed runtime source hashes matched the container. Nine real
primary-bundle probes passed on GPT-4o; this proves the bounded model selection
cases, not a real audio/interactive Telegram conversation. See the acceptance
artifact's deployment follow-up for the remaining journey gap.

## 18. 2026-10-16 report-to-open incident and unresolved recovery gap

Live STT returned `Зароби мені, будь ласка, працівний вікас.` at 06:46:58
Europe/Bratislava. The primary bundle selected `open_work_day`; its real open
event at 06:47 proves the report request had a business side effect. The next
`Я попросила працьовний виказ.` correctly selected the report, but did not undo
the row. Explicit opening at 06:54 later resolved to the open action; the
stored start remained 06:47. Close at 15:39 worked correctly.

Current `WorkTimeService.open_day` same-day idempotency returns an existing
row as `already_open` without applying a different explicit start. The
explicit-open confirmation handler does not check requested versus returned
start before reporting success. A local temporary-DB replay proves this
behavior; the live slot/confirmation branch itself is not fully observable.
Earlier explicit-time design/acceptance must not be generalized to editing
an already-open or closed row.

The 2026-10-14 arrival/receipt repair is insufficient evidence for report/open
safety. A canonical token inside allowed_actions can still be semantically
wrong. No-time opening currently commits immediately. STT context also lacks
work-time domain vocabulary, though audio was not replayed and that omission
is not established as the sole recognition cause.

The approved manual repair corrected only the incident row to 06:54-15:39,
preserving closed status, configured lunch and prior audit history. It adds no
general editing capability and does not fix the runtime conversation.

Proposed next design, not implemented: preserve one bounded primary resolver,
improve report/open/close semantic negative space and STT vocabulary, require
a shared DecisionResolver preview before any opening write, and handle an
explicit different start on an existing open row with old/new preview and
actor/workspace/row-version validation. Never report an applied start when
the returned row differs. New keyboards, correction/cancel/stale handling,
Product Truth/InfoHelp and persistence rollback must be designed together.
No second free-form classifier, voice phrase dictionary or unconfirmed alias
learning is implied.

Acceptance must replay the actual noisy report, correction, explicit arrival
and closing sequence from public text/voice routes; inject a wrong open action
for a report and prove zero writes before confirmation. Include legitimate
arrival/receipt/report negatives, existing-row and repeated approval behavior,
workspace isolation, stale callbacks and final keyboard cleanup. The proposed
flow requires an approved complete design before implementation.

Verdict for that future runtime repair: `needs_architecture_revision`.

## 19. Explicit newer time priority — authorized correction design, 2026-10-16

### Identity, classification and truth

The user requests that a new explicit arrival/departure supersede an erroneous
stored boundary. Extend existing open_work_day / close_work_day and their
preview/edit/cancel flows; no new business action or decision family. Status
remains partial; bounded canonicalization plus Python validation, no learning
upgrade. Runtime owner: handlers/work_time.py and WorkTimeService. Risk medium
for user-confirmed single-row edits. This scope does not fix report/open model
selection, require confirmation for every no-time opening, or implement general
FSM switching. Existing empty-intake recovery remains separate.

### Canonical/semantic/slot contract

New explicit start on a stored dated open/closed row means change start only;
new explicit end means change end only (or close that open row). Preserve the
other clock and row id. A missing date means the current business date for
opening; closing retains its bound open/continuation date, otherwise today.
An explicit existing historical date may select only that same scoped row.
No historical row is created by open. No-time open stays idempotent; closing
now/duration does not silently rewrite an already closed row. Reports/help,
unknown/invalid data, skipped/day-off and duration-only records without an
actual start cannot become boundary corrections.

Reuse open_at_time/close_at_time slots: date ISO, one HH:MM boundary. LLM owns
bounded multilingual normalization, Python validates bounds and record scope.
Correction-aware extraction preserves an explicit date instead of replacing it
with the open row's date. Strict numeric no-LLM fallback stays structural and
must not invent a historical target. Current timezone remains Bratislava.

### Route, FSM, decisions and keyboards

Authorized idle text/voice -> existing primary action -> shared work-time owner
-> bounded slots -> scoped row -> old/new preview -> existing
waiting_open_preview_confirm or waiting_close_preview_confirm. Corrections
use the existing work_time_open_preview/work_time_close_preview
approve_edit_cancel contexts and text/STT/reply-keyboard buttons. Correction
previews intentionally use reply keyboards: generic old decision:* cards are
rejected while a correction is pending because their message ownership cannot
prove approval of this new snapshot. No new inline callback card is created.
Edit returns
to the respective input state and builds a fresh preview; unknown repeats the
frozen old/new preview; cancel/terminal failure/success clear FSM and remove
reply keyboard. The callback transport removes owned inline markup; forbidden
callbacks retain existing no-edit behavior. Expiry/navigation remain shared.
No clarification without its continuation state. A closed record remains
closed when start changes. New start never clears an end or reopens a day.

### Deterministic effects, snapshot and math

Preview stores original full WorkTimeDay, scoped event revision, lunch settings,
field and value. One BEGIN IMMEDIATE transaction revalidates actor/workspace,
row id/date/content, event revision and lunch settings before updating only
that row and appending one time_correction event. No-op confirmed values create
no event. Stale/repeated approval cannot overwrite a later change. No success
claims for an ignored requested time. Fresh-open preview also expects absence;
a concurrently created row must yield conflict, not already_open success.

Python validates existing start, dates not in future, boundary not in future,
and end >= start. For a closed explicit range it recalculates gross/net using
current configured lunch and stores explicit_end, clearing any prior duration
override/snapshot; preview discloses this. Existing duration-only and duration
closing behavior remains unchanged outside a confirmed explicit boundary edit.
Origin/note and the unedited boundary are preserved; no old event is removed.

### Persistence preflight and rollback

Current shape: work_time_days plus events/settings, workspace/actor scoped.
Proposed shape is identical: update one confirmed row, append one event. No
schema migration, backfill, old-row batch rewrite, storage/path change or
production operation. Audit/dry run is local temporary-DB replay of the
incident and historical cases with exact before/after fields and events.
Production deployment/repair still needs existing runbook backup/dry-run/
rollback gates and approval; none is performed by this local task. Reverting
code must retain correction rows/events; never restore a whole old DB over
new business activity. Transaction failure rolls back row and audit together.

### Product Truth, safety and acceptance

work_time_tracking remains partial. Explain confirmed correction of one dated
stored start/end, preserving the other clock. Explicitly exclude arbitrary
multi-shift editing, payroll, missing-clock inference, future times and automatic
corrections/learning. Update registries, Product Truth, Slovak InfoHelp, TZ and
PROJECT_LOG. Source of claims is executable owners plus public-entry proof.

Prove from public text/STT: stored 06:47 -> new 06:54 -> no pre-approval write
-> approve -> 06:54; closed 06:47-15:39 -> start 06:54 -> 8:45 gross / 8:15
net with lunch30; closed end correction 13:40 -> 13:10 preserves 07:10;
historical explicit dates; no-time repeat keeps old clock; unknown/cancel/edit,
invalid/future/reversed clocks; row/lunch change after preview; repeated/stale
approval; injected event failure rolls back; tenant/workspace isolation;
text/voice/button owner convergence and keyboards; old report/manual/duration
journeys unchanged. Model/STT fixtures must be disclosed; no live quality claim.

Design verdict: ready_for_handoff for this user-authorized correction slice.
Current evidence: service.open_day already_open behavior, existing explicit-open
and close FSM/DecisionResolver/voice/callback owners, October 16 and September
9-11 PROJECT_LOG incidents, governing implementation/evaluation/migration
contracts. The broader section 18 model safety proposal remains unresolved.

Local implementation follow-up: design_matches_runtime; full run2782 tests/
7 subtests passed, with final help-UI/raw-schema deltas covered by focused
97/16/7-case checks. The correction Conversation Acceptance Proof records
mocked model/STT boundaries and the runtime_not_proven live semantic/Telegram
verdict. No production operation or deployment occurred.

Deployment follow-up (2026-10-16): deployed as `5a3f3f8`, source-verified.
Three isolated real-provider journeys passed; polling/getMe passed. Actual
Telegram chat/audio remains pending login. The noisy report/open selection
defect is reproduced, unresolved. See the acceptance proof deployment section;
prior local-only verdicts describe their original evaluation stage.

## 20. 2026-10-19 symmetric arrival/departure prompt repair

Design verdict: ready_for_handoff for the user-authorized narrow semantic
repair. Product status stays partial; this is bounded canonicalization, no
new AI maturity level/learning domain. Class: extension of existing action
semantics; no new action/mode, Python parser, confirmation or FSM graph.

Need/evidence: production voice departure Запиши меню отход, будь ласка.
selected open_work_day. Owner confirms workplace UI uses отход/отходи for
leaving work and приход for starting. Existing arrival hint is stronger than
its departure counterpart; speech_to_text context omits attendance vocabulary.
Existing route/DB/confirmation evidence is in the work-time acceptance proof.
This does not replace the broader unresolved report/open safety design.

Route: existing authorization -> idle/explicit empty-wait guard -> one primary
LLM bundle with existing allowed_actions -> open_work_day for personal arrival
or close_work_day for personal departure -> existing Python work-time owner
and scoped service. Active drafts retain ownership, voice uses original STT
once. No post-classifier veto, dictionary route, retry cascade or alias learning.

Hints describe the semantic pair: приход/прихід/prichod records arrival;
отход/отходи/відхід/odchod records departure even when work/day words are
omitted. A surviving departure meaning in noisy personal wording must not
become arrival. Explicit finance/income/payment, waste/production scrap,
receipt upload, reports and capability questions keep their own boundaries.
Negated/conflicting/unrecoverable event meaning returns unknown rather than
inventing arrival. Examples illustrate meaning, never a whitelist.

Slots: existing bounded extractor also receives this event meaning. A clear
performative request to record the current personal departure with neither
end clock nor duration is an explicit current departure event (close_now),
even if the literal word now is omitted. Exact end/duration/date preserve
their existing modes and previews. Questions, past/future assertions, bare
ambiguous nouns and contradictory times are unknown; no missing clock is
guessed for a correction to a closed/historical day. Existing Python closed-
day and snapshot gates remain. Structural no-key parser is NOT expanded.

STT: append compact multilingual attendance spellings as vocabulary only;
keep transcribe/verbatim/no invented words/no semantic rewriting. No command
mapping, learned transcript alias, model migration, new endpoint or post-STT
repair. Whisper has limited prompt control; this cannot prove improved audio
recognition without a real audio replay. See official OpenAI speech-to-text
and prompt-engineering guides consulted2026-10-19.

Effects/UI: current no-time opening and explicit present departure close use
their existing immediate service paths; exact clocks/durations and persisted
corrections retain shared DecisionResolver previews and keyboard lifecycles.
No callback, tenant, DB schema, path, access, storage or calculation change.
No migration/backfill or production write. Code rollback is prompt reversion;
never undo later business rows. Deployment is a separate authorized operation.

Product Truth/help: explain partial arrival/departure terminology and exclusions
without promising perfect noisy speech, payroll, waste/income support or safe
interpretation of every bare word. No automatic alias learning: user-approved
meaning is curated prompt guidance, not a newly persistent learning feature.

Acceptance: real public text and voice/STT entry with temporary SQLite seed
an open day -> departure -> same row closed, preserved arrival/lunch/audit;
unknown/waste/finance/contradiction -> same row unchanged/no accounting save;
arrival keeps one-row idempotence. Assert original input, one primary call,
existing allowed modes and final FSM. STT request test checks vocabulary and
verbatim boundary; disclose fake audio/models. Live model-only probes must
use exact production primary/slot payloads and no business dispatch, including
incident text, wording not in examples and negative neighbors. Do not equate
those with real STT/Telegram/deployment acceptance.

Out of scope: universal no-time-open preview, existing report/open noisy gap,
report cancel-inline bug, default model migration, automatic learning, new
capabilities, server/deploy/commit/push and business data repair.

Section20 implementation follow-up: design_matches_runtime for local candidate.
Final sampled live primary18/18, slots8/8 and two temporary-DB real-provider
handler journeys pass; initial negative-space failures and harness/loopback
limits are disclosed in the acceptance proof. Final full suite repeated
2026-10-20: 2814 passed, 7 subtests passed in 674.70s (0:11:14). Real audio/interactive candidate
Telegram/deployment are not implied by that local evidence.


Section20 authorized release follow-up (2026-10-20): user requested finishing
the work after prior explicit publication/deployment instructions. Commit
62b1046 deployed with existing runbook backup/image rollback, bot-only
recreation and146 tracked Python source hashes matched. Actual deployed
primary18/18 and slots8/8 plus both real-provider/temp-DB handler journeys
passed without candidate code injection. Polling/getMe and schema/work-time
preservation passed. Real Telegram /dochadzka help responded and actor days/
events stayed unchanged. A preflight guard found an existing open actor row,
so no live attendance command was sent. No migration/customer-time repair,
real-audio acceptance, maturity upgrade or broad report/open fix is claimed.
See the existing acceptance artifact for exact evidence and remaining gaps.

## 21. 2026-10-20 report lunch-choice keyboard lifecycle repair

Verdict: ready_for_handoff. User requests fixing the previously reproduced
report-cancel inline-button defect. Class5: deterministic internal cleanup
strategy for existing generate_work_time_report, no new action/slot/decision
family. Work-time Product Truth stays partial; AI maturity unchanged.

Evidence: start_generate_work_time_report sends an inline yes/no lunch card
without storing its Telegram message reference; cancel_current_state clears
FSM and sends ReplyKeyboardRemove, which cannot remove inline buttons.
ActiveFsm guard cleans only InfoHelp/invoice-edit cards. Existing generic
callback cleanup does not establish message ownership before stale cleanup.

Route: existing authorized report text/voice/public owner -> unconfigured
lunch -> waiting_lunch_break_initial_choice and one tracked bot card. Store
only serializable chat/message/actor/workspace references in existing FSM,
not DB. Canonical yes/no remains shared DecisionResolver; exact valid buttons
converge into the same handler. No LLM/STT prompt or report calculation change.

Lifecycle: yes removes old inline card before asking minutes; no removes it
while continuing the existing report/settings operation; unknown retains one
card without adding duplicates. Global /cancel, shared text/voice cancellation,
/menu, /start, timeout and stale reset remove the tracked card before state
clear. Reply cleanup remains ReplyKeyboardRemove on exits. /dochadzka also
cleans the tracked report card before replacing the flow with help.

Callback guard: current lunch-choice buttons require exact tracked message,
chat, human actor and bound workspace. Missing/legacy/mismatched/forbidden
context never executes. Owned stale/duplicate private-chat cards can be
removed after cancellation or restart; no edit of a foreign/unproven message.
Malformed tokens retain a still-valid current card; failed cleanup is logged,
never presented as success and cannot roll back an already saved business
effect. No timer worker is added; timeout cleanup occurs on the next update.

Implementation owners: work_time.py sends/tracks/cleans its report card;
state_control.py invokes cleanup before clearing; active_fsm_guard.py supplies
the current message on navigation/stale exits; decision_callbacks.py checks
card ownership and exposes the real bot through its human-actor adapter.
Shared stale inline editing must require a private bot message addressed to
the callback actor unless an existing exact owner guard has proved ownership.

Acceptance: actual report owner with temporary SQLite and realistic bot-authored
callback messages -> cancel command/text/voice/navigation/timeout removes card,
no settings/day/event/report save. Yes/no text/voice/button keep existing
continuations/settings writes; unknown retains the card; duplicate/old versus
new card, missing/forbidden/wrong-workspace contexts cannot write or clear a
foreign card. Cleanup failure logs and safe state/business result are asserted.
Unchanged invoice/InfoHelp callback journeys cover the touched shared guard.

No schema/storage migration, business-time repair, new learning, semantic
report/open fix or general callback redesign. Update existing Product Truth,
InfoHelp, In_Action registry, acceptance proof and project log. Tests use mock
Telegram/STT/LLM explicitly; any deployment/live evidence is recorded separately.

Section21 implementation: design_matches_runtime. Focused185 tests passed;
final full suite: 2840 passed, 7 subtests passed in 701.04s (0:11:41). Live deployment/Telegram
evidence is recorded separately, never inferred from fixtures.


Section21 release follow-up:deployed d3a05ee with backup/image rollback and146
source hashes verified. Real Telegram report -> visible lunch yes/no -> /cancel
removed both buttons without another click; independent actor work-time and
settings snapshots unchanged. Polling/getMe/schema checks passed; scope
complete, partial capability/maturity unchanged. Existing acceptance proof
records fixture/live boundaries and known orphan/API-failure limitations.

## 22. 2026-10-20 close summary and optional day-specific break — design only

### 22.1 Task, evidence and preflight

Task: make the deduction visible after closing a day and allow an occasional
exception without asking about the break every day. The September 11 repair
in PROJECT_LOG records short days with unwanted deductions; this is a real
recovery need, not permission to infer breaks automatically.

Current status: `work_time_tracking` is `partial`; a day-specific break and
its post-close edit button are `planned`. Target: evaluated partial attendance
with this bounded extension, not payroll or an adaptive account engine. Risk:
high for persisted calculation semantics; routine Telegram UI risk otherwise.
Architect/date: Codex / 2026-10-20, following the user's request to study the
integration. This proof is not implementation, migration or deployment approval.

Read/rechecked: AGENTS; Product_Doctrine_2030; AI_Layer_Implementation_Standards;
Product_Truth_Layer and Registry_MVP_Design; Self_Learning_Layer;
Evaluation_and_Smoke_Test_Standards; Product_UX_Eval_Artifacts; TZ_FakturaBot;
LLM_Orchestrator_Contract; Canonical_Action_Registry; In_Action_Response_Registry;
New_Action_Design_Checklist; Bounded_Resolver_Prompt_Template; this architecture
proof contract; Canonical_Decision_Resolver_Contract; Info_Help_Guidance_Layer;
Customization_Request_Layer; Confirmed_Semantic_Alias_Learning_Contract;
Code_Agent_Handoff_Contract; Implementation_Agent_Checklist;
FakturaBot_Data_Migration_Runbook; User_Access_Model_Roadmap.

Scopes considered: routing, bounded LLM slots, FSM, confirmation, callbacks,
DB/calculation semantics, product/help/eval docs. STT stays transcription-only;
no model, access model, PDF, server, storage-path or tenant-ownership change.
No AI maturity upgrade: deterministic summary is UX/static guidance; bounded
extraction reuses the current layer. A one-day exception, silence, and Cancel
are not learning signals and must never change the usual setting or learn an
alias. This is not Level 7 adaptation or an implemented Level 5 handoff layer.

Current evidence exposes a distinction that the implementation must preserve:
`WorkTimeService.report_net_minutes` applies CURRENT settings to ordinary clock
rows, while confirmed net-duration rows have a fixed net override. Thus changing
the global setting can already recalculate unpinned historical report rows.
`test_explicit_range_report_subtracts_current_lunch_break` and
`test_duration_close_keeps_requested_net_and_extends_end_by_lunch` prove this.
Do not silently freeze all history or subtract twice. Existing snapshot fields
do not prove that a user explicitly chose a break for a particular day.

### 22.2 Architecture classification

Primary class 2: extension of existing `update_work_time_lunch_break`, with
scope/date/value slots and a child correction flow. The post-close card is a
deterministic presentation extension of `close_work_day`. No new top-level
action, menu command, decision family or general-purpose callback store is
needed. Class 3/4 describes components, not the primary business ownership;
class 5 alone would omit the new confirmed persisted exception.

### 22.3 Canonical owner

Keep `update_work_time_lunch_break` in Python-provided allowed_actions. Its
existing default-setting behavior remains; day scope is planned until shipped.
Extend `start_update_work_time_lunch_break` and the scoped `WorkTimeService`,
not voice.py business logic. New service methods proposed here are
`prepare_day_break_change` / `apply_day_break_change`; they do not exist yet.
Only eligible closed clock rows can receive the day exception in this slice.
Close-now keeps immediate completion; explicit-clock close retains its current
preview/confirmation and gains the same summary after successful save.

### 22.4 Semantic boundary

| Meaning/input | Action and slots | Must not become |
|---|---|---|
| `Dnes som nemala prestávku, oprav ju na nulu` | update_work_time_lunch_break, day/today/0 | reopen day or change default |
| `Za 19.10.2026 zmeň prestávku na 15 minút` | same action, day/explicit date/15 | correction to today |
| `Štandardne odpočítavaj 30 minút` | same action, default/no date/30 | one-day exception |
| `Zmeň prestávku` | same action, unknown scope/value -> pending clarification | assumed day/global write |
| `Zavri deň teraz` / `Zavri deň o 17:00` | existing close_work_day modes | break-edit confirmation |
| `Ukáž výkaz` / `Koľko prestávky odpočítavaš?` | report / informational answer | attendance mutation |
| `Oprav odchod na 15:39` | existing boundary correction | break edit |
| contradictory dates, negation, unrecoverable speech | unknown/clarification | guessed target/value |

Hints must include meaning, positive_examples and not_this, including nearby
read-only/report and time-correction intents. Examples illustrate semantics,
never a literal whitelist. The orchestrator's required hint fields prevail
over the template's older optional wording. No post-classifier veto, extra
top-level retry cascade, or expanded multilingual Python phrase dictionary.

### 22.5 Slots and calculation contract

| Slot | Bounds/source | Missing/invalid behavior |
|---|---|---|
| scope | day/default/unknown, bounded primary bundle; trusted button fixes day | ask scope, no inferred last-day default |
| work_date | ISO date or null from bounded extraction; Python resolves relative date in OFFICEFLOW_TIMEZONE | ask date for day scope; reject conflicting/future/missing row |
| minutes | integer 0..180 or null; bounded extraction or strict whole-number input in the minutes state | ask/retry; no guessed duration |

Python supplies business date and schema, validates all slots and transfers
them explicitly from primary diagnostics to the handler. It must not reparse
the full request with a separate business-language parser. Voice may provide
these bounded, previewed date/minute values under the documented work-time
exception; exact identifiers or destructive confirmations gain no voice route.
Minutes cannot exceed the validated gross clock interval. Zero is a real
exception, not absence. Clearing a saved exception back to the default is
deferred; setting another explicit value remains possible.

Proposed additive nullable `work_time_days.lunch_break_minutes_override`:

- NULL preserves existing rules; no historical backfill or reinterpretation.
- An integer including 0 means a confirmed exception for this row only.
- A valid closed clock row without an opaque net override is eligible. Rows
  with this new exception remain eligible for subsequent edits.
- `close_input_mode=duration`, net-only entries, or legacy manually pinned net
  rows without the new exception are excluded from this first slice, even if
  a derived end clock exists. Their confirmed net must not be reinterpreted
  as gross time. Explain this limitation; do not show a misleading edit button.
- For an eligible exception, gross is validated from clocks; net=gross-break.
  Store the exception, lunch snapshot, total and derived net override together.
  This net override is a compatibility projection, not a second deduction.
- One calculation owner returns gross/applied break/net and their provenance
  for summary, previews and reports. New exception takes priority; otherwise
  current legacy rules, including fixed net durations, remain unchanged.
- Existing `_proposed_boundary_day` must preserve an explicit day exception
  and recalculate its derived net on a later arrival/departure correction.
  Reject a corrected range shorter than that break; never silently erase it.

Changing the DEFAULT remains a separate confirmed path. Its preview must
disclose the existing recalculation of unpinned clock history; explicit day
exceptions keep priority. A future-only global policy is a separate decision.

### 22.6 Public routes and convergence

| Entry | Guards/resolution | Shared owner/result |
|---|---|---|
| idle text | authorization, active-FSM guard, one bounded primary bundle with slots | existing update owner -> scope/date/minutes/preview |
| voice | authorization before STT, same state guard and bundle on transcript | same owner/slots/preview; no voice-specific save |
| close result button | authorized human, active workspace, scoped row, fingerprint, no other FSM | same owner with immutable trusted day |
| numeric/decision reply buttons | exact bound state and pending context | same value or DecisionResolver handler as equivalent text/voice |
| /dochadzka | existing help owner | explanation only; no new command required |

An unrelated active FSM retains ownership. This feature does not extend the
existing narrowly defined empty-intake handoff or bypass a draft.

### 22.7 FSM graph and ownership

```text
close success -> save already complete -> summary + optional launcher -> idle
idle update -> [scope] -> [day date] -> minutes -> preview -> shared decision
button -> immutable day -> minutes -> preview -> shared decision
decision: approve -> atomic correction -> fresh summary -> idle
          edit -> minutes for SAME scope/day -> preview
          cancel -> unchanged saved day/default -> idle
```

Planned states: `waiting_lunch_scope`, `waiting_day_break_date`,
`waiting_day_break_minutes`, `waiting_day_break_confirm`; existing default
value/confirmation states keep their owner. Bracketed stages are skipped only
when validated slots already exist. Clarification must store the matching
pending state, not just send a question. Scope is immutable after preview;
retargeting requires Cancel and a fresh request. No automatic report parent
or suspended FSM is created by the post-close card.

Scope/date/minutes: unknown retains the state and explains the expected input;
no business writes. Confirmation unknown retains one preview; Edit replaces
it with the minutes prompt. Missing/deleted/ineligible row ends safely with
no correction. Stale snapshot refreshes old/new information and requires new
approval. Cancel, /start, /menu and reactive timeout clear pending metadata
and reply keyboard; already closed attendance stays closed. No Back control
is added; explain Edit/Cancel as the available recovery controls.

### 22.8 Decisions, callbacks and keyboard lifecycle

Use shared `approve_edit_cancel`, new context `work_time_day_lunch_break_confirm`.
Register it in resolver and handler tests. Text, voice and visible Slovak
`Schváliť / Upraviť / Zrušiť` reply buttons converge. Do not let an old generic
`decision:*` inline card approve this reply-keyboard flow. Confirmation expiry
is 15 minutes, checked on updates, with actor/workspace/day binding and a
fresh preview fingerprint. No background timeout worker is claimed.

Proposed launcher payload: `wtb:<day_id>:<YYYYMMDD>:<24 hex fingerprint>`;
even a 19-digit SQLite id fits Telegram's 64-byte limit. The fingerprint is
a truncated SHA-256 over canonical row, scoped day-event revision and relevant
settings; it is a staleness token, NOT authorization. Python loads only through
the active workspace AND authorized actor, checks date/id, and revalidates
membership. No cross-workspace fallback or silent profile switch.

The launcher makes no business write and is valid across restart while that
context is unchanged; it has no fixed expiry. A stale but proven-owned card
loses markup and gets a fresh summary. Malformed, missing, foreign or wrong-
workspace targets never write; without proven ownership no markup is edited.
An unrelated active FSM rejects the launch without changing that state/card.
Duplicate launch during the child flow cannot replace its pending context.

On a valid launch remove the parent's inline markup and start the child.
Unknown input retains one current input/preview. Terminal success, Cancel,
navigation, expiry and owned stale exit remove reply controls with
ReplyKeyboardRemove; clear pending state, then offer a refreshed day summary
when still accessible/eligible. Navigation continues to its requested owner.
Telegram edit/send failures are logged; they never roll back a committed day
or falsely report cleanup success. Retry/duplicate approval checks database
revision, not whether Telegram successfully removed a keyboard.

### 22.9 Side effects and atomicity

| Effect | Trigger/owner | Gate and failure behavior |
|---|---|---|
| close existing day | current close owner/service | existing close gates unchanged; summary only after commit |
| summary/launcher send | handler after committed close/correction | current scoped row; Telegram failure does not undo save |
| pending FSM data/UI cleanup | validated launcher/text owner | no business save; ownership before markup editing |
| one-day correction | proposed apply_day_break_change | shared approval + BEGIN IMMEDIATE + exact row/event/settings snapshot + current membership/workspace |
| correction audit event | same service transaction | one `lunch_break_correction` old/new event; duplicate/stale approval writes nothing |
| global setting | existing default owner only | explicit default scope and existing confirmation; no day edit touches it |
| monthly report file | existing explicit report request | same calculation owner; day edit does not silently regenerate/send files |

Correction preserves id/date/arrival/departure/closed status, other days,
other actors/workspaces and default settings. A failed transaction changes
neither row nor event. After commit, transport failure is a delivery failure,
not permission to apply again. Keep sensitive text out of callback/audit fields.

### 22.10 Access and precision

Authorization precedes LLM/STT, DB/business storage and temporary files.
Every row/event/settings query and write uses existing workspace_id plus
telegram_id boundaries. Callback source is the bot message; actor is the
human callback sender, not message.from_user. Recheck membership and active
workspace at preview and apply. No admin bulk repair, foreign day lookup,
automatic contact/document save or new exact-value voice permission.

### 22.11 Response and exits

Example only, not a claim that this UI exists:

```text
✅ Pracovný deň je uzavretý.
20.10.2026 · 08:00–17:00
Trvanie: 9 h
Odpočítaná prestávka: 30 min
Odpracované: 8 h 30 min
[Upraviť dnešnú prestávku]
```

No daily question and no new closing approval. Ignoring the inline launcher
leaves FSM idle and permits the next task. Show 0 honestly when deduction is
disabled/unconfigured; do not claim that the person physically took a break.
User-approved label for the current-day close card: `Upraviť dnešnú prestávku`.
The callback remains bound to that saved date; an older message must never
silently retarget the correction to the date on which the button is pressed.
Preview a day edit with exact date, clocks, old/new break and old/new net,
explicitly saying the usual setting is unchanged. Cancel says the correction
was cancelled, not that closing was cancelled. Success returns this day's
current summary and optional launcher. For duration/pinned records, label net
hours as confirmed, avoid inventing an observed break, and explain why this
particular day-break editor is unavailable.

### 22.12 Product Truth and help

Capability id remains `work_time_tracking`, overall `partial`. Currently this
extension is `planned`. Only after runtime/eval acceptance may registry,
Product Truth, InfoHelp and TZ describe eligible day exceptions as supported
within that partial capability. `Can I change today's break?` must be answered
informationally, never executed. Future truthful guidance: use the post-close
button or explicitly ask for a dated break correction; preview/approve; the
usual setting and other days remain. Explain duration/manual-net exclusions
and historical effects of changing the DEFAULT. No claim of payroll/legal
compliance, automatic actual-break detection, perfect STT or all-history locks.

### 22.13 Negative space

Do not steal reports, capability questions, arrival/departure corrections,
receipt/invoice intake or existing active FSMs. Preserve close-now behavior,
net-duration semantics, explicit clock confirmations, old report setup and
October 20 keyboard cleanup. No silence-based save, alias/default learning,
customer-time repair, auto-report generation or forced daily interaction.

### 22.14 Acceptance contract — required, not yet run

Each case must enter the real public owner with temporary scoped SQLite,
record input/action+slots/state/effects/final UI, and disclose provider mocks.

| Case/precondition and exact input | Required result |
|---|---|
| open08:00/default30; `Zavri deň teraz` at17:00 | close_now -> one saved close -> idle; 9h/30min/8h30 summary + launcher, no new question |
| same row; `Zavri deň o 17:00` | existing preview -> shared approve -> same final summary |
| ignore launcher; `Ukáž výkaz za október` | idle report owner, no hidden break state/write |
| closed09:00–14:00/default30; launcher -> `0` -> approve | minutes -> preview -> idle; day0/net5h, one event, default30 and other days unchanged; monthly row/sum5h |
| `Za 19.10.2026 zmeň prestávku na 15 minút` in text/STT | same scoped dated owner/preview; no modification of today's row |
| `Zmeň prestávku` -> `iba dnes` -> `0` | stored scope/date/minutes continuation, no write before shared approval |
| `Ako zmením prestávku?` | truthful capability explanation, no FSM save or business mutation |
| minutes -1/181/>gross, conflicting dates/values, unknown | clarification/retry with no mutation; no guessed zero/date |
| preview -> Edit/Cancel/global Cancel/menu/start/expiry | same-day edit or safe idle/navigation; expected keyboard cleanup; saved closing intact |
| default30 -> day0 -> confirmed default60 | day0 remains0; ordinary unpinned history retains existing recalculation policy |
| explicit day15 -> confirmed arrival/departure correction | preserve15, recalculate derived net; too-short interval rejected |
| duration/pinned legacy row, default then changes | fixed net preserved, no edit launcher/double deduction |
| changed row/event/settings/membership/profile after preview | stale/rejected, no overwrite; new approval required where eligible |
| duplicate approval; restart/duplicate/malformed/missing/stale/foreign launcher | at most one event; owned stale cleanup only; no foreign edit or cross-tenant lookup |
| unrelated active FSM; unauthorized text/voice/button | preserve state; unauthorized no AI/storage/effects |
| Telegram cleanup/send fails before/after save | logged failure, no false cleanup claim, no repeated/rolled-back business save |
| additive migration on copied legacy DB | all new fields NULL; old rows/report totals identical before any explicit exception |
| export/import/workspace copy and rollback rehearsal | exception/derived net retained; no unsafe old-writer activation |

Name tests after these cases in work-time service/routing/time-correction,
callback/keyboard, access/workspace, Product Truth/InfoHelp and migration suites.
Include unchanged default/report and invoice/intake journeys. Full pytest plus
Conversation Acceptance Proof is required for completion. Real-provider probes
and authorized Telegram smoke are separate evidence, never implied by mocks.

### 22.15 Migration, rollout, rollback and exclusions

Affected persisted data: days/calculation fields and new correction events;
settings are read but not rewritten by day scope. Current/proposed shape is in
22.5. No migration of invoices, paths, originals or tenant keys is needed.

Before any migration-sensitive implementation/write, obtain scoped approval
under AGENTS and the migration runbook. Current study authorizes docs only.
Prepare a read-only SQLite audit (mode=ro/query_only) of schema, ownership,
clock/duration/pinned rows, inconsistent intervals and report totals, with
row/event fingerprints. Prepare explicit dry-run/apply migration tooling; it
is planned, not an existing operational command. Dry-run a copied DB; add only
the nullable field and prove unchanged legacy totals and tenant isolation.

Fresh DB schema may include the field; existing production initialization must
not silently ALTER it on startup. Before activation, take a consistent verified
backup and record schema/image/fingerprint rollback checkpoints. Readers must
tolerate the old schema while the UI is disabled. A planned day-break feature
flag defaults off and enables launchers/new edits only after schema readiness.
Readers and boundary writers must still honor already saved exceptions when
the flag is subsequently disabled. Audit workspace-copy/migration field lists.

Before the first exception, an old image can ignore the additional NULL column.
After an exception, the compatibility net projection preserves old report
reads, but old writers may erase that projection or leave it inconsistent.
Therefore rollback means disable new entry points while retaining compatible
calculators/writers, or stop work-time writes pending a compatible forward fix.
Do not claim arbitrary old-image writes are safe. Never restore a whole backup
over later business activity or delete exceptions to make rollback easier.

Deferred: editing duration/opaque manual-net rows through this editor, clearing
an exception back to NULL, global-history freezing, multi-shift attendance,
payroll, generic draft switching, broader noisy report/open remediation,
self-learning, implementation, customer data repair, commit/push and deploy.

### 22.16 Evidence index and verdict

Runtime evidence: bot/services/work_time.py (`WorkTimeDay`, `_scope_condition`,
`close_open_day`, `add_manual_range`, `add_duration_entry`, `report_net_minutes`,
`_proposed_boundary_day`, prepare/apply_boundary_change, `_day_revision`);
bot/services/db.py work_time_days/settings/events schema; bot/handlers/work_time.py
start_update_work_time_lunch_break, current confirmation and result owners;
invoice.py primary slots dispatch/hints; semantic_action_resolver.py slots
diagnostics; voice.py/shared state guard and decision_callbacks.py ownership.
Current Product Truth: bot/services/product_truth.py `work_time_tracking`.
Contracts are listed in22.1; historical repair and released state in PROJECT_LOG.

Verified during this design session: the two existing service tests named in
22.1 passed (2 passed, 39 deselected). This proves current semantics only, not
the planned feature. No code, schema, server or customer row changed.

Verdict: `ready_for_handoff` for this bounded architecture proposal. Required
product/migration approval and read-only implementation verification remain
gates; the verdict does not authorize writes or assert runtime completion.

Section22 implementation follow-up (2026-10-20, local working tree): user
explicitly requested implementation after reviewing the design and current-day
label. Read-only verification: design_matches_runtime; no material semantic
deviation. Existing action/primary slot transfer, scoped service calculation,
day-specific confirmed exception, dated read-only launcher, child FSM and
text/STT/reply-button convergence are implemented behind flag/schema gates.
Close summaries always remain presentation-only; the optional launcher is a
second inline message after reply-keyboard removal. This Telegram presentation
detail changes no state or approval semantics.

The explicit migration CLI adds no startup ALTER/backfill and requires a pinned
baseline, verified SQLite backup and writer-freeze confirmation. Copy tooling
was reviewed and its actual dynamic table-copy owner fixture-tested with an
explicit zero/derived-net projection. New day corrections derive gross from
validated clocks; unedited legacy report rules remain unchanged. Compatible
readers/writers honor exceptions even when the entry flag is off.

Preflight/approval/implementation plan: PROJECT_LOG day-break implementation
entry. Local tests/evidence and final verdict are owned by the existing
Conversation Acceptance Proof, new October20 day-break section. Product Truth,
InfoHelp, canonical/in-action registry, LLM contract, TZ, README and migration
runbook describe the gated partial slice. No new action, model, learning or
maturity level. Server migration/deployment/customer data repair and real-audio
acceptance have not occurred. The earlier planned status describes the design
checkpoint; this follow-up records the local candidate, not production support.

Section22 final local validation:47 feature cases passed; final full suite2915
passed plus7 subtests in744.71s. All264 frozen Python source/test hashes match;
existing Conversation Acceptance Proof verdict safe_to_commit for the gated
local scope. No production migration/deploy/real-provider acceptance implied.
