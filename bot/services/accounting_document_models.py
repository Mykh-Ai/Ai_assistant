from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any


DOCUMENT_TYPE_RECEIPT = 'receipt'
DOCUMENT_TYPE_INCOMING_INVOICE = 'incoming_invoice'
DOCUMENT_TYPE_UNKNOWN = 'unknown'
DOCUMENT_TYPES = {
    DOCUMENT_TYPE_RECEIPT,
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_UNKNOWN,
}

PAYMENT_METHODS = {'cash', 'card', 'bank_transfer', 'unknown'}
READABILITY_VALUES = {'good', 'partial', 'poor'}


@dataclass(frozen=True)
class AccountingDocumentSource:
    input_type: str
    original_filename: str | None = None
    file_unique_id: str | None = None
    upload_date: date | str | None = None


@dataclass(frozen=True)
class AccountingDocumentQuality:
    readability: str = 'unknown'
    missing_fields: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AccountingDocumentCandidate:
    document_type: str
    vendor_name: str | None = None
    vendor_ico: str | None = None
    document_number: str | None = None
    issue_date: date | str | None = None
    tax_date: date | str | None = None
    due_date: date | str | None = None
    total_amount: Decimal | str | int | float | None = None
    currency: str | None = None
    vat_amount: Decimal | str | int | float | None = None
    iban: str | None = None
    variable_symbol: str | None = None
    payment_method: str | None = None
    category_candidate: str | None = None
    quality: AccountingDocumentQuality = field(default_factory=AccountingDocumentQuality)
    source: AccountingDocumentSource = field(default_factory=lambda: AccountingDocumentSource(input_type='unknown'))


def candidate_to_metadata_dict(candidate: AccountingDocumentCandidate) -> dict[str, Any]:
    def _date_value(value: date | str | None) -> str | None:
        if isinstance(value, date):
            return value.isoformat()
        if value is None:
            return None
        return str(value)

    def _decimal_value(value: Decimal | str | int | float | None) -> str | None:
        if value is None:
            return None
        return str(value)

    return {
        'document_type': candidate.document_type,
        'source': {
            'input_type': candidate.source.input_type,
            'original_filename': candidate.source.original_filename,
            'file_unique_id': candidate.source.file_unique_id,
            'upload_date': _date_value(candidate.source.upload_date),
        },
        'business': {
            'vendor_name': candidate.vendor_name,
            'vendor_ico': candidate.vendor_ico,
            'document_number': candidate.document_number,
            'issue_date': _date_value(candidate.issue_date),
            'tax_date': _date_value(candidate.tax_date),
            'due_date': _date_value(candidate.due_date),
            'total_amount': _decimal_value(candidate.total_amount),
            'currency': candidate.currency,
            'vat_amount': _decimal_value(candidate.vat_amount),
            'iban': candidate.iban,
            'variable_symbol': candidate.variable_symbol,
            'payment_method': candidate.payment_method,
            'category_candidate': candidate.category_candidate,
        },
        'quality': {
            'readability': candidate.quality.readability,
            'missing_fields': list(candidate.quality.missing_fields),
            'warnings': list(candidate.quality.warnings),
        },
    }
