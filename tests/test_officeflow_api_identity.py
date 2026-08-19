from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import json
import sqlite3

import pytest

from bot.services.access_control import AccessControlService
from bot.cli.officeflow_api_access import main as api_access_cli_main
from bot.services.api_enrollment import ApiEnrollmentError, ApiEnrollmentService
from bot.services.api_session import ApiSessionError, ApiSessionService
from bot.services.db import init_db
from bot.services.officeflow_api_context import (
    OfficeFlowApiAuthorizationError,
    OfficeFlowApiContextService,
)
from bot.services.principal_identity import PrincipalIdentityError, PrincipalIdentityService


USER_ID = 750_001
OTHER_USER_ID = 750_002
ADMIN_ID = 750_999


def _active_db(tmp_path: Path) -> Path:
    db_path = tmp_path / 'officeflow.db'
    init_db(db_path)
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=ADMIN_ID,
        role='owner',
    )
    return db_path


def _table_values(db_path: Path, table: str) -> list[tuple[object, ...]]:
    with sqlite3.connect(db_path) as connection:
        return connection.execute(f'SELECT * FROM {table} ORDER BY rowid').fetchall()


def test_enrollment_lazily_creates_and_reuses_one_telegram_principal(
    tmp_path: Path,
) -> None:
    db_path = _active_db(tmp_path)
    service = ApiEnrollmentService(db_path)
    with sqlite3.connect(db_path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM principal').fetchone()[0] == 0

    first = service.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    second = service.issue_for_authorized_telegram_user(telegram_id=USER_ID)

    with sqlite3.connect(db_path) as connection:
        principal_count = connection.execute('SELECT COUNT(*) FROM principal').fetchone()[0]
        identities = connection.execute(
            'SELECT principal_id, provider, subject FROM principal_external_identity'
        ).fetchall()
    assert principal_count == 1
    assert len(identities) == 1
    assert identities[0][1:] == ('telegram', str(USER_ID))
    assert first.enrollment_secret != second.enrollment_secret


def test_external_provider_subject_is_unique_and_conflict_fails_closed(
    tmp_path: Path,
) -> None:
    db_path = _active_db(tmp_path)
    service = ApiEnrollmentService(db_path)
    service.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    original = PrincipalIdentityService(db_path).resolve_telegram_identity(USER_ID)
    assert original is not None
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO principal (principal_id, created_at, updated_at) '
            "VALUES ('prn_other', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()

    with pytest.raises(PrincipalIdentityError, match='external_identity_conflict'):
        PrincipalIdentityService(db_path).bind_external_identity(
            principal_id='prn_other',
            provider='telegram',
            subject=str(USER_ID),
        )

    assert PrincipalIdentityService(db_path).resolve_telegram_identity(USER_ID) == original


@pytest.mark.parametrize('access_state', ['blocked', 'deleted_database'])
def test_inactive_user_cannot_issue_or_exchange_enrollment(
    tmp_path: Path,
    access_state: str,
) -> None:
    db_path = _active_db(tmp_path)
    service = ApiEnrollmentService(db_path)
    issued = service.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    access = AccessControlService(db_path)
    if access_state == 'blocked':
        access.block_user(telegram_id=USER_ID, decided_by=ADMIN_ID)
    else:
        access.mark_deleted_database(telegram_id=USER_ID)

    with pytest.raises(ApiEnrollmentError):
        service.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    with pytest.raises(ApiEnrollmentError):
        service.exchange(issued.enrollment_secret)
    assert _table_values(db_path, 'api_session') == []


def test_enrollment_is_hashed_one_time_and_replay_fails(tmp_path: Path) -> None:
    db_path = _active_db(tmp_path)
    service = ApiEnrollmentService(db_path)
    business_tables = (
        'authorized_users',
        'workspace',
        'workspace_membership',
        'active_workspace_selection',
        'supplier',
        'contact',
        'invoice',
        'invoice_item',
    )
    before_business = {
        table: _table_values(db_path, table) for table in business_tables
    }
    issued = service.issue_for_authorized_telegram_user(
        telegram_id=USER_ID,
        device_label='Pixel pilot',
    )

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            'SELECT secret_hash FROM api_enrollment WHERE enrollment_id = ?',
            (issued.enrollment_id,),
        ).fetchone()
        database_dump = '\n'.join(connection.iterdump())
    assert row is not None and len(row[0]) == 64
    assert issued.enrollment_secret not in database_dump

    credentials = service.exchange(issued.enrollment_secret)
    assert credentials.device_label == 'Pixel pilot'
    with pytest.raises(ApiEnrollmentError):
        service.exchange(issued.enrollment_secret)
    with pytest.raises(ApiEnrollmentError):
        service.exchange('ofenr_' + ('x' * 43))
    assert len(_table_values(db_path, 'api_session')) == 1
    assert {
        table: _table_values(db_path, table) for table in business_tables
    } == before_business


