from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import inspect
from pathlib import Path
import sqlite3
from urllib.parse import urlencode

from aiohttp.test_utils import make_mocked_request

from bot.config import Config
from bot import google_drive_oauth_callback_app
import bot.main as bot_main
from bot.google_drive_oauth_callback_app import (
    GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE,
    GOOGLE_DRIVE_CALLBACK_BROWSER_SUCCESS,
    GOOGLE_DRIVE_CALLBACK_TELEGRAM_FAILURE,
    GOOGLE_DRIVE_CALLBACK_TELEGRAM_SUCCESS,
    FakeGoogleOAuthTokenExchanger,
    create_callback_app,
    create_callback_app_from_config,
    handle_google_drive_oauth_callback,
)
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GoogleDriveConnectionService,
)
from bot.services.google_drive_oauth_callback_service import GoogleDriveOAuthCallbackService
from bot.services.google_drive_oauth_state_service import (
    DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
    GOOGLE_DRIVE_OAUTH_ERROR_CODE_MISSING,
    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
    GOOGLE_DRIVE_OAUTH_ERROR_INVALID,
    GOOGLE_DRIVE_OAUTH_ERROR_REUSED,
    GOOGLE_DRIVE_OAUTH_STATUS_REJECTED,
    GoogleDriveOAuthStateService,
)
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import ProductTruthStatus, get_capability
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


REDIRECT_URI = 'https://officeflow.example.test/oauth/google/callback'
AUTH_CODE = '4/0AfJohXn-raw-auth-code-secret'
RAW_STATE_SENTINEL = 'raw-state-token-secret'


class DummyBot:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.messages.append((telegram_id, text))


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'google-drive-oauth-callback-app.db'


def _crypto() -> DeterministicFakeTokenCryptoProvider:
    return DeterministicFakeTokenCryptoProvider(key_id='callback-app-test-key')


def _create_state(
    tmp_path: Path,
    *,
    now: datetime | None = None,
    ttl_minutes: int = 10,
):
    return GoogleDriveOAuthStateService(_db_path(tmp_path)).create_oauth_state(
        workspace_id='telegram-111001',
        telegram_id=111001,
        scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        redirect_uri=REDIRECT_URI,
        now=now or datetime.now(UTC),
        ttl_minutes=ttl_minutes,
    )


def _build_app(tmp_path: Path, *, exchanger: FakeGoogleOAuthTokenExchanger | None = None, bot: DummyBot | None = None):
    exchanger = exchanger or FakeGoogleOAuthTokenExchanger()
    bot = bot or DummyBot()
    callback_service = GoogleDriveOAuthCallbackService(
        db_path=_db_path(tmp_path),
        crypto_provider=_crypto(),
        token_exchanger=exchanger,
    )
    app = create_callback_app(
        callback_service=callback_service,
        oauth_state_service=GoogleDriveOAuthStateService(_db_path(tmp_path)),
        bot=bot,
    )
    return app, exchanger, bot


def _callback_path(**params: str) -> str:
    return '/oauth/google/callback?' + urlencode(params)


def _call(app, **params: str):
    request = make_mocked_request('GET', _callback_path(**params), app=app)
    return asyncio.run(handle_google_drive_oauth_callback(request))


