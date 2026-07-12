from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sqlite3
from uuid import uuid4

from bot.services.access_control import AUTHORIZED_STATUS_ACTIVE
from bot.services.db import managed_connection
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.workspace_context import WorkspaceContext


CREATE_FIRST_WORKSPACE_PROFILE = 'create_first_workspace_profile'
CREATE_ADDITIONAL_WORKSPACE_PROFILE = 'create_additional_workspace_profile'
_ALLOWED_CREATE_MODES = {
    CREATE_FIRST_WORKSPACE_PROFILE,
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
}


class WorkspaceProfileCreationError(RuntimeError):
    pass


class WorkspaceProfileService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._supplier_service = SupplierService(db_path)

    def create_profile(
        self,
        *,
        actor_telegram_id: int,
        profile: SupplierProfile,
        mode: str,
        make_active: bool,
        workspace_id: str | None = None,
        storage_key: str | None = None,
    ) -> WorkspaceContext:
        if mode not in _ALLOWED_CREATE_MODES:
            raise WorkspaceProfileCreationError('invalid_workspace_profile_mode')
        if profile.telegram_id != actor_telegram_id:
            raise WorkspaceProfileCreationError('supplier_actor_mismatch')

        resolved_workspace_id = (
            str(workspace_id).strip()
            if workspace_id is not None
            else f'ws_{uuid4().hex}'
        )
        resolved_storage_key = (
            str(storage_key).strip()
            if storage_key is not None
            else f'workspace-{uuid4().hex}'
        )
        if not resolved_workspace_id or not resolved_storage_key:
            raise WorkspaceProfileCreationError('invalid_workspace_identity')

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            self._require_authorized(connection, actor_telegram_id)
            self._validate_mode(connection, actor_telegram_id, mode)
            try:
                connection.execute(
                    (
                        'INSERT INTO workspace '
                        '(workspace_id, display_name, storage_key, drive_folder_name, '
                        'status, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                    ),
                    (
                        resolved_workspace_id,
                        profile.name,
                        resolved_storage_key,
                        profile.name,
                        'active',
                    ),
                )
                supplier_id = self._supplier_service.save_in_connection(
                    connection,
                    replace(profile, workspace_id=resolved_workspace_id),
                )
                connection.execute(
                    (
                        'INSERT INTO workspace_membership '
                        '(workspace_id, telegram_id, role, status, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                    ),
                    (
                        resolved_workspace_id,
                        actor_telegram_id,
                        'owner',
                        'active',
                    ),
                )
                if make_active:
                    connection.execute(
                        (
                            'INSERT INTO active_workspace_selection '
                            '(telegram_id, workspace_id, updated_at) '
                            'VALUES (?, ?, CURRENT_TIMESTAMP) '
                            'ON CONFLICT(telegram_id) DO UPDATE SET '
                            'workspace_id=excluded.workspace_id, '
                            'updated_at=CURRENT_TIMESTAMP'
                        ),
                        (actor_telegram_id, resolved_workspace_id),
                    )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

        return WorkspaceContext(
            actor_telegram_id=actor_telegram_id,
            workspace_id=resolved_workspace_id,
            workspace_display_name=profile.name,
            storage_key=resolved_storage_key,
            drive_folder_name=profile.name,
            membership_role='owner',
            supplier_id=supplier_id,
        )

    @staticmethod
    def _require_authorized(
        connection: sqlite3.Connection,
        telegram_id: int,
    ) -> None:
        row = connection.execute(
            'SELECT status FROM authorized_users WHERE telegram_id = ?',
            (telegram_id,),
        ).fetchone()
        if row is None or row['status'] != AUTHORIZED_STATUS_ACTIVE:
            raise WorkspaceProfileCreationError('active_authorization_required')

    @staticmethod
    def _validate_mode(
        connection: sqlite3.Connection,
        telegram_id: int,
        mode: str,
    ) -> None:
        memberships = connection.execute(
            (
                'SELECT role FROM workspace_membership '
                'WHERE telegram_id = ? AND status = ?'
            ),
            (telegram_id, 'active'),
        ).fetchall()
        if mode == CREATE_FIRST_WORKSPACE_PROFILE:
            supplier_exists = connection.execute(
                'SELECT 1 FROM supplier WHERE telegram_id = ? LIMIT 1',
                (telegram_id,),
            ).fetchone()
            if memberships or supplier_exists is not None:
                raise WorkspaceProfileCreationError(
                    'first_workspace_requires_clean_business_state'
                )
            return
        if not any(row['role'] == 'owner' for row in memberships):
            raise WorkspaceProfileCreationError(
                'additional_workspace_requires_owner'
            )