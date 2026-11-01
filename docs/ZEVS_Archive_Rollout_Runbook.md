# ZEVS archive routing — reviewable rollout procedure

Status: local implementation proposal; **not deployed**. This document grants
no production access or migration approval. Approved architecture:
`docs/architecture/ZEVS_DOCUMENT_ARCHIVE_ROUTING_AND_FAILURE_NOTICE_V1_ARCHITECTURE_DESIGN_PROOF.md`.

## Configuration shape (synthetic values only)

Keep a read-only, administrator-owned JSON file, mode 0600, outside tracked
source. Mount it read-only and point `GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE` to its
absolute regular-file path. The file is optional: absent means legacy routes;
an explicitly configured malformed file fails closed for receipts/statements.
No annual code/config edit is needed.

```json
{
  "schema_version": 1,
  "routes": [
    {
      "workspace_id": "synthetic-workspace",
      "document_type": "receipt",
      "route_revision": "v1",
      "company_root_folder_id": "synthetic-company-root",
      "annual_folder_template": "Zevs_{YYYY}",
      "document_folder_name": "blocky",
      "relative_suffix_mode": "year_month",
      "payload_mode": "original"
    },
    {
      "workspace_id": "synthetic-workspace",
      "document_type": "bank_statement_original",
      "route_revision": "v1",
      "company_root_folder_id": "synthetic-company-root",
      "annual_folder_template": "Zevs_{YYYY}",
      "document_folder_name": "Vypisy",
      "relative_suffix_mode": "none",
      "payload_mode": "pdf_without_password"
    }
  ]
}
```

Use the actual persisted workspace and a privately verified company root, not
these synthetic identifiers. Existing per-year folder IDs are optional evidence,
not Python constants. Resolution checks exact direct-child names and lineage,
reuses existing folders, and reserves IDs before creating missing folders.

`GOOGLE_DRIVE_FAILURE_NOTICE_CUTOFF` enables durable notices. Set it to the
approved activation time as an explicit timezone-aware ISO timestamp. Its first
use persists the boundary in the notice table. A later differing value is a
bounded configuration failure; do not clear the record to replay old failures.
Unset means delivery is disabled. Upload enabled and notice enabled are separate:
delivery continues for existing notices even while `GOOGLE_DRIVE_ENABLED=0`.

Keep the existing `GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE` secret. Do not
copy its value to shell arguments, this file, Telegram, metadata, SQLite, logs or
AI. The configured storage owner passes `Config.storage_dir` explicitly into
routed enqueue and worker; a missing/untrusted root fails closed.

Routed delivery requires owner OAuth. Service-account/legacy upload providers
cannot report success for a routed job. No scopes/account/token model change is
part of this rollout.

## Read-only audit and dry run before approval

1. Verify exact workspace, active owner/member, supplier and Gmail binding/query
   really correspond to ZEVS. Resolve identities privately; do not infer from
   display names or the actor's current selected profile.
2. Verify the current server commit/image, storage root, secret-file existence
   and readability without reading its value into diagnostics. Follow the owner's
   private server runbook, not a public example. This proposal has not run SSH.
3. With the existing runtime Drive credentials, read the approved company root,
   existing annual/type/month children, parent lineage, MIME/trashed state and
   create capability. The connected ChatGPT Drive account is not this check.
4. Run the read-only inventory against an approved database path:

   ```bash
   python -m bot.cli.archive_delivery_audit --db /path/to/approved/database.sqlite3
   ```

   It uses SQLite `mode=ro` and `query_only`, never bootstraps schema, reports
   hashed job references, and identifies outstanding routed legacy jobs. Review
   their drain/hold/requeue disposition separately. Do not activate over them.
5. Privately map eligible documents to their validated issue date/statement
   period, proposed `Zevs_YYYY/Vypisy` or `Zevs_YYYY/blocky/YYYY-MM`, and payload
   mode. New-year cases must include a late December document received in January
   and a retry spanning New Year. A missing date/period is not assigned `now`.
6. Freeze a DB/storage/config fingerprint and present audit counts, blockers,
   private mapping and this procedure to the owner. No write/apply in this phase.

## Separately approved apply

After explicit operational approval, use a short writer freeze. Take and verify
an online SQLite backup (`quick_check=ok`), original/metadata storage snapshot,
closed-permission config/environment backup and pinned previous image/commit.
Compare the frozen preflight fingerprint before applying anything.

The candidate archive schema adds only `archive_delivery_context` and, when
notices are enabled, `archive_failure_notices`; the activation record lives in
the latter table. Existing jobs, original paths, metadata, OAuth grants and
folder-cache rows are not rewritten. New folder cache entries use a separate
namespace. Candidate bootstrap/notice setup initializes the additive tables;
therefore initial startup with the new image belongs inside the approved apply.

Verify unchanged legacy rows/paths and schema idempotency, set the privately
reviewed routes and activation cutoff, then resume the candidate workers. No
historical backfill/move/reupload/delete is implicit. Source/DB identity belongs
to the original job and cannot be retargeted by later configuration/profile/year.

