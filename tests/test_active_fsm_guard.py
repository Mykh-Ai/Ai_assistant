from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from pathlib import Path
from dataclasses import replace

import pytest

from bot.config import Config
from bot.handlers.invoice import CustomizationRequestStates
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


@pytest.mark.parametrize('action,kind,source', [
    ('unknown', 'unknown', 'llm_bundle'),
    ('unknown', 'capability_or_howto', 'llm_bundle'),
    ('unknown', 'contextual_help', 'llm_bundle'),
    ('add_receipt', 'business_action', 'llm_bundle'),
    ('edit_invoice', 'business_action', 'llm_bundle'),
    ('send_invoice', 'business_action', 'llm_bundle'),
    ('open_work_day', 'business_action', 'python_fallback_after_llm'),
    ('invented_action', 'business_action', 'llm_bundle'),
])
def test_empty_upload_unresolved_or_nonexecutable_bundle_preserves_source(
    tmp_path, monkeypatch, action, kind, source,
) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates

    calls = []

    async def _navigation(**kwargs):
        return 'pass_through'

    async def _primary(**kwargs):
        calls.append(kwargs)
        kwargs['diagnostics'].update(resolution_source=source, routing_kind=kind)
        return action

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _navigation)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state, _fresh_data())
    before = dict(state.data)
    message = _DummyMessage('Vieš evidovať pracovný čas?')
    handled = asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path),
        text=message.text, input_channel='text',
    ))
    assert handled is False
    assert len(calls) == 1
    assert state.current_state == AccountingDocumentIntakeStates.waiting_upload.state
    assert state.data == before
    assert not state.cleared and not message.answers


@pytest.mark.parametrize('extra', [
    {'accounting_document_candidate': {}},
    {'accounting_document_temp_original_path': ''},
    {'accounting_document_upload_started': True},
    {'intake_expires_at': 'future'},
    {'unrecognized_metadata': None},
])
def test_nonempty_upload_never_calls_primary_or_clears(tmp_path, monkeypatch, extra) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates

    async def _navigation(**kwargs):
        return 'pass_through'

    async def _primary(**kwargs):
        raise AssertionError('nonempty source belongs to its state handler')

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _navigation)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state, {**_fresh_data(), **extra})
    before = dict(state.data)
    message = _DummyMessage('Otvor pracovný deň')
    assert asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path),
        text=message.text, input_channel='text',
    )) is False
    assert state.data == before and not state.cleared


def test_empty_upload_changed_during_primary_is_not_discarded(tmp_path, monkeypatch) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates

    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state, _fresh_data())

    async def _navigation(**kwargs):
        return 'pass_through'

    async def _primary(**kwargs):
        await state.update_data(accounting_document_upload_started=True)
        kwargs['diagnostics'].update(resolution_source='llm_bundle', routing_kind='business_action')
        return 'open_work_day'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _navigation)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    message = _DummyMessage('Otvor pracovný deň')
    assert asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path),
        text=message.text, input_channel='text',
    )) is False
    assert state.data['accounting_document_upload_started'] is True
    assert not state.cleared and not message.answers


def test_empty_upload_model_outage_does_not_use_local_action(tmp_path, monkeypatch) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates

    class _Unavailable:
        def __init__(self, **kwargs):
            raise RuntimeError('unavailable')

    async def _navigation(**kwargs):
        return 'pass_through'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _navigation)
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _Unavailable)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state, _fresh_data())
    before = dict(state.data)
    message = _DummyMessage('otvor pracovny den')
    assert asyncio.run(handle_active_fsm_text_update(
        message=message, state=state, config=_config(tmp_path, api_key='sk-test'),
        text=message.text, input_channel='text',
    )) is False
    assert state.data == before and not state.cleared


def test_empty_upload_claim_serializes_with_upload_across_fsm_contexts(tmp_path, monkeypatch) -> None:
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage
    from bot.handlers.accounting_document_intake import (
        AccountingDocumentIntakeStates, accounting_document_upload,
        claim_empty_accounting_upload, empty_accounting_upload_snapshot,
    )

    async def _scenario():
        storage = MemoryStorage()
        key = StorageKey(bot_id=1, chat_id=123, user_id=123)
        started, release = asyncio.Event(), asyncio.Event()

        class _SlowClear(FSMContext):
            async def clear(self):
                started.set()
                await release.wait()
                await super().clear()

        first = _SlowClear(storage=storage, key=key)
        second = FSMContext(storage=storage, key=key)
        foreign = FSMContext(storage=storage, key=StorageKey(bot_id=1, chat_id=456, user_id=456))
        await first.set_state(AccountingDocumentIntakeStates.waiting_upload)
        await first.set_data(_fresh_data())
        snapshot = await empty_accounting_upload_snapshot(first)
        assert await empty_accounting_upload_snapshot(foreign) is None
        claim = asyncio.create_task(claim_empty_accounting_upload(first, snapshot))
        await started.wait()
        upload = asyncio.create_task(accounting_document_upload(
            _DummyMessage('attachment'), second, _config(tmp_path), object(),
        ))
        await asyncio.sleep(0)
        assert not upload.done()
        release.set()
        assert await claim is True
        await upload  # Source is gone: no download, LMM or path creation.
        assert await second.get_state() is None and await second.get_data() == {}
        assert await foreign.get_data() == {}

    asyncio.run(_scenario())


