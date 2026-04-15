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

`edit_invoice` is currently a **reserved top-level action token**.
Phase 1 contract for this token includes only planned bounded item edit behavior as an in-action subflow (`upraviť položku`) inside invoice edit flow, not as a separate top-level action.

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

## 6.1) Planned Phase 1 in-action item edit contract (`upraviť položku`)

Scope contract (docs-first):
- `upraviť položku` is **in-action / subflow** under future `edit_invoice` flow;
- it is **not** a standalone top-level action;
- it is **not** add-item behavior.

Canonical machine-facing operation set for this subflow:
- `replace_service`
- `edit_item_description`
- `unknown`

Operation meaning (human-readable):

1. **`replace_service`**
   - replaces item service identity (canonical service term),
   - may update short service name where applicable,
   - resolves full display title from service alias/service dictionary.

2. **`edit_item_description`**
   - updates only `item_description_raw`,
   - this field is manual free text,
   - this field is not canonical alias and does not mutate service dictionary,
   - must support description mutation modes: `set`, `replace`, `clear`.

Precision and voice-input rule for `item_description_raw`:
- this field is precision-sensitive and text-first in Phase 1;
- voice must not be used for free guessing long detail into stored value;
- when user is in this precision-sensitive step via voice, bot asks bounded Slovak prompt to provide text input.

Future-ready item targeting contract:
- item edit is item-targeted by design;
- current single-item draft may default to first item;
- future multi-item invoices require explicit item selection or bounded clarification (e.g., by ordinal/index, with possible later internal stable identifier mapping in Python).

PDF/render contract linkage:
- main service title is sourced from canonical service alias/service DB resolution;
- optional `item_description_raw` is rendered below the main title;
- rendered detail is limited to max 2 lines;
- if text does not fit, bot must not silently truncate and must ask user (Slovak bounded prompt) to shorten it.

Minimal bounded output shape for `edit_invoice:item_edit`:

```json
{
  "target_item_index": "<integer_like_or_unknown>",
  "operation": "replace_service|edit_item_description|unknown",
  "value": "<candidate_value_or_unknown>"
}
```

Notes:
- `target_item_index` is mandatory at contract level (single-item runtime may default to first item for now).
- For `replace_service`, `value` carries bounded service candidate later validated/resolved by Python.
- For `edit_item_description`, `value` carries text candidate; clear semantics are explicit via empty/null value or explicit clear intent resolved by Python validation.
- For unresolved mapping, operation/value fallback is `unknown`.

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
