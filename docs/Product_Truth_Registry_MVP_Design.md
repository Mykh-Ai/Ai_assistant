# Product Truth Registry MVP Design

## Purpose

This document defines the first concrete runtime design for the Product Truth
registry.

`docs/Product_Truth_Layer.md` defines the contract. This document defines the
MVP artifact shape, owner, initial capability ids, and implementation path for
the first runtime registry.

## Current Status

Docs-first design. Runtime registry is not implemented until code, tests, and
Product Truth evals prove it.

## Recommended Runtime Artifact

Start with a Python-owned registry module, not free-form LLM knowledge:

```text
bot/services/product_truth.py
```

Rationale:

- Python remains source of truth;
- schema can be validated at import/test time;
- entries can reference existing handlers/actions without stringly runtime
  document search;
- future JSON/YAML export can be added later if useful.

Do not let the LLM read markdown files at runtime to decide capability truth.

## Minimum Schema

MVP capability entry:

```text
capability_id
title
domain
status
summary_for_user
current_limitations
runtime_owner
commands
canonical_actions
linked_handlers
truth_source_refs
test_refs
safe_next_steps
customization_allowed
dangerous
requires_setup
requires_admin
requires_external_credentials
setup_state_keys
forbidden_claims
last_verified_at
```

Allowed statuses:

- `supported`;
- `partial`;
- `planned`;
- `unsupported`;
- `unknown`;
- `dangerous`;
- `requires_setup`;
- `requires_admin`;
- `requires_external_credentials`.

Status can be combined through flags. Example: status `unsupported` with
`requires_external_credentials = true` for Google Drive or SMS.

## Initial Capability IDs

Minimum MVP set:

```text
create_invoice
show_existing_invoice
edit_existing_invoice
delete_existing_invoice
invoice_pdf_generation
invoice_pdf_custom_template
send_invoice_email
google_drive_invoice_storage
sms_reminders
accounting_export
supplier_profile
edit_supplier_profile
contacts
service_aliases
add_receipt_or_incoming_invoice
show_recent_accounting_documents
officeflow_idle_attachment_router
voice_invoice_intake
delete_user_database
customization_requests
code_agent_handoff
self_learning_aliases
info_help
```

These ids are product capability ids. They are not automatically canonical
actions.

## Account Setup Merge

The registry should return two layers of truth:

```text
product_status
account_status
```

Example:

```text
capability_id: create_invoice
product_status: supported
account_status: requires_setup when supplier profile or service alias is
missing
```

Account setup facts must be provided by Python services, not inferred by LLM.

## Query API Shape

Recommended service API:

```text
get_capability(capability_id, account_context=None)
search_capabilities(query_or_topic, allowed_capability_ids=None)
get_safe_answer_payload(capability_id, account_context=None)
```

The returned payload should be structured and suitable for InfoHelp to verbalize
without inventing facts.

## Validation Owner

Registry validation belongs to Python tests.

Tests must prove:

- all entries use allowed statuses;
- every `supported` entry has runtime owner evidence;
- unsupported/planned entries do not expose linked mutating actions as ready;
- forbidden claims exist for risky integrations;
- setup/admin/external-credential flags are represented;
- no duplicate capability ids exist.

## First Runtime Acceptance

Product Truth Registry MVP is not complete until:

- registry module exists;
- initial capability ids are present;
- InfoHelp or a focused service can query it;
- tests cover `supported`, `partial`, `planned`, `unsupported`, `unknown`,
  `requires_setup`, `requires_admin`, `requires_external_credentials`, and
  `dangerous`;
- email, SMS, Google Drive, accounting export, PDF custom template,
  customization requests, and code-agent handoff are not claimed supported;
- `PROJECT_LOG.md` records the actual runtime status.

## No-Go Rules

Do not:

- make the LLM the Product Truth source;
- use roadmap docs as runtime support proof;
- mark a capability `supported` without runtime owner and tests;
- hide setup/admin/external-credential requirements;
- let learned aliases change Product Truth.