def test_expired_and_revoked_enrollment_fail_without_session(tmp_path: Path) -> None:
    db_path = _active_db(tmp_path)
    service = ApiEnrollmentService(db_path)
    past = datetime(2026, 1, 1, tzinfo=UTC)
    expired = service.issue_for_authorized_telegram_user(
        telegram_id=USER_ID,
        ttl=timedelta(seconds=1),
        now=past,
    )
    with pytest.raises(ApiEnrollmentError):
        service.exchange(expired.enrollment_secret, now=past + timedelta(seconds=2))

    revoked = service.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    service.revoke_outstanding(revoked.enrollment_id)
    with pytest.raises(ApiEnrollmentError):
        service.exchange(revoked.enrollment_secret)
    assert _table_values(db_path, 'api_session') == []


def test_concurrent_enrollment_consumption_creates_exactly_one_session(
    tmp_path: Path,
) -> None:
    db_path = _active_db(tmp_path)
    issued = ApiEnrollmentService(db_path).issue_for_authorized_telegram_user(
        telegram_id=USER_ID
    )

    def consume() -> bool:
        try:
            ApiEnrollmentService(db_path).exchange(issued.enrollment_secret)
            return True
        except ApiEnrollmentError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: consume(), range(2)))

    assert sorted(results) == [False, True]
    assert len(_table_values(db_path, 'api_session')) == 1


def test_access_expiry_refresh_rotation_restart_revoke_and_replay(
    tmp_path: Path,
) -> None:
    db_path = _active_db(tmp_path)
    issued_at = datetime(2026, 8, 19, 12, 0, tzinfo=UTC)
    sessions = ApiSessionService(
        db_path,
        access_ttl=timedelta(minutes=5),
        refresh_ttl=timedelta(hours=1),
    )
    enrollment = ApiEnrollmentService(db_path, session_service=sessions)
    issued = enrollment.issue_for_authorized_telegram_user(
        telegram_id=USER_ID,
        now=issued_at,
    )
    credentials = enrollment.exchange(issued.enrollment_secret, now=issued_at)

    restarted = ApiSessionService(
        db_path,
        access_ttl=timedelta(minutes=5),
        refresh_ttl=timedelta(hours=1),
    )
    assert restarted.authenticate_access(credentials.access_token, now=issued_at).principal_id
    with pytest.raises(ApiSessionError):
        restarted.authenticate_access(
            credentials.access_token,
            now=issued_at + timedelta(minutes=6),
        )

    rotated = restarted.rotate_refresh(
        credentials.refresh_token,
        now=issued_at + timedelta(minutes=6),
    )
    with pytest.raises(ApiSessionError):
        restarted.rotate_refresh(credentials.refresh_token, now=issued_at + timedelta(minutes=7))
    with pytest.raises(ApiSessionError):
        restarted.authenticate_access(credentials.access_token, now=issued_at + timedelta(minutes=7))
    active_record = restarted.authenticate_access(
        rotated.access_token,
        now=issued_at + timedelta(minutes=7),
    )

    restarted.revoke_access(rotated.access_token, now=issued_at + timedelta(minutes=8))
    with pytest.raises(ApiSessionError):
        restarted.authenticate_access(rotated.access_token, now=issued_at + timedelta(minutes=8))
    with pytest.raises(ApiSessionError):
        restarted.rotate_refresh(rotated.refresh_token, now=issued_at + timedelta(minutes=8))
    with pytest.raises(ApiSessionError):
        restarted.touch_last_seen(
            session_id=active_record.session_id,
            now=issued_at + timedelta(minutes=8),
        )


