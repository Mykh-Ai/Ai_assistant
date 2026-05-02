from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.accounting_document_intake import (
    AccountingDocumentIntakeStates,
    accounting_document_preview_decision,
    accounting_document_upload,
    cmd_accounting_document_intake,
)
from bot.handlers.voice import handle_voice
from bot.services.accounting_document_classifier import AccountingDocumentClassification
from bot.services.accounting_document_models import (
    AccountingDocumentCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
)
from bot.services.decision_resolver import resolve_approve_edit_cancel


class _DummyPhoto:
    def __init__(self, file_id: str = 'photo-id', file_unique_id: str = 'PHOTO123') -> None:
        self.file_id = file_id
        self.file_unique_id = file_unique_id


class _DummyDocument:
    def __init__(
        self,
        file_id: str = 'doc-id',
        file_unique_id: str = 'DOC123',
        file_name: str = 'doklad.pdf',
        mime_type: str = 'application/pdf',
    ) -> None:
        self.file_id = file_id
        self.file_unique_id = file_unique_id
        self.file_name = file_name
        self.mime_type = mime_type


class _DummyVoice:
    def __init__(self, file_id: str = 'voice-id') -> None:
        self.file_id = file_id


class _DummyMessage:
    def __init__(
        self,
        *,
        text: str | None = None,
        photo: list[_DummyPhoto] | None = None,
        document: _DummyDocument | None = None,
        voice: _DummyVoice | None = None,
    ) -> None:
        self.text = text
        self.photo = photo or []
        self.document = document
        self.voice = voice
        self.answers: list[str] = []
        self.message_id = 77

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self, current_state: str | None = None) -> None:
        self.current_state = current_state
        self.data: dict = {}

    async def get_state(self) -> str | None:
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
            self.file_path = 'remote/file'

    def __init__(self) -> None:
        self.downloads: list[Path] = []

    async def get_file(self, file_id: str):
        return self._File()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'accounting-document')
        self.downloads.append(destination)


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
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'fakturabot.db',
        storage_dir=tmp_path,
    )


def _staged_original_path(tmp_path: Path) -> Path:
    return tmp_path / 'uploads' / 'accounting_intake' / 'PHOTO123' / 'original.jpg'


def _patch_accounting_voice(monkeypatch, recognized_text: str, invoice_fallback_calls: list[str]) -> None:
    async def _transcribe(*args, **kwargs) -> str:
        return recognized_text

    async def _process_invoice_text(**kwargs) -> None:
        invoice_fallback_calls.append(str(kwargs.get('invoice_text')))

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _transcribe)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _process_invoice_text)


def _prepare_accounting_preview(monkeypatch, tmp_path: Path) -> tuple[_DummyState, Config]:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _voice_config(tmp_path)
    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    return state, config


def _receipt_candidate() -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Tesco Slovensko s.r.o.',
        issue_date='2026-05-01',
        total_amount='24.90',
        currency='EUR',
        payment_method='card',
        purchase_subject='Kancelárske potreby',
        quality=AccountingDocumentQuality(readability='good'),
        source=AccountingDocumentSource(input_type='photo', original_filename='photo.jpg'),
    )


async def _fake_classify(**kwargs) -> AccountingDocumentClassification:
    return AccountingDocumentClassification(
        document_type='receipt',
        confidence='high',
        reason='receipt layout',
    )


async def _fake_extract(**kwargs) -> AccountingDocumentCandidate:
    return _receipt_candidate()


def test_doklad_starts_intake_fsm_and_asks_for_upload() -> None:
    state = _DummyState()
    message = _DummyMessage(text='/doklad')

    asyncio.run(cmd_accounting_document_intake(message, state))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert 'fotku alebo PDF' in message.answers[-1]


def test_upload_receipt_photo_active_state_saves_temp_and_shows_preview(monkeypatch, tmp_path: Path) -> None:
    captured_bytes: list[bytes | None] = []

    async def _classify(**kwargs) -> AccountingDocumentClassification:
        captured_bytes.append(kwargs['document_input'].file_bytes)
        return await _fake_classify(**kwargs)

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])
    bot = _DummyBot()

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), bot))

    assert bot.downloads == [tmp_path / 'uploads' / 'accounting_intake' / 'PHOTO123' / 'original.jpg']
    assert captured_bytes == [b'accounting-document']
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert 'Náhľad dokladu' in message.answers[-1]
    assert 'Typ: Bloček' in message.answers[-1]
    assert 'Dodávateľ: Tesco Slovensko s.r.o.' in message.answers[-1]
    assert 'Predmet nákupu: Kancelárske potreby' in message.answers[-1]
    assert 'Kategória' not in message.answers[-1]


def test_schvalit_approves_via_shared_resolver_and_confirmed_saves(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    bot = _DummyBot()
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, bot))

    captured: dict[str, str] = {}

    async def _resolver(**kwargs) -> str:
        captured['context_name'] = kwargs['context_name']
        captured['user_input_text'] = kwargs['user_input_text']
        return 'approve'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    decision_message = _DummyMessage(text='schváliť')
    asyncio.run(accounting_document_preview_decision(decision_message, state, config))

    assert captured == {
        'context_name': 'accounting_document_intake_preview',
        'user_input_text': 'schváliť',
    }
    assert state.current_state is None
    metadata_files = list((tmp_path / 'workspaces').rglob('*.json'))
    original_files = list((tmp_path / 'workspaces').rglob('*.jpg'))
    assert len(metadata_files) == 1
    assert len(original_files) == 1
    metadata = json.loads(metadata_files[0].read_text(encoding='utf-8'))
    assert metadata['document_type'] == 'receipt'
    assert metadata['business']['vendor_name'] == 'Tesco Slovensko s.r.o.'
    assert metadata['business']['purchase_subject'] == 'Kancelárske potreby'
    assert 'category_candidate' not in metadata['business']
    assert not (tmp_path / 'uploads' / 'accounting_intake' / 'PHOTO123').exists()
    assert not (tmp_path / 'invoices').exists()
    assert not config.db_path.exists()


