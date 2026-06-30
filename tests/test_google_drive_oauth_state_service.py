from __future__ import annotations

from datetime import UTC, datetime, timedelta
import hashlib
import inspect
from pathlib import Path
import sqlite3
from urllib.parse import parse_qs, urlparse

import pytest

from bot.services import google_drive_oauth_state_service
from bot.services.google_drive_oauth_state_service import (
    DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
    GOOGLE_DRIVE_OAUTH_ERROR_INVALID,
    GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    GOOGLE_DRIVE_OAUTH_ERROR_REUSED,
    GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN,
    GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED,
    GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED,
    GOOGLE_DRIVE_OAUTH_STATUS_PENDING,
    GOOGLE_DRIVE_OAUTH_STATUS_REJECTED,
    GoogleDriveOAuthStateService,
    GoogleDriveOAuthStateServiceError,
)
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import ProductTruthStatus, get_capability


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'google-drive-oauth-states.db'


def _service(tmp_path: Path) -> GoogleDriveOAuthStateService:
    return GoogleDriveOAuthStateService(_db_path(tmp_path))


def _create_state(
    service: GoogleDriveOAuthStateService,
    *,
    now: datetime | None = None,
):
    return service.create_oauth_state(
        workspace_id='telegram-111001',
        telegram_id=111001,
        scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        redirect_uri='https://officeflow.example.test/oauth/google/callback',
        now=now or datetime(2026, 5, 31, 10, 0, tzinfo=UTC),
        ttl_minutes=10,
    )


def test_google_drive_oauth_state_schema_bootstrap_is_idempotent(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service.ensure_schema()
    service.ensure_schema()

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert 'google_drive_oauth_states' in tables
    assert 'google_drive_connections' in tables
    assert 'google_drive_folder_cache' in tables


def test_create_state_stores_hash_not_raw_token(tmp_path: Path) -> None:
    created = _create_state(_service(tmp_path))

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            (
                'SELECT state_token_hash, status, scopes_requested, redirect_uri '
                'FROM google_drive_oauth_states WHERE state_id = ?'
            ),
            (created.record.state_id,),
        ).fetchone()

    assert created.raw_state_token
    assert row[0] != created.raw_state_token
    assert created.raw_state_token not in row[0]
    assert len(row[0]) == 64
    assert row[0] == hashlib.sha256(created.raw_state_token.encode('utf-8')).hexdigest()
    assert row[1] == GOOGLE_DRIVE_OAUTH_STATUS_PENDING
    assert row[2] == ' '.join(DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES)
    assert row[3] == 'https://officeflow.example.test/oauth/google/callback'
    assert created.raw_state_token not in repr(created)
    assert created.raw_state_token not in repr(created.record)


def test_authorization_url_contains_oauth_inputs_and_no_client_secret(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)

    url = service.build_authorization_url(
        client_id='google-client-id.apps.googleusercontent.com',
        redirect_uri='https://officeflow.example.test/oauth/google/callback',
        scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        state_token=created.raw_state_token,
    )
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    assert parsed.scheme == 'https'
    assert parsed.netloc == 'accounts.google.com'
    assert params['client_id'] == ['google-client-id.apps.googleusercontent.com']
    assert params['redirect_uri'] == ['https://officeflow.example.test/oauth/google/callback']
    assert params['response_type'] == ['code']
    assert params['state'] == [created.raw_state_token]
    assert params['access_type'] == ['offline']
    assert params['prompt'] == ['consent']
    assert params['scope'] == [' '.join(DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES)]
    assert 'client_secret' not in params


