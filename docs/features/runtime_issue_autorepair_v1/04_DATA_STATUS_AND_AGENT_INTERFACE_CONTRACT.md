# Data, Status, and Agent Interface Contract

Task ID: `RUNTIME_ISSUE_INTAKE_AND_AUTOREPAIR_V1`

Status: conceptual design only. This document does not create a migration,
table, service, CLI, manifest, or outbox.

## Ownership model

```text
bot -> RuntimeIssueService -> SQLite

maintenance runner -> validated maintenance CLI/service
  -> atomically claim eligible issue in SQLite
  -> emit read-only claimed_issues_<run_id>.json
  -> accept schema-validated result for the live claim
  -> update SQLite and enqueue bot-owned notification

bot notification worker -> claim outbox item -> Telegram -> record delivery
```

SQLite is the only canonical writable store. Work/Codex never writes SQLite
directly and never changes status by editing a manifest. Proposed names describe
future ownership; no such symbols currently exist.

The claim/lease design reuses the transaction semantics demonstrated by
`bot/services/archive_job_service.py`, especially `BEGIN IMMEDIATE`,
`claim_next_runnable_job`, worker identity, lease expiry, retries, and rejected
terminal transitions. It does not reuse the archive-job table.

## Runtime issue record

Conceptual fields:

| Field | Type/bound | Owner and rule |
|---|---|---|
| `issue_id` | Canonical `IR-YYYYMMDD-NNN` or opaque stable ID | Service-generated; never supplied by user |
| `schema_version` | Small integer/string | Service |
| `status` | Issue status enum below | Service transition machine |
| `classification` | Nullable classification enum | Maintenance result only |
| `description` | Sanitized 10–2000-char target bound | Original administrator observation; never replaced by title |
| `short_title` | Up to 120 chars | Deterministic Python derivation |
| `reported_at` | UTC timestamp | Runtime clock |
| `occurred_at` | Nullable UTC timestamp | Only explicit bounded extraction |
| `occurred_at_precision` | `exact`, `date`, `approximate`, `unknown` | Validator |
| `actor_telegram_id` | Integer | Trusted update context |
| `workspace_id` | Trusted ID or null | Read-only workspace resolver; never text |
| `workspace_resolution` | `resolved`, `none`, `ambiguous` | Service audit field |
| `source_channel` | `text`, `voice` | Trusted route |
| `active_fsm_state` | Bounded string/null | Trusted snapshot |
| `active_fsm_context_summary_json` | Versioned allowlist object | Sanitized and size bounded; never raw state |
| `reported_build_sha` | Nullable 40-hex SHA | Trusted source only |
| `build_sha_status` | `known`, `unavailable`, `stale` | Service |
| `telegram_update_id` | Integer | Trusted update |
| `telegram_chat_id` | Integer | Trusted update |
| `telegram_message_id` | Integer | Trusted update |
| `privacy_metadata_json` | Versioned bounded object | Redaction version/flags, no secret values |
| `deduplication_key` | Unique stable digest | Trusted Telegram identity and source, not description alone |
| `record_version` | Monotonic integer | Compare-and-set |
| `claim_run_id` | Nullable run ID | Claim transaction |
| `claim_token_hash` | Nullable digest | Never expose raw token in logs |
| `claimed_at` | Nullable UTC timestamp | Claim transaction |
| `lease_until` | Nullable UTC timestamp | Claim transaction |
| `claim_attempt_count` | Non-negative integer | Service |
| `created_at`, `updated_at` | UTC timestamps | Service |

Raw authorization values, repair/deploy permission, credentials, tokens,
private paths, full environment, unbounded logs, and full FSM data are not
fields.

## Issue status and classification

Issue statuses:

- `new`
- `claimed`
- `expected_behavior`
- `external_failure`
- `insufficient_evidence`
- `feature_request`
- `blocked_high_risk`
- `repair_validating`
- `repair_ready_to_deploy`
- `fixed_deployed`
- `repair_failed_no_deploy`
- `deployment_failed_rolled_back`
- `deployment_failed_rollback_risk`

Classifications:

- `confirmed_low_risk_defect`
- `expected_behavior`
- `external_failure`
- `insufficient_evidence`
- `feature_request`
- `complex_or_high_risk_defect`
- `deployment_failed_rolled_back`
- `deployment_failed_rollback_risk`

