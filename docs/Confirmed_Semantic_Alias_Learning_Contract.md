# Confirmed Semantic Alias Learning Contract

**Document role:** reusable AI-memory contract for storing user-confirmed semantic aliases that improve future bounded lookup/resolution without letting AI or STT mutate business data autonomously.

This contract applies first to FakturaBot invoice customer lookup, where an extracted customer candidate such as `Real-Time Technologies` may be confirmed as an alias for an existing local contact such as `REALTIME TECHNOLOGIES SK, s.r.o.`.

Current implemented domains:
- invoice customer lookup: domain `invoice_customer`, target type `contact`, owner `ContactService`;
- invoice service lookup: domain `invoice_service`, target type `supplier_service_alias`, owner `ServiceAliasService`.

The same pattern may later be reused for other bounded domain levels, such as vendor/category labels or document-intake labels, only after the target domain has an explicit Python owner, bounded resolver contract, storage scope, and tests.

---

## 1. Authority Split

Python remains the only execution and storage authority.

AI/STT/LLM may produce candidate text, but candidate text is never saved as a semantic alias until:
- Python has scoped the action to an authorized supplier/user;
- Python has found exactly one safe target in the existing local data through deterministic lookup, high-confidence fuzzy lookup, or bounded LLM resolution;
- the user explicitly confirms the target through either a shared `DecisionResolver` family or approval of the workflow preview where the target is visibly shown;
- Python writes the alias to local storage.

Resolvers must not claim that an alias was saved. They only normalize noisy input into bounded candidate values. Python decides whether a target is safe, whether the workflow was confirmed, and whether an alias may be stored.

---

## 2. What May Be Stored

A stored semantic alias must be:
- tenant/supplier scoped;
- domain scoped, for example `invoice_customer`;
- target typed, for example `contact`;
- linked to an existing local target row;
- derived from a bounded extracted candidate field, not from the entire raw user message or full STT transcript.

For invoice customer lookup, the stored alias source is the parsed/extracted customer candidate, for example `biznis_sk.odberatel_kandidat` / internal `customer_name`, or a safe source mention from `biznis_sk.odberatel_raw_mention`.

For invoice service lookup, the stored alias source is a safe source mention from `biznis_sk.service_raw_mention` or `biznis_sk.items[].service_raw_mention`, linked to an existing manual service mapping in `supplier_service_alias`. Runtime must not write learned service aliases into `supplier_service_alias`; that table remains the user-owned manual `/sluzbu` service mapping table.

The full raw STT transcript, full invoice request text, or unrelated message text must not be stored as an alias.

Examples of valid alias sources after confirmation:
- Latin STT/transcription variants, for example `Realtim Technologies`, `Real Team Technologies`, or `REALTIME`;
- Cyrillic or mixed-language STT variants after bounded LLM resolution, for example a cleaned customer candidate corresponding to `RealTimeTechnologii`;
- user-typed variants from the same bounded candidate field.

Concrete company names or one-off customer aliases must not be hardcoded in runtime code. They must come from live user input and be stored only through this confirmed alias mechanism.

---

## 3. Lookup Integration Rule

Semantic alias learning must integrate into the existing owner lookup path for the target domain.

For contacts, `ContactService.resolve_contact_lookup(...)` remains the owner. Alias lookup is an additional stage inside that resolver, not a parallel lookup subsystem in invoice handlers.

Expected contact lookup order:
1. exact local contact name;
2. case/normalized local contact name;
3. confirmed semantic alias;
4. high-confidence deterministic fuzzy candidate;
5. bounded LLM resolver over Python-provided target candidates;
6. ambiguity clarification / no match.

High-confidence deterministic fuzzy lookup may auto-select a single safe target for the current draft/preview. Low-confidence results must not be saved as aliases directly; they must either go to bounded LLM resolution or ask the user for clarification.

Bounded LLM resolution must receive only Python-scoped targets for the active supplier/domain and may return only one target from that set or `unknown`. Python must reject any target id or value outside the provided bounds.

For services, `ServiceAliasService` remains the owner. Manual service mappings in `supplier_service_alias` define the canonical local service targets. Confirmed semantic service aliases are an additional lookup stage inside invoice service resolution, not a replacement for `/sluzbu`.

Expected service lookup order:
1. exact/manual service alias in `supplier_service_alias`;
2. confirmed semantic alias in `confirmed_semantic_alias` with domain `invoice_service`;
3. bounded LLM resolver over Python-provided manual service aliases;
4. clarification / no match.

Service alias learning may target only an active service mapping owned by the current supplier. It must not create new manual service mappings, rewrite `canonical_title`, or mutate invoice item descriptions.

---

## 4. Confirmation Rule

Any alias write requires a confirmed workflow result. Two confirmation paths are allowed:

### 4.1 Explicit alias confirmation

For yes/no alias confirmation:
- decision family: `yes_no`;
- example context: `invoice_customer_alias_confirm`;
- canonical outputs consumed by handler: `yes`, `no`, `unknown`.

Handlers must branch only on canonical outputs. No local parsing of `ano`, `nie`, `ok`, multilingual replies, or STT-noisy variants is allowed.

