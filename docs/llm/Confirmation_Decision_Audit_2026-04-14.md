# Confirmation/Decision Resolver Audit — 2026-04-14

Scope: audit-only map of current short in-action confirmations/decisions (text + voice), with contract-gap notes. No runtime behavior changes in this session.

## Resolver inventory (code-evidenced)

### 1) `invoice_preview_confirmation`
- Handler: `process_invoice_preview_confirmation(...)`.
- Context: `invoice_preview_confirmation`.
- Allowed canonical outputs: `ano`, `nie`, `unknown`.
- Resolver path: generic `resolve_semantic_action(...)`.
- `unknown` behavior: user retry prompt `Prosím, odpovedzte áno alebo nie.`
- Non-unknown behavior:
  - `nie` => clear state + cancel message.
  - `ano` => persist invoice + PDF flow + move to `waiting_pdf_decision`.

### 2) `invoice_postpdf_decision`
- Handler: `process_invoice_postpdf_decision(...)`.
- Context: `invoice_postpdf_decision`.
- Allowed canonical outputs: `schvalit`, `upravit`, `zrusit`, `unknown`.
- Resolver path: generic `resolve_semantic_action(...)`.
- `unknown` behavior: user retry prompt `Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.`
- Non-unknown behavior:
  - `schvalit` => mark invoice `pripravena`.
  - `upravit` => delete invoice+items, unlink PDF, clear state, reply edit-not-available.
  - `zrusit` => delete invoice+items, unlink PDF, clear state, cancellation message.

### 3) `contact_confirm` (semantic intake)
- Handler: `process_contact_intake_confirm(...)`.
- Context: `contact_confirm`.
- Allowed canonical outputs: `ano`, `nie`, `unknown`.
- Resolver path: generic `resolve_semantic_action(...)`.
- `unknown` behavior: user retry prompt `Napíšte ano alebo nie.`
- Non-unknown behavior:
  - `nie` => clear state + cancel message.
  - `ano` => save contact draft + clear state.

### 4) `contact_manual_confirm`
- Handler: `contact_confirm(...)`.
- Resolver path: deterministic parser only (`answer in {'ano','nie'}`), text route.
- Allowed values: `ano`, `nie`.
- Unknown/non-match behavior: `Napíšte ano alebo nie.`

### 5) `supplier_onboarding_confirm`
- Handler: `onboarding_confirm(...)`.
- Resolver path: deterministic parser only (`answer in {'ano','nie'}`), text route.
- Allowed values: `ano`, `nie`.
- Unknown/non-match behavior: `Napíšte ano alebo nie.`

## Voice call map (current runtime)

1. `handle_voice(...)` receives Telegram voice.
2. Downloads `.ogg` and runs `transcribe_audio(...)`.
3. Uses raw STT transcript as `recognized_text` (only empty transcript is rejected).
4. Reads FSM state and routes transcript as-is:
   - `waiting_confirm` -> `process_invoice_preview_confirmation(... confirmation_text=recognized_text)`.
   - `waiting_pdf_decision` -> `process_invoice_postpdf_decision(... decision_text=recognized_text)`.
   - `ContactStates.intake_confirm` -> `process_contact_intake_confirm(... answer_text=recognized_text)`.
   - `ContactStates.intake_missing` -> deterministic missing-field processor.
   - `waiting_service_clarification` / `waiting_slot_clarification` -> slot clarification processors.
   - otherwise -> top-level `process_invoice_text(... invoice_text=recognized_text)`.
5. Confirmation/decision handlers call resolver and branch by canonical output.

## Contract-gap notes (current code vs bounded-template docs)

### Generic `resolve_semantic_action(...)`
Current payload includes:
- `context_name`
- `allowed_actions`
- `user_input_text`
- `auxiliary_context`
- `action_hints`

Missing vs prompt-template envelope:
- no `current_state`
- no explicit `supported_languages`
- no explicit `expected_output` field structure

### Dedicated bounded resolver (`resolve_quantity_unit_price_pair(...)`)
This one *does* include:
- `context_name=invoice_slot_clarification`
- `expected_reply_type=quantity_times_unit_price`
- `supported_input_languages=['uk','ru','sk']`
- strict bounded output contract with fallback `unknown`

## STT-noise risk lens (`áno` -> transcript like `Ah, não.`)

Observed resolver behavior is token-based fallback when LLM path is skipped/fails.

- For preview/contact confirms, fallback maps token `no` to `nie`.
- Since tokenizer normalizes accents, transcript token like Portuguese `não` can become `nao`; if a separate token `no` appears in noisy transcript, it is treated as negative (`nie`) and not `unknown`.
- For post-PDF decision, `nie`/`нет` map to destructive branch `zrusit`.

Therefore, noisy STT can be forced into negative/destructive canonical outcomes instead of `unknown` in all three semantic confirmation/decision groups, not just preview.

## Tests audit note
Existing tests cover positive routing and some multilingual confirms/decisions, including voice state routing, but do not currently include explicit noisy-STT ambiguity regressions for `unknown` fallback on confirmation/decision contexts.
