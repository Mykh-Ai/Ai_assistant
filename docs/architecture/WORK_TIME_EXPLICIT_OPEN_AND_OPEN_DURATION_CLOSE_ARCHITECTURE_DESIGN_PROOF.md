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
