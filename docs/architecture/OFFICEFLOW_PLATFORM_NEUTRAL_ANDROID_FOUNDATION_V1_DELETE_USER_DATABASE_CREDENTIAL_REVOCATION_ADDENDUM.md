# OfficeFlow Platform-Neutral Android Foundation V1 — `/vymazat_databazu` Credential Revocation Addendum

Status: **approved normative addendum** to
`docs/architecture/OFFICEFLOW_PLATFORM_NEUTRAL_ANDROID_FOUNDATION_V1_ARCHITECTURE_DESIGN_PROOF.md`

Verdict: `ready_for_handoff`

Approval date: 2026-08-19

This addendum is part of the approved Stage A design. Where it is more specific than the parent proof about `/vymazat_databazu` / `delete_user_database`, this addendum controls. It does not authorize any broader Android, API, FSM, Product Truth, or business-feature expansion.

---

## 1. Product Meaning Of `/vymazat_databazu`

`/vymazat_databazu` is not merely a command that removes selected business rows. It is the existing irreversible **account/business reset** action for the current OfficeFlow/FakturaBot user.

Its user-visible purpose remains:

1. permanently delete the user's current business/workspace data according to the existing deletion contract;
2. remove the user's current access to the product by moving access state to `deleted_database`;
3. require fresh administrator approval before the user may start again;
4. after Stage A API credentials exist, permanently invalidate every previously issued API credential belonging to that same internal principal so that an old device cannot regain access after later re-approval.

The command must therefore establish a **new trust boundary after deletion**. Re-approval may reactivate the person, but it must never reactivate credentials that existed before the deletion event.

This preserves the current promise in `bot/handlers/delete_user_database.py`:

- business data is permanently deleted;
- access is removed;
- a future connection is possible only after new administrator approval.

Stage A extends that promise to first-party API credentials.

---

## 2. Architecture Classification

Primary class: **extension of the existing destructive top-level action `delete_user_database` side-effect contract**.

This is not:

- a new top-level action;
- a new canonical token;
- a new FSM;
- a new slot;
- a new confirmation family;
- an Android-specific action;
- a public API account-deletion endpoint.

The existing public action and confirmation architecture remains authoritative:

```text
/ vymazat_databazu or resolved delete_user_database intent
    -> existing authorization
    -> DeleteUserDatabaseStates.waiting_exact_confirmation
    -> exact typed text: "vymazať databázu"
    -> UserDataDeletionService
    -> destructive reset
    -> FSM clear
    -> final deletion response
```

Voice remains excluded from the exact final confirmation. No button or API shortcut is added.

---

## 3. Canonical Action And Confirmation Contract

Canonical action: `delete_user_database`

Existing owner:

- public/FSM owner: `bot/handlers/delete_user_database.py`;
- destructive service owner: `bot/services/user_data_deletion.py::UserDataDeletionService`.

Existing exact confirmation remains unchanged as the security boundary:

```text
vymazať databázu
```

Rules:

- wrong text -> no deletion and no credential revocation;
- cancel -> no deletion and no credential revocation;
- voice -> still rejected for the exact destructive confirmation;
- unauthorized user -> no deletion and no credential revocation;
- only the same confirmed destructive execution that deletes the account data may revoke all API credentials for that account.

API credential revocation must not become independently reachable from the normal `delete_user_database` confirmation through a weaker route.

---

## 4. Identity And Data Ownership Contract

The deletion action receives the current authenticated Telegram actor under the existing flow.

For API-access cleanup, Python resolves the Stage A internal principal through the existing mapping:

```text
telegram actor
    -> principal_external_identity(provider="telegram", subject=<telegram id>)
    -> principal_id
```

If no principal/external mapping exists because the user never received API enrollment, deletion continues with the existing business-data behavior. Missing API identity is **not** a deletion blocker.

If an active mapping exists, that principal is the only API credential scope affected.

Do not delete or merge another principal.

`workspace_id` remains the business-data tenant boundary. `principal_id` is only the platform-neutral person/access identity.

---

## 5. Required Destructive Side Effects

After the exact typed final confirmation, the database phase must atomically perform the existing account reset plus Stage A credential invalidation.

Required logical transaction:

```text
resolve current actor's principal if present
    -> revoke all non-revoked api_session rows for that principal
    -> revoke all pending api_enrollment rows for that principal
    -> execute existing scoped business/workspace deletion
    -> mark authorized_users.status = deleted_database
    -> commit
```

The exact internal ordering may follow the safest SQLite ownership pattern, but the externally observable contract is atomic for database state: the system must not commit a state where business data was deleted but pre-delete API credentials remain usable.

### API sessions

For every `api_session` owned by the principal:

- an already revoked row remains revoked;
- every currently non-revoked session receives permanent revocation state/timestamp;
- its existing access token must fail;
- its existing refresh token must fail;
- later `/approve` must not make that row usable again.

Do **not** physically delete the session row merely to revoke access. Retain bounded control-plane/audit history.

### API enrollments

For every `api_enrollment` owned by the principal:

- `pending` enrollment becomes revoked with revocation timestamp;
- `consumed` remains consumed;
- already revoked remains revoked;
- an old raw enrollment secret can never create a post-deletion session.

Do **not** issue a replacement enrollment automatically.

### Principal and external identity

Do **not** delete:

- `principal`;
- `principal_external_identity(provider="telegram", ...)`.

Those rows are minimal control-plane identity/audit continuity, analogous to retaining the `authorized_users` row with `deleted_database` status rather than pretending the person never existed.

Business data is destroyed; active credentials are revoked; minimal control-plane identity remains.

---

## 6. File Deletion And Failure Contract

Existing filesystem cleanup remains after the database deletion transaction under the current `UserDataDeletionService` contract.

If local file cleanup partially fails:

- the database reset remains committed;
- API sessions/enrollments remain revoked;
- access remains `deleted_database`;
- the existing partial-files warning path remains valid;
- a filesystem cleanup error must never roll credentials back into an active state.

If the database transaction itself fails before commit:

- business DB deletion must roll back;
- API credential revocation from that transaction must roll back with it;
- `deleted_database` must not be partially committed;
- filesystem destructive cleanup must not start from a failed DB transaction.

No new remote Drive deletion is authorized by this addendum.

---

## 7. Re-Approval Contract

After successful `/vymazat_databazu`:

```text
business data deleted
+ authorized_users = deleted_database
+ all previous API sessions permanently revoked
+ all pending API enrollments revoked
+ principal/external identity retained
```

If an administrator later executes the existing approval flow:

```text
/admin approve
    -> user becomes active again
    -> fresh business onboarding may proceed
    -> Telegram access may work under the existing approval contract
```

But Android/API access must behave differently:

```text
old access token   -> invalid
old refresh token  -> invalid
old enrollment     -> invalid
```

Re-approval must **not** clear `api_session.revoked_at`, restore token hashes, reopen pending enrollments, or otherwise revive pre-deletion credentials.

To use Stage A API again, the administrator must explicitly issue a **new one-time enrollment**. That enrollment creates a new API session after successful exchange.

This is a fresh trust event, not restoration of an old credential set.

---

## 8. Distinction From Temporary Blocking

This addendum changes only `delete_user_database` semantics.

A normal temporary `block` continues to rely on current `AccessControlService` status to deny API use while blocked. This addendum does not redefine block/unblock behavior.

`delete_user_database` is stronger:

- temporary block = current authorization is denied;
- database deletion/account reset = current authorization is denied **and all pre-delete API credentials are permanently revoked**.

Do not generalize destructive credential revocation to unrelated access-state transitions without a separate approved design.

---

## 9. User-Facing Response Contract

The existing exact-confirmation UX remains. The warning/final copy may be minimally synchronized so it does not imply that only Telegram access is affected once Stage A API access exists.

Required meaning before final confirmation:

- business/workspace data will be permanently deleted;
- current product access will be removed;
- existing first-party/API access credentials, if any, will be invalidated;
- future use requires new administrator approval;
- future API use additionally requires a new administrator-issued enrollment.

Do not claim an Android application exists.

Do not expose internal words such as `principal_id`, token hash, session row, or database table names to ordinary users.

The existing partial-files outcome remains allowed, but it must not imply credentials remain active merely because some local files could not be removed.

---

## 10. Negative Space

This change must not:

