# FakturaBot Canonicalization + Slovak-normalized AI Layer — Implementation Plan (Draft)

**Document role:** rollout and implementation-planning document (scope, phases, order, risks, acceptance).  
Detailed LLM behavior contract is maintained separately in `docs/FakturaBot_LLM_Orchestrator_Contract.md`.

## 1) Executive summary

This memo proposes a **minimal-risk, 3-phase rollout** that keeps Python as source of truth and adds normalization in controlled layers:

- **Phase 1 (Python-only):** deterministic contact/service canonicalization for safer lookup and stable internal terms; no AI changes.
- **Phase 2 (LLM layer):** multilingual input → Slovak-normalized business draft, but still draft-only; Python validates/resolves/stores.
- **Phase 3 (PDF follow-up):** optional 1–3 line support/footer text block with layout-safe constraints.

Design principle: fail-loud on ambiguity, no silent auto-fix in high-impact paths.

---

## 2) Phase 1 — Python-side canonicalization layer (no AI)

### 2.1 Current seams in repo (audit)

- Invoice flow currently resolves contact by:
  1) exact name,
  2) case-insensitive exact name.
  If not found, user is pushed to `/contact`. (`_resolve_contact_by_name` in `bot/handlers/invoice.py`.)
- Contact service currently has only exact and case-insensitive match methods; no normalized lookup state model.
- Service alias exists (`ServiceAliasService.resolve_alias`) but only direct alias lookup after LLM extraction; no cross-language deterministic synonym dictionary.
- Invoice persistence already supports `description_raw` and `description_normalized`, which is a good seam for internal canonical term introduction.

### 2.2 Minimal safe patch path

1. Add new Python normalization helpers (separate service module, pure functions):
   - company name lookup normalization,
   - service-term normalization.
2. Extend `ContactService` with deterministic lookup method returning structured result state (not just profile or None).
3. Update invoice handler contact resolution to consume lookup state and branch explicitly.
4. Keep existing DB schema unchanged in first iteration (no migration required).
5. Keep existing `/contact` manual flow unchanged; only invocation conditions become explicit.

### 2.3 Contact/company normalization plan

#### Scope
- lookup-only normalization, **not display normalization**.
- preserve original legal name for invoice/PDF output.

#### Deterministic normalization rules (lookup key)
- lowercase
- trim leading/trailing spaces
- collapse repeated spaces
- remove punctuation variants (`.`, `,`, extra separators) where safe
- normalize legal suffix variants for lookup key only, e.g.:
  - `s.r.o.`, `sro`
  - `a.s.`, `as`

> Important: suffix stripping must be conservative and token-boundary aware (avoid stripping meaningful substrings inside words).

#### Lookup result states (required)
- `exact_match`
- `normalized_match`
- `multiple_candidates`
- `no_match`

#### Behavior contract
- `no_match` must not auto-convert to contact creation.
- `multiple_candidates` must trigger explicit user disambiguation.
- only `exact_match` and `normalized_match` can continue invoice draft flow automatically.

### 2.4 Service-term normalization plan (deterministic)

Add a small Python dictionary for internal canonical service term (Slovak), examples:

- `opravy` → `oprava`
- `ремонт` → `oprava`
- `монтаж` → `montáž`

Usage in Phase 1:
- produce **internal canonical service term** alongside raw text,
- do not replace supplier-defined canonical invoice title generation,
- keep current alias resolution precedence for final output title.
- explicit precedence: deterministic service-term normalization is internal-only; supplier alias mapping remains source of truth for final invoice title shown in preview/PDF.

### 2.4.1 Cross-layer invariant: internal canonicalization vs supplier display mapping

Internal service-term normalization and supplier alias mapping are two separate deterministic layers and must be bridged explicitly in runtime resolution.

- `service_term_internal` / `termin_sluzby_sk` is internal-only normalization for logic and traceability.
- Final preview/PDF service title remains supplier-scoped alias truth (`supplier_service_alias.canonical_title`).
- Final display title resolution must use deterministic cascade:
  1. supplier alias by raw `service_short_name`,
  2. supplier alias by canonical internal term,
  3. supplier alias by deterministic canonical-equivalent bridge forms (for current family: `oprava -> opravy`),
  4. raw `service_short_name` fallback only when all previous deterministic stages miss.

Regression example that motivates this invariant: raw multilingual input `ремонт` normalized internally to `oprava`, while supplier alias exists only under `opravy`; runtime must still resolve the final Slovak supplier title and must not fall back early to raw multilingual text.

### 2.5 Proposed function/data boundaries

- `normalize_company_lookup_key(name: str) -> str`
- `resolve_contact_lookup(telegram_id: int, name: str) -> ContactLookupResult`
  - `state: exact_match|normalized_match|multiple_candidates|no_match`
  - `matched_contact_id: int | None`
  - `candidate_contact_ids: list[int]`
