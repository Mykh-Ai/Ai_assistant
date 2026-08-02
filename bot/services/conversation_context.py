from __future__ import annotations

from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from aiogram import BaseMiddleware
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.methods import SendMessage
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.config import Config
from bot.services.workspace_context import WorkspaceContextService


ConversationRole = Literal['user', 'bot']
UserConversationChannel = Literal['text', 'command', 'voice_stt', 'callback']
_ALLOWED_USER_CHANNELS = {'text', 'command', 'voice_stt', 'callback'}
_TTL = timedelta(minutes=10)


@dataclass(frozen=True)
class ConversationTurn:
    role: ConversationRole
    text: str
    channel: str
    workspace_id: str | None
    created_at: datetime
    visible_button_labels: tuple[str, ...] = ()

    def to_prompt_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            'role': self.role,
            'text': self.text,
            'channel': self.channel,
        }
        if self.visible_button_labels:
            payload['visible_button_labels'] = list(self.visible_button_labels)
        return payload


@dataclass(frozen=True)
class ActiveConversationTurn:
    user_id: int
    chat_id: int
    workspace_id: str | None


_ACTIVE_TURN: ContextVar[ActiveConversationTurn | None] = ContextVar(
    'active_conversation_turn', default=None
)


@contextmanager
def active_conversation_turn(
    *, user_id: int, chat_id: int, workspace_id: str | int | None
) -> Iterator[ActiveConversationTurn]:
    value = ActiveConversationTurn(
        user_id=int(user_id),
        chat_id=int(chat_id),
        workspace_id=_workspace_key(workspace_id),
    )
    token = _ACTIVE_TURN.set(value)
    try:
        yield value
    finally:
        _ACTIVE_TURN.reset(token)


def current_active_conversation_turn() -> ActiveConversationTurn | None:
    return _ACTIVE_TURN.get()


class ConversationContextService:
    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))
        self._turns: dict[tuple[int, int], list[ConversationTurn]] = {}

    def remember_user(
        self,
        user_id: int,
        chat_id: int,
        workspace_id: str | int | None,
        text: str,
        *,
        channel: str,
    ) -> None:
        if channel not in _ALLOWED_USER_CHANNELS:
            return
        normalized = _normalized_text(text)
        if not normalized:
            return
        self._remember(
            user_id=user_id,
            chat_id=chat_id,
            workspace_id=workspace_id,
            role='user',
            text=normalized,
            channel=channel,
        )

    def remember_bot(
        self,
        user_id: int,
        chat_id: int,
        workspace_id: str | int | None,
        text: str,
        *,
        visible_button_labels: tuple[str, ...] | list[str] = (),
    ) -> None:
        normalized = _normalized_text(text)
        if not normalized:
            return
        labels = tuple(
            label for label in (_normalized_text(item) for item in visible_button_labels) if label
        )
        self._remember(
            user_id=user_id,
            chat_id=chat_id,
            workspace_id=workspace_id,
            role='bot',
            text=normalized,
            channel='bot_message',
            visible_button_labels=labels,
        )

    def recent_turns(
        self, user_id: int, chat_id: int, workspace_id: str | int | None
    ) -> list[ConversationTurn]:
        key = (int(user_id), int(chat_id))
        expected_workspace = _workspace_key(workspace_id)
        now = _utc(self._clock())
        current = [
            turn for turn in self._turns.get(key, ()) if now - turn.created_at <= _TTL
        ]
        if current:
            self._turns[key] = current
        else:
            self._turns.pop(key, None)
        return [turn for turn in current if turn.workspace_id == expected_workspace]

    def clear(self, user_id: int, chat_id: int) -> None:
        self._turns.pop((int(user_id), int(chat_id)), None)

    def clear_user(self, user_id: int) -> None:
        actor_id = int(user_id)
        for key in [key for key in self._turns if key[0] == actor_id]:
            self._turns.pop(key, None)

    def _remember(
        self,
        *,
        user_id: int,
        chat_id: int,
        workspace_id: str | int | None,
        role: ConversationRole,
        text: str,
        channel: str,
        visible_button_labels: tuple[str, ...] = (),
    ) -> None:
        key = (int(user_id), int(chat_id))
        workspace = _workspace_key(workspace_id)
        now = _utc(self._clock())
        current = [
            turn for turn in self._turns.get(key, ())
            if now - turn.created_at <= _TTL and turn.workspace_id == workspace
        ]
        current.append(ConversationTurn(
            role=role,
            text=text,
            channel=channel,
            workspace_id=workspace,
            created_at=now,
            visible_button_labels=visible_button_labels,
        ))
        role_turns = [turn for turn in current if turn.role == role]
        if len(role_turns) > 3:
            remove_count = len(role_turns) - 3
            retained: list[ConversationTurn] = []
            for turn in current:
                if turn.role == role and remove_count:
                    remove_count -= 1
                    continue
                retained.append(turn)
            current = retained
        self._turns[key] = current


