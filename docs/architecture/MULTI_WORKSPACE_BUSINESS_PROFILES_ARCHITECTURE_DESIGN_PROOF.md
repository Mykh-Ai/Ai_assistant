# Multi-Workspace Business Profiles — Architecture Design Proof

Verdict: `ready_for_handoff`

Approved product decisions:

1. One physical SQLite database; all business data is logically isolated by a stable `workspace_id`.
2. One shared Google Drive owner OAuth/service configuration; each workspace uses its own Drive folder tree.
3. `/vymazat_databazu` remains an account-level destructive action that removes every business workspace owned by the user and revokes bot access. Deleting only one workspace is outside MVP.

Approval date: 2026-07-11
Implementation checkpoint: 2026-07-13 production migration and exact-SHA runtime deployment passed the frozen-baseline, verified-backup, post-apply audit, and bounded smoke gates. Public profile runtime is ready; same-user two-profile Telegram acceptance remains pending.

## 1. Task Identity And Product Need

Task id / name: `MULTI_WORKSPACE_BUSINESS_PROFILES_V1`

Business need:

One authorized Telegram user must operate two fully isolated businesses through the same Telegram bot:

- Oleksiienko SZČO;
- ZEUS s. r. o.

The user must be able to select the active business profile and then use the existing invoice, contact, service, receipt/incoming-invoice, analytics, work-time, reminder, archive, and profile flows in that workspace only.

User-visible outcome:

- the user sees the active business profile;
- the user can open a profile selector and switch profiles;
- every business read/write uses the active workspace;
- data from one workspace never appears in the other;
- Google Drive authorization remains shared, while archive destinations remain workspace-separated.

Current Product Truth status (2026-07-13 production state): `partial / production migrated and deployed / same-user two-profile acceptance pending`.

Target Product Truth status after migration and deployment acceptance proof remains `partial` for multi-business profiles, because profile deletion, cross-profile analytics, one-off per-request profile overrides, and multi-member workspace administration remain out of scope.

Risk level: high / migration-sensitive / tenant-isolation-sensitive.

## 2. Architecture Classification

Primary class: extension of the existing tenant/access architecture plus one new top-level business action.

New top-level action:

- `switch_business_profile`

Existing action extended:

- `show_supplier_profile` / `/moj_profil` becomes “show active business profile”;
- existing supplier onboarding is extended with an additional-workspace creation mode;
- `/start` and `/menu` become active-workspace-aware.

Subflow added:

- profile selector / profile creation under `/profily`;
- voice switch confirmation;
- additional business-profile onboarding using existing validated supplier fields.

Not a new tenant system from scratch:

The repository already isolates current users by `telegram_id` / `supplier_telegram_id`. The change separates Telegram identity from business workspace identity.

Target identity model:

```text
telegram_id = authenticated Telegram person / notification destination
workspace_id = business tenant / data-isolation key
```

Evidence:

- `docs/User_Access_Model_Roadmap.md` — current tenant isolation is by `telegram_id` / `supplier_telegram_id`.
- `bot/services/db.py` — `supplier.telegram_id` is unique; contacts, invoices, invoice numbering, semantic aliases, follow-up state, and work-time use Telegram-derived keys.
- `bot/services/accounting_document_storage.py` — current workspace key is derived from supplier Telegram ID.
- `bot/handlers/start.py` — current setup/status lookup is by Telegram ID.
- `bot/services/user_data_deletion.py` — current destructive deletion is scoped entirely by Telegram ID.

## 3. Canonical Action Contract

Canonical token: `switch_business_profile`

Status before implementation: `planned`.

Target status: `implemented` only after all business domains use canonical workspace context and the profile switch feature passes Conversation Acceptance Proof.

Plain-language meaning:

Switch the authorized user’s persistent active business workspace to one of the business profiles that the user is allowed to access.

User-facing wording examples:

