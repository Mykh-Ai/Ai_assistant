from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from bot.services.db import managed_connection


ACCESS_STATUS_PENDING = 'pending'
ACCESS_STATUS_APPROVED = 'approved'
ACCESS_STATUS_REJECTED = 'rejected'
ACCESS_STATUS_DELETED_DATABASE = 'deleted_database'
AUTHORIZED_STATUS_ACTIVE = 'active'
AUTHORIZED_STATUS_BLOCKED = 'blocked'
AUTHORIZED_STATUS_DELETED_DATABASE = 'deleted_database'
ROLE_USER = 'user'
ROLE_ADMIN = 'admin'
ROLE_OWNER = 'owner'


@dataclass(frozen=True)
class AccessRequestRecord:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    status: str
    requested_at: str
    decided_at: str | None
    decided_by: int | None


@dataclass(frozen=True)
class AuthorizedUserRecord:
    telegram_id: int
    role: str
    status: str
    created_at: str
    approved_by: int | None


@dataclass(frozen=True)
class AccessRequestInput:
    telegram_id: int
    username: str | None
    first_name: str | None
    last_name: str | None


class AccessControlService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def create_or_refresh_pending_request(self, request: AccessRequestInput) -> AccessRequestRecord:
        existing = self.get_access_request(request.telegram_id)
        existing_user = self.get_authorized_user(request.telegram_id)
        is_deleted_database_user = (
            existing_user is not None and existing_user.status == AUTHORIZED_STATUS_DELETED_DATABASE
        )
        if (
            existing is not None
            and existing.status in {ACCESS_STATUS_APPROVED, ACCESS_STATUS_REJECTED}
            and not is_deleted_database_user
        ):
            return existing

        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO access_requests '
                    '(telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by) '
                    'VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, NULL, NULL) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET '
                    'username=excluded.username, '
                    'first_name=excluded.first_name, '
                    'last_name=excluded.last_name, '
                    'status=?, '
                    'requested_at=CURRENT_TIMESTAMP, '
                    'decided_at=NULL, '
                    'decided_by=NULL'
                ),
                (
                    request.telegram_id,
                    _clean_optional(request.username),
                    _clean_optional(request.first_name),
                    _clean_optional(request.last_name),
                    ACCESS_STATUS_PENDING,
                    ACCESS_STATUS_PENDING,
                ),
            )
            connection.commit()
        refreshed = self.get_access_request(request.telegram_id)
        if refreshed is None:
            raise RuntimeError('Access request save failed.')
        return refreshed

    def get_access_request(self, telegram_id: int) -> AccessRequestRecord | None:
        try:
            with managed_connection(self._db_path) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    (
                        'SELECT telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by '
                        'FROM access_requests WHERE telegram_id = ?'
                    ),
                    (telegram_id,),
                ).fetchone()
        except sqlite3.OperationalError as exc:
            if _is_missing_table_error(exc):
                return None
            raise
        return _access_request_from_row(row) if row is not None else None

    def list_access_requests(self, *, status: str | None = None) -> list[AccessRequestRecord]:
        try:
            with managed_connection(self._db_path) as connection:
                connection.row_factory = sqlite3.Row
                if status is None:
                    rows = connection.execute(
                        (
                            'SELECT telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by '
                            'FROM access_requests ORDER BY requested_at DESC'
                        )
                    ).fetchall()
                else:
                    rows = connection.execute(
                        (
                            'SELECT telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by '
                            'FROM access_requests WHERE status = ? ORDER BY requested_at ASC'
                        ),
                        (status,),
                    ).fetchall()
        except sqlite3.OperationalError as exc:
            if _is_missing_table_error(exc):
                return []
            raise
        return [_access_request_from_row(row) for row in rows]

    def approve_user(self, *, telegram_id: int, approved_by: int, role: str = ROLE_USER) -> None:
        if role not in {ROLE_USER, ROLE_ADMIN, ROLE_OWNER}:
            raise ValueError('invalid_authorized_user_role')
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO authorized_users (telegram_id, role, status, created_at, approved_by) '
                    'VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET '
                    'role=excluded.role, '
                    'status=excluded.status, '
                    'approved_by=excluded.approved_by'
                ),
                (telegram_id, role, AUTHORIZED_STATUS_ACTIVE, approved_by),
            )
            connection.execute(
                (
                    'INSERT INTO access_requests '
                    '(telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by) '
                    'VALUES (?, NULL, NULL, NULL, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET '
                    'status=?, decided_at=CURRENT_TIMESTAMP, decided_by=?'
                ),
                (telegram_id, ACCESS_STATUS_APPROVED, approved_by, ACCESS_STATUS_APPROVED, approved_by),
            )
            connection.commit()

    def reject_user(self, *, telegram_id: int, decided_by: int) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO access_requests '
                    '(telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by) '
                    'VALUES (?, NULL, NULL, NULL, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET '
                    'status=?, decided_at=CURRENT_TIMESTAMP, decided_by=?'
                ),
                (telegram_id, ACCESS_STATUS_REJECTED, decided_by, ACCESS_STATUS_REJECTED, decided_by),
            )
            connection.execute(
                'DELETE FROM authorized_users WHERE telegram_id = ? AND role = ?',
                (telegram_id, ROLE_USER),
            )
            connection.commit()

    def block_user(self, *, telegram_id: int, decided_by: int) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO authorized_users (telegram_id, role, status, created_at, approved_by) '
                    'VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET status=?'
                ),
                (telegram_id, ROLE_USER, AUTHORIZED_STATUS_BLOCKED, decided_by, AUTHORIZED_STATUS_BLOCKED),
            )
            connection.commit()

    def mark_deleted_database(self, *, telegram_id: int) -> None:
        with managed_connection(self._db_path) as connection:
            mark_deleted_database_in_connection(connection, telegram_id=telegram_id)
            connection.commit()

    def get_authorized_user(self, telegram_id: int) -> AuthorizedUserRecord | None:
        try:
            with managed_connection(self._db_path) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    'SELECT telegram_id, role, status, created_at, approved_by FROM authorized_users WHERE telegram_id = ?',
                    (telegram_id,),
                ).fetchone()
        except sqlite3.OperationalError as exc:
            if _is_missing_table_error(exc):
                return None
            raise
        return _authorized_user_from_row(row) if row is not None else None

    def list_authorized_users(self) -> list[AuthorizedUserRecord]:
        try:
            with managed_connection(self._db_path) as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    'SELECT telegram_id, role, status, created_at, approved_by FROM authorized_users ORDER BY created_at DESC'
                ).fetchall()
        except sqlite3.OperationalError as exc:
            if _is_missing_table_error(exc):
                return []
            raise
        return [_authorized_user_from_row(row) for row in rows]

    def is_active_user(self, telegram_id: int) -> bool:
        user = self.get_authorized_user(telegram_id)
        return user is not None and user.status == AUTHORIZED_STATUS_ACTIVE

    def is_admin_user(self, telegram_id: int) -> bool:
        user = self.get_authorized_user(telegram_id)
        return (
            user is not None
            and user.status == AUTHORIZED_STATUS_ACTIVE
            and user.role in {ROLE_ADMIN, ROLE_OWNER}
        )

    def is_blocked_user(self, telegram_id: int) -> bool:
        user = self.get_authorized_user(telegram_id)
        return user is not None and user.status == AUTHORIZED_STATUS_BLOCKED

    def is_deleted_database_user(self, telegram_id: int) -> bool:
        user = self.get_authorized_user(telegram_id)
        return user is not None and user.status == AUTHORIZED_STATUS_DELETED_DATABASE