def test_consume_valid_pending_state_succeeds_once(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)
    now = datetime(2026, 5, 31, 10, 3, tzinfo=UTC)

    consumed = service.consume_oauth_state(raw_state_token=created.raw_state_token, now=now)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, consumed_at, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert consumed.state_id == created.record.state_id
    assert consumed.workspace_id == 'telegram-111001'
    assert consumed.telegram_id == 111001
    assert consumed.scopes_requested == DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES
    assert consumed.redirect_uri == 'https://officeflow.example.test/oauth/google/callback'
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED
    assert row[1] == now.isoformat()
    assert row[2] is None

    with pytest.raises(GoogleDriveOAuthStateServiceError, match=GOOGLE_DRIVE_OAUTH_ERROR_REUSED):
        service.consume_oauth_state(raw_state_token=created.raw_state_token, now=now)


def test_reused_state_is_rejected_with_bounded_error(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)
    now = datetime(2026, 5, 31, 10, 3, tzinfo=UTC)
    service.consume_oauth_state(raw_state_token=created.raw_state_token, now=now)

    with pytest.raises(GoogleDriveOAuthStateServiceError, match=GOOGLE_DRIVE_OAUTH_ERROR_REUSED):
        service.consume_oauth_state(raw_state_token=created.raw_state_token, now=now)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED
    assert row[1] == GOOGLE_DRIVE_OAUTH_ERROR_REUSED


def test_expired_state_is_rejected_and_marked_expired(tmp_path: Path) -> None:
    service = _service(tmp_path)
    start = datetime(2026, 5, 31, 10, 0, tzinfo=UTC)
    created = _create_state(service, now=start)

    with pytest.raises(GoogleDriveOAuthStateServiceError, match=GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED):
        service.consume_oauth_state(
            raw_state_token=created.raw_state_token,
            now=start + timedelta(minutes=11),
        )

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, consumed_at, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED
    assert row[1] is None
    assert row[2] == GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED


@pytest.mark.parametrize('bad_state', ['', 'wrong-state-token'])
def test_wrong_or_missing_state_is_rejected_with_bounded_error(
    tmp_path: Path,
    bad_state: str,
) -> None:
    service = _service(tmp_path)
    _create_state(service)

    with pytest.raises(GoogleDriveOAuthStateServiceError) as exc_info:
        service.consume_oauth_state(raw_state_token=bad_state)

    assert str(exc_info.value) in {GOOGLE_DRIVE_OAUTH_ERROR_INVALID, 'state_token_required'}
    if bad_state:
        assert bad_state not in str(exc_info.value)


def test_rejected_state_is_not_consumed(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)

    rejected = service.mark_oauth_state_rejected(raw_state_token=created.raw_state_token)

    with pytest.raises(GoogleDriveOAuthStateServiceError, match=GOOGLE_DRIVE_OAUTH_ERROR_REJECTED):
        service.consume_oauth_state(raw_state_token=created.raw_state_token)

    assert rejected.status == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert rejected.last_error_code == GOOGLE_DRIVE_OAUTH_ERROR_REJECTED


def test_pending_state_can_transition_to_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)

    rejected = service.mark_oauth_state_rejected(raw_state_token=created.raw_state_token)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, consumed_at, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert rejected.status == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert row[1] is None
    assert row[2] == GOOGLE_DRIVE_OAUTH_ERROR_REJECTED


def test_consumed_state_cannot_be_overwritten_to_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)
    consumed_at = datetime(2026, 5, 31, 10, 3, tzinfo=UTC)
    service.consume_oauth_state(raw_state_token=created.raw_state_token, now=consumed_at)

    result = service.mark_oauth_state_rejected(raw_state_token=created.raw_state_token)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, consumed_at, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert result.status == GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED
    assert row[1] == consumed_at.isoformat()
    assert row[2] is None


def test_expired_state_cannot_be_overwritten_to_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    start = datetime(2026, 5, 31, 10, 0, tzinfo=UTC)
    created = _create_state(service, now=start)
    with pytest.raises(GoogleDriveOAuthStateServiceError, match=GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED):
        service.consume_oauth_state(
            raw_state_token=created.raw_state_token,
            now=start + timedelta(minutes=11),
        )

    result = service.mark_oauth_state_rejected(raw_state_token=created.raw_state_token)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT status, consumed_at, last_error_code FROM google_drive_oauth_states WHERE state_id = ?',
            (created.record.state_id,),
        ).fetchone()

    assert result.status == GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED
    assert row[0] == GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED
    assert row[1] is None
    assert row[2] == GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED


