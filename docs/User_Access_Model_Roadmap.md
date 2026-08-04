# FakturaBot User Access Model Roadmap

This document separates the current controlled dry-run access model from later onboarding automation and from a possible future commercial deployment model.

Source-of-truth priority remains:
1. `docs/TZ_FakturaBot.md`
2. `PROJECT_LOG.md`
3. current code
4. `CHANGELOG.md`

## Phase 1 - Static allowlist / controlled second user

Status: active current dry-run model and bootstrap compatibility model.

Purpose: safely onboard a controlled second real Telegram user without public signup and without changing the deployment into SaaS.

Runtime model:
- one shared Telegram `BOT_TOKEN`;
- one backend process;
- one SQLite DB;
- bootstrap/static allowed Telegram users configured through `ALLOWED_TELEGRAM_USER_IDS`;
- tenant isolation by `telegram_id` / `supplier_telegram_id`;
- no per-user Telegram bot tokens;
- no public self-service onboarding;
- no automatic signup;
- no per-user SMTP credential collection.

Access behavior:
- in pure Phase 1 static-allowlist runtime, unknown `/start` is blocked neutrally;
- if Phase 2 is implemented and deployed, unknown `/start` may create only a pending access request, not business data;
- unknown users do not create supplier profiles;
- unknown users do not create contacts;
- unknown users do not create invoices;
- unknown users do not create invoice PDFs;
- unknown users do not create accounting documents or other business documents;
- unknown users do not create accounting/document metadata;
- unknown users do not create temporary upload files;
- unknown users do not create tenant storage directories or workspaces;
- unknown users must not trigger LLM, STT, or LMM calls.

Operational rule:
- Phase 1 second-user onboarding is manual: the owner/admin adds the approved Telegram user ID through the real untracked server `.env`;
- real Telegram user IDs must not be committed, logged, or copied into public documentation;
- changing `ALLOWED_TELEGRAM_USER_IDS` requires a controlled bot restart if the runtime reads environment variables only at startup;
- `.env.example` and `.env.server.example` must contain placeholders only, never real Telegram IDs, bot tokens, API keys, or secrets.

## Phase 2 - Admin-approved access request flow

Status: implemented in the current code and confirmed by tests / `PROJECT_LOG.md`. It remains controlled onboarding automation, not public signup.

Purpose: remove the need to edit `.env` and restart the bot for each approved user while keeping owner/admin approval mandatory.

Expected behavior:
- unknown `/start` creates a pending access request only;
- unknown `/start` must not trigger LLM, STT, or LMM calls;
- the bot still does not create supplier, tenant, invoice, contact, document, temp-file, or other business data for unknown users;
- a pending access request is not a tenant;
- a pending access request is not a supplier profile;
- a pending access request is not business onboarding;
- pending access requests are separate from business tenant data;
- pending requests must not trigger LLM, STT, or LMM calls;
- admin can list pending requests;
- admin can approve another user with `/approve <telegram_id>` or safely approve the current configured admin account with argument-free `/approve`;
- admin can reject users;
- admin can block users;
- approved users become authorized without editing `.env` and without restarting the bot;
- approval transactionally reactivates one migrated `inactive` owner membership only when exactly one active workspace and one supplier row prove `supplier.telegram_id` ownership for that actor;
- successful single-membership reactivation creates or restores the actor's active workspace selection without creating a workspace or supplier;
- multiple inactive memberships, multiple actor-owned supplier rows, another owner, missing/inactive workspace, or supplier-actor mismatch fail closed and roll back authorization, access-request, membership, and selection writes;
- approval is not a workspace invitation, ownership-transfer, claim, or identity-merge mechanism;
- approval is required before `/supplier`, invoice, contact, accounting-document, and other business flows.
- Narrow maintenance exception: when the separately gated periodic contact-registry monitor is enabled, it may read official data and create a confirmation proposal for a persisted inactive workspace/membership only while the supplier owner remains an active authorized user. It does not reactivate or expose the profile; the contact write remains proposal-button-confirmed and tenant-scoped.
- after approval, the user-facing next step is `/start`, then `/moj_profil`; `/supplier` remains a legacy/technical onboarding alias;
- after the supplier profile is saved, onboarding points only to the next staged step `/sluzbu` instead of showing contact and invoice commands at the same time;
- the approved-user notification may mention that the user's FakturaBot working database can be deleted through `delete_user_database` (`/vymazat_databazu`, voice/text intent); successful exact typed confirmation deletes scoped business data/files, marks the user as `deleted_database`, and requires a fresh `/start` request plus admin approval before re-entry.

Implemented bootstrap/admin configuration:
- `ADMIN_TELEGRAM_USER_IDS` bootstraps administrators;
- `authorized_users` stores approved/blocked users and admin/owner roles;
- `access_requests` stores pending/approved/rejected request metadata.

Boundary:
- this is controlled onboarding automation;
- this is not public self-service signup;
- automatic signup remains forbidden.

## Phase 3 - Future commercial deployment model

Status: future/commercial model, out of scope for the current dry run and Phase 2 access-request work.

Possible future options:
- separate Telegram bot token per client;
- per-client VPS, container, workspace, or deployment unit;
- separate DB, storage, API keys, or secrets per client;
- SaaS/admin UI for operations;
- billing;
- support tooling;
- stronger secrets management or vault/KMS-style storage.

Boundary:
- Phase 3 must not be treated as the current implementation;
- Phase 3 must not be used to justify adding public signup to Phase 1 or Phase 2;
- per-client Telegram bot tokens are not used in Phase 1 or Phase 2;
- implementing Phase 3 requires a separate product/architecture decision and corresponding updates to `docs/TZ_FakturaBot.md` and `PROJECT_LOG.md`.
