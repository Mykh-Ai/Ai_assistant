from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import secrets
import sqlite3

from bot.services.db import managed_connection


TELEGRAM_PROVIDER = 'telegram'
IDENTITY_STATUS_ACTIVE = 'active'


class PrincipalIdentityError(RuntimeError):
    pass


@dataclass(frozen=True)
class PrincipalExternalIdentity:
    identity_id: str
    principal_id: str
    provider: str
    subject: str
    status: str
    created_at: str


class PrincipalIdentityService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def resolve_telegram_identity(
        self,
        telegram_id: int,
    ) -> PrincipalExternalIdentity | None:
        subject = _telegram_subject(telegram_id)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                _IDENTITY_SELECT
                + ' WHERE e.provider = ? AND e.subject = ?',
                (TELEGRAM_PROVIDER, subject),
            ).fetchone()
        return _row_to_identity(row) if row is not None else None

    def resolve_or_create_telegram_identity(
        self,
        telegram_id: int,
    ) -> PrincipalExternalIdentity:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            identity = self.resolve_or_create_telegram_identity_in_connection(
                connection,
                telegram_id,
            )
            connection.commit()
        return identity

    def bind_external_identity(
        self,
        *,
        principal_id: str,
        provider: str,
        subject: str,
    ) -> PrincipalExternalIdentity:
        normalized_provider = _bounded_identity_value(provider, field='provider')
        normalized_subject = _bounded_identity_value(subject, field='subject')
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            principal = connection.execute(
                'SELECT principal_id FROM principal WHERE principal_id = ?',
                (principal_id,),
            ).fetchone()
            if principal is None:
                connection.rollback()
                raise PrincipalIdentityError('principal_not_found')
            existing = connection.execute(
                _IDENTITY_SELECT
                + ' WHERE e.provider = ? AND e.subject = ?',
                (normalized_provider, normalized_subject),
            ).fetchone()
            if existing is not None:
                if str(existing['principal_id']) != principal_id:
                    connection.rollback()
                    raise PrincipalIdentityError('external_identity_conflict')
                connection.commit()
                return _row_to_identity(existing)
            now = _utc_now_text()
            identity_id = _opaque_id('pidn')
            connection.execute(
                'INSERT INTO principal_external_identity '
                '(identity_id, principal_id, provider, subject, status, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    identity_id,
                    principal_id,
                    normalized_provider,
                    normalized_subject,
                    IDENTITY_STATUS_ACTIVE,
                    now,
                ),
            )
            connection.commit()
        return PrincipalExternalIdentity(
            identity_id=identity_id,
            principal_id=principal_id,
            provider=normalized_provider,
            subject=normalized_subject,
            status=IDENTITY_STATUS_ACTIVE,
            created_at=now,
        )

    @staticmethod
    def resolve_or_create_telegram_identity_in_connection(
        connection: sqlite3.Connection,
        telegram_id: int,
    ) -> PrincipalExternalIdentity:
        subject = _telegram_subject(telegram_id)
        connection.row_factory = sqlite3.Row
        existing = connection.execute(
            _IDENTITY_SELECT + ' WHERE e.provider = ? AND e.subject = ?',
            (TELEGRAM_PROVIDER, subject),
        ).fetchone()
        if existing is not None:
            identity = _row_to_identity(existing)
            if identity.status != IDENTITY_STATUS_ACTIVE:
                raise PrincipalIdentityError('external_identity_inactive')
            return identity

        now = _utc_now_text()
        principal_id = _opaque_id('prn')
        identity_id = _opaque_id('pidn')
        connection.execute(
            'INSERT INTO principal (principal_id, created_at, updated_at) '
            'VALUES (?, ?, ?)',
            (principal_id, now, now),
        )
        try:
            connection.execute(
                'INSERT INTO principal_external_identity '
                '(identity_id, principal_id, provider, subject, status, created_at) '
                'VALUES (?, ?, ?, ?, ?, ?)',
                (
                    identity_id,
                    principal_id,
                    TELEGRAM_PROVIDER,
                    subject,
                    IDENTITY_STATUS_ACTIVE,
                    now,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise PrincipalIdentityError('external_identity_conflict') from exc
        return PrincipalExternalIdentity(
            identity_id=identity_id,
            principal_id=principal_id,
            provider=TELEGRAM_PROVIDER,
            subject=subject,
            status=IDENTITY_STATUS_ACTIVE,
            created_at=now,
        )

    def resolve_active_telegram_id(self, principal_id: str) -> int:
        with managed_connection(self._db_path) as connection:
            rows = connection.execute(
                'SELECT e.subject FROM principal_external_identity e '
                'JOIN principal p ON p.principal_id = e.principal_id '
                'WHERE e.principal_id = ? AND e.provider = ? AND e.status = ? '
                'ORDER BY e.identity_id LIMIT 2',
                (principal_id, TELEGRAM_PROVIDER, IDENTITY_STATUS_ACTIVE),
            ).fetchall()
        if len(rows) != 1:
            raise PrincipalIdentityError('principal_telegram_identity_unavailable')
        try:
            telegram_id = int(str(rows[0][0]))
        except ValueError as exc:
            raise PrincipalIdentityError('principal_telegram_identity_invalid') from exc
        if telegram_id <= 0:
            raise PrincipalIdentityError('principal_telegram_identity_invalid')
        return telegram_id


_IDENTITY_SELECT = (
    'SELECT e.identity_id, e.principal_id, e.provider, e.subject, e.status, '
    'e.created_at FROM principal_external_identity e '
    'JOIN principal p ON p.principal_id = e.principal_id'
)


def _row_to_identity(row: sqlite3.Row) -> PrincipalExternalIdentity:
    return PrincipalExternalIdentity(
        identity_id=str(row['identity_id']),
        principal_id=str(row['principal_id']),
        provider=str(row['provider']),
        subject=str(row['subject']),
        status=str(row['status']),
        created_at=str(row['created_at']),
    )


def _telegram_subject(telegram_id: int) -> str:
    if isinstance(telegram_id, bool) or not isinstance(telegram_id, int) or telegram_id <= 0:
        raise PrincipalIdentityError('telegram_identity_invalid')
    return str(telegram_id)


def _bounded_identity_value(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if not normalized or len(normalized) > 255 or any(c in normalized for c in '\r\n\x00'):
        raise PrincipalIdentityError(f'{field}_invalid')
    return normalized


def _opaque_id(prefix: str) -> str:
    return f'{prefix}_{secrets.token_urlsafe(24)}'


def _utc_now_text() -> str:
    return datetime.now(UTC).isoformat()
