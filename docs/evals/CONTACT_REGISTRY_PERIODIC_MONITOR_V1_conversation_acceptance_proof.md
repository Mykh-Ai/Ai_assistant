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

The callback actor, workspace membership, proposal status/TTL, contact IČO,
contact version, old values, and name/IČO conflicts are revalidated. Only
official name, legal address, DIČ, and IČ DPH may change. Invoice rows, invoice
items, `pdf_path`, and PDF bytes remain identical.

### User declines

The proposal becomes dismissed. The contact, invoices, and PDFs remain
unchanged.

### Missing tax result

RPO name/address can still be compared. Missing, unavailable, malformed, or
conflicting Financial Administration data does not clear saved DIČ or IČ DPH
and does not create a false tax-field difference.

### Fail-closed cases

Wrong actor, inactive authorization/membership/workspace, expired proposal,
callback replay, manually changed contact, IČO mismatch, ambiguous exact-IČO
result, or workspace name/IČO conflict performs no contact write.

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

Focused and full-suite results are recorded in `PROJECT_LOG.md` after execution.
