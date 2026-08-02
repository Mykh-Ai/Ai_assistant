from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import json
import logging
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
from bot.handlers.access_admin import CustomizationRequestAdminResponseStates
from bot.handlers.contacts import ContactStates
from bot.handlers.delete_user_database import DeleteUserDatabaseStates, VOICE_EXACT_CONFIRMATION_MESSAGE
from bot.handlers.invoice import CustomizationRequestStates, InvoiceStates
from bot.handlers.work_time import WorkTimeStates
from bot.handlers.onboarding import OnboardingStates, SupplierProfileEditStates
from bot.handlers.supplier import ServiceAliasStates
from bot.handlers.voice import handle_voice
from bot.services.active_fsm_guard import ACTIVE_FSM_LAST_ACTIVITY_AT_KEY
from bot.services.customization_requests import CustomizationRequestService
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService


class _DummyVoice:
    def __init__(self, file_id: str) -> None:
        self.file_id = file_id


class _DummyMessage:
    def __init__(self) -> None:
        self.voice = _DummyVoice('voice-file-id')
        self.answers: list[str] = []
        self.message_id = 77
        self.from_user = type('_User', (), {'id': 111})()

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class _DummyBot:
    class _File:
        def __init__(self) -> None:
            self.file_path = 'voice.ogg'

    async def get_file(self, file_id: str):
        return self._File()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'voice')


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type('_Msg', (), {'content': content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _VoiceInfoHelpOpenAIFake:
    output = '{"capability_id":"unknown","topic_id":"unknown","triage_class":"unknown","confidence":0,"needs_clarification":false}'
    last_payload: dict | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _VoiceInfoHelpOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(_VoiceInfoHelpOpenAIFake.output)


class _DummyState:
    def __init__(self, current_state: str | None) -> None:
        self.current_state = current_state
        self.data: dict = {}

    async def get_state(self) -> str | None:
        return self.current_state

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        data = dict(self.data)
        if self.current_state is not None and ACTIVE_FSM_LAST_ACTIVITY_AT_KEY not in data:
            data[ACTIVE_FSM_LAST_ACTIVITY_AT_KEY] = datetime.now(UTC).isoformat()
        return data
    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()


def _customization_request_draft(request_id: str = 'cr_voice') -> dict:
    return {
        'request_id': request_id,
        'requester_telegram_id': 111,
        'supplier_telegram_id': 111,
        'workspace_id': 'telegram:111',
        'source_channel': 'voice',
        'source_triage_class': 'customization_request_candidate',
        'source_capability_id': None,
        'source_topic_id': None,
        'normalized_title': 'Po\u017eiadavka: Mesa\u010dn\u00fd report',
        'normalized_summary': 'Chcem mesa\u010dn\u00fd report tr\u017eieb.',
        'redacted_original_text': 'Chcem mesa\u010dn\u00fd report tr\u017eieb.',
        'raw_text_hash': '1' * 64,
        'confidence': 0.8,
    }


def _config(tmp_path: Path, *, debug_invoice_transparency: bool = False) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=debug_invoice_transparency,
        db_path=tmp_path / 'voice.db',
        storage_dir=tmp_path,
    )


def test_voice_waiting_confirm_routes_to_preview_confirmation(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    async def _stt(*args, **kwargs) -> str:
        return 'так'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    async def _preview(**kwargs) -> None:
        calls.append('preview')

    async def _postpdf(**kwargs) -> None:
        calls.append('postpdf')

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _postpdf)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(InvoiceStates.waiting_confirm.state)))
    assert calls == ['preview']


def test_voice_delete_database_final_confirmation_is_typed_only(monkeypatch, tmp_path: Path) -> None:
    async def _unexpected_stt(*args, **kwargs) -> str:
        raise AssertionError('final delete confirmation must not call STT')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _unexpected_stt)

    message = _DummyMessage()
    asyncio.run(
        handle_voice(
            message,
            _DummyBot(),
            _config(tmp_path),
            _DummyState(DeleteUserDatabaseStates.waiting_exact_confirmation.state),
        )
    )

    assert message.answers == [VOICE_EXACT_CONFIRMATION_MESSAGE]