Status is workflow truth; classification is diagnostic truth. For example, a
`confirmed_low_risk_defect` may end in `repair_failed_no_deploy` when a test
gate fails. It must not be changed to “fixed.”

## Allowed issue transitions

| From | To | Required evidence |
|---|---|---|
| — | `new` | Authorized idempotent intake transaction |
| `new` | `claimed` | Atomic claim, run ID, claim token, unexpired lease |
| `claimed` | `expected_behavior` | Valid result and evidence digest |
| `claimed` | `external_failure` | Proven bounded external evidence |
| `claimed` | `insufficient_evidence` | Missing-evidence statement |
| `claimed` | `feature_request` | Current Product Truth comparison |
| `claimed` | `blocked_high_risk` | Forbidden-scope/architecture reason |
| `claimed` | `repair_validating` | Proven allowlisted defect and approved authority mode |
| `repair_validating` | `repair_ready_to_deploy` | Regression, focused, adjacent, broad, static, diff, and commit gates pass |
| `repair_validating` | `repair_failed_no_deploy` | Any pre-deploy gate fails |
| `repair_ready_to_deploy` | `fixed_deployed` | Approved deploy plus exact SHA, health, smoke, and error scan |
| `repair_ready_to_deploy` | `deployment_failed_rolled_back` | Deploy/smoke failure plus verified rollback |
| `repair_ready_to_deploy` | `deployment_failed_rollback_risk` | Rollback incomplete or unverified |
| expired `claimed` | `new` | No irreversible/externally visible work; audited expiry recovery |
| expired `claimed` | `claimed` | Atomic reclaim with new token and attempt count; no unsafe prior work |

Current public policy does not permit unattended
`repair_ready_to_deploy -> fixed_deployed`; a human approval record is required.

## Forbidden transitions

- Any state directly to `fixed_deployed` without
  `repair_validating` and `repair_ready_to_deploy`.
- `insufficient_evidence`, `feature_request`, `expected_behavior`,
  `external_failure`, or `blocked_high_risk` to a repair state without a new
  audited claim/review that supplies the missing classification proof.
- A terminal result changed by manifest edit, chat message, raw SQL, or agent
  assertion.
- `deployment_failed_rollback_risk` to any state automatically.
- A stale claim token or mismatched record version changing any state.
- Notification delivery changing issue classification or deploy truth.
- Intake setting classification, repair permission, or deployment status.

Any approved manual correction is a new immutable audit event with actor and
reason; it never silently overwrites history.

## Maintenance run record

| Field | Contract |
|---|---|
| `run_id` | Service-generated stable ID |
| `status` | `started`, `claiming`, `diagnosing`, `repairing`, `deploying`, `completed`, `completed_with_blocks`, `failed`, `rollback_risk` |
| `approval_mode` | `diagnostic_only`, `human_reviewed_patch`, or separately approved future mode |
| `runner_id`, `runner_version` | Trusted maintenance identity/version |
| `policy_version`, `schema_version` | Exact versions |
| `baseline_repo_sha`, `production_sha` | Trusted SHAs or explicit unavailable status |
| `started_at`, `heartbeat_at`, `finished_at` | UTC |
| `global_lease_until` | Prevent overlapping run ownership |
| `claimed_count`, result counts | Service-derived |
| `summary_digest` | Digest of bounded canonical summary |
| `failure_code` | Bounded enum; no raw secrets/errors |

Run transitions:

```text
started -> claiming -> diagnosing
diagnosing -> claiming | repairing | completed | completed_with_blocks | failed
repairing -> claiming | deploying | completed_with_blocks | failed
deploying -> claiming | completed | completed_with_blocks | rollback_risk
rollback_risk -> human reconciliation only
```

At most one run and one issue may be in deploy/rollback activity. The proposed
default is one issue diagnosed at a time.

## Claim and lease model

- Claims are acquired with `BEGIN IMMEDIATE` and committed before manifest
  generation.
- The selection query considers only eligible `new` rows and uses stable
  ordering.
- Claim token, run ID, issue ID, status, and record version are required for
  every heartbeat/result call.
