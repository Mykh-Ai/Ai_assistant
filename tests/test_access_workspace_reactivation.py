from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.access_admin import cmd_approve
from bot.handlers.business_profiles import BusinessProfileStates, cmd_business_profiles
from bot.services.access_control import (
    ACCESS_STATUS_APPROVED,
    ACCESS_STATUS_PENDING,
    AccessApprovalWorkspaceConflict,
    AccessControlService,
)
from bot.services.db import init_db, managed_connection
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_context import WorkspaceContextService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


ADMIN_ID = 970001
USER_ID = 970002
OTHER_ID = 970003


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str, user_id: int) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.current_state = None
        self.data: dict[str, object] = {}

    async def get_state(self):
        return self.current_state

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()


class _DummyBot:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, telegram_id: int, text: str) -> None:
        self.sent.append((telegram_id, text))


def _config(
    tmp_path: Path,
    *,
    admins: frozenset[int] = frozenset({ADMIN_ID}),
) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'access.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset({USER_ID}),
        admin_telegram_user_ids=admins,
    )


def _supplier(user_id: int, name: str) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=user_id,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Bratislava',
        iban='SK3112000000198742637541',
        swift='TATRSKBX',
        email='owner@example.com',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
    )


def _create_profile(
    db_path: Path,
    *,
    name: str = 'Migrated business',
    mode: str = CREATE_FIRST_WORKSPACE_PROFILE,
):
    return WorkspaceProfileService(db_path).create_profile(
        actor_telegram_id=USER_ID,
        profile=_supplier(USER_ID, name),
        mode=mode,
        make_active=mode == CREATE_FIRST_WORKSPACE_PROFILE,
    )


