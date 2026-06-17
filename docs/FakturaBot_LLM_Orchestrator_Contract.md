# FakturaBot LLM Orchestrator Contract

**Document role:** source-of-truth AI orchestration contract for FakturaBot.

This contract defines **Bounded Semantic Canonicalization** via the **Semantic Action Resolver** pattern.

OfficeFlow note: this contract currently applies to the FakturaBot / outgoing invoices module. Future OfficeFlow modules, including Document Intake, must define their own bounded action/value contracts before runtime implementation. This document does not add expenses, bank statement, OCR, or general document-intake runtime actions.

---

## 1) Authority split: Python vs LLM

### Python (source of truth and execution authority)
Python always defines and owns:
- current workflow context / FSM state,
- allowed canonical outputs for this конкретний крок,
- validation and invariant checks,
- all side effects (DB, files, FSM updates, invoice numbering, PDF/email/send flow),
- fail-loud behavior on invalid context/invalid output.

### LLM (bounded semantic canonicalizer)
LLM only resolves noisy input into one canonical value from Python-provided bounds.

LLM output is strictly:
- one allowed canonical output, or
- `unknown`.

LLM never executes actions directly.

### Authorization and tenant boundary

Python authorization and tenant scoping must happen before any LLM/STT/LMM call.

Rules for the controlled multi-user dry run:
- Telegram users must be authorized by Python before user-facing handlers invoke semantic resolution, STT, or document LMM extraction.
- Authorization means either static bootstrap membership in `ALLOWED_TELEGRAM_USER_IDS` or an active row in `authorized_users`.
- Unknown `/start` may create only a minimal access request for administrator review; it must not call LLM/STT/LMM or create supplier/contact/invoice/accounting-document state.
- Admin access commands (`/access_requests`, `/approve`, `/reject`, `/block`, `/users`) are deterministic Python commands and must not call LLM/STT/LMM.
- LLM must not decide authorization.
- LLM must not decide tenant identity.
- LLM must not receive another tenant's stored data.
- DB filtering, invoice-number generation, file-path generation, duplicate checks, and persistence decisions remain deterministic Python logic scoped by `telegram_id` / `supplier_telegram_id`.

### STT transcription context

The STT layer may receive a compact transcription prompt that describes the expected language and product domain for raw Telegram voice messages.

This prompt is only transcription context. It may say that speech can be Slovak, Ukrainian, Russian, English, mixed-language, colloquial, or STT-noisy, and that the domain is Slovak invoicing/accounting for FakturaBot / OfficeFlow.

The STT prompt must not:
- list canonical action tokens as an execution contract;
- decide routing or confirmation outcomes;
- translate, summarize, or rewrite the user request into a command;
- bypass Python authorization, FSM state, bounded resolver validation, or confirmation rules.

After STT, the transcript still flows through the same Python-owned state routing, Canonical DecisionResolver, or bounded Semantic Action Resolver as normal text input.

---

## 2) Bounded Semantic Canonicalization

**Bounded Semantic Canonicalization** means:
1. Python provides context and allowed outputs.
2. LLM maps multilingual/noisy/STT-distorted input to one allowed canonical output.
3. If mapping is unclear, LLM returns `unknown`.
4. Python validates canonical output against current context.
5. Python executes (or fails loud).

No free-form intent execution is allowed.

---

## 3) Canonical action resolution

The same resolver pattern applies to top-level actions.

Example allowed actions (defined by Python per turn):
- `start`
- `create_invoice`
- `add_contact`
- `show_supplier_profile`
- `show_existing_invoice`
- `invoice_period_summary`
- `invoice_analytics`
- `edit_supplier`
- `show_recent_accounting_documents`
- `add_receipt`
- `send_invoice`
- `edit_invoice`
- `edit_existing_invoice`
- `delete_user_database`

LLM must return one of allowed actions or `unknown`.

