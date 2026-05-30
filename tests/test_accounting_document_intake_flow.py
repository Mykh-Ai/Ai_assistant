from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3

import pytest

from bot.config import Config
from bot.handlers.accounting_document_intake import (
    AccountingDocumentIntakeStates,
    _enqueue_archive_after_confirmed_save,
    accounting_document_duplicate_decision,
    accounting_document_preview_decision,
    accounting_document_upload,
    accounting_document_waiting_upload,
    cmd_accounting_document_intake,
)
from bot.services.accounting_document_storage import AccountingDocumentSaveResult, workspace_key_for_supplier
from bot.handlers.voice import handle_voice
from bot.services.accounting_document_classifier import AccountingDocumentClassification
from bot.services.accounting_document_models import (
    AccountingDocumentCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
)
from bot.services.accounting_document_archive_service import AccountingDocumentArchiveService
from bot.services.archive_job_service import ARCHIVE_JOB_PENDING
from bot.services.decision_resolver import resolve_approve_edit_cancel
from bot.services.temp_intake_session import build_intake_session_metadata


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


class _DummyUser:
    def __init__(self, telegram_id: int) -> None:
        self.id = telegram_id


class _DummyMessage:
    def __init__(
        self,
        *,
        text: str | None = None,
        photo: list[_DummyPhoto] | None = None,
        document: _DummyDocument | None = None,
        voice: _DummyVoice | None = None,
        from_user_id: int | None = None,
    ) -> None:
        self.text = text
        self.photo = photo or []
        self.document = document
        self.voice = voice
        self.answers: list[str] = []
        self.message_id = 77
        if from_user_id is not None:
            self.from_user = _DummyUser(from_user_id)

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


def _expire_accounting_state(state: _DummyState, staged_path: Path) -> None:
    now = datetime.now(UTC)
    state.data.update(
        build_intake_session_metadata(
            temp_paths=[staged_path],
            cleanup_kind='accounting_document_preview',
            now=now - timedelta(minutes=6),
        )
    )


def _write_duplicate_metadata(tmp_path: Path) -> Path:
    metadata_dir = tmp_path / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / 'existing.json'
    metadata_path.write_text(
        json.dumps(
            {
                'document_type': 'receipt',
                'business': {
                    'vendor_name': 'Tesco Slovensko s.r.o.',
                    'issue_date': '2026-05-01',
                    'total_amount': '24.90',
                    'currency': 'EUR',
                    'purchase_subject': 'Kancelárske potreby',
                },
                'storage': {
                    'original_path': str(tmp_path / 'workspaces' / 'existing.jpg'),
                    'metadata_path': str(metadata_path),
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    return metadata_path


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


def _incoming_invoice_candidate() -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type='incoming_invoice',
        vendor_name='Dodavatel s.r.o.',
        document_number='INV-2026-001',
        issue_date='2026-05-02',
        due_date='2026-05-16',
        total_amount='120.50',
        currency='EUR',
        iban='SK0000000000000000000000',
        variable_symbol='2026001',
        payment_method='bank_transfer',
        purchase_subject='Material',
        quality=AccountingDocumentQuality(readability='good'),
        source=AccountingDocumentSource(input_type='pdf', original_filename='invoice.pdf'),
    )


async def _fake_classify(**kwargs) -> AccountingDocumentClassification:
    return AccountingDocumentClassification(
        document_type='receipt',
        confidence='high',
        reason='receipt layout',
    )


async def _fake_extract(**kwargs) -> AccountingDocumentCandidate:
    return _receipt_candidate()


async def _fake_extract_incoming_invoice(**kwargs) -> AccountingDocumentCandidate:
    return _incoming_invoice_candidate()


def test_doklad_starts_intake_fsm_and_asks_for_upload() -> None:
    state = _DummyState()
    message = _DummyMessage(text='/doklad')

    asyncio.run(cmd_accounting_document_intake(message, state))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert 'fotku alebo PDF' in message.answers[-1]


def test_blocek_add_commands_start_same_accounting_intake_fsm() -> None:
    for command in ('/add_blocek', '/dodat_blocek'):
        state = _DummyState()
        message = _DummyMessage(text=command)

        asyncio.run(cmd_accounting_document_intake(message, state))

        assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
        assert 'fotku alebo PDF' in message.answers[-1]


def test_waiting_upload_invalid_text_keeps_state_and_includes_cancel_hint() -> None:
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(text='neviem')

    asyncio.run(accounting_document_waiting_upload(message))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert 'fotku alebo PDF' in message.answers[-1]
    assert 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.' in message.answers[-1]


def test_waiting_upload_unsupported_document_keeps_state_and_includes_cancel_hint(tmp_path: Path) -> None:
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(document=_DummyDocument(file_name='note.txt', mime_type='text/plain'))
    bot = _DummyBot()

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), bot))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert bot.downloads == []
    assert 'fotku alebo PDF' in message.answers[-1]
    assert 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.' in message.answers[-1]


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


