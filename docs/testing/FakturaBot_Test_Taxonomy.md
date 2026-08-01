# FakturaBot Python Test Taxonomy

Status: active test-maintenance guidance. Marker coverage is intentionally
partial; registration does not imply that every existing test has been
classified.

## Markers

| Marker | Meaning |
| --- | --- |
| unit | Deterministic isolated logic. |
| contract | Bounded schema, registry, or authority contract. |
| integration | Real temporary database, filesystem, process, or several real components. |
| acceptance | Public-entry user journey with final state, effect, and keyboard assertions. |
| server_smoke | Opt-in deployed-runtime read-only or bounded smoke. |
| external | Opt-in real third-party boundary; not an ordinary PR assumption. |
| regression | Named protection for a previously fixed failure. |
| migration | Persisted-data compatibility, apply, or rollback behavior. |
| workspace | Authorization or tenant/workspace isolation. |
| callback | Callback ownership, stale-state, or idempotency lifecycle. |
| slow | A measured slow test or costly test group. |

Markers describe level or risk. They do not replace domain ownership, exact
node IDs, or the default full suite. Unmarked tests remain part of
python -m pytest -q.

## Execution tiers

### Focused

Run the changed component or exact node IDs while developing:

~~~powershell
python -m pytest -q tests\test_product_truth.py
python -m pytest -q tests\test_invoice_intent_prerouter.py -k invoice_analytics
python -m pytest -q tests\test_work_time_routing.py -k top_level_work_time
~~~

### Adjacent

Run the changed owner plus neighboring contracts that could expose routing,
authorization, state, workspace, or provider-boundary regressions. The
selection is explicit per change; common adjacency groups include:

| Changed area | Adjacent files |
| --- | --- |
| Product Truth / Drive setup | test_product_truth.py, test_info_help.py, test_google_drive_connection_service.py, test_google_drive_oauth_callback_app.py, test_google_drive_oauth_callback_service.py, test_google_drive_oauth_state_service.py, test_google_drive_setup_commands.py |
| Top-level invoice routing | test_invoice_intent_prerouter.py, test_active_fsm_guard.py, test_voice_state_routing.py, test_decision_resolver.py |
| Work-time routing | test_work_time_routing.py, test_work_time_service.py, test_voice_state_routing.py, test_decision_resolver.py |
| Contact normalization | test_contact_lookup_normalization.py, test_contact_registry_flow.py, test_contact_registry_services.py, test_workspace_contact_service.py |
| Customization admin authorization | test_customization_request_admin.py, test_customization_requests.py, test_access_request_flow.py, test_tenant_safety.py |
| Import boundaries | test_architecture_import_boundaries.py plus the owning module test files |

### Full Python suite

Mandatory PR validation:

~~~powershell
python -m pytest -q
~~~

The default command does not exclude marked or unmarked ordinary tests.

### Integration

Tests already classified with real temporary SQLite, filesystem, process, or
multi-component boundaries:

~~~powershell
python -m pytest -q -m integration
~~~

Marker coverage is not yet complete, so this selection supplements rather than
replaces the full suite.

### Acceptance

Deterministic public-entry journeys:

~~~powershell
python -m pytest -q -m acceptance
~~~

Acceptance marker coverage is not yet complete. Existing conversation proof
documents and unmarked handler journeys remain authoritative where applicable.

### External opt-in

Real third-party boundary checks:

~~~powershell
python -m pytest -q -m external
~~~

External coverage is incomplete and requires explicit credentials, redaction,
and a safe environment. Ordinary PR tests must not make live provider calls.

### Server smoke

Bounded post-deploy checks:

~~~powershell
python -m pytest -q -m server_smoke
~~~

Server-smoke coverage is incomplete. Never target production by default, and
do not treat this command as deploy, restart, or production-write approval.
