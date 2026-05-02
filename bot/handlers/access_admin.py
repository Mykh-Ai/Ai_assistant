from __future__ import annotations

import re
import unicodedata

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message

from bot.config import Config
from bot.services.access_control import ACCESS_STATUS_PENDING, AccessControlService
from bot.services.authorization import UNAUTHORIZED_MESSAGE, is_admin_telegram_user


router = Router(name='access_admin')


_ACCESS_REQUESTS_ALIASES = {
    'access requests',
    'access_requests',
    'ziadosti',
    'ziadosti o pristup',
    'zapros',
    '\u0437\u0430\u043f\u0440\u043e\u0441',
    '\u0437\u0430\u043f\u0438\u0442',
    '\u0437\u0430\u043f\u0438\u0442\u0438',
    '\u0437\u0430\u043f\u0438\u0442\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u0443',
    '\u0437\u0430\u044f\u0432\u043a\u0438',
    '\u0437\u0430\u044f\u0432\u043a\u0438 \u0434\u043e\u0441\u0442\u0443\u043f\u0443',
}

_USERS_ALIASES = {
    'users',
    'pouzivatelia',
    'pouzivatel',
    '\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0438',
    '\u043a\u043e\u0440\u0438\u0441\u0442\u0443\u0432\u0430\u0447\u0456',
    '\u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u0438',
}


@router.message(Command('access_requests'))
async def cmd_access_requests(message: Message, config: Config) -> None:
    await _send_access_requests(message, config)


@router.message(
    StateFilter(None),
    lambda message: _normalize_alias(message.text or '') in _ACCESS_REQUESTS_ALIASES,
)
async def access_requests_alias(message: Message, config: Config) -> None:
    await _send_access_requests(message, config)


async def _send_access_requests(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    requests = AccessControlService(config.db_path).list_access_requests(status=ACCESS_STATUS_PENDING)
    if not requests:
        await message.answer('Nie su ziadne cakajuce ziadosti o pristup.')
        return

    lines = ['Cakajuce ziadosti o pristup:']
    for request in requests:
        lines.append(
            _format_access_request_line(
                telegram_id=request.telegram_id,
                username=request.username,
                first_name=request.first_name,
                last_name=request.last_name,
                status=request.status,
            )
        )
    await message.answer('\n'.join(lines))


@router.message(Command('approve'))
async def cmd_approve(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    telegram_id = _parse_telegram_id_arg(message.text or '')
    if telegram_id is None:
        await message.answer('Pouzitie: /approve <telegram_id>')
        return

    AccessControlService(config.db_path).approve_user(
        telegram_id=telegram_id,
        approved_by=message.from_user.id,
    )
    await message.answer(f'Pouzivatel {telegram_id} bol schvaleny.')


@router.message(Command('reject'))
async def cmd_reject(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    telegram_id = _parse_telegram_id_arg(message.text or '')
    if telegram_id is None:
        await message.answer('Pouzitie: /reject <telegram_id>')
        return

    AccessControlService(config.db_path).reject_user(
        telegram_id=telegram_id,
        decided_by=message.from_user.id,
    )
    await message.answer(f'Ziadost pouzivatela {telegram_id} bola zamietnuta.')


@router.message(Command('block'))
async def cmd_block(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    telegram_id = _parse_telegram_id_arg(message.text or '')
    if telegram_id is None:
        await message.answer('Pouzitie: /block <telegram_id>')
        return

    AccessControlService(config.db_path).block_user(
        telegram_id=telegram_id,
        decided_by=message.from_user.id,
    )
    await message.answer(f'Pouzivatel {telegram_id} bol zablokovany.')


@router.message(Command('users'))
async def cmd_users(message: Message, config: Config) -> None:
    await _send_users(message, config)


@router.message(
    StateFilter(None),
    lambda message: _normalize_alias(message.text or '') in _USERS_ALIASES,
)
async def users_alias(message: Message, config: Config) -> None:
    await _send_users(message, config)


async def _send_users(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    users = AccessControlService(config.db_path).list_authorized_users()
    if not users:
        await message.answer('Nie su ziadni autorizovani pouzivatelia v databaze.')
        return

    lines = ['Autorizovani pouzivatelia:']
    for user in users:
        lines.append(f'- telegram_id={user.telegram_id}, role={user.role}, status={user.status}')
    await message.answer('\n'.join(lines))


def _is_admin_message(message: Message, config: Config) -> bool:
    telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    return is_admin_telegram_user(config, telegram_id)


def _parse_telegram_id_arg(text: str) -> int | None:
    parts = text.split(maxsplit=1)
    if len(parts) != 2:
        return None
    try:
        telegram_id = int(parts[1].strip())
    except ValueError:
        return None
    return telegram_id if telegram_id > 0 else None


def _normalize_alias(value: str) -> str:
    text = value.strip().lower().replace('_', ' ')
    normalized = unicodedata.normalize('NFKD', text)
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r'\s+', ' ', without_diacritics).strip()


def _format_access_request_line(
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    status: str,
) -> str:
    username_value = username or '-'
    full_name = ' '.join(part for part in [first_name, last_name] if part).strip() or '-'
    return f'- telegram_id={telegram_id}, username={username_value}, meno={full_name}, status={status}'
