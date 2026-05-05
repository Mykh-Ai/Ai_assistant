from __future__ import annotations

from collections.abc import Awaitable, Callable
import logging
import re
from typing import Any
import unicodedata

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.services.access_control import (
    ACCESS_STATUS_APPROVED,
    ACCESS_STATUS_PENDING,
    AccessControlService,
    AccessRequestInput,
)


UNAUTHORIZED_MESSAGE = 'Pr\u00edstup k botovi nie je povolen\u00fd.'
ACCESS_REQUEST_MESSAGE = (
    '\u010eakujeme za z\u00e1ujem. Pr\u00edstup k botovi mus\u00ed najprv schv\u00e1li\u0165 spr\u00e1vca. '
    'Po schv\u00e1len\u00ed budete m\u00f4c\u0165 pokra\u010dova\u0165 v nastaven\u00ed profilu.'
)
ADMIN_COMMANDS = {'/access_requests', '/approve', '/reject', '/block', '/users'}
ADMIN_COMMAND_ALIASES = {
    'access requests',
    'access_requests',
    'users',
    'pouzivatelia',
    'pouzivatel',
    'ziadosti',
    'ziadosti o pristup',
    'zapros',
    '\u0437\u0430\u043f\u0440\u043e\u0441',
    '\u0437\u0430\u043f\u0438\u0442',
    '\u0437\u0430\u043f\u0438\u0442\u0438',
    '\u0437\u0430\u043f\u0438\u0442\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u0443',
    '\u0437\u0430\u044f\u0432\u043a\u0438',
    '\u0437\u0430\u044f\u0432\u043a\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u0443',
    '\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0438',
    '\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456',
    '\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438',
}

logger = logging.getLogger(__name__)


def is_authorized_telegram_user(config: Config, telegram_user_id: int | None) -> bool:
    if telegram_user_id is None:
        return False
    access_service = AccessControlService(config.db_path)
    if access_service.is_blocked_user(telegram_user_id):
        return False
    if access_service.is_deleted_database_user(telegram_user_id):
        return False
    if telegram_user_id in config.allowed_telegram_user_ids:
        return True
    if access_service.is_active_user(telegram_user_id):
        return True
    if not config.allowed_telegram_user_ids and not config.admin_telegram_user_ids:
        return True
    return False


def is_admin_telegram_user(config: Config, telegram_user_id: int | None) -> bool:
    if telegram_user_id is None:
        return False
    access_service = AccessControlService(config.db_path)
    if access_service.is_blocked_user(telegram_user_id):
        return False
    if access_service.is_deleted_database_user(telegram_user_id):
        return False
    return telegram_user_id in config.admin_telegram_user_ids or access_service.is_admin_user(telegram_user_id)


class TelegramUserAuthorizationMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: dict[str, Any],
    ) -> Any:
        config = data.get('config')
        if not isinstance(config, Config):
            return await handler(event, data)

        telegram_user_id = event.from_user.id if event.from_user is not None else None
        if is_authorized_telegram_user(config, telegram_user_id):
            return await handler(event, data)

        if not isinstance(event, CallbackQuery) and _is_admin_command(event) and is_admin_telegram_user(config, telegram_user_id):
            return await handler(event, data)

        if not isinstance(event, CallbackQuery) and _is_start_command(event):
            await self._handle_unauthorized_start(event=event, data=data, config=config)
            return None

        state = data.get('state')
        if state is not None and hasattr(state, 'clear'):
            await state.clear()
        await _answer_unauthorized(event)
        return None

    async def _handle_unauthorized_start(self, *, event: Message, data: dict[str, Any], config: Config) -> None:
        state = data.get('state')
        if state is not None and hasattr(state, 'clear'):
            await state.clear()

        if event.from_user is None:
            await event.answer(UNAUTHORIZED_MESSAGE)
            return

        access_service = AccessControlService(config.db_path)
        if access_service.is_blocked_user(event.from_user.id):
            await event.answer(UNAUTHORIZED_MESSAGE)
            return

        request = access_service.create_or_refresh_pending_request(
            AccessRequestInput(
                telegram_id=event.from_user.id,
                username=getattr(event.from_user, 'username', None),
                first_name=getattr(event.from_user, 'first_name', None),
                last_name=getattr(event.from_user, 'last_name', None),
            )
        )
        if request.status == ACCESS_STATUS_APPROVED:
            await event.answer(UNAUTHORIZED_MESSAGE)
            return
        if request.status != ACCESS_STATUS_PENDING:
            await event.answer(UNAUTHORIZED_MESSAGE)
            return

        await _notify_admins_about_access_request(event=event, data=data, config=config)
        await event.answer(ACCESS_REQUEST_MESSAGE)


def _command_token(event: Message) -> str:
    text = (getattr(event, 'text', None) or '').strip()
    if not text.startswith('/'):
        return ''
    return text.split(maxsplit=1)[0].split('@', 1)[0].lower()


def _is_start_command(event: Message) -> bool:
    return _command_token(event) == '/start'


def _is_admin_command(event: Message) -> bool:
    command = _command_token(event)
    if command:
        return command in ADMIN_COMMANDS
    return _normalize_admin_alias(getattr(event, 'text', None) or '') in ADMIN_COMMAND_ALIASES


def _normalize_admin_alias(value: str) -> str:
    text = value.strip().lower().replace('_', ' ')
    normalized = unicodedata.normalize('NFKD', text)
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()


async def _answer_unauthorized(event: Message | CallbackQuery) -> None:
    if isinstance(event, CallbackQuery):
        await event.answer(UNAUTHORIZED_MESSAGE, show_alert=True)
        return
    await event.answer(UNAUTHORIZED_MESSAGE)


async def _notify_admins_about_access_request(*, event: Message, data: dict[str, Any], config: Config) -> None:
    bot = data.get('bot')
    if bot is None or not hasattr(bot, 'send_message') or event.from_user is None:
        return
    username = getattr(event.from_user, 'username', None) or '-'
    first_name = getattr(event.from_user, 'first_name', None) or ''
    last_name = getattr(event.from_user, 'last_name', None) or ''
    full_name = ' '.join(part for part in [first_name, last_name] if part).strip() or '-'
    text = (
        'Nov\u00e1 \u017eiados\u0165 o pr\u00edstup: '
        f'telegram_id={event.from_user.id}, username={username}, meno={full_name}'
    )
    for admin_id in config.admin_telegram_user_ids:
        try:
            await bot.send_message(admin_id, text)
        except Exception:
            logger.exception('Failed to send access request notification to admin')