def test_duplicate_found_shows_warning_and_does_not_save_new_document(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_duplicate_decision.state
    assert 'Podobný doklad už existuje' in message.answers[-1]
    assert 'Odpovedzte: áno / nie.' in message.answers[-1]
    assert _staged_original_path(tmp_path).exists()
    assert len(list((tmp_path / 'workspaces').rglob('*.json'))) == 1


def test_duplicate_yes_proceeds_to_preview_without_saving(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    message = _DummyMessage(text='áno')
    asyncio.run(accounting_document_duplicate_decision(message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert 'Náhľad dokladu' in message.answers[-1]
    assert _staged_original_path(tmp_path).exists()
    assert len(list((tmp_path / 'workspaces').rglob('*.json'))) == 1


def test_duplicate_yes_then_preview_approve_saves_new_document(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_duplicate_decision(_DummyMessage(text='áno'), state, config))

    async def _resolver(**kwargs) -> str:
        return 'approve'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='schváliť'), state, config))

    assert state.current_state is None
    assert len(list((tmp_path / 'workspaces').rglob('*.json'))) == 2
    assert not _staged_original_path(tmp_path).exists()


def test_duplicate_no_cleans_temp_and_clears_state(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    message = _DummyMessage(text='nie')
    asyncio.run(accounting_document_duplicate_decision(message, state, config))

    assert state.current_state is None
    assert not _staged_original_path(tmp_path).exists()
    assert len(list((tmp_path / 'workspaces').rglob('*.json'))) == 1
    assert 'zrušené' in message.answers[-1]


def test_duplicate_unknown_keeps_state_and_temp(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    message = _DummyMessage(text='možno')
    asyncio.run(accounting_document_duplicate_decision(message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_duplicate_decision.state
    assert _staged_original_path(tmp_path).exists()
    assert 'áno alebo nie' in message.answers[-1]
    assert 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.' in message.answers[-1]


def test_duplicate_decision_uses_shared_yes_no_resolver(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)
    captured: dict[str, str] = {}

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))

    async def _resolver(**kwargs) -> str:
        captured['context_name'] = kwargs['context_name']
        captured['user_input_text'] = kwargs['user_input_text']
        return 'no'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_yes_no', _resolver)
    asyncio.run(accounting_document_duplicate_decision(_DummyMessage(text='Ah, não.'), state, config))

    assert captured == {
        'context_name': 'accounting_document_duplicate_save_decision',
        'user_input_text': 'Ah, não.',
    }


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


def test_confirmed_receipt_save_enqueues_one_pending_archive_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )

    async def _resolver(**kwargs) -> str:
        return 'approve'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='schváliť', from_user_id=111001), state, config))

    metadata_files = list((tmp_path / 'workspaces').rglob('*.json'))
    original_files = list((tmp_path / 'workspaces').rglob('*.jpg'))
    assert len(metadata_files) == 1
    assert len(original_files) == 1
    with sqlite3.connect(config.db_path) as connection:
        job_row = connection.execute('SELECT * FROM archive_jobs').fetchone()
        state_row = connection.execute('SELECT * FROM accounting_document_archive_state').fetchone()
        job_count = connection.execute('SELECT COUNT(*) FROM archive_jobs').fetchone()[0]

    assert job_count == 1
    assert job_row[1] == workspace_key_for_supplier(111001)
    assert job_row[2] == 111001
    assert job_row[3] == metadata_files[0].stem
    assert job_row[4] == 'receipt'
    assert job_row[5] == str(original_files[0])
    assert job_row[6] == str(metadata_files[0])
    assert job_row[9] == ARCHIVE_JOB_PENDING
    assert state_row[0] == metadata_files[0].stem
    assert state_row[6] == ARCHIVE_JOB_PENDING
    assert state_row[7] == job_row[0]