def _make_actor_migrated_inactive(db_path: Path) -> str:
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=ADMIN_ID,
    )
    context = _create_profile(db_path)
    with managed_connection(db_path) as connection:
        connection.execute(
            "UPDATE workspace_membership SET status='inactive' "
            "WHERE telegram_id=? AND workspace_id=?",
            (USER_ID, context.workspace_id),
        )
        connection.execute(
            'DELETE FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        )
        connection.execute(
            'DELETE FROM authorized_users WHERE telegram_id=?',
            (USER_ID,),
        )
        connection.execute(
            "UPDATE access_requests SET status=?, decided_at=NULL, decided_by=NULL "
            "WHERE telegram_id=?",
            (ACCESS_STATUS_PENDING, USER_ID),
        )
        connection.commit()
    return context.workspace_id


def _counts(db_path: Path) -> tuple[int, int]:
    with managed_connection(db_path) as connection:
        workspace_count = int(connection.execute('SELECT COUNT(*) FROM workspace').fetchone()[0])
        supplier_count = int(connection.execute('SELECT COUNT(*) FROM supplier').fetchone()[0])
    return workspace_count, supplier_count


def test_approval_reactivates_single_verified_migrated_owner_membership(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    workspace_id = _make_actor_migrated_inactive(config.db_path)
    before_counts = _counts(config.db_path)

    result = AccessControlService(config.db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=ADMIN_ID,
    )

    with managed_connection(config.db_path) as connection:
        membership = connection.execute(
            'SELECT role, status FROM workspace_membership '
            'WHERE telegram_id=? AND workspace_id=?',
            (USER_ID, workspace_id),
        ).fetchone()
        selection = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()
    user = AccessControlService(config.db_path).get_authorized_user(USER_ID)
    request = AccessControlService(config.db_path).get_access_request(USER_ID)

    assert result.reactivated_workspace_membership is True
    assert result.restored_active_selection is True
    assert membership == ('owner', 'active')
    assert selection == (workspace_id,)
    assert user is not None and user.status == 'active'
    assert request is not None and request.status == ACCESS_STATUS_APPROVED
    assert _counts(config.db_path) == before_counts == (1, 1)
    assert WorkspaceContextService(config.db_path).resolve_for_user(USER_ID).workspace_id == workspace_id


def test_approval_restores_selection_for_single_existing_active_membership(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = AccessControlService(config.db_path)
    service.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    context = _create_profile(config.db_path)
    with managed_connection(config.db_path) as connection:
        connection.execute(
            'DELETE FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        )
        connection.commit()

    result = service.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)

    with managed_connection(config.db_path) as connection:
        selection = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()
    assert result.reactivated_workspace_membership is False
    assert result.restored_active_selection is True
    assert selection == (context.workspace_id,)
    assert _counts(config.db_path) == (1, 1)


def test_clean_approval_creates_no_workspace_supplier_membership_or_selection(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)

    result = AccessControlService(config.db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=ADMIN_ID,
    )

    with managed_connection(config.db_path) as connection:
        assert connection.execute('SELECT COUNT(*) FROM workspace_membership').fetchone()[0] == 0
        assert connection.execute('SELECT COUNT(*) FROM active_workspace_selection').fetchone()[0] == 0
    assert result.reactivated_workspace_membership is False
    assert result.restored_active_selection is False
    assert _counts(config.db_path) == (0, 0)


def test_multiple_inactive_memberships_fail_closed_and_roll_back_approval(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = AccessControlService(config.db_path)
    service.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    _create_profile(config.db_path, name='First')
    _create_profile(
        config.db_path,
        name='Second',
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    )
    with managed_connection(config.db_path) as connection:
        connection.execute(
            "UPDATE workspace_membership SET status='inactive' WHERE telegram_id=?",
            (USER_ID,),
        )
        connection.execute(
            'DELETE FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        )
        connection.execute(
            'DELETE FROM authorized_users WHERE telegram_id=?',
            (USER_ID,),
        )
        connection.execute(
            "UPDATE access_requests SET status=? WHERE telegram_id=?",
            (ACCESS_STATUS_PENDING, USER_ID),
        )
        connection.commit()

    with pytest.raises(
        AccessApprovalWorkspaceConflict,
        match='ambiguous_inactive_workspace_memberships',
    ):
        service.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)

    with managed_connection(config.db_path) as connection:
        statuses = connection.execute(
            'SELECT status FROM workspace_membership WHERE telegram_id=? ORDER BY workspace_id',
            (USER_ID,),
        ).fetchall()
        auth_count = connection.execute(
            'SELECT COUNT(*) FROM authorized_users WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()[0]
    request = service.get_access_request(USER_ID)
    assert statuses == [('inactive',), ('inactive',)]
    assert auth_count == 0
    assert request is not None and request.status == ACCESS_STATUS_PENDING
    assert _counts(config.db_path) == (2, 2)


def test_supplier_actor_mismatch_fails_closed_and_rolls_back_approval(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    workspace_id = _make_actor_migrated_inactive(config.db_path)
    with managed_connection(config.db_path) as connection:
        connection.execute(
            'UPDATE supplier SET telegram_id=? WHERE workspace_id=?',
            (OTHER_ID, workspace_id),
        )
        connection.commit()

    with pytest.raises(
        AccessApprovalWorkspaceConflict,
        match='inactive_workspace_ownership_conflict',
    ):
        AccessControlService(config.db_path).approve_user(
            telegram_id=USER_ID,
            approved_by=ADMIN_ID,
        )

    with managed_connection(config.db_path) as connection:
        membership_status = connection.execute(
            'SELECT status FROM workspace_membership '
            'WHERE telegram_id=? AND workspace_id=?',
            (USER_ID, workspace_id),
        ).fetchone()[0]
        auth_count = connection.execute(
            'SELECT COUNT(*) FROM authorized_users WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()[0]
        selection_count = connection.execute(
            'SELECT COUNT(*) FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()[0]
    assert membership_status == 'inactive'
    assert auth_count == 0
    assert selection_count == 0


def test_admin_approval_conflict_is_bounded_and_sends_no_notification(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = AccessControlService(config.db_path)
    service.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    _create_profile(config.db_path, name='First')
    _create_profile(
        config.db_path,
        name='Second',
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    )
    with managed_connection(config.db_path) as connection:
        connection.execute(
            "UPDATE workspace_membership SET status='inactive' WHERE telegram_id=?",
            (USER_ID,),
        )
        connection.execute('DELETE FROM authorized_users WHERE telegram_id=?', (USER_ID,))
        connection.commit()
    message = _DummyMessage(f'/approve {USER_ID}', ADMIN_ID)
    bot = _DummyBot()

    asyncio.run(cmd_approve(message, config, bot=bot))

    assert bot.sent == []
    assert message.answers == [
        'Schválenie sa nevykonalo: existujúce vlastníctvo business workspace '
        'nie je jednoznačné. Žiadne údaje neboli zmenené.'
    ]
    assert service.get_authorized_user(USER_ID) is None


def test_configured_admin_can_self_approve_without_exposing_telegram_id(tmp_path: Path) -> None:
    config = _config(tmp_path, admins=frozenset({USER_ID}))
    init_db(config.db_path)
    workspace_id = _make_actor_migrated_inactive(config.db_path)
    message = _DummyMessage('/approve', USER_ID)
    bot = _DummyBot()

    asyncio.run(cmd_approve(message, config, bot=bot))

    with managed_connection(config.db_path) as connection:
        membership = connection.execute(
            'SELECT status FROM workspace_membership '
            'WHERE telegram_id=? AND workspace_id=?',
            (USER_ID, workspace_id),
        ).fetchone()
        selection = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()
    user = AccessControlService(config.db_path).get_authorized_user(USER_ID)

    assert membership == ('active',)
    assert selection == (workspace_id,)
    assert user is not None and user.status == 'active'
    assert bot.sent and bot.sent[0][0] == USER_ID
    assert '/start' in message.answers[-1]


def test_approve_with_invalid_explicit_target_keeps_usage_error(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('/approve invalid', ADMIN_ID)

    asyncio.run(cmd_approve(message, config, bot=_DummyBot()))

    assert message.answers == ['Pouzitie: /approve <telegram_id>']
    assert AccessControlService(config.db_path).get_authorized_user(ADMIN_ID) is None


def test_admin_approval_of_other_migrated_user_unlocks_profily(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    workspace_id = _make_actor_migrated_inactive(config.db_path)
    admin_message = _DummyMessage(f'/approve {USER_ID}', ADMIN_ID)

    asyncio.run(cmd_approve(admin_message, config, bot=_DummyBot()))

    profile_message = _DummyMessage('/profily', USER_ID)
    state = _DummyState()
    asyncio.run(cmd_business_profiles(profile_message, state, config))

    context = WorkspaceContextService(config.db_path).resolve_for_user(USER_ID)
    assert context.workspace_id == workspace_id
    assert state.current_state == BusinessProfileStates.waiting_selection.state
    assert profile_message.answers
    assert all('dostupn' not in answer for answer in profile_message.answers)
    assert 'Migrated business' in profile_message.answers[-1]


def test_approving_migrated_user_preserves_existing_registered_user(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = AccessControlService(config.db_path)

    service.approve_user(telegram_id=USER_ID, approved_by=ADMIN_ID)
    existing = _create_profile(config.db_path, name='Existing business')

    service.approve_user(telegram_id=OTHER_ID, approved_by=ADMIN_ID)
    migrated = WorkspaceProfileService(config.db_path).create_profile(
        actor_telegram_id=OTHER_ID,
        profile=_supplier(OTHER_ID, 'Other migrated business'),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
    )
    with managed_connection(config.db_path) as connection:
        connection.execute(
            "UPDATE workspace_membership SET status='inactive' "
            'WHERE telegram_id=? AND workspace_id=?',
            (OTHER_ID, migrated.workspace_id),
        )
        connection.execute(
            'DELETE FROM active_workspace_selection WHERE telegram_id=?',
            (OTHER_ID,),
        )
        connection.execute(
            'DELETE FROM authorized_users WHERE telegram_id=?',
            (OTHER_ID,),
        )
        connection.execute(
            'UPDATE access_requests SET status=?, decided_at=NULL, decided_by=NULL '
            'WHERE telegram_id=?',
            (ACCESS_STATUS_PENDING, OTHER_ID),
        )
        connection.commit()
    before_counts = _counts(config.db_path)

    asyncio.run(
        cmd_approve(
            _DummyMessage(f'/approve {OTHER_ID}', ADMIN_ID),
            config,
            bot=_DummyBot(),
        )
    )

    existing_context = WorkspaceContextService(config.db_path).resolve_for_user(USER_ID)
    existing_message = _DummyMessage('/profily', USER_ID)
    existing_state = _DummyState()
    asyncio.run(cmd_business_profiles(existing_message, existing_state, config))

    assert existing_context.workspace_id == existing.workspace_id
    assert existing_state.current_state == BusinessProfileStates.waiting_selection.state
    assert 'Existing business' in existing_message.answers[-1]
    assert _counts(config.db_path) == before_counts == (2, 2)
    with managed_connection(config.db_path) as connection:
        existing_membership = connection.execute(
            'SELECT role, status FROM workspace_membership '
            'WHERE telegram_id=? AND workspace_id=?',
            (USER_ID, existing.workspace_id),
        ).fetchone()
        existing_selection = connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id=?',
            (USER_ID,),
        ).fetchone()
    assert existing_membership == ('owner', 'active')
    assert existing_selection == (existing.workspace_id,)