`edit_invoice` remains a **reserved top-level action token**.
Runtime editing is defined as bounded in-action/subflow operations under invoice flow (`upraviť`), not as a separate top-level executor.
`show_existing_invoice` is an explicit read-only top-level action for viewing an already created/persisted invoice by number reference; Python performs supplier-scoped lookup, sends summary/PDF when available, clears FSM state, and must not enter edit mode or mutate invoice rows/PDFs.
`invoice_period_summary` is an explicit read-only top-level action for answering yearly summary questions over already saved outgoing invoices. LLM/resolver may only select the canonical token when Python includes it in `allowed_actions`; Python parses the supported year period, filters by the current `supplier_telegram_id`, groups totals by currency, renders the answer, clears FSM state, and must not create/edit/delete invoices, generate PDFs, or summarize receipts/incoming invoices.
`invoice_analytics` is a partial read-only top-level pilot for broader questions over already saved outgoing invoices, such as counts, sums, customer/normalized-payment-status/month grouping, period comparisons, and bounded matching lists. Python filters the current supplier's invoice rows, exposes only a sanitized dataframe, injects the current runtime date, derives bot payment state from follow-up state plus due dates, validates any LLM-generated analysis code, and executes it in a timeout-killed child process without DB/file/network/write access. LLM must not run SQL, inspect storage paths, treat raw invoice lifecycle status as payment truth, mutate invoice state, claim bank-confirmed settlement, claim receipt/incoming-invoice/bank/tax/accounting analytics, or replace the supported deterministic `invoice_period_summary` path.
`edit_existing_invoice` is an explicit top-level action for editing an already created/persisted invoice by number reference; LLM only resolves intent + reference text, Python performs DB lookup with supplier scope and ambiguity handling.

OfficeFlow/Document Intake actions may be top-level only when explicitly registered and backed by Python-owned runtime validation. Current bounded top-level accounting actions are limited to the existing recent-documents view and the existing upload-waiting intake starter. Voice/text `add_receipt` starts the upload FSM and asks for a photo/PDF; it must not create an invoice, extract a receipt, or save accounting metadata from voice content alone. Future actions for contracts archive, bank statements, categories, or manual accounting-document editing must be introduced docs-first in the relevant registry and then implemented only after Python-side validation/storage contracts are defined.

---

## 4) Optional semantic action hints for ambiguous actions

Some canonical actions are semantically ambiguous in multilingual/noisy user input.
For such actions, Python may provide optional compact `action_hints` in resolver context.

Rules:
- hints are **optional** (not required for every action),
- use them selectively when plain allowed-actions list is not stable enough,
- hints are contextual guidance for bounded resolution, not ontology and not keyword-parser replacement.

Reference ambiguous action:
- `add_service_alias` is implemented as a user-facing top-level action through `/sluzbu` plus semantic text/voice invoke. The runtime starts the existing service-alias FSM. Its precision-sensitive alias/display-name values remain text-only.

Profile and data-management actions:
- `show_supplier_profile` is the user-facing `/moj_profil` profile surface for the user's own supplier/company/billing details in Slovak FakturaBot product semantics: `fakturačné údaje dodávateľa`, `firemné údaje`, invoice issuer details, identifiers, address, and payment details; if no supplier profile exists it starts supplier profile creation.
- `edit_supplier` is the targeted `/upravit_profil` flow for changing supplier/company/billing details after Python validation and shared confirmation.
- `delete_user_database` is implemented for full user database deletion/leaving FakturaBot. User-facing examples include `/vymazat_databazu` and voice/text phrases such as `Chcem vymazať moju databázu`. Resolver/LLM may only classify the top-level entry intent when Python includes `delete_user_database` in `allowed_actions`; final deletion is Python/FSM-owned and requires the exact typed confirmation `vymazať databázu`. Voice must not pass the final confirmation.

Hint fields:
- `meaning`
- optional `positive_examples`
- optional `not_this`

---

## 5) Canonical in-state reply resolution

The same resolver pattern applies inside FSM states.

Examples:
- preview draft-review state allowed replies: `schvalit`, `upravit`, `zrusit`, `unknown`
- post-PDF state allowed replies: `schvalit`, `upravit`, `zrusit`

Even when LLM resolves `schvalit` / `upravit` / `zrusit`, Python still validates state and performs execution.