def test_upload_started_before_candidate_blocks_empty_claim(tmp_path, monkeypatch) -> None:
    from bot.handlers.accounting_document_intake import (
        AccountingDocumentIntakeStates, accounting_document_upload,
        claim_empty_accounting_upload, empty_accounting_upload_snapshot,
    )

    monkeypatch.setattr('bot.handlers.accounting_document_intake._extract_supported_attachment', lambda message: None)

    async def _scenario():
        state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state, _fresh_data())
        before = await empty_accounting_upload_snapshot(state)
        await accounting_document_upload(_DummyMessage('file'), state, _config(tmp_path), object())
        assert state.data['accounting_document_upload_started'] is True
        assert await empty_accounting_upload_snapshot(state) is None
        assert await claim_empty_accounting_upload(state, before) is False
        assert not state.cleared

    asyncio.run(_scenario())


@pytest.mark.parametrize('channel', ['text', 'voice'])
def test_empty_upload_interrupt_still_requires_authorization(tmp_path, monkeypatch, channel) -> None:
    from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
    from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE

    config = replace(_config(tmp_path), allowed_telegram_user_ids=frozenset({USER_ID + 1}))
    init_db(config.db_path)
    state = _DummyState(AccountingDocumentIntakeStates.waiting_upload.state, _fresh_data())
    message = _DummyMessage('Otvor pracovný deň' if channel == 'text' else '')
    if channel == 'voice':
        message.voice = type('_Voice', (), {'file_id': 'blocked'})()

    async def _unexpected(*args, **kwargs):
        raise AssertionError('unauthorized user must not reach guard/STT/primary/owner')

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', _unexpected)
    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _unexpected)
    asyncio.run(TelegramUserAuthorizationMiddleware()(
        _unexpected, message, {'state': state, 'config': config},
    ))
    assert message.answers == [UNAUTHORIZED_MESSAGE]
    assert state.current_state is None  # Existing access-rejection cleanup.


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


def test_info_help_offer_menu_control_removes_owned_inline_keyboard(tmp_path: Path) -> None:
    class _Bot:
        def __init__(self) -> None:
            self.edits: list[tuple[int, int, object | None]] = []

        async def edit_message_reply_markup(self, *, chat_id, message_id, reply_markup=None) -> None:
            self.edits.append((chat_id, message_id, reply_markup))

    message = _DummyMessage('/menu')
    message.chat = type('Chat', (), {'id': USER_ID + 1000})()
    message.bot = _Bot()
    state = _DummyState(
        CustomizationRequestStates.waiting_admin_offer_decision.state,
        {
            **_fresh_data(),
            'info_help_offer_message_id': 501,
            'info_help_offer_chat_id': USER_ID + 1000,
        },
    )

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
    assert state.cleared is True
    assert message.bot.edits == [(USER_ID + 1000, 501, None)]
    assert 'Všetky používateľské možnosti' in message.answers[-1]


def test_info_help_offer_keyboard_cleanup_failure_does_not_block_menu(
    tmp_path: Path, caplog
) -> None:
    class _FailingBot:
        async def edit_message_reply_markup(self, **kwargs) -> None:
            raise RuntimeError('cleanup failed')

    message = _DummyMessage('/menu')
    message.chat = type('Chat', (), {'id': USER_ID + 1000})()
    message.bot = _FailingBot()
    state = _DummyState(
        CustomizationRequestStates.waiting_admin_offer_decision.state,
        {
            **_fresh_data(),
            'info_help_offer_message_id': 502,
            'info_help_offer_chat_id': USER_ID + 1000,
        },
    )

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
    assert state.cleared is True
    assert 'Všetky používateľské možnosti' in message.answers[-1]
    assert 'Failed to clear InfoHelp admin-offer inline keyboard' in caplog.text


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