- weaken or replace the exact typed destructive confirmation;
- make voice sufficient for final confirmation;
- add an API deletion endpoint;
- add an Android deletion flow;
- delete `principal` or Telegram external identity;
- physically purge session/enrollment audit rows as the default revocation mechanism;
- automatically issue new credentials after deletion;
- automatically restore API access after `/approve`;
- change workspace ownership semantics;
- alter unrelated users' sessions/enrollments;
- alter temporary block/unblock semantics;
- add external service calls;
- delete remote Drive files;
- change Telegram FSM routing beyond the minimum truthful copy synchronization if needed;
- change any other canonical business action.

---

## 11. Side-Effect Ownership Map

| Side effect | Trigger | Python owner | Validation before effect | Failure / rollback | Idempotency |
|---|---|---|---|---|---|
| resolve principal for current actor | exact confirmed delete | principal identity owner / bounded in-connection helper | authenticated existing actor | missing principal is allowed; continue old deletion | deterministic mapping |
| revoke all API sessions for principal | exact confirmed delete | `ApiSessionService` or a small in-connection helper owned by it | principal mapping belongs to actor | same SQLite transaction as account reset | already revoked rows remain revoked |
| revoke pending enrollments | exact confirmed delete | `ApiEnrollmentService` or a small in-connection helper owned by it | principal mapping belongs to actor | same SQLite transaction | consumed/revoked rows remain terminal |
| existing business/workspace DB deletion | exact confirmed delete | `UserDataDeletionService` existing owners | existing account/workspace scoping | transaction rollback on DB failure | existing deletion semantics |
| set `deleted_database` | exact confirmed delete | existing access-control deletion helper | same actor | same transaction | existing semantics |
| local file cleanup | after committed DB reset | `UserDataDeletionService` existing filesystem owner | existing scoped path validation | partial-files result; DB/credential reset stays committed | existing bounded cleanup |

LLM/STT/LMM never owns or authorizes any of these effects.

---

## 12. Acceptance Scenarios

### A1 — delete with active API session and pending enrollment

Precondition:

- authorized user with business data;
- one active API session;
- one additional pending enrollment;
- valid principal mapping.

Input:

- existing `/vymazat_databazu` flow;
- exact typed final confirmation `vymazať databázu`.

Expected:

- business data/workspaces deleted per existing contract;
- user status becomes `deleted_database`;
- active API session permanently revoked;
- pending enrollment revoked;
- principal and Telegram external identity remain;
- FSM clears and existing final deletion outcome is shown.

### A2 — pre-delete access and refresh tokens never revive

Precondition: A1 completed.

Expected:

- old access token fails;
- old refresh token fails.

Then administrator re-approves the user.

Expected again:

- same old access token still fails;
- same old refresh token still fails.

### A3 — pre-delete pending enrollment never revives

Precondition: A1 completed and old raw pending enrollment secret is known by the test.

Then administrator re-approves the user.

Expected:

- exchange of the old secret still fails;
- no new session is created.

### A4 — fresh enrollment after re-approval

Precondition:

- account was deleted and later re-approved;
- old credentials remain terminal.

Expected:

- admin may issue a new enrollment;
- new enrollment is distinct from old terminal credentials;
- new exchange can create a fresh session;
- no pre-delete session row is reactivated.

### A5 — user never had API identity

Precondition:

- normal existing user/business data;
- no principal/external mapping;
- no API session/enrollment rows.

Expected:

- `/vymazat_databazu` behaves exactly as before;
- missing API identity is not an error;
- existing deletion and `deleted_database` result succeed.

### A6 — unrelated principal isolation

Precondition:

- user A and user B each have principals, sessions, and enrollments.

Delete user A.

Expected:

- only A's API sessions/enrollments are terminalized;
- B's credentials and business data are unchanged.

### A7 — wrong confirmation / cancel

Expected:

- no business deletion;
- no session revocation;
- no enrollment revocation;
- no access-status mutation.

### A8 — voice precision boundary

Input: spoken/voice exact phrase while in final destructive state.

Expected:

- current typed-only safety boundary remains;
- no business deletion or credential revocation from voice alone.

### A9 — database failure is atomic

Inject a DB failure before commit.

Expected:

- business DB state rolls back;
- API session/enrollment state rolls back;
- `deleted_database` is not committed;
- filesystem cleanup is not started.

### A10 — local file cleanup partial failure