- `normalize_service_term(raw_item: str) -> str | None`
- `build_internal_item_canon(raw_item: str, supplier_id: int) -> ItemCanonResult`
  - combines deterministic service-term map + current alias resolver (without overriding explicit alias mapping policy).

### 2.6 Acceptance criteria (Phase 1)

- Input `Tesla sro` matches stored `Tesla s.r.o.` as `normalized_match`.
- `Tesla` with two possible contacts returns `multiple_candidates`.
- `no_match` path asks user to explicitly confirm the next step; no automatic `/contact` creation.
- `ремонт` normalizes to Slovak internal term `oprava` deterministically.
- Existing exact-match behavior remains unchanged for exact cases.
- No DB migrations required.

---

## 3) Phase 2 — LLM Slovak-normalized business layer (future)

### 3.1 Boundary: LLM vs Python

Architecture rule:
- user input may be Slovak / Ukrainian / Russian / mixed, but business semantics passed from LLM to Python must be Slovak-normalized.

LLM responsibilities:
- interpret multilingual/noisy input,
- produce structured draft with Slovak-normalized business meaning,
- preserve original text,
- flag missing/ambiguous fields,
- never claim side effects.

Python responsibilities:
- contact lookup and state resolution,
- validation and defaults,
- canonical dictionaries and alias truth,
- storage/PDF/QR/email side effects,
- final truth after user confirmation.

Detailed LLM behavior, payload schema, and failure rules are defined in `docs/FakturaBot_LLM_Orchestrator_Contract.md`.

### 3.2 Planning-level payload shape (non-normative)

- `input.original_text` (raw user/STT text for traceability)
- `business_sk` (Slovak-normalized business draft for Python workflows)
- `trace` (ambiguities/missing-fields for explicit fail-loud clarification paths)

Rule: legal/business identifiers (`IČO`, `DIČ`, legal suffixes, exact registered names) must never be invented by LLM.

### 3.3 Terminology dictionary ownership (planning view)

- **LLM vocabulary/synonym layer:** understanding user language (SK/UA/RU/mixed/noisy), mapping to draft Slovak business semantics.
- **Python canonical dictionary:** truth layer for normalized business terms, alias precedence, and lookup-safe normalization rules.

Decision rule: LLM suggests; Python canonical dictionary decides final normalized field used for workflow.

### 3.4 Acceptance criteria (Phase 2)

- Mixed-language input produces Slovak-normalized business fields + preserved original text.
- Ambiguity is explicit in payload; no hidden guesses.
- Python can ignore/override LLM draft fields when deterministic rules disagree.
- No side effect is executed from LLM output without Python validation + user confirmation.

---

## 4) Phase 3 — Small PDF follow-up (optional support/footer text)

### 4.1 Minimal safe seam in current generator

Current footer line is drawn near bottom (`pdf.drawString(..., 12 * mm, ...)`).
Safe seam:
- extend `PdfInvoiceData` with optional field, e.g. `supporting_text: str | None`,
- render only when present,
- max 1–3 lines, wrapped by existing width helpers,
- place above/beside current fixed footer zone without touching totals/QR zones.

### 4.2 Layout risks

- collision with QR/total block when items table grows downward,
- overflow near bottom margin for long text,
- font readability in small space.

### 4.3 Risk controls

- hard cap: 3 lines, fixed font size, truncation with explicit ellipsis,
- render guard: if insufficient vertical space, skip optional block (fail-safe),
- do not alter existing invoice totals/QR positioning logic in first patch.

### 4.4 Acceptance criteria (Phase 3)

- When `supporting_text` is empty: PDF identical to current layout.
- When provided (1–3 short lines): text appears in defined support area, no overlap with totals/QR/table.
- Long text is safely truncated; PDF generation never crashes.

---

## 5) Recommended implementation order

1. **Phase 1.A** contact lookup normalization + explicit lookup states.
2. **Phase 1.B** deterministic service-term canonicalization.
3. Integrate Phase 1 states into invoice handler UX branches.
4. **Phase 2** LLM Slovak-normalized draft schema + Python gatekeeping.
5. **Phase 3** optional PDF support/footer block.

Reason: Phase 1 reduces operational risk immediately and creates deterministic substrate for safe AI expansion.

---

## 6) Main risks / open questions

1. Final legal-suffix stripping set for Slovak companies (exact safe list + token rules).
2. UX for `multiple_candidates` selection in Telegram (single-step list vs explicit command).
3. Precedence policy between:
   - supplier alias map,
   - deterministic service-term map,
   - LLM proposed `service_term_sk`.
4. Whether to store new canonicalization trace fields now or postpone until Phase 2.
5. PDF optional text i18n policy (fixed Slovak support text vs user-language free text).

---

## 7) Suggested spec document path in repo

`docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md`
