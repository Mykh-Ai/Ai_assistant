from __future__ import annotations

import asyncio
import importlib
import inspect
from pathlib import Path

from aiogram.filters import StateFilter
import pytest

from bot.config import Config
from bot.handlers import routers
from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
from bot.handlers.contacts import ContactStates, router as contacts_router
from bot.handlers.officeflow_attachment_router import (
    OfficeFlowAttachmentRouterStates,
    officeflow_accounting_proposal,
    officeflow_idle_attachment,
    router as officeflow_router,
)
from bot.services.officeflow_attachment_lmm import OfficeFlowAttachmentLmmError
from bot.services.officeflow_attachment_models import OfficeFlowAttachmentClassification


officeflow_router_module = importlib.import_module('bot.handlers.officeflow_attachment_router')
voice_module = importlib.import_module('bot.handlers.voice')


class _DummyUser:
    def __init__(self, user_id: int = 111) -> None:
        self.id = user_id


class _DummyPhoto:
    def __init__(self, file_id: str = 'photo-id', file_unique_id: str = 'PHOTO123') -> None:
        self.file_id = file_id
        self.file_unique_id = file_unique_id
        self.file_size = 123


class _DummyDocument:
    def __init__(
        self,
        file_id: str = 'doc-id',
        file_unique_id: str = 'DOC123',
        file_name: str = 'document.pdf',
        mime_type: str = 'application/pdf',
    ) -> None:
        self.file_id = file_id
        self.file_unique_id = file_unique_id
        self.file_name = file_name
        self.mime_type = mime_type
        self.file_size = 456


class _DummyVoice:
    def __init__(self, file_id: str = 'voice-id') -> None:
        self.file_id = file_id


class _DummyMessage:
    def __init__(
        self,
        *,
        text: str | None = None,
        caption: str | None = None,
        photo: list[_DummyPhoto] | None = None,
        document: _DummyDocument | None = None,
        voice: _DummyVoice | None = None,
    ) -> None:
        self.text = text
        self.caption = caption
        self.photo = photo or []
        self.document = document
        self.voice = voice
        self.from_user = _DummyUser()
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self, current_state: str | None = None) -> None:
        self.current_state = current_state
        self.data: dict = {}

    async def get_state(self):
        return self.current_state

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()


class _DummyBot:
    class _File:
        def __init__(self) -> None:
            self.file_path = 'remote/path'

    async def get_file(self, file_id: str):
        return self._File()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'officeflow-attachment')


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'fakturabot.db',
        storage_dir=tmp_path,
    )


def _voice_config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='test-key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'fakturabot.db',
        storage_dir=tmp_path,
    )


def _stage_accounting_proposal_state(tmp_path: Path) -> tuple[_DummyState, Path]:
    state = _DummyState(OfficeFlowAttachmentRouterStates.accounting_proposal.state)
    staged_path = tmp_path / 'uploads' / 'attachment_intake' / 'PHOTO123' / 'original.jpg'
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_bytes(b'photo')
    state.data.update(
        {
            'officeflow_attachment_staged_path': str(staged_path),
            'officeflow_attachment_metadata': {
                'file_unique_id': 'PHOTO123',
                'input_type': 'photo',
                'original_filename': 'photo.jpg',
                'mime_type': 'image/jpeg',
                'extension': '.jpg',
            },
            'officeflow_attachment_classification': {
                'document_type': 'receipt',
                'confidence': 'high',
                'reason': 'receipt evidence',
            },
        }
    )
    return state, staged_path


def _patch_voice_stt_and_invoice_fallback(monkeypatch, recognized_text: str, invoice_fallback_calls: list[str]) -> None:
    async def _transcribe(*args, **kwargs) -> str:
        return recognized_text

    async def _process_invoice_text(**kwargs) -> None:
        invoice_fallback_calls.append(str(kwargs.get('invoice_text')))

    monkeypatch.setattr(voice_module, 'transcribe_audio', _transcribe)
    monkeypatch.setattr(voice_module, 'process_invoice_text', _process_invoice_text)


async def _classify_as(document_type: str, **kwargs) -> OfficeFlowAttachmentClassification:
    return OfficeFlowAttachmentClassification(
        document_type=document_type,
        confidence='high',
        reason=f'{document_type} evidence',
    )


def test_idle_photo_receipt_stages_and_asks_accounting_proposal(monkeypatch, tmp_path: Path) -> None:
    async def _classifier(**kwargs):
        return await _classify_as('receipt', **kwargs)

    monkeypatch.setattr(officeflow_router_module, 'classify_officeflow_attachment', _classifier)
    state = _DummyState()
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(officeflow_idle_attachment(message, state, _config(tmp_path), _DummyBot()))

    staged_path = tmp_path / 'uploads' / 'attachment_intake' / 'PHOTO123' / 'original.jpg'
    assert staged_path.exists()
    assert state.current_state == OfficeFlowAttachmentRouterStates.accounting_proposal.state
    assert 'výdavkový doklad' in message.answers[-1]
    assert 'Odpovedzte: áno / nie.' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()


