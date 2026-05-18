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
- User input may be Slovak, Ukrainian, Russian, mixed-language, colloquial, or STT-noisy.
- For top-level actions, the resolver should first infer the user meaning and internally normalize it to Slovak product semantics for the current FakturaBot context, then choose one allowed canonical token.
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
- examples are illustrative only, never a whitelist or exact-match requirement;
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

## 4) InfoHelp and Unknown / Discovery / Triage

InfoHelp uses two bounded classification steps before any response is rendered:

1. known Product Truth capability/topic classification;
2. Unknown / Discovery / Triage when no known `capability_id` or topic fits.

The model may only classify into Python-provided IDs/classes. It must not
invent capability IDs, change Product Truth status, execute actions, promise
feature availability, save customization requests, notify admins, or bypass
FSM/state/auth gates.

Allowed triage classes:

```json
[
  "known_product_capability",
  "new_business_feature_request",
  "customization_request_candidate",
  "admin_review_candidate",
  "out_of_domain",
  "spam_or_abuse",
  "smalltalk",
  "unclear_needs_clarification",
  "possible_product_truth_candidate",
  "unknown"
]
```

Compact triage envelope:

```json
{
  "context_name": "info_help_unknown_triage",
  "current_state": null,
  "user_input_text": "Vieš mi spraviť prehľad tržieb za minulý mesiac?",
  "supported_languages": ["sk", "uk", "ru"],
  "allowed_triage_classes": [
    "new_business_feature_request",
    "customization_request_candidate",
    "admin_review_candidate",
    "out_of_domain",
    "spam_or_abuse",
    "smalltalk",
    "unclear_needs_clarification",
    "possible_product_truth_candidate",
    "unknown"
  ],
  "known_capability_ids": ["create_invoice", "send_invoice_email", "accounting_export"],
  "expected_output": {
    "triage_class": "one allowed triage class",
    "capability_id": "known id or unknown",
    "response_mode_hint": "optional non-authoritative hint, only if requested"
  },
  "auxiliary_context": {
    "request_storage_available": false,
    "admin_notification_available": false
  }
}
```

The output is classification only. The model must not authoritatively choose
the final response mode. If `response_mode_hint` is requested, Python may
validate, ignore, or override it. Python derives the final response mode from
Product Truth primary status, flags/context, account state, active
FSM/routing state, and safety policy before rendering Product Truth, asking
clarification, rejecting out-of-domain input, ignoring/blocking noise,
answering smalltalk briefly, or offering a future confirmation-gated request
path.
