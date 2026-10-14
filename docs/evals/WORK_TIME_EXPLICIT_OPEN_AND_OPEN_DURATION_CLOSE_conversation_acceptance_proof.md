# Work-Time Explicit Open And Open-Duration Close — Conversation Acceptance Proof

Date: 2026-09-10

Status: `deployed`; `work_time_tracking` remains `partial`.

## Accepted journeys

| Journey | Expected observable result | Evidence |
|---|---|---|
| `Відкрий робочий день` | One open row at controlled current Bratislava business time; no confirmation because no exact time was supplied. | `test_open_work_day_without_time_uses_current_business_time` |
| `Запиши приход на роботу в 7.10` | Preview shows 07:10; no DB write before approval; approval creates the open row at 07:10. | `test_open_work_day_with_explicit_dotted_time_requires_preview_and_uses_that_time` |
| Explicit future arrival | No DB write; flow remains in recoverable exact-time input. | `test_open_work_day_with_future_time_requires_correction_without_write` |
| Corrected `7:10` | Returns to explicit-open preview without losing FSM ownership. | same routing test |
| Open day + `Запиши мені сьогодні 6 відпрацьованих годин` | Existing row enters close preview; approval closes that row with 360 net minutes; no second same-day row. | `test_add_work_time_duration_closes_existing_open_day` |
| Text, voice, or decision button at open preview | All converge on the same handler and shared DecisionResolver family. | `tests/test_voice_state_routing.py`, `tests/test_decision_callbacks.py`, `tests/test_decision_resolver.py` |

## Locked regressions

- A dotted value such as `16.07` in close context remains ambiguous and must
  not silently become 16:07.
- `close_now` is allowed only for an explicit now/teraz equivalent.
- Unknown, invalid, canceled, future, or stale explicit-open candidates do not
  write.
- Duration is confirmed net worked time; lunch is added only when deriving a
  displayed departure and does not reduce the confirmed duration.
- Voice transport contains no business phrase dictionary, and every write
  remains Python-owned and workspace-scoped.

## Automated evidence

- Focused service/routing/DecisionResolver suite: `829 passed`.
- Voice/callback/top-level routing suite: `335 passed`.
- Full repository suite: `2708 passed, 7 subtests passed`.

## Scope boundary

No schema/storage migration, payroll logic, general closed-row editor, or
multi-shift support is included. After separate explicit approval, PR #115 was
merged and deployed as `32dd682`; the single confirmed 2026-09-09 incident row
was repaired only after a stopped-bot content-matching SQLite backup and exact
precondition audit. The repair is recorded in `PROJECT_LOG.md` and is not a
general editing capability.

Verdict: `passed_and_deployed`.

## 2026-10-14 arrival-versus-receipt hint repair (local addendum)

Design: section 17 of
`docs/architecture/WORK_TIME_EXPLICIT_OPEN_AND_OPEN_DURATION_CLOSE_ARCHITECTURE_DESIGN_PROOF.md`,
authorized by the user's request to strengthen personal arrival semantics.
Environment: local working tree based on `91a0b1ce`; synthetic actor 1001,
fresh FSM, temporary SQLite initialized with the current schema, controlled
business clock 2026-10-14 07:07. This addendum is not deployed evidence.

Public traces are executable in
`tests/test_work_time_routing.py::test_arrival_receipt_boundary_public_entry_payload_and_effects`
for each of text (`process_invoice_text`) and voice (`handle_voice`). Voice STT,
primary OpenAI responses, no-time slot output and unknown-help responses are
fixtures; the actual primary prompt serialization, allowed-action validation,
Python dispatch, domain owner, SQLite effect and final FSM are real. The actor
is already authorized at handler entry; authorization middleware is outside
these traces and unchanged. No production calls or credentials are used.

| Exact input, both channels | Fixture bundle result | Observed route/state/effect | Result |
|---|---|---|---|
| `Запиши мне приход.` | `open_work_day/business_action`, no time slot | Existing open owner -> one open row at 07:07 -> idle; repeated request leaves one row; synthetic other actor has no row | pass |
| `Запиши мені приход.` | same | same | pass |
| `Zapíš mi príchod.` | same | same | pass |
| `Додай чек.` | `add_receipt/business_action` | Existing document-intake owner -> `waiting_upload`, asks for photo/PDF, zero work-day/invoice writes | pass |
| `Запиши приход денег.` | `unknown/unknown` | Existing guidance owner -> idle, response, no work-day/invoice writes or attachment waiting state | pass |
| `Zaznamenaj príjem peňazí.` | same | same | pass |

Every trace checks unmodified input in the outbound primary payload, both
action IDs plus unknown in allowed actions, arrival positive semantics and
symmetric document/money exclusions. No reply/inline keyboard is created by
these unchanged branches; final response markup is absent, fixture audio is
removed, and no invoice or accounting-workspace directories are created.
Unknown and receipt cases show no work-time row; all cases show zero invoices.
Existing explicit-arrival, preview-confirmation, active-FSM and Product Truth
tests cover unchanged neighboring journeys; this repair adds no new callback,
confirmation, missing-slot, cancellation or unauthorized entry policy.

Evidence: 12 new public-entry parameter cases passed. Combined focused
work-time/service/voice/primary-routing/Product Truth/InfoHelp/FSM suite:
537 passed. Full `python -m pytest -q`: 2720 passed, 7 subtests passed.
Product Truth remains partial; guidance explains arrival at work and excludes
money/receipt semantics. `git diff --check` passed.

Real GPT-4o recognition, real audio STT, interactive Telegram and deployed
acceptance were not run. Fixture outputs do not prove that GPT-4o now chooses
the expected actions. Fresh-FSM safe switching remains the documented gap.

Verdict for this addendum: `runtime_not_proven` (local payload and execution
checks pass; live semantic recognition/deployment remain unproven).