conversation_context_service = ConversationContextService()


class ConversationContextMiddleware(BaseMiddleware):
    def __init__(self, service: ConversationContextService | None = None) -> None:
        self._service = service or conversation_context_service

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        actor = getattr(event, 'from_user', None)
        message = event if isinstance(event, Message) else getattr(event, 'message', None)
        chat = getattr(message, 'chat', None)
        if actor is None or chat is None:
            return await handler(event, data)
        workspace_id = _resolve_workspace_id(data.get('config'), int(actor.id))
        with active_conversation_turn(
            user_id=int(actor.id), chat_id=int(chat.id), workspace_id=workspace_id
        ):
            if isinstance(event, Message):
                text = (event.text or '').strip()
                if text:
                    self._service.remember_user(
                        int(actor.id), int(chat.id), workspace_id, text,
                        channel='command' if text.startswith('/') else 'text',
                    )
            return await handler(event, data)


class OutgoingConversationContextMiddleware(BaseRequestMiddleware):
    def __init__(self, service: ConversationContextService | None = None) -> None:
        self._service = service or conversation_context_service

    async def __call__(self, make_request, bot, method):
        result = await make_request(bot, method)
        active = current_active_conversation_turn()
        if active is None or not isinstance(method, SendMessage):
            return result
        if str(method.chat_id) != str(active.chat_id):
            return result
        labels = _inline_button_labels(method.reply_markup)
        self._service.remember_bot(
            active.user_id,
            active.chat_id,
            active.workspace_id,
            method.text,
            visible_button_labels=labels,
        )
        return result


def remember_voice_transcript(
    *, user_id: int, chat_id: int, workspace_id: str | int | None, text: str
) -> None:
    conversation_context_service.remember_user(
        user_id, chat_id, workspace_id, text, channel='voice_stt'
    )


def remember_callback_label(*, user_id: int, chat_id: int, label: str) -> None:
    active = current_active_conversation_turn()
    workspace_id = active.workspace_id if active is not None else None
    conversation_context_service.remember_user(
        user_id, chat_id, workspace_id, label, channel='callback'
    )


def clear_conversation_for_message(message: Message) -> None:
    actor = getattr(message, 'from_user', None)
    chat = getattr(message, 'chat', None)
    if actor is not None and chat is not None:
        conversation_context_service.clear(int(actor.id), int(chat.id))


def _resolve_workspace_id(config: object, user_id: int) -> str | None:
    if not isinstance(config, Config) or not config.db_path.exists():
        return None
    try:
        return WorkspaceContextService(config.db_path).resolve_for_user_readonly(user_id).workspace_id
    except Exception:
        return None


def _inline_button_labels(reply_markup: object) -> tuple[str, ...]:
    if not isinstance(reply_markup, InlineKeyboardMarkup):
        return ()
    return tuple(button.text for row in reply_markup.inline_keyboard for button in row if button.text)


def _normalized_text(value: object) -> str:
    return ' '.join(str(value or '').split()).strip()


def _workspace_key(value: str | int | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
