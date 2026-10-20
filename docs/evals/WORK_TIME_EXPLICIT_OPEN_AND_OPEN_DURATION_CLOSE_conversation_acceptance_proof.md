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

### Deployment and real-model follow-up, 2026-10-14

The user explicitly authorized deployment. Runtime commit `f5f605e` was
published and deployed through the private runbook, with a consistent SQLite
backup and retained prior image at
`/bot/backups/arrival-routing-20261014T091913Z`. Startup/polling succeeded;
Cloudflare stayed up; schema and all business-table counts matched the backup,
SQLite quick_check returned ok, and the invoice/InfoHelp/Product Truth source
hashes matched the running image.

The actual deployed `process_invoice_text` supplied its primary bundle kwargs
to a capture function that deliberately aborted before dispatch. Then the
real resolver/OpenAI boundary was invoked with those same allowed actions and
hints for nine synthetic requests. No business handler, FSM mutation, DB write
or Telegram send ran in these probes. The non-admin bundle was used; input
was already text, so STT/audio and authorization middleware were outside this
probe. Every result used `resolution_source=llm_bundle`, and OpenAI returned
`response.model=gpt-4o-2024-08-06` with configured `gpt-4o`.

| Probe | Actual result | Expected result | Result |
|---|---|---|---|
| `Запиши мне приход.` (two separate calls) | `open_work_day` twice | `open_work_day` | pass |
| `Запиши мені приход.` | `open_work_day` | `open_work_day` | pass |
| `Zapíš mi príchod.` | `open_work_day` | `open_work_day` | pass |
| `Додай чек.` | `add_receipt` | `add_receipt` | pass |
| `Pridaj bloček.` | `add_receipt` | `add_receipt` | pass |
| `Запиши приход денег.` | `unknown` | `unknown` | pass |
| `Zaznamenaj príjem peňazí.` | `unknown` | `unknown` | pass |
| `Запиши приход на роботу в 7.10` | `open_work_day` | `open_work_day` | pass |

Operational result: deployed, 9/9 bounded real-model probes passed. The earlier
local-only verdict is superseded for model selection and deployment. A complete
real-user audio/interactive Telegram journey remains `runtime_not_proven`;
fresh-FSM safe switching remains out of scope.

Separately approved operational recovery: after the user confirmed 07:07 and
one notification, one workspace-scoped open-day row was inserted for
2026-10-14 through the existing service in a single outer transaction, with
open/manual-correction events. Other days/events remained unchanged; an
independent mode=ro readback verified one open row, start 07:07, no end/total,
both audit events and integrity_check=ok. A private Telegram notice was then
accepted with the verified recipient/text; no incoming voice conversation was
exercised. The data-repair backup and delivery receipt are retained under
`/bot/backups/work-time-open-recovery-20261014T093148Z`; identifiers stay private.
This operation adds no general repair/automatic-notification capability.

## 2026-10-16 observed failed report/open sequence

Production runtime remains the earlier deployed code. Private scoped evidence:
`/bot/backups/work-time-1016-audit-20261016T142025Z/evidence.json`.

| Actual input / business time | Actual action/effect before manual repair | Verdict |
|---|---|---|
| STT `Зароби мені, будь ласка, працівний вікас.` / 06:46:58 | `open_work_day`; persisted open at 06:47 instead of a report | fail |
| STT `Я попросила працьовний виказ.` / 06:47:18 | `generate_work_time_report`; earlier accidental open remains | report route passes; recovery incomplete |
| STT `Відкриття працьовного дня 6.54.` / 06:54:30 | `open_work_day`; row retains 06:47; slot/approval details not fully logged | requested arrival not reflected |
| STT `Закрий мені працьовний день зараз.` / 15:39:20 | `close_work_day`; persisted correct end 15:39 | pass |

A temporary service-level replay separately proved an already-open 06:47 day
returns `already_open` and 06:47 when an explicit 06:54 start is requested.
This replay is code-path evidence, not a real voice/model test. The earlier
nine live semantic probes did not cover the noisy report or this sequence.

User-authorized data repair was completed with a consistent SQLite backup at
`/bot/backups/work-time-1016-correction-20261016T142233Z`, one guarded
transaction and one appended correction event. Independent readback proves
exactly one closed 06:54-15:39 row, 525 gross minutes, 495 net minutes under
the unchanged 30-minute lunch policy, and integrity_check=ok. Other work-day
rows and prior events were unchanged. No runtime patch/deployment or new
notification was performed.

