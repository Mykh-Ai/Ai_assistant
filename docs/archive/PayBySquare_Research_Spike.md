# Technical Research Spike: real Pay by Square QR integration for FakturaBot

Date: 2026-04-03
Scope: research-only (no integration patch in `bot/services/pdf_generator.py` in this spike)

## 1) Short summary

Current Phase 4 PDF flow uses a placeholder string (`PAYBYSQUARE|...`) and does **not** generate a real PAY by square payload.

Research outcome:
- Official source-of-truth is PAY by square specification (v1.2.0) + by square API docs.
- Python ecosystem has one known direct package (`pay-by-square`), but it appears stale (last PyPI release in 2020) and does not enforce current v1.2 requirements.
- Most active open-source implementation appears to be `xseman/bysquare` (TypeScript/Go, active npm releases), not Python-native.

**Recommended path for FakturaBot:** option 3 — implement a **minimal internal Python encoder** for PAY by square (focused only on invoice payment use case), based on spec 1.2 rules and strict input validation, with small surface area and tests.

## 2) Findings

### 2.1 Official / practical spec sources

1. PAY by square specifications 1.2.0 (SBA/by square).
   - Contains encoding flow (CRC32 + LZMA + Base32hex), data model references and invoice recommendations.
   - Important recommendation for invoice payment orders: `BeneficiaryName` is required in v1.2 recommendations.

2. by square API docs (`portal.bysquare.com/docs`)
   - Practical schema-like constraints for fields in generate endpoint.
   - Useful regex examples for IBAN/BIC/symbols and required fields in API contract.
   - Requires API key (paid SaaS/credit model), therefore introduces external operational dependency.

### 2.2 Candidate implementations (library/repo)

#### A) Python package: `pay-by-square` (PyPI + GitHub `matusf/pay-by-square`)

- **What it is**: tiny Python function returning PAY by square payload string; QR image done separately by `qrcode`.
- **Pros**:
  - Python-native.
  - MIT license.
  - Very small dependency surface (stdlib for payload generation).
- **Cons / risks**:
  - Last release on PyPI: 2020-07-05 (stale risk).
  - Public API marks `beneficiary_name` optional by default, while practical v1.2 guidance says beneficiary is required.
  - No visible strict validation layer for required/format-constrained fields.

#### B) Adaptation candidate: `xseman/bysquare` (TypeScript/Go, Apache-2.0)

- **What it is**: actively maintained BYSQUARE implementation (encode/decode), supports PAY by square 1.2.0 and multiple runtimes.
- **Pros**:
  - Active project signal (npm package `bysquare` recently published, frequent updates).
  - Explicitly claims compatibility with latest PAY by square standard.
  - Includes both TS and Go implementations.
- **Cons / risks**:
  - Not Python-native: integration would require Node subprocess, FFI, or sidecar service.
  - Adds runtime complexity and failure modes to currently simple PDF pipeline.

#### C) Adaptation candidate (PHP ecosystem): `QrPaymentSK` / `paybysquare-php`

- **What it is**: mature PHP implementations.
- **Pros**:
  - Real-world usage patterns and validations can be used as reference.
- **Cons / risks**:
  - Wrong runtime for FakturaBot (Python).
  - Some PHP paths rely on external `xz` binary presence (ops dependency).

#### D) Own minimal implementation (Python, spec-driven)

- **Pros**:
  - No cross-runtime bridge.
  - Full control over validation and strictness.
  - Minimal dependencies and deterministic behavior for current invoice scope.
- **Cons / risks**:
  - Need careful conformance testing against known-good outputs/scanners.
  - Team owns long-term maintenance.

### 2.3 Verdict

For FakturaBot repo, the best practical path is:

1. **Primary recommendation: own minimal Python implementation** (option 3), spec-driven, with strict validation for the subset we actually use.
2. Keep `pay-by-square` only as optional reference/check during development, not as core production dependency.
3. Do not use paid by square API as core generation path for MVP (external service dependency + key management + availability coupling).

Rejected alternatives:
- `pay-by-square` as final dependency: rejected due to maintenance/staleness and unclear v1.2 strictness.
- TS/Go adapter now: rejected for integration complexity disproportionate to current PDF scope.
- SaaS API-first: rejected for reliability and dependency reasons in current MVP scope.

## 3) Minimal required payload for FakturaBot use case

Requested use-case fields:
- IBAN
- amount
- currency
- variable symbol
- due date

Research correction:
- For modern PAY by square (1.2 recommendation context), **beneficiary name must be treated as required** for invoice payment order compatibility.

### Practical field set for V1 integration (paymentorder)

Required (for our integration policy):
1. `PaymentOptions = paymentorder`
2. `BankAccounts[0].IBAN`
3. `Amount`
4. `CurrencyCode` (EUR default, ISO 4217 3 letters)
5. `BeneficiaryName`

