from __future__ import annotations

import ast
import inspect

import pytest

from bot.services import product_truth
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import AccountTruthStatus, ProductTruthStatus


REQUIRED_MVP_CAPABILITY_IDS = {
    'create_invoice',
    'show_existing_invoice',
    'edit_existing_invoice',
    'delete_existing_invoice',
    'mark_existing_invoice_paid',
    'invoice_due_date_reminders',
    'invoice_pdf_generation',
    'invoice_pdf_custom_template',
    'send_invoice_email',
    'gmail_statement_collection',
    'google_drive_invoice_storage',
    'google_drive_invoice_archive_after_due_date',
    'sms_reminders',
    'accounting_export',
    'supplier_profile',
    'edit_supplier_profile',
    'contacts',
    'service_aliases',
    'add_receipt_or_incoming_invoice',
    'accounting_document_categories',
    'show_recent_accounting_documents',
    'officeflow_idle_attachment_router',
    'voice_invoice_intake',
    'delete_user_database',
    'customization_requests',
    'admin_customization_review',
    'admin_response_to_user',
    'admin_response_delivery_observability',
    'access_request_approval',
    'invoice_draft_edit_flow',
    'invoice_analytics',
    'accounting_document_analytics',
    'receipt_analytics',
    'bank_cashflow_tax_analytics',
    'code_agent_handoff',
    'self_learning_aliases',
    'info_help',
}

NOT_SUPPORTED_CAPABILITY_IDS = {
    'send_invoice_email',
    'sms_reminders',
    'accounting_export',
    'bank_cashflow_tax_analytics',
    'invoice_pdf_custom_template',
    'code_agent_handoff',
}

EXTERNAL_CREDENTIAL_CAPABILITY_IDS = {
    'send_invoice_email',
    'gmail_statement_collection',
    'google_drive_invoice_storage',
    'google_drive_invoice_archive_after_due_date',
    'sms_reminders',
    'accounting_export',
}

DANGEROUS_CAPABILITY_IDS = {
    'delete_existing_invoice',
    'delete_user_database',
    'code_agent_handoff',
}


def _registry_by_id():
    return {entry.capability_id: entry for entry in product_truth.list_capabilities()}


def test_registry_loads_and_validates() -> None:
    assert product_truth.list_capabilities()
    assert product_truth.validate_registry() == ()


def test_capability_ids_are_unique() -> None:
    capability_ids = [entry.capability_id for entry in product_truth.list_capabilities()]
    assert len(capability_ids) == len(set(capability_ids))


def test_required_mvp_capability_ids_are_present() -> None:
    assert REQUIRED_MVP_CAPABILITY_IDS <= set(_registry_by_id())


def test_all_statuses_are_allowed_primary_product_statuses() -> None:
    allowed_statuses = {status.value for status in ProductTruthStatus}
    assert allowed_statuses == {'supported', 'partial', 'planned', 'unsupported', 'unknown'}
    for entry in product_truth.list_capabilities():
        assert entry.status.value in allowed_statuses


def test_supported_entries_have_runtime_evidence() -> None:
    for entry in product_truth.list_capabilities():
        if entry.status == ProductTruthStatus.SUPPORTED:
            assert entry.runtime_owner, entry.capability_id
            assert entry.truth_source_refs, entry.capability_id
            assert entry.test_refs, entry.capability_id


def test_unsupported_and_planned_entries_do_not_claim_implemented_handlers() -> None:
    for entry in product_truth.list_capabilities():
        if entry.status in {ProductTruthStatus.UNSUPPORTED, ProductTruthStatus.PLANNED}:
            assert entry.runtime_owner is None, entry.capability_id
            assert entry.linked_handlers == (), entry.capability_id
            assert entry.canonical_actions == (), entry.capability_id


def test_risky_future_capabilities_are_not_supported() -> None:
    entries = _registry_by_id()
    for capability_id in NOT_SUPPORTED_CAPABILITY_IDS:
        assert entries[capability_id].status != ProductTruthStatus.SUPPORTED


def test_dangerous_capabilities_have_flag_and_safe_next_steps() -> None:
    entries = _registry_by_id()
    for capability_id in DANGEROUS_CAPABILITY_IDS:
        entry = entries[capability_id]
        assert entry.dangerous is True
        assert entry.safe_next_steps