Verdict: incident data repaired; report-to-open safety and existing-start
correction remain `failed_runtime_acceptance`, not fixed by the data repair.

## 2026-10-20 optional day-break correction — local candidate

Design: section22 of the existing work-time Architecture Design Proof. User
approved implementation and the current-day label `Upraviť dnešnú prestávku`.
Design verification: design_matches_runtime. Working tree based on3d52699;
not committed/deployed. The following evidence applies to this extension, not
the unresolved noisy report/open incident above.

Environment: Windows/Python3.12, synthetic actor1001 and isolated workspace
fixtures, controlled Bratislava business clock2026-10-20 17:00, temporary
SQLite/Excel and real additive migration/backup operations on fixtures only.
Telegram methods, STT audio and OpenAI responses are mocked. Actual Python
primary-prompt serialization/action validation/slot transfer, public handlers,
shared DecisionResolver and storage owners run. Windows sandbox socketpair
creation hung before test execution; local tests were rerun with loopback
access. No production credentials, original audio or real messages were used.

### Public traces and observed outcomes

| Scenario/input and precondition | Observed route, state, effect and final UI | Evidence/result |
|---|---|---|
| open08:00/default30; `Zavri deň teraz` at17:00 | primary close_work_day -> close_now owner -> one closed row; no extra approval; FSM/data empty; gross9:00, break30, net8:30; reply removal then optional current-day launcher | test_public_close_finishes_idle_and_optional_button_does_not_start_flow[False], pass |
| same; `Zavri deň o 17:00` | primary close_work_day -> close_at_time -> existing boundary preview; no save until shared approve; same final summary/idle | same test[True], pass |
| eligible closed day; `Dnes som nemala prestávku, oprav ju na nulu`, text and STT | primary update_work_time_lunch_break + day/2026-10-20/0 transferred to existing owner -> dated preview, no mutation; Schváliť -> shared approve -> atomic exception0/net540, same id/clocks/status; one correction event; idle + refreshed launcher | test_public_day_zero_break_preserves_default_other_day_and_report[text/voice], pass |
| same day; optional button -> `0` -> Schváliť | human/private bot/actor/workspace/day/fingerprint guard -> parent inline removed -> minutes -> same preview/approve/service; no business effect on click alone | same test[button], pass |
| another day19.10 has net510/default30 | day20 correction leaves other day/default unchanged; generated real Excel date20 row9h, total17h30; duplicate approval adds no event | same test, pass |
| `Zmeň prestávku` -> `iba dnes` -> voice `pätnásť minút` -> voice `Schváliť` | primary unknown scope -> waiting_lunch_scope -> waiting_day_break_minutes -> shared preview -> net525/exception15, then idle; temporary audio removed | test_scope_clarification_then_voice_minutes_and_shared_voice_confirmation, pass |
| ignore launcher -> `Ukáž výkaz za október` -> `Ako zmením prestávku?` | no hidden break FSM; report runs then informational guidance without attendance mutation; current-day card remains optional | test_ignore_button_then_public_report_and_help_do_not_enter_break_edit, pass |
| day already has exception0; `Зміни сьогодні прихід на роботу на сьому годину` | primary open_work_day -> open_at_time07:00 -> old08:00/new07:00 preview; shared approval changes only arrival, keeps17:00/closed/exception0, derived net600; no second row; later default60 does not alter600 | test_day_exception_survives_later_public_arrival_correction_and_default_change, pass |
| pending preview; row/settings/event changes before approval | approve writes nothing; refreshed old/new preview requires another approval; only the second valid approval appends one correction event | test_stale_snapshot_no_overwrite_and_new_approval_needed, pass |
| pending child; Zrušiť,/cancel,Edit,unknown,expired; menu/start/timeout/help | saved closing unchanged; Edit retains day and removes reply controls; unknown keeps confirmation keyboard; terminal/navigation clears child pending state and removes replies; eligible day summary refreshed | test_child_controls_cleanup_and_preserve_saved_closing + test_navigation_cleanup_preserves_day_and_leaves_child_flow, pass |
| foreign/malformed/missing/active/stale/disabled/cleanup-failure launcher | no attendance writes; foreign/unproven messages untouched; unrelated FSM preserved; owned stale markup removed and current data shown; API cleanup failure logged with safe pending flow | test_launcher_ownership_staleness_and_cleanup, pass |
| workspace/membership/actor changes after preview | no correction to either scoped workspace row; no event | test_authority_change_between_preview_and_confirmation_cannot_write, pass |
| other FSM starts during Telegram cleanup; Cancel during slot extraction | new pending state cannot take over/resurrect the old flow | test_callback_does_not_take_over_flow_started_during_telegram_cleanup + test_unknown_or_cancel_during_slot_extraction_cannot_resurrect_flow, pass |
| Telegram result send fails after approved commit | exception0 and one event persist; state idle; failure logged, no retry/rollback/false cleanup claim | test_committed_correction_survives_result_delivery_failure, pass |
| invalid boolean/negative/>180 minutes, malformed/future date, malformed scope | Python rejects or stores appropriate clarification, no save/default guess | test_invalid_break_has_no_service_write + test_invalid_extracted_slots_clarify_without_write, pass |
| duration/pinned net; old generic inline approve at new reply preview | no day editor/double deduction; old inline cannot approve new snapshot | test_fixed_net_exclusion_and_old_inline_cannot_approve_new_preview, pass |
| flag off after saved exception; later boundary correction | no new launcher, reads preserve exception; shortened interval below break rejected; corrected start recalculates compatible derived net | test_disabled_entry_and_later_boundary_keep_saved_exception, pass |
| legacy gross field disagrees with clocks | old unedited report unchanged; preparation read-only; approved correction derives gross/net/projection from clocks consistently | test_day_break_rederives_gross_from_clocks_without_silent_legacy_backfill, pass |
| copied old DB without new column | init_db does not add column; old reads unchanged; stale baseline/unconfirmed freeze cannot apply; approved fixture apply verifies backup and unchanged business digest; all new values NULL | test_explicit_schema_migration_preserves_legacy_values_and_no_startup_alter, pass |
| existing workspace table-copy owner | explicit zero/derived net and clocks survive copying into scoped target | test_existing_workspace_copy_preserves_explicit_zero_and_compatibility_net, pass |
| `Ako zmením prestávku?` | partial truth/help, flag/schema condition and fixed-net exclusions explained; public question no mutation; payroll/autodetection exclusions retained | test_truth_help_explain_feature_gate_and_no_daily_prompt + public question trace, pass |

