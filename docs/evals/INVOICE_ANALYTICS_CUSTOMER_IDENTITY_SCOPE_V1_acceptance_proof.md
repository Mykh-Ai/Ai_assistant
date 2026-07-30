# Invoice Analytics Customer Identity Scope V1 Acceptance Proof

Status: `partial`, local repair validated; review required before merge/deploy.

## Product journey

An authorized idle user asks by text or voice/STT for invoice analytics about
one customer using a noisy, transliterated, or Cyrillic name. The existing
`invoice_analytics` action remains the owner.

Python supplies only unique current-tenant contact names plus `unknown` to the
bounded resolver. If one contact is selected, Python prefilters the sanitized
invoice dataframe by its trusted `contact_id`. The analytics planner receives a
catalog marker that the customer scope is already enforced and is rejected if
it attempts a second raw `customer_name` or `contact_id` filter.

## Acceptance scenarios

1. Noisy/Cyrillic explicit customer reference
   - Given two contacts and invoices in the same tenant.
   - The resolver can return only one supplied contact name or `unknown`.
   - The planner/executor sees only the selected contact's invoice rows.
   - The result excludes the other contact's amount.

2. General analytics question
   - The customer resolver returns `unknown`.
   - Python leaves the current-tenant dataframe unfiltered.
   - The data catalog has no active customer scope.

3. Planner negative space
   - With trusted customer scope active, a plan referencing `customer_name` or
     `contact_id` is rejected as `customer_scope_must_not_be_refiltered`.
   - A plan aggregating the already-prefiltered dataframe is accepted.

4. Tenant and side-effect boundary
   - Resolver candidates come only from `ScopedInvoiceRuntime.list_contacts()`.
   - No Telegram/workspace identifiers or contact tax/email fields are supplied
     as resolver option descriptions.
   - No alias/contact/invoice/PDF/DB/storage write occurs.

5. Product truth and forbidden claims
   - Capability remains `partial`, outgoing invoices/current tenant/read-only.
   - This does not claim broad accounting, bank, receipt, tax, or cross-tenant
     analytics.
   - Invoice history and already generated PDFs are not rewritten.

## Automated evidence

- Focused invoice analytics tests: 54 passed, 195 deselected.
- Adjacent analytics/Product Truth/InfoHelp/voice tests: 469 passed.
- Full repository suite: 2376 passed, 7 subtests passed.
- Compileall and `git diff --check` passed; diff-check reported only existing
  Windows line-ending conversion warnings.