- Raw claim tokens are returned only to the isolated runner and are never put
  in public logs or bot messages; canonical storage may keep a verifier hash.
- A heartbeat extends an unexpired lease only for its live owner.
- A stale owner cannot record a result after lease expiry/reclaim.
- Lease expiry alone never resets a claim if a commit, merge, deploy, or
  rollback operation was recorded. Reconciliation is mandatory.
- Reclaim increments attempts and emits an audit event.
- A retry cap transitions repeated interrupted diagnoses to
  `insufficient_evidence` or human review according to approved policy; it
  never fabricates a diagnosis.

## Deduplication and intake idempotency

The service constructs a versioned key from trusted
`actor_telegram_id`, `telegram_chat_id`, `telegram_update_id`,
`telegram_message_id`, and `source_channel`. The key has a unique constraint.

- Same Telegram delivery: return the original issue ID; do not insert or reset
  maintenance status.
- Similar description in a new message: create a distinct issue by default.
- Optional similarity grouping may add a non-canonical relation later but
  cannot suppress an authorized new observation in V1.
- A retried acknowledgement does not create another issue.

## Generated manifest schema

Conceptual top-level JSON:

```json
{
  "schema_version": "runtime-issue-manifest-v1",
  "run_id": "MR-...",
  "generated_at": "UTC timestamp",
  "policy_version": "runtime-issue-autorepair-v1",
  "baseline_repo_sha": "40-hex or null",
  "production_sha": "40-hex or null",
  "issues": [
    {
      "issue_id": "IR-...",
      "record_version": 2,
      "claim_reference": "opaque non-secret reference",
      "description": "sanitized observation",
      "short_title": "bounded title",
      "reported_at": "UTC timestamp",
      "occurred_at": null,
      "source_channel": "text",
      "trusted_context": {
        "workspace_id": "trusted ID or null",
        "actor_telegram_id": 123,
        "active_fsm_state": "bounded state or null",
        "active_fsm_context_summary": {},
        "reported_build_sha": null,
        "telegram_update_id": 456,
        "telegram_message_id": 789
      },
      "privacy_metadata": {
        "redaction_version": "v1",
        "truncated": false
      }
    }
  ],
  "manifest_digest": "sha256:..."
}
```

The actual claim secret, bot token, credentials, raw log data, private paths,
authorization/deploy permissions, unrelated issues, and cross-workspace data
are excluded. The service signs or otherwise validates the manifest digest
according to the approved implementation design. A changed manifest is
rejected on result submission and never updates SQLite.

## Bounded log evidence schema

Each evidence item:

| Field | Rule |
|---|---|
| `evidence_id` | Service-generated |
| `source_kind` | Approved enum such as `structured_event`, `bounded_log_excerpt`, `test_reproduction`, `code_owner`, `contract`, `deployment_verification` |
| `time_start`, `time_end` | UTC and bounded window |
| `build_sha` | Trusted SHA/null |
| `workspace_scope` | Trusted ID/digest; no widening |
| `correlation_ids` | Allowlisted update/message/event IDs |
| `event_names` | Allowlisted structured names |
| `sanitized_excerpt` | Optional, size/line bounded |
| `content_digest` | Digest of evidence as evaluated |
| `redaction_version`, `redaction_flags` | Required |
| `source_reference` | Bounded public file/symbol/test or opaque private reference |

Maximum window, item count, bytes, and retention require public approval before
implementation. Raw production logs never become the canonical issue record or
public PR evidence.

## Diagnosis and result schema

| Field | Rule |
|---|---|
| `result_schema_version` | Exact supported version |
| `issue_id`, `run_id`, `record_version`, `claim_reference` | Must match live claim |
| `classification` | Exact enum |
| `root_cause_status` | `proven`, `not_proven`, `not_applicable` |
| `summary` | Bounded sanitized text |
| `evidence_ids`, `evidence_digest` | Canonical references |
| `code_owners`, `test_owners` | Existing file/symbol/test references |
| `risk_scope` | Allowlist/forbidden analysis |
| `code_changed` | Boolean derived/verified |
| `branch`, `commit_sha`, `pr_reference` | Nullable; trusted verification |
| `test_results` | Bounded focused/adjacent/broad/static result set |
| `deployment` | Not started, exact target/deployed SHA, gates |
| `rollback` | Not required, verified, or unresolved risk |
| `final_status` | Allowed transition only |
| `result_version` | Monotonic |

