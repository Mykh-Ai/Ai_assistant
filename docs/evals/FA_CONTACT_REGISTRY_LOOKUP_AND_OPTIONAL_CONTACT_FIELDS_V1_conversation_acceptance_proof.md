# FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1 Conversation Acceptance Proof

Verdict: `safe_to_commit`

This verdict means the applicable local automated journeys pass and no known implementation defect or unapproved material design deviation remains. It is not permission to commit, push, migrate production data, configure production, restart, or deploy.

## Evidence boundary

- Approved architecture: `docs/architecture/FA_CONTACT_REGISTRY_LOOKUP_AND_OPTIONAL_CONTACT_FIELDS_V1_ARCHITECTURE_DESIGN_PROOF.md`, verdict `ready_for_handoff`.
- Audited baseline `main` HEAD before changes: `f4415cdf71bedf370aa5f141c7abee8efff80cb4`.
- Delivery state: task commit `ba2d0dc` was pushed to `origin/main`. Pre-existing local edits in `PROJECT_LOG.md` and `tests/test_access_workspace_reactivation.py` remain unstaged and were not included.
- Environment: Windows/PowerShell, local temporary SQLite fixtures, synthetic actors/workspaces/companies.
- External boundary: automated tests use fakes and never call the internet. Read-only audit manually verified HTTP 200 and current JSON shape for official RPO search/detail on 2026-07-17. No Financial Administration API key was configured and that provider was not added.
- No production Telegram user, workspace, contact, invoice, DB, storage, credential, or server state was read or changed by implementation tests.

## Public-entry and task scenarios A-J

### A. Exact company by IČO

- Precondition: synthetic authorized actor, active workspace/profile, registry enabled, fake one-result RPO provider.
- Entry/inputs: shared `/contact` owner via `start_add_contact_intake`; text `87654321`; button `supplement`; typed DIČ `0987654321`, email, spaced lowercase IBAN, contact person; button `save`; canonical decision `yes`.
- Guards/owners: workspace bound before fake request; `contact_name_hint` -> `SlovakCompanyRegistry` boundary -> registry detail preview -> typed registry states -> `RegistryContactSaveService`.
- FSM: `name_hint` -> `registry_detail_preview` -> `registry_required_dic` -> three optional states -> `registry_detail_preview` -> `registry_final_confirm` -> cleared.
- Side effect: zero rows through preview and final-confirm state; exactly one workspace contact after `yes`.
- Observed output: official name/address retained, missing DIČ requested, IČ DPH shown/saved null, normalized IBAN visible, final success message.
- Evidence: `test_exact_registry_result_requires_typed_dic_optionals_and_final_confirmation`; fake provider/local DB. Result: pass.

### B. Multiple similar names

- Input: broad text `bau` after the shared entry owner.
- Result: two distinguishing candidates with official name, IČO, and municipality; bounded inline payloads contain only nonce/index/action and no company data; no auto-selection and no write.
- Valid index selection loads only that subject detail. Invalid index, wrong nonce, wrong user, wrong workspace, repeated callback, and expired callback fail closed. Wrong-workspace validation is read-only and does not recreate a missing active-workspace selection.
- Evidence: `test_multiple_candidates_are_bounded_buttons_and_stale_callbacks_write_nothing`. Result: pass.

### C. No registry result

- Input: `Missing Company`; fake returns zero results.
- FSM/output: `registry_fallback` with retry/manual/PDF choices; original name can continue through manual source state.
- Side effect: no contact write.
- Evidence: `test_registry_error_and_zero_results_offer_manual_fallback_without_write`. Result: pass.

### D. Registry outage

- Input: company search; fake raises bounded `RegistryLookupError('registry_unavailable')`.
- Output: no stack trace/raw body; manual/PDF fallback remains available; workspace binding remains in session.
- Side effect: none.
- Evidence: same fallback test plus malformed provider-shape test. Result: pass.

### E. Non-DPH payer / unknown DPH status

- Fake official detail supplies no IČ DPH.
- Observed: preview displays `IČ DPH: -`; final row stores null. No `SK` plus DIČ construction exists in provider, handler, or merge owner.
- Evidence: exact-IČO flow and `test_registry_details_never_infer_dic_or_ic_dph`. Result: pass.

### F. Optional business fields

- Email, IBAN, and contact person can be typed or skipped; `vymazať` explicitly clears an existing local value. Contact IBAN is text-only, MOD-97 validated, and stored uppercase without spaces.
- All entered values appear in preview before final confirmation. Document-assisted IBAN is normalized and remains an unsaved preview draft.
- Evidence: exact-IČO flow, `test_registry_explicit_optional_replacement_and_clear`, `test_document_assisted_contact_iban_is_a_normalized_preview_draft`, `test_llm_extracted_iban_is_normalized_before_draft`, existing manual skip tests. Result: pass.

