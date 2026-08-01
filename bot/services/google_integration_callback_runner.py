from __future__ import annotations

import asyncio

from aiohttp import web

from bot.config import Config
from bot.google_integration_callback_app import (
    create_google_integration_callback_app,
)
from bot.services.authorization import is_admin_telegram_user
from bot.services.google_gmail_config import GoogleGmailConfig
from bot.services.google_integration_callback_service import (
    GoogleIntegrationCallbackService,
)
from bot.services.google_integration_oauth import (
    GoogleIntegrationTokenClient,
    OfficialGoogleIdentityVerifier,
)
from bot.services.google_integration_service import (
    GoogleIntegrationError,
    GoogleIntegrationService,
    GoogleOAuthState,
)
from bot.services.token_crypto import FernetTokenCryptoProvider
from bot.services.workspace_context import WorkspaceContextService


async def run_google_integration_callback(
    *, bot: object, config: Config, gmail: GoogleGmailConfig
) -> None:
    if not gmail.callback_enabled:
        return
    crypto = FernetTokenCryptoProvider(
        secret=gmail.token_crypto_secret, key_id="google-integration-fernet-v1"
    )
    integration = GoogleIntegrationService(config.db_path, crypto)
    integration.ensure_schema()
    callback = GoogleIntegrationCallbackService(
        integration=integration,
        tokens=GoogleIntegrationTokenClient(
            client_id=gmail.client_id or "",
            client_secret=gmail.client_secret or "",
        ),
        identities=OfficialGoogleIdentityVerifier(client_id=gmail.client_id or ""),
        validate_context=lambda state: _validate_context(config, gmail, state),
    )

    async def notify(telegram_id: int, success: bool) -> None:
        text = (
            "Gmail pripojenie bolo úspešne uložené."
            if success
            else "Gmail pripojenie sa nepodarilo dokončiť. Skúste /gmail_connect znova."
        )
        if hasattr(bot, "send_message"):
            await bot.send_message(telegram_id, text)

    app = create_google_integration_callback_app(
        callback_service=callback,
        proxy_secret=gmail.callback_proxy_secret or "",
        notify=notify,
    )
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    site = web.TCPSite(runner, gmail.callback_host, gmail.callback_port)
    await site.start()
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


def _validate_context(
    config: Config, gmail: GoogleGmailConfig, state: GoogleOAuthState
) -> None:
    if state.requested_service != "gmail":
        raise GoogleIntegrationError("oauth_service_invalid")
    if state.workspace_id != gmail.target_workspace_id:
        raise GoogleIntegrationError("oauth_workspace_invalid")
    if not is_admin_telegram_user(config, state.telegram_id):
        raise GoogleIntegrationError("oauth_requester_unauthorized")
    workspace = WorkspaceContextService(config.db_path)
    workspace.require_membership(state.telegram_id, state.workspace_id)
    canonical = workspace.resolve_for_background_workspace(state.workspace_id)
    if canonical.workspace_id != state.workspace_id:
        raise GoogleIntegrationError("oauth_workspace_invalid")
