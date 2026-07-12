from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.contacts import contact_confirm, start_add_contact_intake
from bot.services.access_control import AccessControlService
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import WorkspaceContextService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_ID = 80801


def _supplier(name: str) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=USER_ID,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Address',
        iban='SK3112000000198742637541',
        swift='GIBASKBX',
        email='owner@example.test',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
    )


def _contact(name: str, workspace_id: str) -> ContactProfile:
    return ContactProfile(
        workspace_id=workspace_id,
        supplier_telegram_id=USER_ID,
        name=name,
        ico='87654321',
        dic='0987654321',
        ic_dph=None,
        address='Customer address',
        email='customer@example.test',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=None,
    )


def _contexts(db_path: Path):
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=999,
        role='owner',
    )
    profiles = WorkspaceProfileService(db_path)
    first = profiles.create_profile(
        actor_telegram_id=USER_ID,
        profile=_supplier('First business'),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id='ws_first',
        storage_key='first-business',
    )
    second = profiles.create_profile(
        actor_telegram_id=USER_ID,
        profile=_supplier('Second business'),
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
        make_active=False,
        workspace_id='ws_second',
        storage_key='second-business',
    )
    return first, second


def test_same_contact_name_is_isolated_between_workspaces(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second = _contexts(db_path)
    service = WorkspaceContactService(db_path)

    first_contact = service.create_or_replace(
        first,
        _contact('Shared Customer', first.workspace_id),
    )
    second_contact = service.create_or_replace(
        second,
        _contact('Shared Customer', second.workspace_id),
    )

    assert first_contact.id != second_contact.id
    assert first_contact.workspace_id == first.workspace_id
    assert second_contact.workspace_id == second.workspace_id
    assert [row.id for row in service.list_contacts(first)] == [first_contact.id]
    assert [row.id for row in service.list_contacts(second)] == [second_contact.id]
    assert service.get_by_id(first, second_contact.id) is None
    assert service.get_by_id(second, first_contact.id) is None


def test_legacy_contact_api_fails_closed_for_multiple_profiles(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second = _contexts(db_path)
    WorkspaceContactService(db_path).create_or_replace(
        first,
        _contact('Customer', first.workspace_id),
    )

    with pytest.raises(
        RuntimeError,
        match='ambiguous_contact_scope_requires_workspace',
    ):
        ContactService(db_path).get_all_by_supplier(USER_ID)


def test_workspace_contact_rejects_actor_and_workspace_mismatch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second = _contexts(db_path)
    service = WorkspaceContactService(db_path)

    with pytest.raises(ValueError, match='contact_workspace_mismatch'):
        service.create_or_replace(
            first,
            _contact('Wrong workspace', second.workspace_id),
        )

    wrong_actor = _contact('Wrong actor', first.workspace_id)
    wrong_actor.supplier_telegram_id = 999
    with pytest.raises(ValueError, match='contact_actor_mismatch'):
        service.create_or_replace(first, wrong_actor)

    assert service.list_contacts(first) == []
    assert service.list_contacts(second) == []

def test_same_alias_resolves_independently_per_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second = _contexts(db_path)
    service = WorkspaceContactService(db_path)
    first_contact = service.create_or_replace(
        first,
        _contact('First Legal Name', first.workspace_id),
    )
    second_contact = service.create_or_replace(
        second,
        _contact('Second Legal Name', second.workspace_id),
    )

    service.create_confirmed_alias(
        first,
        alias_text='Shared spoken customer',
        contact_id=first_contact.id,
        source='test',
    )
    service.create_confirmed_alias(
        second,
        alias_text='Shared spoken customer',
        contact_id=second_contact.id,
        source='test',
    )

    first_result = service.resolve_contact_lookup(first, 'Shared spoken customer')
    second_result = service.resolve_contact_lookup(second, 'Shared spoken customer')
    assert first_result.state == 'alias_match'
    assert second_result.state == 'alias_match'
    assert first_result.matched_contact.id == first_contact.id
    assert second_result.matched_contact.id == second_contact.id


def test_workspace_alias_rejects_foreign_contact_id(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second = _contexts(db_path)
    service = WorkspaceContactService(db_path)
    foreign = service.create_or_replace(
        second,
        _contact('Foreign', second.workspace_id),
    )

    with pytest.raises(ValueError, match='contact_alias_workspace_mismatch'):
        service.create_confirmed_alias(
            first,
            alias_text='Foreign alias',
            contact_id=foreign.id,
            source='test',
        )

    assert service.resolve_contact_lookup(first, 'Foreign alias').state == 'no_match'

class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self) -> None:
        self.from_user = _DummyUser(USER_ID)
        self.text = ''
        self.answers: list[str] = []

    async def answer(self, text: str, **_kwargs) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}
        self.state = None

    async def clear(self) -> None:
        self.data = {}
        self.state = None

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self):
        return dict(self.data)

    async def set_state(self, value) -> None:
        self.state = value

    async def get_state(self):
        return self.state


