from __future__ import annotations

import asyncio
from pathlib import Path
import sqlite3

import pytest

from bot.config import Config
from bot.handlers import invoice, voice
from bot.handlers.runtime_issue import RUNTIME_ISSUE_ACTION
from bot.services.authorization import TelegramUserAuthorizationMiddleware
from bot.services.db import init_db
from bot.services.info_help import InfoHelpTriageResult


ADMIN_ID = 111
USER_ID = 222
UNKNOWN_ID = 333


class _Voice:
    file_id = 'voice-runtime-issue'


class _Message:
    def __init__(self, *, actor: int = ADMIN_ID, message_id: int = 51) -> None:
        self.voice = _Voice()
        self.text = None
        self.from_user = type('User', (), {'id': actor})()
        self.chat = type('Chat', (), {'id': 61})()
        self.message_id = message_id
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class _Bot:
    async def get_file(self, file_id: str):
        return type('File', (), {'file_path': 'runtime-issue.ogg'})()

    async def download_file(self, file_path: str, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'not-real-audio')


class _State:
    def __init__(self, current: str | None = None, data: dict | None = None) -> None:
        self.current = current
        self.data = dict(data or {})
        self.clear_calls = 0
        self.set_calls = 0
        self.update_calls = 0

    async def get_state(self) -> str | None:
        return self.current

    async def get_data(self) -> dict:
        return dict(self.data)

    async def set_state(self, state) -> None:
        self.set_calls += 1
        self.current = state.state if hasattr(state, 'state') else state

    async def update_data(self, **kwargs) -> None:
        self.update_calls += 1
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.clear_calls += 1
        self.current = None
        self.data.clear()


def _config(tmp_path: Path) -> Config:
    config = Config(
        bot_token='token',
        openai_api_key='fake-key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'voice.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset({ADMIN_ID, USER_ID}),
        admin_telegram_user_ids=frozenset({ADMIN_ID}),
    )
    init_db(config.db_path)
    return config


def _rows(config: Config) -> list[sqlite3.Row]:
    with sqlite3.connect(config.db_path) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            'SELECT actor_telegram_id, telegram_update_id, telegram_message_id, '
            'telegram_chat_id, workspace_id, source_channel, active_fsm_state, '
            'description FROM runtime_issues ORDER BY created_at'
        ).fetchall()


def test_admin_idle_voice_converges_on_shared_capture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)

    async def _stt(*args, **kwargs) -> str:
        return 'Nahlás chybu: po potvrdení sa správa nezobrazila.'

    async def _resolver(**kwargs):
        return RUNTIME_ISSUE_ACTION

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(invoice, 'resolve_semantic_action', _resolver)
    message = _Message()
    asyncio.run(
        voice.handle_voice(
            message,
            _Bot(),
            config,
            _State(),
            type('Update', (), {'update_id': 1201})(),
        )
    )

    rows = _rows(config)
    assert len(rows) == 1
    assert rows[0]['actor_telegram_id'] == ADMIN_ID
    assert rows[0]['telegram_update_id'] == 1201
    assert rows[0]['telegram_message_id'] == 51
    assert rows[0]['telegram_chat_id'] == 61
    assert rows[0]['source_channel'] == 'voice'
    assert 'uložil ako IR-' in message.answers[-1]