### G. Existing contact by IČO

- Precondition: existing same-IČO contact with email, IBAN, contact person, contract path, and referencing invoice.
- Result: transaction updates official fields on the same row; omitted optional values and contract path are preserved; contact id and invoice `contact_id` remain unchanged.
- Evidence: `test_registry_insert_and_update_preserve_identity_and_unsupplied_optional_fields`. Result: pass.

### H. Dangerous name collision

- Same exact name with different IČO returns `name_conflict`; name and IČO matching different rows returns `split_conflict`; duplicate same-IČO rows return `ico_conflict`.
- Result: final service re-checks inside `BEGIN IMMEDIATE`, raises bounded conflict, and performs no mutation.
- Evidence: `test_same_name_different_ico_is_refused_without_write`, `test_split_and_duplicate_ico_conflicts_are_refused`. Result: pass.

### I. Stale candidate button

- Wrong actor/workspace/nonce/index, expired session, replay after state transition, and callback after ordinary state loss return the safe stale-action path. Malformed/stale callbacks do not refresh activity or persist an active-workspace selection.
- Result: no DB or external write; candidate details are not fetched twice.
- Evidence: multi-candidate callback test and shared stale callback/state-control regression. Result: pass.

### J. Old manual journey

- Registry disabled or active workspace outside the pilot allowlist never constructs/calls the provider and continues through the existing manual source owner.
- Manual flow retains company name, IČO, DIČ, optional IČ DPH, validated address, optional email, new optional IBAN, contact person, shared confirmation, `/menu`, cancel, and inactivity timeout.
- PDF/contract intake remains available and now carries optional IBAN as a draft.
- Evidence: disabled/non-pilot test, `tests/test_contact_intake_semantic_flow.py`, voice/state-control focused regression. Result: pass.

## Remaining canonical acceptance matrix

| Requirement | Result and evidence |
|---|---|
| Commands converge | `/contact`, `/contact_add`, `/add_kontakt` are one `cmd_contact` registration; `test_all_contact_commands_share_one_registered_owner`. |
| Semantic/voice entry | Existing `add_contact` route still calls `start_add_contact_intake`; broad voice regression passes. Exact registry/tax/email/IBAN states are rejected before STT; final yes/no confirmation reuses the shared helper. |
| Missing/invalid slot | Missing DIČ enters `registry_required_dic`; invalid email/IBAN remains in its typed state with no write. Provider unusable address/detail falls back. |
| Canonical decisions | `contact_confirm`, `contact_intake_confirm`, and `contact_registry_confirm` are registered `yes_no` contexts; text/voice/buttons converge on shared handlers. |
| Active FSM/navigation | Candidate/preview/fallback consume only bounded buttons; exact states consume typed values; shared `/menu`, cancel, and five-minute inactivity expiry remain active. Accepted typed input and fully validated buttons refresh both shared contact and registry deadlines. |
| Nearby action/unknown | Registry remains an internal `add_contact` strategy; no new action token. Unsupported button/action/decision returns stale or unknown with no write. |
| Product Truth/InfoHelp no effect | Registry capability question resolves to `contacts` guidance and does not enter FSM or touch DB; `test_info_help_explains_registry_contact_support_and_limits`. |
| Unauthorized/tenant safety | Existing access middleware and workspace context remain the public gate; registry flow binds and revalidates actor membership and active workspace. Full access/workspace regressions pass. |
| Persisted-data safety | Fresh/legacy/workspace schemas add nullable `iban` once; repeated init is a no-op; rows, ids, invoice references are preserved; unknown shapes fail closed. |
| Unchanged shared layers | Supplier `validate_iban` is unchanged; contact uses a narrow validator. Invoice lookup/aliases, onboarding, document intake, shared callbacks, workspace migration, and state control pass focused/full regression. |

## Design-to-code map

