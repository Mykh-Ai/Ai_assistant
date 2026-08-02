from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import RLock


@dataclass(frozen=True)
class InfoHelpContextKey:
    telegram_user_id: int
    chat_id: int
    workspace_id: str


@dataclass(frozen=True)
class InfoHelpConversationTurn:
    role: str
    text: str
    channel: str
    created_at: datetime
    visible_button_labels: tuple[str, ...] = ()

    def as_payload(self) -> dict[str, object]:
        return {
            'role': self.role,
            'text': self.text,
            'channel': self.channel,
            'created_at': self.created_at.astimezone(UTC).isoformat(),
            'visible_button_labels': list(self.visible_button_labels),
        }


class InfoHelpConversationContextService:
    """Small process-local context window; loss on restart is intentional."""

    def __init__(
        self,
        *,
        ttl: timedelta = timedelta(minutes=10),
        max_turns_per_role: int = 3,
    ) -> None:
        self._ttl = ttl
        self._max_turns_per_role = max_turns_per_role
        self._turns: dict[InfoHelpContextKey, list[InfoHelpConversationTurn]] = defaultdict(list)
        self._lock = RLock()

    @staticmethod
    def key(*, telegram_user_id: int, chat_id: int, workspace_id: str | None) -> InfoHelpContextKey:
        return InfoHelpContextKey(
            telegram_user_id=int(telegram_user_id),
            chat_id=int(chat_id),
            workspace_id=str(workspace_id or 'no-active-workspace'),
        )

    def capture_user(
        self,
        key: InfoHelpContextKey,
        *,
        text: str,
        channel: str,
        created_at: datetime | None = None,
    ) -> None:
        self._capture(
            key,
            InfoHelpConversationTurn(
                role='user',
                text=_bounded_visible_text(text),
                channel=channel if channel in {'text', 'command', 'voice_stt', 'callback_selection'} else 'text',
                created_at=_utc_now(created_at),
            ),
        )

    def capture_bot(
        self,
        key: InfoHelpContextKey,
        *,
        text: str,
        visible_button_labels: tuple[str, ...] | list[str] = (),
        created_at: datetime | None = None,
    ) -> None:
        self._capture(
            key,
            InfoHelpConversationTurn(
                role='bot',
                text=_bounded_visible_text(text),
                channel='text',
                created_at=_utc_now(created_at),
                visible_button_labels=tuple(
                    _bounded_visible_text(label, max_length=80)
                    for label in tuple(visible_button_labels)[:12]
                    if str(label).strip()
                ),
            ),
        )

    def recent(
        self,
        key: InfoHelpContextKey,
        *,
        now: datetime | None = None,
    ) -> tuple[InfoHelpConversationTurn, ...]:
        threshold = _utc_now(now) - self._ttl
        with self._lock:
            fresh = [turn for turn in self._turns.get(key, ()) if turn.created_at >= threshold]
            if fresh:
                self._turns[key] = fresh
            else:
                self._turns.pop(key, None)
                return ()
            selected: list[InfoHelpConversationTurn] = []
            for role in ('user', 'bot'):
                selected.extend([turn for turn in fresh if turn.role == role][-self._max_turns_per_role :])
            return tuple(sorted(selected, key=lambda turn: turn.created_at))

    def clear(self, key: InfoHelpContextKey) -> None:
        with self._lock:
            self._turns.pop(key, None)

    def clear_actor_chat(self, *, telegram_user_id: int, chat_id: int) -> None:
        with self._lock:
            keys = [
                key for key in self._turns
                if key.telegram_user_id == telegram_user_id and key.chat_id == chat_id
            ]
            for key in keys:
                self._turns.pop(key, None)

    def _capture(self, key: InfoHelpContextKey, turn: InfoHelpConversationTurn) -> None:
        if not turn.text:
            return
        with self._lock:
            turns = self._turns[key]
            turns.append(turn)
            for role in ('user', 'bot'):
                role_indexes = [index for index, item in enumerate(turns) if item.role == role]
                for index in reversed(role_indexes[: -self._max_turns_per_role]):
                    turns.pop(index)


def _bounded_visible_text(value: object, *, max_length: int = 1200) -> str:
    return ' '.join(str(value or '').split())[:max_length]


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


info_help_conversation_context = InfoHelpConversationContextService()


def clear_info_help_context_for_message(message: object) -> None:
    actor_id = getattr(getattr(message, 'from_user', None), 'id', None)
    chat_id = getattr(getattr(message, 'chat', None), 'id', None)
    if not isinstance(actor_id, int):
        return
    info_help_conversation_context.clear_actor_chat(
        telegram_user_id=actor_id, chat_id=chat_id if isinstance(chat_id, int) else actor_id
    )
