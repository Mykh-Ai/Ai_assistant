from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import inspect
import json
from pathlib import Path
import sqlite3

import pytest

from bot.services import google_drive_oauth_callback_service
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
    GOOGLE_DRIVE_ERROR_SCOPE_MISSING,
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GoogleDriveConnectionService,
)
from bot.services.google_drive_oauth_callback_service import (
    GOOGLE_DRIVE_CALLBACK_ERROR_MISSING_CODE,
    GoogleDriveOAuthCallbackService,
    GoogleOAuthInvalidGrantError,
    GoogleOAuthProviderError,
    GoogleOAuthTokenBundle,
)
from bot.services.google_drive_oauth_state_service import (
    DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
    GOOGLE_DRIVE_OAUTH_ERROR_INVALID,
    GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    GOOGLE_DRIVE_OAUTH_ERROR_REUSED,
    GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED,
    GOOGLE_DRIVE_OAUTH_STATUS_REJECTED,
    GoogleDriveOAuthStateService,
)
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import ProductTruthStatus, get_capability
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


AUTH_CODE = '4/0AfJohXn-raw-auth-code-secret'
STATE_NOW = datetime(2026, 5, 31, 10, 0, tzinfo=UTC)
CALLBACK_NOW = datetime(2026, 5, 31, 10, 3, tzinfo=UTC)
REDIRECT_URI = 'https://officeflow.example.test/oauth/google/callback'


@dataclass
class FakeTokenExchanger:
    bundle: GoogleOAuthTokenBundle | None = None
    exception: Exception | None = None
    calls: int = 0
    seen_codes: list[str] | None = None

    def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        scopes: tuple[str, ...],
    ) -> GoogleOAuthTokenBundle:
        self.calls += 1
        if self.seen_codes is None:
            self.seen_codes = []
        self.seen_codes.append(code)
        assert redirect_uri == REDIRECT_URI
        assert scopes == DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES
        if self.exception is not None:
            raise self.exception
        assert self.bundle is not None
        return self.bundle


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'google-drive-oauth-callback.db'


def _crypto() -> DeterministicFakeTokenCryptoProvider:
    return DeterministicFakeTokenCryptoProvider(key_id='test-key')


def _default_bundle(
    *,
    refresh_token: str | None = 'refresh-token-secret',
    scopes: tuple[str, ...] = DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
) -> GoogleOAuthTokenBundle:
    return GoogleOAuthTokenBundle(
        access_token='access-token-secret',
        refresh_token=refresh_token,
        expires_at='2026-05-31T11:00:00+00:00',
        scope=scopes,
        token_type='Bearer',
        id_token='id-token-secret',
        google_subject='google-subject-1',
        google_email='USER@Example.COM',
    )


def _create_state(tmp_path: Path, *, now: datetime = STATE_NOW):
    state_service = GoogleDriveOAuthStateService(_db_path(tmp_path))
    return state_service.create_oauth_state(
        workspace_id='telegram-111001',
        telegram_id=111001,
        scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        redirect_uri=REDIRECT_URI,
        now=now,
        ttl_minutes=10,
    )


def _callback_service(
    tmp_path: Path,
    exchanger: FakeTokenExchanger,
) -> GoogleDriveOAuthCallbackService:
    return GoogleDriveOAuthCallbackService(
        db_path=_db_path(tmp_path),
        crypto_provider=_crypto(),
        token_exchanger=exchanger,
    )


def _all_db_values(tmp_path: Path) -> str:
    chunks: list[str] = []
    with sqlite3.connect(_db_path(tmp_path)) as connection:
        for table in ('google_drive_oauth_states', 'google_drive_connections'):
            rows = connection.execute(f'SELECT * FROM {table}').fetchall()
            for row in rows:
                for value in row:
                    if isinstance(value, bytes):
                        chunks.append(value.decode('utf-8', errors='ignore'))
                    else:
                        chunks.append(str(value))
    return '\n'.join(chunks)


