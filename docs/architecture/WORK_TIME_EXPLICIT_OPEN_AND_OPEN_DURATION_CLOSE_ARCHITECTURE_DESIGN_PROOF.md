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