def test_concurrent_refresh_fails_closed(tmp_path: Path) -> None:
    db_path = _active_db(tmp_path)
    enrollment = ApiEnrollmentService(db_path)
    issued = enrollment.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    credentials = enrollment.exchange(issued.enrollment_secret)

    def rotate() -> bool:
        try:
            ApiSessionService(db_path).rotate_refresh(credentials.refresh_token)
            return True
        except ApiSessionError:
            return False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: rotate(), range(2)))
    assert sorted(results) == [False, True]
    assert len(_table_values(db_path, 'api_session')) == 1


@pytest.mark.parametrize('access_state', ['blocked', 'deleted_database'])
def test_current_access_revocation_invalidates_existing_session(
    tmp_path: Path,
    access_state: str,
) -> None:
    db_path = _active_db(tmp_path)
    enrollment = ApiEnrollmentService(db_path)
    issued = enrollment.issue_for_authorized_telegram_user(telegram_id=USER_ID)
    credentials = enrollment.exchange(issued.enrollment_secret)
    access = AccessControlService(db_path)
    if access_state == 'blocked':
        access.block_user(telegram_id=USER_ID, decided_by=ADMIN_ID)
    else:
        access.mark_deleted_database(telegram_id=USER_ID)

    with pytest.raises(ApiSessionError):
        ApiSessionService(db_path).rotate_refresh(credentials.refresh_token)


def test_temporary_block_denies_without_terminalizing_session(
    tmp_path: Path,
) -> None:
    db_path = _active_db(tmp_path)
    issue = ApiEnrollmentService(db_path).issue_for_authorized_telegram_user(
        telegram_id=USER_ID,
        device_label='Temporary block device',
    )
    credentials = ApiEnrollmentService(db_path).exchange(issue.enrollment_secret)
    context = OfficeFlowApiContextService(db_path)
    assert context.authenticate_access(credentials.access_token).telegram_id == USER_ID

    access = AccessControlService(db_path)
    access.block_user(telegram_id=USER_ID, decided_by=ADMIN_ID)
    with pytest.raises(OfficeFlowApiAuthorizationError):
        context.authenticate_access(credentials.access_token)
    listed = ApiSessionService(db_path).list_sessions_for_telegram_user(USER_ID)
    assert len(listed) == 1
    assert listed[0].status == 'active'
    assert listed[0].revoked_at is None

    access.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID, role='owner')
    assert context.authenticate_access(credentials.access_token).telegram_id == USER_ID


def test_admin_session_list_and_revoke_are_target_scoped_and_secret_free(
    tmp_path: Path,
) -> None:
    db_path = _active_db(tmp_path)
    AccessControlService(db_path).approve_user(
        telegram_id=OTHER_USER_ID,
        approved_by=ADMIN_ID,
        role='user',
    )
    enrollment = ApiEnrollmentService(db_path)

    first_issue = enrollment.issue_for_authorized_telegram_user(
        telegram_id=USER_ID,
        device_label='Lost phone',
    )
    first = enrollment.exchange(first_issue.enrollment_secret)
    second_issue = enrollment.issue_for_authorized_telegram_user(
        telegram_id=USER_ID,
        device_label='Kept phone',
    )
    second = enrollment.exchange(second_issue.enrollment_secret)
    other_issue = enrollment.issue_for_authorized_telegram_user(
        telegram_id=OTHER_USER_ID,
        device_label='Other tenant phone',
    )
    other = enrollment.exchange(other_issue.enrollment_secret)
    sessions = ApiSessionService(db_path)

    listed = sessions.list_sessions_for_telegram_user(USER_ID)
    serialized = json.dumps([record.__dict__ for record in listed])
    assert [record.device_label for record in listed] == ['Kept phone', 'Lost phone']
    assert all(record.status == 'active' for record in listed)
    for forbidden in (
        'principal_id',
        'access_token',
        'refresh_token',
        'access_token_hash',
        'refresh_token_hash',
        first.access_token,
        first.refresh_token,
        other.access_token,
    ):
        assert forbidden not in serialized

    lost_session_id = next(
        record.session_id for record in listed if record.device_label == 'Lost phone'
    )
    kept_session_id = next(
        record.session_id for record in listed if record.device_label == 'Kept phone'
    )
    revoked = sessions.revoke_session_for_telegram_user(
        telegram_id=USER_ID,
        session_id=lost_session_id,
    )
    repeated = sessions.revoke_session_for_telegram_user(
        telegram_id=USER_ID,
        session_id=lost_session_id,
    )
    assert revoked.status == repeated.status == 'revoked'
    assert revoked.revoked_at == repeated.revoked_at
    with pytest.raises(ApiSessionError):
        sessions.authenticate_access(first.access_token)
    with pytest.raises(ApiSessionError):
        sessions.rotate_refresh(first.refresh_token)
    assert sessions.authenticate_access(second.access_token)
    assert sessions.authenticate_access(other.access_token)

    with pytest.raises(ApiSessionError, match='api_session_not_found'):
        sessions.revoke_session_for_telegram_user(
            telegram_id=OTHER_USER_ID,
            session_id=kept_session_id,
        )
    assert sessions.authenticate_access(second.access_token)

    AccessControlService(db_path).block_user(
        telegram_id=USER_ID,
        decided_by=ADMIN_ID,
    )
    blocked_target = sessions.revoke_session_for_telegram_user(
        telegram_id=USER_ID,
        session_id=kept_session_id,
    )
    assert blocked_target.status == 'revoked'
    assert [record.device_label for record in sessions.list_sessions_for_telegram_user(OTHER_USER_ID)] == [
        'Other tenant phone'
    ]


