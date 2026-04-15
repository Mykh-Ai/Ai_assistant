# FakturaBot LLM Orchestrator Contract

**Document role:** source-of-truth AI orchestration contract for FakturaBot.

This contract defines **Bounded Semantic Canonicalization** via the **Semantic Action Resolver** pattern.

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
- `create_invoice`
- `add_contact`
- `send_invoice`
- `edit_invoice`

LLM must return one of allowed actions or `unknown`.

`edit_invoice` remains a **reserved top-level action token**.
Runtime editing is defined as bounded in-action/subflow operations under invoice flow (`upraviť`), not as a separate top-level executor.

---

## 4) Optional semantic action hints for ambiguous actions

Some canonical actions are semantically ambiguous in multilingual/noisy user input.
For such actions, Python may provide optional compact `action_hints` in resolver context.

Rules:
- hints are **optional** (not required for every action),
- use them selectively when plain allowed-actions list is not stable enough,
- hints are contextual guidance for bounded resolution, not ontology and not keyword-parser replacement.

Reference ambiguous action:
- `add_service_alias` (manual `/service` flow exists now; top-level semantic/voice invoke is future runtime work).

Hint fields:
- `meaning`
- optional `positive_examples`
- optional `not_this`

---

## 5) Canonical in-state reply resolution

The same resolver pattern applies inside FSM states.

Examples:
- preview state allowed replies: `ano`, `nie`
- post-PDF state allowed replies: `schvalit`, `upravit`, `zrusit`

Even when LLM resolves `schvalit` / `upravit` / `zrusit`, Python still validates state and performs execution.

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
- `edit_item_unit`
- `edit_item_unit_price`
- `unknown`

Status map:
- `replace_service` — **implemented** (bounded subflow runtime exists)
- `edit_item_description` — **implemented** (bounded subflow runtime exists)
- `edit_item_quantity` — **planned (not yet implemented)**
- `edit_item_unit` — **planned (not yet implemented)**
- `edit_item_unit_price` — **planned (not yet implemented)**

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

3. **`edit_item_quantity` / `edit_item_unit` / `edit_item_unit_price`**
   - update only respective item numeric/unit fields,
   - must preserve invoice arithmetic invariants and fail loud on non-recoverable conflicts,
   - are precision-sensitive and text-first for final value capture where ambiguity risk is high.

### Item targeting and clarification contract

- Precision-sensitive item-level operations require item targeting by contract.
- Single-item invoices may default to first item target.
- Multi-item invoices require explicit item selection or bounded clarification.
- If target item or operation remains ambiguous, resolver output must be `unknown` and Python asks bounded clarification.

### Precision-sensitive input policy

- `item_description_raw`, `edit_item_quantity`, `edit_item_unit`, and `edit_item_unit_price` are precision-sensitive.
- For voice-originated ambiguous values, bot must switch to bounded Slovak text prompt before final persistence.
- No free guessing into stored precision fields.

### Destructive/integrity-sensitive edits

- Any destructive or integrity-sensitive edit must fail safe (halt this edit step + bounded user clarification).
- No silent truncation, no silent normalization that changes business meaning.

### Minimal bounded output shape for `edit_invoice:subflow`

```json
{
  "target_item_index": "<integer_like_or_unknown>",
  "operation": "edit_invoice_number|edit_invoice_date|edit_invoice_contact|replace_service|edit_item_description|edit_item_quantity|edit_item_unit|edit_item_unit_price|unknown",
  "value": "<candidate_value_or_unknown>"
}
```

Notes:
- `target_item_index` is mandatory for item-level operations (single-item runtime may default to first item).
- For invoice-level operations, `target_item_index` is `unknown`/ignored.
- `value` is always candidate-only; Python validates, enforces invariants, and executes or fails loud.
- Newly mapped operations in this section are docs-only and not runtime-implemented unless explicitly marked implemented above.

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

## 11) Registry linkage (audit discipline)

Action/resolver audit must be synchronized with:
- `docs/llm/Canonical_Action_Registry.md` (top-level + manual command flows + reserved placeholders),
- `docs/llm/In_Action_Response_Registry.md` (bounded in-action responses and slot/value groups).

Important:
- command-only manual flows are still implemented user-facing actions and must not be treated as absent only because they bypass semantic top-level resolver.

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