def test_idle_pdf_incoming_invoice_asks_accounting_proposal(monkeypatch, tmp_path: Path) -> None:
    async def _classifier(**kwargs):
        return await _classify_as('incoming_invoice', **kwargs)

    monkeypatch.setattr(officeflow_router_module, 'classify_officeflow_attachment', _classifier)
    state = _DummyState()
    message = _DummyMessage(document=_DummyDocument())

    asyncio.run(officeflow_idle_attachment(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state == OfficeFlowAttachmentRouterStates.accounting_proposal.state
    assert 'bloček/prijatá faktúra' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()


def test_idle_pdf_contract_asks_contact_contract_proposal_without_save(monkeypatch, tmp_path: Path) -> None:
    async def _classifier(**kwargs):
        return await _classify_as('contract', **kwargs)

    monkeypatch.setattr(officeflow_router_module, 'classify_officeflow_attachment', _classifier)
    state = _DummyState()
    message = _DummyMessage(document=_DummyDocument())
    config = _config(tmp_path)

    asyncio.run(officeflow_idle_attachment(message, state, config, _DummyBot()))

    assert state.current_state == OfficeFlowAttachmentRouterStates.route_choice.state
    assert 'vytvoriť kontakt' in message.answers[-1]
    assert not (tmp_path / 'contracts').exists()
    assert not config.db_path.exists()


def test_idle_unknown_asks_bounded_clarification_without_save(monkeypatch, tmp_path: Path) -> None:
    async def _classifier(**kwargs):
        return await _classify_as('unknown', **kwargs)

    monkeypatch.setattr(officeflow_router_module, 'classify_officeflow_attachment', _classifier)
    state = _DummyState()
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(officeflow_idle_attachment(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state == OfficeFlowAttachmentRouterStates.unknown_clarification.state
    assert 'jednoznačne zaradiť' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()


def test_lmm_error_cleans_staged_attachment_and_sends_slovak_failure(monkeypatch, tmp_path: Path) -> None:
    async def _classifier(**kwargs):
        raise OfficeFlowAttachmentLmmError('missing_api_key')

    monkeypatch.setattr(officeflow_router_module, 'classify_officeflow_attachment', _classifier)
    state = _DummyState()
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(officeflow_idle_attachment(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state is None
    assert 'nepodarilo bezpečne zaradiť' in message.answers[-1]
    assert not (tmp_path / 'uploads' / 'attachment_intake' / 'PHOTO123').exists()


def test_accounting_proposal_uses_decision_resolver_yes_no(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, str] = {}

    async def _resolver(**kwargs):
        captured['context_name'] = kwargs['context_name']
        captured['user_input_text'] = kwargs['user_input_text']
        return 'no'

    monkeypatch.setattr(officeflow_router_module, 'resolve_yes_no', _resolver)
    state = _DummyState(OfficeFlowAttachmentRouterStates.accounting_proposal.state)
    staged_path = tmp_path / 'uploads' / 'attachment_intake' / 'PHOTO123' / 'original.jpg'
    staged_path.parent.mkdir(parents=True, exist_ok=True)
    staged_path.write_bytes(b'photo')
    state.data.update(
        {
            'officeflow_attachment_staged_path': str(staged_path),
            'officeflow_attachment_metadata': {'file_unique_id': 'PHOTO123'},
        }
    )
    message = _DummyMessage(text='Ah, não.')

    asyncio.run(officeflow_accounting_proposal(message, state, _config(tmp_path)))

    assert captured == {
        'context_name': 'idle_attachment_accounting_proposal',
        'user_input_text': 'Ah, não.',
    }
    assert state.current_state is None
    assert not staged_path.exists()


@pytest.mark.parametrize(
    'answer_text',
    [
        'ano',
        '\u00e1no',
        'tak',
        'ok',
        '\u0442\u0430\u043a',
        '\u0434\u0430',
    ],
)
def test_accounting_proposal_yes_variants_continue_via_shared_resolver(monkeypatch, tmp_path: Path, answer_text: str) -> None:
    captured: dict[str, object] = {}

    async def _process(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(officeflow_router_module, 'process_staged_accounting_document', _process)
    state, staged_path = _stage_accounting_proposal_state(tmp_path)
    message = _DummyMessage(text=answer_text)

    asyncio.run(officeflow_accounting_proposal(message, state, _config(tmp_path)))

    assert captured['document_type_hint'] == 'receipt'
    assert captured['staged_path'] == staged_path
    assert not staged_path.exists()


def test_accounting_proposal_unknown_keeps_staged_file_and_asks_clarification(tmp_path: Path) -> None:
    state, staged_path = _stage_accounting_proposal_state(tmp_path)
    message = _DummyMessage(text='asi')

    asyncio.run(officeflow_accounting_proposal(message, state, _config(tmp_path)))

    assert state.current_state == OfficeFlowAttachmentRouterStates.accounting_proposal.state
    assert staged_path.exists()
    assert 'áno alebo nie' in message.answers[-1]


def test_accounting_proposal_no_cleans_staged_file(tmp_path: Path) -> None:
    state, staged_path = _stage_accounting_proposal_state(tmp_path)
    message = _DummyMessage(text='nie')

    asyncio.run(officeflow_accounting_proposal(message, state, _config(tmp_path)))

    assert state.current_state is None
    assert not staged_path.exists()
    assert 'zrušené' in message.answers[-1]


def test_accounting_proposal_handler_has_no_local_confirmation_parser() -> None:
    source = inspect.getsource(officeflow_accounting_proposal)
    source += inspect.getsource(officeflow_router_module.handle_officeflow_accounting_proposal_text)

    assert 'resolve_yes_no' in source
    assert '.lower(' not in source
    assert 'normalized' not in source
    assert "in {'ano'" not in source
    assert "in {'áno'" not in source
    assert "in {'tak'" not in source


@pytest.mark.parametrize('recognized_text', ['ano', 'ANO', 'tak', '\u0442\u0430\u043a'])
def test_voice_accounting_proposal_yes_continues_to_accounting(monkeypatch, tmp_path: Path, recognized_text: str) -> None:
    captured: dict[str, object] = {}
    invoice_fallback_calls: list[str] = []

    async def _process(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(officeflow_router_module, 'process_staged_accounting_document', _process)
    _patch_voice_stt_and_invoice_fallback(monkeypatch, recognized_text, invoice_fallback_calls)
    state, staged_path = _stage_accounting_proposal_state(tmp_path)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(voice_module.handle_voice(message, _DummyBot(), _voice_config(tmp_path), state))

    assert captured['document_type_hint'] == 'receipt'
    assert captured['staged_path'] == staged_path
    assert invoice_fallback_calls == []
    assert not staged_path.exists()


def test_voice_accounting_proposal_no_cleans_staged_file(monkeypatch, tmp_path: Path) -> None:
    invoice_fallback_calls: list[str] = []

    async def _process(**kwargs) -> None:
        raise AssertionError('accounting continuation must not run for no')

    monkeypatch.setattr(officeflow_router_module, 'process_staged_accounting_document', _process)
    _patch_voice_stt_and_invoice_fallback(monkeypatch, 'nie', invoice_fallback_calls)
    state, staged_path = _stage_accounting_proposal_state(tmp_path)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(voice_module.handle_voice(message, _DummyBot(), _voice_config(tmp_path), state))

    assert state.current_state is None
    assert invoice_fallback_calls == []
    assert not staged_path.exists()
    assert 'Spracovanie' in message.answers[-1]


def test_voice_accounting_proposal_unknown_keeps_state_and_staging(monkeypatch, tmp_path: Path) -> None:
    invoice_fallback_calls: list[str] = []

    async def _process(**kwargs) -> None:
        raise AssertionError('accounting continuation must not run for unknown')

    monkeypatch.setattr(officeflow_router_module, 'process_staged_accounting_document', _process)
    _patch_voice_stt_and_invoice_fallback(monkeypatch, 'Ah, n\u00e3o.', invoice_fallback_calls)
    state, staged_path = _stage_accounting_proposal_state(tmp_path)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(voice_module.handle_voice(message, _DummyBot(), _voice_config(tmp_path), state))

    assert state.current_state == OfficeFlowAttachmentRouterStates.accounting_proposal.state
    assert invoice_fallback_calls == []
    assert staged_path.exists()
    assert 'odpovedzte' in message.answers[-1]
    assert 'nie' in message.answers[-1]


def test_shared_router_is_idle_only_and_registered_before_contacts() -> None:
    assert routers.index(officeflow_router) < routers.index(contacts_router)
    idle_handler = officeflow_router.message.handlers[0]
    assert any(isinstance(filter_object.callback, StateFilter) for filter_object in idle_handler.filters)


def test_active_state_handlers_remain_distinct() -> None:
    assert AccountingDocumentIntakeStates.waiting_upload.state != OfficeFlowAttachmentRouterStates.accounting_proposal.state
    assert ContactStates.source_after_name.state != OfficeFlowAttachmentRouterStates.route_choice.state