def test_external_integrations_have_credential_flags_and_forbidden_claims() -> None:
    entries = _registry_by_id()
    for capability_id in EXTERNAL_CREDENTIAL_CAPABILITY_IDS:
        entry = entries[capability_id]
        assert entry.status in {ProductTruthStatus.UNSUPPORTED, ProductTruthStatus.PARTIAL}
        assert entry.requires_external_credentials is True
        assert entry.forbidden_claims


def test_info_help_record_matches_partial_product_truth_runtime() -> None:
    entry = _registry_by_id()['info_help']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert 'bounded contextual recovery' in entry.summary_for_user
    assert 'partial Level 2 foundation' in entry.current_limitations[0]
    assert 'one no-retry contextual recovery call' in entry.current_limitations[0]
    assert 'process memory only' in entry.current_limitations[1]
    assert 'ten-minute TTL' in entry.current_limitations[1]
    assert 'Python validates IDs' in entry.current_limitations[2]
    assert 'never switches directly' in entry.current_limitations[3]
    assert 'deployed multilingual/noisy Telegram acceptance' in entry.current_limitations[4]
    assert 'contextual_info_help_recovery.py' in (entry.runtime_owner or '')
    assert 'tests/test_info_help.py' in entry.test_refs
    assert 'tests/test_contextual_info_help_recovery.py' in entry.test_refs
    assert entry.last_verified_at == '2026-08-02'
    assert 'I answered from Product Truth in the live bot.' not in entry.forbidden_claims
    assert 'InfoHelp Level 2 is complete.' in entry.forbidden_claims
    assert 'I can answer any product capability question.' in entry.forbidden_claims
    assert 'InfoHelp saved your customization request.' in entry.forbidden_claims
    assert 'InfoHelp sent an admin response.' in entry.forbidden_claims


def test_customization_requests_record_matches_partial_human_review_runtime() -> None:
    entry = _registry_by_id()['customization_requests']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert 'confirmation-gated capture' in entry.summary_for_user
    assert 'admin list/detail' in entry.current_limitations[0]
    assert 'answer-only admin response-to-user' in entry.current_limitations[0]
    assert 'No automatic implementation' in entry.current_limitations[1]
    assert 'Product Truth mutation' in entry.current_limitations[1]
    assert 'code-agent handoff' in entry.current_limitations[1]
    assert 'auto retry' in entry.current_limitations[1]
    assert '/customization_request_reply' in entry.commands
    assert 'tests/test_customization_request_admin.py' in entry.test_refs
    assert 'This feature will be implemented.' in entry.forbidden_claims
    assert 'Product Truth was updated.' in entry.forbidden_claims
    assert 'A code-agent task was created.' in entry.forbidden_claims
    assert 'Complete Level 3 customization layer is available.' in entry.forbidden_claims


def test_admin_response_records_exist_with_honest_partial_limits() -> None:
    entries = _registry_by_id()
    response = entries['admin_response_to_user']
    observability = entries['admin_response_delivery_observability']

    assert response.status == ProductTruthStatus.PARTIAL
    assert 'answer-kind response' in response.summary_for_user
    assert 'answer kind only' in response.current_limitations[0]
    assert 'no threaded history' in response.current_limitations[0]
    assert 'no auto retry' in response.current_limitations[0]
    assert 'Admin replies are guaranteed to arrive.' in response.forbidden_claims
    assert 'The answer makes the feature supported.' in response.forbidden_claims

    assert observability.status == ProductTruthStatus.PARTIAL
    assert 'not_started' in observability.summary_for_user
    assert 'send_pending' in observability.summary_for_user
    assert 'send_failed' in observability.summary_for_user
    assert 'no retry command' in observability.current_limitations[0]
    assert 'The bot will retry automatically.' in observability.forbidden_claims