## Controlled verification

Use separately approved real statement/receipt input, then independently read
Drive IDs, parents, size/checksum and delivery reference. Open the archived PDF
without a password and privately compare all pages with the source. Confirm the
encrypted original hash remains unchanged. Confirm receipt retention only after
verified success and metadata retention throughout.

Test temporary/permanent failure with synthetic provider fixtures rather than
breaking real credentials. Confirm one actual authorized Telegram notice when
approved, correct recipient, no keyboard/FSM mutation, restart recovery and
`sent_at` only after a confirmed send. A crash after send but before the DB ack
can repeat the same short reference; exactly-once delivery is not claimed.

If create outcome cannot be verified, the notice says saving could not be
confirmed, not that the file definitely does not exist. A missing local source
must be stated honestly. A blocked/unauthorized recipient is never replaced by
a different chat.

## Rollback

Pause archive workers before changing image/config. Do not allow an older worker
to consume new-context jobs through its legacy uploader. Disable notice delivery
by removing its environment enablement while preserving its persisted cutoff;
restoring the same cutoff later is safe. Preserve new tables/context/reservations.

Keep sources/metadata and already-created remote files. Never delete/move remote
files automatically, drop the additive tables, clear terminal attempts, or restore
an old full database over newer business activity. Re-enable only a compatible
worker or keep new-context jobs paused pending a forward fix. Report unresolved
remote IDs for read-only reconciliation.

## Server-agent handoff — 2026-11-01 (Europe/Berlin)

The product owner authorized preparing/publishing the implementation on GitHub.
Publication is **not** merge, server apply, activation or production-write
approval. The implementation's local acceptance tests use synthetic transports;
real-provider/server acceptance remains unproven. The publishing agent must
supply the exact reviewed PR URL and implementation commit SHA in its final
handoff. This document intentionally contains no installation IDs or secrets.

### Required private inputs and pinned source

Before server access read the actual private
`docs/local-only/FakturaBot_Server_Agent_Context.md`. Do not use its public
example as live authority. Obtain these values through the approved private
context, not a public PR/comment/log:

| Input | Required verification |
|---|---|
| `REVIEWED_IMPLEMENTATION_SHA`, reviewed PR, permitted integration step | Exact reviewed implementation commit, not arbitrary latest main; record resulting integrated/deployed SHA separately. Merge/integration requires its own authorization. No `git reset --hard`, force push or unrelated edits. |
| Actual `/bot` project checkout, compose file, environment file, service name | Match the private runbook and live checkout/image. Capture dirty status before changes. Limit operations to the bot project/service; do not recreate cloudflared or other projects. |
| Actual host storage path and container bind | Verify the live mount; do not infer host storage from a container path or assumed compose cwd. Read mount metadata only; do not print environment/secret-bearing `docker inspect` or `compose config` output. |
| Persisted ZEVS workspace ID, storage key, actor/active owner membership | Resolve from scoped persisted ownership and Gmail binding; display names or currently selected actor profile are insufficient. No creation/repair is implicit. |
| Verified company root Drive ID and original user-provided folder links | Privately inspect the linked 2026 anchors and their ancestors with the **runtime owner's** credentials, identify one approved company root and exact direct-child lineage. Do not use a Vypisy/blocky child ID as the company root. Do not copy IDs into this repo. |
| Existing owner OAuth binding, encrypted refresh token, crypto secret, root/account configuration | Keep existing token model/scopes; route root and legacy root have different purposes. Verify actual owner account and create capability. No re-consent/credential replacement is implicit. |
| Existing Gmail target workspace, expected mailbox/query, opening-password file | Verify same scoped ZEVS owner/source, read-only Gmail grant and runtime file readability. Opening password stays file-backed; never emit its value to Telegram, logs, shell args, git or AI. |
| Private routes path, approved cutoff, retention choices | Freeze reviewed JSON revision/root/workspace mapping; cutoff is one timezone-aware activation instant. Preserve existing retention settings unless explicitly changed; bank source always retained. |

Concrete repository deployment facts, which must still be checked against the
live compose invocation:

- `docker-compose.prod.yml` runs service `bot`, container `fakturabot`, with
  `DB_PATH=/bot/data/storage/fakturabot.db`, `STORAGE_DIR=/bot/data/storage`.
- Its storage mount is `./data/storage:/bot/data/storage`; the host path depends
  on the actual compose project directory. It is not automatically `/bot/data`.
- The existing `/bot/secrets:/bot/secrets:ro` mount can hold the private JSON
  route file and existing password file. No compose/token-model change is needed.
- `bot.main` calls `init_db` before starting schedulers. Candidate startup can
  therefore initialize schema even if Drive upload is disabled: it belongs
  **after backup and approved apply**, not in read-only preflight.

The private environment delta should contain only reviewed additions, for
example (placeholders are not runnable installation values):

