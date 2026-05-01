from __future__ import annotations

import base64
from collections.abc import Callable
import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from bot.services.officeflow_attachment_classifier import parse_officeflow_attachment_classification
from bot.services.officeflow_attachment_models import (
    DOCUMENT_TYPE_CONTACT_SOURCE,
    DOCUMENT_TYPE_CONTRACT,
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    DOCUMENT_TYPE_UNKNOWN,
    OfficeFlowAttachment,
    OfficeFlowAttachmentClassification,
)


_PROMPT_PATH = Path(__file__).parent.parent.parent / 'prompts' / 'officeflow_attachment_classification_prompt.txt'
_MAX_INLINE_FILE_BYTES = 20 * 1024 * 1024


class OfficeFlowAttachmentLmmError(RuntimeError):
    pass


ClientFactory = Callable[[str], Any]


async def classify_officeflow_attachment(
    *,
    attachment: OfficeFlowAttachment,
    api_key: str | None,
    model: str,
    client_factory: ClientFactory | None = None,
) -> OfficeFlowAttachmentClassification:
    raw = await _call_json_lmm(
        attachment=attachment,
        api_key=api_key,
        model=model,
        client_factory=client_factory,
    )
    return parse_officeflow_attachment_classification(raw)


async def _call_json_lmm(
    *,
    attachment: OfficeFlowAttachment,
    api_key: str | None,
    model: str,
    client_factory: ClientFactory | None,
) -> str:
    if not api_key or not api_key.startswith('sk-'):
        raise OfficeFlowAttachmentLmmError('openai_api_key_required')

    prompt = _PROMPT_PATH.read_text(encoding='utf-8')
    client = client_factory(api_key) if client_factory is not None else AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': _build_user_content(attachment)},
        ],
    )
    raw = response.choices[0].message.content
    if not isinstance(raw, str) or not raw.strip():
        raise OfficeFlowAttachmentLmmError('empty_lmm_response')
    return raw


def _build_user_content(attachment: OfficeFlowAttachment) -> str | list[dict[str, Any]]:
    payload = _classification_bundle(attachment)
    file_bytes = attachment.staged_path.read_bytes()
    if len(file_bytes) > _MAX_INLINE_FILE_BYTES:
        raise OfficeFlowAttachmentLmmError('attachment_file_too_large')

    metadata_text = json.dumps(payload, ensure_ascii=False)
    return [
        {'type': 'text', 'text': metadata_text},
        _file_content_item(attachment=attachment, file_bytes=file_bytes),
    ]


def _classification_bundle(attachment: OfficeFlowAttachment) -> dict[str, Any]:
    return {
        'current_state': None,
        'active_user_intent': 'idle_attachment',
        'allowed_document_types': [
            DOCUMENT_TYPE_RECEIPT,
            DOCUMENT_TYPE_INCOMING_INVOICE,
            DOCUMENT_TYPE_CONTRACT,
            DOCUMENT_TYPE_CONTACT_SOURCE,
            DOCUMENT_TYPE_UNKNOWN,
        ],
        'routing_hints': {
            'receipt': 'retail receipt, cash register receipt, small expense proof',
            'incoming_invoice': 'supplier invoice received by the business',
            'contract': 'agreement, signed contract, long-living legal reference document',
            'contact_source': 'document that can provide company/contact details',
            'unknown': 'use when the document cannot be classified safely',
        },
        'forbidden_side_effects': [
            'do_not_create_expense',
            'do_not_create_contact',
            'do_not_save_contract',
            'do_not_route_or_execute_business_action',
        ],
        'extracted_pdf_text': attachment.extracted_pdf_text,
        'attachment_metadata': {
            'input_type': attachment.input_type,
            'original_filename': attachment.original_filename,
            'mime_type': attachment.mime_type,
            'extension': attachment.extension,
            'file_size': attachment.file_size,
            'caption': attachment.caption,
            'has_extracted_pdf_text': bool(attachment.extracted_pdf_text),
        },
        'expected_output': {
            'document_type': 'receipt|incoming_invoice|contract|contact_source|unknown',
            'confidence': 'high|medium|low',
            'reason': 'short human-auditable reason',
        },
    }


def _file_content_item(*, attachment: OfficeFlowAttachment, file_bytes: bytes) -> dict[str, Any]:
    encoded = base64.b64encode(file_bytes).decode('ascii')
    if attachment.mime_type.startswith('image/'):
        return {
            'type': 'image_url',
            'image_url': {
                'url': f'data:{attachment.mime_type};base64,{encoded}',
                'detail': 'high',
            },
        }

    if attachment.mime_type == 'application/pdf':
        return {
            'type': 'file',
            'file': {
                'filename': attachment.original_filename or 'document.pdf',
                'file_data': f'data:application/pdf;base64,{encoded}',
            },
        }

    raise OfficeFlowAttachmentLmmError('unsupported_attachment_mime_type')