def test_voice_waiting_confirm_routes_to_preview_confirmation_for_uk_no(monkeypatch, tmp_path: Path) -> None:
    captured_confirmation_text: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'Ні.'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    async def _preview(**kwargs) -> None:
        captured_confirmation_text.append(kwargs.get('confirmation_text'))

    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', lambda **kwargs: None)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_confirm.state),
        )
    )
    assert captured_confirmation_text == ['Ні.']


def test_voice_waiting_confirm_logs_confirm_routing_for_noisy_stt(monkeypatch, tmp_path: Path, caplog) -> None:
    captured_confirmation_text: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'Ah, não!'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    async def _preview(**kwargs) -> None:
        captured_confirmation_text.append(kwargs.get('confirmation_text'))

    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', lambda **kwargs: None)

    config = _config(tmp_path, debug_invoice_transparency=True)
    with caplog.at_level(logging.INFO):
        asyncio.run(
            handle_voice(
                _DummyMessage(),
                _DummyBot(),
                config,
                _DummyState(InvoiceStates.waiting_confirm.state),
            )
        )

    assert captured_confirmation_text == ['Ah, não!']
    assert any('"event": "confirm_voice_routing"' in rec.message for rec in caplog.records)


def test_voice_waiting_pdf_decision_routes_to_postpdf(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    async def _stt(*args, **kwargs) -> str:
        return 'schváliť'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    async def _preview(**kwargs) -> None:
        calls.append('preview')

    async def _postpdf(**kwargs) -> None:
        calls.append('postpdf')

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _postpdf)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_pdf_decision.state),
        )
    )
    assert calls == ['postpdf']


def test_voice_waiting_pdf_decision_logs_approval_routing_and_passes_stt_text(monkeypatch, tmp_path: Path, caplog) -> None:
    captured_decision_text: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ЗРУШИТИ'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    async def _postpdf(**kwargs) -> None:
        captured_decision_text.append(kwargs.get('decision_text'))

    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _postpdf)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', lambda **kwargs: None)

    config = _config(tmp_path, debug_invoice_transparency=True)
    with caplog.at_level(logging.INFO):
        asyncio.run(
            handle_voice(
                _DummyMessage(),
                _DummyBot(),
                config,
                _DummyState(InvoiceStates.waiting_pdf_decision.state),
            )
        )

    assert captured_decision_text == ['ЗРУШИТИ']
    assert any('"event": "approval_voice_routing"' in rec.message for rec in caplog.records)


def test_voice_non_decision_state_routes_to_generic_create_flow(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    async def _stt(*args, **kwargs) -> str:
        return 'vytvor fakturu'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    async def _preview(**kwargs) -> None:
        calls.append('preview')

    async def _postpdf(**kwargs) -> None:
        calls.append('postpdf')

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', _preview)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _postpdf)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['generic']


def test_voice_waiting_invoice_input_routes_to_invoice_text(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'urob faktúru pre Tech Company za opravu'

    async def _invoice_text(**kwargs) -> None:
        calls.append(kwargs['invoice_text'])

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _invoice_text)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_input.state),
        )
    )
    assert calls == ['urob faktúru pre Tech Company za opravu']


def test_voice_contact_missing_state_requires_text_input(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'kontakt@zs.sk'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', lambda **kwargs: None)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', lambda **kwargs: None)

    async def _contact_missing(**kwargs) -> None:
        calls.append('contact_missing')

    monkeypatch.setattr('bot.handlers.voice.process_contact_intake_confirm', lambda **kwargs: None)

    message = _DummyMessage()
    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), _DummyState(ContactStates.intake_missing.state)))
    assert calls == []
    assert message.answers[-1] == 'V tomto kroku prosím doplňte chýbajúci údaj textom.'


def test_voice_delete_invoice_confirm_routes_to_delete_confirmation_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ok'

    async def _delete_confirm(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_delete_existing_invoice_confirm', _delete_confirm)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_delete_existing_invoice_confirm.state),
        )
    )
    assert calls == ['ok']


def test_voice_manual_contact_confirm_routes_to_contact_confirmation_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ok'

    async def _contact_confirm(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.contact_confirm', _contact_confirm)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(ContactStates.confirm.state),
        )
    )
    assert calls == ['ok']


def test_voice_onboarding_confirm_routes_to_onboarding_confirmation_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ok'

    async def _onboarding_confirm(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.onboarding_confirm', _onboarding_confirm)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(OnboardingStates.confirm.state),
        )
    )
    assert calls == ['ok']


