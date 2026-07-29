from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import process_invoice_text
from bot.handlers.business_profiles import (
    BusinessProfileStates,
    business_profile_selection,
    business_profile_switch_confirm,
    cmd_business_profiles,
    start_switch_business_profile,
)
from bot.services.access_control import AccessControlService
from bot.services.db import init_db
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_context import WorkspaceContextService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_ID = 81801


class _User:
    id = USER_ID


class _Message:
    def __init__(self, text: str = '') -> None:
        self.text = text
        self.from_user = _User()
        self.answers: list[str] = []
        self.markups: list[object] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)
        self.markups.append(kwargs.get('reply_markup'))


class _State:
    def __init__(self, current_state: str | None = None) -> None:
        self.current_state = current_state
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


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'bot.db',
        storage_dir=tmp_path,
    )


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


def _setup(config: Config):
    init_db(config.db_path)
    AccessControlService(config.db_path).approve_user(
        telegram_id=USER_ID,
        approved_by=999,
        role='owner',
    )
    profiles = WorkspaceProfileService(config.db_path)
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


def test_profily_lists_and_switches_exact_accessible_profile(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _first, second = _setup(config)
    state = _State()
    message = _Message('/profily')

    asyncio.run(cmd_business_profiles(message, state, config))
    assert state.current_state == BusinessProfileStates.waiting_selection.state
    assert 'First business (aktívny)' in message.answers[-1]

    selection_message = _Message('Second business')
    asyncio.run(business_profile_selection(selection_message, state, config))
    assert getattr(selection_message.markups[-1], 'remove_keyboard', False) is True
    active = WorkspaceContextService(config.db_path).resolve_for_user(USER_ID)
    assert active.workspace_id == second.workspace_id
    assert state.current_state is None


def test_profily_does_not_clear_or_switch_foreign_active_fsm(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first, _second = _setup(config)
    state = _State('InvoiceStates:confirm')
    state.data['draft'] = {'invoice_number': '20260001'}
    message = _Message('/profily')

    asyncio.run(cmd_business_profiles(message, state, config))

    assert state.current_state == 'InvoiceStates:confirm'
    assert state.data['draft'] == {'invoice_number': '20260001'}
    assert WorkspaceContextService(config.db_path).resolve_for_user(USER_ID).workspace_id == first.workspace_id


def test_voice_switch_requires_confirmation_before_mutation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    first, second = _setup(config)
    state = _State()

    asyncio.run(
        start_switch_business_profile(
            message=_Message('Second business'),
            state=state,
            config=config,
            profile_ref='Second business',
            source_channel='voice',
        )
    )
    assert state.current_state == BusinessProfileStates.waiting_switch_confirm.state
    assert WorkspaceContextService(config.db_path).resolve_for_user(USER_ID).workspace_id == first.workspace_id

    asyncio.run(
        business_profile_switch_confirm(
            _Message('ano'),
            state,
            config,
        )
    )
    assert WorkspaceContextService(config.db_path).resolve_for_user(USER_ID).workspace_id == second.workspace_id

def test_idle_text_router_switches_only_to_accessible_workspace(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _first, second = _setup(config)
    state = _State()
    message = _Message('Prepnúť profil na Second business')

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=message.text,
        )
    )

    assert WorkspaceContextService(config.db_path).resolve_for_user(USER_ID).workspace_id == second.workspace_id
    assert 'Second business' in message.answers[-1]


def test_business_profile_cancel_removes_reply_keyboard(tmp_path: Path) -> None:
    config = _config(tmp_path)
    _setup(config)
    state = _State()
    asyncio.run(cmd_business_profiles(_Message('/profily'), state, config))
    cancel_message = _Message('Zru\u0161i\u0165')

    asyncio.run(business_profile_selection(cancel_message, state, config))

    assert state.current_state is None
    assert getattr(cancel_message.markups[-1], 'remove_keyboard', False) is True
