# CONTACT_REGISTRY_PERIODIC_MONITOR_V1 Conversation Acceptance Proof

## Scope and status

- Architecture:
  `docs/architecture/CONTACT_REGISTRY_PERIODIC_MONITOR_V1_ARCHITECTURE_DESIGN_PROOF.md`
- Capability status: `partial`, `requires_setup`,
  `requires_external_credentials`.
- AI maturity: unchanged; the workflow is deterministic Python and adds no
  LLM, STT, LMM, or self-learning authority.
- Production monitor default: disabled.

## Accepted journeys

### Official address changed

Given an authorized active workspace contact with exact IČO and an old legal
address, when its due 14-day slot arrives and RPO returns one exact identity
with a different address, the bot sends one bounded old/new proposal.

Expected controls:

- `Aktualizovať kontakt`
- `Ponechať bez zmeny`

Expected safety copy states that already issued invoices and PDFs do not
change.

### User approves

The callback actor, every grouped workspace membership, proposal status/TTL,
canonical contact IČO, contact version, old values, and name/IČO conflicts are
revalidated in one immediate transaction. Only
official name, legal address, DIČ, and IČ DPH may change. Invoice rows, invoice
items, `pdf_path`, and PDF bytes remain identical.

Two proposals for different companies remain independently actionable. Duplicate
contacts for the same authorized owner, canonical IČO, and identical official
target snapshot receive one grouped card; one approval updates every explicitly
grouped workspace contact atomically. Saved IČO formatting such as `47 983 973`
versus `47983973` does not create a false stale result. The same IČO owned by a
different actor is never grouped or mutated.

### User declines

The proposal group becomes dismissed. All grouped contacts, invoices, and PDFs
remain unchanged.

### Missing tax result

RPO name/address can still be compared. Missing, unavailable, malformed, or
conflicting Financial Administration data does not clear saved DIČ or IČ DPH
and does not create a false tax-field difference.

### Fail-closed cases

Wrong actor, inactive authorization/membership/workspace, expired proposal,
callback replay, manually changed contact, IČO mismatch, ambiguous exact-IČO
result, or workspace name/IČO conflict performs no contact write.

If any grouped duplicate is stale, unauthorized, expired, or conflicting, no
member of the group is partially updated. Existing legacy cards delivered before
grouping may still be visible; replay after another grouped resolution is stale
and cannot repeat a contact write.

Owned stale, expired, and identity-conflict cards remove obsolete markup and
explain the bounded reason. Missing or wrong-actor cards retain markup because
ownership is not proven. Telegram cleanup failure is logged and never rolls back
an already committed contact update.

### Dry run

The same eligibility, authorization, exact-IČO lookup, detail enrichment, and
diff logic runs with persistence and Telegram delivery disabled. Proposal and
monitor tables remain unchanged.

## Automated evidence

`tests/test_contact_registry_monitor.py` covers:

- DST-aware calendar scheduling at 03:00 `Europe/Bratislava`;
- 14-day next slot;
- preservation of saved tax values on missing provider values;
- approval, replay, wrong-actor, and stale-contact behavior;
- exact inactive-capable IČO search;
- no-write dry run;
- bounded callback payload;
- unchanged invoice row and PDF bytes after approved contact update.
- two sequential real handler callbacks for distinct proposal UUIDs;
- separate stale/conflict messaging and owned keyboard cleanup;
- cleanup-failure logging without business rollback;
- inactive-profile inclusion only for an actively authorized supplier owner.
- formatted saved-IČO versus canonical proposal identity regression;
- one grouped notification for same-owner duplicates across workspaces;
- one public callback applying two grouped rows atomically;
- all-or-nothing rollback when one grouped duplicate is stale;
- same-IČO cross-actor isolation.

Focused and full-suite results are recorded in `PROJECT_LOG.md` after execution.

## 2026-08-04 grouped duplicate repair evidence

- Focused monitor/service/handler/Product Truth/workspace suite: `48 passed`.
- Full repository suite: `2506 passed, 7 subtests passed`.
- `python -m compileall -q bot`: passed.
- `git diff --check`: passed with line-ending warnings only.
- Production deploy and real callback smoke: pending at commit gate and must be
  appended to `PROJECT_LOG.md` after rollout.

`safe_to_commit`
