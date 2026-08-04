# Gmail Protected Statement Period Routing V1 — Conversation Acceptance Proof

Status: `repository_verified`; production rollout and historical repair are
pending separate approval.

## Product journey

An authorized workspace has an active, administrator-configured Gmail
collector. A matching message contains a bank statement PDF whose opening
password is the stable deployment secret and whose owner/edit password is
different and unknown.

Expected deterministic journey:

1. The collector downloads the allowlisted attachment through
   `gmail.readonly`.
2. Python opens it in memory with the opening password and reads bounded header
   text. It neither asks for nor uses the owner/edit password.
3. If the previous statement is `24.06.2026` and the current statement is
   `24.07.2026`, the inclusive interval is `25.06.2026`–`24.07.2026`.
4. June contributes six days and July contributes twenty-four, so the selected
   archive month is `2026-07`.
5. The original encrypted bytes and bounded metadata are stored atomically.
   `parse_status` remains `deferred`.
6. When the separate owner Drive archive is enabled, the new job targets
   `<workspace>/2026/bankove_vypisy/2026-07`, even if local ingestion happened
   in August.
7. The Telegram notification identifies the selected archive month without
   claiming parsing or reconciliation.

## Safe failure journeys

| Input/runtime state | Required outcome |
|---|---|
| Encrypted PDF, password secret absent | Original stored; `password_required`; no new Drive job |
| Encrypted PDF, password wrong | Original stored; `password_invalid`; no secret/raw text in output or logs; no new Drive job |
| Current or previous header dates conflict | `period_ambiguous`; no month guess and no new Drive job |
| Explicit range covers equal days in two months | Month containing interval end wins |
| Non-PDF allowlisted legacy attachment | Stored with `not_pdf`; no period-routed Drive job in this version |
| Existing import/job/file | No automatic backfill, move, rewrite, or deletion |

## Evidence

- `tests/test_gmail_statement_period.py` proves correct opening-password use
  with a different owner password, missing/wrong-password failures, explicit
  and previous/current date extraction, greatest-day selection, tie-break, and
  ambiguity rejection.
- `tests/test_google_gmail_config.py` proves the password is loaded only from an
  absolute file-backed secret and is absent from config representation.
- `tests/test_gmail_statement_collector.py` proves additive legacy-schema
  migration and row preservation alongside existing storage/dedup behavior.
- `tests/test_gmail_statement_archive.py` proves a July ingestion path can
  produce a June Drive target only when an explicit validated period is passed.
- `tests/test_gmail_statement_scheduler.py` proves bounded notification text
  reports the selected period and still denies parsing/reconciliation.

Focused repository verification on 2026-08-04: `69 passed` before the final
truth/docs synchronization. Final full suite: `2518 passed, 7 subtests passed`
in 482.43 seconds. Production smoke remains required before production
acceptance.

## Forbidden claims checked

- no arbitrary bank-layout or OCR support;
- no PDF editing or owner-password recovery;
- no decrypted file retention;
- no transaction parsing, matching, reconciliation, cashflow, VAT, tax, or
  accounting conclusions;
- no automatic correction of historical Drive archives;
- no Gmail mutation or Drive scope added to the Gmail grant.