def test_rejected_state_reject_call_is_deterministic_noop(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_state(service)
    first = service.mark_oauth_state_rejected(raw_state_token=created.raw_state_token)

    second = service.mark_oauth_state_rejected(raw_state_token=created.raw_state_token)

    assert first == second
    assert second.status == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert second.last_error_code == GOOGLE_DRIVE_OAUTH_ERROR_REJECTED


@pytest.mark.parametrize('bad_state', ['', 'wrong-state-token'])
def test_reject_wrong_or_missing_state_is_safe(
    tmp_path: Path,
    bad_state: str,
) -> None:
    service = _service(tmp_path)
    _create_state(service)

    with pytest.raises(GoogleDriveOAuthStateServiceError) as exc_info:
        service.mark_oauth_state_rejected(raw_state_token=bad_state)

    assert str(exc_info.value) in {GOOGLE_DRIVE_OAUTH_ERROR_INVALID, 'state_token_required'}
    if bad_state:
        assert bad_state not in str(exc_info.value)


@pytest.mark.parametrize(
    'raw_error_code',
    [
        'https://accounts.google.com/o/oauth2/v2/auth?code=secret',
        '4/0AfJohXn-auth-code-like-value',
        'ya29.a0AfH6SMB-access-token-like-value',
        '{"error":"invalid_grant","error_description":"Bad Request"}',
    ],
)
def test_rejected_state_normalizes_raw_error_codes(
    tmp_path: Path,
    raw_error_code: str,
) -> None:
    service = _service(tmp_path)
    created = _create_state(service)

    rejected = service.mark_oauth_state_rejected(
        raw_state_token=created.raw_state_token,
        error_code=raw_error_code,
    )

    assert rejected.status == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED
    assert rejected.last_error_code == GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN
    assert raw_error_code not in repr(rejected)


def test_create_state_rejects_missing_required_fields(tmp_path: Path) -> None:
    service = _service(tmp_path)

    with pytest.raises(GoogleDriveOAuthStateServiceError, match='workspace_id_required'):
        service.create_oauth_state(
            workspace_id='',
            telegram_id=111001,
            scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
            redirect_uri='https://officeflow.example.test/oauth/google/callback',
        )
    with pytest.raises(GoogleDriveOAuthStateServiceError, match='telegram_id_required'):
        service.create_oauth_state(
            workspace_id='telegram-111001',
            telegram_id=0,
            scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
            redirect_uri='https://officeflow.example.test/oauth/google/callback',
        )
    with pytest.raises(GoogleDriveOAuthStateServiceError, match='scopes_required'):
        service.create_oauth_state(
            workspace_id='telegram-111001',
            telegram_id=111001,
            scopes=[],
            redirect_uri='https://officeflow.example.test/oauth/google/callback',
        )
    with pytest.raises(GoogleDriveOAuthStateServiceError, match='redirect_uri_invalid'):
        service.create_oauth_state(
            workspace_id='telegram-111001',
            telegram_id=111001,
            scopes=DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
            redirect_uri='ftp://example.test/callback',
        )


def test_oauth_state_service_has_no_google_or_network_imports() -> None:
    source = inspect.getsource(google_drive_oauth_state_service)

    forbidden = ('googleapiclient', 'google.auth', 'requests', 'httpx', 'aiohttp', 'socket')

    assert not any(name in source for name in forbidden)


def test_google_drive_product_truth_is_partial_service_account_not_oauth() -> None:
    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Can bot save invoices to Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.PARTIAL
    assert result.capability.runtime_owner is not None
    assert answer is not None