- “Перемкни на ZEUS.”
- “Працюємо як ZEUS.”
- “Повернись на živnosť.”
- “Prepnúť firemný profil na ZEUS.”
- “Vyber profil Oleksiienko SZČO.”

Runtime owner:

A shared Python workspace/profile context service, not a handler-local dictionary and not the LLM.

Recommended public command:

- `/profily`

Allowed contexts:

- idle authorized user only;
- no switch execution during an active business FSM.

Entry modes:

- command;
- semantic text;
- semantic voice transcript;
- reply-keyboard profile selection.

Structured slot:

- `business_profile_ref`

The bounded LLM may select only from Python-provided accessible workspace candidates. Python validates membership and executes the switch.

## 4. Semantic Boundary Matrix

| Exact user meaning/input | Expected action/status | Why | Must not become |
|---|---|---|---|
| “Перемкни на ZEUS” | `switch_business_profile`, slot ZEUS | explicit switch intent | show/edit supplier or customer lookup |
| “Покажи мої профілі” | open `/profily` selector/list | profile-management/navigation request | immediate switch |
| “Покажи профіль ZEUS” | show/select clarification; no switch without switch intent | read/show wording | implicit mutation |
| “Зміни IBAN ZEUS” | edit active supplier or clarification | profile-field edit | workspace switch |
| “Створи фактуру для ZEUS” | resolve customer/business ambiguity | ZEUS may be customer or supplier profile | silent profile switch |
| “Покажи фактури ZEUS” while SZČO active | clarification / explain switch-first model | cross-workspace read not implicit in MVP | cross-workspace leak |
| “Покажи фактури обох фірм” | unsupported cross-workspace analytics guidance | combined analytics out of scope | aggregate without explicit architecture |
| unknown profile name | `unknown` / selector remains open | no accessible candidate | create workspace or choose closest write default |
| profile without membership | access denied, no side effect | Python membership gate | cross-tenant access |

Ambiguity rules:

```text
meaning:
  explicit request to change the persistent active business context
positive_examples:
  switch, prepnúť, zmeniť aktívny profil, work as ZEUS
not_this:
  show profile, edit profile field, customer named ZEUS, invoice addressed to ZEUS,
  ask about capability, combined analytics
```

## 5. Structured Slot Contract

| Slot | Type / allowed values | Source | Required | Default owner | Invalid behavior | Voice / precision boundary |
|---|---|---|---|---|---|---|
| `business_profile_ref` | one accessible workspace id/reference from Python-provided candidate list | bounded LLM, exact command text, reply-keyboard text | no | none; missing opens selector | remain in selector / clarify; no switch | voice may identify candidate but requires confirmation |

Candidate object supplied by Python should include only opaque stable id plus user-facing label, for example:

```text
workspace_id: ws_...
label: ZEUS s. r. o.
aliases: [ZEUS, sro]
```

Rules:

- Python owns candidate list, membership, exact workspace id, validation, and write.
- LLM may only return one candidate id or `unknown`.
- No global multilingual Python phrase dictionary for business names.
- Exact reply-keyboard selection or exact unique text match may switch immediately after membership validation.
- Voice unique match enters confirmation before switching.
- Missing slot opens selector.
- Ambiguous or inaccessible candidate never changes active selection.

## 6. Public Route And Convergence Map

| Entry mode | Public entry | Guards | Resolver/helper | Shared Python owner | Result |
|---|---|---|---|---|---|
| command | `/profily` | authorization; active-FSM block; memberships | deterministic selector | workspace context service | list/select/create profile |
| text | idle semantic router | authorization; no active FSM | top-level resolver + bounded candidates | same switch helper | immediate exact switch or selector |
| voice | voice handler after STT | authorization before STT; active-FSM guard after STT | same top-level resolver | same helper, then confirmation | confirmed switch or no change |
| reply keyboard | profile-selection FSM | authorization; expected state; accessible candidates | exact visible label -> workspace id | same helper | switch and exit |
| confirmation buttons/text/voice | switch-confirm FSM | authorization; expected state; pending target; activity freshness | shared DecisionResolver `yes_no` | same helper | switch or cancel |

