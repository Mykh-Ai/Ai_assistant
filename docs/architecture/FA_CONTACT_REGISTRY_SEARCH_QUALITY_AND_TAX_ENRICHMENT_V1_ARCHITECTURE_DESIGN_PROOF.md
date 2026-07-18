# FA_CONTACT_REGISTRY_SEARCH_QUALITY_AND_TAX_ENRICHMENT_V1 Architecture Design Proof

## 1. Task identity and baseline

- Task: `FA_CONTACT_REGISTRY_SEARCH_QUALITY_AND_TAX_ENRICHMENT_V1`
- Date: 2026-07-18
- Classification: narrow corrective extension of the existing `add_contact` registry subflow; no new canonical action.
- Audited branch and HEAD: `main` at `692eebb89e17937f032d13f87e3e833bf700d472`.
- Protected dirty tree before this task: modified `PROJECT_LOG.md` and `tests/test_access_workspace_reactivation.py`; neither may be reset, discarded, or treated as clean-baseline evidence.
- Existing registry-contact runtime is part of the audited HEAD. No separate registry implementation files were visible as uncommitted changes.
- Current Product Truth: contacts are `partial`; official RPO lookup is disabled by default and optionally pilot-scoped. RPO supplies identity/address data. DIČ is currently typed and IČ DPH is never inferred.
- Target Product Truth, if implementation becomes authorized by evidence: RPO identity/address plus optional, disabled-by-default Financial Administration enrichment by the exact selected IČO. Missing, invalid, ambiguous, unavailable, or unconfigured tax data continues through typed DIČ.
- AI maturity: unchanged. Normalization, filtering, ranking, exact matching, provider mapping, validation, and merge decisions are deterministic Python. No LLM authority is added.

## 2. Preflight declaration

- Documents inspected for this amendment: the parent architecture proof and Conversation Acceptance Proof; current Product Doctrine, AI/Product Truth, self-learning, evaluation, UX, TZ, LLM registry/response, and InfoHelp contracts as applicable; current official RPO and Financial Administration documentation and official published tax-list artifacts.
- Runtime owners inspected: `bot/services/slovak_company_registry.py`, registry portions of `bot/handlers/contacts.py`, `bot/services/registry_contact_save.py`, `bot/services/validation.py`, `bot/config.py`, environment examples, and focused registry/contact tests.
- Touched scopes planned: deterministic routing inside `add_contact`, FSM detail transition, external read-only providers, configuration/secrets, Product Truth/InfoHelp wording, tests/evals, and bounded source metadata.
- Touched scopes excluded: LLM, STT, LMM, new canonical actions, DB schema/storage migration, PDF layout, server state, deployment, commercial data sources, scraping, and automatic writes.
- Current implementation status after the user-authorized evidence-independent slice: deterministic RPO exact/soft ranking is implemented locally; the tax HTTP/provider/aggregation boundary is implemented and fake-tested, but production tax mapping remains fail-closed and `requires_external_credentials` pending exact API metadata evidence.
- Proof journey: exact `Zevs s.r.o.` suppresses four weak surname/substring candidates and loads one RPO detail; exact-IČO tax enrichment adds only validated official DIČ/IČ DPH; save remains confirmation-gated with zero prior DB writes.
- Self-learning: considered and rejected for this slice. Company-name normalization and ranking must remain deterministic and global; no learned aliases or raw queries are stored.
- User-facing claims must be backed by current code/tests plus the `contacts` Product Truth entry, focused docs/evals, and official provider documentation.

## 3. Current implementation audit

### RPO query and result processing

