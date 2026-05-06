# TASK: Add source customer mention to invoice extraction bundle for future contact alias learning

## Context

FakturaBot / OfficeFlow already has or plans confirmed semantic alias learning for contacts.

Problem:
When a user dictates an invoice by voice, STT may return a mixed-language or transliterated transcript.

Example:

> "вистав фактуру на фірму тек компані за opravy elektroinštalácie na 1000 eur"

The actual customer mention in the transcript may be:

> "тек компані"

But the LLM invoice extraction layer may normalize this to:

> "Tech Company"

or match it to an existing contact:

> "Tech Company s.r.o."

Python should not be expected to reliably extract the raw company/customer mention from the full STT transcript by itself, especially when the mention is Cyrillic transliteration, mixed-language, misspelled, or embedded in a longer sentence.

The correct architecture is:

STT transcript  
→ LLM invoice extraction  
→ structured bundle with both raw/source mention and normalized customer candidate  
→ Python ContactService validation / lookup  
→ invoice preview  
→ user approval  
→ only then optional confirmed alias learning.

Python remains the source of truth.  
LLM only extracts and normalizes structured data.

---

## Goal

Extend the invoice extraction bundle so the LLM returns both:

1. the normalized/customer candidate used for lookup;
2. the raw/source customer mention from the original user input.

This prepares the project for safe contact alias learning after user approval.

---

## Status as of 2026-05-06

Implemented for invoice customer raw mentions and invoice service raw mentions.

Current runtime field names follow the existing invoice extraction schema:

- `biznis_sk.odberatel_raw_mention` stores the raw/source customer mention from the original text or STT transcript.
- `biznis_sk.service_raw_mention` stores an optional raw/source service mention for the whole invoice draft.
- `biznis_sk.items[].service_raw_mention` stores an optional raw/source service mention per extracted invoice item.

Implemented customer behavior:

- the invoice prompt asks the LLM to extract `odberatel_raw_mention` as an exact or near-exact phrase from `vstup.povodny_text`;
- the parser preserves this field as optional structured data;
- Python validates the raw customer mention before treating it as an alias candidate;
- after invoice preview approval, Python may store the safe raw mention as a confirmed contact alias through the existing ContactService / `confirmed_semantic_alias` path.

Implemented service behavior:

- the invoice prompt asks the LLM to extract `service_raw_mention` as an exact or near-exact phrase from `vstup.povodny_text`;
- the parser preserves this field as optional structured data;
- Python validates the raw service mention before treating it as an alias candidate;
- Python first resolves the service to an existing manual `/sluzbu` mapping;
- after invoice preview approval, Python may store the safe raw mention as a confirmed service alias through `ServiceAliasService` / `confirmed_semantic_alias`;
- future invoice lookup can resolve the learned practical variant through the existing service resolution path.

Important boundary:

- learned service aliases are stored in `confirmed_semantic_alias` with domain `invoice_service`;
- they point to existing `supplier_service_alias` rows;
- they must not be written into `supplier_service_alias`, because that table represents user-provided manual service aliases;
- runtime must not create/edit manual `/sluzbu` mappings, rewrite service titles, or mutate invoice item descriptions from learned aliases.

Remaining work:

- add any missing ambiguity gates before contact alias persistence if multiple contacts are plausible;
- decide whether to enforce the 10-alias cap for contact aliases too;
- broaden rejection tests for raw mentions that contain variable business data such as amount, date, IBAN, email, phone, invoice number, price, or quantity.

---

## Required bundle fields

Add fields similar to:

```json
{
  "customer_raw_mention": "тек компані",
  "customer_normalized_name": "Tech Company",
  "customer_match_candidate": "Tech Company s.r.o.",
  "customer_match_confidence": "high"
}
```

Alternative field names are acceptable if they match existing project conventions, but the meaning must be preserved.

Current FakturaBot field mapping:

- `customer_raw_mention` -> `biznis_sk.odberatel_raw_mention`
- `service_raw_mention` -> `biznis_sk.service_raw_mention` or `biznis_sk.items[].service_raw_mention`

Field meanings

customer_raw_mention

The exact or near-exact phrase from the original user input/STT transcript that refers to the customer/company.

Example:

тек компані

customer_normalized_name

The normalized business/customer name inferred by the LLM.

Example:

Tech Company

customer_match_candidate

The matched contact display name or candidate used by Python lookup, if available.

Example:

Tech Company s.r.o.

customer_match_confidence