def test_access_request_and_invoice_draft_records_exist() -> None:
    entries = _registry_by_id()

    assert entries['access_request_approval'].status == ProductTruthStatus.SUPPORTED
    assert entries['access_request_approval'].requires_admin is True
    assert 'Pending access means business access is active.' in entries['access_request_approval'].forbidden_claims

    assert entries['invoice_draft_edit_flow'].status == ProductTruthStatus.SUPPORTED
    assert 'edit/approve/cancel' in entries['invoice_draft_edit_flow'].summary_for_user
    assert 'tests/test_decision_callbacks.py' in entries['invoice_draft_edit_flow'].test_refs


def test_invoice_due_date_reminders_record_is_partial_automatic_runtime() -> None:
    entry = _registry_by_id()['invoice_due_date_reminders']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.commands == ()
    assert 'background scheduler' in entry.current_limitations[0]
    assert 'invoice_followup_scheduler.py' in (entry.runtime_owner or '')
    assert 'No email, SMS' in entry.current_limitations[2]
    assert 'owner OAuth' in entry.current_limitations[2]
    assert 'Overdue invoice reminders use email or SMS.' in entry.forbidden_claims
    assert 'I archived the invoice to Google Drive.' in entry.forbidden_claims


def test_invoice_analytics_record_is_partial_read_only_runtime() -> None:
    entry = _registry_by_id()['invoice_analytics']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.commands == ()
    assert entry.canonical_actions == ('invoice_analytics',)
    assert 'read-only' in entry.summary_for_user
    assert 'saved outgoing invoices' in entry.summary_for_user
    assert 'bot/services/invoice_analytics_dataset.py' in entry.linked_handlers
    assert 'bot/services/safe_python_analytics_executor.py' in entry.linked_handlers
    assert 'docs/llm/Invoice_Analytics_Runtime_Contract.md' in entry.truth_source_refs
    assert 'docs/llm/Safe_Data_Analyst_Runtime_Checklist.md' in entry.truth_source_refs
    assert 'tests/test_invoice_analytics_dataset.py' in entry.test_refs
    assert 'tests/test_safe_python_analytics_executor.py' in entry.test_refs
    assert 'tests/test_invoice_analytics_answerer.py' in entry.test_refs
    assert any('receipts' in limitation.lower() for limitation in entry.current_limitations)
    assert any('bank' in limitation.lower() for limitation in entry.current_limitations)
    assert any('Slovak' in limitation for limitation in entry.current_limitations)
    assert 'I analyzed receipts or incoming invoices.' in entry.forbidden_claims
    assert 'I changed invoice status or edited invoices from analytics.' in entry.forbidden_claims
    assert 'I answered invoice analytics in Ukrainian because the user wrote Ukrainian.' in entry.forbidden_claims
    assert 'This is full accounting analytics.' in entry.forbidden_claims


def test_accounting_document_analytics_record_is_partial_read_only_runtime() -> None:
    entry = _registry_by_id()['accounting_document_analytics']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.runtime_owner == 'bot/handlers/invoice.py::_run_accounting_document_analytics'
    assert entry.commands == ()
    assert entry.canonical_actions == ('accounting_document_analytics',)
    assert 'read-only' in entry.summary_for_user
    assert 'receipts and incoming invoices' in entry.summary_for_user
    assert 'bot/services/accounting_document_analytics_dataset.py' in entry.linked_handlers
    assert 'bot/services/accounting_document_analytics_planner.py' in entry.linked_handlers
    assert 'bot/services/accounting_document_analytics_executor.py' in entry.linked_handlers
    assert 'tests/test_accounting_document_analytics_dataset.py' in entry.test_refs
    assert 'tests/test_accounting_document_analytics_planner.py' in entry.test_refs
    assert any('current workspace' in limitation for limitation in entry.current_limitations)
    assert any('VAT/tax reports' in limitation for limitation in entry.current_limitations)
    assert 'I changed a receipt, incoming invoice, category, file, or database row from analytics.' in entry.forbidden_claims
    assert 'This is full accounting analytics.' in entry.forbidden_claims


def test_receipt_analytics_record_is_partial_alias_for_accounting_document_runtime() -> None:
    entry = _registry_by_id()['receipt_analytics']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.runtime_owner == 'bot/handlers/invoice.py::_run_accounting_document_analytics'
    assert entry.commands == ()
    assert entry.canonical_actions == ('accounting_document_analytics',)
    assert 'accounting_document_analytics' in entry.summary_for_user
    assert 'bot/services/accounting_document_analytics_dataset.py' in entry.linked_handlers
    assert 'tests/test_accounting_document_analytics_executor.py' in entry.test_refs
    assert any('No bank matching' in limitation for limitation in entry.current_limitations)
    assert 'I changed receipt metadata from analytics.' in entry.forbidden_claims