- Eight-digit input uses RPO `/search` with `identifier=<IČO>` and `onlyActive=true`.
- Name input passes `normalize_company_search_name()` to RPO `fullName`; the current function case-folds, removes diacritics/punctuation, tokenizes, and strips selected legal suffixes.
- Candidate mapping reads current `fullNames`, `identifiers`, and `addresses`; termination presence maps to inactive.
- Current ranking recognizes exact normalized core name, token-prefix, and all-whole-token containment, then truncates to the configured maximum.
- Current ranking does not filter weak rows. Consequently a provider substring such as `zevs` inside `klimaszevska` can remain visible even though it receives no whole-token score.
- Search currently asks `onlyActive=true`, so inactive ordering cannot be implemented or tested without deliberately changing the provider query. The corrective slice should keep this current active-only query unless exact-IČO/name historical behavior is separately approved from official semantics.

### FSM and enrichment

- One mapped search result immediately invokes RPO detail loading and enters `registry_detail_preview`; multiple results enter `registry_candidates`.
- Detail mapping deliberately sets `dic=None` and `ic_dph=None` and identifies only `slovak_rpo`.
- `supplement` enters `registry_required_dic` when validated DIČ is absent; otherwise it advances to optional email.
- Final save revalidates actor/workspace and contact fields and writes only after the shared `yes_no` decision.
- Callback replay after state transition is fail-closed. Tax lookup must be attached to the one detail-loading owner so replay/final confirmation cannot invoke it.
- Source persistence is already bounded: `source_type='registry'`; `source_note` is the bounded, deduplicated provider-source tuple. No schema migration is required to store `slovak_rpo+financna_sprava` semantics.

### Configuration and secret handling

- Existing registry configuration follows frozen `Config` fields plus bounded environment parsing.
- RPO timeout is positive and capped at 30 seconds; maximum results are bounded.
- The proposed tax settings fit the same pattern: disabled by default, nullable stripped key, positive timeout capped at 30 seconds, fixed production base URL in code, and constructor-level client/base injection only for tests.
- No current Financial Administration key was present in the process environment, `.env`, or `faktura.env` during the audit. Secret values were not printed.

## 4. Official RPO evidence verified

- Current official Statistics Office page was last updated 2026-06-10 and states that access is free and requires no registration.
- The official page points to the RPO Apiary technical documentation and production base `https://api.statistics.sk/rpo/v1/`.
- The current implementation and the already accepted parent proof use `/search`, `identifier`, `fullName`, `onlyActive`, and `/entity/{id}`; the parent proof records a successful live read-only shape audit on 2026-07-17.
- The corrective search algorithm must not depend on undocumented RPO ordering or substring relevance. It must map all bounded returned rows, compute local deterministic relevance, reject weak rows, and only then truncate.

## 5. Search-quality architecture amendment

### Canonical representations

Create a frozen deterministic representation containing at least:

```text
normalized_full
normalized_core
full_tokens
core_tokens
legal_suffix
```

Normalization rules:

1. Unicode case-fold and remove combining marks for matching only; retain official display text unchanged.
2. Replace commas and ordinary punctuation with token boundaries; collapse repeated whitespace.
3. Recognize only an explicit suffix table, including defensible Slovak variants of `s. r. o.`, `s.r.o.`, `sro`, `spol. s r. o.`, and `a. s.`/`as` already covered by the parent implementation.
4. `normalized_full` retains a canonical legal-suffix token, so `Zevs s.r.o.`, `Zevs s. r. o.`, and `zevs sro` share a defensible full representation.
5. `normalized_core` removes one recognized trailing legal suffix. It never removes letters from the middle of a token.
6. `ZE VS` remains two core tokens and is never an exact identity match for `ZEVS`; compact equality may surface `Zevs` only as a suggestion requiring explicit selection.

### Deterministic rank and filter

For each mapped candidate compute a match class before sorting:

1. exact IČO when the query is eight digits;
2. exact normalized full name;
3. exact normalized core name;
4. exact complete core-token sequence;
5. all meaningful query tokens present as whole candidate core tokens;
6. bounded partial match passing an explicit threshold;
7. inactive after active except for an exact identity match, if inactive querying is later approved.