def test_zrusit_cancels_without_confirmed_save(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    message = _DummyMessage(text='zrušiť')
    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state is None
    assert 'zrušené' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()
    assert not (tmp_path / 'uploads' / 'accounting_intake' / 'PHOTO123').exists()
    assert not (tmp_path / 'invoices').exists()
    assert not config.db_path.exists()


def test_unknown_decision_asks_for_clarification(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    message = _DummyMessage(text='neviem')
    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert 'schváliť, upraviť alebo zrušiť' in message.answers[-1]


def test_upravit_keeps_accounting_preview_state_without_save(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    message = _DummyMessage(text='upraviť')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert staged_path.exists()
    assert 'Úprava výdavkového dokladu zatiaľ nie je dostupná.' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()


def test_upravit_cyrillic_keeps_accounting_preview_state_if_unknown_or_edit(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    message = _DummyMessage(text='управить')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert staged_path.exists()
    assert not (tmp_path / 'workspaces').exists()
    assert message.answers[-1] in {
        'Úprava výdavkového dokladu zatiaľ nie je dostupná. Môžete ho schváliť alebo zrušiť.',
        'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.',
    }


@pytest.mark.parametrize(
    ('recognized_text', 'expected_state_cleared', 'expect_staged_file'),
    [
        ('schváliť', True, False),
        ('zrušiť', True, False),
    ],
)
def test_voice_accounting_preview_approve_cancel_use_same_decision_path(
    monkeypatch,
    tmp_path: Path,
    recognized_text: str,
    expected_state_cleared: bool,
    expect_staged_file: bool,
) -> None:
    invoice_fallback_calls: list[str] = []
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _patch_accounting_voice(monkeypatch, recognized_text, invoice_fallback_calls)

    asyncio.run(handle_voice(_DummyMessage(voice=_DummyVoice()), _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert (state.current_state is None) is expected_state_cleared
    assert staged_path.exists() is expect_staged_file


def test_voice_accounting_preview_edit_keeps_state_and_staging(monkeypatch, tmp_path: Path) -> None:
    invoice_fallback_calls: list[str] = []
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _patch_accounting_voice(monkeypatch, 'upraviť', invoice_fallback_calls)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert staged_path.exists()
    assert 'Úprava výdavkového dokladu zatiaľ nie je dostupná.' in message.answers[-1]


def test_voice_accounting_preview_unknown_keeps_state_and_staging(monkeypatch, tmp_path: Path) -> None:
    invoice_fallback_calls: list[str] = []
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _patch_accounting_voice(monkeypatch, 'Ah, não.', invoice_fallback_calls)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert staged_path.exists()
    assert 'schváliť, upraviť alebo zrušiť' in message.answers[-1]


def test_upload_outside_active_state_is_not_intercepted(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _classify(**kwargs):
        calls.append('classify')
        return await _fake_classify(**kwargs)

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _classify)
    state = _DummyState(None)
    message = _DummyMessage(photo=[_DummyPhoto()])
    bot = _DummyBot()

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), bot))

    assert calls == []
    assert bot.downloads == []
    assert message.answers == []


def test_unknown_classification_cleans_temp_and_asks_for_clearer_upload(monkeypatch, tmp_path: Path) -> None:
    async def _unknown_classify(**kwargs) -> AccountingDocumentClassification:
        return AccountingDocumentClassification(
            document_type='unknown',
            confidence='low',
            reason='Unreadable',
        )

    calls: list[str] = []

    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        calls.append('extract')
        return _receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _unknown_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert calls == []
    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert 'nepodarilo rozpozna' in message.answers[-1]
    assert not (tmp_path / 'uploads' / 'accounting_intake' / 'PHOTO123').exists()


def test_poor_readability_cleans_temp_and_asks_for_better_file(monkeypatch, tmp_path: Path) -> None:
    async def _poor_extract(**kwargs) -> AccountingDocumentCandidate:
        return AccountingDocumentCandidate(
            document_type='receipt',
            vendor_name='Tesco Slovensko s.r.o.',
            issue_date='2026-05-01',
            total_amount='24.90',
            currency='EUR',
            payment_method='card',
            purchase_subject='Kancelárske potreby',
            quality=AccountingDocumentQuality(readability='poor'),
            source=AccountingDocumentSource(input_type='photo', original_filename='photo.jpg'),
        )

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _poor_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert 'rozmazan' in message.answers[-1]
    assert not (tmp_path / 'uploads' / 'accounting_intake' / 'PHOTO123').exists()


def test_accounting_document_decision_context_supports_slovak_aliases() -> None:
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='accounting_document_intake_preview',
            user_input_text='schváliť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'approve'
    assert asyncio.run(
        resolve_approve_edit_cancel(
            context_name='accounting_document_intake_preview',
            user_input_text='zrušiť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'cancel'
