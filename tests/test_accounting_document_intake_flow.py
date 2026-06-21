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
    accounting_document_category_selection,
    accounting_document_duplicate_decision,
    accounting_document_new_category_confirm,
    accounting_document_new_category_label,
    accounting_document_preview_decision,
    accounting_document_unknown_category_decision,
    accounting_document_upload,
    accounting_document_waiting_upload,
    cmd_accounting_document_intake,
)
from bot.services.accounting_document_storage import AccountingDocumentSaveResult, workspace_key_for_supplier
from bot.handlers.voice import handle_voice
from bot.services.accounting_document_classifier import AccountingDocumentClassification
from bot.services.accounting_document_models import (
    AccountingDocumentCandidate,
    AccountingDocumentCategoryCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
    AccountingDocumentSuggestedCategory,
)
from bot.services.accounting_document_archive_service import AccountingDocumentArchiveService
from bot.services.archive_job_service import ARCHIVE_JOB_PENDING
from bot.services.decision_resolver import resolve_accounting_document_category_preview_decision
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
        self.reply_markups: list[object] = []
        self.message_id = 77
        if from_user_id is not None:
            self.from_user = _DummyUser(from_user_id)

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)
        self.reply_markups.append(kwargs.get('reply_markup'))


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


def _keyboard_texts(markup: object | None) -> list[str]:
    keyboard = getattr(markup, 'keyboard', None)
    if keyboard is None:
        return []
    return [getattr(button, 'text', '') for row in keyboard for button in row]


def _is_keyboard_removed(markup: object | None) -> bool:
    return bool(getattr(markup, 'remove_keyboard', False))


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


def _unknown_category_receipt_candidate() -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Tesco Slovensko s.r.o.',
        issue_date='2026-05-01',
        total_amount='24.90',
        currency='EUR',
        payment_method='card',
        purchase_subject='Nejasný nákup',
        document_category_candidate=AccountingDocumentCategoryCandidate(
            category_id='unknown_review',
            confidence='low',
            review_required=True,
            reason='unclear purchase',
        ),
        suggested_new_categories=[
            AccountingDocumentSuggestedCategory(label_sk='Špeciálny nákup', reason='visible text'),
        ],
        quality=AccountingDocumentQuality(readability='good'),
        source=AccountingDocumentSource(input_type='photo', original_filename='photo.jpg'),
    )


def _categorized_receipt_candidate() -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Papier s.r.o.',
        issue_date='2026-05-01',
        total_amount='24.90',
        currency='EUR',
        payment_method='card',
        purchase_subject='Kancelárske potreby',
        document_category_candidate=AccountingDocumentCategoryCandidate(
            category_id='office_supplies',
            confidence='medium',
            review_required=False,
            reason='paper and office text',
        ),
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
    assert 'Navrhovaná kategória: nezistená' in message.answers[-1]


def test_upload_passes_allowed_categories_to_lmm(monkeypatch, tmp_path: Path) -> None:
    captured_allowed_categories: list[list[dict]] = []

    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        captured_allowed_categories.append(kwargs['allowed_categories'])
        return _categorized_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()], from_user_id=111001)

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert captured_allowed_categories
    assert any(item['category_id'] == 'office_supplies' for item in captured_allowed_categories[0])
    assert any(item['category_id'] == 'unknown_review' for item in captured_allowed_categories[0])
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert 'Navrhovaná kategória: office_supplies' in message.answers[-1]


def test_unknown_category_candidate_prompts_before_preview(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_unknown_category_decision.state
    assert 'Najprv skúste vybrať existujúcu kategóriu.' in message.answers[-1]
    assert 'Špeciálny nákup' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()


def test_unknown_category_create_cancel_does_not_create_category_or_save(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_unknown_category_decision(_DummyMessage(text='vytvoriť novú kategóriu'), state, config))
    asyncio.run(accounting_document_new_category_label(_DummyMessage(text='Moja nová kategória'), state, config))
    asyncio.run(accounting_document_new_category_confirm(_DummyMessage(text='nie'), state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert not list((tmp_path / 'workspaces').rglob('categories.json'))
    assert not list((tmp_path / 'workspaces').rglob('receipts/metadata/*.json'))


def test_create_new_category_then_save_persists_confirmed_snapshot(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()], from_user_id=111001), state, config, _DummyBot()))
    asyncio.run(accounting_document_unknown_category_decision(_DummyMessage(text='vytvoriť novú kategóriu', from_user_id=111001), state, config))
    asyncio.run(accounting_document_new_category_label(_DummyMessage(text='Klientske náklady', from_user_id=111001), state, config))
    asyncio.run(accounting_document_new_category_confirm(_DummyMessage(text='áno', from_user_id=111001), state, config))
    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert 'Klientske náklady' in state.data['accounting_document_candidate']['category']['label_snapshot']

    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='uložiť s kategóriou', from_user_id=111001), state, config))

    metadata_path = next((tmp_path / 'workspaces').rglob('receipts/metadata/*.json'))
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    assert metadata['category']['label_snapshot'] == 'Klientske náklady'
    assert metadata['category']['category_id'].startswith('workspace_klientske_naklady')