def test_confirmed_incoming_invoice_save_enqueues_one_pending_archive_job(monkeypatch, tmp_path: Path) -> None:
    async def _classify(**kwargs) -> AccountingDocumentClassification:
        return AccountingDocumentClassification(
            document_type='incoming_invoice',
            confidence='high',
            reason='invoice layout',
        )

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _classify)
    monkeypatch.setattr(
        'bot.handlers.accounting_document_intake.extract_accounting_document_metadata',
        _fake_extract_incoming_invoice,
    )
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(document=_DummyDocument(), from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )

    async def _resolver(**kwargs) -> str:
        return 'approve'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='schváliť', from_user_id=111001), state, config))

    metadata_files = list((tmp_path / 'workspaces').rglob('incoming_invoices/metadata/*.json'))
    original_files = list((tmp_path / 'workspaces').rglob('incoming_invoices/originals/*.pdf'))
    assert len(metadata_files) == 1
    assert len(original_files) == 1
    service = AccountingDocumentArchiveService(config.db_path)
    state_record = service.get_state(
        workspace_id=workspace_key_for_supplier(111001),
        document_id=metadata_files[0].stem,
    )

    assert state_record is not None
    assert state_record.archive_status == ARCHIVE_JOB_PENDING
    assert state_record.document_type == 'incoming_invoice'
    assert state_record.local_file_path == str(original_files[0])
    assert state_record.metadata_path == str(metadata_files[0])


def test_preview_state_does_not_enqueue_archive_job_before_confirmation(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert not config.db_path.exists()


def test_preview_cancel_does_not_enqueue_archive_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='zrušiť', from_user_id=111001), state, config))

    assert state.current_state is None
    assert not (tmp_path / 'workspaces').exists()
    assert not config.db_path.exists()


def test_failed_confirmed_save_does_not_enqueue_archive_job(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )

    async def _resolver(**kwargs) -> str:
        return 'approve'

    def _failing_save(**kwargs):
        raise OSError('disk full')

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.save_confirmed_accounting_document', _failing_save)
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='schváliť', from_user_id=111001), state, config))

    assert not config.db_path.exists()
    assert not (tmp_path / 'workspaces').exists()


