from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bot.services.accounting_document_classifier import AccountingDocumentClassifierParseError
from bot.services.accounting_document_extraction import AccountingDocumentExtractionParseError
from bot.services.accounting_document_lmm import (
    AccountingDocumentLmmError,
    AccountingDocumentLmmInput,
    classify_accounting_document,
    extract_accounting_document_metadata,
)


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type('_Message', (), {'content': content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content: str, calls: list[dict]) -> None:
        self._content = content
        self._calls = calls

    async def create(self, **kwargs):
        self._calls.append(kwargs)
        return _FakeResponse(self._content)


class _FakeClient:
    def __init__(self, content: str, calls: list[dict]) -> None:
        self.chat = type('_Chat', (), {'completions': _FakeCompletions(content, calls)})()


def _client_factory(content: str, calls: list[dict]):
    def _factory(api_key: str):
        assert api_key == 'sk-test'
        return _FakeClient(content, calls)

    return _factory


def _document_input() -> AccountingDocumentLmmInput:
    return AccountingDocumentLmmInput(
        input_type='pdf',
        original_filename='doc.pdf',
        mime_type='application/pdf',
        text_content='visible text excerpt',
    )


def _image_document_input() -> AccountingDocumentLmmInput:
    return AccountingDocumentLmmInput(
        input_type='photo',
        original_filename='receipt.jpg',
        mime_type='image/jpeg',
        file_bytes=b'jpeg-bytes',
    )


def _pdf_document_input() -> AccountingDocumentLmmInput:
    return AccountingDocumentLmmInput(
        input_type='pdf',
        original_filename='invoice.pdf',
        mime_type='application/pdf',
        file_bytes=b'%PDF bytes',
    )


def test_classification_wrapper_passes_model_json_into_classifier_parser() -> None:
    calls: list[dict] = []
    raw = json.dumps({'document_type': 'receipt', 'confidence': 'high', 'reason': 'Receipt layout.'})

    result = asyncio.run(
        classify_accounting_document(
            document_input=_document_input(),
            api_key='sk-test',
            model='gpt-4o',
            client_factory=_client_factory(raw, calls),
        )
    )

    assert result.document_type == 'receipt'
    assert result.confidence == 'high'
    assert calls[0]['response_format'] == {'type': 'json_object'}
    assert calls[0]['temperature'] == 0
    assert 'strict JSON only' in calls[0]['messages'][0]['content']
    user_payload = json.loads(calls[0]['messages'][1]['content'])
    assert user_payload['document_input']['has_file_bytes'] is False


def test_extraction_wrapper_passes_model_json_into_extraction_parser() -> None:
    calls: list[dict] = []
    raw = json.dumps(
        {
            'document_type': 'incoming_invoice',
            'source': {'input_type': 'pdf', 'original_filename': 'invoice.pdf'},
            'business': {
                'vendor_name': 'Vendor',
                'vendor_ico': None,
                'document_number': '202605001',
                'issue_date': '2026-05-01',
                'tax_date': None,
                'due_date': '2026-05-15',
                'total_amount': '118.42',
                'currency': 'EUR',
                'vat_amount': None,
                'iban': None,
                'variable_symbol': '202605001',
                'payment_method': 'bank_transfer',
                'purchase_subject': 'Dodávka elektrickej energie',
            },
            'quality': {'readability': 'good', 'missing_fields': [], 'warnings': []},
            'trace': {'raw_visible_text_excerpt': 'Faktura 202605001'},
            'document_category_candidate': {
                'category_id': 'materials',
                'confidence': 'medium',
                'review_required': False,
            },
        }
    )

    candidate = asyncio.run(
        extract_accounting_document_metadata(
            document_input=_document_input(),
            document_type_hint='incoming_invoice',
            allowed_categories=[
                {'category_id': 'materials', 'label_sk': 'Materiál', 'review_required': False},
                {'category_id': 'unknown_review', 'label_sk': 'Na kontrolu', 'review_required': True},
            ],
            api_key='sk-test',
            model='gpt-4o',
            client_factory=_client_factory(raw, calls),
        )
    )

    assert candidate.document_type == 'incoming_invoice'
    assert candidate.vendor_name == 'Vendor'
    user_payload = json.loads(calls[0]['messages'][1]['content'])
    assert user_payload['document_type_hint'] == 'incoming_invoice'
    assert user_payload['document_input']['original_filename'] == 'doc.pdf'
    assert user_payload['allowed_categories'][0]['category_id'] == 'materials'
    assert candidate.document_category_candidate is not None
    assert candidate.document_category_candidate.category_id == 'materials'


def test_image_bytes_are_sent_as_chat_image_url_data_url() -> None:
    calls: list[dict] = []
    raw = json.dumps({'document_type': 'receipt', 'confidence': 'high', 'reason': 'Receipt layout.'})

    asyncio.run(
        classify_accounting_document(
            document_input=_image_document_input(),
            api_key='sk-test',
            model='gpt-4o',
            client_factory=_client_factory(raw, calls),
        )
    )

    content = calls[0]['messages'][1]['content']
    assert isinstance(content, list)
    assert content[0]['type'] == 'text'
    assert json.loads(content[0]['text'])['document_input']['has_file_bytes'] is True
    assert content[1]['type'] == 'image_url'
    assert content[1]['image_url']['url'].startswith('data:image/jpeg;base64,')
    assert content[1]['image_url']['detail'] == 'high'


def test_pdf_bytes_are_sent_as_chat_file_data_url() -> None:
    calls: list[dict] = []
    raw = json.dumps({'document_type': 'incoming_invoice', 'confidence': 'high', 'reason': 'PDF invoice.'})

    asyncio.run(
        classify_accounting_document(
            document_input=_pdf_document_input(),
            api_key='sk-test',
            model='gpt-4o',
            client_factory=_client_factory(raw, calls),
        )
    )

    content = calls[0]['messages'][1]['content']
    assert isinstance(content, list)
    assert content[0]['type'] == 'text'
    assert content[1]['type'] == 'file'
    assert content[1]['file']['filename'] == 'invoice.pdf'
    assert content[1]['file']['file_data'].startswith('data:application/pdf;base64,')


def test_unsupported_file_mime_type_is_rejected_before_provider_call() -> None:
    calls: list[dict] = []

    with pytest.raises(AccountingDocumentLmmError, match='unsupported_document_mime_type'):
        asyncio.run(
            classify_accounting_document(
                document_input=AccountingDocumentLmmInput(
                    input_type='unknown',
                    original_filename='notes.txt',
                    mime_type='text/plain',
                    file_bytes=b'text',
                ),
                api_key='sk-test',
                model='gpt-4o',
                client_factory=_client_factory('{}', calls),
            )
        )

    assert calls == []


def test_oversized_inline_file_is_rejected_before_provider_call() -> None:
    calls: list[dict] = []

    with pytest.raises(AccountingDocumentLmmError, match='document_file_too_large'):
        asyncio.run(
            classify_accounting_document(
                document_input=AccountingDocumentLmmInput(
                    input_type='photo',
                    original_filename='large.jpg',
                    mime_type='image/jpeg',
                    file_bytes=b'x' * (20 * 1024 * 1024 + 1),
                ),
                api_key='sk-test',
                model='gpt-4o',
                client_factory=_client_factory('{}', calls),
            )
        )

    assert calls == []


def test_non_json_model_response_produces_controlled_parse_error() -> None:
    with pytest.raises(AccountingDocumentClassifierParseError, match='classification_not_json'):
        asyncio.run(
            classify_accounting_document(
                document_input=_document_input(),
                api_key='sk-test',
                model='gpt-4o',
                client_factory=_client_factory('not json', []),
            )
        )


def test_model_response_with_forbidden_side_effect_fields_is_rejected() -> None:
    raw = json.dumps(
        {
            'document_type': 'receipt',
            'saved_path': 'storage/workspaces/mykhailo-szco/file.jpg',
            'source': {'input_type': 'photo', 'original_filename': 'receipt.jpg'},
            'business': {
                'vendor_name': 'Tesco',
                'vendor_ico': None,
                'document_number': None,
                'issue_date': '2026-05-01',
                'tax_date': None,
                'due_date': None,
                'total_amount': '24.90',
                'currency': 'EUR',
                'vat_amount': None,
                'iban': None,
                'variable_symbol': None,
                'payment_method': 'card',
                'purchase_subject': 'Potraviny',
            },
            'quality': {'readability': 'good', 'missing_fields': [], 'warnings': []},
            'trace': {'raw_visible_text_excerpt': 'TESCO'},
        }
    )

    with pytest.raises(AccountingDocumentExtractionParseError, match='side_effect_field_forbidden:saved_path'):
        asyncio.run(
            extract_accounting_document_metadata(
                document_input=_document_input(),
                document_type_hint='receipt',
                api_key='sk-test',
                model='gpt-4o',
                client_factory=_client_factory(raw, []),
            )
        )


def test_wrapper_does_not_write_files_or_db(tmp_path: Path) -> None:
    calls: list[dict] = []
    raw = json.dumps({'document_type': 'unknown', 'confidence': 'low', 'reason': 'Unreadable.'})

    asyncio.run(
        classify_accounting_document(
            document_input=_document_input(),
            api_key='sk-test',
            model='gpt-4o',
            client_factory=_client_factory(raw, calls),
        )
    )

    assert list(tmp_path.iterdir()) == []
    assert calls


def test_prompt_files_exist_and_state_strict_json_only() -> None:
    classification_prompt = Path('prompts/accounting_document_classification_prompt.txt')
    extraction_prompt = Path('prompts/accounting_document_extraction_prompt.txt')

    assert classification_prompt.exists()
    assert extraction_prompt.exists()
    assert 'strict JSON only' in classification_prompt.read_text(encoding='utf-8')
    assert 'strict JSON only' in extraction_prompt.read_text(encoding='utf-8')


def test_extraction_prompt_forbids_side_effect_fields() -> None:
    text = Path('prompts/accounting_document_extraction_prompt.txt').read_text(encoding='utf-8')

    for token in ('saved_path', 'status', 'confirmed', 'final_category', 'saved_category', 'category_created'):
        assert token in text
    assert 'Do not create paths.' in text
    assert 'Do not decide final accounting category.' in text
    assert '"purchase_subject": "string|null"' in text
    assert 'allowed_categories' in text
    assert '"document_category_candidate"' in text
    assert '"category_candidate"' in text
    assert 'Do not mutate a category registry.' in text


def test_wrapper_is_provider_isolated_and_mocked() -> None:
    calls: list[dict] = []
    raw = json.dumps({'document_type': 'receipt', 'confidence': 'medium', 'reason': 'Receipt-like totals.'})

    result = asyncio.run(
        classify_accounting_document(
            document_input=_document_input(),
            api_key='sk-test',
            model='gpt-4o-mini',
            client_factory=_client_factory(raw, calls),
        )
    )

    assert result.document_type == 'receipt'
    assert calls[0]['model'] == 'gpt-4o-mini'
