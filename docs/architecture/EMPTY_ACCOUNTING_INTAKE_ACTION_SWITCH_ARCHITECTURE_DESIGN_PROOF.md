# Empty Accounting Intake Action Switch — Architecture Design Proof

## 1. Identity and product need

2026-10-16. User-authorized correction to the October 14 recovery gap: a
mistaken receipt action entered upload waiting, and a subsequent explicit
work-day request could not escape it. Cancel/menu/start already work.
Target: allow a clear new executable request to replace only proven empty
accounting upload waiting. Product status remains partial; risk medium.

## 2. Classification

Extension of existing state-aware routing, not a new business action. Existing
canonical actions and their execution owners remain authoritative. This is
not general fresh-FSM switching or an editor of saved work-time records.

## 3. Action contract

No new canonical token. Source is exactly
`AccountingDocumentIntakeStates:waiting_upload`. Destinations are existing
primary allowed actions with Python owners, excluding unknown, reserved
send_invoice/edit_invoice, repeated add_receipt and runtime issue capture
(which already has its own active-flow interrupt).

## 4. Semantic boundary

| Input in empty upload waiting | Result | Must not become |
|---|---|---|
| Explicit start work / open today at 07:07 | Existing open owner | upload instruction loop |
| Explicit report or another executable task | Existing primary-selected owner | inferred attachment content |
| Capability/how-to, unclear/noisy input, bare yes/value | Preserve source flow | guessed switch/write |
| Photo/PDF | Existing intake owner; mark processing begun | idle classifier |
| Cancel/menu/start | Existing global navigation | new switch mechanism |

Primary resolver receives the source state and expected attachment input as
context. The navigation resolver remains unchanged. A switch requires a valid
real primary bundle business_action result; local fallback on model outage is
insufficient. No phrase dictionary, probe/replay classification, confidence
threshold or post-action InfoHelp classifier is introduced.

## 5. Slots

Existing action schemas remain unchanged. Original text/STT, channel, request
and update identity reach the same owner, including primary report slots.
Python still validates dates/times, workspace and confirmations. No slots are
inferred from the old upload state.

## 6. Public routes

Authorized text: authorization middleware -> active FSM middleware -> existing
primary router in empty-intake mode -> original execution owner.
Authorized voice: authorization -> STT -> same guard -> same primary router.
No second primary call. Attachments remain state-owned. No new command/button.

## 7. FSM and preservation

Empty means exact source state and only the three shared FSM activity keys
(or no keys). Fresh age is required by the guard. Any other key, even an
empty candidate/path or unknown metadata, disables this exception.

Source -> primary unknown/help/fallback/error: source and data stay unchanged.
Source -> supported new action: revalidate exact snapshot -> clear source ->
existing target owner -> that owner's normal state/exit.
Changed snapshot -> no switch. No useful draft is discarded or restored.
After handing off, target errors/rollback belong to its existing owner; do
not restore old state over a potentially committed target effect.

Upload marks processing begun under the same per-FSM process-local lock used
for final switch revalidation/clear. Thus downloads/extraction in flight are
not mistaken for empty waiting. Key is the aiogram storage key, independent
of the FSMContext object. Lock lifetime is weakly held; no persistent storage.
Current runtime uses one process and in-memory FSM. This is not a distributed
locking or multi-worker guarantee.

## 8. Decisions and keyboards

No additional switch confirmation: the explicit new executable request is
the instruction to abandon an empty waiting state. No file/draft exists.
Every target's DecisionResolver and destructive/exact-value gates remain.
Source starter creates no keyboard. On accepted switch, send a short Slovak
explanation with ReplyKeyboardRemove before the target shows its own UI.
Unknown/blocked source retains its UI; no callback/inline ownership changes.
No claim that a work day was saved before its actual owner succeeds.

## 9. Effects

Guard/claim owns only source FSM clear and navigation copy. Upload marker is
FSM-only. Existing target owns all DB/files/external effects and validation.
No new schema, stored-data rewrite, migration, filesystem cleanup or server
operation. Rollback is reverting this routing slice; target data stays valid.

## 10. Authorization and scope

Authorization still precedes text guard, voice STT and primary LLM. No tenant
data is added to the prompt. Existing owners resolve/revalidate workspace
membership. Different actors/chats/storage keys cannot claim one another's
source state. No cross-workspace state restoration or guessed data cleanup.

## 11. Responses and exits

Accepted switch: explain that upload waiting ended and process the new
request. Target preview/success/error and final FSM are unchanged. Unknown or
capability question does not launch a task; existing source response remains.
Cancel/start/menu retain their existing terminal cleanup.

## 12. Product Truth and InfoHelp

Existing add_receipt_or_incoming_invoice and work_time_tracking remain partial
for their bounded surfaces. Guidance may explain replacing empty receipt
waiting with a new explicit request; it must not claim arbitrary draft
switching, saved-time correction, new model quality or automatic learning.
Capability questions alone do not trigger the target action or clear source.

## 13. Negative space

Any file, candidate, intake session metadata, processing marker, other FSM,
reserved action, unknown/help result, local model fallback, or state drift
blocks the exception. Fresh non-empty FSM ownership remains unchanged. Stale
recovery, runtime issue capture and global navigation retain their owners.

## 14. Acceptance

Public text middleware and public voice handler: fresh empty waiting -> exact
explicit arrival -> existing open preview -> shared approve -> one correct
row/event, no accounting document or upload. Test no-time arrival and report
slot transfer; one primary bundle per update. Fixtures are not live STT/model
proof. Unknown/help/reserved/same action/outage preserve source. Processing,
candidate, unknown key, changed snapshot and foreign FSM do not switch. Test
different FSMContext objects with same storage key against upload/claim race.
Assert reply keyboard removal, target preview, final state, tenant no-effect,
cancel/start regressions and existing upload acceptance. Run focused and full
tests; record missing real Telegram/audio/model evidence honestly.

## 15. Out of scope

Saved work-time editing, model migration, STT vocabulary, general draft
suspension/restoration, new confirmations, server writes, deploy, push and
production repair. No action-alias learning from this event.

## 16. Evidence and verdict

Owners: active_fsm_guard.handle_active_fsm_text_update;
accounting_document_intake.cmd_accounting_document_intake/accounting_document_upload;
invoice.process_invoice_text; voice.handle_voice. Existing tests:
test_active_fsm_guard, test_work_time_routing, test_voice_state_routing.
Contracts: AGENTS.md, LLM Orchestrator section 5A, Architecture Design Proof,
New Action Design Checklist, DecisionResolver, implementation and evaluation
standards. This explicit empty-source exception extends section 5A; it does
not claim the previously deferred general switching feature.

Design verdict: ready_for_handoff for this user-authorized narrow scope.

Implementation follow-up: design_matches_runtime; local full suite passed
2746 tests / 7 subtests. Live model/audio/Telegram acceptance is still
runtime_not_proven; see the linked conversation acceptance proof.
