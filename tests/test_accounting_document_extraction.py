from __future__ import annotations

from decimal import Decimal
import json

import pytest

from bot.services.accounting_document_extraction import (
    AccountingDocumentExtractionParseError,
    parse_accounting_document_extraction,
)
from bot.services.accounting_document_validation import validate_accounting_document_candidate


def _receipt_payload() -> dict:
    return {
        'document_type': 'receipt',
        'source': {
            'input_type': 'photo',
            'original_filename': 'receipt.jpg',
        },
        'business': {
            'vendor_name': 'Tesco',
            'vendor_ico': None,
            'document_number': None,
            'issue_date': '2026-05-01',
            'tax_date': None,
            'due_date': None,
            'total_amount': 24.90,
            'currency': 'eur',
            'vat_amount': '4.15',
            'iban': None,
            'variable_symbol': None,
            'payment_method': 'card',
            'purchase_subject': 'Potraviny a drogéria',
        },
        'quality': {
            'readability': 'good',
            'missing_fields': [],
            'warnings': [],
        },
        'trace': {
            'raw_visible_text_excerpt': 'TESCO 24,90 EUR',
        },
    }


def _incoming_invoice_payload() -> dict:
    return {
        'document_type': 'incoming_invoice',
        'source': {
            'input_type': 'pdf',
            'original_filename': 'invoice.pdf',
        },
        'business': {
            'vendor_name': 'Stredoslovenska energetika',
            'vendor_ico': '12345678',
            'document_number': '202605001',
            'issue_date': '2026-05-01',
            'tax_date': '2026-05-01',
            'due_date': '2026-05-15',
            'total_amount': '118,42',
            'currency': 'EUR',
            'vat_amount': '19.74',
            'iban': 'SK3112000000198742637541',
            'variable_symbol': '202605001',
            'payment_method': 'bank_transfer',
            'purchase_subject': 'Dodávka elektrickej energie',
        },
        'quality': {
            'readability': 'partial',
            'missing_fields': [],
            'warnings': ['iban read from visible text'],
        },
        'trace': {
            'raw_visible_text_excerpt': 'Faktura 202605001',
        },
    }


def test_valid_receipt_extraction_json_accepted_and_converted_to_candidate() -> None:
    candidate = parse_accounting_document_extraction(json.dumps(_receipt_payload()))

    assert candidate.document_type == 'receipt'
    assert candidate.vendor_name == 'Tesco'
    assert candidate.total_amount == Decimal('24.9')
    assert candidate.vat_amount == Decimal('4.15')
    assert candidate.currency == 'EUR'
    assert candidate.payment_method == 'card'
    assert candidate.purchase_subject == 'Potraviny a drogéria'
    assert candidate.source.input_type == 'photo'


def test_valid_incoming_invoice_extraction_json_accepted_and_converted_to_candidate() -> None:
    candidate = parse_accounting_document_extraction(json.dumps(_incoming_invoice_payload()))

    assert candidate.document_type == 'incoming_invoice'
    assert candidate.vendor_name == 'Stredoslovenska energetika'
    assert candidate.document_number == '202605001'
    assert candidate.total_amount == Decimal('118.42')
    assert candidate.payment_method == 'bank_transfer'
    assert candidate.quality.readability == 'partial'
    assert candidate.quality.warnings == ['iban read from visible text']


def test_extraction_result_can_be_passed_to_existing_validation() -> None:
    candidate = parse_accounting_document_extraction(json.dumps(_incoming_invoice_payload()))

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is True
    assert result.errors == []


def test_non_json_extraction_rejected() -> None:
    with pytest.raises(AccountingDocumentExtractionParseError, match='extraction_not_json'):
        parse_accounting_document_extraction('not json')


def test_unsupported_extraction_document_type_rejected() -> None:
    payload = _receipt_payload()
    payload['document_type'] = 'bank_statement'

    with pytest.raises(AccountingDocumentExtractionParseError, match='document_type_unsupported'):
        parse_accounting_document_extraction(json.dumps(payload))


def test_unsupported_payment_method_rejected() -> None:
    payload = _receipt_payload()
    payload['business']['payment_method'] = 'crypto'

    with pytest.raises(AccountingDocumentExtractionParseError, match='payment_method_unsupported'):
        parse_accounting_document_extraction(json.dumps(payload))


def test_unsupported_readability_rejected() -> None:
    payload = _receipt_payload()
    payload['quality']['readability'] = 'perfect'

    with pytest.raises(AccountingDocumentExtractionParseError, match='readability_unsupported'):
        parse_accounting_document_extraction(json.dumps(payload))


def test_side_effect_top_level_fields_rejected() -> None:
    payload = _receipt_payload()
    payload['saved_path'] = 'storage/workspaces/mykhailo-szco/years/2026/expenses/05/file.jpg'

    with pytest.raises(AccountingDocumentExtractionParseError, match='side_effect_field_forbidden:saved_path'):
        parse_accounting_document_extraction(json.dumps(payload))