### Design-to-code, effects and regression map

- Existing update action/hints and slot transfer: invoice.py; bounded
  continuation in services/work_time.py; no voice business parser. No new
  command; /dochadzka remains informational. Public dispatch always transfers
  a slot object, so missing provider slots clarify rather than entering the
  old direct-call default-setting compatibility adapter.
- Existing work_time handler owns the new scope/date/minutes/confirmation
  states and read-only launcher. Day binding is immutable; canonical reply
  buttons and voice use shared work_time_day_lunch_break_confirm. Snapshot,
  current membership/workspace and preview expiry gate one service transaction.
- WorkTimeDay optional field, old-schema SELECT NULL compatibility,
  day_calculation/report owner and boundary writer preserve the precedence:
  explicit exception, otherwise existing fixed net/default behavior.
- State-control/active-FSM/decision-callback/voice shared integration is scoped
  to the new flow; existing report-card cleanup and invoice/intake journeys
  are exercised by the regression suite. Authorization middleware still runs
  before AI/temporary storage; the new owners additionally recheck access.
- DB correction and event commit together; no other rows/settings change.
  Summary/launcher/cleanup are transport effects; failure cannot undo a save.
  Monthly Excel remains explicit/on-demand, not auto-regenerated by correction.
- Product Truth/InfoHelp, canonical/in-action registries, LLM contract, TZ,
  migration runbook/README/changelog/log match the gated partial local slice.
  No self-learning, maturity upgrade, payroll/HR or perfect-STT claim.

### Verification and operational boundary

