from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
import re

from bot.services.accounting_document_models import (
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    DOCUMENT_TYPE_UNKNOWN,
    DOCUMENT_TYPES,
    PAYMENT_METHODS,
    READABILITY_VALUES,
    AccountingDocumentCandidate,
)
from bot.services.validation import validate_iban


@dataclass(frozen=True)
class AccountingDocumentValidationResult:
    can_save: bool
    errors: list[str]
    warnings: list[str]
    normalized_total_amount: Decimal | None = None
    normalized_currency: str | None = None
    normalized_issue_date: date | None = None


def parse_iso_date(value: date | str | None) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def parse_positive_decimal(value: Decimal | str | int | float | None) -> Decimal | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value).replace(',', '.').strip())
    except (InvalidOperation, AttributeError):
        return None
    if parsed <= Decimal('0'):
        return None
    return parsed


def validate_accounting_document_candidate(
    candidate: AccountingDocumentCandidate,
    *,
    allow_safe_eur_default: bool = False,
) -> AccountingDocumentValidationResult:
    errors: list[str] = []
    warnings: list[str] = list(candidate.quality.warnings)

    if candidate.document_type not in DOCUMENT_TYPES:
        errors.append('document_type_invalid')
    if candidate.document_type == DOCUMENT_TYPE_UNKNOWN:
        errors.append('document_type_unknown')

    if candidate.quality.readability not in READABILITY_VALUES and candidate.quality.readability != 'unknown':
        warnings.append('readability_unknown')
    if candidate.quality.readability == 'poor':
        warnings.append('readability_poor_requires_review')

    issue_date = parse_iso_date(candidate.issue_date)
    for field_name in ('issue_date', 'tax_date', 'due_date'):
        raw_value = getattr(candidate, field_name)
        if raw_value is not None and str(raw_value).strip() and parse_iso_date(raw_value) is None:
            errors.append(f'{field_name}_invalid')

    amount = parse_positive_decimal(candidate.total_amount)
    if amount is None:
        errors.append('total_amount_required_positive')

    currency = (candidate.currency or '').strip().upper()
    if not currency:
        if allow_safe_eur_default:
            currency = 'EUR'
            warnings.append('currency_defaulted_to_eur')
        else:
            errors.append('currency_required')
    elif not re.fullmatch(r'[A-Z]{3}', currency):
        errors.append('currency_invalid')

    if candidate.payment_method is not None:
        payment_method = candidate.payment_method.strip()
        if payment_method and payment_method not in PAYMENT_METHODS:
            warnings.append('payment_method_unknown')

    if candidate.iban and not validate_iban(candidate.iban):
        warnings.append('iban_invalid')

    if candidate.variable_symbol and not re.fullmatch(r'[0-9A-Za-z./-]{1,35}', candidate.variable_symbol.strip()):
        warnings.append('variable_symbol_invalid')

    if candidate.document_type == DOCUMENT_TYPE_RECEIPT:
        if not _has_text(candidate.vendor_name):
            errors.append('vendor_name_required')
        if issue_date is None:
            errors.append('issue_date_required')
    elif candidate.document_type == DOCUMENT_TYPE_INCOMING_INVOICE:
        if not _has_text(candidate.vendor_name):
            errors.append('vendor_name_required')
        if not _has_text(candidate.document_number):
            errors.append('document_number_required')
        if issue_date is None:
            errors.append('issue_date_required')

    return AccountingDocumentValidationResult(
        can_save=not errors,
        errors=errors,
        warnings=warnings,
        normalized_total_amount=amount,
        normalized_currency=currency or None,
        normalized_issue_date=issue_date,
    )


def _has_text(value: str | None) -> bool:
    return bool((value or '').strip())
