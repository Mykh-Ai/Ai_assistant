from __future__ import annotations

import json

import pytest

from bot.services.accounting_document_classifier import (
    AccountingDocumentClassifierParseError,
    parse_accounting_document_classification,
)


def test_valid_receipt_classifier_json_accepted() -> None:
    result = parse_accounting_document_classification(
        json.dumps(
            {
                'document_type': 'Receipt',
                'confidence': 'High',
                'reason': 'Cash register receipt is visible.',
            }
        )
    )

    assert result.document_type == 'receipt'
    assert result.confidence == 'high'
    assert result.reason == 'Cash register receipt is visible.'


def test_valid_incoming_invoice_classifier_json_accepted() -> None:
    result = parse_accounting_document_classification(
        json.dumps(
            {
                'document_type': ' incoming_invoice ',
                'confidence': 'medium',
                'reason': 'Invoice number and due date are visible.',
            }
        )
    )

    assert result.document_type == 'incoming_invoice'
    assert result.confidence == 'medium'


def test_unknown_classifier_json_accepted() -> None:
    result = parse_accounting_document_classification(
        json.dumps(
            {
                'document_type': 'unknown',
                'confidence': 'low',
                'reason': 'The document is unreadable.',
            }
        )
    )

    assert result.document_type == 'unknown'
    assert result.confidence == 'low'


def test_non_json_classifier_rejected() -> None:
    with pytest.raises(AccountingDocumentClassifierParseError, match='classification_not_json'):
        parse_accounting_document_classification('not json')


def test_unsupported_classifier_document_type_rejected() -> None:
    with pytest.raises(AccountingDocumentClassifierParseError, match='document_type_unsupported'):
        parse_accounting_document_classification(
            json.dumps({'document_type': 'bank_statement', 'confidence': 'high', 'reason': 'statement'})
        )


def test_unsupported_classifier_confidence_rejected() -> None:
    with pytest.raises(AccountingDocumentClassifierParseError, match='confidence_unsupported'):
        parse_accounting_document_classification(
            json.dumps({'document_type': 'receipt', 'confidence': 'certain', 'reason': 'receipt'})
        )