def test_valid_state_and_code_store_connected_encrypted_connection(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(bundle=_default_bundle())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    connection_service = GoogleDriveConnectionService(_db_path(tmp_path), _crypto())
    record = connection_service.get_connection_for_workspace(workspace_id='telegram-111001')
    decrypted = connection_service.decrypt_token_for_workspace(workspace_id='telegram-111001')
    decrypted_payload = json.loads(decrypted.decode('utf-8'))

    assert result.success is True
    assert result.workspace_id == 'telegram-111001'
    assert result.telegram_id == 111001
    assert result.google_email == 'user@example.com'
    assert record is not None
    assert record.status == GOOGLE_DRIVE_STATUS_CONNECTED
    assert record.google_subject == 'google-subject-1'
    assert record.google_email == 'user@example.com'
    assert record.scopes_granted == DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES
    assert record.connected_at == CALLBACK_NOW.isoformat()
    assert decrypted_payload['refresh_token'] == 'refresh-token-secret'
    assert decrypted_payload['access_token'] == 'access-token-secret'
    assert decrypted_payload['id_token'] == 'id-token-secret'


def test_exchanger_called_once_and_state_consumed_once(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(bundle=_default_bundle())
    service = _callback_service(tmp_path, exchanger)

    first = service.handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )
    second = service.handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, consumed_at, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert first.success is True
    assert second.success is False
    assert second.error_code == GOOGLE_DRIVE_OAUTH_ERROR_REUSED
    assert exchanger.calls == 1
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED
    assert row[1] == CALLBACK_NOW.isoformat()
    assert row[2] == GOOGLE_DRIVE_OAUTH_ERROR_REUSED


def test_expired_state_rejected_and_exchanger_not_called(tmp_path: Path) -> None:
    created = _create_state(tmp_path, now=STATE_NOW)
    exchanger = FakeTokenExchanger(bundle=_default_bundle())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=STATE_NOW + timedelta(minutes=11),
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED
    assert exchanger.calls == 0


def test_wrong_state_rejected_and_exchanger_not_called(tmp_path: Path) -> None:
    _create_state(tmp_path)
    exchanger = FakeTokenExchanger(bundle=_default_bundle())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token='wrong-state-secret',
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_OAUTH_ERROR_INVALID
    assert exchanger.calls == 0


def test_missing_code_rejects_state_and_exchanger_not_called(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(bundle=_default_bundle())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code='',
        now=CALLBACK_NOW,
    )

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert result.success is False
    assert result.workspace_id == 'telegram-111001'
    assert result.telegram_id == 111001
    assert result.error_code == GOOGLE_DRIVE_CALLBACK_ERROR_MISSING_CODE
    assert exchanger.calls == 0
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert row[1] == 'drive_unknown_error'


def test_rejected_state_is_not_exchanged(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    GoogleDriveOAuthStateService(_db_path(tmp_path)).mark_oauth_state_rejected(
        raw_state_token=created.raw_state_token,
    )
    exchanger = FakeTokenExchanger(bundle=_default_bundle())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_OAUTH_ERROR_REJECTED
    assert exchanger.calls == 0


def test_missing_refresh_token_fails_with_needs_reauth(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(bundle=_default_bundle(refresh_token=None))

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_ERROR_NEEDS_REAUTH
    assert exchanger.calls == 1
    assert GoogleDriveConnectionService(
        _db_path(tmp_path),
        _crypto(),
    ).get_connection_for_workspace(workspace_id='telegram-111001') is None


def test_missing_required_scope_fails_with_scope_missing(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(
        bundle=_default_bundle(scopes=('openid', 'email', 'profile')),
    )

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_ERROR_SCOPE_MISSING
    assert exchanger.calls == 1


def test_invalid_grant_maps_to_auth_revoked(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(exception=GoogleOAuthInvalidGrantError())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_ERROR_AUTH_REVOKED
    assert exchanger.calls == 1


def test_provider_error_maps_to_connection_error(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(exception=GoogleOAuthProviderError())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert result.success is False
    assert result.error_code == GOOGLE_DRIVE_ERROR_CONNECTION
    assert exchanger.calls == 1


def test_plaintext_tokens_code_and_state_do_not_appear_in_db(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    exchanger = FakeTokenExchanger(bundle=_default_bundle())

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )
    db_values = _all_db_values(tmp_path)

    assert result.success is True
    assert 'access-token-secret' not in db_values
    assert 'refresh-token-secret' not in db_values
    assert 'id-token-secret' not in db_values
    assert AUTH_CODE not in db_values
    assert created.raw_state_token not in db_values


def test_result_and_token_bundle_repr_do_not_expose_secrets(tmp_path: Path) -> None:
    created = _create_state(tmp_path)
    bundle = _default_bundle()
    exchanger = FakeTokenExchanger(bundle=bundle)

    result = _callback_service(tmp_path, exchanger).handle_callback(
        state_token=created.raw_state_token,
        code=AUTH_CODE,
        now=CALLBACK_NOW,
    )

    assert AUTH_CODE not in repr(result)
    assert created.raw_state_token not in repr(result)
    assert 'access-token-secret' not in repr(result)
    assert 'refresh-token-secret' not in repr(result)
    assert 'id-token-secret' not in repr(result)
    assert 'access-token-secret' not in repr(bundle)
    assert 'refresh-token-secret' not in repr(bundle)
    assert 'id-token-secret' not in repr(bundle)


def test_oauth_callback_service_has_no_google_or_network_imports() -> None:
    source = inspect.getsource(google_drive_oauth_callback_service)

    forbidden = ('googleapiclient', 'google.auth', 'requests', 'httpx', 'aiohttp', 'socket')

    assert not any(name in source for name in forbidden)


def test_google_drive_product_truth_stays_unsupported() -> None:
    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Can bot save invoices to Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.UNSUPPORTED
    assert result.capability.runtime_owner is None
    assert answer is not None
