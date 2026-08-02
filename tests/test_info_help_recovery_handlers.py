from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers import routers
from bot.handlers.info_help_recovery import (
    contextual_recovery_selection,
    dispatch_recovery_action,
    handle_idle_contextual_recovery,
    show_main_menu_navigation,
)
from bot.services.contextual_info_help_recovery import (
    ContextualRecoveryResult,
    GENUINELY_UNCLEAR_MESSAGE,
    contextual_recovery_store,
)
from bot.services.info_help import InfoHelpTriageResult


class _User:
    def __init__(self, user_id: int = 101) -> None:
        self.id = user_id


class _Chat:
    def __init__(self, chat_id: int = 202) -> None:
        self.id = chat_id


class _Message:
    def __init__(self, text: str = '') -> None:
        self.text = text
        self.from_user = _User()
        self.chat = _Chat()
        self.answers = []
        self.edits = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append((text, kwargs))

    async def edit_reply_markup(self, **kwargs) -> None:
        self.edits.append(kwargs)


class _Callback:
    def __init__(self, data: str, *, user_id: int = 101, chat_id: int = 202) -> None:
        self.data = data
        self.from_user = _User(user_id)
        self.message = _Message()
        self.message.chat = _Chat(chat_id)
        self.answers = []

    async def answer(self, text: str | None = None, **kwargs) -> None:
        self.answers.append((text, kwargs))


class _State:
    def __init__(self, current: str | None = None) -> None:
        self.current = current
        self.data = {}
        self.cleared = False

    async def get_state(self):
        return self.current

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, state):
        self.current = state.state if hasattr(state, 'state') else state

    async def clear(self):
        self.current = None
        self.data.clear()
        self.cleared = True


def _config(tmp_path: Path) -> Config:
    return Config(bot_token='token', openai_api_key=None, openai_stt_model='whisper-1',
                  openai_llm_model='gpt-4o', debug_invoice_transparency=False,
                  db_path=tmp_path / 'db.sqlite', storage_dir=tmp_path)


def test_unknown_command_router_is_last() -> None:
    assert routers[-1].name == 'info_help_recovery'


def test_idle_recovery_offers_bounded_buttons_without_starting_state(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr(
        'bot.services.info_help.classify_info_help_triage',
        lambda **kwargs: InfoHelpTriageResult(),
    )

    async def _resolve(**kwargs):
        return ContextualRecoveryResult(
            recovery_outcome='clarify_candidates',
            candidate_action_ids=('create_invoice', 'add_contact'),
            object_domain='unknown',
        )

    monkeypatch.setattr('bot.handlers.info_help_recovery.resolve_contextual_recovery', _resolve)
    message = _Message('/contat')
    state = _State()

    asyncio.run(handle_idle_contextual_recovery(
        message=message, state=state, config=_config(tmp_path), text=message.text,
        input_channel='command'))

    assert state.current is None
    keyboard = message.answers[-1][1]['reply_markup']
    assert [row[0].text for row in keyboard.inline_keyboard] == [
        'Vytvoriť faktúru', 'Pridať kontakt'
    ]
    assert all(row[0].callback_data.startswith('infohelp:') for row in keyboard.inline_keyboard)


def test_idle_genuinely_unclear_uses_exact_short_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(
        'bot.services.info_help.classify_info_help_triage',
        lambda **kwargs: InfoHelpTriageResult(),
    )

    async def _resolve(**kwargs):
        return ContextualRecoveryResult()

    monkeypatch.setattr('bot.handlers.info_help_recovery.resolve_contextual_recovery', _resolve)
    message = _Message('???')

    asyncio.run(handle_idle_contextual_recovery(
        message=message, state=_State(), config=_config(tmp_path), text=message.text,
        input_channel='text'))

    assert message.answers == [(GENUINELY_UNCLEAR_MESSAGE, {})]


def test_recovery_selection_converges_on_existing_invoice_owner(tmp_path: Path, monkeypatch) -> None:
    calls = []

    async def _cmd_invoice(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr('bot.handlers.invoice.cmd_invoice', _cmd_invoice)
    message = _Message()
    state = _State()

    asyncio.run(dispatch_recovery_action(
        action_id='create_invoice', message=message, state=state, config=_config(tmp_path)))

    assert calls and calls[0]['message'] is message and calls[0]['state'] is state


def test_valid_callback_is_single_use_and_cleans_owned_keyboard(tmp_path: Path, monkeypatch) -> None:
    calls = []

    async def _dispatch(**kwargs):
        calls.append(kwargs['action_id'])

    monkeypatch.setattr('bot.handlers.info_help_recovery.dispatch_recovery_action', _dispatch)
    token = contextual_recovery_store.create(
        user_id=101, chat_id=202, workspace_id=None,
        candidate_action_ids=['create_invoice'],
    )
    callback = _Callback(f'infohelp:{token}:0')

    asyncio.run(contextual_recovery_selection(callback, _State(), _config(tmp_path)))
    asyncio.run(contextual_recovery_selection(callback, _State(), _config(tmp_path)))

    assert calls == ['create_invoice']
    assert callback.message.edits == [{'reply_markup': None}]
    assert callback.answers[-1][1]['show_alert'] is True


def test_forbidden_callback_cannot_alter_owned_message(tmp_path: Path, monkeypatch) -> None:
    token = contextual_recovery_store.create(
        user_id=101, chat_id=202, workspace_id=None,
        candidate_action_ids=['create_invoice'],
    )
    callback = _Callback(f'infohelp:{token}:0', user_id=999)

    asyncio.run(contextual_recovery_selection(callback, _State(), _config(tmp_path)))

    assert callback.message.edits == []
    assert callback.answers[-1][1]['show_alert'] is True


def test_navigation_button_preserves_state_until_click_then_uses_menu(tmp_path: Path) -> None:
    callback = _Callback('navigation:show_main_menu')
    state = _State('InvoiceStates:waiting_input')

    asyncio.run(show_main_menu_navigation(callback, state, _config(tmp_path)))

    assert state.current is None
    assert state.cleared is True
    assert callback.message.edits == [{'reply_markup': None}]
    assert 'Všetky používateľské možnosti' in callback.message.answers[-1][0]
