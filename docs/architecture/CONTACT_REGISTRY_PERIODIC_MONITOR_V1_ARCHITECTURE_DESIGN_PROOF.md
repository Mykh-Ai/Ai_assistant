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

When a real difference exists, Python persists one pending proposal per contact
snapshot. Proposals created for the same authorized actor, canonical IČO, and
identical official target snapshot are presented as one Telegram group message
identifying the company, affected saved-profile count, and old/new values with
`Update contact` and `Leave unchanged` buttons. The callback contains only an
opaque proposal UUID and canonical `yes`/`no`.

Each proposal UUID remains bound to one contact snapshot. Proposals with a
different actor, canonical IČO, or official target snapshot remain independently
actionable. Same-owner duplicate contacts with the same canonical IČO and target
snapshot form one atomic confirmation group. Formatting differences such as
`47 983 973` versus `47983973` are identity-equivalent and never create a false
`contact_ico_changed` stale result. If any grouped contact changed, lost
authorization, or conflicts, the group performs no partial contact write.

Approval revalidates callback actor, every grouped workspace ownership, pending
status, expiry, canonical contact IČO, contact version/old values, and name/IČO
conflicts in one immediate transaction. It updates only the four monitored
contact columns for all explicitly grouped rows and marks every grouped proposal
applied. Replays, wrong actors, stale contacts, expired proposals, conflicts,
cross-owner same-IČO rows, and malformed callbacks fail closed.
The asynchronous callback does not alter FSM state.

New duplicate proposals receive one inline keyboard for the group. Handled
`applied`, `dismissed`, owned `stale`, `expired`, and `conflict` outcomes remove
that markup. Legacy already-delivered cards may remain individually visible;
after one grouped resolution, replaying another legacy card is stale and removes
only its owned markup. `missing` and `forbidden` do not edit markup because
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
4. `Update contact` revalidates and atomically changes allowed fields on every
   explicitly grouped same-owner duplicate;
5. duplicate/replayed/stale/wrong-tenant callbacks make no write.

## 7. Acceptance gate

Required evidence: config/calendar tests, exact inactive-IČO provider test,
diff/no-clear tests, authorization and workspace isolation, batch/failure
behavior, proposal TTL/idempotency/staleness/conflict tests, deletion cleanup,
Product Truth/InfoHelp/eval updates, invoice-row/PDF-byte invariants, focused
tests, full suite, disabled production deploy, no-write dry-run, enabled
schedule, and healthy-container smoke.

## 8. 2026-08-04 production incident repair

Production evidence showed one owner had the same IČO saved in two isolated
workspaces, once as `47983973` and once as `47 983 973`. The literal callback
comparison rejected the formatted row as `contact_ico_changed`; a later invoice
correctly used that still-unmodified workspace contact. The repair canonicalizes
IČO at revalidation and conflict boundaries, groups only same-owner/same-target
pending rows without a schema change or backfill, and applies the group atomically.

Persisted-data shape remains unchanged. Existing monitor/proposal rows are
compatible and derive group membership dynamically; rollback is code rollback
plus the normal pre-deploy SQLite backup. No invoice row, PDF, workspace owner,
active selection, contact IČO formatting, or unrelated contact field is rewritten.

ready_for_handoff
