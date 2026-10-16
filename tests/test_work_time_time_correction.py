from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import sqlite3

import pytest
from aiogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.config import Config
from bot.handlers.invoice import process_invoice_text
from bot.handlers import voice
from bot.handlers.work_time import (
    WorkTimeStates, start_open_work_day, start_close_work_day,
    work_time_open_input, work_time_open_preview_confirm, work_time_close_preview_confirm,
)
from bot.services.active_fsm_guard import ACTIVE_FSM_LAST_ACTIVITY_AT_KEY, handle_active_fsm_text_update
from bot.services.db import init_db
from bot.services.work_time import WorkTimeService


class State:
    current = None

    def __init__(self):
        self.data = {}

    async def get_state(self):
        return self.current

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs):
        self.data.update(kwargs)

    async def set_state(self, value):
        self.current = getattr(value, 'state', value)

    async def clear(self):
        self.current = None
        self.data.clear()


class Message:
    def __init__(self, text='', actor=1001):
        self.text = text
        self.from_user = type('User', (), {'id': actor})()
        self.message_id = 99
        self.answers = []
        self.markup = []

    async def answer(self, text, **kwargs):
        self.answers.append(text)
        self.markup.append(kwargs.get('reply_markup'))


@pytest.fixture
def setup(tmp_path, monkeypatch):
    config = Config(
        bot_token='test', openai_api_key='sk-test', openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o', debug_invoice_transparency=False,
        db_path=tmp_path/'time.db', storage_dir=tmp_path,
    )
    init_db(config.db_path)
    now = datetime(2026, 10, 16, 18, 0)
    monkeypatch.setattr('bot.services.work_time.work_time_local_now', lambda value=None: value or now)
    monkeypatch.setattr('bot.handlers.work_time.work_time_local_now', lambda value=None: value or now)
    service = WorkTimeService(config.db_path)
    service.save_lunch_break_settings(telegram_id=1001, enabled=True, minutes=30)
    return config, service


def fake_models(monkeypatch, *, field, work_date='2026-10-16', value='06:54'):
    payloads = []

    class Model:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': self})()

        async def create(self, **kwargs):
            payload = json.loads(kwargs['messages'][1]['content'])
            payloads.append(payload)
            if payload['context_name'] == 'top_level_action':
                result = {'canonical_action': 'open_work_day' if field == 'start_time' else 'close_work_day', 'routing_kind': 'business_action'}
            else:
                result = {
                    'canonical': 'work_time_entry', 'mode': 'open_at_time' if field == 'start_time' else 'close_at_time',
                    'date': work_date, 'start_time': value if field == 'start_time' else None,
                    'end_time': value if field == 'end_time' else None, 'duration_minutes': None,
                }
            response = type('Response', (), {})()
            response.choices = [type('Choice', (), {'message': type('Content', (), {'content': json.dumps(result)})()})()]
            return response

    monkeypatch.setattr('bot.services.work_time.AsyncOpenAI', Model)
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', Model)
    return payloads


def seed(service, *, closed=True, date='2026-10-16'):
    day = service.open_day(telegram_id=1001, now=datetime.fromisoformat(date+'T06:47')).day
    if closed:
        day = service.close_open_day(telegram_id=1001, end_datetime=datetime.fromisoformat(date+'T15:39')).day
    return day


