from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path

from bot.config import Config
from bot.handlers.work_time import WorkTimeStates
from bot.services.active_fsm_guard import (
    ACTIVE_FSM_EXPIRED_MESSAGE,
    ACTIVE_FSM_LAST_ACTIVITY_AT_KEY,
    ACTIVE_FSM_STALE_MESSAGE,
    ActiveFsmMessageMiddleware,
    handle_active_fsm_text_update,
    touch_active_fsm_activity,
)
from bot.services.db import init_db


USER_ID = 770001


class _DummyUser:
    def __init__(self, user_id: int = USER_ID) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.from_user = _DummyUser()
        self.answers: list[str] = []
        self.message_id = 99

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self, current_state: str | None, data: dict | None = None) -> None:
        self.current_state = current_state
        self.data = dict(data or {})
        self.cleared = False

    async def get_state(self) -> str | None:
        return self.current_state

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.cleared = True
        self.current_state = None
        self.data.clear()

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state


def _config(tmp_path: Path, *, api_key: str | None = None) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=api_key,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'active-fsm-guard.db',
        storage_dir=tmp_path,
    )


def _fresh_data() -> dict:
    return {ACTIVE_FSM_LAST_ACTIVITY_AT_KEY: datetime.now(UTC).isoformat()}


def _stale_data(minutes: int = 60) -> dict:
    return {ACTIVE_FSM_LAST_ACTIVITY_AT_KEY: (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()}


def test_active_text_show_main_menu_clears_state_and_uses_existing_menu(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'show_main_menu'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    message = _DummyMessage('ukaz moznosti')
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state, _fresh_data())

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert state.cleared is True
    assert 'Všetky používateľské možnosti' in message.answers[-1]


def test_active_text_resume_start_status_clears_state_and_uses_start_router(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'resume_start_status'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    init_db(_config(tmp_path).db_path)
    message = _DummyMessage('zacni odznova')
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state, _fresh_data())

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert 'profil dodávateľa' in message.answers[-1]


def test_active_text_cancel_current_flow_uses_state_control_cancel(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'cancel_current_flow'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    message = _DummyMessage('zrus to')
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state, _fresh_data())

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert message.answers == ['Rozpracovaná akcia bola zrušená. Bot je v režime čakania.']


def test_active_text_pass_through_is_not_swallowed_and_stamps_after_handler(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'pass_through'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    state = _DummyState(WorkTimeStates.waiting_close_input.state, _fresh_data())
    message = _DummyMessage('16:30')
    calls: list[str] = []

    async def _handler(event, data):
        calls.append(event.text)

    asyncio.run(
        ActiveFsmMessageMiddleware()(
            _handler,
            message,
            {'state': state, 'config': _config(tmp_path)},
        )
    )

    assert calls == ['16:30']
    assert ACTIVE_FSM_LAST_ACTIVITY_AT_KEY in state.data


def test_active_navigation_resolver_error_fails_open_for_fresh_update(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        raise RuntimeError('resolver unavailable')

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    state = _DummyState(WorkTimeStates.waiting_close_input.state, _fresh_data())
    message = _DummyMessage('16:30')
    calls: list[str] = []

    async def _handler(event, data):
        calls.append(event.text)

    asyncio.run(
        ActiveFsmMessageMiddleware()(
            _handler,
            message,
            {'state': state, 'config': _config(tmp_path)},
        )
    )

    assert calls == ['16:30']


def test_stale_state_new_business_text_clears_then_routes_idle_once(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'pass_through'

    routed: list[tuple[str, str]] = []

    async def _route(**kwargs) -> None:
        routed.append((kwargs['text'], kwargs['input_channel']))

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    monkeypatch.setattr('bot.services.active_fsm_guard._route_through_idle_top_level', _route)
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state, _stale_data())
    message = _DummyMessage('vytvor fakturu pre Tech Company za servis 100 eur')

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert state.cleared is True
    assert message.answers == [ACTIVE_FSM_STALE_MESSAGE]
    assert routed == [(message.text, 'text')]


def test_stale_approve_like_text_fails_closed_and_does_not_route(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'pass_through'

    async def _route(**kwargs) -> None:
        raise AssertionError('stale approve-like text must not be replayed to idle routing')

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    monkeypatch.setattr('bot.services.active_fsm_guard._route_through_idle_top_level', _route)
    state = _DummyState(WorkTimeStates.waiting_delete_month_confirm.state, _stale_data())
    message = _DummyMessage('ano')

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert message.answers == [ACTIVE_FSM_EXPIRED_MESSAGE]


def test_legacy_state_without_timestamp_approve_like_text_fails_closed(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'pass_through'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state)
    message = _DummyMessage('schváliť')

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert message.answers == [ACTIVE_FSM_EXPIRED_MESSAGE]


def test_legacy_state_without_timestamp_clear_top_level_request_routes_idle(tmp_path: Path, monkeypatch) -> None:
    async def _resolver(**kwargs) -> str:
        return 'pass_through'

    async def _probe(**kwargs) -> bool:
        return True

    routed: list[str] = []

    async def _route(**kwargs) -> None:
        routed.append(kwargs['text'])

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _resolver)
    monkeypatch.setattr('bot.services.active_fsm_guard._looks_like_top_level_request', _probe)
    monkeypatch.setattr('bot.services.active_fsm_guard._route_through_idle_top_level', _route)
    state = _DummyState(WorkTimeStates.waiting_manual_range_confirm.state)
    message = _DummyMessage('vytvor fakturu pre Tech Company za servis 100 eur')

    handled = asyncio.run(
        handle_active_fsm_text_update(
            message=message,
            state=state,
            config=_config(tmp_path),
            text=message.text,
            input_channel='text',
        )
    )

    assert handled is True
    assert state.current_state is None
    assert routed == [message.text]


def test_touch_activity_records_started_and_last_activity_without_clearing_state() -> None:
    state = _DummyState(WorkTimeStates.waiting_close_input.state)

    asyncio.run(touch_active_fsm_activity(state))

    assert state.current_state == WorkTimeStates.waiting_close_input.state
    assert ACTIVE_FSM_LAST_ACTIVITY_AT_KEY in state.data