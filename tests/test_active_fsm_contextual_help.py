from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import InvoiceStates
from bot.handlers.work_time import WorkTimeStates
from bot.services.active_fsm_state_descriptors import (
    all_registered_state_prefixes,
    describe_active_fsm_state,
    render_active_fsm_help,
)
from bot.services.active_fsm_guard import (
    ACTIVE_FSM_LAST_ACTIVITY_AT_KEY,
    handle_contextual_info_help_recovery,
    handle_active_fsm_text_update,
)


class _User:
    id = 101


class _Chat:
    id = 202


class _Message:
    def __init__(self, text: str) -> None:
        self.text = text
        self.from_user = _User()
        self.chat = _Chat()
        self.answers = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append((text, kwargs))


class _State:
    def __init__(self, value: str) -> None:
        self.value = value
        self.data = {ACTIVE_FSM_LAST_ACTIVITY_AT_KEY: datetime.now(UTC).isoformat()}
        self.cleared = False

    async def get_state(self):
        return self.value

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def clear(self):
        self.cleared = True
        self.value = None


def _config(tmp_path: Path) -> Config:
    return Config(bot_token='token', openai_api_key=None, openai_stt_model='whisper-1',
                  openai_llm_model='gpt-4o', debug_invoice_transparency=False,
                  db_path=tmp_path / 'db.sqlite', storage_dir=tmp_path)


def test_invoice_and_work_time_states_have_python_owned_descriptors() -> None:
    invoice = describe_active_fsm_state(InvoiceStates.waiting_input.state)
    work = describe_active_fsm_state(WorkTimeStates.waiting_close_input.state)

    assert invoice.action_id == 'create_invoice'
    assert invoice.expected_input_kind == 'text'
    assert work.action_id == 'work_time'
    assert 'čas' in work.expected_input.casefold()


def test_every_reachable_state_group_has_registered_prefix() -> None:
    assert all_registered_state_prefixes() == {
        'AccountingDocumentIntakeStates', 'BusinessProfileStates', 'ContactStates',
        'CustomizationRequestAdminResponseStates', 'CustomizationRequestStates',
        'DeleteUserDatabaseStates', 'InvoiceStates', 'OfficeFlowAttachmentRouterStates',
        'OnboardingStates', 'ServiceAliasStates', 'SupplierProfileEditStates',
        'WorkTimeStates',
    }


def test_renderer_has_required_copy_and_menu_callback() -> None:
    text, keyboard = render_active_fsm_help(InvoiceStates.waiting_input.state)

    assert text.startswith('Teraz vykonávate:')
    assert '\nAktuálny krok:' in text
    button = keyboard.inline_keyboard[0][0]
    assert button.text == 'Hlavné menu'
    assert button.callback_data == 'navigation:show_main_menu'


def test_describe_active_flow_preserves_fsm(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs):
        return 'describe_active_flow'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    state = _State(InvoiceStates.waiting_input.state)
    message = _Message('čo teraz robíme?')

    handled = asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path), text=message.text,
        input_channel='text'))

    assert handled is True
    assert state.value == InvoiceStates.waiting_input.state
    assert state.cleared is False
    assert message.answers[0][0].startswith('Teraz vykonávate:')


def test_describe_expected_input_preserves_fsm(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs):
        return 'describe_expected_input'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    state = _State(WorkTimeStates.waiting_close_input.state)
    message = _Message('čo odo mňa potrebuješ?')

    handled = asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path), text=message.text,
        input_channel='text'))

    assert handled is True
    assert state.value == WorkTimeStates.waiting_close_input.state
    assert 'čas' in message.answers[0][0].casefold()


def test_active_contextual_recovery_preserves_fsm(tmp_path: Path, monkeypatch) -> None:
    async def _navigation(**kwargs):
        return 'contextual_recovery'

    calls = []

    async def _recovery(**kwargs):
        calls.append(kwargs)
        await kwargs['message'].answer('state-aware recovery')

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _navigation)
    monkeypatch.setattr('bot.services.active_fsm_guard.handle_contextual_info_help_recovery', _recovery)
    state = _State(InvoiceStates.waiting_input.state)
    message = _Message('myslel som zákazníka')

    handled = asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path), text=message.text,
        input_channel='text'))

    assert handled is True
    assert state.value == InvoiceStates.waiting_input.state
    assert calls[0]['active_state_descriptor'].action_id == 'create_invoice'

def test_genuinely_unclear_active_recovery_is_state_aware(tmp_path: Path) -> None:
    state = _State(InvoiceStates.waiting_input.state)
    message = _Message('???')

    asyncio.run(handle_contextual_info_help_recovery(
        message=message,
        state=state,
        config=_config(tmp_path),
        text=message.text,
        input_channel='text',
        active_state_descriptor=describe_active_fsm_state(state.value),
    ))

    assert state.value == InvoiceStates.waiting_input.state
    assert state.cleared is False
    assert message.answers[0][0].startswith('Tejto odpovedi som nerozumel.')
    assert message.answers[0][1]['reply_markup'].inline_keyboard[0][0].text == 'Hlavné menu'


def test_resolver_failure_still_passes_normal_state_input(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs):
        raise RuntimeError('offline')

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    state = _State(InvoiceStates.waiting_input.state)
    message = _Message('ACME, servis 100 eur')

    handled = asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path), text=message.text,
        input_channel='text'))

    assert handled is False
    assert state.value == InvoiceStates.waiting_input.state
