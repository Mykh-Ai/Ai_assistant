from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.contacts import ContactStates
from bot.handlers.invoice import InvoiceStates
from bot.handlers.supplier import ServiceAliasStates
from bot.handlers.voice import handle_voice


class _DummyVoice:
    def __init__(self, file_id: str) -> None:
        self.file_id = file_id


class _DummyMessage:
    def __init__(self) -> None:
        self.voice = _DummyVoice('voice-file-id')
        self.answers: list[str] = []

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


class _DummyState:
    def __init__(self, current_state: str | None) -> None:
        self.current_state = current_state

    async def get_state(self) -> str | None:
        return self.current_state


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
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


def test_voice_contact_missing_state_routes_to_contact_missing_handler(monkeypatch, tmp_path: Path) -> None:
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

    monkeypatch.setattr('bot.handlers.voice.process_contact_missing_fields', _contact_missing)
    monkeypatch.setattr('bot.handlers.voice.process_contact_intake_confirm', lambda **kwargs: None)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(ContactStates.intake_missing.state)))
    assert calls == ['contact_missing']


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


def test_voice_waiting_edit_invoice_number_value_routes_to_number_handler(monkeypatch, tmp_path: Path) -> None:
    calls: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'zmeň číslo na dvadsať dva'

    async def _number_value(**kwargs) -> None:
        calls.append(kwargs['message'].text)

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _stt)
    monkeypatch.setattr('bot.handlers.voice.invoice_edit_invoice_number_value', _number_value)
    asyncio.run(
        handle_voice(
            _DummyMessage(),
            _DummyBot(),
            _config(tmp_path),
            _DummyState(InvoiceStates.waiting_edit_invoice_number_value.state),
        )
    )
    assert calls == ['zmeň číslo na dvadsať dva']


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
