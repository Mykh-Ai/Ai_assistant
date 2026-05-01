from __future__ import annotations

import json

import pytest

from bot.services.officeflow_attachment_classifier import (
    OfficeFlowAttachmentClassifierParseError,
    parse_officeflow_attachment_classification,
)


@pytest.mark.parametrize(
    'document_type',
    ['receipt', 'incoming_invoice', 'contract', 'contact_source', 'unknown'],
)
def test_parse_valid_document_types(document_type: str) -> None:
    result = parse_officeflow_attachment_classification(
        json.dumps(
            {
                'document_type': document_type,
                'confidence': 'high',
                'reason': 'visible layout',
            }
        )
    )

    assert result.document_type == document_type
    assert result.confidence == 'high'
    assert result.reason == 'visible layout'


@pytest.mark.parametrize(
    'raw_json',
    [
        '{"document_type":"receipt","confidence":"high","reason":"ok","action":"save"}',
        '{"document_type":"bank_statement","confidence":"high","reason":"ok"}',
        '{"document_type":"receipt","confidence":"certain","reason":"ok"}',
        '{"document_type":"receipt","confidence":"high","reason":"   "}',
        'not-json',
    ],
)
def test_parse_rejects_invalid_payloads(raw_json: str) -> None:
    with pytest.raises(OfficeFlowAttachmentClassifierParseError):
        parse_officeflow_attachment_classification(raw_json)
