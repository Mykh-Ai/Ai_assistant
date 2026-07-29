# Telegram Keyboard Lifecycle Audit - 2026-07-29

## Verdict

`needs_revision`

The repository has bounded decision and callback safety contracts, but keyboard lifecycle requirements were historically scattered. The audit found seven runtime keyboard families. Normal terminal handling is generally safe, but timeout/stale cleanup and cleanup-failure observability are inconsistent.

This artifact records the one-time inventory and remediation status. It is not a parallel architecture contract. Normative ownership remains in `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`.

## Scope And Method

Inspected active code and focused tests for:

- every `ReplyKeyboardMarkup`, `ReplyKeyboardRemove`, and `KeyboardButton` under `bot/`;
- every `InlineKeyboardMarkup`, `InlineKeyboardButton`, and `edit_reply_markup` under `bot/`;
- every `@router.callback_query` handler under `bot/handlers/`;
- public-wrapper tests that assert final reply or inline keyboard state;
- terminal success, no/cancel, timeout, owned stale/expired, forbidden, retry/back/edit, and Telegram cleanup-failure behavior.

No server or live Telegram operation was performed. External Telegram edit failures remain mocked.

## Inventory

| Family | Type | Runtime owner | Normal terminal cleanup | Negative/stale cleanup | Test evidence | Audit status |
|---|---|---|---|---|---|---|
| Business profile selector | reply | `bot/handlers/business_profiles.py` | `ReplyKeyboardRemove` on select/cancel/no/unavailable | global cancel now removes | exact switch and cancel assert final removal | repaired |
| OfficeFlow attachment proposal | reply | `bot/handlers/officeflow_attachment_router.py` | `ReplyKeyboardRemove` on no/cancel/missing draft | shared intake timeout previously omitted removal; repaired in this audit | focused timeout/cancel flow | repaired |
| Accounting document intake | reply | `bot/handlers/accounting_document_intake.py` plus global state control | save/cancel/error paths remove | global cancel and shared timeout previously omitted removal; both repaired | focused success/cancel/timeout tests | repaired |
| Shared `decision:*` surfaces | inline | `bot/handlers/decision_callbacks.py`, factories in `bot/keyboards/decision.py` | handled callback clears markup | state-less/stale/expired cleanup repaired; forbidden authority remains fail-closed | public-wrapper yes/no/stale and cleanup-failure tests | repaired |
| Invoice due-date follow-up | inline | `bot/handlers/invoice_followup.py` | mark-paid/remind-later/mute clear markup | owned expired/legacy cleanup repaired; cross-tenant forbidden intentionally retains | focused handler and workspace tests | repaired |
| Contact registry lookup | inline | `bot/handlers/contacts.py` | valid pick/action transitions clear or replace | expiry is combined with nonce/actor validation, so safe cleanup authority is not separately represented | callback/FSM tests; lifecycle assertions incomplete | open |
| Contact registry background monitor | inline | `bot/handlers/contact_registry_monitor.py` and `bot/services/contact_registry_monitor.py` | applied/dismissed clear | service distinguishes stale/expired/forbidden/missing, but handler leaves all rejected markup and silently ignores cleanup failure | applied-path test only | open; concurrent uncommitted scope |

## Confirmed Findings

### KBD-001 - Reply keyboard timeout cleanup

`bot/services/temp_intake_session.py::ensure_intake_session_active` cleared FSM state and temporary files but answered without `ReplyKeyboardRemove`. This affected both OfficeFlow attachment proposal and accounting intake timeout exits.

Status: repaired. The shared timeout response now removes the reply keyboard. Focused tests assert the final markup.

### KBD-002 - Global cancel reply keyboard cleanup

The earlier `state_control_router` consumed accounting `Zrusit` text before the local FSM handler and cleared state without removing the reply keyboard. Accounting category states were also missing from temp cleanup coverage.

Status: repaired before this audit and retained in the inventory.

### KBD-003 - Shared decision stale inline cleanup

Handled shared decision callbacks removed markup, but state-less/stale/expired paths returned before cleanup.

Status: repaired before this audit. Owned obsolete markup is removed without business dispatch.

### KBD-004 - Invoice follow-up expired inline cleanup

Normal invoice follow-up decisions removed markup. Parsed expired or legacy callbacks were owned obsolete reminder cards but intentionally retained their buttons.

Status: repaired. Expired/legacy cards now clear markup before the stale alert. Cross-supplier or otherwise forbidden callbacks still do not edit markup.

### KBD-005 - Cleanup authority is not modeled consistently

Several handlers use one stale message for malformed, expired, missing, replayed, and forbidden outcomes. Cleanup is safe only after actor/message/workspace ownership is proven. The contact registry lookup handler needs an explicit validation result before stale cleanup can be changed safely.

Status: open.

### KBD-006 - Telegram cleanup failures are not consistently observable

`invoice_followup.py`, `decision_callbacks.py`, and `contacts.py` log inline cleanup failures. The concurrent uncommitted `contact_registry_monitor.py` handler still swallows generic exceptions. A live connection failure there can therefore look identical to a lifecycle bug.

Status: partially repaired. Shared decision and contact lookup cleanup failures now log without rolling back committed business effects. The concurrent uncommitted monitor handler remains open.

### KBD-007 - Test evidence is uneven

Business profile and OfficeFlow tests previously proved FSM/business results without always asserting final keyboard state. Some contact callback tests still call dispatch helpers directly instead of the public callback wrapper, which cannot prove markup removal.

Status: partially repaired. Business-profile select/cancel, OfficeFlow no/timeout, accounting preview timeout, and shared decision cleanup-failure paths now assert lifecycle behavior. Contact lookup and monitor evidence remain incomplete.

## Required Remediation Order

1. Keep the repaired global cancel, intake timeout, shared decision stale, and invoice follow-up expiry behavior covered by focused tests.
2. Introduce a small typed callback validation result for contact registry lookup so `expired/owned_stale` and `forbidden/unproven` are distinct before cleanup.
3. For contact registry monitor, remove markup on `stale` and `expired`, retain it on `forbidden` and `missing`, and add handler tests. Coordinate with its current uncommitted implementation before editing.
4. Add redacted logging to the remaining monitor cleanup helper.
5. Add missing contact lookup and monitor final-keyboard assertions.
6. Run the callback/reply-keyboard focused suite, then the full suite when feasible.

## Acceptance Matrix For Future Audits

Every keyboard family must prove:

- keyboard creation and bounded labels/tokens;
- equivalent text/voice/button convergence where promised;
- terminal success final state and keyboard;
- no/cancel/global-cancel final state and keyboard;
- error and timeout final state and keyboard;
- owned stale/expired cleanup with no business side effect;
- forbidden/unproven ownership with no business effect and no foreign message edit;
- non-terminal retry/back/edit retaining or replacing the correct keyboard;
- cleanup API failure logging and preservation of already committed effects;
- tenant/workspace isolation and duplicate-click/idempotency behavior.

## Evidence Run In This Audit

- `python -m pytest -q tests\test_temp_intake_session.py tests\test_officeflow_attachment_router.py tests\test_accounting_document_intake_flow.py tests\test_invoice_followup_handler.py` - 94 passed.
- `python -m pytest -q tests\test_business_profiles_handler.py tests\test_decision_callbacks.py tests\test_contact_registry_flow.py` - 37 passed.

Broader verification and remaining remediation are recorded separately; this `needs_revision` verdict must not be upgraded until KBD-005 through KBD-007 are resolved or explicitly accepted.
