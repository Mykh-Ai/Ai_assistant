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
