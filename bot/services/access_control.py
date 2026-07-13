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
WORKSPACE_MEMBERSHIP_STATUS_ACTIVE = 'active'
WORKSPACE_MEMBERSHIP_STATUS_INACTIVE = 'inactive'


class AccessApprovalWorkspaceConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class AccessApprovalResult:
    reactivated_workspace_membership: bool
    restored_active_selection: bool


@dataclass(frozen=True)
class _WorkspaceApprovalPlan:
    reactivate_workspace_id: str | None = None
    selection_workspace_id: str | None = None


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

    def approve_user(
        self,
        *,
        telegram_id: int,
        approved_by: int,
        role: str = ROLE_USER,
    ) -> AccessApprovalResult:
        if role not in {ROLE_USER, ROLE_ADMIN, ROLE_OWNER}:
            raise ValueError('invalid_authorized_user_role')
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            try:
                workspace_plan = _workspace_approval_plan(connection, telegram_id)
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
                    (
                        telegram_id,
                        ACCESS_STATUS_APPROVED,
                        approved_by,
                        ACCESS_STATUS_APPROVED,
                        approved_by,
                    ),
                )
                if workspace_plan.reactivate_workspace_id is not None:
                    cursor = connection.execute(
                        (
                            'UPDATE workspace_membership SET status=?, updated_at=CURRENT_TIMESTAMP '
                            'WHERE telegram_id=? AND workspace_id=? AND status=?'
                        ),
                        (
                            WORKSPACE_MEMBERSHIP_STATUS_ACTIVE,
                            telegram_id,
                            workspace_plan.reactivate_workspace_id,
                            WORKSPACE_MEMBERSHIP_STATUS_INACTIVE,
                        ),
                    )
                    if cursor.rowcount != 1:
                        raise AccessApprovalWorkspaceConflict(
                            'workspace_membership_reactivation_race'
                        )
                if workspace_plan.selection_workspace_id is not None:
                    connection.execute(
                        (
                            'INSERT INTO active_workspace_selection '
                            '(telegram_id, workspace_id, updated_at) '
                            'VALUES (?, ?, CURRENT_TIMESTAMP) '
                            'ON CONFLICT(telegram_id) DO UPDATE SET '
                            'workspace_id=excluded.workspace_id, updated_at=CURRENT_TIMESTAMP'
                        ),
                        (telegram_id, workspace_plan.selection_workspace_id),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return AccessApprovalResult(
            reactivated_workspace_membership=(
                workspace_plan.reactivate_workspace_id is not None
            ),
            restored_active_selection=(
                workspace_plan.selection_workspace_id is not None
            ),
        )

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


def _workspace_approval_plan(
    connection: sqlite3.Connection,
    telegram_id: int,
) -> _WorkspaceApprovalPlan:
    required_tables = {
        'workspace',
        'workspace_membership',
        'active_workspace_selection',
        'supplier',
    }
    table_names = {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    if not required_tables <= table_names:
        return _WorkspaceApprovalPlan()

    memberships = connection.execute(
        (
            'SELECT workspace_id, role, status FROM workspace_membership '
            'WHERE telegram_id=? ORDER BY workspace_id'
        ),
        (telegram_id,),
    ).fetchall()
    inactive_memberships = [
        row
        for row in memberships
        if str(row['status']) == WORKSPACE_MEMBERSHIP_STATUS_INACTIVE
    ]
    unsupported_statuses = [
        row
        for row in memberships
        if str(row['status'])
        not in {
            WORKSPACE_MEMBERSHIP_STATUS_ACTIVE,
            WORKSPACE_MEMBERSHIP_STATUS_INACTIVE,
        }
    ]
    if unsupported_statuses:
        raise AccessApprovalWorkspaceConflict(
            'unsupported_workspace_membership_status'
        )

    if inactive_memberships:
        if len(memberships) != 1 or len(inactive_memberships) != 1:
            raise AccessApprovalWorkspaceConflict(
                'ambiguous_inactive_workspace_memberships'
            )
        membership = inactive_memberships[0]
        workspace_id = str(membership['workspace_id'])
        if str(membership['role']) != ROLE_OWNER:
            raise AccessApprovalWorkspaceConflict(
                'inactive_workspace_membership_not_owner'
            )
        _validate_inactive_workspace_ownership(
            connection,
            telegram_id=telegram_id,
            workspace_id=workspace_id,
        )
        return _WorkspaceApprovalPlan(
            reactivate_workspace_id=workspace_id,
            selection_workspace_id=workspace_id,
        )

    active_memberships = [
        row
        for row in memberships
        if str(row['status']) == WORKSPACE_MEMBERSHIP_STATUS_ACTIVE
    ]
    if len(memberships) == 1 and len(active_memberships) == 1:
        workspace_id = str(active_memberships[0]['workspace_id'])
        workspace = connection.execute(
            'SELECT status FROM workspace WHERE workspace_id=?',
            (workspace_id,),
        ).fetchone()
        if workspace is None or str(workspace['status']) != 'active':
            raise AccessApprovalWorkspaceConflict(
                'single_active_membership_workspace_unavailable'
            )
        return _WorkspaceApprovalPlan(selection_workspace_id=workspace_id)
    return _WorkspaceApprovalPlan()


def _validate_inactive_workspace_ownership(
    connection: sqlite3.Connection,
    *,
    telegram_id: int,
    workspace_id: str,
) -> None:
    workspace = connection.execute(
        'SELECT status FROM workspace WHERE workspace_id=?',
        (workspace_id,),
    ).fetchone()
    workspace_suppliers = connection.execute(
        'SELECT telegram_id FROM supplier WHERE workspace_id=?',
        (workspace_id,),
    ).fetchall()
    actor_suppliers = connection.execute(
        'SELECT workspace_id FROM supplier WHERE telegram_id=?',
        (telegram_id,),
    ).fetchall()
    owner_memberships = connection.execute(
        (
            'SELECT telegram_id FROM workspace_membership '
            'WHERE workspace_id=? AND role=?'
        ),
        (workspace_id, ROLE_OWNER),
    ).fetchall()
    if workspace is None or str(workspace['status']) != 'active':
        raise AccessApprovalWorkspaceConflict('inactive_workspace_unavailable')
    if (
        len(workspace_suppliers) != 1
        or int(workspace_suppliers[0]['telegram_id']) != telegram_id
        or len(actor_suppliers) != 1
        or str(actor_suppliers[0]['workspace_id']) != workspace_id
        or len(owner_memberships) != 1
        or int(owner_memberships[0]['telegram_id']) != telegram_id
    ):
        raise AccessApprovalWorkspaceConflict(
            'inactive_workspace_ownership_conflict'
        )


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