```dotenv
GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE=/bot/secrets/zevs-document-routes.json
GOOGLE_DRIVE_FAILURE_NOTICE_CUTOFF=<APPROVED_TIMEZONE_AWARE_ACTIVATION_ISO8601>
```

Use the JSON shape above with `<PERSISTED_ZEVS_WORKSPACE_ID>` and
`<VERIFIED_COMPANY_ROOT_ID>` substituted privately. Install it as a regular,
non-symlink administrator-owned file, mode0600, readable by the bot UID and
mounted read-only. Validate both receipt and statement entries without printing
the document. Keep `GOOGLE_DRIVE_MODE=owner_oauth`, the existing grant and
`GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE`. Confirm upload/worker enablement
and notice cutoff deliberately; unset cutoff disables notice delivery.

### Execution gates and evidence to return

1. **Source/integration gate.** Record current server SHA/image/dirty status and
   compare the provided reviewed SHA. Prepare a pinned candidate image without
   running `bot.main` or mounting writable live storage. If integration is not
   authorized, stop at a reviewable deployment plan; do not merge implicitly.
2. **Read-only preflight gate.** With route config mounted read-only, run the
   candidate `python -m bot.cli.archive_delivery_audit --db <ACTUAL_DB_PATH>`
   against a consistent read-only database view. Record integrity/counts and
   hashed blockers; the command does not initialize schema. Separately verify
   root/annual/type/month lineage and permission using runtime credentials.
   Do not import bot.main, start workers, call schema-bootstrapping helpers or
   silently refresh/repair OAuth state in this phase. If valid read-only access
   is unavailable, report the credential/reauth blocker; any persisted refresh
   or repair belongs in a separately authorized operational step.
   Active pending/retry_wait/uploading legacy jobs for the configured override
   block activation until their explicit drain/hold/requeue disposition is
   reviewed. Do not synthesize contexts or rewrite legacy targets.
3. **Offline rehearsal gate.** Make an approved consistent SQLite backup into a
   separate rehearsal directory (SQLite backup API, not an unsafe live-file
   copy). On that copy only, run the exact pinned candidate's normal `init_db`
   and notice reconciliation with the proposed cutoff; no network or scheduler.
   This initializes additive context/outbox/activation schema. Repeat twice,
   compare old table rows, paths, statuses, counts, ownership and FK/integrity
   against the frozen preflight snapshot. Check private route mapping/dry-run
   for December2026 received January2027, first2027 statement/receipt and2028.
   Missing dates/periods must remain review cases. Dry-run mapping must not
   enqueue jobs, transform live files or mark import/archive/OAuth states. PDF
   opening secrets stay memory-only, never shell arguments or diagnostic output.
   Rehearsal is a storage write
   to a separate copy and needs the applicable operational authorization.
4. **Backup/apply gate.** Present the audit, rehearsed schema diff, exact pinned
   image/SHA, private mapping, blockers disposition and rollback to the owner.
   After explicit apply approval freeze **all bot writers** briefly. Before any
   candidate bootstrap, verify version/fingerprints again and take tested DB,
   originals/metadata, closed-permission environment/config and previous-image
   backups. Keep hashes/counts privately; `quick_check` and backup restore must
   pass. Existing business rows, paths, token grants and archive states are not
   migrated or retargeted. If the preflight fingerprint changed, reassess.
5. **Controlled activation gate.** Apply only the reviewed additive schema/config
   and pinned bot image. Confirm live startup matches offline rehearsal, source
   authority points to the actual bind mount, and both route entries/cutoff are
   effective. Resume only the candidate-compatible workers. Do not enqueue old
   sources or reset old attempts; no backfill/move/delete is implicit. Monitor
   ordinary bot polling and unrelated legacy behavior as well as worker health.
6. **External acceptance gate.** Use separately authorized test documents/chat.
   Prove one receipt's confirmed local save→verified correct-year/month Drive
   file and one protected statement→unencrypted direct Vypisy copy with unchanged
   encrypted-source hash. Independently read remote parent/name/type/size/md5/
   opaque delivery reference. Privately open/compare all pages; verify metadata
   retention and configured receipt retention after verified success. Prove one
   real terminal authorized notice without changing active FSM/keyboards; do not
   induce failure by breaking production credentials. Keep remote content/IDs
   private. Fake fixtures are not a substitute for this gate.
7. **Return a precise report.** Supply deployed source/image, source tree/schema
   hashes, backup verification, legacy-row comparison, route/year evidence,
   original retention, actual authorized message result and unexpected errors.
   Mark every unrun real operation `not_run`; do not call the integration fully
   accepted until this evidence exists. Include explicit rollback/readiness state.

On failure pause workers and keep a compatible candidate or forward fix. Never
start an old legacy worker while new-context jobs are runnable, even with the
route environment removed: those contexts already persist in SQLite. A broad
old-DB restore can overwrite newer business activity and is not an automatic
rollback. Preserve contexts, reservations, cutoff, source/metadata and remote
files for read-only reconciliation. Publication/integration and operational
apply remain distinct decisions throughout.