def test_change_document_category_updates_preview_only_until_save(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _categorized_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='zmeniť kategóriu'), state, config))
    asyncio.run(accounting_document_category_selection(_DummyMessage(text='materials'), state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state
    assert state.data['accounting_document_candidate']['category']['category_id'] == 'materials'
    assert not list((tmp_path / 'workspaces').rglob('receipts/metadata/*.json'))

    asyncio.run(accounting_document_preview_decision(_DummyMessage(text='uložiť s kategóriou'), state, config))
    metadata_path = next((tmp_path / 'workspaces').rglob('receipts/metadata/*.json'))
    metadata = json.loads(metadata_path.read_text(encoding='utf-8'))
    assert metadata['category']['category_id'] == 'materials'


def test_duplicate_found_shows_warning_and_does_not_save_new_document(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_duplicate_decision.state
    assert 'POZOR! Tento doklad už je uložený!!!!' in message.answers[-1]
    assert 'Ak je to ten istý bloček, nepridávajte ho znova.' in message.answers[-1]
    assert '/menu' in message.answers[-1]
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
        return 'save_with_category'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
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
        return 'save_with_category'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
    decision_message = _DummyMessage(text='schváliť')
    asyncio.run(accounting_document_preview_decision(decision_message, state, config))

    assert captured == {
        'context_name': 'accounting_document_category_preview_decision',
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
        return 'save_with_category'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
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
        return 'save_with_category'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
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
        return 'save_with_category'

    def _failing_save(**kwargs):
        raise OSError('disk full')

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
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
        return 'save_with_category'

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
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
        return 'save_with_category'

    def _failing_enqueue(self, **kwargs):
        raise RuntimeError(f'archive unavailable at {tmp_path / "secret-path"} with sk-test-token')

    def _capture_warning(message: str, *args, **kwargs) -> None:
        log_calls.append((message, args, kwargs))

    monkeypatch.setattr('bot.handlers.accounting_document_intake.resolve_accounting_document_category_preview_decision', _resolver)
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
    assert 'uložiť s kategóriou, zmeniť kategóriu, uložiť bez kategórie alebo zrušiť' in message.answers[-1]
    assert 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.' in message.answers[-1]


def test_upravit_opens_accounting_document_category_selection_without_save(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    message = _DummyMessage(text='upraviť')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_document_category_selection.state
    assert staged_path.exists()
    assert 'Vyberte kategóriu z existujúceho zoznamu.' in message.answers[-1]
    assert not (tmp_path / 'workspaces').exists()


def test_upravit_cyrillic_keeps_accounting_preview_state_if_unknown_or_edit(monkeypatch, tmp_path: Path) -> None:
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    message = _DummyMessage(text='управить')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    assert state.current_state in {
        AccountingDocumentIntakeStates.waiting_preview_decision.state,
        AccountingDocumentIntakeStates.waiting_document_category_selection.state,
    }
    assert staged_path.exists()
    assert not (tmp_path / 'workspaces').exists()
    assert message.answers[-1] in {
        'Prosím, vyberte: uložiť s kategóriou, zmeniť kategóriu, uložiť bez kategórie alebo zrušiť.\n\nAk chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.',
    } or 'Vyberte kategóriu z existujúceho zoznamu.' in message.answers[-1]


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


def test_voice_accounting_preview_edit_opens_category_selection(monkeypatch, tmp_path: Path) -> None:
    invoice_fallback_calls: list[str] = []
    state, config = _prepare_accounting_preview(monkeypatch, tmp_path)
    staged_path = _staged_original_path(tmp_path)
    _patch_accounting_voice(monkeypatch, 'upraviť', invoice_fallback_calls)
    message = _DummyMessage(voice=_DummyVoice())

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert invoice_fallback_calls == []
    assert state.current_state == AccountingDocumentIntakeStates.waiting_document_category_selection.state
    assert staged_path.exists()
    assert 'Vyberte kategóriu z existujúceho zoznamu.' in message.answers[-1]


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
    assert 'uložiť s kategóriou, zmeniť kategóriu, uložiť bez kategórie alebo zrušiť' in message.answers[-1]
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
        resolve_accounting_document_category_preview_decision(
            context_name='accounting_document_category_preview_decision',
            user_input_text='schváliť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'save_with_category'
    assert asyncio.run(
        resolve_accounting_document_category_preview_decision(
            context_name='accounting_document_category_preview_decision',
            user_input_text='zrušiť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'cancel'

def test_category_preview_reply_keyboard_offers_standard_decisions(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    buttons = _keyboard_texts(message.reply_markups[-1])
    assert '✅ Uložiť s kategóriou' in buttons
    assert '✏️ Zmeniť kategóriu' in buttons
    assert '📎 Uložiť bez kategórie' in buttons
    assert '❌ Zrušiť' in buttons
    assert '✏️ Zmeniť kategóriu položky' not in buttons


def test_unknown_category_reply_keyboard_prioritizes_existing_category(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    buttons = _keyboard_texts(message.reply_markups[-1])
    assert buttons[:4] == [
        '📂 Vybrať existujúcu kategóriu',
        '➕ Vytvoriť novú kategóriu',
        '📎 Uložiť ako Na kontrolu',
        '❌ Zrušiť',
    ]


def test_duplicate_prompt_reply_keyboard_offers_loud_duplicate_choices(monkeypatch, tmp_path: Path) -> None:
    _write_duplicate_metadata(tmp_path)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    message = _DummyMessage(photo=[_DummyPhoto()])

    asyncio.run(accounting_document_upload(message, state, _config(tmp_path), _DummyBot()))

    assert _keyboard_texts(message.reply_markups[-1]) == ['➕ Pridať iný bloček', '⚠️ Uložiť aj tak', '🏠 /menu']


def test_category_selection_reply_keyboard_uses_display_labels(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _categorized_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)
    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    message = _DummyMessage(text='zmeniť kategóriu')

    asyncio.run(accounting_document_preview_decision(message, state, config))

    buttons = _keyboard_texts(message.reply_markups[-1])
    assert 'Materiál' in buttons
    assert 'Kancelárske potreby' in buttons
    assert '↩️ Späť' in buttons
    assert 'materials' not in buttons


def test_unknown_category_existing_selection_can_continue_to_create_new(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_unknown_category_decision(_DummyMessage(text='vybrat existujucu kategoriu'), state, config))
    selection_message = _DummyMessage(text='vytvorit novu kategoriu')
    asyncio.run(accounting_document_category_selection(selection_message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_new_category_label.state
    assert state.data['accounting_document_category_target'] == 'document'
    assert 'Zadajte' in selection_message.answers[-1]
    assert 'textom' in selection_message.answers[-1]
    assert _is_keyboard_removed(selection_message.reply_markups[-1])


def test_unknown_category_existing_selection_back_returns_to_unknown_menu(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)

    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_unknown_category_decision(_DummyMessage(text='vybrat existujucu kategoriu'), state, config))
    back_message = _DummyMessage(text='spat')
    asyncio.run(accounting_document_category_selection(back_message, state, config))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_unknown_category_decision.state
    assert 'Najprv' in back_message.answers[-1]
    assert 'existuj' in back_message.answers[-1]
    back_buttons = _keyboard_texts(back_message.reply_markups[-1])
    assert len(back_buttons) >= 4
    assert any('existuj' in button for button in back_buttons)
    assert any('Vytvori' in button for button in back_buttons)


def test_new_category_and_similar_decision_reply_keyboards(monkeypatch, tmp_path: Path) -> None:
    async def _extract(**kwargs) -> AccountingDocumentCandidate:
        return _unknown_category_receipt_candidate()

    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)
    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_unknown_category_decision(_DummyMessage(text='vytvoriť novú kategóriu'), state, config))

    label_message = _DummyMessage(text='Unikátna kategória')
    asyncio.run(accounting_document_new_category_label(label_message, state, config))
    assert _keyboard_texts(label_message.reply_markups[-1]) == ['✅ Áno', '❌ Nie']

    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    asyncio.run(accounting_document_unknown_category_decision(_DummyMessage(text='vytvoriť novú kategóriu'), state, config))
    similar_message = _DummyMessage(text='Kancelárske potreby')
    asyncio.run(accounting_document_new_category_label(similar_message, state, config))
    assert _keyboard_texts(similar_message.reply_markups[-1]) == [
        '✅ Použiť existujúcu',
        '➕ Vytvoriť novú aj tak',
        '↩️ Späť',
    ]


def test_success_and_cancel_remove_category_reply_keyboard(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr('bot.handlers.accounting_document_intake.classify_accounting_document', _fake_classify)
    monkeypatch.setattr('bot.handlers.accounting_document_intake.extract_accounting_document_metadata', _fake_extract)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    config = _config(tmp_path)
    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()], from_user_id=111001), state, config, _DummyBot()))

    save_message = _DummyMessage(text='uložiť s kategóriou', from_user_id=111001)
    asyncio.run(accounting_document_preview_decision(save_message, state, config))

    assert 'Doklad bol uložený.' in save_message.answers[-1]
    assert 'Ďalšie kroky:' in save_message.answers[-1]
    assert '/add_blocek' in save_message.answers[-1]
    assert '/blocek' in save_message.answers[-1]
    assert '/menu' in save_message.answers[-1]
    assert 'Metadata:' not in save_message.answers[-1]
    assert _is_keyboard_removed(save_message.reply_markups[-1])

    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state)
    asyncio.run(accounting_document_upload(_DummyMessage(photo=[_DummyPhoto()]), state, config, _DummyBot()))
    cancel_message = _DummyMessage(text='zrušiť')
    asyncio.run(accounting_document_preview_decision(cancel_message, state, config))
    assert _is_keyboard_removed(cancel_message.reply_markups[-1])