The partial threshold is dependency-free and explicit. It accepts compact core equality as suggestion-only, one edit for compact names of at least five characters, whole-token containment, and bounded token prefix/suffix coverage. Thus `Empbau` may suggest both `Empebau` and `Empe bau`, while `ZE VS` may suggest `Zevs`. Pure internal substring matches such as `zevs` inside `klimaszevska` receive no score. Suggested matches never auto-select, even when only one remains.

Exact-result collapse:

- If exactly one active candidate matches exact normalized full or exact normalized core name, return only it, even if weak provider rows precede it.
- If multiple active candidates share that exact normalized name, return all exact matches only and require selection with name, IČO, and municipality.
- If no exact match exists, retain only above-threshold rows, sort deterministically, and truncate to `CONTACT_REGISTRY_MAX_RESULTS`.
- If no rows pass, return the existing no-result/manual/PDF fallback.
- An exact eight-digit IČO result remains a single exact identity result.

This produces the required `Zevs s.r.o.` outcome while preserving bounded useful `bau` matches whose names contain `bau` as a complete token or defensible prefix token. `Klimaszevská` never receives exact or whole-token credit for query token `zevs`.

## 6. Official Financial Administration evidence verified

### API contract and authenticated metadata verified

- Official Information Lists API documentation reports version `1.2.1`.
- Fixed production base: `https://iz.opendata.financnasprava.sk/api`.
- Authentication: API key in request header named exactly `key`.
- Standard rate limit: 1,000 requests/hour.
- Generic endpoints: `GET /lists`, `GET /lists/{slug}`, `GET /data/{slug}`, and `GET /data/{slug}/search`.
- Search parameters documented by the current OpenAPI file: required path `slug`; required query `page` (integer, default 1), `column` (string), and `search` (string, minimum length 5).
- Generic response envelope fields: `page`, `pages`, `itemsCount`, `itemsPerPage`, and `data` array.
- Documented endpoint statuses include 200; 400/404 for invalid/missing list/search/page; and 503 while a list is updating. An initial 401 was traced to a one-character Windows-to-SSH secret-transfer corruption; after exact-byte replacement, authenticated metadata and search calls returned 200.

### Official list content verified from current published exports

- Income-tax registered entities are published daily at official artifact `ds_dsrdp.zip`. Its XSD/XML fields are `DIC`, `ICO`, `NAZOV_DS`, `OBEC`, `PSC`, `ULICA_CISLO`, and `NAZOV_STATU`; authenticated API metadata reported update `2026-07-18 05:01:16`.
- DPH-registered entities are published daily at official artifact `ds_dphs.zip`. Its XSD/XML fields are `IC_DPH`, `ICO`, `NAZOV_DS`, `OBEC`, `PSC`, `ULICA_CISLO`, `STAT`, `DRUH_REG_DPH`, `DATUM_REG`, optional `DATUM_ZMENY_DRUHU_REG`, and optional `PLAT_DPH_OD`; authenticated API metadata reported update `2026-07-18 05:00:02`.
- The current DPH export directly supplies `IC_DPH`; `SK + DIČ` inference is forbidden and unnecessary.
- The current DPH export contains different registration kinds and optional effective/change fields. Presence alone does not prove ordinary payer status, and absence alone must not be rendered as an authoritative non-VAT claim without exact approved list semantics.

### Key-authenticated schema evidence recorded on 2026-07-18

