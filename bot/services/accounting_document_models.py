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
CATEGORY_CONFIDENCE_VALUES = {'low', 'medium', 'high'}


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
class AccountingDocumentCategoryCandidate:
    category_id: str | None = None
    confidence: str = 'low'
    review_required: bool = False
    reason: str | None = None


@dataclass(frozen=True)
class AccountingDocumentSuggestedCategory:
    label_sk: str
    reason: str | None = None


@dataclass(frozen=True)
class AccountingDocumentConfirmedCategory:
    category_id: str
    label_snapshot: str
    source: str = 'user_confirmed'
    candidate_source: str | None = 'lmm'
    confidence: str | None = None
    review_required: bool = False


@dataclass(frozen=True)
class AccountingDocumentLineItemCandidate:
    description: str | None = None
    amount: Decimal | str | int | float | None = None
    currency: str | None = None
    vat_amount: Decimal | str | int | float | None = None
    category_candidate: AccountingDocumentCategoryCandidate | None = None
    suggested_new_categories: list[AccountingDocumentSuggestedCategory] = field(default_factory=list)
    category: AccountingDocumentConfirmedCategory | None = None


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
    purchase_subject: str | None = None
    document_category_candidate: AccountingDocumentCategoryCandidate | None = None
    suggested_new_categories: list[AccountingDocumentSuggestedCategory] = field(default_factory=list)
    line_items: list[AccountingDocumentLineItemCandidate] = field(default_factory=list)
    category: AccountingDocumentConfirmedCategory | None = None
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

    payload: dict[str, Any] = {
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
            'purchase_subject': candidate.purchase_subject,
        },
        'quality': {
            'readability': candidate.quality.readability,
            'missing_fields': list(candidate.quality.missing_fields),
            'warnings': list(candidate.quality.warnings),
        },
    }
    if candidate.document_category_candidate is not None:
        payload['document_category_candidate'] = _category_candidate_dict(candidate.document_category_candidate)
    if candidate.suggested_new_categories:
        payload['suggested_new_categories'] = [
            _suggested_category_dict(suggestion) for suggestion in candidate.suggested_new_categories[:3]
        ]
    if candidate.category is not None:
        payload['category'] = _confirmed_category_dict(candidate.category)
    if candidate.line_items:
        payload['line_items'] = [_line_item_dict(item) for item in candidate.line_items]
    return payload


def _category_candidate_dict(candidate: AccountingDocumentCategoryCandidate) -> dict[str, Any]:
    return {
        'category_id': candidate.category_id,
        'confidence': candidate.confidence,
        'review_required': candidate.review_required,
        'reason': candidate.reason,
    }


def _suggested_category_dict(suggestion: AccountingDocumentSuggestedCategory) -> dict[str, Any]:
    return {
        'label_sk': suggestion.label_sk,
        'reason': suggestion.reason,
    }


def _confirmed_category_dict(category: AccountingDocumentConfirmedCategory) -> dict[str, Any]:
    return {
        'category_id': category.category_id,
        'label_snapshot': category.label_snapshot,
        'source': category.source,
        'candidate_source': category.candidate_source,
        'confidence': category.confidence,
        'review_required': category.review_required,
    }


def _line_item_dict(item: AccountingDocumentLineItemCandidate) -> dict[str, Any]:
    payload: dict[str, Any] = {
        'description': item.description,
        'amount': str(item.amount) if item.amount is not None else None,
        'currency': item.currency,
        'vat_amount': str(item.vat_amount) if item.vat_amount is not None else None,
    }
    if item.category_candidate is not None:
        payload['category_candidate'] = _category_candidate_dict(item.category_candidate)
    if item.suggested_new_categories:
        payload['suggested_new_categories'] = [
            _suggested_category_dict(suggestion) for suggestion in item.suggested_new_categories[:3]
        ]
    if item.category is not None:
        payload['category'] = _confirmed_category_dict(item.category)
    return payload
