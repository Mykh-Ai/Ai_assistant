from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import InvoiceStates
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
    monkeypatch.setattr('bot.handlers.voice.process_invoice_postpdf_decision', _postpdf)
    monkeypatch.setattr('bot.handlers.voice.process_invoice_text', _generic)

    asyncio.run(handle_voice(_DummyMessage(), _DummyBot(), _config(tmp_path), _DummyState(None)))
    assert calls == ['generic']