| Architecture requirement | Runtime owner | Evidence |
|---|---|---|
| Existing action/entry owner | `bot/handlers/contacts.py::cmd_contact`, `start_add_contact_intake` | command and manual/semantic tests |
| Official deterministic provider | `bot/services/slovak_company_registry.py` | provider mapping/ranking/error/inactive tests; read-only live shape audit |
| Bounded async request | `_request_json` | timeout/status/size/JSON code inspection plus malformed/error fakes |
| FSM candidate/detail/optional flow | `ContactStates` and registry handlers | `tests/test_contact_registry_flow.py` |
| Callback ownership/expiry | `_validated_registry_callback`, `_refresh_registry_activity`, `WorkspaceContextService.resolve_for_user_readonly` | wrong actor/workspace/nonce/index/expiry/replay, no-selection-write, and activity-refresh tests |
| Contact IBAN model/storage | `db.py`, contact services/model, parser, handlers, validation | migration, workspace, manual/document tests |
| Conflict-safe transaction | `RegistryContactSaveService` | insert/update/preserve/conflict/invoice-reference tests |
| Product Truth/InfoHelp | `product_truth.py`, `info_help.py` | truth/guidance focused tests |
| Shared confirmation | `decision_resolver.py` consumers and decision callback router | DecisionResolver/callback/voice tests |

## Implementation variance

- Cache remains intentionally deferred, as approved in the architecture proof. Therefore no no-op cache TTL environment setting is exposed and no cache can become canonical contact storage.
- Provider aggregation is represented by one stable service boundary, but v1 implements only official RPO. The Financial Administration information-list API requires separate credentials/setup and was not added. Missing DIČ is typed; IČ DPH stays null unless an approved official source supplies it in a future slice.
- Product Truth status is `partial`, not fully supported, because registry lookup is disabled by default, optionally pilot-gated, and depends on an external official source. No architecture approval gap remains for the declared local scope.

## Post-review repairs

- Stale registry callback validation now resolves workspace context through a non-mutating service path. The regression deletes the actor's active selection before a wrong-workspace callback and proves the row remains absent.
- Registry inactivity now follows the shared five-minute contact inactivity contract. Accepted typed input and fully validated buttons refresh both deadlines; stale/malformed callbacks do not.
- AI/document-extracted IBAN is deterministically validated and normalized before either partial or complete draft storage. Invalid extracted values remain visible to the existing typed correction gate.
- These repairs do not expand capability status, provider scope, persistence shape, AI maturity, or deployment authorization.

## Verification

- Post-review targeted contact/registry/workspace regression: `python -m pytest -q tests/test_contact_registry_flow.py tests/test_contact_intake_semantic_flow.py tests/test_workspace_context.py` -> `33 passed in 19.01s`.
- Expanded focused registry/contact/workspace/migration/decision/state/voice/Product Truth regression: `python -m pytest -q tests/test_contact_registry_flow.py tests/test_contact_intake_semantic_flow.py tests/test_workspace_context.py tests/test_contact_registry_services.py tests/test_contact_iban_migration.py tests/test_decision_callbacks.py tests/test_state_control.py tests/test_voice_state_routing.py tests/test_contact_registry_truth.py` -> `139 passed in 36.37s`.
- Final full regression: `python -m pytest -q` -> `2204 passed, 7 subtests passed in 326.14s`.
- Runtime compile: `python -m compileall -q bot` -> pass.

## Delivery and production verification

- Runtime/audit commit 997d3e7 was pushed and fast-forwarded on the clean server checkout. Before restart, the repaired canonical dry-run reported public_profile_switch_ready=true, blocker_count=0, migration_required=false, apply_block_reason=database_already_migrated, and writes_performed=false. The Drive audit reported deployment_ready=true, blocker_count=0, and an unchanged DB hash.
- Verified pre-schema rollback backup: /var/backups/fakturabot/20260717T190725Z_997d3e7_contact_registry. Source and backup integrity are ok; backup SHA-256 is 587ccd95596bb5aad651d79f8df2d23435bb44be1274c08a532c2268625aeab4. The snapshot contains four contacts, nine invoices, and no contact.iban column.
- Docker rebuilt and recreated the FakturaBot container at 997d3e7. Startup logs show FakturaBot starting, Start polling, and Run polling; no recent ERROR, traceback, exception, or Telegram conflict was found. Host/container hashes match for the contact handler, registry provider, registry save owner, and migration audit repair.
- Post-deploy DB verification: integrity ok; contact.iban exists exactly once and is nullable; all four existing rows retain null IBAN; all table counts match the backup; nine invoices remain; orphan invoice contact references are zero.
- Post-deploy canonical dry-run remains ready with zero blockers and no writes. Drive audit remains ready with zero blockers and unchanged hash. A bounded live official-RPO smoke returned one exact-IČO candidate, bounded count, usable detail fields, and provider source metadata without printing company data or raw bodies.
- Runtime configuration remains fail-closed: contact registry lookup is disabled, pilot workspace count is zero, timeout is five seconds, and maximum results is five.

## Remaining acceptance gate

- No real Telegram pilot conversation was performed. Enabling the feature requires an explicit approved pilot workspace list and a controlled user journey; production code and additive schema are otherwise deployed and verified.