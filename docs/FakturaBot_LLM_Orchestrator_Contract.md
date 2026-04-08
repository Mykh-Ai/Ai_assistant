# FakturaBot LLM Orchestrator Contract (Draft)

**Document role:** detailed LLM/orchestrator contract document for Phase 2 AI behavior (boundary, schema/payload rules, prompt constraints, examples, failure rules).  
Rollout order, phase scope, and implementation sequencing are defined in `docs/FakturaBot_Canonicalization_and_SK_AI_Implementation_Plan.md`.

## 1) Runtime context extracted from current repository

This contract is intentionally grounded in what is already implemented.

### 1.1 Runtime and stack

- **Python runtime (conservative statement):**
  - **Container baseline:** Python **3.11** (`Dockerfile`: `python:3.11-slim`).
  - **Observed local runtime in current review cycle:** Python **3.12**.
  - Therefore, treat runtime expectation as **Python 3.11+**, with 3.11 guaranteed in Docker and 3.12 possible in local runs.  
- **Telegram framework:** `aiogram` 3.x, async handler architecture.  
- **LLM/STT client:** OpenAI Python SDK (`openai>=1.30,<2.0`) with:
  - STT model from config (`OPENAI_STT_MODEL`, default `whisper-1`),
  - LLM model from config (`OPENAI_LLM_MODEL`, default `gpt-4o`).
- **Persistence/storage:**
  - SQLite DB (`DB_PATH`, default `storage/fakturabot.db`),
  - local file storage `storage/` (`invoices/`, `contracts/`, `uploads/`).

### 1.2 Where Python is source of truth (already implemented)

Python currently remains authoritative for:

- user/session orchestration (FSM states in handlers),
- supplier/contact existence checks in local DB,
- alias resolution of services (`ServiceAliasService`),
- date defaults and due-date calculation,
- numeric parsing and minimal field validation,
- invoice saving and numbering,
- PDF generation and file persistence,
- final commit of data only after explicit user confirmation (`ano`).

### 1.3 Where LLM is currently allowed to help

Current implemented LLM role in repo:

- parse invoice draft text (including STT output) into structured fields via JSON,
- no autonomous side effects,
- no DB writes,
- no final validation authority.

### 1.4 Current capability boundaries that must be explicit

- Invoice parsing flow exists and is active (`/invoice` + voice path).  
- Manual supplier/contact onboarding exists and is deterministic.  
- Contracts handler is currently a **placeholder** (`Phase 0 placeholder`), so document/contact extraction from files is not yet an active runtime flow.

---

## 2) Supported input language policy

The orchestrator must accept and normalize user input in:

1. **Slovak**
2. **Ukrainian**
3. **Russian**
4. **Mixed-language input** (any combination of SK/UA/RU in one message)
5. **STT/noisy/transliterated input** (partial misspellings, latin transliteration, clipped grammar)

Policy rules:

- Do not reject input by language.
- Preserve user meaning even if grammar is broken.
- Keep entity extraction tolerant to:
  - decimal separators (`,` and `.`),
  - inflected names,
  - short/colloquial service names,
  - STT artifacts (missing diacritics, merged words, phonetic spelling).
- When uncertain, return ambiguity/clarification requests, not guessed facts.

### 2.1 User-facing language policy (separate layers)

To avoid mixing concerns, language policy is split into three layers:

1. **Input handling language:** SK/UA/RU/mixed/noisy transliteration accepted (this section).
2. **Internal machine contract language:** output JSON keys and enum values are always **English**.
3. **Bot reply language strategy:** user-facing clarification/confirmation text should follow the user’s latest message language when reliably detectable; otherwise fall back to Slovak default bot UX wording already used in handlers.

---

## 3) Output contract (strict)

The orchestrator output must be:

- **JSON only**,
- **English keys only**,
- **no prose outside JSON**,
- deterministic, action-plan-style for Python execution.

Hard rules:

- No markdown, no code fences, no commentary.
- Unknown or absent values must be explicit `null`.
- If multiple plausible interpretations exist, include them in `ambiguities` and request clarification in `action_plan`.
- Never claim side effects were executed.