Optional but needed by FakturaBot business flow:
6. `VariableSymbol` (numeric string, usually up to 10 digits)
7. `PaymentDueDate` (date)
8. `PaymentNote` (human context)
9. `BIC` (optional in many flows; can be omitted if not required by receiving app)

### Format constraints to enforce in Python validator (minimum)

- IBAN: uppercase alnum, country+check prefix; reject malformed values.
- Currency: `^[A-Z]{3}$`.
- VS: numeric, max 10 digits.
- KS: numeric, max 4 digits (if used later).
- SS: numeric, max 10 digits (if used later).
- Due date: serialize to schema-expected date format.
- Note/text: normalize to safe Unicode form; test Slovak diacritics in scanner apps.

### Diacritics / note nuance

- Spec recommendations discuss structured payment note and usability in banking apps.
- Banking apps can differ in which reference fields they display; include `PaymentNote` for user-facing clarity when needed.
- Must test with diacritics in Beneficiary/Note on real scanning clients (at least 2 SK banking apps).

## 4) Implementation recommendation (no code patch in this spike)

### 4.1 Dependency choice

- Keep existing `qrcode` dependency for image rendering.
- Add **no new heavy runtime dependency** for payload encoding.
- Implement internal helper module, e.g. `bot/services/pay_by_square.py`, with pure-Python encoding pipeline:
  1. map validated fields into PAY data sequence,
  2. CRC32,
  3. LZMA1 raw compression with correct filter params,
  4. prepend length/header,
  5. Base32hex transform to payload string.

### 4.2 Integration shape for `bot/services/pdf_generator.py`

After research spike is approved, minimal integration patch should:
1. Replace placeholder `qr_payload = f'PAYBYSQUARE|...'` with a call to the internal encoder service.
2. Feed data from existing invoice/supplier fields:
   - IBAN from supplier profile,
   - amount/currency from invoice,
   - VS from invoice,
   - due date from invoice,
   - beneficiary name from supplier name,
   - optional note from invoice number or invoice context string.
3. Keep `_draw_qr(...)` unchanged (it already accepts payload string and renders PNG).

### 4.3 Docs/changelog updates expected in real integration PR

When integration patch is done:
- Update `docs/TZ_FakturaBot.md` with explicit statement that PDF QR now uses real PAY by square payload generation (including required fields and validation behavior).
- Add decision entry to `PROJECT_LOG.md` describing chosen implementation path and why alternatives were rejected.
- Add user-facing line in `CHANGELOG.md` for real Pay by Square compatibility (not placeholder).

### 4.4 Compatibility verification plan

Definition of done for implementation PR:
1. Unit tests:
   - deterministic payload for fixed input vector,
   - validation failures for malformed IBAN/currency/VS/date.
2. Regression check:
   - PDF generation still succeeds and embeds QR image.
3. Real-world scan checks (manual):
   - test at least 2 Slovak mobile banking apps,
   - verify imported fields (IBAN, amount, currency, VS, due date, beneficiary, note),
   - keep screenshots/notes in PR description.

## 5) Risks / open questions

1. **Spec version drift risk**
   - Need to pin implementation explicitly to PAY by square 1.2 behavior.
2. **Bank app variance risk**
   - Some clients may hide/show symbols differently; note handling should remain robust.
3. **Text normalization risk**
   - Diacritics and long notes may be rendered differently across scanner apps.
4. **Conformance confidence**
   - Without official public test vectors, we should maintain internal golden vectors + manual scan matrix.

## 6) Optional post-spike implementation sketch

Likely file changes in next PR:
- `bot/services/pay_by_square.py` (new)
- `bot/services/pdf_generator.py` (replace placeholder payload generation call)
- `docs/TZ_FakturaBot.md` (document real behavior)
- `PROJECT_LOG.md` (decision record)
- `CHANGELOG.md` (release note)

No code changes to runtime logic were made in this spike beyond this research artifact.

## Sources

- PAY by square specifications 1.2.0: https://app.bysquare.com/OrionLibraries/Orion.Web.Components/Common/Handlers/File.ashx?a=Orion.Web&c=Orion.Web.Modules.Content.Data.ArticlesDataSource&fd=1&id=3&m=GetArticleAttachement
- by square API docs: https://portal.bysquare.com/docs/
- PyPI `pay-by-square`: https://pypi.org/project/pay-by-square/
- GitHub `matusf/pay-by-square`: https://github.com/matusf/pay-by-square
- GitHub `xseman/bysquare`: https://github.com/xseman/bysquare
- npm `bysquare`: https://www.npmjs.com/package/bysquare
- GitHub `RikudouSage/QrPaymentSK`: https://github.com/RikudouSage/QrPaymentSK
- GitHub `FELDSAM-INC/paybysquare-php`: https://github.com/FELDSAM-INC/paybysquare-php