Global rule:

No business handler may derive tenant context directly from `message.from_user.id` after migration. Telegram ID is the actor/authorization/notification identity; workspace context is resolved separately.

## 7. Workspace Domain Model

Canonical tables/entities:

```text
workspace
- workspace_id TEXT PRIMARY KEY
- display_name TEXT NOT NULL
- storage_key TEXT NOT NULL UNIQUE
- drive_folder_name TEXT NOT NULL
- status TEXT NOT NULL
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL

workspace_membership
- workspace_id TEXT NOT NULL
- telegram_id INTEGER NOT NULL
- role TEXT NOT NULL
- status TEXT NOT NULL
- created_at TEXT NOT NULL
- updated_at TEXT NOT NULL
- UNIQUE(workspace_id, telegram_id)

active_workspace_selection
- telegram_id INTEGER PRIMARY KEY
- workspace_id TEXT NOT NULL
- updated_at TEXT NOT NULL
```

MVP membership behavior:

- current authorized user may own multiple workspaces;
- only an owner may create an additional business profile;
- sharing one workspace with additional Telegram users is not exposed in MVP;
- normal access approval may reactivate exactly one migration-created inactive owner membership when supplier actor ownership is unique and consistent;
- that reactivation and active-selection restore are part of the approval transaction and create no workspace or supplier;
- ambiguous memberships or ownership fail closed; approval does not attach a different actor or transfer workspace ownership;
- authorization remains user-level through current access control;
- workspace membership is the second, mandatory business-data gate.

Shared runtime object:

```text
WorkspaceContext
- actor_telegram_id
- workspace_id
- workspace_display_name
- storage_key
- drive_folder_name
- membership_role
- supplier_id
```

Recommended owner:

```text
WorkspaceContextService.resolve_for_user(telegram_id)
WorkspaceContextService.require_membership(telegram_id, workspace_id)
WorkspaceContextService.set_active_workspace(telegram_id, workspace_id)
```

Resolution rules:

1. verify current authorization;
2. list active memberships;
3. one membership -> auto-select if needed;
4. multiple memberships -> use persisted active selection;
5. missing/invalid selection -> require selector before business action;
6. validate membership on every resolution and every switch;
7. never trust workspace id from LLM, callback, FSM data, or request without membership validation.

## 8. Canonical Data Scope

After migration, `workspace_id` is the canonical business isolation key for every applicable domain:

- supplier profile;
- contacts and contracts;
- service aliases;
- confirmed semantic aliases;
- outgoing invoices and invoice items through invoice ownership;
- invoice numbering;
- invoice follow-up/payment/reminder/archive state;
- receipts and incoming invoices;
- accounting categories and metadata;
- invoice analytics;
- accounting-document analytics;
- work-time days/settings/events/reports;
- customization requests that belong to a business workspace;
- archive jobs and archive state;
- background reminders;
- workspace storage paths and generated artifacts.

Tables that already contain `workspace_id` must be audited to ensure the value becomes the stable business workspace id, not a derived `telegram-<id>` substitute.

Telegram-derived fields may remain temporarily only as actor/notification/audit compatibility fields. They must not remain the canonical query or uniqueness key for business data.

Important uniqueness changes:

```text
supplier: UNIQUE(workspace_id)
invoice: UNIQUE(workspace_id, invoice_number)
invoice_number_settings: UNIQUE(workspace_id, issue_year)
work_time_days: UNIQUE(workspace_id, work_date)
active_workspace_selection: one per telegram user
```

Supplier service target:

- business paths use `get_by_workspace_id()`;
- `get_by_telegram_id()` is retired from normal business routing and may remain only as a temporary migration compatibility helper.

## 9. Storage And Path Contract

`workspace.storage_key` is immutable and is the canonical key for new workspace-scoped filesystem paths.

Target new paths:

```text
storage/invoices/<storage_key>/<invoice_number>.pdf
storage/workspaces/<storage_key>/years/<year>/...
storage/uploads/accounting_intake/<storage_key>/...
storage/uploads/attachment_intake/<storage_key>/...
```

Migration safety:

- do not move existing invoice PDFs merely to normalize paths;
- preserve existing `invoice.pdf_path` values when the referenced file is valid;
- use the current canonical accounting workspace key as the migrated existing workspace `storage_key` when safe;
- report legacy `mykhailo-szco`, `telegram-<id>`, Windows, flat, missing, and orphan paths in dry-run;
- no cross-workspace fallback reads as a substitute for migration;
- no path guessed from active workspace when a persisted canonical path exists.

New ZEUS data uses its own newly generated immutable storage key.

## 10. Google Drive Contract

Approved model:

- reuse the existing single owner OAuth/service-account archive provider;
- do not create separate OAuth credentials or API configuration for ZEUS;
- preserve the owner connection configured through the current owner workspace/configuration;
- separate archive destinations through workspace-specific target folder paths.

Current evidence:

- `GoogleDriveOwnerOAuthArchiveProvider` is explicitly a single owner OAuth connection;
- archive jobs already carry `workspace_id` and `target_folder_path`;
- the provider resolves/creates folder paths below one configured root.

Target Drive layout:

```text
FakturaBot/
  Oleksiienko SZČO/
    ...
  ZEUS s. r. o./
    ...
```

`drive_folder_name` is stored per workspace and must not be inferred from mutable user text at upload time.

Background upload rule:

```text
archive_job.workspace_id
-> load workspace
-> validate job/storage ownership
-> build workspace-specific target_folder_path
-> upload through shared owner provider
```

The active workspace selection is irrelevant to background job execution.

No deletion of remote Drive files is added by this task. Account-level local-data deletion must preserve the shared owner OAuth connection unless a separate explicit admin action removes it.

## 11. FSM Graph And State Ownership

### Idle switch flow

```text
IDLE
  -> /profily or switch_business_profile
      -> no target
          -> waiting_business_profile_selection
              -> exact accessible selection -> switch -> IDLE
              -> add profile -> additional profile onboarding
              -> unknown -> remain
              -> cancel -> IDLE unchanged
      -> exact accessible text/command target
          -> switch -> IDLE
      -> voice unique target
          -> waiting_business_profile_switch_confirm
              -> yes -> switch -> IDLE
              -> no -> IDLE unchanged
              -> unknown -> remain
              -> stale -> fail closed; no switch
```

### Active business FSM

A fresh active business FSM owns the conversation. Profile switching is not executed.

For explicit profile-switch intent while active:

- respond that the current process belongs to the bound profile;
- preserve the current FSM state/data;
- instruct the user to finish or cancel first;
- do not clear state;
- do not change active workspace;
- do not replay the switch into idle routing.

This is a safe blocked interrupt, not fresh-FSM safe switching.

### Flow workspace binding

Every business FSM entry must bind shared metadata:

```text
flow_workspace_id
flow_workspace_bound_at
shared activity timestamp
```

Before any save/delete/pay/send/upload/confirmation callback:

1. validate authorization;
2. validate current membership in `flow_workspace_id`;
3. validate expected state and freshness;
4. validate current active workspace still equals the bound workspace, or fail closed;
5. execute through the workspace-scoped Python owner.

Legacy active states without workspace binding after deployment must fail safely with bounded recovery; they must not guess the workspace from Telegram ID.

## 12. Profile Creation Subflow

`/profily` includes `Pridať firemný profil` for workspace owners.

Reuse existing supplier onboarding field validation and UX, but add an explicit mode:

```text
create_first_workspace_profile
create_additional_workspace_profile
edit_active_workspace_profile
```

Additional workspace creation must not call the old `create_or_replace()` behavior keyed by Telegram ID.

No persistent workspace row is created until the final validated confirmation.

Final save is one transaction:

```text
create workspace
-> create supplier profile for workspace
-> create owner membership
-> initialize required workspace settings/numbering defaults
-> optionally set active workspace
-> commit
```

Any failure rolls back the entire transaction.

After save:

```text
Profil ZEUS s. r. o. bol uložený.
Nastaviť ho ako aktívny profil?
[Áno] [Nie]
```

Use shared DecisionResolver. `Nie` preserves the previous active workspace.

## 13. User-Facing Response And Exit Contract

`/start` and `/menu` show the active business profile for users with a valid workspace:

```text
Aktívny firemný profil: ZEUS s. r. o.
```

`/profily` shows accessible profiles, marks the active one, and provides:

- select another profile;
- add business profile for owner;
- cancel/back.

Terminal switch response:

```text
Aktívny firemný profil bol zmenený na ZEUS s. r. o.
```

After switching:

- FSM is idle;
- profile selector keyboard is removed;
- next actions run in the new workspace;
- no old workspace business state survives.

For business previews and mutating confirmations, the active/bound business profile must be visible enough to prevent issuing data under the wrong company.

## 14. Authorization, Tenant, Callback, And Side-Effect Boundaries

Authorization remains first and precedes STT/LLM/LMM/temp/storage/business work.

Workspace membership is mandatory before any business read/write.

Side effects:

| Side effect | Python owner | Required validation | Fail-safe |
|---|---|---|---|
| persist active workspace | workspace context service | authorization + active membership + idle state | no change |
| create workspace/profile | workspace/profile service transaction | owner role + validated supplier data + confirmation | full rollback |
| business data read/write | domain service with WorkspaceContext | membership + workspace id | no cross-workspace fallback |
| file generation/storage | domain storage owner | workspace storage key + ownership | no guessed path |
| Drive upload | archive worker/provider | job workspace + storage ownership + shared provider | retry/fail without cross-workspace upload |
| callback mutation | active FSM/domain helper | auth + membership + state + workspace binding + freshness | fail closed |
| account-level deletion | deletion service | exact typed confirmation + explicit all-workspace preview | no partial silent delete |

Profile-selection reply keyboard is preferred over a stateless mutation callback. Confirmation callbacks/buttons must use existing shared DecisionResolver/callback safety behavior.

## 15. Background Jobs And Notifications

Background jobs are workspace-bound and do not consult the user’s current active selection.

Every job/reminder must retain:

- `workspace_id`;
- business object id;
- intended notification `telegram_id` or a deterministic owner membership lookup;
- timestamps/idempotency state.

User notification must identify the business profile when ambiguity is possible, for example:

```text
ZEUS s. r. o. — faktúra 20260012 je po splatnosti.
```

Switching the interactive active profile must not retarget or suppress jobs from another workspace.

## 16. Existing Data Migration Contract

The migration is additive-first and migration-sensitive.

### Read-only audit

Before writing migration code or applying anything to the server, report:

- current deployed commit and schema;
- supplier rows;
- all business tables and rows grouped by current Telegram-derived tenant key;
- current indexes and uniqueness constraints;
- invoice PDF path classifications and file existence;
- accounting workspace keys, metadata/original counts, parse failures, and orphans;
- archive jobs/states by workspace key;
- Google Drive owner connection mode and current root;
- work-time rows/settings/events;
- rows with inconsistent or missing tenant ownership;
- no real Telegram IDs or secrets in public artifacts.

### Migration plan

For every current supplier/authorized business owner:

1. create one workspace representing the existing business;
2. create owner membership;
3. set active selection;
4. backfill `workspace_id` to all business rows;
5. preserve current valid storage paths;
6. convert uniqueness/query ownership to workspace id;
7. validate counts and foreign/business ownership;
8. only then enable workspace-only runtime reads/writes.

The existing owner workspace becomes Oleksiienko SZČO. ZEUS is created later through the additional-profile flow and begins empty.

### Compatibility rollout

A temporary dual-column period is allowed only if:

