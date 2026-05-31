from __future__ import annotations

from dataclasses import dataclass
import logging

from aiohttp import web
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import Config, load_config
from bot.services.db import init_db
from bot.services.google_drive_oauth_callback_service import (
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GoogleDriveOAuthCallbackResult,
    GoogleDriveOAuthCallbackService,
    GoogleOAuthTokenBundle,
)
from bot.services.google_drive_oauth_state_service import (
    GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    GoogleDriveOAuthStateService,
    GoogleDriveOAuthStateServiceError,
)
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


logger = logging.getLogger(__name__)

OAUTH_CALLBACK_PATH = '/oauth/google/callback'

CALLBACK_SERVICE_KEY = web.AppKey('google_drive_oauth_callback_service', GoogleDriveOAuthCallbackService)
OAUTH_STATE_SERVICE_KEY = web.AppKey('google_drive_oauth_state_service', GoogleDriveOAuthStateService)
BOT_KEY = web.AppKey('telegram_bot', object)

GOOGLE_DRIVE_CALLBACK_BROWSER_SUCCESS = (
    'Google Drive pripojenie bolo spracovane. Mozete sa vratit do Telegramu.'
)
GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE = (
    'Google Drive pripojenie sa nepodarilo spracovat. Vratte sa do Telegramu a skuste pripojenie znova.'
)
GOOGLE_DRIVE_CALLBACK_TELEGRAM_SUCCESS = (
    'Google Drive pripojenie bolo uspesne ulozene. Samotna archivacia dokladov bude aktivna az po '
    'dokonceni podporovaneho runtime nastavenia.'
)
GOOGLE_DRIVE_CALLBACK_TELEGRAM_FAILURE = (
    'Google Drive pripojenie sa nepodarilo ulozit. Skuste /google_drive_connect znova.'
)


@dataclass
class FakeGoogleOAuthTokenExchanger:
    calls: int = 0

    def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        scopes: tuple[str, ...],
    ) -> GoogleOAuthTokenBundle:
        self.calls += 1
        return GoogleOAuthTokenBundle(
            access_token='fake-callback-access-token',
            refresh_token='fake-callback-refresh-token',
            expires_at=None,
            scope=scopes,
            token_type='Bearer',
            id_token=None,
            google_subject='fake-google-subject',
            google_email='fake-google-drive@example.test',
        )


def create_callback_app(
    *,
    callback_service: GoogleDriveOAuthCallbackService,
    oauth_state_service: GoogleDriveOAuthStateService,
    bot: object,
) -> web.Application:
    app = web.Application()
    app[CALLBACK_SERVICE_KEY] = callback_service
    app[OAUTH_STATE_SERVICE_KEY] = oauth_state_service
    app[BOT_KEY] = bot
    app.router.add_get(OAUTH_CALLBACK_PATH, handle_google_drive_oauth_callback)
    return app


def create_callback_app_from_config(config: Config) -> web.Application:
    _validate_runtime_config(config)
    init_db(config.db_path)
    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    exchanger = FakeGoogleOAuthTokenExchanger()
    crypto_provider = DeterministicFakeTokenCryptoProvider(key_id='fake-google-drive-callback-key')
    callback_service = GoogleDriveOAuthCallbackService(
        db_path=config.db_path,
        crypto_provider=crypto_provider,
        token_exchanger=exchanger,
    )
    oauth_state_service = GoogleDriveOAuthStateService(config.db_path)
    return create_callback_app(
        callback_service=callback_service,
        oauth_state_service=oauth_state_service,
        bot=bot,
    )


async def handle_google_drive_oauth_callback(request: web.Request) -> web.Response:
    state_token = (request.query.get('state') or '').strip()
    code = (request.query.get('code') or '').strip()
    google_error = (request.query.get('error') or '').strip()

    if not state_token:
        logger.info('google_drive_oauth_callback_failed', extra={'error_code': 'drive_oauth_state_invalid'})
        return _browser_response(success=False)

    if google_error:
        result = _reject_google_error_state(request, state_token=state_token)
        await _send_telegram_result(request, result)
        return _browser_response(success=False)

    callback_service = _callback_service(request)
    result = callback_service.handle_callback(state_token=state_token, code=code)
    await _send_telegram_result(request, result)
    logger.info(
        'google_drive_oauth_callback_result',
        extra={'success': result.success, 'error_code': result.error_code},
    )
    return _browser_response(success=result.success)


def _reject_google_error_state(request: web.Request, *, state_token: str) -> GoogleDriveOAuthCallbackResult:
    state_service = _oauth_state_service(request)
    try:
        state = state_service.mark_oauth_state_rejected(
            raw_state_token=state_token,
            error_code=GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
        )
    except GoogleDriveOAuthStateServiceError:
        logger.info('google_drive_oauth_callback_failed', extra={'error_code': 'drive_oauth_state_invalid'})
        return GoogleDriveOAuthCallbackResult(success=False, error_code=GOOGLE_DRIVE_ERROR_CONNECTION)
    logger.info('google_drive_oauth_callback_failed', extra={'error_code': GOOGLE_DRIVE_OAUTH_ERROR_REJECTED})
    return GoogleDriveOAuthCallbackResult(
        success=False,
        workspace_id=state.workspace_id,
        telegram_id=state.telegram_id,
        error_code=GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    )


async def _send_telegram_result(request: web.Request, result: GoogleDriveOAuthCallbackResult) -> None:
    if result.telegram_id is None:
        return
    text = GOOGLE_DRIVE_CALLBACK_TELEGRAM_SUCCESS if result.success else GOOGLE_DRIVE_CALLBACK_TELEGRAM_FAILURE
    bot = request.app[BOT_KEY]
    if not hasattr(bot, 'send_message'):
        return
    try:
        await bot.send_message(result.telegram_id, text)
    except Exception:
        logger.exception(
            'google_drive_oauth_callback_telegram_notification_failed',
            extra={'success': result.success, 'error_code': result.error_code},
        )


def _browser_response(*, success: bool) -> web.Response:
    text = GOOGLE_DRIVE_CALLBACK_BROWSER_SUCCESS if success else GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    status = 200 if success else 400
    return web.Response(text=text, status=status, content_type='text/plain')


def _callback_service(request: web.Request) -> GoogleDriveOAuthCallbackService:
    return request.app[CALLBACK_SERVICE_KEY]


def _oauth_state_service(request: web.Request) -> GoogleDriveOAuthStateService:
    return request.app[OAUTH_STATE_SERVICE_KEY]


def _validate_runtime_config(config: Config) -> None:
    if not str(config.bot_token).strip():
        raise RuntimeError('BOT_TOKEN is required')
    if not config.google_oauth_callback_use_fake_exchanger:
        raise RuntimeError('GOOGLE_OAUTH_CALLBACK_USE_FAKE_EXCHANGER must be enabled for this fake callback skeleton')
    if config.google_oauth_callback_port <= 0:
        raise RuntimeError('GOOGLE_OAUTH_CALLBACK_PORT must be a positive integer')


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )
    config = load_config()
    app = create_callback_app_from_config(config)
    web.run_app(
        app,
        host=config.google_oauth_callback_host,
        port=config.google_oauth_callback_port,
    )


if __name__ == '__main__':
    main()