def _config(db_path: Path, tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset({USER_ID}),
        admin_telegram_user_ids=frozenset(),
    )


def test_contact_fsm_keeps_starting_workspace_after_active_switch(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second = _contexts(db_path)
    message = _DummyMessage()
    state = _DummyState()
    config = _config(db_path, tmp_path)

    asyncio.run(
        start_add_contact_intake(message=message, state=state, config=config)
    )
    assert state.data['contact_workspace_id'] == first.workspace_id
    WorkspaceContextService(db_path).set_active_workspace(USER_ID, second.workspace_id)
    state.data.update(
        {
            'name': 'FSM Customer',
            'ico': '87654321',
            'dic': '0987654321',
            'ic_dph': '',
            'address': 'Customer 1',
            'email': 'customer@example.test',
            'contact_person': '',
        }
    )

    asyncio.run(
        contact_confirm(
            message=message,
            state=state,
            config=config,
            canonical_decision='yes',
        )
    )

    service = WorkspaceContactService(db_path)
    assert service.get_by_name(first, 'FSM Customer') is not None
    assert service.get_by_name(second, 'FSM Customer') is None

def test_confirmed_service_alias_is_isolated_by_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second = _contexts(db_path)
    assert first.supplier_id is not None
    assert second.supplier_id is not None
    service = ServiceAliasService(db_path)
    service.create_mapping(first.supplier_id, 'servis', 'First service')
    service.create_mapping(second.supplier_id, 'servis', 'Second service')
    first_mapping = service.get_mapping_by_alias(
        supplier_id=first.supplier_id,
        service_short_name='servis',
    )
    second_mapping = service.get_mapping_by_alias(
        supplier_id=second.supplier_id,
        service_short_name='servis',
    )
    assert first_mapping is not None
    assert second_mapping is not None

    assert service.create_confirmed_service_alias(
        supplier_telegram_id=USER_ID,
        supplier_id=first.supplier_id,
        alias_text='shared spoken service',
        service_alias_id=first_mapping.id,
        source='test',
        workspace_id=first.workspace_id,
    )
    assert service.create_confirmed_service_alias(
        supplier_telegram_id=USER_ID,
        supplier_id=second.supplier_id,
        alias_text='shared spoken service',
        service_alias_id=second_mapping.id,
        source='test',
        workspace_id=second.workspace_id,
    )

    first_result = service.resolve_confirmed_service_alias(
        supplier_telegram_id=USER_ID,
        supplier_id=first.supplier_id,
        alias_text='shared spoken service',
        workspace_id=first.workspace_id,
    )
    second_result = service.resolve_confirmed_service_alias(
        supplier_telegram_id=USER_ID,
        supplier_id=second.supplier_id,
        alias_text='shared spoken service',
        workspace_id=second.workspace_id,
    )
    assert first_result is not None
    assert second_result is not None
    assert first_result.service_display_name == 'First service'
    assert second_result.service_display_name == 'Second service'
    assert service.resolve_confirmed_service_alias(
        supplier_telegram_id=USER_ID,
        supplier_id=first.supplier_id,
        alias_text='shared spoken service',
    ) is None