Focused new feature:47 passed in40.64s. Earlier broad work-time/shared-decision
regression run:994 passed in148.26s; final full-suite result is recorded below.
Additional real CLI smoke on a synthetic old-schema SQLite fixture: audit and
dry-run produced identical aggregate reports, integrity ok and writes_performed
false; DB file SHA-256 stayed identical. Apply without required parameters exited2
before writes. Sanitized audit/dry-run JSON retained outside Git. This is local
tool acceptance, not a production migration or audit.
Python source/test manifest frozen before the final run; JUnit retained outside
Git. Full-suite evidence must match that manifest before this candidate is
marked safe_to_commit.

No server audit/migration, customer-row repair, real-provider/audio test,
interactive Telegram, commit/push/merge or deployment was performed. These are
not inferred from fixtures. Production activation remains default off and needs
the approved read-only audit/backup/fingerprint-pinned migration/readback under
the runbook. After a real exception, rollback must retain compatible writers;
an arbitrary old image is unsafe for subsequent work-time edits.

Final full suite:2915 passed,7 subtests passed in744.71s (0:12:24), exit0.
All264 frozen Python source/test hashes still match the tested candidate;
git diff --check passed. JUnit: work-time-day-break-full.xml retained in the
task artifact directory. No source changed during the final full run.

Verdict: `safe_to_commit` for this gated local candidate and fixture-proven
scope. This is not commit/merge/deploy approval or production acceptance.
Production rollout is separate; the broader noisy report/open issue remains
unresolved. Real model/audio/Telegram and production migration remain unrun.

### Authorized production activation and deployed-provider follow-up

User explicitly approved the explained schema change on the server and
commit/push/merge/deployment. Runtime665b497 was published in PR#117 and merged
as9a88536. Image13576138 is running with the feature enabled and schema ready.
This supersedes the preceding local-only limitation for deployment/provider
evidence; original audio and interactive Telegram feature acceptance are still
unrun.

Private checkpoint: /bot/backups/day-break-deploy-20261020T124359Z contains
before.sqlite, verified migration backup, original environment/logs, old image
referenceef2e4cc2, pinned audit/dry-run/apply/readback JSON and rollback notes.
Only the bot was stopped/recreated; cloudflared id/start time did not change.
Every pre-existing table value was equal immediately after the additive ALTER;
all new fields NULL. Final live64 days/196 events/2 settings, scoped monthly
report vector/totals, FK checks and integrity stayed unchanged. No customer-time
write/exception/repair was executed. Other .env values were preserved; only
WORK_TIME_DAY_BREAK_ENABLED=1 was introduced. Existing Google binding check
timestamps changed on startup (last_attempt_at,last_successful_check_at,
updated_at); binding rows and all other values were independently verified.

Actual deployed147 Python source hashes match merged Git blobs. Python3.11.17,
gpt-4o/whisper-1 unchanged. Telegram getMe, startup/polling and restarts0 passed;
no error, traceback or polling conflict. pytest is absent from the runtime image;
no dependency was installed. The full2915+7 regression result remains the local
tested candidate proof, not a claim of server pytest execution.

Deployed real-provider trace uses actual process_invoice_text, primary/slot
prompts, shared decisions and service owners in a separate interpreter. Real
gpt-4o; controlled17:00 clock; authorized synthetic workspace/actor; SQLite/Excel
under a verified isolated /tmp directory; fake Telegram transport (no messages):

| Exact input / state | Observed effect and final state | Result |
|---|---|---|
| `Zavri mi pracovný deň teraz.`; open08:00/default30 | existing close_now -> closed17:00/net8:30, idle and current-day launcher | pass |
| `Dnes som nemala prestávku, oprav ju na nulu.`; idle | day/date/0 -> dated preview, no save until Schváliť; exception0/net9h, usual30 unchanged, one event, idle | pass |
| `Зміни сьогодні прихід на роботу на 07:00.`; closed with exception0 | old08:00/new07:00 preview -> shared approval; keeps17:00/closed/exception0, net10h, idle | pass |
| `Ukáž výkaz za tento mesiac.`; idle with optional launcher ignored | one real temporary Excel report, no hidden break FSM, idle | pass |

Sanitized source/runtime/provider/CLI evidence retained in the task artifact
directory; final live audit independently proves no production attendance effect.
Verdict remains safe_to_commit for the implemented slice, now published and
activated by explicit user approval. This does not claim original-STT/audio,
interactive Telegram UI acceptance, perfect noisy intent safety or payroll.
