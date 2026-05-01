from __future__ import annotations

from decimal import Decimal

from bot.services.accounting_document_models import (
    AccountingDocumentCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
)
from bot.services.accounting_document_validation import validate_accounting_document_candidate


def _source() -> AccountingDocumentSource:
    return AccountingDocumentSource(input_type='pdf', original_filename='doc.pdf', file_unique_id='file-1')


def test_valid_receipt_passes_validation() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Tesco',
        issue_date='2026-05-01',
        total_amount=Decimal('24.90'),
        currency='EUR',
        payment_method='card',
        source=_source(),
    )

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is True
    assert result.errors == []
    assert result.normalized_total_amount == Decimal('24.90')
    assert result.normalized_currency == 'EUR'


def test_receipt_missing_amount_vendor_date_blocks_save() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name=' ',
        issue_date=None,
        total_amount=None,
        currency='EUR',
        source=_source(),
    )

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is False
    assert 'vendor_name_required' in result.errors
    assert 'issue_date_required' in result.errors
    assert 'total_amount_required_positive' in result.errors


def test_valid_incoming_invoice_passes_validation() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='incoming_invoice',
        vendor_name='Stredoslovenska energetika',
        document_number='202605001',
        issue_date='2026-05-01',
        due_date='2026-05-15',
        total_amount='118.42',
        currency='EUR',
        iban='SK3112000000198742637541',
        variable_symbol='202605001',
        source=_source(),
    )

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is True
    assert result.errors == []
    assert result.normalized_total_amount == Decimal('118.42')


def test_incoming_invoice_missing_document_number_blocks_save() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='incoming_invoice',
        vendor_name='Vendor',
        document_number='',
        issue_date='2026-05-01',
        total_amount='10.00',
        currency='EUR',
        source=_source(),
    )

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is False
    assert 'document_number_required' in result.errors


def test_invalid_date_blocks_save() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Tesco',
        issue_date='2026-99-01',
        total_amount='24.90',
        currency='EUR',
        source=_source(),
    )

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is False
    assert 'issue_date_invalid' in result.errors


def test_negative_or_zero_amount_blocks_save() -> None:
    for value in ('0', '-1.00'):
        candidate = AccountingDocumentCandidate(
            document_type='receipt',
            vendor_name='Tesco',
            issue_date='2026-05-01',
            total_amount=value,
            currency='EUR',
            source=_source(),
        )

        result = validate_accounting_document_candidate(candidate)

        assert result.can_save is False
        assert 'total_amount_required_positive' in result.errors


def test_missing_currency_blocks_unless_safe_default_is_allowed() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Tesco',
        issue_date='2026-05-01',
        total_amount='24.90',
        currency=None,
        source=_source(),
    )

    blocked = validate_accounting_document_candidate(candidate)
    defaulted = validate_accounting_document_candidate(candidate, allow_safe_eur_default=True)

    assert blocked.can_save is False
    assert 'currency_required' in blocked.errors
    assert defaulted.can_save is True
    assert defaulted.normalized_currency == 'EUR'
    assert 'currency_defaulted_to_eur' in defaulted.warnings


def test_unknown_document_type_cannot_save() -> None:
    candidate = AccountingDocumentCandidate(
        document_type='unknown',
        vendor_name='Tesco',
        issue_date='2026-05-01',
        total_amount='24.90',
        currency='EUR',
        source=_source(),
        quality=AccountingDocumentQuality(readability='poor'),
    )

    result = validate_accounting_document_candidate(candidate)

    assert result.can_save is False
    assert 'document_type_unknown' in result.errors
    assert 'readability_poor_requires_review' in result.warnings