### 4.2 Preview-approved alias learning

For workflow previews where the resolved target is visible to the user, the final preview approval may serve as the confirmation signal for alias learning.

For invoice customer lookup:
- Python may resolve a customer candidate to one safe contact through exact/normalized/alias/fuzzy/bounded LLM lookup;
- the invoice preview must show the canonical contact name from local DB;
- only after the user approves the invoice preview may Python store the cleaned customer candidate as an alias for that contact;
- if the preview is edited, cancelled, rejected, or unresolved, no alias is stored from that candidate.

For invoice service lookup:
- Python may resolve a service candidate to one existing manual service mapping through exact/manual alias, confirmed semantic alias, or bounded LLM lookup;
- the invoice preview must show the canonical service display name from the manual service mapping;
- only after the user approves the invoice preview may Python store a safe `service_raw_mention` as a confirmed semantic alias for that service mapping;
- if the preview is edited, cancelled, rejected, or unresolved, no service alias is stored from that candidate.

This avoids unnecessary `ano` / `nie` prompts when the target is already safely resolved and the user will approve the whole invoice preview.

---

## 5. Resolver Quality Gates

Alias learning must pass a quality gate before storage:

- exact/normalized match: no new alias is required unless the candidate contains a useful alternate user form;
- existing alias match: do not create duplicate aliases;
- high-confidence fuzzy match: may be stored after workflow preview approval;
- bounded LLM match: may be stored after workflow preview approval;
- low-confidence deterministic match: must go to bounded LLM or clarification, not direct alias storage;
- one-contact fallback without semantic confidence: must not create an alias;
- `unknown`, ambiguity, or cancelled flow: must not create an alias.

Cyrillic, transliterated, or heavily STT-distorted candidates should normally go through bounded LLM resolution before they become eligible for alias storage.

Default cap for confirmed semantic aliases is 10 aliases per target per supplier/domain. If the cap is reached, runtime must not auto-add a new alias and must not silently replace existing aliases.

---

## 6. Country / Legal Suffix Safety

Lookup normalization may ignore punctuation, whitespace, legal suffixes, and safe separators for lookup only.

Country-like suffix tokens require care:
- if the user candidate has no country token, a single close candidate with a country suffix may be proposed for confirmation;
- if the user candidate explicitly includes a country token such as `SK` or `CZ`, that token must be respected;
- `REALTIME TECHNOLOGIES CZ` must not silently match `REALTIME TECHNOLOGIES SK`;
- if both SK and CZ contacts exist and the user omits the country token, the result must be ambiguous, not auto-selected.

Unrelated contacts with low similarity are not candidates. For example, a strong `REALTIME...` candidate must not be blocked just because another contact such as `ZEVS s.r.o.` exists in the same supplier scope. Clarification is required only when there are multiple plausible bounded targets, a country-token conflict, or insufficient confidence.

---

## 7. Side Effects

Alias learning must not:
- create contacts;
- edit contact display names;
- change ICO/DIC/address/email;
- create or edit manual service mappings in `supplier_service_alias`;
- rewrite service canonical titles;
- rewrite invoice item descriptions;
- create invoices;
- change invoice numbering;
- save accounting documents;
- run external company lookup.

It may only add/update a scoped alias row after a valid confirmation signal defined by this contract: explicit alias confirmation or approval of a workflow preview that visibly used the resolved target.

---

## 8. Reusable Domain Requirements

Before applying this learning pattern to another domain, the implementation must define:
- domain name and target type;
- Python owner service for lookup and writes;
- storage scope and tenant boundary;
- exact/normalized/alias/fuzzy/LLM lookup order for that domain;
- confirmation signal that makes alias storage valid;
- forbidden side effects;
- tests proving cross-tenant isolation and no raw transcript storage.

Examples:
- invoice customer lookup: domain `invoice_customer`, target type `contact`, owner `ContactService`;
- invoice service lookup: domain `invoice_service`, target type `supplier_service_alias`, owner `ServiceAliasService`;
- future document-intake labels/categories: must define a separate intake/category owner and must not save accounting metadata without user approval.

---

## 9. Test Requirements

Runtime patches using this contract must add tests proving:
- explicit alias-confirmation write happens only after canonical `yes`;
- alias write may happen after approved preview only when the canonical target was visibly used in that preview;
- canonical `no` does not write the alias and returns to clarification;
- `unknown` keeps the confirmation state and repeats the bounded prompt;
- raw full STT/request text is not stored as alias;
- future lookup uses the stored alias through the existing domain lookup owner;
- learned service aliases do not create or update rows in `supplier_service_alias`;
- alias cap is enforced per target per supplier/domain;
- explicit country-token mismatch does not match;
- missing country-token with multiple country variants is ambiguous.
- high-confidence fuzzy with one plausible candidate can resolve without an extra yes/no prompt;
- unrelated low-similarity contacts do not force clarification;
- low-confidence or transliterated/cyrillic candidates go through bounded LLM or clarification before alias storage;
- bounded LLM output outside Python-provided targets is rejected.
