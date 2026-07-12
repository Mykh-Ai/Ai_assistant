from __future__ import annotations

from pathlib import Path

import pytest

from bot.services.access_control import AccessControlService
from bot.services.db import init_db, managed_connection
from bot.services.workspace_context import (
    WorkspaceAuthorizationRequired,
    WorkspaceContextService,
    WorkspaceMembershipRequired,
    WorkspaceSelectionRequired,
)


USER_ID = 10101
OTHER_USER_ID = 20202


def _insert_workspace(
    db_path: Path,
    *,
    workspace_id: str,
    display_name: str,
    telegram_id: int = USER_ID,
    membership_status: str = 'active',
) -> None:
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO workspace '
                '(workspace_id, display_name, storage_key, drive_folder_name, status, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
            ),
            (workspace_id, display_name, f'{workspace_id}-storage', display_name, 'active'),
        )
        connection.execute(
            (
                'INSERT INTO workspace_membership '
                '(workspace_id, telegram_id, role, status, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
            ),
            (workspace_id, telegram_id, 'owner', membership_status),
        )
        connection.commit()


def _approve(db_path: Path, telegram_id: int = USER_ID) -> None:
    AccessControlService(db_path).approve_user(telegram_id=telegram_id, approved_by=999)


def test_workspace_resolution_requires_user_authorization(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _insert_workspace(db_path, workspace_id='ws_one', display_name='One')
    with pytest.raises(WorkspaceAuthorizationRequired):
        WorkspaceContextService(db_path).resolve_for_user(USER_ID)


def test_single_membership_is_auto_selected_and_persisted(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    _insert_workspace(db_path, workspace_id='ws_one', display_name='One')
    context = WorkspaceContextService(db_path).resolve_for_user(USER_ID)
    assert context.workspace_id == 'ws_one'
    assert context.actor_telegram_id == USER_ID
    with managed_connection(db_path) as connection:
        row = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id = ?',
            (USER_ID,),
        ).fetchone()
    assert row == ('ws_one',)


def test_multiple_memberships_require_persisted_valid_selection(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    _insert_workspace(db_path, workspace_id='ws_one', display_name='One')
    _insert_workspace(db_path, workspace_id='ws_two', display_name='Two')
    service = WorkspaceContextService(db_path)
    with pytest.raises(WorkspaceSelectionRequired):
        service.resolve_for_user(USER_ID)
    assert service.set_active_workspace(USER_ID, 'ws_two').workspace_id == 'ws_two'
    assert service.resolve_for_user(USER_ID).workspace_id == 'ws_two'


def test_cross_user_workspace_selection_is_rejected_without_side_effect(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    _approve(db_path, OTHER_USER_ID)
    _insert_workspace(db_path, workspace_id='ws_other', display_name='Other', telegram_id=OTHER_USER_ID)
    with pytest.raises(WorkspaceMembershipRequired):
        WorkspaceContextService(db_path).set_active_workspace(USER_ID, 'ws_other')
    with managed_connection(db_path) as connection:
        count = connection.execute(
            'SELECT COUNT(*) FROM active_workspace_selection WHERE telegram_id = ?',
            (USER_ID,),
        ).fetchone()[0]
    assert count == 0


def test_inactive_membership_is_not_accessible(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    _insert_workspace(
        db_path,
        workspace_id='ws_inactive',
        display_name='Inactive',
        membership_status='inactive',
    )
    with pytest.raises(WorkspaceMembershipRequired):
        WorkspaceContextService(db_path).resolve_for_user(USER_ID)