@pytest.mark.parametrize('channel', ['text', 'voice'])
@pytest.mark.parametrize('field,closed,value', [
    ('start_time', False, '06:54'), ('start_time', True, '06:54'),
    ('end_time', True, '15:20'), ('end_time', False, '15:39'),
])
def test_public_new_explicit_time_supersedes_stored_boundary(setup, monkeypatch, channel, field, closed, value):
    config, service = setup
    original = seed(service, closed=closed)
    payloads = fake_models(monkeypatch, field=field, value=value)
    state, message = State(), Message(f'Oprav dnes {"prichod" if field == "start_time" else "odchod"} na {value}.')

    class Bot:
        async def get_file(self, file_id):
            return type('File', (), {'file_path': 'fixture.ogg'})()

        async def download_file(self, file_path, destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b'fixture')

    async def stt(*args, **kwargs):
        return message.text

    monkeypatch.setattr('bot.handlers.voice.transcribe_audio', stt)

    async def journey():
        if channel == 'voice':
            message.voice = type('Voice', (), {'file_id': 'fixture'})()
            await voice.handle_voice(message, Bot(), config, state)
        else:
            await process_invoice_text(message=message, state=state, config=config, invoice_text=message.text)
        assert service.get_day(telegram_id=1001, work_date=original.work_date) == original
        assert state.current in {WorkTimeStates.waiting_open_preview_confirm.state, WorkTimeStates.waiting_close_preview_confirm.state}
        assert 'Povodne: 06:47' in message.answers[-1]
        assert value in message.answers[-1]
        assert isinstance(message.markup[-1], ReplyKeyboardMarkup)
        confirm = work_time_open_preview_confirm if field == 'start_time' else work_time_close_preview_confirm
        reply = Message('Schváliť')
        await confirm(reply, state, config)
        assert isinstance(reply.markup[-1], ReplyKeyboardRemove)
        result = service.get_day(telegram_id=1001, work_date=original.work_date)
        assert result.id == original.id
        assert getattr(result, field) == value
        other = 'end_time' if field == 'start_time' else 'start_time'
        assert getattr(result, other) == getattr(original, other)
        if result.end_time:
            start_dt = datetime.fromisoformat(result.work_date+'T'+result.start_time)
            end_dt = datetime.fromisoformat(result.work_date+'T'+result.end_time)
            assert result.gross_minutes == int((end_dt-start_dt).total_seconds()//60)
            assert result.total_minutes == result.gross_minutes-30
            assert result.status == 'closed'
        else:
            assert result.status == 'open'
        assert state.current is None
        assert service.get_day(telegram_id=1002, work_date=original.work_date) is None

    asyncio.run(journey())
    assert len([p for p in payloads if p['context_name'] == 'top_level_action']) == 1
    assert [p for p in payloads if p['context_name'] != 'top_level_action'][0]['allow_boundary_correction'] is True
    with sqlite3.connect(config.db_path) as conn:
        assert conn.execute('SELECT count(*) FROM work_time_days').fetchone()[0] == 1
        assert conn.execute("SELECT count(*) FROM work_time_events WHERE event_type='time_correction'").fetchone()[0] == 1
    assert not list(config.storage_dir.rglob('*.ogg'))


def test_historical_end_correction_preserves_explicit_date_over_open_day(setup, monkeypatch):
    config, service = setup
    historical = seed(service, date='2026-09-09')
    today = service.open_day(telegram_id=1001, now=datetime(2026, 10, 16, 7, 0)).day
    fake_models(monkeypatch, field='end_time', work_date='2026-09-09', value='13:10')
    state = State()
    asyncio.run(start_close_work_day(Message(), state, config, text='Oprav odchod 9.9.2026 na 13:10'))
    asyncio.run(work_time_close_preview_confirm(Message('Schváliť'), state, config))
    changed = service.get_day(telegram_id=1001, work_date='2026-09-09')
    assert changed.id == historical.id and changed.end_time == '13:10'
    assert changed.start_time == historical.start_time
    assert service.get_open_day(telegram_id=1001) == today


@pytest.mark.parametrize('branch', ['unknown', 'cancel', 'edit'])
def test_correction_controls_and_final_reply_keyboard(setup, monkeypatch, branch):
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))
    reply = Message()
    asyncio.run(work_time_open_preview_confirm(reply, state, config, canonical_decision=branch))
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original
    assert state.current == {'unknown': WorkTimeStates.waiting_open_preview_confirm.state, 'edit': WorkTimeStates.waiting_open_input.state, 'cancel': None}[branch]
    assert isinstance(reply.markup[-1], ReplyKeyboardMarkup if branch == 'unknown' else ReplyKeyboardRemove)


@pytest.mark.parametrize('field,value', [('start_time','16:00'), ('start_time','23:59'), ('end_time','06:00'), ('end_time','23:59')])
def test_invalid_reverse_future_boundary_never_proposes_write(setup, field, value):
    _, service = setup
    original = seed(service)
    assert service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field=field, value=value) is None
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


@pytest.mark.parametrize('change_after_preview', ['row', 'lunch'])
def test_stale_snapshot_and_duplicate_approval_cannot_overwrite(setup, change_after_preview):
    _, service = setup
    original = seed(service)
    change = service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field='start_time', value='06:54')
    if change_after_preview == 'row':
        another = service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field='end_time', value='15:20')
        assert service.apply_boundary_change(telegram_id=1001, change=another).ok
    else:
        service.save_lunch_break_settings(telegram_id=1001, enabled=False, minutes=0)
    before = service.get_day(telegram_id=1001, work_date=original.work_date)
    assert service.apply_boundary_change(telegram_id=1001, change=change).reason == 'day_changed'
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == before
    fresh = service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field='start_time', value='06:54')
    assert service.apply_boundary_change(telegram_id=1001, change=fresh).ok
    assert service.apply_boundary_change(telegram_id=1001, change=fresh).reason == 'day_changed'
    no_op = service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field='start_time', value='06:54')
    assert service.apply_boundary_change(telegram_id=1001, change=no_op).reason == 'unchanged'


