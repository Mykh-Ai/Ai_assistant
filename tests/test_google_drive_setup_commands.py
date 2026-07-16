from __future__ import annotations

import asyncio
import inspect
import os
from pathlib import Path
import re
import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest

from bot.config import Config
from bot.handlers import settings
from bot.handlers.settings import (
    GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE,
    GOOGLE_DRIVE_CONFIG_MISSING_MESSAGE,
    GOOGLE_DRIVE_DISCONNECTED_MESSAGE,
    GOOGLE_DRIVE_NOT_CONNECTED_MESSAGE,
    cmd_google_drive_connect,
    cmd_google_drive_disconnect,
    cmd_google_drive_status,
)
from bot.services.access_control import AccessControlService
from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.db import init_db, managed_connection
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GOOGLE_DRIVE_STATUS_DISCONNECTED,
    GOOGLE_DRIVE_STATUS_ERROR,
    GOOGLE_DRIVE_STATUS_NEEDS_REAUTH,
    GOOGLE_DRIVE_STATUS_REVOKED,
    GoogleDriveConnectionService,
)
from bot.services.google_drive_oauth_state_service import DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import ProductTruthStatus, get_capability
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


ADMIN_ID = 111001
USER_ID = 222002
UNKNOWN_ID = 333003


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str, user_id: int) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def _config(
    tmp_path: Path,
    *,
    admins: frozenset[int] = frozenset({ADMIN_ID}),
    client_id: str | None = 'client-id.apps.googleusercontent.com',
    redirect_uri: str | None = 'https://officeflow.example.test/oauth/google/callback',
) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'google-drive-setup.db',
        storage_dir=tmp_path,
        admin_telegram_user_ids=admins,
        google_oauth_client_id=client_id,
        google_oauth_redirect_uri=redirect_uri,
    )


def _state_rows(db_path: Path) -> list[sqlite3.Row]:
    with managed_connection(db_path) as connection:
        connection.row_factory = sqlite3.Row
        table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'google_drive_oauth_states'"
        ).fetchone()
        if table is None:
            return []
        return list(connection.execute('SELECT * FROM google_drive_oauth_states'))


def _workspace_id() -> str:
    return 'owner'


def _extract_url(text: str) -> str:
    match = re.search(r'https://accounts\.google\.com/[^\s]+', text)
    assert match is not None
    return match.group(0)


def _connection_service(config: Config) -> GoogleDriveConnectionService:
    return GoogleDriveConnectionService(
        config.db_path,
        DeterministicFakeTokenCryptoProvider(key_id='setup-test-key'),
    )


def _assert_no_status_internals(answer: str) -> None:
    forbidden = (
        'access_token',
        'refresh_token',
        'id_token',
        'safe-test-token',
        'ciphertext',
        'client_secret',
        'state_token',
        'authorization_url',
        'auth code',
        'openid',
        'drive.file',
        'googleapis',
        'scope',
    )

    lowered = answer.lower()
    assert not any(value in lowered for value in forbidden)


