"""Admin-only Gmail statement collector setup commands."""

import html

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Config
from bot.services.authorization import is_admin_telegram_user
from bot.services.google_gmail_config import load_google_gmail_config
from bot.services.google_integration_service import (
    GoogleIntegrationError,
    GoogleIntegrationService,
)
from bot.services.token_crypto import FernetTokenCryptoProvider, TokenCryptoError
from bot.services.workspace_context import WorkspaceContextService, WorkspaceContextError


router = Router(name="gmail_settings")

ADMIN_ONLY = "Pripojenie Gmailu môže spravovať iba administrátor."
NOT_CONFIGURED = (
    "Gmail zber výpisov nie je pripravený. Skontrolujte serverovú konfiguráciu."
)


@router.message(Command("gmail_connect"))
async def cmd_gmail_connect(message: Message, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if not is_admin_telegram_user(config, telegram_id):
        await message.answer(ADMIN_ONLY)
        return
    try:
        gmail = load_google_gmail_config()
        if not gmail.enabled:
            raise RuntimeError("gmail_disabled")
        workspace = WorkspaceContextService(config.db_path).require_membership(
            telegram_id, gmail.target_workspace_id or ""
        )
        service = _service(config, gmail.token_crypto_secret)
        prepared = service.prepare_oauth(
            workspace_id=workspace.workspace_id,
            telegram_id=telegram_id,
            service="gmail",
            oauth_client_key="primary",
            expected_google_email=gmail.expected_email or "",
            client_id=gmail.client_id or "",
            redirect_uri=gmail.public_redirect_uri or "",
        )
    except (RuntimeError, GoogleIntegrationError, WorkspaceContextError, TokenCryptoError):
        await message.answer(NOT_CONFIGURED)
        return
    await message.answer(
        f"Pripojenie Gmailu bude patriť k profilu "
        f"{html.escape(workspace.workspace_display_name)}.\n"
        f"Očakávaný účet: {html.escape(gmail.expected_email or '')}.\n\n"
        "Otvorte bezpečný odkaz a dokončite autorizáciu:\n"
        f"{html.escape(prepared.authorization_url, quote=False)}\n\n"
        "Pripojenie bude aktívne až po úspešnom návrate z Google."
    )


@router.message(Command("gmail_status"))
async def cmd_gmail_status(message: Message, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if not is_admin_telegram_user(config, telegram_id):
        await message.answer(ADMIN_ONLY)
        return
    try:
        gmail = load_google_gmail_config()
        workspace = WorkspaceContextService(config.db_path).require_membership(
            telegram_id, gmail.target_workspace_id or ""
        )
        status = _service(config, gmail.token_crypto_secret).get_binding_status(
            workspace.workspace_id
        )
    except GoogleIntegrationError as exc:
        if str(exc) == "google_binding_not_found":
            await message.answer("Gmail zatiaľ nie je pripojený.")
            return
        await message.answer("Stav Gmail pripojenia sa nepodarilo načítať.")
        return
    except (RuntimeError, WorkspaceContextError, TokenCryptoError):
        await message.answer(NOT_CONFIGURED)
        return
    lines = [
        "Gmail zber bankových výpisov:",
        f"- profil: {html.escape(workspace.workspace_display_name)}",
        f"- účet: {html.escape(status.google_email)}",
        f"- pripojenie: {html.escape(status.grant_status)}",
        f"- zber: {html.escape(status.binding_status)}",
        f"- posledná úspešná kontrola: "
        f"{html.escape(status.last_successful_check_at or 'zatiaľ neprebehla')}",
        f"- posledná chyba: {html.escape(status.last_error_code or 'žiadna')}",
        "- spracovanie obsahu: nepodporované (odložené)",
        f"- Google Drive archív: {'zapnutý samostatne' if config.google_drive_enabled else 'nie je nakonfigurovaný'}",
    ]
    await message.answer("\n".join(lines))


@router.message(Command("gmail_disconnect"))
async def cmd_gmail_disconnect(message: Message, config: Config) -> None:
    telegram_id = _telegram_id(message)
    if not is_admin_telegram_user(config, telegram_id):
        await message.answer(ADMIN_ONLY)
        return
    try:
        gmail = load_google_gmail_config()
        workspace = WorkspaceContextService(config.db_path).require_membership(
            telegram_id, gmail.target_workspace_id or ""
        )
        _service(config, gmail.token_crypto_secret).disconnect(workspace.workspace_id)
    except (RuntimeError, WorkspaceContextError, TokenCryptoError):
        await message.answer(NOT_CONFIGURED)
        return
    await message.answer(
        "Gmail pripojenie bolo lokálne odpojené. Budúci zber je zastavený. "
        "Už uložené výpisy ani súbory na Google Drive sa nevymazali."
    )


def _service(config: Config, secret: str | None) -> GoogleIntegrationService:
    return GoogleIntegrationService(
        config.db_path,
        FernetTokenCryptoProvider(
            secret=secret, key_id="google-integration-fernet-v1"
        ),
    )


def _telegram_id(message: Message) -> int:
    user = getattr(message, "from_user", None)
    return int(getattr(user, "id", 0) or 0)