def test_audit_failure_rolls_back_and_other_workspace_cannot_apply(setup, monkeypatch):
    config, legacy = setup
    service = WorkTimeService(config.db_path, workspace_id='ws_first')
    original = seed(service)
    change = service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field='start_time', value='06:54')
    assert WorkTimeService(config.db_path, workspace_id='ws_second').apply_boundary_change(telegram_id=1001, change=change).reason == 'day_changed'
    assert legacy.apply_boundary_change(telegram_id=1001, change=change).reason == 'day_changed'

    def fail(*args, **kwargs):
        raise sqlite3.OperationalError('injected audit failure')

    monkeypatch.setattr(service, '_record_event', fail)
    with pytest.raises(sqlite3.OperationalError):
        service.apply_boundary_change(telegram_id=1001, change=change)
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


def test_duration_override_is_explicitly_replaced_by_confirmed_range(setup):
    _, service = setup
    service.open_day(telegram_id=1001, now=datetime(2026,10,16,7,10))
    original = service.close_open_day(telegram_id=1001, duration_minutes=360).day
    assert original.end_time == '13:40' and original.net_work_minutes_override == 360
    change = service.prepare_boundary_change(telegram_id=1001, work_date=original.work_date, field='end_time', value='13:10')
    result = service.apply_boundary_change(telegram_id=1001, change=change).day
    assert result.start_time == '07:10' and result.end_time == '13:10'
    assert result.gross_minutes == 360 and result.total_minutes == 330
    assert result.net_work_minutes_override is None and result.close_input_mode == 'explicit_end'


def test_no_time_repeat_and_fresh_preview_conflict_do_not_rewrite(setup, monkeypatch):
    config, service = setup
    original = seed(service, closed=False)
    config = replace(config, openai_api_key=None)
    asyncio.run(start_open_work_day(Message(), State(), config, text='Zacinam pracovny den'))
    assert service.get_open_day(telegram_id=1001) == original
    result = service.open_day(telegram_id=1001, start_datetime=datetime(2026,10,16,6,54), expected_no_day=True)
    assert not result.ok and result.reason == 'day_changed'


def test_expired_correction_removes_reply_keyboard_without_write(setup, monkeypatch):
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))
    state.data[ACTIVE_FSM_LAST_ACTIVITY_AT_KEY] = (datetime.now(UTC)-timedelta(hours=1)).isoformat()

    async def navigation(**kwargs):
        return 'pass_through'

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', navigation)
    reply = Message('Schváliť')
    assert asyncio.run(handle_active_fsm_text_update(message=reply,state=state,config=config,text=reply.text,input_channel='text'))
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original
    assert state.current is None and isinstance(reply.markup[-1], ReplyKeyboardRemove)


def test_historical_arrival_edit_keeps_bound_date(setup, monkeypatch):
    config, service = setup
    original = seed(service, date='2026-09-09')
    fake_models(monkeypatch, field='start_time', work_date='2026-09-09', value='07:10')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 9.9.2026 na 07:10'))
    asyncio.run(work_time_open_preview_confirm(Message(), state, config, canonical_decision='edit'))
    # Missing date in an edit reply defaults to the preserved historical row.
    fake_models(monkeypatch, field='start_time', work_date=None, value='07:15')
    asyncio.run(work_time_open_input(Message('07:15'), state, config))
    asyncio.run(work_time_open_preview_confirm(Message('Schváliť'), state, config))
    changed = service.get_day(telegram_id=1001, work_date='2026-09-09')
    assert changed.id == original.id and changed.start_time == '07:15'
    assert changed.end_time == original.end_time
    assert service.get_day(telegram_id=1001, work_date='2026-10-16') is None


@pytest.mark.parametrize('command', ['/cancel', '/menu', '/start'])
def test_correction_global_navigation_removes_reply_keyboard(setup, monkeypatch, command):
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))
    reply = Message(command)
    assert asyncio.run(handle_active_fsm_text_update(message=reply,state=state,config=config,text=command,input_channel='text'))
    assert state.current is None
    assert any(isinstance(markup, ReplyKeyboardRemove) for markup in reply.markup)
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


def test_old_inline_card_cannot_approve_or_remove_correction_ui(setup, monkeypatch):
    from bot.handlers.decision_callbacks import decision_callback
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))

    class Callback:
        data = 'decision:approve'
        message = Message()

        async def answer(self, *args, **kwargs):
            pass

    async def forbid_edit(**kwargs):
        raise AssertionError('unproven old card must not be edited')

    callback = Callback()
    callback.message.edit_reply_markup = forbid_edit
    asyncio.run(decision_callback(callback, state, config))
    assert state.current == WorkTimeStates.waiting_open_preview_confirm.state
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


