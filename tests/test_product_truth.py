from __future__ import annotations

import ast
import inspect

from bot.services import product_truth
from bot.services.product_truth import AccountTruthStatus, ProductTruthStatus


REQUIRED_MVP_CAPABILITY_IDS = {
    'create_invoice',
    'show_existing_invoice',
    'edit_existing_invoice',
    'delete_existing_invoice',
    'invoice_pdf_generation',
    'invoice_pdf_custom_template',
    'send_invoice_email',
    'google_drive_invoice_storage',
    'sms_reminders',
    'accounting_export',
    'supplier_profile',
    'edit_supplier_profile',
    'contacts',
    'service_aliases',
    'add_receipt_or_incoming_invoice',
    'show_recent_accounting_documents',
    'officeflow_idle_attachment_router',
    'voice_invoice_intake',
    'delete_user_database',
    'customization_requests',
    'code_agent_handoff',
    'self_learning_aliases',
    'info_help',
}

NOT_SUPPORTED_CAPABILITY_IDS = {
    'send_invoice_email',
    'google_drive_invoice_storage',
    'sms_reminders',
    'accounting_export',
    'invoice_pdf_custom_template',
    'customization_requests',
    'code_agent_handoff',
}

EXTERNAL_CREDENTIAL_CAPABILITY_IDS = {
    'send_invoice_email',
    'google_drive_invoice_storage',
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
        assert entry.status == ProductTruthStatus.UNSUPPORTED
        assert entry.requires_external_credentials is True
        assert entry.forbidden_claims


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