def mark_deleted_database_in_connection(connection: sqlite3.Connection, *, telegram_id: int) -> None:
    connection.execute(
        (
            'INSERT INTO authorized_users (telegram_id, role, status, created_at, approved_by) '
            'VALUES (?, ?, ?, CURRENT_TIMESTAMP, NULL) '
            'ON CONFLICT(telegram_id) DO UPDATE SET status=?'
        ),
        (telegram_id, ROLE_USER, AUTHORIZED_STATUS_DELETED_DATABASE, AUTHORIZED_STATUS_DELETED_DATABASE),
    )
    connection.execute(
        (
            'INSERT INTO access_requests '
            '(telegram_id, username, first_name, last_name, status, requested_at, decided_at, decided_by) '
            'VALUES (?, NULL, NULL, NULL, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?) '
            'ON CONFLICT(telegram_id) DO UPDATE SET '
            'status=?, decided_at=CURRENT_TIMESTAMP, decided_by=?'
        ),
        (
            telegram_id,
            ACCESS_STATUS_DELETED_DATABASE,
            telegram_id,
            ACCESS_STATUS_DELETED_DATABASE,
            telegram_id,
        ),
    )


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_missing_table_error(exc: sqlite3.OperationalError) -> bool:
    return 'no such table' in str(exc).lower()


def _access_request_from_row(row: sqlite3.Row) -> AccessRequestRecord:
    return AccessRequestRecord(
        telegram_id=int(row['telegram_id']),
        username=row['username'],
        first_name=row['first_name'],
        last_name=row['last_name'],
        status=row['status'],
        requested_at=row['requested_at'],
        decided_at=row['decided_at'],
        decided_by=row['decided_by'],
    )


def _authorized_user_from_row(row: sqlite3.Row) -> AuthorizedUserRecord:
    return AuthorizedUserRecord(
        telegram_id=int(row['telegram_id']),
        role=row['role'],
        status=row['status'],
        created_at=row['created_at'],
        approved_by=row['approved_by'],
    )