def _all_db_values(tmp_path: Path) -> str:
    chunks: list[str] = []
    with sqlite3.connect(_db_path(tmp_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        for table in ('google_drive_oauth_states', 'google_drive_connections'):
            if table not in tables:
                continue
            for row in connection.execute(f'SELECT * FROM {table}').fetchall():
                for value in row:
                    if isinstance(value, bytes):
                        chunks.append(value.decode('utf-8', errors='ignore'))
                    else:
                        chunks.append(str(value))
    return '\n'.join(chunks)


def _assert_response_safe(text: str, created_state: str | None = None) -> None:
    forbidden = [
        AUTH_CODE,
        RAW_STATE_SENTINEL,
        'fake-callback-access-token',
        'fake-callback-refresh-token',
        'client_secret',
        'access_token',
        'refresh_token',
        'id_token',
    ]
    if created_state is not None:
        forbidden.append(created_state)
    assert not any(value in text for value in forbidden)


def test_valid_state_and_code_returns_success_sends_telegram_and_creates_connection(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(app, state=created.raw_state_token, code=AUTH_CODE)

    connection_service = GoogleDriveConnectionService(_db_path(tmp_path), _crypto())
    record = connection_service.get_connection_for_workspace(workspace_id='telegram-111001')

    assert response.status == 200
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_SUCCESS
    assert bot.messages == [(111001, GOOGLE_DRIVE_CALLBACK_TELEGRAM_SUCCESS)]
    assert exchanger.calls == 1
    assert record is not None
    assert record.status == GOOGLE_DRIVE_STATUS_CONNECTED
    assert record.google_email == 'fake-google-drive@example.test'
    _assert_response_safe(response.text, created.raw_state_token)
    _assert_response_safe(bot.messages[0][1], created.raw_state_token)


def test_missing_state_returns_generic_failure_and_does_not_call_exchanger(tmp_path: Path) -> None:
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(app, code=AUTH_CODE)

    assert response.status == 400
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 0
    assert bot.messages == []
    _assert_response_safe(response.text)


def test_wrong_state_returns_generic_failure_and_does_not_call_exchanger(tmp_path: Path) -> None:
    _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(app, state=RAW_STATE_SENTINEL, code=AUTH_CODE)

    assert response.status == 400
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 0
    assert bot.messages == []
    assert GOOGLE_DRIVE_OAUTH_ERROR_INVALID not in response.text
    _assert_response_safe(response.text)


def test_expired_state_returns_generic_failure_and_does_not_call_exchanger(tmp_path: Path) -> None:
    created = _create_state(tmp_path, now=datetime(2000, 1, 1, tzinfo=UTC))
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(app, state=created.raw_state_token, code=AUTH_CODE)

    assert response.status == 400
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 0
    assert bot.messages == []
    assert GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED not in response.text


def test_reused_state_returns_generic_failure_and_does_not_call_exchanger_twice(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)
    first = _call(app, state=created.raw_state_token, code=AUTH_CODE)

    second = _call(app, state=created.raw_state_token, code=AUTH_CODE)

    assert first.status == 200
    assert second.status == 400
    assert second.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 1
    assert bot.messages == [(111001, GOOGLE_DRIVE_CALLBACK_TELEGRAM_SUCCESS)]
    assert GOOGLE_DRIVE_OAUTH_ERROR_REUSED not in second.text


def test_missing_code_returns_failure_sends_safe_message_and_sets_bounded_state_error(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(app, state=created.raw_state_token)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert response.status == 400
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 0
    assert bot.messages == [(111001, GOOGLE_DRIVE_CALLBACK_TELEGRAM_FAILURE)]
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert row[1] == GOOGLE_DRIVE_OAUTH_ERROR_CODE_MISSING
    _assert_response_safe(response.text, created.raw_state_token)
    _assert_response_safe(bot.messages[0][1], created.raw_state_token)


def test_google_error_param_rejects_state_and_sends_safe_failure_message(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(
        app,
        state=created.raw_state_token,
        error='access_denied_raw_google_error',
    )

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert response.status == 400
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 0
    assert bot.messages == [(111001, GOOGLE_DRIVE_CALLBACK_TELEGRAM_FAILURE)]
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert row[1] == 'drive_oauth_state_rejected'
    assert 'access_denied_raw_google_error' not in response.text
    assert 'access_denied_raw_google_error' not in bot.messages[0][1]


def test_google_error_with_wrong_state_sends_no_telegram_and_does_not_call_exchanger(tmp_path: Path) -> None:
    _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(
        app,
        state=RAW_STATE_SENTINEL,
        error='access_denied_raw_google_error',
        error_description='raw-provider-url https://accounts.google.com/o/oauth2/v2/auth?code=secret',
    )

    assert response.status == 400
    assert response.text == GOOGLE_DRIVE_CALLBACK_BROWSER_FAILURE
    assert exchanger.calls == 0
    assert bot.messages == []
    assert 'access_denied_raw_google_error' not in response.text
    assert 'raw-provider-url' not in response.text


def test_google_error_description_is_not_reflected_to_browser_or_telegram(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)
    raw_description = 'token-like-error refresh_token=secret&client_secret=hidden'

    response = _call(
        app,
        state=created.raw_state_token,
        error='access_denied',
        error_description=raw_description,
    )

    assert response.status == 400
    assert exchanger.calls == 0
    assert bot.messages == [(111001, GOOGLE_DRIVE_CALLBACK_TELEGRAM_FAILURE)]
    assert raw_description not in response.text
    assert raw_description not in bot.messages[0][1]


def test_query_telegram_id_is_ignored_and_consumed_state_user_is_notified(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, exchanger, bot = _build_app(tmp_path)

    response = _call(
        app,
        state=created.raw_state_token,
        code=AUTH_CODE,
        telegram_id='999999',
    )

    assert response.status == 200
    assert exchanger.calls == 1
    assert bot.messages == [(111001, GOOGLE_DRIVE_CALLBACK_TELEGRAM_SUCCESS)]


def test_browser_telegram_and_db_do_not_include_code_state_or_tokens(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    app, _, bot = _build_app(tmp_path)

    response = _call(app, state=created.raw_state_token, code=AUTH_CODE)
    db_values = _all_db_values(tmp_path)

    assert response.status == 200
    _assert_response_safe(response.text, created.raw_state_token)
    _assert_response_safe(bot.messages[0][1], created.raw_state_token)
    assert AUTH_CODE not in db_values
    assert created.raw_state_token not in db_values
    assert 'fake-callback-access-token' not in db_values
    assert 'fake-callback-refresh-token' not in db_values


def test_callback_app_uses_fake_exchanger_and_imports_no_google_client_or_archive_worker() -> None:
    source = inspect.getsource(google_drive_oauth_callback_app)

    forbidden = (
        'googleapiclient',
        'google.auth',
        'requests',
        'httpx',
        'socket',
        'ClientSession',
        'archive_worker',
    )

    assert not any(value in source for value in forbidden)
    assert 'FakeGoogleOAuthTokenExchanger' in source
    assert 'DeterministicFakeTokenCryptoProvider' not in source


def test_bot_main_has_no_callback_app_wiring() -> None:
    source = inspect.getsource(bot_main)

    assert 'google_drive_oauth_callback_app' not in source
    assert 'oauth/google/callback' not in source


def test_create_callback_app_from_config_requires_bot_token(tmp_path: Path) -> None:
    config = _config(tmp_path, bot_token='', use_fake_exchanger=True)

    try:
        create_callback_app_from_config(config)
    except RuntimeError as exc:
        assert str(exc) == 'BOT_TOKEN is required'
    else:
        raise AssertionError('missing BOT_TOKEN must fail safely')


def test_create_callback_app_from_config_fails_closed_by_default(tmp_path: Path) -> None:
    config = _config(tmp_path, bot_token='123:ABC', use_fake_exchanger=False)

    try:
        create_callback_app_from_config(config)
    except RuntimeError as exc:
        assert str(exc) == (
            'Google Drive OAuth callback runtime is disabled until production token exchange '
            'and token crypto are configured'
        )
    else:
        raise AssertionError('callback runtime must fail closed without production exchanger/crypto')


def test_create_callback_app_from_config_rejects_fake_mode_and_creates_no_db(tmp_path: Path) -> None:
    config = _config(tmp_path, bot_token='123:ABC', use_fake_exchanger=True)

    try:
        create_callback_app_from_config(config)
    except RuntimeError as exc:
        assert 'production token exchange and token crypto' in str(exc)
    else:
        raise AssertionError('fake mode must not enable runtime callback startup')

    assert not _db_path(tmp_path).exists()


def test_callback_runtime_is_not_wired_to_real_token_exchanger() -> None:
    source = inspect.getsource(google_drive_oauth_callback_app)

    assert 'google_oauth_token_exchanger' not in source
    assert 'bot.services.google_oauth_token_exchanger' not in source
    assert 'UrllibGoogleOAuthHTTPClient' not in source


def test_google_drive_product_truth_is_partial_service_account_not_oauth() -> None:
    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Can bot save invoices to Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.PARTIAL
    assert result.capability.runtime_owner is not None
    assert answer is not None
    assert 'owner OAuth' in answer


def _config(
    tmp_path: Path,
    *,
    bot_token: str = '123:ABC',
    use_fake_exchanger: bool = True,
) -> Config:
    return Config(
        bot_token=bot_token,
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=_db_path(tmp_path),
        storage_dir=tmp_path,
        google_oauth_callback_host='127.0.0.1',
        google_oauth_callback_port=8080,
        google_oauth_callback_use_fake_exchanger=use_fake_exchanger,
    )