### 3.1 Contact lookup state contract (Python-side, post-LLM)

LLM does not decide contact identity truth. After LLM extraction of `customer_name`, Python must run DB lookup and expose one of these states:

- `exact_match` — exact string match found.
- `normalized_match` — non-exact but deterministic normalized/case-insensitive match found.
- `multiple_candidates` — more than one plausible contact candidate.
- `no_match` — no contact found.

Rules:

- `no_match` must **not** be auto-converted into “add new contact” by orchestrator default behavior.
- `multiple_candidates` must trigger clarification/selection flow, not silent auto-pick.
- Only Python lookup result can promote contact status to resolved.

---

## 4) Strict LLM/Python responsibility boundary

### LLM responsibilities

- detect user intent,
- extract candidate entities from free text,
- mark uncertainty,
- produce deterministic JSON plan for Python.

### Python responsibilities (source of truth)

- resolve contacts/services against local DB,
- validate business and format constraints,
- apply defaults (dates, due days, etc.),
- ask user confirmation,
- save/update records,
- generate PDF/QR,
- send email (optional capability; depends on SMTP completeness and flow readiness),
- define final truth in storage/state.

**Non-negotiable principle:** LLM output is a draft hypothesis; Python+user confirmation decides truth.

### 4.1 Explicit Python actions/tools contract (expected callable layer)

This section defines concrete Python-side callable actions expected by the orchestrator contract (whether direct function call, dispatcher command, or handler entrypoint):

- `route_invoice_flow(input_text)` → enters `/invoice` processing path.
- `route_voice_invoice_flow(stt_text)` → same invoice path via voice/STT handoff.
- `lookup_contact_by_name(telegram_id, customer_name)` → returns lookup state (`exact_match | normalized_match | multiple_candidates | no_match`) and candidates.
- `route_contact_onboarding()` → enters `/contact` manual flow.
- `route_supplier_onboarding()` → enters `/supplier` onboarding flow.
- `route_service_alias_flow()` → enters `/service` alias mapping flow.
- `resolve_service_alias(supplier_id, item_name_raw)` → deterministic alias→canonical resolution in Python.
- `create_invoice_draft_preview(...)` → Python validation/defaulting + preview object.
- `confirm_and_save_invoice(...)` → write invoice + items to SQLite.
- `generate_invoice_pdf(invoice_id)` → produce PDF in local storage.
- `send_invoice_email(invoice_id)` → optional; run only when SMTP config is complete and flow enables it.

The LLM can request routing/clarification only; it cannot claim any tool call succeeded.

---

## 5) Draft system prompt for orchestrator layer

Use as system prompt template:

```text
You are FakturaBot Orchestrator.

Role:
- Interpret multilingual user input (Slovak/Ukrainian/Russian, including mixed or noisy STT text).
- Produce deterministic machine-readable JSON for Python workflows.

Critical constraints:
- Output JSON only. No prose outside JSON.
- Use English keys only.
- Do not invent facts. If unknown, output null.
- If uncertain, surface ambiguity and request clarification in action_plan.
- Never claim DB/storage/PDF/email actions were executed.

Runtime reality constraints:
- Python is source of truth.
- LLM only interprets intent and extracts entities.
- Contact resolution, validation, saving, PDF/QR/email are Python responsibilities.

Supported intents (current runtime):
- create_invoice_draft
- add_contact_manual
- supplier_onboarding
- manage_service_alias
- extract_contact_from_document (not active runtime flow yet; mark as not_supported_yet when requested)
- clarify_previous_step
- unknown

For create_invoice_draft, extract when present:
- customer_name
- item_name_raw
- quantity
- unit
- amount
- currency
- delivery_date
- due_days
- due_date

Date rules:
- Keep only explicitly stated dates.
- Normalize to YYYY-MM-DD when confidently inferable.
- Do not fabricate issue_date.

Return object fields exactly per schema_version "fakturabot.orchestrator.v1".
```

---