def test_voice_name_hint_state_requires_text_input(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'ZS'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    msg = _DummyMessage()
    asyncio.run(handle_voice(msg, _DummyBot(), _config(tmp_path), _DummyState(ContactStates.name_hint.state)))
    assert msg.answers[-1] == 'V tomto kroku zadajte názov firmy textom.'


def test_voice_source_after_name_state_requires_text_or_pdf(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return '12345678'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    msg = _DummyMessage()
    asyncio.run(handle_voice(msg, _DummyBot(), _config(tmp_path), _DummyState(ContactStates.source_after_name.state)))
    assert msg.answers[-1] == 'V tomto kroku pošlite zmluvu/PDF alebo zadajte IČO textom.'


def test_voice_waiting_service_clarification_routes_to_service_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'oprava'

    async def _service(**kwargs) -> None:
        calls.append('service')

    async def _slot(**kwargs) -> None:
        calls.append('slot')

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', _service)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', _slot)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_service_clarification.state),
        )
    )
    assert calls == ['service']


def test_voice_waiting_slot_clarification_routes_to_slot_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    captured_text: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'два крат по 1500'

    async def _service(**kwargs) -> None:
        calls.append('service')

    async def _slot(**kwargs) -> None:
        calls.append('slot')
        captured_text.append(kwargs.get('clarification_text'))

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', _service)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', _slot)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_slot_clarification.state),
        )
    )
    assert calls == ['slot']
    assert captured_text == ['два крат по 1500']


def test_voice_waiting_customer_alias_confirm_routes_to_alias_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []
    captured_text: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ano'

    async def _alias(**kwargs) -> None:
        calls.append('alias')
        captured_text.append(kwargs.get('answer_text'))

    async def _generic(**kwargs) -> None:
        calls.append('generic')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_customer_alias_confirm', _alias)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_preview_confirmation', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_service_clarification', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_slot_clarification', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _generic)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_customer_alias_confirm.state),
        )
    )

    assert calls == ['alias']
    assert captured_text == ['ano']


def test_voice_waiting_edit_description_requires_text_input(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'dopln text pre halu B'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    msg = _DummyMessage()
    asyncio.run(
        handle_voice(
            msg,
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_description_value.state),
        )
    )
    assert msg.answers[-1].startswith('Pre finálny opis položky použite textový vstup.')


def test_voice_waiting_edit_scope_routes_to_edit_scope_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'položka'

    async def _scope(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_scope', _scope)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_scope.state),
        )
    )
    assert calls == ['položka']


def test_voice_global_cancel_in_active_state_runs_shared_cancel(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'відмінити'

    async def _scope(**kwargs) -> None:
        calls.append('edit_scope')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_scope', _scope)

    message = _DummyMessage()
    state = _DummyState(InvoiceStates.waiting_edit_scope.state)
    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), state))

    assert calls == []
    assert state.current_state is None
    assert message.answers == ['Rozpracovaná akcia bola zrušená. Bot je v režime čakania.']


def test_voice_exact_global_cancel_bypasses_llm_resolver(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'скасувати'

    async def _unexpected_resolver(**kwargs) -> str:
        raise AssertionError('exact global cancel transcript must not call LLM resolver')

    async def _scope(**kwargs) -> None:
        calls.append('edit_scope')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.services.decision_resolver.resolve_semantic_action', _unexpected_resolver)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_scope', _scope)

    message = _DummyMessage()
    state = _DummyState(InvoiceStates.waiting_edit_scope.state)
    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), state))

    assert calls == []
    assert state.current_state is None
    assert message.answers == ['Rozpracovaná akcia bola zrušená. Bot je v režime čakania.']

def test_voice_waiting_edit_item_target_routes_to_item_target_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return '2'

    async def _target(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_item_target', _target)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_item_target.state),
        )
    )
    assert calls == ['2']


def test_voice_waiting_edit_invoice_action_routes_to_invoice_action_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'upraviť číslo faktúry'

    async def _invoice_action(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_invoice_action', _invoice_action)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_invoice_action.state),
        )
    )
    assert calls == ['upraviť číslo faktúry']