Project-level decision policy is maintained in `docs/Canonical_Decision_Resolver_Contract.md`.
The required migration target is one shared Canonical DecisionResolver for confirmation-like replies.
Phase 1 runtime now exposes the shared wrapper in `bot/services/decision_resolver.py` and routes the current invoice, contact, onboarding, and existing-invoice delete confirmation flows through it.
This does not add OfficeFlow Document Intake runtime actions or Telegram button/callback handling.

Implementation gate:
- `docs/Canonical_Decision_Resolver_Contract.md` is mandatory for new actions and subflows.
- Any reply that means confirm/reject/approve/edit/cancel/save/delete/route must go through `bot/services/decision_resolver.py`.
- New handlers must not parse raw confirmation words locally.
- New resolver work must extend or reuse a bounded decision family, not introduce per-flow synonym lists.
- Python handlers may branch only on canonical decision outputs.

Decision families:
- `approve_edit_cancel` -> `approve` / `edit` / `cancel` / `unknown`
- `yes_no` -> `yes` / `no` / `unknown`
- `attachment_route_choice` -> `create_contact` / `save_contract` / `cancel` / `unknown`
- `attachment_document_type_choice` -> `receipt` / `incoming_invoice` / `contract` / `contact_source` / `cancel` / `unknown`

Existing machine tokens such as `schvalit`, `upravit`, `zrusit`, `ano`, and `nie` remain current runtime compatibility vocabulary where already used. New confirmation-like flows should not add per-module local parsers and should converge text, voice transcript, and future Telegram button/callback input into the same canonical decision path.

Current Phase 2 voice-control boundary:
- top-level user-facing actions with runtime routes should be voice-reachable unless explicitly documented otherwise;
- active FSM state wins over idle top-level routing;
- voice may choose bounded actions, fields, items, routes, document types, and confirmation options;
- precision-sensitive exact values remain text/file-only, including invoice numbers, item numeric values, IBAN, IČO, DIČ, IČ DPH, email, final item descriptions, service alias names, and exact destructive confirmations.

Confirmed alias learning for noisy semantic values is governed by `docs/Confirmed_Semantic_Alias_Learning_Contract.md`. The same authority split applies: AI/STT may produce only a bounded candidate, Python must validate against scoped local targets, and only a confirmed cleaned candidate may be stored as an alias. Confirmation may be an explicit DecisionResolver confirmation or approval of a workflow preview where the resolved target is visibly shown.

Preview backward-compatible aliases:
- `ano` maps to `schvalit`;
- `nie` maps to `zrusit`.

Preview decision semantics:
- `schvalit` means final approval: Python validates the proposed invoice number, creates the final invoice row, assigns the final number, and generates PDF.
- `upravit` means draft edit: Python mutates FSM `invoice_draft` only and returns an updated preview.
- `zrusit` means draft cancellation: Python clears FSM without DB invoice row creation and without PDF generation.

---

## 6) Canonical value resolution

The same resolver pattern applies to structured values/slots.

Example service/value canonicalization:
- `oprava`
- `revizia`
- `servis`

Python provides allowed canonical values for the field; LLM returns exactly one or `unknown`.

---

## 6.1) Planned full `edit_invoice` in-action/subflow map (`upraviť`)

Scope contract (docs-first):
- `edit_invoice` stays reserved as top-level canonical action token;
- runtime behavior is bounded in-action/subflow editing inside invoice flow;
- edit surface is split into **invoice-level** and **item-level** operation groups;
- add-item behavior remains out of scope.

### A) Invoice-level edit operations (mapped)

Canonical machine-facing operations:
- `edit_invoice_number`
- `edit_invoice_date`
- `edit_invoice_contact`

Status map:
- `edit_invoice_number` — **implemented** (bounded subflow runtime exists)
- `edit_invoice_date` — **implemented** (bounded subflow runtime exists, strict Phase 1 format `DD.MM.RRRR`)
- `edit_invoice_contact` — **planned (not yet implemented)**

Integrity/fail-safe rule:
- these operations are integrity-sensitive and must fail loud on invalid/ambiguous payload;
- Python must not silently auto-fix numbering/date/contact linkage mismatches.

### B) Item-level edit operations (mapped)