- every write persists canonical `workspace_id`;
- reads are workspace-first;
- Telegram-derived fallback is bounded to migration compatibility and cannot cross workspaces;
- the public switch action remains hidden until every required domain is workspace-safe;
- compatibility code has a removal plan and tests.

### Apply gate

Implementation may create migration tooling and local fixture tests. It must not apply server DB/storage migration, restart/deploy, or enable the public switch without:

- backup;
- dry-run report;
- explicit user approval;
- rollback plan;
- post-migration audit and server smoke.

Local tooling satisfies the implementation part of this gate with fingerprint-pinned dry-run/apply, exclusive-lock refusal, verified DB and content-hashed storage backup, separately audited target construction, atomic replacement, manifest-bound rollback, and emergency restore on post-swap mismatch. The production operational gate was completed on 2026-07-13 for exact SHA 7408399239eba8cb221ba7b6e7267ccf1d60a867; this does not waive the same gate for future migrations or make the still-pending same-user two-profile conversation acceptance complete.

## 17. Delete-Database Contract

`/vymazat_databazu` remains account-level in MVP.

Preview must explicitly state that all owned business profiles will be removed, listing their names.

On exact typed confirmation:

- delete workspace-scoped local business rows/files for every workspace owned by the account;
- revoke/remove workspace memberships and active selection;
- preserve the shared Google owner OAuth/service configuration;
- do not delete already uploaded remote Drive files unless a separate explicitly approved feature exists;
- mark the user’s bot access as deleted/revoked under current access-control semantics.

Deleting only ZEUS or only SZČO is outside MVP.

## 18. Product Truth And InfoHelp Contract

Capability id: `multi_business_profiles`

Target status: `partial`.

Truthful claim after full accepted implementation:

> An authorized user can maintain multiple isolated business profiles and switch the active profile. Invoices, contacts, documents, numbering, analytics, work-time, reminders, and local storage are isolated by the active workspace. One owner Google Drive connection can archive each workspace into a separate folder tree.

Limitations:

- one active workspace at a time;
- no switch during an active business process;
- no combined analytics across profiles;
- no one-off “execute as other profile” without switching;
- no individual profile deletion;
- no data copying/merging between profiles;
- no public workspace sharing/member administration;
- Google Drive remote deletion is not part of the feature.

Forbidden claims:

- separate physical database per profile;
- separate Google credentials required per profile;
- automatic migration without audit/backup/approval;
- combined financial/accounting view across both companies;
- switching active profile changes the owner of existing records;
- profile switch is safe before all domains are workspace-scoped.

## 19. Negative-Space And Regression Contract

The implementation must not regress:

- current single-workspace onboarding and invoice creation;
- existing supplier profile show/edit semantics, now scoped to active workspace;
- access-request/admin authorization;
- active-FSM navigation, stale-state recovery, and callback guards;
- invoice/receipt/incoming-document separation;
- existing analytics safety and read-only behavior;
- current Google Drive owner OAuth/service-account provider;
- persisted invoice `pdf_path` resolution;
- current data-deletion typed confirmation;
- tenant isolation between different Telegram users.

The feature must not expose a profile switch before all mandatory domains are workspace-safe.

## 20. Acceptance Scenario Contract

The post-implementation Conversation Acceptance Proof must include at least:

1. Existing single-workspace fixture migrates with row/file counts unchanged.
2. Existing valid invoice PDFs remain resolvable without moving them.
3. Existing accounting documents remain visible only in the migrated workspace.
4. ZEUS profile is created atomically and begins empty.
5. Active workspace survives process restart.
6. `/start` and `/menu` show the correct active profile.
7. `/profily` lists only accessible profiles and marks the active one.
8. Exact reply-keyboard selection switches immediately.
9. Exact semantic text switch with a unique accessible match works.
10. Voice switch requires confirmation; no confirmation means no switch.
11. Missing/ambiguous/unknown target remains recoverable with no switch.
12. Switch attempt during active invoice/contact/accounting/work-time FSM is blocked without clearing state.
13. Stale/wrong-state switch confirmation produces no side effect.
14. Old-workspace stale mutation callback after a switch fails closed.
15. Supplier profile show/edit uses the active workspace.
16. Same invoice number may exist independently in both workspaces.
17. Contacts/contracts/service aliases do not leak between workspaces.
18. Receipts/incoming invoices/categories do not leak.
19. Invoice analytics sees only active workspace data.
20. Accounting-document analytics sees only active workspace data.
21. Work-time rows/settings/reports are fully separated.
22. Background invoice reminder identifies and uses its stored workspace regardless of interactive active selection.
23. One owner Google Drive connection uploads into different workspace folder trees.
24. Unauthorized user and non-member workspace id produce no AI/storage/business side effect.
25. Cross-tenant ids in LLM/FSM/callback data are rejected by Python.
26. `/vymazat_databazu` previews and deletes all owned profiles locally while preserving shared Google credentials/remote files.
27. Current single-workspace user journey remains correct.
28. Public profile switching cannot be enabled in a partially migrated runtime.

Each scenario must record exact input, state sequence, action/slots, workspace ids, side effect/no-side-effect, final state, response/keyboard, and real/mocked boundaries.

## 21. Out Of Scope And Known Gaps

- separate physical SQLite database per profile;
- separate Telegram bot/token per profile;
- separate Google OAuth/API credentials per profile;
- profile deletion/archive/restore;
- combined cross-profile analytics or reports;
- copying contacts/services/documents between workspaces;
- sharing one workspace with another user through UI;
- role administration UI;
- one-message temporary profile override;
- automatic server migration/deployment;
- moving all legacy invoice PDFs solely for path normalization;
- remote Google Drive file deletion.

## 22. Evidence Index

Mandatory implementation audit targets:

- `AGENTS.md`
- `docs/llm/Top_Level_Subflow_Architecture_Design_Proof_Contract.md`
- `docs/llm/New_Action_Design_Checklist.md`
- `docs/Code_Agent_Handoff_Contract.md`
- `docs/Evaluation_and_Smoke_Test_Standards.md`
- `docs/User_Access_Model_Roadmap.md`
- `docs/FakturaBot_Data_Migration_Runbook.md`
- `docs/TZ_FakturaBot.md`
- `docs/Product_Truth_Layer.md`
- `docs/Info_Help_Guidance_Layer.md`
- `docs/llm/FakturaBot_LLM_Orchestrator_Contract.md`
- `docs/Canonical_Decision_Resolver_Contract.md`
- `docs/llm/Canonical_Action_Registry.md`
- `docs/llm/In_Action_Response_Registry.md`
- `bot/services/db.py`
- `bot/services/access_control.py` and authorization middleware
- `bot/services/supplier_service.py`
- `bot/services/contact_service.py`
- `bot/services/invoice_service.py`
- invoice analytics dataset/planner route
- accounting document storage/registry/categories/analytics
- `bot/services/work_time.py`
- `bot/services/active_fsm_guard.py`
- `bot/services/decision_resolver.py`
- `bot/services/archive_job_service.py`
- `bot/services/archive_worker.py`
- `bot/services/google_drive_owner_oauth_client.py`
- `bot/services/google_drive_archive_scheduler.py`
- `bot/services/user_data_deletion.py`
- `bot/handlers/start.py`
- `bot/handlers/supplier.py`
- `bot/handlers/voice.py`
- `bot/handlers/decision_callbacks.py`
- relevant tests and recent `PROJECT_LOG.md` entries.

## 23. Final Handoff Verdict

Verdict: `ready_for_handoff`

Reason:

The business outcome, identity/workspace split, data-scope boundaries, active selection, public action, FSM behavior, Google Drive ownership, migration gates, deletion semantics, Product Truth limitations, negative space, and acceptance scenarios are explicitly approved. The implementation agent must verify exact current symbols/schema and stop on a material contradiction instead of changing this architecture silently.
