from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import secrets
import sqlite3

from bot.services.access_control import (
    AUTHORIZED_STATUS_ACTIVE,
    AccessControlService,
)
from bot.services.api_session import (
    ApiSessionCredentials,
    ApiSessionError,
    ApiSessionService,
    hash_credential,
    sanitize_device_label,
)
from bot.services.db import managed_connection
from bot.services.principal_identity import PrincipalIdentityService


DEFAULT_ENROLLMENT_TTL = timedelta(minutes=30)
MAX_ENROLLMENT_TTL = timedelta(hours=24)


class ApiEnrollmentError(RuntimeError):
    pass


@dataclass(frozen=True)
class IssuedApiEnrollment:
    enrollment_id: str
    enrollment_secret: str
    expires_at: str
    device_label: str | None


@dataclass(frozen=True)
class ApiEnrollmentStatus:
    enrollment_id: str
    status: str
    device_label: str | None
    created_at: str
    expires_at: str
    consumed_at: str | None
    revoked_at: str | None


class ApiEnrollmentService:
    def __init__(
        self,
        db_path: Path,
        *,
        session_service: ApiSessionService | None = None,
    ) -> None:
        self._db_path = db_path
        self._session_service = session_service or ApiSessionService(db_path)

    def issue_for_authorized_telegram_user(
        self,
        *,
        telegram_id: int,
        ttl: timedelta = DEFAULT_ENROLLMENT_TTL,
        device_label: str | None = None,
        now: datetime | None = None,
    ) -> IssuedApiEnrollment:
        if ttl.total_seconds() <= 0 or ttl > MAX_ENROLLMENT_TTL:
            raise ApiEnrollmentError('api_enrollment_ttl_invalid')
        user = AccessControlService(self._db_path).get_authorized_user(telegram_id)
        if user is None or user.status != AUTHORIZED_STATUS_ACTIVE:
            raise ApiEnrollmentError('api_enrollment_target_not_authorized')

        current = _utc_now(now)
        expires_at = current + ttl
        label = sanitize_device_label(device_label)
        raw_secret = f'ofenr_{secrets.token_urlsafe(32)}'
        enrollment_id = _opaque_id('enr')
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            _require_active_telegram_user(connection, telegram_id)
            identity = PrincipalIdentityService.resolve_or_create_telegram_identity_in_connection(
                connection,
                telegram_id,
            )
            connection.execute(
                'INSERT INTO api_enrollment '
                '(enrollment_id, principal_id, secret_hash, status, device_label, '
                'created_at, expires_at, consumed_at, revoked_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL)',
                (
                    enrollment_id,
                    identity.principal_id,
                    hash_credential('enrollment', raw_secret),
                    'pending',
                    label,
                    current.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()
        return IssuedApiEnrollment(
            enrollment_id=enrollment_id,
            enrollment_secret=raw_secret,
            expires_at=expires_at.isoformat(),
            device_label=label,
        )

    def exchange(
        self,
        raw_secret: str,
        *,
        device_label: str | None = None,
        now: datetime | None = None,
    ) -> ApiSessionCredentials:
        try:
            secret_hash = hash_credential('enrollment', raw_secret)
            requested_label = sanitize_device_label(device_label)
        except ApiSessionError as exc:
            raise ApiEnrollmentError('api_enrollment_invalid') from exc
        current = _utc_now(now)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                'SELECT enrollment_id, principal_id, status, device_label, expires_at '
                'FROM api_enrollment WHERE secret_hash = ?',
                (secret_hash,),
            ).fetchone()
            if row is None or str(row['status']) != 'pending':
                connection.rollback()
                raise ApiEnrollmentError('api_enrollment_invalid')
            if _parse_utc(str(row['expires_at'])) <= current:
                connection.rollback()
                raise ApiEnrollmentError('api_enrollment_invalid')
            _require_active_principal(connection, str(row['principal_id']))
            issued_label = row['device_label']
            if issued_label and requested_label and str(issued_label) != requested_label:
                connection.rollback()
                raise ApiEnrollmentError('api_enrollment_invalid')
            label = str(issued_label) if issued_label else requested_label
            cursor = connection.execute(
                'UPDATE api_enrollment SET status = ?, consumed_at = ? '
                'WHERE enrollment_id = ? AND secret_hash = ? AND status = ?',
                (
                    'consumed',
                    current.isoformat(),
                    str(row['enrollment_id']),
                    secret_hash,
                    'pending',
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ApiEnrollmentError('api_enrollment_invalid')
            credentials = self._session_service.create_session_in_connection(
                connection,
                principal_id=str(row['principal_id']),
                device_label=label,
                now=current,
            )
            connection.commit()
        return credentials

    def revoke_outstanding(
        self,
        enrollment_id: str,
        *,
        now: datetime | None = None,
    ) -> None:
        normalized_id = _bounded_identifier(enrollment_id, field='enrollment_id')
        with managed_connection(self._db_path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            cursor = connection.execute(
                'UPDATE api_enrollment SET status = ?, revoked_at = ? '
                'WHERE enrollment_id = ? AND status = ?',
                ('revoked', _utc_now(now).isoformat(), normalized_id, 'pending'),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ApiEnrollmentError('api_enrollment_not_pending')
            connection.commit()

    @staticmethod
    def revoke_pending_for_principal_in_connection(
        connection: sqlite3.Connection,
        *,
        principal_id: str,
        now: datetime | None = None,
    ) -> int:
        """Revoke pending enrollment without owning the caller's transaction."""

        normalized_principal_id = _bounded_identifier(
            principal_id,
            field='principal_id',
        )
        return connection.execute(
            'UPDATE api_enrollment SET status = ?, revoked_at = ? '
            'WHERE principal_id = ? AND status = ?',
            (
                'revoked',
                _utc_now(now).isoformat(),
                normalized_principal_id,
                'pending',
            ),
        ).rowcount

    def list_status_for_telegram_user(
        self,
        telegram_id: int,
    ) -> list[ApiEnrollmentStatus]:
        identity = PrincipalIdentityService(self._db_path).resolve_telegram_identity(
            telegram_id
        )
        if identity is None:
            return []
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                'SELECT enrollment_id, status, device_label, created_at, expires_at, '
                'consumed_at, revoked_at FROM api_enrollment '
                'WHERE principal_id = ? ORDER BY created_at DESC',
                (identity.principal_id,),
            ).fetchall()
        return [
            ApiEnrollmentStatus(
                enrollment_id=str(row['enrollment_id']),
                status=str(row['status']),
                device_label=row['device_label'],
                created_at=str(row['created_at']),
                expires_at=str(row['expires_at']),
                consumed_at=row['consumed_at'],
                revoked_at=row['revoked_at'],
            )
            for row in rows
        ]


def _require_active_telegram_user(
    connection: sqlite3.Connection,
    telegram_id: int,
) -> None:
    row = connection.execute(
        'SELECT status FROM authorized_users WHERE telegram_id = ?',
        (telegram_id,),
    ).fetchone()
    if row is None or str(row[0]) != AUTHORIZED_STATUS_ACTIVE:
        raise ApiEnrollmentError('api_enrollment_target_not_authorized')


def _require_active_principal(
    connection: sqlite3.Connection,
    principal_id: str,
) -> None:
    rows = connection.execute(
        'SELECT e.subject FROM principal_external_identity e '
        'JOIN principal p ON p.principal_id = e.principal_id '
        'JOIN authorized_users a ON CAST(a.telegram_id AS TEXT) = e.subject '
        'WHERE e.principal_id = ? AND e.provider = ? AND e.status = ? '
        'AND a.status = ? LIMIT 2',
        (principal_id, 'telegram', 'active', AUTHORIZED_STATUS_ACTIVE),
    ).fetchall()
    if len(rows) != 1:
        raise ApiEnrollmentError('api_enrollment_target_not_authorized')


def _bounded_identifier(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if (
        not normalized
        or len(normalized) > 128
        or any(c in normalized for c in '\r\n\x00 ')
    ):
        raise ApiEnrollmentError(f'{field}_invalid')
    return normalized


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
        raise ApiEnrollmentError('api_enrollment_invalid') from exc
    return _utc_now(parsed)