def test_repeated_archive_enqueue_for_confirmed_document_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )

    async def _resolver(**kwargs) -> str:
        return 'approve'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='schváliť', from_user_id=111001), state, config))

    metadata_path = next((tmp_path / 'workspaces').rglob('*.json'))
    original_path = next((tmp_path / 'workspaces').rglob('*.jpg'))
    _enqueue_archive_after_confirmed_save(
        db_path=config.db_path,
        result=AccountingDocumentSaveResult(original_path=original_path, metadata_path=metadata_path),
        candidate=_receipt_candidate(),
        supplier_telegram_id=111001,
    )

    with sqlite3.connect(config.db_path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM archive_jobs').fetchone()[0] == 1


def test_archive_enqueue_failure_keeps_confirmed_document_without_google_or_cleanup(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)
    log_calls: list[tuple[str, tuple, dict]] = []

    asyncio.run(
        accounting_document_upload(
            _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001),
            state,
            config,
            _DummyBot(),
        )
    )

    async def _resolver(**kwargs) -> str:
        return 'approve'

    def _failing_enqueue(self, **kwargs):
        raise RuntimeError(f'archive unavailable at {tmp_path / "secret-path"} with sk-test-token')

    def _capture_warning(message: str, *args, **kwargs) -> None:
        log_calls.append((message, args, kwargs))

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_approve_edit_cancel', _resolver)
    monkeypatch.setattr(
        'bot.handlers.accounting_document_intake.AccountingDocumentArchiveService.enqueue_confirmed_document',
        _failing_enqueue,
    )
    monkeypatch.setattr('bot.handlers.accounting_document_intake.logger.warning', _capture_warning)
    decision_message = _DummyMessage(text='schváliť', from_user_id=111001)
    asyncio.run(accounting_document_preview_decision(decision_message, state, config))

    original_path = next((tmp_path / 'workspaces').rglob('*.jpg'))
    metadata_path = next((tmp_path / 'workspaces').rglob('*.json'))
    assert log_calls
    rendered_log = log_calls[0][0] % log_calls[0][1]

    assert original_path.exists()
    assert not (tmp_path / 'uploads' / 'accounting_intake' / '111001' / 'PHOTO123').exists()
    assert not config.db_path.exists()
    assert state.current_state is None
    assert 'Doklad bol uložený.' in decision_message.answers[-1]
    assert 'archive_enqueue_failed' in rendered_log
    assert str(original_path) not in rendered_log
    assert str(metadata_path) not in rendered_log
    assert metadata_path.stem not in rendered_log
    assert 'secret-path' not in rendered_log
    assert 'sk-test-token' not in rendered_log
    assert 'archive unavailable' not in rendered_log
    assert not log_calls[0][2].get('exc_info')


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
    assert 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.' in message.answers[-1]


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


def test_expired_accounting_preview_cleans_temp_and_skips_approve(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _expire_accounting_state(state, staged_path)
    message = _DummyMessage(text='schváliť')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state is None
    assert not staged_path.exists()
    assert not (tmp_path / 'workspaces').exists()
    assert 'nečinnosti' in message.answers[-1]


def test_expired_accounting_preview_cleans_temp_and_skips_cancel(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _expire_accounting_state(state, staged_path)
    message = _DummyMessage(text='zrušiť')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state is None
    assert not staged_path.exists()
    assert 'nečinnosti' in message.answers[-1]


def test_expired_accounting_preview_cleans_temp_and_skips_edit(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _expire_accounting_state(state, staged_path)
    message = _DummyMessage(text='upraviť')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state is None
    assert not staged_path.exists()
    assert 'nečinnosti' in message.answers[-1]


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
    assert 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.' in message.answers[-1]


def test_voice_expired_accounting_preview_cleans_temp_and_does_not_fall_back_to_invoice(
    monkeypatch,
    tmp_path: Path,
) -> None:
    invoice_fallback_calls: list[str] = []
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _expire_accounting_state(state, staged_path)
    _patch_accounting_voice(monkeypatch, 'schváliť', invoice_fallback_calls)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert state.current_state is None
    assert not staged_path.exists()
    assert not (tmp_path / 'workspaces').exists()
    assert 'nečinnosti' in message.answers[-1]


def test_voice_duplicate_decision_routes_to_same_helper(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    invoice_fallback_calls: list[str] = []
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _voice_config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    _patch_accounting_voice(monkeypatch, 'áno', invoice_fallback_calls)
    message = _DummyMessage(voice=_DummyVoice())
    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert 'Náhľad dokladu' in message.answers[-1]
    assert _staged_original_path(tmp_path).exists()


def test_voice_expired_duplicate_decision_cleans_temp_and_does_not_fall_back_to_invoice(
    monkeypatch,
    tmp_path: Path,
) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    invoice_fallback_calls: list[str] = []
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _voice_config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    _expire_accounting_state(state, _staged_original_path(tmp_path))
    _patch_accounting_voice(monkeypatch, 'áno', invoice_fallback_calls)
    message = _DummyMessage(voice=_DummyVoice())
    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert state.current_state is None
    assert not _staged_original_path(tmp_path).exists()
    assert 'nečinnosti' in message.answers[-1]


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
