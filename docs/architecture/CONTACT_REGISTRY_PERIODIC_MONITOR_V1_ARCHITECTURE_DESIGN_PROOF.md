# CONTACT_REGISTRY_PERIODIC_MONITOR_V1 Architecture Design Proof

## 1. Decision

- Task: periodically compare saved workspace contacts with official Slovak
  registries and offer a confirmation-gated contact update.
- Schedule: every 14 calendar days at 03:00 in `Europe/Bratislava`, anchored
  at Monday 2026-08-03 03:00.
- Classification: deterministic internal `contacts` strategy plus an
  asynchronous notification decision; no new canonical top-level action.
- Product status: `partial`, `requires_setup`, and
  `requires_external_credentials`. The monitor is disabled by default.
- AI maturity: unchanged. Python owns schedule, lookup, diff, authorization,
  proposal persistence, validation, and update. No LLM/STT/LMM or learning is
  added.

## 2. Contract and scope preflight

The Product Doctrine, AI Layer, Product Truth, Product Truth Registry,
Self-Learning, evaluation/UX, TZ, LLM action/response, DecisionResolver,
InfoHelp, code-agent handoff, implementation checklist, migration runbook,
contact-registry proofs, top-level/subflow proof contract, and private server
runbook were inspected before implementation.

Touched scopes: configuration, external read-only registry access, scheduler,
SQLite schema, tenant-scoped contact updates, callback confirmation, deletion
cleanup, Product Truth/InfoHelp/TZ, tests/evals, deployment and rollback.

Explicitly out of scope: new actions, conversational text/voice confirmation,
automatic contact updates, invoice/PDF regeneration, changes to email/IBAN/
contact person/contracts, public SaaS expansion, and learned aliases.

## 3. Persisted data and migration safety

Current production evidence before implementation:

- SQLite quick check was `ok`;
- 5 contacts, 4 with valid eight-digit IČO, no null workspace;
- 10 invoices referencing 2 distinct contacts;
- no duplicate `(workspace_id, ico)` groups;
- neither proposed monitor table existed.

The change is additive. It creates:

1. `contact_registry_monitor_state`, keyed by contact and workspace, containing
   bounded scheduling/result state only.
2. `contact_registry_change_proposal`, keyed by an opaque proposal UUID,
   containing bounded old/new values, changed field names, sources, actor,
   contact version, TTL, notification status, and resolution status.

There is no `ALTER`, rebuild, backfill, contact rewrite, invoice rewrite, path
rewrite, or PDF regeneration. User-data deletion removes proposal/state rows
before deleting contacts.

Production rollout order is stop container, backup DB and environment with
hash/build/image evidence, deploy with the monitor disabled, validate additive
schema, run a no-write/no-notification registry dry-run, then enable the
schedule. Rollback restores the previous code/image and verified DB backup.

## 4. Runtime design

Eligibility requires:

- globally enabled contact registry lookup and monitor flags;
- a valid eight-digit contact IČO;
- non-null workspace;
- persisted workspace ownership/supplier and authorized user; the workspace or
  membership may be inactive so dormant profile contacts are not left stale;
- due calendar slot and no live pending proposal.

The official RPO query is exact by IČO and may include inactive entities for
monitoring. The selected result must be the single exact IČO match. Detail and
optional tax enrichment then produce a bounded candidate.

Monitored fields are official company name, legal address, DIČ, and IČ DPH.
IČO is the immutable identity anchor. Missing or failed tax data never clears
saved DIČ/IČ DPH. Normalized equality prevents formatting-only notifications.
Raw provider responses are neither logged nor persisted.

When a real difference exists, Python persists one pending proposal and sends
the authorized workspace owner a Telegram message identifying the contact and
IČO and showing old/new values with
`Update contact` and `Leave unchanged` buttons. The callback contains only an
opaque proposal UUID and canonical `yes`/`no`.

Each proposal UUID remains independently bound to one contact snapshot. Applying
one contact proposal does not invalidate a different contact proposal. If a
proposal itself expired, its contact changed, or its resulting identity conflicts
with another saved contact, Python returns that exact bounded outcome instead of
presenting every case as a missing proposal.

Approval revalidates callback actor, authorized workspace ownership, pending
status, expiry, contact workspace/IČO/version/old values, and name/IČO
conflicts in one immediate transaction. It updates only the four monitored
contact columns and marks the proposal applied. Replays, wrong actors, stale
contacts, expired proposals, conflicts, and malformed callbacks fail closed.
The asynchronous callback does not alter FSM state.

Handled `applied`, `dismissed`, owned `stale`, `expired`, and `conflict` outcomes
remove their inline markup. `missing` and `forbidden` do not edit markup because
message ownership is unproven. Cleanup failures are logged without reversing an
already committed contact effect.

## 5. Invoice immutability

This workflow issues no `UPDATE invoice`, `UPDATE invoice_item`, PDF generation,
file write, or `pdf_path` mutation. Existing invoices retain the details and
PDF already issued. Tests snapshot invoice rows and PDF bytes before and after
an approved contact change.

This guarantee is scoped to the monitor workflow. Existing explicit invoice
editing/regeneration behavior remains governed by its own flow.

## 6. Failure and observability rules

Provider failures update only bounded monitor error/failure state and schedule
the next calendar check; they do not change a contact or create a misleading
proposal. Telegram send failures keep a bounded pending proposal and record the
failed attempt; they never update the contact. Automatic delivery retry is outside V1. Logs contain record identifiers and error codes, not
contact payloads or credentials.

The user journey proving the feature is:

1. a due authorized workspace contact is resolved by exact IČO;
2. an official address/name/tax difference creates one notification;
3. `Leave unchanged` dismisses it with no contact/invoice/PDF change; or
4. `Update contact` revalidates and changes only allowed contact fields;
5. duplicate/replayed/stale/wrong-tenant callbacks make no write.

## 7. Acceptance gate

Required evidence: config/calendar tests, exact inactive-IČO provider test,
diff/no-clear tests, authorization and workspace isolation, batch/failure
behavior, proposal TTL/idempotency/staleness/conflict tests, deletion cleanup,
Product Truth/InfoHelp/eval updates, invoice-row/PDF-byte invariants, focused
tests, full suite, disabled production deploy, no-write dry-run, enabled
schedule, and healthy-container smoke.

ready_for_handoff