Canonical machine-facing operations:
- `replace_service`
- `edit_item_description`
- `edit_item_quantity`
- `edit_item_unit_price`
- `edit_item_total_amount`
- `unknown`

Status map:
- `replace_service` — **implemented** (bounded subflow runtime exists)
- `edit_item_description` — **implemented** (bounded subflow runtime exists)
- `edit_item_quantity` — **implemented** (bounded subflow runtime exists)
- `edit_item_unit_price` — **implemented** (bounded subflow runtime exists)
- `edit_item_total_amount` — **implemented** (bounded subflow runtime exists)

Operation meaning highlights:
1. **`replace_service`**
   - replaces item service identity (canonical service term),
   - may update short service name where applicable,
   - resolves full display title from service alias/service dictionary.

2. **`edit_item_description`**
   - updates only `item_description_raw`,
   - this field is manual free text,
   - this field is not canonical alias and does not mutate service dictionary,
   - supports description mutation modes: `set`, `replace`, `clear`.

3. **`edit_item_quantity` / `edit_item_unit_price` / `edit_item_total_amount`**
   - update only respective item numeric/unit fields,
   - must preserve invoice arithmetic invariants and fail loud on non-recoverable conflicts,
   - are precision-sensitive and text-first for final value capture where ambiguity risk is high.

### Item targeting and clarification contract

- Precision-sensitive item-level operations require item targeting by contract.
- Single-item invoices may default to first item target.
- Multi-item invoices require explicit item selection or bounded clarification.
- If target item or operation remains ambiguous, resolver output must be `unknown` and Python asks bounded clarification.

### Precision-sensitive input policy

- `item_description_raw`, `edit_item_quantity`, `edit_item_unit_price`, and `edit_item_total_amount` are precision-sensitive.
- For voice-originated ambiguous values, bot must switch to bounded Slovak text prompt before final persistence.
- No free guessing into stored precision fields.

### Destructive/integrity-sensitive edits

- Any destructive or integrity-sensitive edit must fail safe (halt this edit step + bounded user clarification).
- No silent truncation, no silent normalization that changes business meaning.

### Minimal bounded output shape for `edit_invoice:subflow`

```json
{
  "target_item_index": "<integer_like_or_unknown>",
  "operation": "edit_invoice_number|edit_invoice_date|edit_invoice_contact|replace_service|edit_item_description|edit_item_quantity|edit_item_unit_price|edit_item_total_amount|unknown",
  "value": "<candidate_value_or_unknown>"
}
```

Notes:
- `target_item_index` is mandatory for item-level operations (single-item runtime may default to first item).
- For invoice-level operations, `target_item_index` is `unknown`/ignored.
- `value` is always candidate-only; Python validates, enforces invariants, and executes or fails loud.
- Newly mapped operations in this section are docs-only and not runtime-implemented unless explicitly marked implemented above.

---

## 6.2) Planned `create_invoice` Phase 2 dual-shape intake contract (docs-first)

Scope contract (Phase 1 for future multi-item intake):
- add-item executor flow remains out of scope;
- this section defines only bounded intake/output contract evolution for `create_invoice`.

### A) Backward-compatible dual-shape rule

- Existing singleton item fields in `biznis_sk` remain valid and accepted.
- Optional bounded `biznis_sk.items[]` is added as candidate multi-item output.
- `items[]` is optional in Phase 1 and must not break legacy singleton payloads.
- Hard cutover to list-only contract is explicitly out of scope for this docs patch.

### B) LLM vs Python authority for item segmentation

- LLM may return bounded candidate segmentation into item candidates (`items[]`).
- LLM does not decide final acceptance/persistence and does not own side effects.
- For multilingual / mixed / noisy STT input, LLM first normalizes business meaning into Slovak draft semantics before filling the bounded invoice payload shape.
- LLM may also preserve optional raw/source mention fields from the original user/STT wording for later Python-validated alias learning:
  - `biznis_sk.odberatel_raw_mention`;
  - `biznis_sk.service_raw_mention`;
  - `biznis_sk.items[].service_raw_mention`.