Confidence level for the extraction/match.

Example values may be:

high
medium
low
unknown

If the project already has a customer/contact extraction schema, extend that schema instead of creating a parallel one.

Important architecture rules
Python remains the source of truth.
LLM only extracts/normalizes structured data.
LLM must not create aliases directly.
Python must validate extracted customer fields through existing ContactService/contact lookup logic.
Alias learning must happen only after invoice preview approval or explicit user confirmation.
Do not learn aliases from the full raw STT transcript.
Learn only the extracted customer mention.
Do not create aliases before preview approval.

Correct alias candidate:

"тек компані" → "Tech Company s.r.o."

Wrong alias candidate:

"вистав фактуру на фірму тек компані за opravy elektroinštalácie na 1000 eur" → "Tech Company s.r.o."

The full voice/text command contains variable data such as service, price, dates, payment terms, and other invoice-specific details. It must not be stored as a contact alias.

Alias learning rule for future phase

After invoice preview approval, Python may store a confirmed alias if all conditions are true:

customer_raw_mention is present;
matched contact/customer is confirmed by preview approval or explicit user choice;
raw mention is not too long;
raw mention does not contain invoice amount, date, IBAN, email, phone number, invoice number, or other variable business data;
raw mention is not already known;
there is no ambiguity between multiple contacts;
alias limit per contact/user/domain is not exceeded.

Suggested limit:

max 5 confirmed aliases per contact per supplier/user/domain

If the limit is reached, do not auto-add a new alias. Do not silently replace existing aliases unless a later task explicitly designs that behavior.

Safety / ambiguity

If multiple contacts match the normalized name, do not auto-store alias.

Example ambiguous candidates:

Tech Company s.r.o.
Tech Company Plus s.r.o.
Tech Company SK s.r.o.

In this case Python must ask the user to choose/confirm the correct contact first.

Only after explicit choice or invoice preview approval may the alias be stored.

Example expected flow

Original/STT input:

вистав фактуру на фірму тек компані за opravy elektroinštalácie na 1000 eur

LLM invoice extraction returns:

{
  "customer_raw_mention": "тек компані",
  "customer_normalized_name": "Tech Company",
  "customer_match_candidate": "Tech Company s.r.o.",
  "customer_match_confidence": "high",
  "service_description": "opravy elektroinštalácie",
  "amount": 1000,
  "currency": "EUR"
}

Python then performs contact lookup/validation:

customer_raw_mention = "тек компані"
customer_normalized_name = "Tech Company"
matched contact = "Tech Company s.r.o."

Bot shows invoice preview with the matched customer.

If the user approves the preview, Python may store confirmed alias:

"тек компані" → "Tech Company s.r.o."

If the user rejects or edits the customer, do not store alias from the rejected preview.

Out of scope for this task

Do not implement general command alias learning here.

Do not implement top-level action alias learning here.

Do not modify voice top-level command routing here.

Do not teach aliases for variable command phrases like:

"видали фактуру номер 08"
"управить фактуру 15"
"zmeniť faktúru 2026-000015"

Those require future pattern/slot learning, not simple alias storage.

Do not change destructive confirmation behavior.

Do not weaken existing Python/FSM validation.

Do not bypass ContactService.

Do not create aliases directly from LLM output without Python validation and user approval.

Tests required

Add or update tests proving:

Invoice extraction bundle can carry customer_raw_mention.
Mixed-language or Cyrillic-transliterated customer mention is preserved separately from normalized customer name.
Python does not create contact alias before preview approval.
Alias may be created only after approved preview or explicit user confirmation.
Alias is not created when multiple contact candidates are ambiguous.
Alias is not created from the full invoice command text.
Alias is not created if raw mention contains variable data such as amount, date, email, IBAN, invoice number, or phone number.
Existing invoice creation flow still works for normal text and voice-derived transcripts.
Existing ContactService lookup/validation remains the authority for final contact matching.
Expected result

The invoice creation flow should preserve this distinction:

Original/STT input:
"вистав фактуру на фірму тек компані за opravy na 1000 eur"

LLM extraction:
customer_raw_mention = "тек компані"
customer_normalized_name = "Tech Company"

Python/contact lookup:
matched contact = "Tech Company s.r.o."

After user approves preview:
confirmed alias may be stored:
"тек компані" → "Tech Company s.r.o."

This prepares FakturaBot / OfficeFlow for safe contact alias self-learning without forcing Python to guess company names from noisy STT transcripts.
