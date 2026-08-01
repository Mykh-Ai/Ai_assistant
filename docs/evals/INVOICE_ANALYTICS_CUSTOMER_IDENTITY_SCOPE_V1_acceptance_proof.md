# Invoice Analytics Customer Identity Scope V1 Acceptance Proof

Status: `partial`, merged and deployed at
`2379869c6f609624082fc36eb1e088174e554154`; real Telegram voice acceptance remains pending.

## Product journey

An authorized idle user asks by text or voice/STT for invoice analytics about
one customer using a noisy, transliterated, or Cyrillic name. The existing
`invoice_analytics` action remains the owner.

A bounded extractor returns only the explicitly stated customer reference or
`null`; it receives no contact list. Python then reuses the invoice-generation
tenant-scoped contact chain: exact, normalized, confirmed alias, fuzzy, and only
then bounded LLM fallback. If one contact is resolved, Python prefilters the
sanitized invoice dataframe by its trusted `contact_id`. The planner receives a
catalog marker that customer scope is already enforced and is rejected if it
attempts a second raw `customer_name` or `contact_id` filter.

## Acceptance scenarios

1. Noisy/Cyrillic explicit customer reference
   - Given two contacts and invoices in the same tenant.
   - The extractor returns only the noisy/Cyrillic company mention.
   - A previously confirmed alias resolves before bounded LLM fallback.
   - The planner/executor sees only the selected contact's invoice rows.
   - The result excludes the other contact's amount.

2. General analytics question
   - The extractor returns `null`.
   - Python leaves the current-tenant dataframe unfiltered.
   - The data catalog has no active customer scope.

3. Explicit unresolved customer
   - Exact, normalized, alias, fuzzy, and bounded fallback do not resolve it.
   - Python asks for the precise saved contact name.
   - The planner does not run over all invoices.

4. Planner negative space
   - With trusted customer scope active, a plan referencing `customer_name` or
     `contact_id` is rejected as `customer_scope_must_not_be_refiltered`.
   - A plan aggregating the already-prefiltered dataframe is accepted.

5. Tenant and side-effect boundary
   - Resolver candidates come only from `ScopedInvoiceRuntime.list_contacts()`.
   - No cross-tenant candidates are supplied to deterministic or bounded lookup.
   - No alias/contact/invoice/PDF/DB/storage write occurs.

6. Product truth and forbidden claims
   - Capability remains `partial`, outgoing invoices/current tenant/read-only.
   - This does not claim broad accounting, bank, receipt, tax, or cross-tenant
     analytics.
   - Invoice history and already generated PDFs are not rewritten.

## Automated evidence

- Alias-first regression failed before the repair and passes after it.
- Final focused, adjacent, full-suite, compileall, and diff-check evidence is
  recorded in `PROJECT_LOG.md` for the merged repair commit.