- Raw/source mention fields are candidate trace fields only. They must not include the full invoice command, amount, date, invoice number, IBAN, email, phone, payment terms, or unrelated invoice data.
- LLM must not create aliases. Python may use a safe raw mention only after scoped lookup, preview display, and user approval/confirmation.
- LLM output must stay aligned to the exact Python intake structure expected by current invoice flow (`vstup`, `zamer`, `biznis_sk`, `stopa` and bounded `biznis_sk.items[]`).
- Python remains final validator/workflow owner:
  - validates item boundaries,
  - validates quantity/unit/unit_price/amount coherence per item,
  - validates invoice total coherence,
  - enforces bounded item count and render/page safety.
- Python execution outcomes:
  - accept and continue,
  - ask bounded clarification,
  - or safe fallback to compatible singleton path.

### C) Phase 1 strict bounds

- `items[]` maximum size: **3**.
- No open-ended extraction of arbitrary line-item count.
- If `items[]` exceeds bounds or contains unresolved ambiguity, Python must not silently truncate/merge.

### D) Candidate item shape (`biznis_sk.items[]`)

Each candidate item is machine-safe and bounded, with fields aligned to existing invoice terminology:
- optional `service_raw_mention` (source phrase from original/STT wording; not normalized and not persisted by this contract alone),
- `polozka_povodna` (service/raw item text candidate),
- `termin_sluzby_sk` (internal Slovak service term candidate),
- `mnozstvo`,
- `jednotka`,
- `cena_za_jednotku`,
- `suma`,
- optional future-compatible `item_description_raw` (detail candidate; optional in Phase 1).

This is a candidate extraction shape, not an execution command.

Invoice draft intake shape rule:
- raw user/STT wording may be SK/UA/RU/mixed/noisy,
- `vstup.povodny_text` preserves the original wording,
- `biznis_sk.*` must contain Slovak-normalized business meaning suitable for deterministic Python validation,
- `biznis_sk` fields must be filled only in the bounded machine-safe schema expected by Python runtime,
- LLM must not invent extra top-level fields or alternate output formats.

### E) Split semantics rules (contract examples)

- `montáž dva razy po 1000` => one item (`mnozstvo=2`, `cena_za_jednotku=1000`).
- `oprava 3000 a montáž 1000` => two candidate items.
- `oprava 3000, montáž 2x1000` => two candidate items (second item carries multiplier semantics).
- `polozka 1 oprava 3000, polozka 2 stavebne prace 1000` => two candidate items.
- `položka číslo 1 oprava 3000, položka číslo 2 stavebné práce 1000` => two candidate items.
- `друга положка oprava 3000, третя положка stavebni roboti 1000` => treat ordinal item markers as explicit candidate item boundaries and normalize item meaning to Slovak in `biznis_sk`.
- `позиция номер 1 ремонт 3000, позиция номер 2 монтаж 1000` => two candidate items with Slovak-normalized service terms in `biznis_sk`.
- If item boundaries or quantity semantics are ambiguous, Python must request bounded clarification (no silent guess).

### F) Fail-safe / clarification triggers for multi-item candidate intake

Python must not auto-accept multi-item candidate output when any of the following holds:
- ambiguous item boundaries;
- ambiguous quantity semantics;
- ambiguous service resolution for one or more items;
- inconsistent per-item or aggregate totals;
- render/page safety bounds exceeded.

In these cases Python asks bounded clarification or falls back safely; no destructive/silent correction.

### G) Runtime follow-up impact areas (not implemented here)

Future runtime patches must align this intake contract with:
- parser/validator,
- internal draft normalization (singleton auto-wrap to one-item list),
- preview formatting,
- PDF row rendering,
- total calculation and invariant checks,
- optional per-item detail (`item_description_raw`) rendering.

Status marker:
- Phase 1 runtime support is implemented with backward-compatible dual-shape intake.
- Legacy singleton remains supported; bounded `items[]` (max 3) is optional.
- Follow-up runtime scope remains: deeper ambiguity handling and future item-detail evolution.

---

## 7) Output format

Resolver output for each bounded resolution must be machine-safe and minimal:

