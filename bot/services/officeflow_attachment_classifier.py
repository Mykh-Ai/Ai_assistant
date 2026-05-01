from __future__ import annotations

import json
from typing import Any

from bot.services.officeflow_attachment_models import (
    CONFIDENCE_VALUES,
    DOCUMENT_TYPES,
    OfficeFlowAttachmentClassification,
)


class OfficeFlowAttachmentClassifierParseError(ValueError):
    pass


def parse_officeflow_attachment_classification(raw_json: str) -> OfficeFlowAttachmentClassification:
    """Parse idle attachment classifier output only; no routing or side effects."""
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise OfficeFlowAttachmentClassifierParseError('classification_not_json') from exc

    if not isinstance(payload, dict):
        raise OfficeFlowAttachmentClassifierParseError('classification_not_object')

    allowed_keys = {'document_type', 'confidence', 'reason'}
    unexpected_keys = set(payload) - allowed_keys
    if unexpected_keys:
        raise OfficeFlowAttachmentClassifierParseError(f'unexpected_field:{sorted(unexpected_keys)[0]}')

    document_type = _normalized_string(payload.get('document_type'))
    confidence = _normalized_string(payload.get('confidence'))
    reason = payload.get('reason')

    if document_type not in DOCUMENT_TYPES:
        raise OfficeFlowAttachmentClassifierParseError('document_type_unsupported')
    if confidence not in CONFIDENCE_VALUES:
        raise OfficeFlowAttachmentClassifierParseError('confidence_unsupported')
    if not isinstance(reason, str) or not reason.strip():
        raise OfficeFlowAttachmentClassifierParseError('reason_required')

    return OfficeFlowAttachmentClassification(
        document_type=document_type,
        confidence=confidence,
        reason=' '.join(reason.split()),
    )


def _normalized_string(value: Any) -> str:
    if not isinstance(value, str):
        return ''
    return value.strip().lower()
