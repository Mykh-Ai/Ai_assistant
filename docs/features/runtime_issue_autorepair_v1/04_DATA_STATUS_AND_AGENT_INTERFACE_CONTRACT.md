# Data, Status, And Agent Interface Contract

Stage 1 task ID: `RUNTIME_ISSUE_INTAKE_V1`

Stage 2 task ID: `RUNTIME_ISSUE_AUTOREPAIR_V1`

Status: `approved_design_pending_implementation`

## 1. Ownership model

```text
Stage 1 OfficeFlow bot
-> RuntimeIssueService
-> immutable runtime_issues observation

Stage 2 handoff service
-> dedicated handoff record and lease
-> bounded read-only handoff manifest

ChatGPT Work / GitHub workshop
-> durable source receipt
-> diagnosis log
-> source issue -> zero/one/multiple findings
-> carry-forward queue
-> repair branches/tests/commits/Draft PRs

Stage 2 acknowledgment service
-> records only durable workshop delivery evidence

Notification bridge
-> validates a bounded Slovak template request
-> bot-owned sender delivers and records status
```

The worker never mutates `runtime_issues` directly and never runs arbitrary SQL.

## 2. Stage 1 invariant

The existing `runtime_issues` table remains the canonical immutable intake observation. Its current `intake_status='new'` constraint is not broadened for Stage 2.

Stage 1 fields remain owned by the existing service, including:

- issue ID;
- sanitized description/title;
- reported timestamp;
- trusted actor/chat/update/message identifiers;
- nullable trusted workspace;
- source channel;
- nullable FSM state and allowlisted context summary;
- trusted build SHA status;
- privacy metadata;
- deduplication identity.

`active_fsm_state=null` means no FSM was active and is valid. It must not be confused with a technical read failure.

## 3. Dedicated Stage 2 handoff record

Proposed conceptual fields:

| Field | Rule |
|---|---|
| `handoff_id` | service-generated stable `RH-...` |
| `issue_id` | existing Stage 1 issue reference |
| `status` | `leased`, `acknowledged`, `expired_unacknowledged`, `reconciled` |
| `lease_token_hash` | verifier only; raw token returned only to runner if needed |
| `lease_owner` | approved Work/runner identity |
| `leased_at`, `lease_until` | UTC |
| `manifest_schema_version` | exact supported version |
| `manifest_digest` | digest of returned sanitized manifest |
| `workshop_branch` | expected workshop branch after ack |
| `workshop_commit_sha` | exact durable receipt commit after ack |
| `acknowledged_at` | UTC/null |
| `attempt_count` | incremented on safe re-offer |
| `created_at`, `updated_at` | UTC |

An issue may have only one acknowledged workshop handoff. An unacknowledged expired lease may be safely offered again.

## 4. Handoff transitions

```text
no handoff -> leased
leased -> acknowledged
leased -> expired_unacknowledged
expired_unacknowledged -> leased
acknowledged -> terminal delivery fact
```

Forbidden:

- acknowledgment without verified durable workshop commit;
- diagnosis/classification written into the handoff record;
- changing the Stage 1 issue row to represent workshop status;
- stale/mismatched lease token acknowledgment;
- two acknowledged handoffs for the same issue.

## 5. Handoff manifest

Conceptual JSON:

```json
{
  "schema_version": "runtime-issue-handoff-v1",
  "handoff_id": "RH-...",
  "generated_at": "UTC",
  "lease_until": "UTC",
  "manifest_digest": "sha256:...",
  "issue": {
    "issue_id": "IR-...",
    "description": "sanitized observation",
    "short_title": "bounded title",
    "reported_at": "UTC",
    "source_channel": "text",
    "workspace_id": null,
    "workspace_resolution_reason": "no_active_workspace",
    "active_fsm_state": null,
    "fsm_context_status": "not_active",
    "active_fsm_context_summary": {},
    "reported_build_sha": null,
    "build_sha_status": "unavailable",
    "telegram_update_id": 123,
    "telegram_message_id": 456,
    "privacy_metadata": {}
  }
}
```

The manifest excludes bot tokens, credentials, raw logs, arbitrary environment data, private commands, unrelated issues, and cross-workspace records.

## 6. Workshop persistence

Target branch:

```text
maintenance/runtime-issue-workshop
```

Target files:

```text
docs/features/runtime_issue_autorepair_v1/workshop/AUTOREPAIR_QUEUE.json
docs/features/runtime_issue_autorepair_v1/workshop/AUTOREPAIR_LOG.md
```