```json
{
  "canonical": "<allowed_token_or_unknown>"
}
```

Rules:
- only one canonical token,
- token must be from Python-provided allowed set,
- fallback is `unknown`,
- no side-effect claims.

---

## 8) Safety and execution rule

Non-negotiable rule:
- **Python is the only execution authority.**

Therefore:
- LLM cannot create/update/delete records,
- LLM cannot mutate FSM directly,
- LLM cannot mark actions as completed,
- Python must fail loud on invalid context or disallowed canonical output.

---

## 9) Language policy

- User input may be multilingual, mixed, noisy, transliterated, or STT-distorted.
- User-facing bot replies remain Slovak-only.
- Raw transcript may be stored separately for trace/debug.
- Internal canonical outputs use project-defined canonical tokens only.

---

## 10) Design principle

Unified resolver principle for FakturaBot AI layer:
- one bounded semantic mechanism,
- reused for top-level action resolution,
- reused for in-state reply resolution,
- reused for value/slot canonicalization,
- with Python-owned validation and execution.

In short:

**Python defines bounds and executes. LLM canonicalizes within bounds.**

---

## 10.1) Shared OfficeFlow attachment classification contract

The shared OfficeFlow idle attachment classifier is a pre-router above accounting intake and contact/contract intake.

Strict routing rule:
- Active FSM state wins.
- If the user is already in `/doklad` upload state, the accounting intake handler owns the upload.
- If the user is in contact source/intake state, the contact flow owns the upload.
- The shared idle attachment classifier runs only when there is no active FSM state.

LMM contract:
- LMM classifies document type only.
- Allowed `document_type` values are `receipt`, `incoming_invoice`, `contract`, `contact_source`, and `unknown`.
- LMM must return strict JSON only: `document_type`, `confidence`, `reason`.
- LMM must not choose a final business action.
- LMM must not claim anything was saved, routed, confirmed, created, or executed.

Python contract:
- Python stages the original file in neutral temporary attachment staging.
- Python builds the classification bundle with idle state, allowed document types, routing hints, forbidden side effects, attachment metadata, and extracted PDF text when available.
- Python validates the classifier output.
- Python maps `document_type` to a bounded user-facing proposal.
- Python asks the user before any confirmed accounting save, contact creation, or contract save.
- Python remains the only workflow authority and the only component allowed to perform side effects after approval.

Slice status:
- Accounting proposal path can continue into the existing accounting document preview and confirmation flow.
- Contact-source path can continue into the existing contact draft preview and confirmation flow.
- Standalone `save_contract` is reserved until a separate contract-save approval/storage contract exists.

---

## 11) Registry linkage (audit discipline)

Action/resolver audit must be synchronized with:
- `docs/llm/Canonical_Action_Registry.md` (top-level + manual command flows + reserved placeholders),
- `docs/llm/In_Action_Response_Registry.md` (bounded in-action responses and slot/value groups).

Important:
- command-only manual flows are still implemented user-facing actions and must not be treated as absent only because they bypass semantic top-level resolver.
- explicit delete command flow maps to canonical action `delete_existing_invoice` and MUST require explicit user confirmation before any destructive action.
- `show_recent_accounting_documents` is implemented as the `/blocky` read-only command and deterministic idle text aliases. It lists only confirmed accounting Document Intake metadata under workspace/year/month expenses folders. It is not a broad document browser, not contract storage, not outgoing invoice PDF browsing, not temp upload access, not delete/edit/search, and not Google Drive sync. `/blocky` does not call LMM.

---

## 12) Slot-level clarification and partial draft retention

Slot-level clarification is mandatory for all structured workflows in this project.

Rules:
- one unresolved slot must not collapse the whole workflow when the rest of the draft is usable;
- Python must preserve partial draft/state for the current workflow step;
- bot asks only for the unresolved slot (Slovak user-facing prompt);
- user reply updates only that slot in preserved draft;
- continuation resumes from current workflow (no full restart from zero);
- full reset is reserved only for fatal errors (unusable payload structure, internal runtime failure, or impossible recovery path).

This is a project-wide contract, not invoice-only. The same behavior applies to existing and future structured flows.