def test_category_candidates_and_line_items_are_candidate_only() -> None:
    payload = _receipt_payload()
    payload['document_category_candidate'] = {
        'category_id': 'office_supplies',
        'confidence': 'medium',
        'review_required': False,
        'reason': 'visible office supply text',
    }
    payload['suggested_new_categories'] = [
        {'label_sk': 'Špeciálne kancelárske nákupy', 'reason': 'more specific label'},
        {'label_sk': 'Extra ignored'},
        {'label_sk': 'Third'},
        {'label_sk': 'Fourth ignored'},
    ]
    payload['line_items'] = [
        {
            'description': 'papier',
            'amount': '12.00',
            'currency': 'EUR',
            'vat_amount': '2.00',
            'category_candidate': {
                'category_id': 'office_supplies',
                'confidence': 'high',
                'review_required': False,
            },
        }
    ]

    candidate = parse_accounting_document_extraction(
        json.dumps(payload),
        allowed_category_ids={'office_supplies', 'unknown_review'},
    )

    assert candidate.document_category_candidate is not None
    assert candidate.document_category_candidate.category_id == 'office_supplies'
    assert candidate.document_category_candidate.confidence == 'medium'
    assert candidate.category is None
    assert [suggestion.label_sk for suggestion in candidate.suggested_new_categories] == [
        'Špeciálne kancelárske nákupy',
        'Extra ignored',
        'Third',
    ]
    assert candidate.line_items[0].description == 'papier'
    assert candidate.line_items[0].category_candidate is not None
    assert candidate.line_items[0].category_candidate.category_id == 'office_supplies'
    assert candidate.line_items[0].category is None


def test_invalid_category_candidate_falls_back_to_unknown_review() -> None:
    payload = _receipt_payload()
    payload['document_category_candidate'] = {
        'category_id': 'invented_model_category',
        'confidence': 'high',
        'review_required': False,
    }

    candidate = parse_accounting_document_extraction(
        json.dumps(payload),
        allowed_category_ids={'materials', 'unknown_review'},
    )

    assert candidate.document_category_candidate is not None
    assert candidate.document_category_candidate.category_id == 'unknown_review'
    assert candidate.document_category_candidate.confidence == 'low'
    assert candidate.document_category_candidate.review_required is True


@pytest.mark.parametrize('field_name', ['final_category', 'saved_category', 'category_created', 'confirmed', 'db_id'])
def test_category_side_effect_fields_are_rejected_anywhere(field_name: str) -> None:
    payload = _receipt_payload()
    payload['line_items'] = [{'description': 'papier', field_name: 'materials'}]

    with pytest.raises(AccountingDocumentExtractionParseError, match=f'side_effect_field_forbidden:{field_name}'):
        parse_accounting_document_extraction(json.dumps(payload), allowed_category_ids={'materials'})


def test_suggested_new_categories_must_not_create_ids() -> None:
    payload = _receipt_payload()
    payload['suggested_new_categories'] = [{'label_sk': 'Nová kategória', 'category_id': 'workspace_new'}]

    with pytest.raises(AccountingDocumentExtractionParseError, match='suggested_new_category_id_forbidden'):
        parse_accounting_document_extraction(json.dumps(payload))


def test_purchase_subject_is_raw_fact_not_category() -> None:
    payload = _receipt_payload()
    payload['business']['purchase_subject'] = 'Kancelárske potreby'

    candidate = parse_accounting_document_extraction(json.dumps(payload))

    assert candidate.purchase_subject == 'Kancelárske potreby'
    assert candidate.category is None
    assert candidate.document_category_candidate is None
    assert validate_accounting_document_candidate(candidate).can_save is True


def test_legacy_category_candidate_is_read_as_purchase_subject_only() -> None:
    payload = _receipt_payload()
    payload['business'].pop('purchase_subject')
    payload['business']['category_candidate'] = 'office supplies'

    candidate = parse_accounting_document_extraction(json.dumps(payload))

    assert candidate.purchase_subject == 'office supplies'
    assert candidate.document_category_candidate is None


def test_asfinag_vignette_subject_is_factual_purchase_subject() -> None:
    payload = _receipt_payload()
    payload['business'].update(
        {
            'vendor_name': 'ASFINAG',
            'vendor_ico': 'ATU 43143200',
            'document_number': '80046117600044',
            'issue_date': '2026-03-14',
            'tax_date': '2026-03-14',
            'total_amount': '9.60',
            'currency': 'EUR',
            'vat_amount': '0.00',
            'payment_method': 'card',
            'purchase_subject': '1-dňová diaľničná známka Rakúsko - osobné vozidlo',
        }
    )

    candidate = parse_accounting_document_extraction(json.dumps(payload))

    assert candidate.vendor_name == 'ASFINAG'
    assert candidate.purchase_subject == '1-dňová diaľničná známka Rakúsko - osobné vozidlo'
    assert candidate.category is None
    assert candidate.document_category_candidate is None
    assert validate_accounting_document_candidate(candidate).can_save is True