## 6) JSON schema (model output)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://fakturabot.local/schemas/orchestrator-output-v1.json",
  "title": "FakturaBotOrchestratorOutputV1",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "schema_version",
    "input_language",
    "intent",
    "entities",
    "missing_fields",
    "ambiguities",
    "action_plan"
  ],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "fakturabot.orchestrator.v1"
    },
    "input_language": {
      "type": "string",
      "enum": ["sk", "uk", "ru", "mixed", "unknown"]
    },
    "intent": {
      "type": "object",
      "additionalProperties": false,
      "required": ["name", "confidence"],
      "properties": {
        "name": {
          "type": "string",
          "enum": [
            "create_invoice_draft",
            "add_contact_manual",
            "supplier_onboarding",
            "manage_service_alias",
            "extract_contact_from_document",
            "clarify_previous_step",
            "unknown"
          ]
        },
        "confidence": {
          "type": "number",
          "minimum": 0,
          "maximum": 1
        }
      }
    },
    "entities": {
      "type": "object",
      "additionalProperties": false,
      "required": [
        "customer_name",
        "item_name_raw",
        "quantity",
        "unit",
        "amount",
        "currency",
        "delivery_date",
        "due_days",
        "due_date",
        "contact_name",
        "contact_email",
        "contact_ico",
        "contact_dic",
        "contact_ic_dph",
        "contact_address",
        "contact_person"
      ],
      "properties": {
        "customer_name": {"type": ["string", "null"]},
        "item_name_raw": {"type": ["string", "null"]},
        "quantity": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "unit": {"type": ["string", "null"]},
        "amount": {"type": ["number", "null"], "exclusiveMinimum": 0},
        "currency": {
          "type": ["string", "null"],
          "pattern": "^[A-Z]{3}$"
        },
        "delivery_date": {
          "type": ["string", "null"],
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "due_days": {"type": ["integer", "null"], "minimum": 1},
        "due_date": {
          "type": ["string", "null"],
          "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
        },
        "contact_name": {"type": ["string", "null"]},
        "contact_email": {"type": ["string", "null"]},
        "contact_ico": {"type": ["string", "null"]},
        "contact_dic": {"type": ["string", "null"]},
        "contact_ic_dph": {"type": ["string", "null"]},
        "contact_address": {"type": ["string", "null"]},
        "contact_person": {"type": ["string", "null"]}
      }
    },
    "missing_fields": {
      "type": "array",
      "items": {"type": "string"},
      "uniqueItems": true
    },
    "ambiguities": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["field", "candidates", "reason"],
        "properties": {
          "field": {"type": "string"},
          "candidates": {
            "type": "array",
            "minItems": 2,
            "items": {"type": "string"}
          },
          "reason": {"type": "string"}
        }
      }
    },
    "action_plan": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["step", "action", "target", "message_to_user"],
        "properties": {
          "step": {"type": "integer", "minimum": 1},
          "action": {
            "type": "string",
            "enum": [
              "route_to_flow",
              "ask_clarification",
              "request_missing_fields",
              "not_supported_yet",
              "reject"
            ]
          },
          "target": {"type": "string"},
          "message_to_user": {"type": "string"}
        }
      }
    }
  }
}
```

---

## 7) Realistic multilingual examples (14)

> Note: examples show **model output only** per contract.

### Example 1 — SK invoice creation

User input: `Vytvor faktúru pre Tesla Slovakia, položka montáž dverí, suma 320 eur.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"sk","intent":{"name":"create_invoice_draft","confidence":0.97},"entities":{"customer_name":"Tesla Slovakia","item_name_raw":"montáž dverí","quantity":null,"unit":null,"amount":320,"currency":"EUR","delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["quantity","delivery_date"],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepared invoice draft candidates. Please confirm missing fields."}]}
```

### Example 2 — UA invoice creation

User input: `Створи фактуру для ТОВ Ромашка: ремонт кондиціонера, 1 шт, 150 євро, дата поставки 2026-04-05.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"uk","intent":{"name":"create_invoice_draft","confidence":0.98},"entities":{"customer_name":"ТОВ Ромашка","item_name_raw":"ремонт кондиціонера","quantity":1,"unit":"шт","amount":150,"currency":"EUR","delivery_date":"2026-04-05","due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":[],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepared invoice draft."}]}
```

### Example 3 — RU with shortened customer name

User input: `Сделай фактуру на Теслу, услуга проводка, 500 евро.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"ru","intent":{"name":"create_invoice_draft","confidence":0.9},"entities":{"customer_name":"Тесла","item_name_raw":"проводка","quantity":null,"unit":null,"amount":500,"currency":"EUR","delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["quantity"],"ambiguities":[{"field":"customer_name","candidates":["Тесла","Tesla Slovakia"],"reason":"Shortened name may match multiple local contacts."}],"action_plan":[{"step":1,"action":"ask_clarification","target":"customer_name","message_to_user":"Уточните точное название клиента из вашей адресной книги."}]}
```

### Example 4 — Mixed UA/RU/SK wording

User input: `Фактура pre Alfa s.r.o., замена замка, 2 ks, 45 euro за kus, dodanie 7.4.2026.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"mixed","intent":{"name":"create_invoice_draft","confidence":0.96},"entities":{"customer_name":"Alfa s.r.o.","item_name_raw":"замена замка","quantity":2,"unit":"ks","amount":90,"currency":"EUR","delivery_date":"2026-04-07","due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":[],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepared invoice draft."}]}
```

### Example 5 — Service alias wording

User input: `Prosím faktúru pre Beta, položka 'elektro robota', 200 EUR.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"sk","intent":{"name":"create_invoice_draft","confidence":0.93},"entities":{"customer_name":"Beta","item_name_raw":"elektro robota","quantity":null,"unit":null,"amount":200,"currency":"EUR","delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["quantity"],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepared invoice draft. Python will resolve service alias if configured."}]}
```

### Example 6 — Missing amount

User input: `Створи фактуру для Orion, монтаж вікон, 3 штуки.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"uk","intent":{"name":"create_invoice_draft","confidence":0.94},"entities":{"customer_name":"Orion","item_name_raw":"монтаж вікон","quantity":3,"unit":"штуки","amount":null,"currency":null,"delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["amount"],"ambiguities":[],"action_plan":[{"step":1,"action":"request_missing_fields","target":"amount","message_to_user":"Please provide invoice amount and currency."}]}
```

### Example 7 — Missing date and due-days

User input: `Счет для Delta, обслуживание котла, 120 EUR.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"ru","intent":{"name":"create_invoice_draft","confidence":0.95},"entities":{"customer_name":"Delta","item_name_raw":"обслуживание котла","quantity":null,"unit":null,"amount":120,"currency":"EUR","delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["delivery_date"],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepared draft; Python may apply default delivery date if user confirms."}]}
```

### Example 8 — Ambiguous amount interpretation

User input: `Фактура для EkoDom, фарбування 12 500.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"mixed","intent":{"name":"create_invoice_draft","confidence":0.74},"entities":{"customer_name":"EkoDom","item_name_raw":"фарбування","quantity":null,"unit":null,"amount":null,"currency":null,"delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["amount","currency"],"ambiguities":[{"field":"amount","candidates":["12.5","12500"],"reason":"Number tokenization unclear in noisy input."}],"action_plan":[{"step":1,"action":"ask_clarification","target":"amount","message_to_user":"Please confirm exact amount and currency."}]}
```

### Example 9 — STT/transliterated noisy input

User input: `faktura dlya kompanii Nova bud itemka montazh dverey suma 300 evro srok 14 dney`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"mixed","intent":{"name":"create_invoice_draft","confidence":0.87},"entities":{"customer_name":"Nova bud","item_name_raw":"montazh dverey","quantity":null,"unit":null,"amount":300,"currency":"EUR","delivery_date":null,"due_days":14,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["quantity"],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepared draft from noisy/transliterated text."}]}
```

### Example 10 — Manual contact intent

User input: `Додай контакт: ТОВ Лотос, ІПН 1234567890, адреса Київ, email office@lotos.ua`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"uk","intent":{"name":"add_contact_manual","confidence":0.97},"entities":{"customer_name":null,"item_name_raw":null,"quantity":null,"unit":null,"amount":null,"currency":null,"delivery_date":null,"due_days":null,"due_date":null,"contact_name":"ТОВ Лотос","contact_email":"office@lotos.ua","contact_ico":null,"contact_dic":"1234567890","contact_ic_dph":null,"contact_address":"Київ","contact_person":null},"missing_fields":["contact_ico"],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"contact","message_to_user":"Route to manual contact flow and continue required fields."}]}
```

### Example 11 — Document extraction intent (not active yet)

User input: `З цього договору витягни реквізити замовника і додай в контакти.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"uk","intent":{"name":"extract_contact_from_document","confidence":0.96},"entities":{"customer_name":null,"item_name_raw":null,"quantity":null,"unit":null,"amount":null,"currency":null,"delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":[],"ambiguities":[],"action_plan":[{"step":1,"action":"not_supported_yet","target":"contracts","message_to_user":"Document extraction flow is not active in current runtime. Ask user to use /contact for manual entry."}]}
```

### Example 12 — Unknown/general chat intent

User input: `Яка сьогодні погода у Братиславі?`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"uk","intent":{"name":"unknown","confidence":0.99},"entities":{"customer_name":null,"item_name_raw":null,"quantity":null,"unit":null,"amount":null,"currency":null,"delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":[],"ambiguities":[],"action_plan":[{"step":1,"action":"reject","target":"out_of_scope","message_to_user":"This request is outside FakturaBot business flows."}]}
```