def test_cleanup_send_failure_does_not_rollback_or_repeat_committed_change(setup, monkeypatch, caplog):
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))
    reply = Message('Schváliť')

    async def fail_answer(*args, **kwargs):
        raise RuntimeError('injected Telegram failure')

    reply.answer = fail_answer
    asyncio.run(work_time_open_preview_confirm(reply, state, config))
    assert state.current is None
    assert service.get_day(telegram_id=1001, work_date=original.work_date).start_time == '06:54'
    assert 'keyboard delivery failed' in caplog.text
    with sqlite3.connect(config.db_path) as conn:
        assert conn.execute("SELECT count(*) FROM work_time_events WHERE event_type='time_correction'").fetchone()[0] == 1


def test_closed_now_without_new_explicit_clock_does_not_overwrite(setup, monkeypatch):
    config, service = setup
    original = seed(service)
    config = replace(config, openai_api_key=None)
    state = State()
    asyncio.run(start_close_work_day(Message(), state, config, text='zatvor teraz'))
    assert state.current == WorkTimeStates.waiting_close_input.state
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


@pytest.mark.parametrize('text', ['Schváliť', '/start'])
def test_denied_actor_cannot_confirm_and_reply_keyboard_is_removed(setup, monkeypatch, text):
    from bot.services.authorization import TelegramUserAuthorizationMiddleware
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))
    config = replace(config, allowed_telegram_user_ids=frozenset({2002}))
    reply = Message(text)

    async def forbidden(*args, **kwargs):
        raise AssertionError('access denial must precede resolver/handler')

    asyncio.run(TelegramUserAuthorizationMiddleware()(forbidden,reply,{'state':state,'config':config}))
    assert state.current is None and isinstance(reply.markup[-1], ReplyKeyboardRemove)
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


def test_product_truth_explains_correction_without_executing(setup):
    from bot.services.info_help import build_product_truth_guidance
    from bot.services.product_truth import get_safe_answer_payload
    config, service = setup
    original = seed(service)
    # Existing Product Truth capability entry, not a claim of arbitrary help NLP.
    answer = build_product_truth_guidance(user_input_text='Vie bot evidovat odpracovane hodiny?')
    assert answer is not None and 'oprav dnesny prichod na 06:54' in answer
    assert 'po potvrdeni' in answer
    assert get_safe_answer_payload('work_time_tracking')['product_status'] == 'partial'
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


@pytest.mark.parametrize('mode,start,end,duration', [
    ('close_at_time','07:00','15:39',None),
    ('close_at_time',None,'15:39',360),
    ('close_now',None,'15:39',None),
    ('close_with_duration',None,'15:39',360),
    ('close_at_time','invalid','15:39',None),
    ('close_at_time',None,'15:39','invalid'),
    ('open_at_time','06:54','invalid',None),
])
def test_conflicting_close_slots_are_unknown_not_partial_corrections(setup, monkeypatch, mode, start, end, duration):
    from bot.services.work_time import resolve_work_time_entry_candidate
    config, service = setup
    original = seed(service)

    class Model:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': self})()

        async def create(self, **kwargs):
            result = {'canonical':'work_time_entry','mode':mode,'date':original.work_date,
                      'start_time':start,'end_time':end,'duration_minutes':duration}
            return type('Response', (), {'choices': [type('Choice', (), {'message': type('Body', (), {'content': json.dumps(result)})()})()]})()

    monkeypatch.setattr('bot.services.work_time.AsyncOpenAI', Model)
    assert asyncio.run(resolve_work_time_entry_candidate(
        user_input_text='conflicting fixture',api_key=config.openai_api_key,model=config.openai_llm_model,
        operation='open' if mode == 'open_at_time' else 'close',open_day=original,allow_boundary_correction=True,
    )) is None
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original


def test_work_time_help_exit_removes_correction_keyboard_and_does_not_write(setup, monkeypatch):
    from bot.handlers.work_time import cmd_dochadzka
    config, service = setup
    original = seed(service)
    fake_models(monkeypatch, field='start_time')
    state = State()
    asyncio.run(start_open_work_day(Message(), state, config, text='Oprav prichod 06:54'))
    reply = Message('/dochadzka')
    asyncio.run(cmd_dochadzka(reply, state, config))
    assert state.current is None and isinstance(reply.markup[-1], ReplyKeyboardRemove)
    assert 'oprav dnesny prichod na 06:54' in reply.answers[-1]
    assert service.get_day(telegram_id=1001, work_date=original.work_date) == original