def test_admin_connect_creates_oauth_state_and_returns_safe_authorization_url(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/google_drive_connect', ADMIN_ID)

    asyncio.run(cmd_google_drive_connect(message, config))

    assert len(message.answers) == 1
    answer = message.answers[0]
    assert 'rezime nastavenia' in answer
    assert 'nenahrava subory' in answer
    assert 'nespusta archivaciu' in answer
    assert 'client_secret' not in answer

    url = _extract_url(answer)
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    assert parsed.scheme == 'https'
    assert parsed.netloc == 'accounts.google.com'
    assert params['client_id'] == ['client-id.apps.googleusercontent.com']
    assert params['redirect_uri'] == ['https://officeflow.example.test/oauth/google/callback']
    assert params['scope'] == [' '.join(DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES)]
    assert params['access_type'] == ['offline']
    assert params['prompt'] == ['consent']
    assert 'client_secret' not in params

    rows = _state_rows(config.db_path)
    assert len(rows) == 1
    assert rows[0]['workspace_id'] == _workspace_id()
    assert rows[0]['telegram_id'] == ADMIN_ID
    assert rows[0]['state_token_hash'] != params['state'][0]
    assert params['state'][0] not in rows[0]['state_token_hash']


def test_connect_missing_google_oauth_config_does_not_create_state(tmp_path: Path) -> None:
    config = _config(tmp_path, client_id=None)
    init_db(config.db_path)
    message = _DummyMessage('/google_drive_connect', ADMIN_ID)

    asyncio.run(cmd_google_drive_connect(message, config))

    assert message.answers == [GOOGLE_DRIVE_CONFIG_MISSING_MESSAGE]
    assert _state_rows(config.db_path) == []


def test_connect_missing_google_oauth_redirect_uri_does_not_create_state(tmp_path: Path) -> None:
    config = _config(tmp_path, redirect_uri=None)
    init_db(config.db_path)
    message = _DummyMessage('/google_drive_connect', ADMIN_ID)

    asyncio.run(cmd_google_drive_connect(message, config))

    assert message.answers == [GOOGLE_DRIVE_CONFIG_MISSING_MESSAGE]
    assert _state_rows(config.db_path) == []


def test_non_admin_cannot_connect_and_no_state_is_created(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    message = _DummyMessage('/google_drive_connect', USER_ID)

    asyncio.run(cmd_google_drive_connect(message, config))

    assert message.answers == [GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE]
    assert _state_rows(config.db_path) == []


def test_unauthorized_user_is_blocked_by_middleware_before_connect_handler(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/google_drive_connect', UNKNOWN_ID)
    state = _DummyState()
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('called')
        await cmd_google_drive_connect(event, data['config'])

    asyncio.run(
        TelegramUserAuthorizationMiddleware()(
            _handler,
            message,
            {'config': config, 'state': state},
        )
    )

    assert calls == []
    assert state.cleared is True
    assert message.answers == [UNAUTHORIZED_MESSAGE]
    assert _state_rows(config.db_path) == []


@pytest.mark.parametrize(
    'command',
    [
        '/google_drive_connect',
        '/google_drive_status',
        '/google_drive_disconnect',
    ],
)
def test_admin_google_drive_commands_pass_middleware_allowlist(
    tmp_path: Path,
    command: str,
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage(command, ADMIN_ID)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append(event.text)

    asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert calls == [command]
    assert message.answers == []


def test_status_without_connection_is_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/google_drive_status', ADMIN_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    assert message.answers == [GOOGLE_DRIVE_NOT_CONNECTED_MESSAGE]


def test_non_admin_cannot_read_google_drive_status(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    message = _DummyMessage('/google_drive_status', USER_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    assert message.answers == [GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE]


def test_status_connected_hides_secrets_and_runtime_overclaim(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _connection_service(config).create_or_update_connection(
        workspace_id=_workspace_id(),
        telegram_id=ADMIN_ID,
        scopes_granted=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_plaintext='access_token=plain refresh_token=secret',
        status=GOOGLE_DRIVE_STATUS_CONNECTED,
        google_email='Owner@Example.Test',
        root_folder_path='OfficeFlow/Faktury',
    )
    message = _DummyMessage('/google_drive_status', ADMIN_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    answer = message.answers[0]
    assert 'status: connected' in answer
    assert 'owner@example.test' in answer
    assert 'OfficeFlow/Faktury' in answer
    assert 'nespusta nahravanie suborov' in answer
    _assert_no_status_internals(answer)


def test_status_needs_reauth_shows_bounded_error_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = _connection_service(config)
    service.create_or_update_connection(
        workspace_id=_workspace_id(),
        telegram_id=ADMIN_ID,
        scopes_granted=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_plaintext='safe-test-token',
        google_email='owner@example.test',
    )
    service.mark_needs_reauth(
        workspace_id=_workspace_id(),
        error_code=GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    )
    message = _DummyMessage('/google_drive_status', ADMIN_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    answer = message.answers[0]
    assert 'status: needs_reauth' in answer
    assert 'opatovne prihlasenie' in answer
    assert GOOGLE_DRIVE_ERROR_AUTH_REVOKED in answer
    _assert_no_status_internals(answer)


def test_status_disconnected_is_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = _connection_service(config)
    service.create_or_update_connection(
        workspace_id=_workspace_id(),
        telegram_id=ADMIN_ID,
        scopes_granted=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_plaintext='safe-test-token',
        google_email='owner@example.test',
    )
    service.mark_disconnected(workspace_id=_workspace_id())
    message = _DummyMessage('/google_drive_status', ADMIN_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    answer = message.answers[0]
    assert 'status: disconnected' in answer
    assert 'zatial nie je aktivne pripojeny' in answer
    _assert_no_status_internals(answer)


def test_status_revoked_is_safe(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _connection_service(config).create_or_update_connection(
        workspace_id=_workspace_id(),
        telegram_id=ADMIN_ID,
        scopes_granted=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_plaintext='safe-test-token',
        status=GOOGLE_DRIVE_STATUS_REVOKED,
        google_email='owner@example.test',
    )
    message = _DummyMessage('/google_drive_status', ADMIN_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    answer = message.answers[0]
    assert 'status: revoked' in answer
    assert 'zatial nie je aktivne pripojeny' in answer
    _assert_no_status_internals(answer)


def test_status_error_shows_bounded_error_only(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _connection_service(config).create_or_update_connection(
        workspace_id=_workspace_id(),
        telegram_id=ADMIN_ID,
        scopes_granted=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_plaintext='safe-test-token',
        status=GOOGLE_DRIVE_STATUS_ERROR,
        google_email='owner@example.test',
    )
    with managed_connection(config.db_path) as connection:
        connection.execute(
            'UPDATE google_drive_connections SET last_error_code = ? WHERE workspace_id = ?',
            (GOOGLE_DRIVE_ERROR_CONNECTION, _workspace_id()),
        )
        connection.commit()
    message = _DummyMessage('/google_drive_status', ADMIN_ID)

    asyncio.run(cmd_google_drive_status(message, config))

    answer = message.answers[0]
    assert 'status: error' in answer
    assert GOOGLE_DRIVE_ERROR_CONNECTION in answer
    assert 'chybovy stav' in answer
    _assert_no_status_internals(answer)


def test_disconnect_marks_local_connection_disconnected_without_delete_or_google_api(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fail_delete(*args, **kwargs):
        raise AssertionError('delete must not be called')

    monkeypatch.setattr(Path, 'unlink', _fail_delete)
    monkeypatch.setattr(os, 'remove', _fail_delete)

    config = _config(tmp_path)
    init_db(config.db_path)
    service = _connection_service(config)
    service.create_or_update_connection(
        workspace_id=_workspace_id(),
        telegram_id=ADMIN_ID,
        scopes_granted=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_plaintext='safe-test-token',
        google_email='owner@example.test',
    )
    message = _DummyMessage('/google_drive_disconnect', ADMIN_ID)

    asyncio.run(cmd_google_drive_disconnect(message, config))

    record = service.get_connection_for_workspace(workspace_id=_workspace_id())
    assert message.answers == [GOOGLE_DRIVE_DISCONNECTED_MESSAGE]
    assert record is not None
    assert record.status == GOOGLE_DRIVE_STATUS_DISCONNECTED


def test_non_admin_cannot_disconnect(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    message = _DummyMessage('/google_drive_disconnect', USER_ID)

    asyncio.run(cmd_google_drive_disconnect(message, config))

    assert message.answers == [GOOGLE_DRIVE_ADMIN_ONLY_MESSAGE]


def test_google_drive_setup_commands_have_no_google_api_or_network_imports() -> None:
    source = inspect.getsource(settings)

    forbidden = ('googleapiclient', 'google.auth', 'requests', 'httpx', 'aiohttp', 'socket')

    assert not any(name in source for name in forbidden)


def test_google_drive_product_truth_is_partial_service_account_not_oauth() -> None:
    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Can bot save invoices to Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.PARTIAL
    assert result.capability.runtime_owner is not None
    assert answer is not None