Precondition: DB reset succeeds; one scoped local file deletion fails.

Expected:

- business DB deletion remains committed;
- access remains `deleted_database`;
- API sessions/enrollments remain terminal;
- existing partial-files user message is used;
- no credential resurrection.

### A11 — unchanged temporary block behavior

Precondition: user has valid session and is only temporarily blocked, not database-deleted.

Expected:

- API denied through current access status;
- this addendum does not impose account-reset revocation semantics on ordinary block/unblock.

---

## 13. Tests Required Before Merge

At minimum add/extend tests proving:

- session revoke-all by principal is scoped and terminal;
- pending enrollment revoke-all by principal is scoped and terminal;
- exact `delete_user_database` execution performs those credential effects in the same DB transaction as account reset;
- no-principal legacy user deletion remains green;
- wrong/cancel/voice-final-confirmation paths produce no credential side effects;
- old access/refresh/enrollment credentials stay invalid after later re-approval;
- new enrollment after re-approval works without reviving an old session;
- unrelated user's API credentials remain unchanged;
- DB fault injection proves rollback;
- local filesystem cleanup failure does not undo credential/account revocation;
- existing `/vymazat_databazu` regression remains green.

The Stage A acceptance proof must be updated with this account-reset credential-revocation evidence before `safe_to_commit` is restored.

---

## 14. Migration / Storage Impact

No new table or storage migration is introduced by this addendum beyond the already approved Stage A API-access tables.

It changes runtime behavior over existing Stage A rows only:

- `api_session.revoked_at`;
- pending `api_enrollment.status/revoked_at`.

No business-table rebuild, file move, principal backfill, or path migration is authorized.

Production apply/deploy remains separately gated under `docs/FakturaBot_Data_Migration_Runbook.md`.

---

## 15. Evidence And Design Verdict

Evidence:

- parent proof: `docs/architecture/OFFICEFLOW_PLATFORM_NEUTRAL_ANDROID_FOUNDATION_V1_ARCHITECTURE_DESIGN_PROOF.md`;
- existing handler: `bot/handlers/delete_user_database.py`;
- existing destructive owner: `bot/services/user_data_deletion.py::UserDataDeletionService`;
- Stage A identity/session/enrollment owners in PR #104;
- current access model keeps `deleted_database` as a persistent access-control state;
- user decision on 2026-08-19: account reset must permanently invalidate pre-delete API credentials while retaining minimal principal identity continuity.

Final verdict: `ready_for_handoff`.

The implementation agent may add only the bounded credential-revocation integration described here while fixing PR #104. Any broader redesign of `/vymazat_databazu`, block/unblock, Android flows, public API deletion, principal lifecycle, or Product Truth requires a separate architecture decision.

---

## 16. Implementation Checkpoint — 2026-08-19

Implementation checkpoint: `safe_to_commit`

The bounded addendum is implemented without material design variance:

- `UserDataDeletionService` opens one immediate SQLite transaction, resolves only the existing active Telegram principal mapping, revokes all non-revoked sessions and pending enrollments through their service-owned in-connection helpers, executes the existing scoped reset, marks `deleted_database`, and commits once;
- missing principal remains a valid legacy deletion case and no principal is created by deletion;
- principal/external identity and terminal credential audit rows are retained;
- wrong confirmation, cancel, and voice-final-confirmation paths remain effect-free;
- database failure rolls back credential, business, and access effects together and does not start filesystem cleanup;
- post-commit local cleanup failure leaves credentials and access terminal;
- later re-approval does not revive old access, refresh, or enrollment secrets; a fresh administrator enrollment is required;
- unrelated principals remain untouched and ordinary temporary block/unblock remains non-terminal.

Evidence: `tests/test_delete_user_database_flow.py` passed 12 tests, the combined Stage A/addendum targeted proof passed 52 tests, the shared access/workspace/tenant regression passed 64 tests, and the full repository suite passed 2605 tests plus 7 subtests. Static compile and diff checks pass. Detailed A1–A11 evidence is recorded in `docs/evals/OFFICEFLOW_PLATFORM_NEUTRAL_ANDROID_FOUNDATION_V1_acceptance_proof.md`.

No production migration, deployment, server restart, public API exposure, new Android runtime, new business action, new FSM, or external-service effect was performed.
