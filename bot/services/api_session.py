from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import secrets
import sqlite3

from bot.services.access_control import AUTHORIZED_STATUS_ACTIVE
from bot.services.db import managed_connection
from bot.services.principal_identity import IDENTITY_STATUS_ACTIVE, TELEGRAM_PROVIDER


DEFAULT_ACCESS_TTL = timedelta(minutes=15)
DEFAULT_REFRESH_TTL = timedelta(days=30)
MAX_CREDENTIAL_LENGTH = 160


class ApiSessionError(RuntimeError):
    pass


@dataclass(frozen=True)
class ApiSessionRecord:
    session_id: str
    principal_id: str
    device_label: str | None
    created_at: str
    last_seen_at: str | None
    access_expires_at: str
    refresh_expires_at: str
    revoked_at: str | None
    token_version: int


@dataclass(frozen=True)
class ApiSessionCredentials:
    access_token: str
    refresh_token: str
    access_expires_at: str
    refresh_expires_at: str
    device_label: str | None


class ApiSessionService:
    def __init__(
        self,
        db_path: Path,
        *,
        access_ttl: timedelta = DEFAULT_ACCESS_TTL,
        refresh_ttl: timedelta = DEFAULT_REFRESH_TTL,
    ) -> None:
        if access_ttl.total_seconds() <= 0 or refresh_ttl <= access_ttl:
            raise ValueError('api_session_ttl_invalid')
        self._db_path = db_path
        self._access_ttl = access_ttl
        self._refresh_ttl = refresh_ttl

    def create_session(
        self,
        *,
        principal_id: str,
        device_label: str | None,
    ) -> ApiSessionCredentials:
        with managed_connection(self._db_path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            _require_current_active_authorization(connection, principal_id)
            credentials = self.create_session_in_connection(
                connection,
                principal_id=principal_id,
                device_label=device_label,
            )
            connection.commit()
        return credentials

    def create_session_in_connection(
        self,
        connection: sqlite3.Connection,
        *,
        principal_id: str,
        device_label: str | None,
        now: datetime | None = None,
    ) -> ApiSessionCredentials:
        current = _utc_now(now)
        normalized_label = sanitize_device_label(device_label)
        access_token = _new_credential('ofacc')
        refresh_token = _new_credential('ofref')
        access_expires = current + self._access_ttl
        refresh_expires = current + self._refresh_ttl
        session_id = _opaque_id('ses')
        connection.execute(
            'INSERT INTO api_session '
            '(session_id, principal_id, access_token_hash, refresh_token_hash, '
            'device_label, created_at, last_seen_at, access_expires_at, '
            'refresh_expires_at, revoked_at, token_version) '
            'VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, 1)',
            (
                session_id,
                principal_id,
                hash_credential('access', access_token),
                hash_credential('refresh', refresh_token),
                normalized_label,
                current.isoformat(),
                access_expires.isoformat(),
                refresh_expires.isoformat(),
            ),
        )
        return ApiSessionCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires.isoformat(),
            refresh_expires_at=refresh_expires.isoformat(),
            device_label=normalized_label,
        )

    def authenticate_access(
        self,
        raw_access_token: str,
        *,
        now: datetime | None = None,
    ) -> ApiSessionRecord:
        token_hash = hash_credential('access', raw_access_token)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                _SESSION_SELECT + ' WHERE access_token_hash = ?',
                (token_hash,),
            ).fetchone()
        if row is None:
            raise ApiSessionError('api_access_invalid')
        record = _row_to_session(row)
        if record.revoked_at is not None or _parse_utc(record.access_expires_at) <= _utc_now(now):
            raise ApiSessionError('api_access_invalid')
        return record

    def rotate_refresh(
        self,
        raw_refresh_token: str,
        *,
        now: datetime | None = None,
    ) -> ApiSessionCredentials:
        old_hash = hash_credential('refresh', raw_refresh_token)
        current = _utc_now(now)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                _SESSION_SELECT + ' WHERE refresh_token_hash = ?',
                (old_hash,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise ApiSessionError('api_refresh_invalid')
            record = _row_to_session(row)
            if (
                record.revoked_at is not None
                or _parse_utc(record.refresh_expires_at) <= current
            ):
                connection.rollback()
                raise ApiSessionError('api_refresh_invalid')
            _require_current_active_authorization(connection, record.principal_id)

            access_token = _new_credential('ofacc')
            refresh_token = _new_credential('ofref')
            access_expires = current + self._access_ttl
            refresh_expires = current + self._refresh_ttl
            cursor = connection.execute(
                'UPDATE api_session SET access_token_hash = ?, refresh_token_hash = ?, '
                'last_seen_at = ?, access_expires_at = ?, refresh_expires_at = ?, '
                'token_version = token_version + 1 '
                'WHERE session_id = ? AND refresh_token_hash = ? '
                'AND revoked_at IS NULL AND token_version = ?',
                (
                    hash_credential('access', access_token),
                    hash_credential('refresh', refresh_token),
                    current.isoformat(),
                    access_expires.isoformat(),
                    refresh_expires.isoformat(),
                    record.session_id,
                    old_hash,
                    record.token_version,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ApiSessionError('api_refresh_invalid')
            connection.commit()
        return ApiSessionCredentials(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_expires.isoformat(),
            refresh_expires_at=refresh_expires.isoformat(),
            device_label=record.device_label,
        )

    def revoke_access(self, raw_access_token: str, *, now: datetime | None = None) -> None:
        token_hash = hash_credential('access', raw_access_token)
        current = _utc_now(now).isoformat()
        with managed_connection(self._db_path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            cursor = connection.execute(
                'UPDATE api_session SET revoked_at = ? '
                'WHERE access_token_hash = ? AND revoked_at IS NULL',
                (current, token_hash),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ApiSessionError('api_access_invalid')
            connection.commit()

    def touch_last_seen(
        self,
        *,
        session_id: str,
        now: datetime | None = None,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            cursor = connection.execute(
                'UPDATE api_session SET last_seen_at = ? '
                'WHERE session_id = ? AND revoked_at IS NULL',
                (_utc_now(now).isoformat(), session_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ApiSessionError('api_access_invalid')
            connection.commit()


def sanitize_device_label(value: str | None) -> str | None:
    if value is None:
        return None
    label = str(value).strip()
    if not label:
        return None
    if len(label) > 80 or any(c in label for c in '\r\n\x00'):
        raise ApiSessionError('device_label_invalid')
    return label


def hash_credential(kind: str, raw_value: str) -> str:
    value = str(raw_value)
    expected_prefix = {'access': 'ofacc_', 'refresh': 'ofref_', 'enrollment': 'ofenr_'}.get(kind)
    if (
        expected_prefix is None
        or not value.startswith(expected_prefix)
        or len(value) > MAX_CREDENTIAL_LENGTH
        or len(value) < len(expected_prefix) + 43
        or any(c in value for c in '\r\n\x00 ')
    ):
        raise ApiSessionError(f'api_{kind}_invalid')
    return hashlib.sha256(f'officeflow-{kind}-v1:{value}'.encode()).hexdigest()


def _require_current_active_authorization(
    connection: sqlite3.Connection,
    principal_id: str,
) -> int:
    rows = connection.execute(
        'SELECT e.subject FROM principal_external_identity e '
        'JOIN principal p ON p.principal_id = e.principal_id '
        'JOIN authorized_users a ON CAST(a.telegram_id AS TEXT) = e.subject '
        'WHERE e.principal_id = ? AND e.provider = ? AND e.status = ? '
        'AND a.status = ? ORDER BY e.identity_id LIMIT 2',
        (
            principal_id,
            TELEGRAM_PROVIDER,
            IDENTITY_STATUS_ACTIVE,
            AUTHORIZED_STATUS_ACTIVE,
        ),
    ).fetchall()
    if len(rows) != 1:
        raise ApiSessionError('api_principal_not_authorized')
    try:
        telegram_id = int(str(rows[0][0]))
    except ValueError as exc:
        raise ApiSessionError('api_principal_not_authorized') from exc
    if telegram_id <= 0:
        raise ApiSessionError('api_principal_not_authorized')
    return telegram_id


_SESSION_SELECT = (
    'SELECT session_id, principal_id, device_label, created_at, last_seen_at, '
    'access_expires_at, refresh_expires_at, revoked_at, token_version '
    'FROM api_session'
)


def _row_to_session(row: sqlite3.Row) -> ApiSessionRecord:
    return ApiSessionRecord(
        session_id=str(row['session_id']),
        principal_id=str(row['principal_id']),
        device_label=row['device_label'],
        created_at=str(row['created_at']),
        last_seen_at=row['last_seen_at'],
        access_expires_at=str(row['access_expires_at']),
        refresh_expires_at=str(row['refresh_expires_at']),
        revoked_at=row['revoked_at'],
        token_version=int(row['token_version']),
    )


def _new_credential(prefix: str) -> str:
    return f'{prefix}_{secrets.token_urlsafe(32)}'


def _opaque_id(prefix: str) -> str:
    return f'{prefix}_{secrets.token_urlsafe(24)}'


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_utc(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ApiSessionError('api_session_timestamp_invalid') from exc
    return _utc_now(parsed)