def test_accounting_document_categories_record_is_partial_controlled_runtime() -> None:
    entry = _registry_by_id()['accounting_document_categories']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.commands == ()
    assert entry.canonical_actions == ()
    assert 'controlled document category' in entry.summary_for_user
    assert 'not a top-level action' in entry.current_limitations[0]
    assert 'Python-provided allowed categories' in entry.current_limitations[1]
    assert 'Workspace custom categories' in entry.current_limitations[2]
    assert 'No tax deductibility' in entry.current_limitations[3]
    assert 'bot/services/accounting_document_categories.py' in entry.linked_handlers
    assert 'tests/test_accounting_document_categories.py' in entry.test_refs
    assert 'The model saved or created a category directly.' in entry.forbidden_claims
    assert 'I generated receipt analytics from categories.' in entry.forbidden_claims


def test_bank_cashflow_tax_analytics_record_is_unsupported() -> None:
    entry = _registry_by_id()['bank_cashflow_tax_analytics']

    assert entry.status == ProductTruthStatus.UNSUPPORTED
    assert entry.runtime_owner is None
    assert entry.commands == ()
    assert entry.canonical_actions == ()
    assert 'not implemented' in entry.summary_for_user
    assert any('bank statement intake' in limitation for limitation in entry.current_limitations)
    assert any('cashflow model' in limitation for limitation in entry.current_limitations)
    assert any('tax advice' in limitation for limitation in entry.current_limitations)
    assert 'I analyzed bank movements.' in entry.forbidden_claims
    assert 'I produced a VAT or tax report.' in entry.forbidden_claims
    assert 'This is full accounting analytics.' in entry.forbidden_claims


def test_gmail_statement_collection_is_honest_partial_runtime() -> None:
    entry = _registry_by_id()['gmail_statement_collection']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.requires_external_credentials is True
    assert entry.requires_admin is True
    assert 'gmail.readonly' in entry.current_limitations[1]
    assert 'parse_status=deferred' in entry.current_limitations[3]
    assert 'gmail_statement_scheduler.py' in (entry.runtime_owner or '')
    assert 'A collected statement was parsed or reconciled.' in entry.forbidden_claims


def test_google_drive_after_due_date_archive_record_is_partial_owner_oauth() -> None:
    entry = _registry_by_id()['google_drive_invoice_archive_after_due_date']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.requires_external_credentials is True
    assert entry.requires_admin is True
    assert 'invoice_drive_archive_service.py' in (entry.runtime_owner or '')
    assert 'owner OAuth credentials' in entry.current_limitations[0]
    assert 'old local stub' in entry.current_limitations[1]
    assert 'not deleted locally' in entry.current_limitations[2]
    assert 'The invoice was uploaded to Drive before the worker reports uploaded.' in entry.forbidden_claims
    assert 'This is per-client Google OAuth Drive storage.' in entry.forbidden_claims
    assert 'Service-account mode works with personal My Drive.' in entry.forbidden_claims


def test_google_drive_invoice_storage_record_is_partial_owner_oauth() -> None:
    entry = _registry_by_id()['google_drive_invoice_storage']

    assert entry.status == ProductTruthStatus.PARTIAL
    assert entry.requires_external_credentials is True
    assert entry.requires_admin is True
    assert 'google_drive_archive_scheduler.py' in (entry.runtime_owner or '')
    assert 'not per-client OAuth' in entry.current_limitations[0]
    assert 'generated PDFs remain stored locally' in entry.current_limitations[1]
    assert 'Receipts and incoming invoices' in entry.current_limitations[2]
    assert any('owning workspace persisted Drive folder' in value for value in entry.current_limitations)
    assert any('existing remote files are not migrated' in value for value in entry.current_limitations)
    assert 'accounting_document_archive_path.py' in (entry.runtime_owner or '')
    assert 'All business profiles share one archive folder.' in entry.forbidden_claims
    assert 'A confirmed local save means the Drive upload already succeeded.' in entry.forbidden_claims
    assert any('Service-account mode is unsupported' in limitation for limitation in entry.current_limitations)
    assert 'This is per-client Google OAuth Drive storage.' in entry.forbidden_claims
    assert 'Service-account mode works with personal My Drive.' in entry.forbidden_claims