def test_voice_waiting_edit_invoice_action_routes_date_text_to_invoice_action_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'upraviť dátum faktúry'

    async def _invoice_action(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_invoice_action', _invoice_action)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_invoice_action.state),
        )
    )
    assert calls == ['upraviť dátum faktúry']


def test_voice_waiting_edit_item_action_routes_to_item_action_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'zmeniť službu'

    async def _action(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_item_action', _action)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_item_action.state),
        )
    )
    assert calls == ['zmeniť službu']


def test_voice_waiting_edit_service_value_routes_to_service_value_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'montaz'

    async def _service_value(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_service_value', _service_value)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_service_value.state),
        )
    )
    assert calls == ['montaz']


def test_voice_waiting_edit_invoice_number_value_requires_text_input(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'zmeň číslo na dvadsať dva'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    message = _DummyMessage()
    asyncio.run(
        handle_voice(
            message,
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_invoice_number_value.state),
        )
    )
    assert message.answers[-1] == 'Číslo faktúry prosím zadajte textom vo formáte RRRRNNNN.'


def test_voice_waiting_edit_invoice_date_value_routes_to_date_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'zmeň dátum na pätnásteho marca'

    async def _date_value(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_invoice_date_value', _date_value)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_invoice_date_value.state),
        )
    )
    assert calls == ['zmeň dátum na pätnásteho marca']


def test_voice_supplier_profile_field_routes_to_field_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'chcem zmeniť IBAN'

    async def _field(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.supplier_profile_edit_field', _field)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(SupplierProfileEditStates.field.state),
        )
    )
    assert calls == ['chcem zmeniť IBAN']


def test_voice_supplier_profile_value_requires_text_input(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'novy iban je es ka...'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    message = _DummyMessage()
    asyncio.run(
        handle_voice(
            message,
            _DummyBot(),
            _config(tmp_path),
            _DummyState(SupplierProfileEditStates.value.state),
        )
    )
    assert message.answers[-1] == 'V tomto kroku prosím zadajte hodnotu textom.'


def test_voice_top_level_add_service_alias_routes_to_existing_service_flow(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'pridaj novú položku'

    calls: list[str] = []

    async def _invoice_text(**kwargs) -> None:
        calls.append('invoice_text')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _invoice_text)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['invoice_text']


def test_voice_idle_start_routes_to_existing_start_flow(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'почати'

    calls: list[str] = []

    async def _start(**kwargs) -> None:
        calls.append('start')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.cmd_start', _start)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['start']


def test_voice_idle_show_existing_invoice_reaches_top_level_router(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'покажи фактуру 04'

    calls: list[str] = []

    async def _invoice_text(**kwargs) -> None:
        calls.append(kwargs['invoice_text'])

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _invoice_text)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['покажи фактуру 04']


def test_voice_idle_invoice_period_summary_answers_from_top_level_router(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Na akú sumu som vystavil faktúry v tomto roku?'

    config = _config(tmp_path)
    init_db(config.db_path)
    InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        invoice_number='20260001',
        issue_date='2026-02-10',
        delivery_date='2026-02-10',
        due_date='2026-02-24',
        due_days=14,
        total_amount=120,
        currency='EUR',
        status='created',
        items=[
            CreateInvoiceItemPayload(
                description_raw='oprava',
                description_normalized='Oprava',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=120,
                total_price=120,
            )
        ],
    )
    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)

    message = _DummyMessage()
    state = _DummyState(None)
    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state is None
    assert 'Súhrn vystavených faktúr za aktuálny rok 2026' in message.answers[-1]
    assert 'Počet faktúr: 1' in message.answers[-1]
    assert 'Celkom: 120.00 EUR' in message.answers[-1]
    assert not (tmp_path / 'invoices').exists()


def test_voice_idle_invoice_analytics_reaches_top_level_router(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Покажи фактури за травень'

    calls: list[tuple[str, str]] = []

    async def _invoice_text(**kwargs) -> None:
        calls.append((kwargs['invoice_text'], kwargs['input_channel']))

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _invoice_text)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == [('Покажи фактури за травень', 'voice')]


def test_voice_idle_profile_routes_to_profile_view(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'môj profil'

    calls: list[str] = []

    async def _profile(**kwargs) -> None:
        calls.append('profile')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.cmd_moj_profil', _profile)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['profile']


def test_voice_idle_unknown_gets_info_help_guidance(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'blabla'

    async def _resolver(**kwargs) -> str:
        return 'unknown'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)

    message = _DummyMessage()
    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), _DummyState(None)))

    assert message.answers[-1] == (
        'Tejto správe som nerozumel.\nSkúste prosím stručne napísať, čo chcete urobiť.'
    )


