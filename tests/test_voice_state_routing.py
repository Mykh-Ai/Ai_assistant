from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
from bot.handlers.contacts import ContactStates
from bot.handlers.delete_user_database import DeleteUserDatabaseStates, VOICE_EXACT_CONFIRMATION_MESSAGE
from bot.handlers.invoice import InvoiceStates
from bot.handlers.onboarding import OnboardingStates, SupplierProfileEditStates
from bot.handlers.supplier import ServiceAliasStates
from bot.handlers.voice import handle_voice


class _DummyVoice:
    def __init__(self, file_id: str) -> None:
        self.file_id = file_id


class _DummyMessage:
    def __init__(self) -> None:
        self.voice = _DummyVoice('voice-file-id')
        self.answers: list[str] = []
        self.message_id = 77

    async def answer(self, text: str) -> None:
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
        return dict(self.data)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()


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
        return '\u0432\u0456\u0434\u043c\u0456\u043d\u0438\u0442\u0438'

    async def _cancel(**kwargs) -> None:
        calls.append('cancel')

    async def _scope(**kwargs) -> None:
        calls.append('edit_scope')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.cancel_current_state', _cancel)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_scope', _scope)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_scope.state),
        )
    )
    assert calls == ['cancel']


def test_voice_exact_global_cancel_bypasses_llm_resolver(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'скасувати'

    async def _cancel(**kwargs) -> None:
        calls.append('cancel')

    async def _unexpected_resolver(**kwargs) -> str:
        raise AssertionError('exact global cancel transcript must not call LLM resolver')

    async def _scope(**kwargs) -> None:
        calls.append('edit_scope')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.cancel_current_state', _cancel)
    monkeypatch.setattr('bot.handlers.voice.resolve_global_cancel', _unexpected_resolver)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_scope', _scope)

    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_scope.state),
        )
    )
    assert calls == ['cancel']


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

    assert 'Nerozumiem, čo chcete spraviť.' in message.answers[-1]
    assert 'vytvoriť faktúru' in message.answers[-1]


@pytest.mark.parametrize(
    ('transcript', 'expected_fragment'),
    [
        ('Vie\u0161 mi spravi\u0165 preh\u013ead tr\u017eieb za minul\u00fd mesiac?', 'nov\u00fa biznis funkciu'),
        ('Ak\u00e9 bude po\u010dasie zajtra?', 'mimo rozsahu OfficeFlow'),
        ('Ako sa m\u00e1\u0161?', 'biznis \u00falohami'),
        ('urob mi to', 'Nie je jasn\u00e9'),
        (
            'Povedz adminovi, \u017ee potrebujem automatick\u00e9 pripomienky nezaplaten\u00fdch fakt\u00far.',
            'Ni\u010d som neposlal ani neulo\u017eil',
        ),
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
    assert not config.db_path.exists()
    assert not (tmp_path / 'invoices').exists()


def test_voice_idle_transcript_can_use_llm_info_help_triage_without_side_effects(
    monkeypatch,
    tmp_path: Path,
) -> None:
    async def _stt(*args, **kwargs) -> str:
        return 'cashflow dashboard pls'

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
    assert 'mimo rozsahu OfficeFlow' in message.answers[-1]
    assert 'Free-form answer must not render' not in message.answers[-1]
    assert _VoiceInfoHelpOpenAIFake.last_payload is not None
    assert _VoiceInfoHelpOpenAIFake.last_payload['input_channel'] == 'voice'
    assert 'answer_text' not in _VoiceInfoHelpOpenAIFake.last_payload
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
