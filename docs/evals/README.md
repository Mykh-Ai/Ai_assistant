# Product UX Evals

This directory is reserved for product UX eval scenarios, smoke checks, and
manual review artifacts.

The governing convention is `docs/Product_UX_Eval_Artifacts.md`.

Do not store secrets, raw customer data, private invoices, credentials, or
cross-tenant data in eval artifacts.

Initial planned eval files:

- `product_truth_infohelp_smoke.md`
- `customization_request_mvp_smoke.md`
- `pdf_layout_manual_review.md`
- `access_tenant_safety_smoke.md`

## Naming Guidance

For each major capability, add or update a focused smoke artifact:

```text
docs/evals/<capability>_smoke.md
```

Examples:

- `google_drive_invoice_storage_smoke.md`
- `admin_response_human_review_smoke.md`
- `invoice_email_delivery_smoke.md`

Each artifact should cover runtime behavior, Product Truth answer, InfoHelp
answer, setup/authorization limits, forbidden claims, and no side effects from
informational questions.
