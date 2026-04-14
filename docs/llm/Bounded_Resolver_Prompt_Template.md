# Bounded Resolver Prompt Template

Purpose: compact spec for Python -> LLM bounded semantic resolution payloads.

## 1) Base envelope

```json
{
  "context_name": "top_level_action",
  "current_state": "optional_fsm_state_or_step",
  "user_input_text": "raw user text or STT transcript",
  "supported_languages": ["sk", "uk", "ru"],
  "allowed_actions": ["create_invoice", "add_contact", "add_service_alias", "unknown"],
  "expected_output": {"canonical_action": "one allowed token or unknown"},
  "auxiliary_context": {}
}
```

Rules:
- Python defines the bounded set (`allowed_actions` or `allowed_responses`).
- LLM returns exactly one allowed canonical token or `unknown`.
- No side-effect text, no free-form plans.

## 2) Optional `action_hints` (selective)

Use only when a top-level action is semantically ambiguous and plain allowed-actions list is not stable enough.
Hints are optional guidance, not mandatory overhead.

`action_hints` shape:
- `meaning` (required when hint is used)
- `positive_examples` (optional)
- `not_this` (optional)

Guidelines:
- keep hints compact and practical;
- do not turn hints into ontology or keyword parser;
- use mainly to separate nearby actions (e.g. `create_invoice` vs `add_service_alias` vs `edit_invoice`).

## 3) Compact example

```json
{
  "context_name": "top_level_action",
  "user_input_text": "pridaj novú položku pre faktúru",
  "allowed_actions": [
    "create_invoice",
    "add_service_alias",
    "edit_invoice",
    "unknown"
  ],
  "action_hints": {
    "create_invoice": {
      "meaning": "Create a new invoice draft from user content.",
      "not_this": [
        "Do not use when user asks to add/edit saved service naming mappings."
      ]
    },
    "add_service_alias": {
      "meaning": "Add a new short service/item name mapping used later in invoice PDFs.",
      "positive_examples": [
        "pridaj novú položku",
        "pridaj novú službu",
        "додай нову назву послуги"
      ],
      "not_this": [
        "Do not use when user asks to create a concrete invoice now.",
        "Do not use when user asks to edit an already created invoice."
      ]
    }
  },
  "expected_output": {"canonical_action": "create_invoice|add_service_alias|edit_invoice|unknown"}
}
```

Note:
- noisy user forms (including malformed mixed-language input) may appear in runtime input examples,
- but canonical bot-facing wording remains controlled by product docs and Slovak bot replies.
