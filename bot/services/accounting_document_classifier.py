from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from bot.services.accounting_document_models import DOCUMENT_TYPES


CONFIDENCE_VALUES = {'high', 'medium', 'low'}


class AccountingDocumentClassifierParseError(ValueError):
    pass


@dataclass(frozen=True)
class AccountingDocumentClassification:
    document_type: str
    confidence: str
    reason: str


def parse_accounting_document_classification(raw_json: str) -> AccountingDocumentClassification:
    """Parse LMM classifier output only; this function performs no I/O or business action."""
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AccountingDocumentClassifierParseError('classification_not_json') from exc

    if not isinstance(payload, dict):
        raise AccountingDocumentClassifierParseError('classification_not_object')

    allowed_keys = {'document_type', 'confidence', 'reason'}
    unexpected_keys = set(payload) - allowed_keys
    if unexpected_keys:
        raise AccountingDocumentClassifierParseError(f'unexpected_field:{sorted(unexpected_keys)[0]}')

    document_type = _normalized_string(payload.get('document_type'))
    confidence = _normalized_string(payload.get('confidence'))
    reason = payload.get('reason')

    if document_type not in DOCUMENT_TYPES:
        raise AccountingDocumentClassifierParseError('document_type_unsupported')
    if confidence not in CONFIDENCE_VALUES:
        raise AccountingDocumentClassifierParseError('confidence_unsupported')
    if not isinstance(reason, str) or not reason.strip():
        raise AccountingDocumentClassifierParseError('reason_required')

    return AccountingDocumentClassification(
        document_type=document_type,
        confidence=confidence,
        reason=' '.join(reason.split()),
    )


def _normalized_string(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    return value.strip().lower()
