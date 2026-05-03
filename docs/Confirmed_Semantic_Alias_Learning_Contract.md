# Confirmed Semantic Alias Learning Contract

**Document role:** reusable contract for storing user-confirmed semantic aliases that improve future bounded lookup/resolution without letting AI or STT mutate business data autonomously.

This contract applies first to FakturaBot invoice customer lookup, where an extracted customer candidate such as `Real-Time Technologies` may be confirmed as an alias for an existing local contact such as `REALTIME TECHNOLOGIES SK, s.r.o.`.

---

## 1. Authority Split

Python remains the only execution and storage authority.

AI/STT/LLM may produce candidate text, but candidate text is never saved as a semantic alias until:
- Python has scoped the action to an authorized supplier/user;
- Python has found exactly one safe target candidate in the existing local data;
- the user explicitly confirms the proposed target through a shared `DecisionResolver` family;
- Python writes the alias to local storage.

The resolver must not claim that an alias was saved. It only normalizes the user's confirmation reply.

---

## 2. What May Be Stored

A stored semantic alias must be:
- tenant/supplier scoped;
- domain scoped, for example `invoice_customer`;
- target typed, for example `contact`;
- linked to an existing local target row;
- derived from a bounded extracted candidate field, not from the entire raw user message or full STT transcript.

For invoice customer lookup, the stored alias source is the parsed/extracted customer candidate, for example `biznis_sk.odberatel_kandidat` / internal `customer_name`.

The full raw STT transcript, full invoice request text, or unrelated message text must not be stored as an alias.

---

## 3. Lookup Integration Rule

Semantic alias learning must integrate into the existing owner lookup path for the target domain.

For contacts, `ContactService.resolve_contact_lookup(...)` remains the owner. Alias lookup is an additional stage inside that resolver, not a parallel lookup subsystem in invoice handlers.

Expected contact lookup order:
1. exact local contact name;
2. case/normalized local contact name;
3. confirmed semantic alias;
4. safe single close candidate requiring confirmation;
5. multiple candidates / no match.

---

## 4. Confirmation Rule

Any alias write is confirmation-like and must use the shared `DecisionResolver`.

For yes/no alias confirmation:
- decision family: `yes_no`;
- example context: `invoice_customer_alias_confirm`;
- canonical outputs consumed by handler: `yes`, `no`, `unknown`.

Handlers must branch only on canonical outputs. No local parsing of `ano`, `nie`, `ok`, multilingual replies, or STT-noisy variants is allowed.

---

## 5. Country / Legal Suffix Safety

Lookup normalization may ignore punctuation, whitespace, legal suffixes, and safe separators for lookup only.

Country-like suffix tokens require care:
- if the user candidate has no country token, a single close candidate with a country suffix may be proposed for confirmation;
- if the user candidate explicitly includes a country token such as `SK` or `CZ`, that token must be respected;
- `REALTIME TECHNOLOGIES CZ` must not silently match `REALTIME TECHNOLOGIES SK`;
- if both SK and CZ contacts exist and the user omits the country token, the result must be ambiguous, not auto-selected.

---

## 6. Side Effects

Alias learning must not:
- create contacts;
- edit contact display names;
- change ICO/DIC/address/email;
- create invoices;
- change invoice numbering;
- save accounting documents;
- run external company lookup.

It may only add/update a scoped alias row after explicit confirmation.

---

## 7. Test Requirements

Runtime patches using this contract must add tests proving:
- alias write happens only after canonical `yes`;
- canonical `no` does not write the alias and returns to clarification;
- `unknown` keeps the confirmation state and repeats the bounded prompt;
- raw full STT/request text is not stored as alias;
- future lookup uses the stored alias through the existing domain lookup owner;
- explicit country-token mismatch does not match;
- missing country-token with multiple country variants is ambiguous.