- Corrected exact-byte key transfer produced authenticated `GET /api/lists` status 200; the key remained secret and no response body containing taxpayer rows was logged.
- Income list: `slug=ds_dsrdp`, `searchable=ico`; detail metadata confirmed the same slug/searchable pair.
- DPH list: `slug=ds_dphs`, `searchable=ic_dph,ico`; detail metadata confirmed the same slug/searchable pair.
- Exact income search by IČO returned envelope keys `page,pages,itemsCount,itemsPerPage,data`, one exact row, and row keys `dic,ico,id,nazov_ds,nazov_statu,obec,psc,ulica_cislo`; DIČ was a validated 10-digit value.
- Exact DPH search by a selected official list IČO returned the same envelope, one exact row, and row keys `datum_reg,datum_zmeny_druhu_reg,druh_reg_dph,ic_dph,ico,id,nazov_ds,obec,plat_dph_od,psc,stat,ulica_cislo`; IČ DPH was directly returned as `SK` plus 10 digits.
- Exact searches used `page=1,column=ico,search=<eight-digit-IČO>` and returned `pages=1,itemsPerPage=1000` for observed matches.
- No-result exact IČO searches returned 404 for both `ds_dsrdp` and `ds_dphs`; the provider already maps 404 to an empty result.
- DPH page 1 reported `315` pages, `314204` items, and 1000 rows. Its first 1000 rows contained 1000 distinct searchable IČOs and no observed duplicate-IČO group.
- Multiple/conflicting exact-IČO rows remain fail-closed by deterministic code/tests; they were not manufactured against the live provider.

## 7. Implemented tax-provider boundary and verified production mapping

The local slice adds a separate provider and aggregation owner. `verified_financna_sprava_schema()` now binds only the audited lowercase API fields and exact official slugs:

```python
@dataclass(frozen=True)
class TaxRegistryDetails:
    ico: str
    dic: str | None
    ic_dph: str | None
    is_vat_registered: bool | None
    source_ids: tuple[str, ...]

class SlovakTaxRegistry:
    async def lookup_by_ico(self, ico: str) -> TaxRegistryDetails | None:
        ...
```

Required mapping remains:

- Query only by the exact selected eight-digit RPO IČO, never by company name.
- Normalize and compare every returned IČO exactly.
- Validate DIČ with the current project validator and IČ DPH with the current project validator.
- Never fabricate either value and never generate `SK + DIČ`.
- Treat conflicting distinct validated values for the same exact IČO as `tax_registry_conflict` and return no enrichment.
- Treat no exact IČO row as no enrichment, not a name match.
- Do not claim non-VAT status unless the audited current-list semantics justify it; otherwise `is_vat_registered=None` and `ic_dph=None`.
- Make at most one income-list search and one DPH-list search per selected IČO. No candidate-list, replay, final-confirmation, or DB-save calls.

Implemented owners: `bot/services/slovak_tax_registry.py` and the detail aggregation factory in `bot/handlers/contacts.py`. Automated tests use injected fake list specs and no internet. The fixed production client is not constructed while the verified schema is absent, even if a key is present.
- Merge validated values into the unsaved RPO draft. Preserve RPO preview and enter typed DIČ on disabled/not-configured/failure/ambiguity/invalid/no-result outcomes.
- Store no raw response. Persist only existing bounded source metadata: `source_type=registry`, provider sources equivalent to `slovak_rpo` plus `financna_sprava` when at least one validated tax field is used.

External request owner must use asynchronous HTTP, separate bounded connect/read timeout within a total maximum of 30 seconds, bounded response bytes, explicit status mapping, safe JSON/schema validation, no retries, no raw response logging, and bounded codes: `tax_registry_disabled`, `tax_registry_not_configured`, `tax_registry_unauthorized`, `tax_registry_rate_limited`, `tax_registry_unavailable`, `tax_registry_malformed`, and `tax_registry_conflict`. The key must never be incorporated into exception text or state.

## 8. FSM and side-effect amendment

```text
registry search
  -> one exact candidate -> RPO detail GET
       -> optional tax aggregation by selected exact IČO
            validated DIČ -> combined preview; required-DIČ state skipped
            no/invalid/ambiguous/unavailable tax data -> RPO preview; typed DIČ retained
  -> several exact candidates -> bounded candidate selection
  -> bounded relevant non-exact candidates -> bounded candidate selection
  -> no relevant candidates -> existing manual/PDF fallback
```

