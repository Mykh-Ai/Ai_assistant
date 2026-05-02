from __future__ import annotations

from decimal import Decimal, InvalidOperation
import json
from typing import Any

from bot.services.accounting_document_models import (
    DOCUMENT_TYPES,
    PAYMENT_METHODS,
    READABILITY_VALUES,
    AccountingDocumentCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
)


_ALLOWED_TOP_LEVEL_KEYS = {'document_type', 'source', 'business', 'quality', 'trace'}
_SIDE_EFFECT_TOP_LEVEL_KEYS = {'id', 'db_id', 'saved_path', 'status', 'confirmed', 'final_category'}


class AccountingDocumentExtractionParseError(ValueError):
    pass


def parse_accounting_document_extraction(raw_json: str) -> AccountingDocumentCandidate:
    """
    Parse LMM extraction output into a candidate model.

    This module does not call LMM/Vision, does not save files, does not write DB rows,
    and does not execute business actions. Parsed data remains candidate-only until
    Python validation and explicit user confirmation.
    """
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AccountingDocumentExtractionParseError('extraction_not_json') from exc

    if not isinstance(payload, dict):
        raise AccountingDocumentExtractionParseError('extraction_not_object')

    _reject_top_level_fields(payload)

    document_type = _normalized_string(payload.get('document_type'))
    if document_type not in DOCUMENT_TYPES:
        raise AccountingDocumentExtractionParseError('document_type_unsupported')

    source = _parse_source(payload.get('source'))
    business = _expect_object(payload.get('business'), 'business_required')
    quality = _parse_quality(payload.get('quality'))

    payment_method = _nullable_normalized_string(business.get('payment_method'))
    if payment_method is not None and payment_method not in PAYMENT_METHODS:
        raise AccountingDocumentExtractionParseError('payment_method_unsupported')

    return AccountingDocumentCandidate(
        document_type=document_type,
        vendor_name=_nullable_string(business.get('vendor_name')),
        vendor_ico=_nullable_string(business.get('vendor_ico')),
        document_number=_nullable_string(business.get('document_number')),
        issue_date=_nullable_string(business.get('issue_date')),
        tax_date=_nullable_string(business.get('tax_date')),
        due_date=_nullable_string(business.get('due_date')),
        total_amount=_nullable_decimal(business.get('total_amount'), 'total_amount_invalid'),
        currency=_nullable_normalized_string(business.get('currency'), uppercase=True),
        vat_amount=_nullable_decimal(business.get('vat_amount'), 'vat_amount_invalid'),
        iban=_nullable_string(business.get('iban')),
        variable_symbol=_nullable_string(business.get('variable_symbol')),
        payment_method=payment_method,
        purchase_subject=_nullable_string(business.get('purchase_subject'))
        or _nullable_string(business.get('category_candidate')),
        quality=quality,
        source=source,
    )


def _reject_top_level_fields(payload: dict[str, Any]) -> None:
    side_effect_keys = set(payload) & _SIDE_EFFECT_TOP_LEVEL_KEYS
    if side_effect_keys:
        raise AccountingDocumentExtractionParseError(f'side_effect_field_forbidden:{sorted(side_effect_keys)[0]}')
    unexpected_keys = set(payload) - _ALLOWED_TOP_LEVEL_KEYS
    if unexpected_keys:
        raise AccountingDocumentExtractionParseError(f'unexpected_top_level_field:{sorted(unexpected_keys)[0]}')


def _parse_source(value: Any) -> AccountingDocumentSource:
    source = _expect_object(value, 'source_required')
    return AccountingDocumentSource(
        input_type=_nullable_string(source.get('input_type')) or 'unknown',
        original_filename=_nullable_string(source.get('original_filename')),
    )


def _parse_quality(value: Any) -> AccountingDocumentQuality:
    quality = _expect_object(value, 'quality_required')
    readability = _normalized_string(quality.get('readability'))
    if readability not in READABILITY_VALUES:
        raise AccountingDocumentExtractionParseError('readability_unsupported')

    missing_fields = _string_list(quality.get('missing_fields'), 'missing_fields_invalid')
    warnings = _string_list(quality.get('warnings'), 'warnings_invalid')
    return AccountingDocumentQuality(
        readability=readability,
        missing_fields=missing_fields,
        warnings=warnings,
    )


def _expect_object(value: Any, error: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AccountingDocumentExtractionParseError(error)
    return value


def _nullable_decimal(value: Any, error: str) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(',', '.').strip())
    except (InvalidOperation, AttributeError) as exc:
        raise AccountingDocumentExtractionParseError(error) from exc


def _string_list(value: Any, error: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise AccountingDocumentExtractionParseError(error)
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise AccountingDocumentExtractionParseError(error)
        cleaned = item.strip()
        if cleaned:
            result.append(cleaned)
    return result


def _nullable_string(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return str(value)
    cleaned = value.strip()
    return cleaned or None


def _nullable_normalized_string(value: Any, *, uppercase: bool = False) -> str | None:
    text = _nullable_string(value)
    if text is None:
        return None
    normalized = text.upper() if uppercase else text.lower()
    return normalized or None


def _normalized_string(value: Any) -> str:
    text = _nullable_string(value)
    return (text or '').lower()