### Example 13 — Service alias management intent

User input: `Pridaj alias služby: "opravy" nech ide ako "Oprava a servis zariadenia".`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"sk","intent":{"name":"manage_service_alias","confidence":0.98},"entities":{"customer_name":null,"item_name_raw":null,"quantity":null,"unit":null,"amount":null,"currency":null,"delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":[],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"service","message_to_user":"Route user to /service alias flow (2-step alias->canonical input)."}]}
```

### Example 14 — No exact contact match (must not auto-add)

User input: `Сделай фактуру на компанию Ромашка, монтаж, 200 евро.`

```json
{"schema_version":"fakturabot.orchestrator.v1","input_language":"ru","intent":{"name":"create_invoice_draft","confidence":0.94},"entities":{"customer_name":"Ромашка","item_name_raw":"монтаж","quantity":null,"unit":null,"amount":200,"currency":"EUR","delivery_date":null,"due_days":null,"due_date":null,"contact_name":null,"contact_email":null,"contact_ico":null,"contact_dic":null,"contact_ic_dph":null,"contact_address":null,"contact_person":null},"missing_fields":["quantity"],"ambiguities":[],"action_plan":[{"step":1,"action":"route_to_flow","target":"invoice","message_to_user":"Prepare draft and run Python contact lookup. If lookup=no_match, ask user to confirm exact contact or start /contact manually."}]}
```

---

## 8) Failure behavior (short)

### 8.1 Contact is uncertain

- Put candidate names into `ambiguities`.
- Use `ask_clarification` action.
- Python must not auto-select a contact if multiple matches exist.
- Python lookup state `no_match` must prompt explicit user decision; do not silently switch to contact creation.

### 8.2 Amount/date is missing

- Add fields to `missing_fields`.
- Use `request_missing_fields` when blocking.
- If non-blocking for draft preview, route with explicit note; Python applies deterministic defaults only where already defined by runtime.

### 8.3 Multiple interpretations

- Keep disputed field as `null` unless one interpretation is clearly dominant.
- List alternatives in `ambiguities` with reason.
- First action step must be clarification request.

---

## 9) Proposed rollout (non-code)

1. Add this document as source contract for orchestrator prompt + parser tests.
2. Replace current invoice-only prompt with orchestrator prompt only when Python side consumes full schema.
3. Keep backward compatibility path until handlers are ready for `action_plan` processing.