@pytest.mark.contract
def test_google_drive_invoice_storage_product_truth_is_partial_owner_oauth() -> None:
    result = product_truth.get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Can bot save invoices to Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.PARTIAL
    assert result.capability.runtime_owner is not None
    assert answer is not None


def test_create_invoice_returns_supported_with_account_setup_requirement() -> None:
    result = product_truth.get_capability(
        'create_invoice',
        account_context={
            'authorized_user': True,
            'supplier_profile': False,
            'service_alias': False,
            'contact': False,
        },
    )

    assert result.product_status == ProductTruthStatus.SUPPORTED
    assert result.account_status == AccountTruthStatus.REQUIRES_SETUP
    assert result.account_requires_setup is True
    assert result.account_requires_admin is False
    assert result.missing_setup_keys == ('supplier_profile', 'service_alias', 'contact')

    payload = product_truth.get_safe_answer_payload(
        'create_invoice',
        account_context={
            'authorized_user': True,
            'supplier_profile': False,
            'service_alias': False,
            'contact': False,
        },
    )
    assert payload['product_status'] == 'supported'
    assert payload['account_status'] == 'requires_setup'
    assert payload['requires_setup'] is True
    assert payload['missing_setup_keys'] == ['supplier_profile', 'service_alias', 'contact']


def test_unknown_capability_lookup_returns_structured_unknown() -> None:
    result = product_truth.get_capability('future_magic_feature')

    assert result.product_status == ProductTruthStatus.UNKNOWN
    assert result.account_status == AccountTruthStatus.UNKNOWN
    assert result.capability.capability_id == 'future_magic_feature'
    assert result.capability.runtime_owner is None
    assert result.capability.linked_handlers == ()

    payload = product_truth.get_safe_answer_payload('future_magic_feature')
    assert payload['capability_id'] == 'future_magic_feature'
    assert payload['product_status'] == 'unknown'
    assert payload['safe_next_steps']


def test_product_truth_module_has_no_runtime_side_effect_imports() -> None:
    source = inspect.getsource(product_truth)
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    imported_modules: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported_roots.add(alias.name.split('.', 1)[0])
                imported_modules.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split('.', 1)[0])
            imported_modules.add(node.module)

    assert imported_roots <= {'__future__', 'dataclasses', 'enum', 'typing'}
    assert not any(module == 'openai' or module.startswith('openai.') for module in imported_modules)
    assert not any(module == 'aiogram' or module.startswith('aiogram.') for module in imported_modules)
    assert not any(module == 'sqlite3' or module.startswith('sqlite3.') for module in imported_modules)
    assert not any(module == 'pathlib' or module.startswith('pathlib.') for module in imported_modules)
    assert not any(module == 'os' or module.startswith('os.') for module in imported_modules)
    assert not any(module == 'bot.handlers' or module.startswith('bot.handlers.') for module in imported_modules)
    assert not any(module == 'bot.config' or module.startswith('bot.config.') for module in imported_modules)
    assert not any(module == 'bot.services.db' for module in imported_modules)
    assert not any(module == 'bot.services.speech_to_text' for module in imported_modules)
    assert not any(module == 'bot.services.officeflow_attachment_lmm' for module in imported_modules)
    assert not any(module == 'bot.services.accounting_document_lmm' for module in imported_modules)


def test_mark_existing_invoice_paid_record_is_supported_confirmation_gated_runtime() -> None:
    entry = _registry_by_id()['mark_existing_invoice_paid']
    assert entry.status.value == 'supported'
    assert entry.canonical_actions == ('mark_existing_invoice_paid',)
    assert 'InvoiceFollowupService.mark_paid' in entry.runtime_owner
    assert any('bot-local payment state' in limitation for limitation in entry.current_limitations)
    assert any('bank payment' in claim.lower() or 'bank data' in claim.lower() for claim in entry.forbidden_claims)