def test_admin_active_fsm_voice_preserves_state_and_data(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    protected = {
        'contact_draft': {'name': 'Secret Customer'},
        'active_fsm_last_activity_at': '2026-07-28T12:00:00+00:00',
    }
    state = _State('ContactStates:name_hint', protected)

    async def _stt(*args, **kwargs) -> str:
        return 'Ulož ako problém, že po potvrdení kontaktu zmizlo tlačidlo.'

    async def _issue(**kwargs) -> bool:
        return True

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(
        'bot.handlers.runtime_issue.resolve_runtime_issue_intent',
        _issue,
    )
    message = _Message()
    asyncio.run(
        voice.handle_voice(
            message,
            _Bot(),
            config,
            state,
            type('Update', (), {'update_id': 1301})(),
        )
    )

    rows = _rows(config)
    assert len(rows) == 1
    assert rows[0]['source_channel'] == 'voice'
    assert rows[0]['active_fsm_state'] == 'ContactStates:name_hint'
    assert state.current == 'ContactStates:name_hint'
    assert state.data == protected
    assert state.clear_calls == state.set_calls == state.update_calls == 0


def test_authorized_non_admin_issue_like_voice_never_reaches_issue_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    allowed: list[str] = []

    async def _stt(*args, **kwargs) -> str:
        return 'Nahlás chybu: po potvrdení sa správa nezobrazila.'

    async def _resolver(**kwargs):
        allowed.extend(kwargs['allowed_actions'])
        return 'unknown'

    async def _no_guidance(**kwargs):
        return InfoHelpTriageResult()

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(invoice, 'resolve_semantic_action', _resolver)
    monkeypatch.setattr(
        invoice,
        'resolve_info_help_triage_result_with_llm',
        _no_guidance,
    )
    asyncio.run(
        voice.handle_voice(
            _Message(actor=USER_ID),
            _Bot(),
            config,
            _State(),
            type('Update', (), {'update_id': 1401})(),
        )
    )

    assert RUNTIME_ISSUE_ACTION not in allowed
    assert _rows(config) == []


def test_authorized_non_admin_normal_voice_keeps_existing_voice_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    calls: list[dict[str, object]] = []

    async def _stt(*args, **kwargs) -> str:
        return 'Ukáž môj profil dodávateľa.'

    async def _existing_dispatch(**kwargs) -> None:
        calls.append(kwargs)

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(voice, 'process_invoice_text', _existing_dispatch)
    message = _Message(actor=USER_ID)
    asyncio.run(
        voice.handle_voice(
            message,
            _Bot(),
            config,
            _State(),
            type('Update', (), {'update_id': 1501})(),
        )
    )

    assert len(calls) == 1
    assert calls[0]['invoice_text'] == 'Ukáž môj profil dodávateľa.'
    assert calls[0]['input_channel'] == 'voice'
    assert calls[0]['telegram_update_id'] == 1501
    assert _rows(config) == []


@pytest.mark.parametrize(
    'prefix',
    [
        '\u041f\u0440\u043e\u0431\u043b\u0435\u043c\u0430',
        '\u041f\u043e\u043c\u0438\u043b\u043a\u0430',
        '\u0411\u0430\u0433',
        'Chyba',
        'Problem',
        'Bug',
        'Error',
    ],
)
def test_admin_idle_voice_problem_prefix_bypasses_business_router(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prefix: str,
) -> None:
    config = _config(tmp_path)
    transcript = (
        f'{prefix}: invoice analytics for a company started the wrong action.'
    )

    async def _stt(*args, **kwargs) -> str:
        return transcript

    async def _unexpected_business_resolver(**kwargs):
        raise AssertionError('problem-prefixed STT must not reach the business resolver')

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(invoice, 'resolve_semantic_action', _unexpected_business_resolver)
    message = _Message()

    asyncio.run(
        voice.handle_voice(
            message,
            _Bot(),
            config,
            _State(),
            type('Update', (), {'update_id': 1601})(),
        )
    )

    rows = _rows(config)
    assert len(rows) == 1
    assert rows[0]['source_channel'] == 'voice'
    assert rows[0]['description'] == transcript
    assert 'IR-' in message.answers[-1]


def test_non_admin_idle_voice_problem_prefix_enters_confirmed_admin_review_preview(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    transcript = (
        '\u041f\u043e\u043c\u0438\u043b\u043a\u0430: yearly invoice analytics asks for an invoice number.'
    )

    async def _stt(*args, **kwargs) -> str:
        return transcript

    async def _unexpected_business_resolver(**kwargs):
        raise AssertionError('problem-prefixed STT must not reach the business resolver')

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(invoice, 'resolve_semantic_action', _unexpected_business_resolver)
    message = _Message(actor=USER_ID)
    state = _State()

    asyncio.run(
        voice.handle_voice(
            message,
            _Bot(),
            config,
            state,
            type('Update', (), {'update_id': 1701})(),
        )
    )

    assert _rows(config) == []
    assert state.current == 'CustomizationRequestStates:waiting_preview_decision'
    assert message.answers


def test_admin_active_fsm_voice_problem_prefix_preserves_owned_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = _config(tmp_path)
    transcript = 'Chyba: invoice confirmation did not show a response.'
    protected = {'invoice_draft': {'customer': 'Alfa', 'total': '100.00'}}
    state = _State('InvoiceStates:waiting_input', protected)

    async def _stt(*args, **kwargs) -> str:
        return transcript

    async def _unexpected_issue_resolver(**kwargs):
        raise AssertionError('explicit problem prefix must bypass the LLM issue resolver')

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    monkeypatch.setattr(
        'bot.handlers.runtime_issue.resolve_runtime_issue_intent',
        _unexpected_issue_resolver,
    )
    message = _Message()

    asyncio.run(
        voice.handle_voice(
            message,
            _Bot(),
            config,
            state,
            type('Update', (), {'update_id': 1801})(),
        )
    )

    rows = _rows(config)
    assert len(rows) == 1
    assert rows[0]['description'] == transcript
    assert state.current == 'InvoiceStates:waiting_input'
    assert state.data == protected
    assert state.clear_calls == state.set_calls == state.update_calls == 0


def test_generally_unauthorized_voice_is_blocked_before_handler_and_stt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    called = False

    async def _stt(*args, **kwargs):
        raise AssertionError('unauthorized voice must be blocked before STT')

    async def _handler(event, data):
        nonlocal called
        called = True
        await voice.handle_voice(event, _Bot(), config, data['state'])

    monkeypatch.setattr(voice, 'transcribe_audio', _stt)
    message = _Message(actor=UNKNOWN_ID)
    state = _State()
    asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            message,
            {'config': config, 'state': state},
        )
    )

    assert called is False
    assert message.answers == ['Prístup k botovi nie je povolený.']
    assert _rows(config) == []