@pytest.mark.parametrize(
    ('transcript', 'expected_fragment'),
    [
        ('Ak\u00e9 bude po\u010dasie zajtra?', 'mimo rozsahu OfficeFlow'),
        ('Ako sa m\u00e1\u0161?', 'biznis \u00falohami'),
        ('urob mi to', 'Tejto spr\u00e1ve som nerozumel.'),
    ],
)
def test_voice_idle_transcript_uses_safe_info_help_triage(
    monkeypatch,
    tmp_path: Path,
    transcript: str,
    expected_fragment: str,
) -> None:
    async def _stt(*args, **kwargs) -> str:
        return transcript

    async def _resolver(**kwargs) -> str:
        return 'unknown'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)

    message = _DummyMessage()
    state = _DummyState(None)
    config = _config(tmp_path)

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state is None
    assert expected_fragment in message.answers[-1]
    assert 'podporovan\u00e9' not in message.answers[-1]
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_voice_idle_transcript_can_start_customization_request_preview(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Vie\u0161 mi spravi\u0165 preh\u013ead tr\u017eieb za minul\u00fd mesiac?'

    async def _resolver(**kwargs) -> str:
        return 'unknown'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)

    message = _DummyMessage()
    state = _DummyState(None)
    config = _config(tmp_path)

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state == CustomizationRequestStates.waiting_preview_decision.state
    assert 'N\u00e1vrh po\u017eiadavky' in message.answers[-1]
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_voice_customization_preview_approve_saves_one_request(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'schv\u00e1li\u0165'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(CustomizationRequestStates.waiting_preview_decision.state)
    state.data = {
        'customization_request_draft': _customization_request_draft('cr_voice_approve'),
        'customization_request_saved_id': None,
    }
    message = _DummyMessage()

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    records = CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111)
    assert len(records) == 1
    assert records[0].request_id == 'cr_voice_approve'
    assert state.current_state is None


def test_voice_customization_preview_cancel_saves_nothing(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'zru\u0161i\u0165'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(CustomizationRequestStates.waiting_preview_decision.state)
    state.data = {
        'customization_request_draft': _customization_request_draft('cr_voice_cancel'),
        'customization_request_saved_id': None,
    }
    message = _DummyMessage()

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(telegram_id=111) == []
    assert state.current_state is None


def test_voice_customization_edit_text_is_text_first(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Nov\u00fd presn\u00fd n\u00e1zov'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    original_draft = _customization_request_draft('cr_voice_edit')
    state = _DummyState(CustomizationRequestStates.waiting_edit_text.state)
    state.data = {'customization_request_draft': dict(original_draft)}
    message = _DummyMessage()

    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), state))

    assert state.current_state == CustomizationRequestStates.waiting_edit_text.state
    assert state.data['customization_request_draft'] == original_draft
    assert 'textom' in message.answers[-1]


def test_voice_admin_response_text_state_requires_typed_text(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'odpoveď cez hlas'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    message = _DummyMessage()
    state = _DummyState(CustomizationRequestAdminResponseStates.waiting_response_text.state)
    state.data = {
        'customization_request_admin_response_draft': {
            'response_text': None,
            'request_id': 'cr_voice_admin_response',
        }
    }

    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), state))

    assert state.current_state == CustomizationRequestAdminResponseStates.waiting_response_text.state
    assert state.data['customization_request_admin_response_draft']['response_text'] is None
    assert message.answers[-1] == 'Odpoveď pre používateľa prosím napíšte textom.'


def test_voice_admin_response_preview_routes_to_shared_decision_handler(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'odoslať'

    calls: list[str] = []

    async def _response_preview(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.customization_request_response_preview_decision', _response_preview)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state),
        )
    )

    assert calls == ['odoslať']


