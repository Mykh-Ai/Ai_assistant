from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from aiogram.methods import SendMessage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.services.conversation_context import (
    ConversationContextService,
    OutgoingConversationContextMiddleware,
    active_conversation_turn,
)


def _service(now: datetime) -> ConversationContextService:
    return ConversationContextService(clock=lambda: now)


def test_context_is_bounded_to_three_turns_per_role_and_chronological() -> None:
    now = datetime(2026, 8, 2, 10, tzinfo=UTC)
    service = _service(now)
    for index in range(5):
        service.remember_user(1, 10, 100, f'u{index}', channel='text')
        service.remember_bot(1, 10, 100, f'b{index}')

    turns = service.recent_turns(1, 10, 100)

    assert [turn.text for turn in turns] == ['u2', 'b2', 'u3', 'b3', 'u4', 'b4']
    assert sum(turn.role == 'user' for turn in turns) == 3
    assert sum(turn.role == 'bot' for turn in turns) == 3


def test_context_expires_after_ten_minutes() -> None:
    now = datetime(2026, 8, 2, 10, tzinfo=UTC)
    clock = [now]
    service = ConversationContextService(clock=lambda: clock[0])
    service.remember_user(1, 10, 100, 'hello', channel='text')
    clock[0] = now + timedelta(minutes=10, seconds=1)

    assert service.recent_turns(1, 10, 100) == []


def test_context_is_isolated_by_user_and_chat() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    service.remember_user(1, 10, 100, 'first', channel='text')
    service.remember_user(2, 10, 100, 'second', channel='text')
    service.remember_user(1, 20, 100, 'third', channel='text')

    assert [turn.text for turn in service.recent_turns(1, 10, 100)] == ['first']
    assert [turn.text for turn in service.recent_turns(2, 10, 100)] == ['second']
    assert [turn.text for turn in service.recent_turns(1, 20, 100)] == ['third']


def test_workspace_change_never_mixes_context() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    service.remember_user(1, 10, 100, 'workspace 100', channel='text')
    service.remember_user(1, 10, 200, 'workspace 200', channel='text')

    assert service.recent_turns(1, 10, 100) == []
    assert [turn.text for turn in service.recent_turns(1, 10, 200)] == ['workspace 200']


def test_empty_and_forbidden_payloads_are_not_stored() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    service.remember_user(1, 10, None, '   ', channel='text')
    service.remember_user(1, 10, None, 'raw', channel='photo')
    service.remember_user(1, 10, None, 'raw', channel='callback_data')

    assert service.recent_turns(1, 10, None) == []


def test_command_voice_and_callback_labels_are_bounded_channels() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    service.remember_user(1, 10, None, '/menu', channel='command')
    service.remember_user(1, 10, None, 'prepis hlasu', channel='voice_stt')
    service.remember_user(1, 10, None, 'Vytvoriť faktúru', channel='callback')

    assert [turn.channel for turn in service.recent_turns(1, 10, None)] == [
        'command', 'voice_stt', 'callback'
    ]


def test_clear_removes_only_requested_conversation() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    service.remember_user(1, 10, None, 'one', channel='text')
    service.remember_user(1, 20, None, 'two', channel='text')

    service.clear(1, 10)

    assert service.recent_turns(1, 10, None) == []
    assert [turn.text for turn in service.recent_turns(1, 20, None)] == ['two']


def test_clear_user_removes_all_user_chats_only() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    service.remember_user(1, 10, None, 'one', channel='text')
    service.remember_user(1, 20, None, 'two', channel='text')
    service.remember_user(2, 10, None, 'other', channel='text')

    service.clear_user(1)

    assert service.recent_turns(1, 10, None) == []
    assert service.recent_turns(1, 20, None) == []
    assert [turn.text for turn in service.recent_turns(2, 10, None)] == ['other']


def test_outgoing_capture_records_same_chat_text_and_inline_labels() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    middleware = OutgoingConversationContextMiddleware(service)
    method = SendMessage(
        chat_id=10,
        text='Choose',
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text='First', callback_data='secret:1')]]
        ),
    )

    async def _send(bot, request):
        return object()

    async def _run() -> None:
        with active_conversation_turn(user_id=1, chat_id=10, workspace_id=100):
            await middleware(_send, object(), method)

    asyncio.run(_run())

    turn = service.recent_turns(1, 10, 100)[0]
    assert turn.text == 'Choose'
    assert turn.visible_button_labels == ('First',)
    assert 'secret:1' not in repr(turn)


def test_outgoing_capture_ignores_background_and_cross_chat_sends() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    middleware = OutgoingConversationContextMiddleware(service)

    async def _send(bot, request):
        return object()

    async def _run() -> None:
        await middleware(_send, object(), SendMessage(chat_id=10, text='background'))
        with active_conversation_turn(user_id=1, chat_id=10, workspace_id=None):
            await middleware(_send, object(), SendMessage(chat_id=20, text='cross chat'))

    asyncio.run(_run())

    assert service.recent_turns(1, 10, None) == []
    assert service.recent_turns(1, 20, None) == []


def test_outgoing_capture_does_not_store_failed_send() -> None:
    service = _service(datetime(2026, 8, 2, 10, tzinfo=UTC))
    middleware = OutgoingConversationContextMiddleware(service)

    async def _send(bot, request):
        raise RuntimeError('send failed')

    async def _run() -> None:
        with active_conversation_turn(user_id=1, chat_id=10, workspace_id=None):
            try:
                await middleware(_send, object(), SendMessage(chat_id=10, text='not sent'))
            except RuntimeError:
                pass

    asyncio.run(_run())

    assert service.recent_turns(1, 10, None) == []
