"""Settings and integration setup command handlers."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Config
from bot.services.authorization import is_admin_telegram_user
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GOOGLE_DRIVE_STATUS_DISCONNECTED,
    GOOGLE_DRIVE_STATUS_ERROR,
    GOOGLE_DRIVE_STATUS_NEEDS_REAUTH,
    GOOGLE_DRIVE_STATUS_REVOKED,
    GoogleDriveConnectionService,
    GoogleDriveConnectionServiceError,
    GoogleDriveConnectionRecord,
)
from bot.services.google_drive_oauth_state_service import (
    DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
    GoogleDriveOAuthStateService,
    GoogleDriveOAuthStateServiceError,
)
from bot.services.token_crypto import UnconfiguredTokenCryptoProvider

router = Router(name='settings')

GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE = (
    'Google Drive pripojenie moze v tejto verzii spravovat iba spravca.'
)
GOOGLE_DRIVE_CONFIG_MISSING_MESSAGE = (
    'Google Drive pripojenie nie je v bote nakonfigurovane. '
    'Chyba GOOGLE_OAUTH_CLIENT_ID alebo GOOGLE_OAUTH_REDIRECT_URI.'
)
GOOGLE_DRIVE_NOT_CONNECTED_MESSAGE = 'Google Drive archiv zatial nie je pripojeny.'
GOOGLE_DRIVE_DISCONNECTED_MESSAGE = (
    'Google Drive pripojenie bolo v bote odpojene. '
    'Subory, ktore uz existuju na Google Drive, sa tymto nemazu.'
)


@router.message(Command('google_drive_connect'))
async def cmd_google_drive_connect(message: Message, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if not _is_admin_message(message, config):
        await message.answer(GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE)
        return

    if not config.google_oauth_client_id or not config.google_oauth_redirect_uri:
        await message.answer(GOOGLE_DRIVE_CONFIG_MISSING_MESSAGE)
        return

    state_service = GoogleDriveOAuthStateService(config.db_path)
    try:
        created = state_service.create_oauth_state(
            workspace_id=_workspace_id_for_telegram_id(telegram_id),
            telegram_id=telegram_id,
            scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
            redirect_uri=config.google_oauth_redirect_uri,
        )
        authorization_url = state_service.build_authorization_url(
            client_id=config.google_oauth_client_id,
            redirect_uri=config.google_oauth_redirect_uri,
            scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
            state_token=created.raw_state_token,
        )
    except GoogleDriveOAuthStateServiceError:
        await message.answer(
            'Google Drive pripojenie sa teraz nepodarilo pripravit. Skuste to neskor.'
        )
        return

    await message.answer(
        'Google Drive archiv je v rezime nastavenia. Tento prikaz iba pripravi '
        'bezpecny prihlasovaci odkaz; nenahrava subory a nespusta archivaciu.\n\n'
        f'Otvorte tento odkaz a dokoncite pripojenie:\n{authorization_url}\n\n'
        'Archivovanie do Google Drive bude aktivne az po dokonceni runtime '
        'callbacku a realneho upload adaptera.'
    )


@router.message(Command('google_drive_status'))
async def cmd_google_drive_status(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE)
        return

    record = _connection_service(config).get_connection_for_workspace(
        workspace_id=_workspace_id_for_telegram_id(_telegram_id(message))
    )
    if record is None:
        await message.answer(GOOGLE_DRIVE_NOT_CONNECTED_MESSAGE)
        return

    await message.answer(_format_google_drive_status(record))


@router.message(Command('google_drive_disconnect'))
async def cmd_google_drive_disconnect(message: Message, config: Config) -> None:
    if not _is_admin_message(message, config):
        await message.answer(GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE)
        return

    service = _connection_service(config)
    workspace_id = _workspace_id_for_telegram_id(_telegram_id(message))
    try:
        service.mark_disconnected(workspace_id=workspace_id)
    except GoogleDriveConnectionServiceError as exc:
        if str(exc) == 'connection_not_found':
            await message.answer(GOOGLE_DRIVE_NOT_CONNECTED_MESSAGE)
            return
        await message.answer('Google Drive pripojenie sa teraz nepodarilo odpojit.')
        return

    await message.answer(GOOGLE_DRIVE_DISCONNECTED_MESSAGE)


def _is_admin_message(message: Message, config: Config) -> bool:
    return is_admin_telegram_user(config, _telegram_id(message))


def _telegram_id(message: Message) -> int:
    user = getattr(message, 'from_user', None)
    if user is None or getattr(user, 'id', None) is None:
        return 0
    return int(user.id)


def _workspace_id_for_telegram_id(telegram_id: int) -> str:
    return f'telegram-{telegram_id}'


def _connection_service(config: Config) -> GoogleDriveConnectionService:
    return GoogleDriveConnectionService(config.db_path, UnconfiguredTokenCryptoProvider())


def _format_google_drive_status(record: GoogleDriveConnectionRecord) -> str:
    status = record.status
    lines = ['Google Drive archiv - stav pripojenia:', f'- status: {status}']
    if record.google_email:
        lines.append(f'- ucet: {record.google_email}')
    if record.root_folder_path:
        lines.append(f'- priecinok: {record.root_folder_path}')
    if record.last_error_code:
        lines.append(f'- posledna chyba: {record.last_error_code}')

    if status == GOOGLE_DRIVE_STATUS_CONNECTED:
        lines.append('Pripojenie je ulozene v bote, ale tento prikaz nespusta nahravanie suborov.')
    elif status == GOOGLE_DRIVE_STATUS_NEEDS_REAUTH:
        lines.append('Pripojenie vyzaduje opatovne prihlasenie cez /google_drive_connect.')
    elif status in {GOOGLE_DRIVE_STATUS_DISCONNECTED, GOOGLE_DRIVE_STATUS_REVOKED}:
        lines.append('Google Drive archiv zatial nie je aktivne pripojeny.')
    elif status == GOOGLE_DRIVE_STATUS_ERROR:
        lines.append('Pripojenie ma chybovy stav a vyzaduje kontrolu spravcom.')
    return '\n'.join(lines)
