import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    _detect_invoice_intent,
    _detect_invoice_postpdf_decision,
    _detect_invoice_preview_confirmation,
    process_invoice_text,
)


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.message_id = 1
        self.update_id = 1
        self.from_user = None
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


@pytest.mark.parametrize(
    'text',
    [
        'витворить фактуру для Tech Company',
        'сделай фактуру для Tech Company',
        'сделать фактуру для Tech Company',
        'sprav fakturu pre Tech Company',
        'urob fakturu pre Tech Company',
        'створи фактуру для Tech Company',
        'vytvoriť fakturu pre Tech Company',
    ],
)
def test_detects_create_invoice_intent_for_mixed_noisy_starts(text: str) -> None:
    assert _detect_invoice_intent(text) == 'create_invoice'


@pytest.mark.parametrize(
    'text',
    [
        'upraviť fakturu 20260001',
        'upravit fakturu 20260001',
        'управить фактуру 20260001',
        'исправь фактуру 20260001',
        'отредактируй фактуру 20260001',
    ],
)
def test_detects_reserved_edit_invoice_intent(text: str) -> None:
    assert _detect_invoice_intent(text) == 'edit_invoice'


@pytest.mark.parametrize(
    'text',
    [
        'pošli fakturu 20260001',
        'poslať fakturu 20260001',
        'відправ фактуру 20260001',
        'надішли фактуру 20260001',
        'отправь фактуру 20260001',
    ],
)
def test_detects_reserved_send_invoice_intent(text: str) -> None:
    assert _detect_invoice_intent(text) == 'send_invoice'


def test_returns_unknown_when_no_known_intent_detected() -> None:
    assert _detect_invoice_intent('faktura pre Tech Company') == 'unknown'


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('áno', 'confirm_preview'),
        ('ano', 'confirm_preview'),
        ('так', 'confirm_preview'),
        ('да', 'confirm_preview'),
        ('nie', 'cancel_preview'),
        ('ні', 'cancel_preview'),
        ('нет', 'cancel_preview'),
    ],
)
def test_preview_confirmation_parser_handles_multilingual_variants(text: str, expected: str) -> None:
    assert _detect_invoice_preview_confirmation(text) == expected


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('schváliť', 'approve_pdf_invoice'),
        ('potvrdiť', 'approve_pdf_invoice'),
        ('схвалити', 'approve_pdf_invoice'),
        ('подтвердить', 'approve_pdf_invoice'),
        ('áno', 'approve_pdf_invoice'),
        ('так', 'approve_pdf_invoice'),
        ('да', 'approve_pdf_invoice'),
        ('upraviť', 'edit_pdf_invoice'),
        ('управить', 'edit_pdf_invoice'),
        ('исправь', 'edit_pdf_invoice'),
        ('редагувати', 'edit_pdf_invoice'),
        ('zrušiť', 'cancel_pdf_invoice'),
        ('vymazať', 'cancel_pdf_invoice'),
        ('зрушити', 'cancel_pdf_invoice'),
        ('скасувати', 'cancel_pdf_invoice'),
        ('удалить', 'cancel_pdf_invoice'),
        ('nie', 'cancel_pdf_invoice'),
        ('ні', 'cancel_pdf_invoice'),
        ('нет', 'cancel_pdf_invoice'),
    ],
)
def test_postpdf_parser_handles_required_multilingual_variants(text: str, expected: str) -> None:
    assert _detect_invoice_postpdf_decision(text) == expected


@pytest.mark.parametrize(
    'text',
    [
        'upraviť fakturu 20260001',
        'отредактируй фактуру 20260001',
        'pošli fakturu 20260001',
        'відправ фактуру 20260001',
    ],
)
def test_reserved_edit_and_send_verbs_do_not_enter_create_flow(text: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    async def _forbidden_parse(*args, **kwargs):
        raise AssertionError('Phase 2 parser must not be called for reserved intents.')

    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _forbidden_parse)

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )
    message = _DummyMessage(text)
    state = _DummyState()

    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=text))

    assert state.cleared is True
    assert message.answers
    assert 'zatiaľ nie je podporovaná' in message.answers[-1]
