from __future__ import annotations

from pathlib import Path
import sqlite3

import pytest

from bot.services.access_control import AccessControlService
from bot.services.db import init_db, managed_connection
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileCreationError,
    WorkspaceProfileService,
)


USER_ID = 70701


def _profile(name: str, *, workspace_id: str | None = None) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=USER_ID,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Test address',
        iban='SK3112000000198742637541',
        swift='GIBASKBX',
        email='owner@example.test',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
        workspace_id=workspace_id,
    )


def _approve(db_path: Path) -> None:
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=999,
        role='owner',
    )


def _count(db_path: Path, table: str) -> int:
    with managed_connection(db_path) as connection:
        return int(connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0])


def test_supplier_service_keeps_legacy_single_profile_upsert(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    service = SupplierService(db_path)

    service.create_or_replace(_profile('First'))
    service.create_or_replace(_profile('Updated'))

    saved = service.get_by_telegram_id(USER_ID)
    assert saved is not None
    assert saved.name == 'Updated'
    assert saved.workspace_id is None
    assert _count(db_path, 'supplier') == 1


def test_first_and_additional_profiles_are_atomic_and_workspace_scoped(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    service = WorkspaceProfileService(db_path)

    first = service.create_profile(
        actor_telegram_id=USER_ID,
        profile=_profile('Oleksiienko SZCO'),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id='ws_first',
        storage_key='oleksiienko-szco',
    )
    second = service.create_profile(
        actor_telegram_id=USER_ID,
        profile=_profile('ZEUS s. r. o.'),
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
        make_active=False,
        workspace_id='ws_zeus',
        storage_key='zeus-sro',
    )

    supplier_service = SupplierService(db_path)
    assert supplier_service.get_by_workspace_id(first.workspace_id).name == 'Oleksiienko SZCO'
    assert supplier_service.get_by_workspace_id(second.workspace_id).name == 'ZEUS s. r. o.'
    with pytest.raises(
        RuntimeError,
        match='ambiguous_supplier_profile_requires_workspace',
    ):
        supplier_service.get_by_telegram_id(USER_ID)
    with managed_connection(db_path) as connection:
        active = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id = ?',
            (USER_ID,),
        ).fetchone()
    assert active == ('ws_first',)
    assert _count(db_path, 'workspace') == 2
    assert _count(db_path, 'workspace_membership') == 2
    assert _count(db_path, 'supplier') == 2


def test_profile_creation_rolls_back_all_rows_on_workspace_conflict(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    service = WorkspaceProfileService(db_path)
    service.create_profile(
        actor_telegram_id=USER_ID,
        profile=_profile('First'),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id='ws_first',
        storage_key='shared-key',
    )

    with pytest.raises(sqlite3.IntegrityError):
        service.create_profile(
            actor_telegram_id=USER_ID,
            profile=_profile('Second'),
            mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
            make_active=False,
            workspace_id='ws_second',
            storage_key='shared-key',
        )

    assert _count(db_path, 'workspace') == 1
    assert _count(db_path, 'workspace_membership') == 1
    assert _count(db_path, 'supplier') == 1


def test_unauthorized_user_cannot_create_workspace_or_supplier(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)

    with pytest.raises(
        WorkspaceProfileCreationError,
        match='active_authorization_required',
    ):
        WorkspaceProfileService(db_path).create_profile(
            actor_telegram_id=USER_ID,
            profile=_profile('Forbidden'),
            mode=CREATE_FIRST_WORKSPACE_PROFILE,
            make_active=True,
        )

    assert _count(db_path, 'workspace') == 0
    assert _count(db_path, 'workspace_membership') == 0
    assert _count(db_path, 'supplier') == 0


def test_additional_profile_requires_existing_owner_membership(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)

    with pytest.raises(
        WorkspaceProfileCreationError,
        match='additional_workspace_requires_owner',
    ):
        WorkspaceProfileService(db_path).create_profile(
            actor_telegram_id=USER_ID,
            profile=_profile('Second'),
            mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
            make_active=False,
        )

    assert _count(db_path, 'workspace') == 0

def test_first_workspace_requires_clean_business_state(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _approve(db_path)
    SupplierService(db_path).create_or_replace(_profile('Legacy'))

    with pytest.raises(
        WorkspaceProfileCreationError,
        match='first_workspace_requires_clean_business_state',
    ):
        WorkspaceProfileService(db_path).create_profile(
            actor_telegram_id=USER_ID,
            profile=_profile('Duplicate first'),
            mode=CREATE_FIRST_WORKSPACE_PROFILE,
            make_active=True,
        )

    assert _count(db_path, 'workspace') == 0
    assert _count(db_path, 'workspace_membership') == 0
    assert _count(db_path, 'supplier') == 1