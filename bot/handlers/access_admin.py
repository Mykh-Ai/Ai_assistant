from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Config
from bot.services.access_control import ACCESS_STATUS_PENDING, AccessControlService
from bot.services.authorization import UNAUTHORIZED_MESSAGE, is_admin_telegram_user


router = Router(name='access_admin')


@router.message(Command('access_requests'))
async def cmd_access_requests(message: Message, config: Config) -> None:
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
