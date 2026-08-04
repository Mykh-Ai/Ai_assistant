# Gmail Protected Statement Period Routing V1 — Architecture Design Proof

Status: `ready_for_handoff`

## Decision

The controlled Gmail bank-statement collector may inspect a PDF attachment in
memory to determine its statement period before the existing immutable original
is routed to the owner Google Drive archive. This remains a deterministic Python
integration extension. It is not a new canonical Telegram action, FSM flow, AI
capability, transaction parser, or accounting workflow.

The opening password is deployment-owned configuration. It must be loaded from
an administrator-managed, read-only secret file named by
`GOOGLE_GMAIL_STATEMENT_PDF_OPEN_PASSWORD_FILE`. The password must not be
accepted through Telegram, committed to Git, stored in SQLite or metadata,
included in logs, or retained in a decrypted file. The PDF owner/edit password
is neither required nor requested.

## Current-state variance being repaired

The earlier Gmail V1 proof says the archive year/month comes from the validated
Gmail internal date. The current runtime instead stores new originals under the
collector execution timestamp and derives the Drive target from that local
path. A statement imported in August can therefore be archived under August
even when the statement itself covers June.

V1 period routing supersedes both choices for newly collected PDF statements:

- local storage continues to represent the immutable ingestion location and is
  not moved;
- Drive routing uses the validated statement period extracted from the PDF;
- existing rows, local paths, Drive files, and archive jobs are not rewritten
  automatically.

## Period contract

The detector may use only bounded statement-header evidence:

1. an explicit `od <date> do <date>` / statement-period range; or
2. a unique current statement date together with a unique previous-statement
   date, where the covered interval begins on the day after the previous
   statement and ends on the current statement date.

Transaction dates must not be counted or interpreted as the statement period.
The selected archive month is the calendar month containing the greatest number
of inclusive covered days. When two months have the same count, the month
containing the interval end wins. The interval must be ordered and bounded; an
ambiguous, missing, malformed, or implausibly long interval is not guessed.

Examples:

- `2026-06-25` through `2026-07-24` selects July (24 July days versus 6 June
  days);
- `2026-06-16` through `2026-07-15` selects July by the end-month tie-break;
- previous statement `2026-05-31` and current statement `2026-06-30` yields
  `2026-06-01` through `2026-06-30`, therefore June.

## Runtime sequence and authority split

1. Gmail readonly transport downloads an allowlisted bounded attachment.
2. Python validates the attachment and, for PDF input, opens it in memory with
   the configured opening password when encryption requires one.
3. Python extracts bounded header text and resolves the period with the contract
   above.
4. The encrypted source bytes are stored unchanged using the existing atomic
   workspace-scoped intake path.
5. Period status and bounded dates are stored in metadata and additive SQLite
   columns. No password or extracted page text is persisted.
6. Only a statement with `statement_period_status=detected` may be enqueued into
   the period-derived Drive folder. Otherwise the original remains local and the
   archive is withheld for safe review.

No LLM, LMM, STT, or self-learning component participates in this sequence.

## Failure states

The detector returns bounded machine codes rather than raw parser exceptions or
page content:

- `not_pdf` — non-PDF attachments remain stored but are not period-routed by
  this version;
- `password_required` — encrypted PDF and no configured opening password;
- `password_invalid` — the configured opening password did not decrypt it;
- `pdf_unreadable` — invalid or unsupported PDF structure;
- `text_unavailable` — bounded pages yielded no usable text;
- `period_ambiguous` — dates conflict, are missing, or fail interval bounds;
- `detected` — validated start, end, selected year/month, and source are
  available.

Failures never disclose the password, decrypted content, sender, or subject in
logs. A period failure must not silently fall back to the import month for a new
Gmail statement archive job.

## Persistence and migration safety

The `gmail_statement_imports` table receives additive nullable period columns
and a non-destructive status default. Schema repair is idempotent and preserves
all existing rows. Existing imports remain `not_checked`; there is no automatic
backfill, local-path rewrite, Drive move, deletion, or archive-job mutation.

Before any production backfill or correction, the administrator must perform a
read-only audit, take a database and storage backup, review a dry-run mapping,
and explicitly approve the write. Rollback is restoring the database backup;
existing immutable originals remain available throughout.

## Product truth and limits

This capability stays `partial` and `requires_setup`, `requires_admin`, and
`requires_external_credentials`. It may claim only deterministic period
detection and new-item Drive routing for supported statement layouts when the
opening-password secret is configured. It must not claim arbitrary bank PDF
support, PDF editing, owner-password recovery, transaction parsing,
reconciliation, cashflow, VAT, tax analysis, or automatic repair of historical
archives.

## Acceptance evidence

- encrypted PDF opens with the user/opening password while a different owner
  password exists;
- missing and wrong passwords fail closed without secret leakage;
- explicit and previous/current date layouts resolve the inclusive interval;
- the greatest-covered-days rule and end-month tie-break are unit tested;
- a PDF stored in an August ingestion path can enqueue to the June Drive target;
- legacy schema rows survive additive schema initialization;
- encrypted source bytes remain byte-for-byte unchanged and no decrypted file
  is created;
- Product Truth, InfoHelp, setup docs, project log, and UX acceptance evidence
  describe the same partial capability.

