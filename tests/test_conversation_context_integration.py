from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

from bot.config import Config
from bot.handlers.start import cmd_menu, cmd_start
from bot.handlers.state_control import cancel_current_state
from bot.services.authorization import TelegramUserAuthorizationMiddleware
from bot.services.conversation_context import (
    ConversationContextMiddleware,
    conversation_context_service,
)
from bot.services.db import init_db


class _User:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _Chat:
    def __init__(self, chat_id: int) -> None:
        self.id = chat_id


class _Message:
    def __init__(self, text: str, *, user_id: int = 101, chat_id: int = 202) -> None:
        self.text = text
        self.from_user = _User(user_id)
        self.chat = _Chat(chat_id)
        self.answers = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append((text, kwargs))


class _State:
    def __init__(self, current: str | None = None) -> None:
        self.current = current
        self.data = {}

    async def get_state(self):
        return self.current

    async def get_data(self):
        return dict(self.data)

    async def clear(self):
        self.current = None
        self.data.clear()


def _config(tmp_path: Path, *, allowed: frozenset[int] = frozenset()) -> Config:
    return Config(bot_token='token', openai_api_key=None, openai_stt_model='whisper-1',
                  openai_llm_model='gpt-4o', debug_invoice_transparency=False,
                  db_path=tmp_path / 'db.sqlite', storage_dir=tmp_path,
                  allowed_telegram_user_ids=allowed)


def test_main_registers_authorization_before_context_before_active_guard() -> None:
    import bot.main

    source = inspect.getsource(bot.main.main)
    authorization = source.index('TelegramUserAuthorizationMiddleware()')
    context = source.index('ConversationContextMiddleware()')
    active_guard = source.index('ActiveFsmMessageMiddleware()')

    assert authorization < context < active_guard
    assert source.index('OutgoingConversationContextMiddleware()') > context


def test_unauthorized_update_never_enters_context_or_downstream(tmp_path: Path) -> None:
    config = _config(tmp_path, allowed=frozenset({999}))
    init_db(config.db_path)
    message = _Message('sensitive business text', user_id=101)
    conversation_context_service.clear_user(101)

    async def _downstream(event, data):
        raise AssertionError('unauthorized update must stop before context and AI routing')

    context_middleware = ConversationContextMiddleware(conversation_context_service)

    async def _context_handler(event, data):
        return await context_middleware(_downstream, event, data)

    asyncio.run(TelegramUserAuthorizationMiddleware()(
        _context_handler, message, {'config': config}))

    assert conversation_context_service.recent_turns(101, 202, None) == []
    assert message.answers


def test_start_and_menu_clear_completed_conversation_context(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('/start')
    conversation_context_service.remember_user(101, 202, None, 'before', channel='text')
    asyncio.run(cmd_start(message=message, config=config, state=_State()))
    assert conversation_context_service.recent_turns(101, 202, None) == []

    conversation_context_service.remember_user(101, 202, None, 'before', channel='text')
    asyncio.run(cmd_menu(message=message, config=config, state=_State()))
    assert conversation_context_service.recent_turns(101, 202, None) == []


def test_cancel_clears_completed_conversation_context(tmp_path: Path) -> None:
    config = _config(tmp_path)
    message = _Message('/cancel')
    conversation_context_service.remember_user(101, 202, None, 'before', channel='text')

    asyncio.run(cancel_current_state(message=message, state=_State(), config=config))

    assert conversation_context_service.recent_turns(101, 202, None) == []