The service validates both schema and external facts available through trusted
interfaces. An agent string saying “deployed” cannot set `fixed_deployed`.

## Notification outbox schema

| Field | Contract |
|---|---|
| `notification_id` | Stable service ID |
| `idempotency_key` | Unique `issue_id:result_version:recipient` digest |
| `issue_id`, `result_version` | Canonical result |
| `recipient_telegram_id`, `chat_id` | Trusted issue/admin context |
| `category` | `issue_stored`, `diagnosis_completed`, `fixed_deployed`, `blocked_no_changes`, `insufficient_evidence`, `external_failure`, `rollback_completed`, `rollback_risk` |
| `payload_version`, `payload_json` | Template fields only; no raw agent-authored Telegram request |
| `status` | `pending`, `sending`, `sent`, `retry_wait`, `failed` |
| `attempt_count`, `next_attempt_at`, `lease_until`, `worker_id` | Retry/lease |
| `telegram_message_id` | Delivery evidence when sent |
| `last_error_code` | Bounded/sanitized |
| `created_at`, `sent_at`, `updated_at` | UTC |

The bot-owned worker atomically claims `pending`/eligible `retry_wait` rows,
renders approved truthful templates, sends with existing bot ownership, and
records delivery. Retry is bounded with backoff. Duplicate worker execution
does not rerun maintenance or change issue status. The maintenance runner never
receives bot credentials.

## Notification transitions

```text
pending -> sending -> sent
sending -> retry_wait -> sending
sending -> failed
retry_wait -> failed
```

An expired `sending` lease may return to `retry_wait`. A `sent` row is terminal.
Creating a new result version can create a new idempotency key; resending the
same result cannot.

## Privacy, redaction, and retention

- Persist the minimum observation and trusted correlation context needed.
- Redact detected credentials, tokens, private keys, auth headers, secrets,
  private paths, and unneeded personal/financial values before issue
  persistence or manifest generation.
- Never store raw voice audio in this feature contract; the existing voice
  owner’s retention/error behavior remains separate.
- Store only allowlisted FSM summary fields and event names.
- Scope log collection by time, trusted identifiers, workspace, and SHA.
- Give every schema a redaction version and truncation flag.
- Apply an approved retention period independently to manifests/evidence while
  preserving the canonical audit facts required by policy.
- Public commit/PR/project-log text contains bounded issue ID and technical
  facts, not the raw report or production logs.
- Private operational evidence stays in the separately mounted private input
  and is never copied into the repository.

Retention durations, byte limits, and whether a redacted description may
remain when secrets dominate the input are unresolved public decisions.

## Workspace boundaries

- Intake resolves workspace only from the authorized actor’s current trusted
  context.
- Cross-workspace IDs from text, voice, manifest edits, or result payloads are
  ignored/rejected.
- Every issue/evidence/result query includes trusted workspace scope or an
  explicitly authorized global-admin maintenance scope with audited reason.
- A maintenance manifest contains one issue and cannot enumerate unrelated
  tenants.
- Bot notification target comes from the trusted actor/admin record, never from
  issue description or agent output.
- Global maintenance metrics contain counts only and cannot reveal tenant
  descriptions or identifiers across workspaces.

Evidence: `bot/services/workspace_context.py`,
`tests/test_workspace_context.py`, and `tests/test_tenant_safety.py`.

## Service/agent failure contract

- Invalid schema, digest, token, version, transition, workspace, or evidence
  scope: reject with no canonical mutation.
- Persistence failure: rollback transaction; return a bounded error; do not
  claim the issue stored/result recorded.
- Manifest generation failure after claim: retain the claim for bounded retry
  or release through audited recovery.
- Agent interruption: lease recovery rules apply.
- Notification failure: retry outbox only; do not rerun result/deployment.
- Unknown production SHA: issue may be stored/diagnosed, but no successful
  autorepair classification may reach deployment.
- Rollback risk: freeze run and require human reconciliation.

Exact private deployment, rollback, and server-verification interfaces are not
part of the public schema. **Private operational evidence required before
implementation/deployment.**