### 6.1 Queue responsibility

The queue answers what remains to be diagnosed, repaired, reviewed, or escalated. It contains compact machine-readable facts and `log_ref` values.

Source issue conceptual fields:

- `issue_id`;
- `handoff_id`;
- `status`: `received_for_diagnosis`, `diagnosing`, `decomposed`, `partially_resolved`, `resolved`, `blocked`;
- `finding_ids`;
- `log_ref`;
- received/updated timestamps;
- workshop receipt SHA.

Finding conceptual fields:

- `finding_id`;
- `parent_issue_id`;
- `classification`;
- `status`;
- `owner_scope`;
- `log_ref`;
- `next_action`;
- exact branch/commit/PR facts when verified;
- test summary references;
- updated timestamp.

### 6.2 Log responsibility

The append-oriented log answers:

- what the handoff script returned;
- what sources were inspected;
- what bounded evidence was found or unavailable;
- how the issue was decomposed;
- why each finding received its status;
- what code/data/production did or did not change;
- what the next worker should do.

The log stores bounded sanitized summaries, not raw logs or secrets.

## 7. Workshop status transitions

Source issue:

```text
received_for_diagnosis -> diagnosing
diagnosing -> decomposed | resolved | blocked
decomposed -> partially_resolved | resolved | blocked
partially_resolved -> partially_resolved | resolved | blocked
```

Finding:

```text
received_for_diagnosis -> diagnosing
diagnosing -> needs_more_diagnostics
           | queued_for_repair
           | resolved_expected_behavior
           | resolved_external_failure
           | resolved_no_code
           | requires_architecture_design
           | requires_product_decision
           | requires_authorized_data_correction
           | blocked_by_security_boundary
           | blocked_by_accounting_truth
           | insufficient_evidence
queued_for_repair -> repair_in_progress
repair_in_progress -> patch_ready_for_review
                   | branch_pushed_pr_blocked
                   | repair_failed_no_patch
```

No queue edit may claim `patch_ready_for_review` without verified pushed commit and Draft PR.

## 8. Bounded evidence interface

Target command:

```text
runtime_issue_evidence collect(issue_id, handoff_id)
```

Evidence item fields:

| Field | Rule |
|---|---|
| `evidence_id` | service-generated |
| `source_kind` | approved enum: structured event, bounded log excerpt, test reproduction, code owner, contract, Git fact, runtime health |
| `time_start`, `time_end` | bounded UTC window |
| `workspace_scope` | trusted ID/null; never widened |
| `correlation_ids` | allowlisted update/message/issue/handoff IDs |
| `build_sha` | trusted SHA/null |
| `event_names` | allowlisted names |
| `sanitized_excerpt` | optional capped text |
| `content_digest` | digest of evaluated evidence |
| `redaction_version`, `redaction_flags` | required |
| `source_reference` | public file/symbol/test or opaque private reference |

Allowed evidence categories include actual recorded STT results/errors, Docker health/restarts, Python exceptions, and network/provider facts. Absence of evidence is represented explicitly.

## 9. Notification bridge

The worker submits only a validated template enum and bounded fields. Conceptual fields:

- `notification_id`;
- idempotency key from issue/finding/result version/recipient;
- issue and optional finding ID;
- trusted recipient/chat resolution;
- template enum;
- bounded template payload;
- `pending`, `sending`, `sent`, `retry_wait`, `failed`;
- attempts/lease/error code;
- Telegram message ID when sent.

The worker never receives the production bot token. A delivery retry does not rerun maintenance.

## 10. Privacy and tenant boundaries

- workspace may be null when none was active;
- no active FSM is valid context;
- evidence queries use trusted issue identifiers, bounded time, and workspace when present;
- cross-workspace widening is rejected;
- raw STT audio is not required;
- raw production logs are not committed;
- server paths/commands remain in the private first-read skill;
- public workshop/PR text contains bounded IDs and technical facts only.

## 11. Failure contract

- invalid schema/digest/token/lease/version: reject with no canonical mutation;
- workshop push fails: do not acknowledge handoff;
- ack fails after a verified push: preserve receipt, retry/reconcile acknowledgment without duplicating the source item;
- evidence unavailable: record the gap; do not invent cause;
- queue/log conflict: stop and reconcile; no force-push;
- notification failure: retry delivery only;
- unknown production SHA: diagnosis may continue, but claims requiring exact deployment truth are forbidden;
- direct SQL attempt: policy violation; stop.