- The aggregation call belongs only in the detail-loading owner after actor/workspace and selected subject validation.
- Candidate display performs no tax request.
- The draft remains FSM-only until explicit final confirmation.
- Callback replay cannot repeat detail/tax lookup because the state no longer accepts a candidate callback after successful consumption.
- Wrong actor/workspace/profile must fail before tax lookup.
- Tax failure must not clear selected RPO identity/address or terminate contact creation.

## 9. Configuration implemented, disabled by default

```text
CONTACT_TAX_LOOKUP_ENABLED=0
FINANCNA_SPRAVA_API_KEY=
FINANCNA_SPRAVA_TIMEOUT_SECONDS=5
```

- Disabled by default; existing registry flag and pilot gate remain parents.
- Missing key disables tax enrichment only.
- Timeout is positive and at most 30 seconds.
- Production base is a code constant, not an unrestricted environment variable.
- Tests may inject a fake base/client without network.
- The API key is never logged, persisted, previewed, placed in callbacks/FSM, or included in examples.

## 10. Tests and acceptance required after evidence completion

Implementation must add the complete search-quality, tax-provider, FSM, zero-write, replay/idempotency, access/workspace, manual/PDF, and full regression matrix specified by the task. All automated tests use fakes; normal tests make no internet calls.

The focused Conversation Acceptance Proof must record at least:

1. Five-row observed Zevs provider response collapses to the single exact active company and opens detail with zero DB writes.
2. Exact-IČO validated DIČ enrichment skips typed DIČ and still requires final confirmation.
3. Tax timeout retains RPO draft and enters typed DIČ.
4. Income DIČ plus no exact current DPH row leaves IČ DPH null and makes no VAT-status overclaim.
5. Two exact active names require selection and display IČO/municipality.

No live tax API assertions belong in automated tests. The bounded read-only key-authenticated schema smoke is recorded above; automated tests remain fake-only and deterministic.

## 11. Migration, deployment, and negative space

- No DB schema or storage migration is designed or required.
- Existing same-IČO merge, optional local-field preservation, same-name/different-IČO conflict, split conflict, and invoice-reference rules remain unchanged.
- Manual contact creation, PDF/document intake, voice precision exclusions, active-FSM ownership, shared DecisionResolver, tenant isolation, and unauthorized-user external-call prohibition remain unchanged.
- No commercial scraping, background sync, automatic contact creation, production write, migration, restart, deployment, commit, or push belongs to this task.
- Deployment remains separately gated by production schema/data audit, backup/rollback, flags/pilot configuration, bounded server runtime smoke, controlled Telegram acceptance, and explicit deployment approval.

## 12. Evidence resolution and residual limits

The authorized read-only audit completed the mandatory mapping evidence without exposing the key or raw taxpayer values:

1. `GET /api/lists` and both `GET /api/lists/{slug}` calls confirmed exact names, slugs, searchable fields, and update timestamps.
2. Exact-IČO searches confirmed lowercase JSON field names for `ico`, `dic`, and `ic_dph` plus the full observed row-key sets.
3. Matching searches confirmed page-one/single-page behavior and `itemsPerPage=1000`.
4. No-result searches confirmed HTTP 404 for both approved lists.
5. A current DPH row confirmed IČ DPH is supplied directly; no DIČ-derived construction is needed or allowed.

Residual limitations:

- no duplicate/historical exact-IČO group was observed in the bounded live sample, so conflicting rows remain fake-tested and fail closed;
- 403, 429, timeout, 5xx, malformed JSON, oversized body, and unexpected schema behavior remain fake-tested from the documented contract rather than intentionally triggered live;
- official lists can update or be temporarily unavailable, so manual DIČ fallback remains mandatory.

These residual limits do not require guessed mappings and do not block implementation handoff. They continue to block any claim of `safe_to_deploy` without the separate deployment gates.

ready_for_handoff