def test_voice_idle_transcript_can_use_llm_info_help_triage_without_side_effects(
    monkeypatch,
    tmp_path: Path,
) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'nejasny hlasovy vstup'

    async def _resolver(**kwargs) -> str:
        return 'unknown'

    _VoiceInfoHelpOpenAIFake.output = json.dumps(
        {
            'capability_id': 'unknown',
            'topic_id': 'out_of_domain',
            'triage_class': 'out_of_domain',
            'confidence': 0.81,
            'needs_clarification': False,
            'answer_text': 'Free-form answer must not render',
        }
    )
    _VoiceInfoHelpOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _VoiceInfoHelpOpenAIFake)

    config = Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'voice.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage()
    state = _DummyState(None)

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state is None
    assert 'Tejto spr\u00e1ve som nerozumel.' in message.answers[-1]
    assert 'Free-form answer must not render' not in message.answers[-1]
    assert _VoiceInfoHelpOpenAIFake.last_payload is None
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_voice_idle_profile_rekvizity_uses_top_level_resolver_path(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Мої реквізити'

    resolver_inputs: list[str] = []
    calls: list[str] = []

    async def _resolver(**kwargs) -> str:
        resolver_inputs.append(kwargs['user_input_text'])
        return 'show_supplier_profile'

    async def _profile(**kwargs) -> None:
        calls.append('profile')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.cmd_moj_profil', _profile)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert resolver_inputs == ['Мої реквізити']
    assert calls == ['profile']


def test_voice_idle_profile_edit_routes_to_profile_edit(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'upraviť môj profil'

    calls: list[str] = []

    async def _edit_profile(**kwargs) -> None:
        calls.append('edit_profile')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.cmd_upravit_profil', _edit_profile)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['edit_profile']


def test_voice_idle_recent_accounting_documents_routes_to_existing_view(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'покажи останні чеки'

    calls: list[str] = []

    async def _recent(**kwargs) -> None:
        calls.append('recent')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.invoice.cmd_blocky', _recent)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['recent']


def test_voice_idle_add_receipt_starts_upload_flow_and_not_invoice(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'додай, будь ласка, чек'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    message = _DummyMessage()
    message.from_user = type('_User', (), {'id': 111})()
    state = _DummyState(None)
    config = _config(tmp_path)

    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert 'fotku alebo PDF' in message.answers[-1]
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_voice_unhandled_active_state_requires_text_and_does_not_fall_back(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'vytvor fakturu'

    calls: list[str] = []

    async def _invoice_text(**kwargs) -> None:
        calls.append('invoice_text')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _invoice_text)
    message = _DummyMessage()

    asyncio.run(handle_voice(message, _DummyBot(), _config(tmp_path), _DummyState(OnboardingStates.name.state)))

    assert calls == []
    assert message.answers[-1] == 'V tomto kroku prosím zadajte hodnotu textom.'


def test_voice_service_short_name_state_rejects_voice(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'opravy'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    msg = _DummyMessage()
    asyncio.run(handle_voice(msg, _DummyBot(), _config(tmp_path), _DummyState(ServiceAliasStates.waiting_short_name.state)))
    assert msg.answers[-1] == 'Napíšte krátky názov položky textom.'


def test_voice_service_display_name_state_rejects_voice(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Servis elektromotora'

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    msg = _DummyMessage()
    asyncio.run(handle_voice(msg, _DummyBot(), _config(tmp_path), _DummyState(ServiceAliasStates.waiting_display_name.state)))
    assert msg.answers[-1] == 'Napíšte plný názov služby textom.'


def test_voice_idle_accounting_document_analytics_reaches_top_level_router(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'Koľko som minul v BAUHAUS?'

    calls: list[tuple[str, str]] = []

    async def _invoice_text(**kwargs) -> None:
        calls.append((kwargs['invoice_text'], kwargs['input_channel']))

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _invoice_text)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))

    assert calls == [('Koľko som minul v BAUHAUS?', 'voice')]

def test_voice_mark_existing_invoice_paid_confirmation_routes_to_mark_paid_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ano'

    async def _mark_paid(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    async def _generic(**kwargs) -> None:
        raise AssertionError('generic invoice routing should not run for mark-paid confirmation state')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_mark_existing_invoice_paid_confirm', _mark_paid)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state),
        )
    )

    assert calls == ['ano']




def test_voice_work_time_lunch_break_initial_choice_routes_to_shared_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ano'

    async def _handler(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.work_time_lunch_break_initial_choice', _handler)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(WorkTimeStates.waiting_lunch_break_initial_choice.state),
        )
    )

    assert calls == ['ano']


def test_voice_work_time_lunch_break_value_routes_to_value_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return '60 minut'

    async def _handler(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.work_time_lunch_break_value', _handler)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(WorkTimeStates.waiting_lunch_break_value.state),
        )
    )

    assert calls == ['60 minut']


def test_voice_work_time_lunch_break_update_value_routes_to_value_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return '45 minut'

    async def _handler(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.work_time_lunch_break_update_value', _handler)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(WorkTimeStates.waiting_lunch_break_update_value.state),
        )
    )

    assert calls == ['45 minut']


