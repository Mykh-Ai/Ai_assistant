from __future__ import annotations

import base64
from collections.abc import Callable
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from openai import AsyncOpenAI

from bot.services.accounting_document_classifier import (
    AccountingDocumentClassification,
    parse_accounting_document_classification,
)
from bot.services.accounting_document_extraction import parse_accounting_document_extraction
from bot.services.accounting_document_models import AccountingDocumentCandidate


_PROMPTS_DIR = Path(__file__).parent.parent.parent / 'prompts'
_CLASSIFICATION_PROMPT_PATH = _PROMPTS_DIR / 'accounting_document_classification_prompt.txt'
_EXTRACTION_PROMPT_PATH = _PROMPTS_DIR / 'accounting_document_extraction_prompt.txt'
_MAX_INLINE_FILE_BYTES = 20 * 1024 * 1024


class AccountingDocumentLmmError(RuntimeError):
    pass


@dataclass(frozen=True)
class AccountingDocumentLmmInput:
    """Abstract LMM input envelope; this module does not download, save, or route Telegram files."""

    input_type: str
    original_filename: str | None = None
    mime_type: str | None = None
    text_content: str | None = None
    file_bytes: bytes | None = None


ClientFactory = Callable[[str], Any]


async def classify_accounting_document(
    *,
    document_input: AccountingDocumentLmmInput,
    api_key: str | None,
    model: str,
    client_factory: ClientFactory | None = None,
) -> AccountingDocumentClassification:
    """
    Call the configured LMM provider for candidate classification only.

    The returned model text is immediately parsed by the strict classifier parser.
    This function does not create IDs, paths, files, DB records, final categories,
    or business side effects.
    """
    raw = await _call_json_lmm(
        prompt_path=_CLASSIFICATION_PROMPT_PATH,
        document_input=document_input,
        api_key=api_key,
        model=model,
        client_factory=client_factory,
    )
    return parse_accounting_document_classification(raw)


async def extract_accounting_document_metadata(
    *,
    document_input: AccountingDocumentLmmInput,
    document_type_hint: str | None,
    allowed_categories: list[dict[str, Any]] | None = None,
    api_key: str | None,
    model: str,
    client_factory: ClientFactory | None = None,
) -> AccountingDocumentCandidate:
    """
    Call the configured LMM provider for candidate metadata extraction only.

    The returned model text is immediately parsed by the strict extraction parser.
    This function does not save files, write DB rows, choose final accounting
    categories, or execute business actions.
    """
    raw = await _call_json_lmm(
        prompt_path=_EXTRACTION_PROMPT_PATH,
        document_input=document_input,
        api_key=api_key,
        model=model,
        client_factory=client_factory,
        extra_payload={
            'document_type_hint': document_type_hint,
            'allowed_categories': allowed_categories or [],
        },
    )
    allowed_category_ids = {
        str(item.get('category_id')).strip()
        for item in allowed_categories or []
        if isinstance(item, dict) and item.get('category_id')
    }
    return parse_accounting_document_extraction(raw, allowed_category_ids=allowed_category_ids or None)


async def _call_json_lmm(
    *,
    prompt_path: Path,
    document_input: AccountingDocumentLmmInput,
    api_key: str | None,
    model: str,
    client_factory: ClientFactory | None,
    extra_payload: dict[str, Any] | None = None,
) -> str:
    if not api_key or not api_key.startswith('sk-'):
        raise AccountingDocumentLmmError('openai_api_key_required')

    prompt = prompt_path.read_text(encoding='utf-8')
    client = client_factory(api_key) if client_factory is not None else AsyncOpenAI(api_key=api_key)
    payload = {
        'document_input': {
            'input_type': document_input.input_type,
            'original_filename': document_input.original_filename,
            'mime_type': document_input.mime_type,
            'text_content': document_input.text_content,
            'has_file_bytes': document_input.file_bytes is not None,
        },
    }
    if extra_payload:
        payload.update(extra_payload)

    user_content = _build_user_content(document_input=document_input, payload=payload)
    response = await client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={'type': 'json_object'},
        messages=[
            {'role': 'system', 'content': prompt},
            {'role': 'user', 'content': user_content},
        ],
    )
    raw = response.choices[0].message.content
    if not isinstance(raw, str) or not raw.strip():
        raise AccountingDocumentLmmError('empty_lmm_response')
    return raw


def _build_user_content(*, document_input: AccountingDocumentLmmInput, payload: dict[str, Any]) -> str | list[dict[str, Any]]:
    if document_input.file_bytes is None:
        return json.dumps(payload, ensure_ascii=False)

    if len(document_input.file_bytes) > _MAX_INLINE_FILE_BYTES:
        raise AccountingDocumentLmmError('document_file_too_large')

    metadata_text = json.dumps(payload, ensure_ascii=False)
    file_item = _file_content_item(document_input)
    return [
        {'type': 'text', 'text': metadata_text},
        file_item,
    ]


def _file_content_item(document_input: AccountingDocumentLmmInput) -> dict[str, Any]:
    mime_type = _normalize_mime_type(document_input)
    encoded = base64.b64encode(document_input.file_bytes or b'').decode('ascii')
    filename = document_input.original_filename or _default_filename(mime_type)

    if mime_type.startswith('image/'):
        return {
            'type': 'image_url',
            'image_url': {
                'url': f'data:{mime_type};base64,{encoded}',
                'detail': 'high',
            },
        }

    if mime_type == 'application/pdf':
        return {
            'type': 'file',
            'file': {
                'filename': filename,
                'file_data': f'data:application/pdf;base64,{encoded}',
            },
        }

    raise AccountingDocumentLmmError('unsupported_document_mime_type')


def _normalize_mime_type(document_input: AccountingDocumentLmmInput) -> str:
    mime_type = (document_input.mime_type or '').strip().lower()
    if mime_type:
        return mime_type
    if document_input.input_type == 'photo':
        return 'image/jpeg'
    if document_input.input_type == 'pdf':
        return 'application/pdf'
    return 'application/octet-stream'


def _default_filename(mime_type: str) -> str:
    if mime_type == 'application/pdf':
        return 'document.pdf'
    if mime_type == 'image/png':
        return 'photo.png'
    if mime_type == 'image/webp':
        return 'photo.webp'
    return 'photo.jpg'