def test_admin_cli_issues_once_lists_safely_and_revokes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path = _active_db(tmp_path)
    monkeypatch.setenv('DB_PATH', str(db_path))

    assert api_access_cli_main(
        [
            'issue',
            '--telegram-id',
            str(USER_ID),
            '--device-label',
            'Pilot device',
        ]
    ) == 0
    issued = json.loads(capsys.readouterr().out)
    raw_secret = issued['enrollment_secret']
    assert raw_secret.startswith('ofenr_')

    assert api_access_cli_main(['status', '--telegram-id', str(USER_ID)]) == 0
    status_output = capsys.readouterr().out
    status = json.loads(status_output)
    assert status['enrollments'][0]['enrollment_id'] == issued['enrollment_id']
    assert raw_secret not in status_output
    assert 'secret_hash' not in status_output
    assert 'principal_id' not in status_output

    credentials = ApiEnrollmentService(db_path).exchange(raw_secret)
    assert api_access_cli_main(['sessions', '--telegram-id', str(USER_ID)]) == 0
    sessions_output = capsys.readouterr().out
    sessions = json.loads(sessions_output)['sessions']
    assert len(sessions) == 1
    assert sessions[0]['device_label'] == 'Pilot device'
    assert sessions[0]['status'] == 'active'
    assert sessions[0]['session_id'].startswith('ses_')
    for forbidden in (
        'principal_id',
        'access_token',
        'refresh_token',
        'hash',
        credentials.access_token,
        credentials.refresh_token,
    ):
        assert forbidden not in sessions_output

    assert api_access_cli_main(
        [
            'revoke-session',
            '--telegram-id',
            str(USER_ID),
            '--session-id',
            sessions[0]['session_id'],
        ]
    ) == 0
    revoked_session_output = capsys.readouterr().out
    revoked_session = json.loads(revoked_session_output)
    assert revoked_session['session_id'] == sessions[0]['session_id']
    assert revoked_session['status'] == 'revoked'
    assert 'principal_id' not in revoked_session_output
    assert 'token' not in revoked_session_output
    with pytest.raises(ApiSessionError):
        ApiSessionService(db_path).authenticate_access(credentials.access_token)

    outstanding = ApiEnrollmentService(db_path).issue_for_authorized_telegram_user(
        telegram_id=USER_ID
    )
    assert api_access_cli_main(
        ['revoke-enrollment', '--enrollment-id', outstanding.enrollment_id]
    ) == 0
    revoked = json.loads(capsys.readouterr().out)
    assert revoked == {
        'enrollment_id': outstanding.enrollment_id,
        'status': 'revoked',
    }
    with pytest.raises(ApiEnrollmentError):
        ApiEnrollmentService(db_path).exchange(outstanding.enrollment_secret)