def test_voice_work_time_lunch_break_update_confirm_routes_to_shared_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ulozit'

    async def _handler(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.work_time_lunch_break_update_confirm', _handler)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(WorkTimeStates.waiting_lunch_break_update_confirm.state),
        )
    )

    assert calls == ['ulozit']




def test_voice_active_work_time_manual_preview_repeats_preview_instead_of_top_level_report(monkeypatch, tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state)
    state.data['work_time_manual_candidate'] = {
        'work_date': '2026-07-02',
        'start_time': '06:00',
        'end_time': '16:30',
        'duration_minutes': None,
        'close_mode': 'manual_range',
    }

    async def _stt(*args, **kwargs) -> str:
        return 'vytvor vykaz hodin za jul'

    async def _generic(**kwargs) -> None:
        raise AssertionError('active work-time preview must not fall back to top-level report routing')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    message = _DummyMessage()
    asyncio.run(handle_voice(message, _DummyBot(), config, state))

    assert state.current_state == WorkTimeStates.waiting_manual_range_confirm.state
    assert 'Mate rozpracovany nahlad doplnenia pracovneho casu' in message.answers[-1]
    assert 'Prichod: 06:00' in message.answers[-1]
    assert 'Odchod: 16:30' in message.answers[-1]


def test_voice_work_time_delete_month_confirmation_routes_to_shared_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'ano'

    async def _delete_month_confirm(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    async def _generic(**kwargs) -> None:
        raise AssertionError('generic invoice routing should not run for work-time delete confirmation state')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.work_time_delete_month_confirm', _delete_month_confirm)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(WorkTimeStates.waiting_delete_month_confirm.state),
        )
    )

    assert calls == ['ano']


def test_voice_work_time_delete_month_input_routes_to_month_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'jul 2026'

    async def _delete_month_input(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.work_time_delete_month_input', _delete_month_input)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(WorkTimeStates.waiting_delete_month_input.state),
        )
    )

    assert calls == ['jul 2026']


def test_voice_active_fsm_navigation_guard_handles_transcript_before_state_routing(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'hlavné menu'

    guard_calls: list[tuple[str, str]] = []

    async def _guard(**kwargs) -> bool:
        guard_calls.append((kwargs['text'], kwargs['input_channel']))
        return True

    async def _unexpected_state_handler(**kwargs) -> None:
        raise AssertionError('state-specific voice handler must not run after handled navigation')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.handle_active_fsm_text_update', _guard)
    monkeypatch.setattr('bot.handlers.voice.work_time_close_input', _unexpected_state_handler)

    state = _DummyState(WorkTimeStates.waiting_close_input.state)
    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), state))

    assert guard_calls == [('hlavné menu', 'voice')]
    assert state.current_state == WorkTimeStates.waiting_close_input.state


def test_voice_active_fsm_navigation_pass_through_continues_existing_state_handler(monkeypatch, tmp_path: Path) -> None:
    async def _stt(*args, **kwargs) -> str:
        return '16:30'

    guard_calls: list[str] = []
    state_calls: list[str] = []

    async def _guard(**kwargs) -> bool:
        guard_calls.append(kwargs['text'])
        return False

    async def _close_input(**kwargs) -> None:
        state_calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.handle_active_fsm_text_update', _guard)
    monkeypatch.setattr('bot.handlers.voice.work_time_close_input', _close_input)

    state = _DummyState(WorkTimeStates.waiting_close_input.state)
    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), state))

    assert guard_calls == ['16:30']
    assert state_calls == ['16:30']