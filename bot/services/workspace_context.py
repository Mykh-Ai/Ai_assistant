from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from bot.services.access_control import AUTHORIZED_STATUS_ACTIVE
from bot.services.db import managed_connection


WORKSPACE_STATUS_ACTIVE = 'active'
MEMBERSHIP_STATUS_ACTIVE = 'active'


class WorkspaceContextError(RuntimeError):
    pass


class WorkspaceAuthorizationRequired(WorkspaceContextError):
    pass


class WorkspaceMembershipRequired(WorkspaceContextError):
    pass


class WorkspaceSelectionRequired(WorkspaceContextError):
    pass


@dataclass(frozen=True)
class WorkspaceContext:
    actor_telegram_id: int
    workspace_id: str
    workspace_display_name: str
    storage_key: str
    drive_folder_name: str
    membership_role: str
    supplier_id: int | None


class WorkspaceContextService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def list_accessible_workspaces(self, telegram_id: int) -> list[WorkspaceContext]:
        self._require_authorized_user(telegram_id)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT w.workspace_id, w.display_name, w.storage_key, '
                    'w.drive_folder_name, m.role '
                    'FROM workspace_membership AS m '
                    'JOIN workspace AS w ON w.workspace_id = m.workspace_id '
                    'WHERE m.telegram_id = ? AND m.status = ? AND w.status = ? '
                    'ORDER BY w.created_at, w.workspace_id'
                ),
                (telegram_id, MEMBERSHIP_STATUS_ACTIVE, WORKSPACE_STATUS_ACTIVE),
            ).fetchall()
            supplier_ids = self._supplier_ids_by_workspace(connection, rows)

        return [
            WorkspaceContext(
                actor_telegram_id=telegram_id,
                workspace_id=row['workspace_id'],
                workspace_display_name=row['display_name'],
                storage_key=row['storage_key'],
                drive_folder_name=row['drive_folder_name'],
                membership_role=row['role'],
                supplier_id=supplier_ids.get(row['workspace_id']),
            )
            for row in rows
        ]

    def resolve_for_user(self, telegram_id: int) -> WorkspaceContext:
        contexts = self.list_accessible_workspaces(telegram_id)
        if not contexts:
            raise WorkspaceMembershipRequired('active_workspace_membership_required')
        if len(contexts) == 1:
            context = contexts[0]
            self._persist_active_selection(telegram_id, context.workspace_id)
            return context
        selected_workspace_id = self._get_active_selection(telegram_id)
        for context in contexts:
            if context.workspace_id == selected_workspace_id:
                return context
        raise WorkspaceSelectionRequired('active_workspace_selection_required')

    def resolve_for_user_readonly(self, telegram_id: int) -> WorkspaceContext:
        contexts = self.list_accessible_workspaces(telegram_id)
        if not contexts:
            raise WorkspaceMembershipRequired('active_workspace_membership_required')
        if len(contexts) == 1:
            return contexts[0]
        selected_workspace_id = self._get_active_selection(telegram_id)
        for context in contexts:
            if context.workspace_id == selected_workspace_id:
                return context
        raise WorkspaceSelectionRequired('active_workspace_selection_required')

    def resolve_for_background_workspace(self, workspace_id: str) -> WorkspaceContext:
        normalized_workspace_id = str(workspace_id).strip()
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT w.workspace_id, w.display_name, w.storage_key, '
                    'w.drive_folder_name, m.role, s.id AS supplier_id, '
                    's.telegram_id AS actor_telegram_id '
                    'FROM workspace w '
                    'JOIN supplier s ON s.workspace_id = w.workspace_id '
                    'JOIN workspace_membership m '
                    'ON m.workspace_id = w.workspace_id '
                    'AND m.telegram_id = s.telegram_id '
                    'JOIN authorized_users a ON a.telegram_id = s.telegram_id '
                    'WHERE w.workspace_id = ? AND w.status = ? '
                    'AND m.status = ? AND a.status = ?'
                ),
                (
                    normalized_workspace_id,
                    WORKSPACE_STATUS_ACTIVE,
                    MEMBERSHIP_STATUS_ACTIVE,
                    AUTHORIZED_STATUS_ACTIVE,
                ),
            ).fetchone()
        if row is None:
            raise WorkspaceMembershipRequired(
                'background_workspace_owner_membership_required'
            )
        return WorkspaceContext(
            actor_telegram_id=int(row['actor_telegram_id']),
            workspace_id=str(row['workspace_id']),
            workspace_display_name=str(row['display_name']),
            storage_key=str(row['storage_key']),
            drive_folder_name=str(row['drive_folder_name']),
            membership_role=str(row['role']),
            supplier_id=int(row['supplier_id']),
        )
    def require_membership(self, telegram_id: int, workspace_id: str) -> WorkspaceContext:
        normalized_workspace_id = str(workspace_id).strip()
        for context in self.list_accessible_workspaces(telegram_id):
            if context.workspace_id == normalized_workspace_id:
                return context
        raise WorkspaceMembershipRequired('active_workspace_membership_required')

    def set_active_workspace(self, telegram_id: int, workspace_id: str) -> WorkspaceContext:
        context = self.require_membership(telegram_id, workspace_id)
        self._persist_active_selection(telegram_id, context.workspace_id)
        return context

    def _require_authorized_user(self, telegram_id: int) -> None:
        with managed_connection(self._db_path) as connection:
            row = connection.execute(
                'SELECT status FROM authorized_users WHERE telegram_id = ?',
                (telegram_id,),
            ).fetchone()
        if row is None or row[0] != AUTHORIZED_STATUS_ACTIVE:
            raise WorkspaceAuthorizationRequired('active_authorization_required')

    def _get_active_selection(self, telegram_id: int) -> str | None:
        with managed_connection(self._db_path) as connection:
            row = connection.execute(
                'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id = ?',
                (telegram_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def _persist_active_selection(self, telegram_id: int, workspace_id: str) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO active_workspace_selection (telegram_id, workspace_id, updated_at) '
                    'VALUES (?, ?, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET '
                    'workspace_id=excluded.workspace_id, updated_at=CURRENT_TIMESTAMP'
                ),
                (telegram_id, workspace_id),
            )
            connection.commit()

    @staticmethod
    def _supplier_ids_by_workspace(
        connection: sqlite3.Connection,
        workspace_rows: list[sqlite3.Row],
    ) -> dict[str, int]:
        supplier_columns = {
            row[1] for row in connection.execute('PRAGMA table_info(supplier)').fetchall()
        }
        if 'workspace_id' not in supplier_columns or not workspace_rows:
            return {}
        workspace_ids = [str(row['workspace_id']) for row in workspace_rows]
        placeholders = ','.join('?' for _ in workspace_ids)
        rows = connection.execute(
            f'SELECT id, workspace_id FROM supplier WHERE workspace_id IN ({placeholders})',
            workspace_ids,
        ).fetchall()
        return {str(row['workspace_id']): int(row['id']) for row in rows}