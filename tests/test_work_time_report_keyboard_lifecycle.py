from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardRemove

from bot.config import Config
from bot.handlers import voice
from bot.handlers.decision_callbacks import decision_callback
from bot.handlers.invoice import process_invoice_text
from bot.handlers.state_control import cmd_cancel
from bot.handlers.work_time import (
    WORK_TIME_REPORT_CHOICE_KEY, WorkTimeStates, cmd_dochadzka,
    work_time_lunch_break_initial_choice,
)
from bot.services.active_fsm_guard import (
    ACTIVE_FSM_LAST_ACTIVITY_AT_KEY, ActiveFsmMessageMiddleware,
    handle_active_fsm_text_update, touch_active_fsm_activity,
)
from bot.services.db import init_db
from bot.services.work_time import WorkTimeCandidate, WorkTimeService


class Telegram:
    def __init__(self):
        self.messages = {}
        self.edits = []
        self.documents = []
        self.document_markups = []
        self.fail_cleanup = False

    async def edit_message_reply_markup(self, *, chat_id, message_id, reply_markup):
        if self.fail_cleanup:
            raise RuntimeError('Telegram edit failed')
        self.edits.append((chat_id, message_id, reply_markup))
        self.messages[message_id].reply_markup = reply_markup

    async def get_file(self, file_id):
        return SimpleNamespace(file_path='fixture.ogg')

    async def download_file(self, file_path, destination):
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b'fixture')


class Message:
    def __init__(self, bot, text='', *, actor=1001):
        self.bot, self.text = bot, text
        self.from_user = SimpleNamespace(id=actor, is_bot=False)
        self.chat = SimpleNamespace(id=actor, type='private')
        self.message_id = 77

    async def answer(self, text, **kwargs):
        sent = Message(self.bot, text, actor=self.chat.id)
        sent.from_user = SimpleNamespace(id=9000, is_bot=True)
        sent.message_id = len(self.bot.messages) + 100
        sent.reply_markup = kwargs.get('reply_markup')
        self.bot.messages[sent.message_id] = sent
        return sent

    async def answer_document(self, document, **kwargs):
        self.bot.documents.append(document)
        self.bot.document_markups.append(kwargs.get('reply_markup'))

    async def edit_reply_markup(self, *, reply_markup):
        return await self.bot.edit_message_reply_markup(chat_id=self.chat.id, message_id=self.message_id, reply_markup=reply_markup)


class Callback:
    def __init__(self, source, token='yes', *, actor=1001):
        self.message, self.data = source, 'decision:' + token
        self.from_user = SimpleNamespace(id=actor, is_bot=False)
        self.answers = []

    async def answer(self, text=None, **kwargs):
        self.answers.append(text)


async def start_report(tmp_path, monkeypatch):
    config = Config(
        bot_token='123:fixture', openai_api_key='fixture',
        openai_stt_model='whisper-1', openai_llm_model='gpt-4o',
        debug_invoice_transparency=False, db_path=tmp_path/'test.db', storage_dir=tmp_path,
        allowed_telegram_user_ids=frozenset({1001}),
    )
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    service.add_duration_entry(telegram_id=1001, candidate=WorkTimeCandidate(work_date=date(2026, 7, 2), duration_minutes=480))

    async def primary(**kwargs):
        kwargs['diagnostics']['slots'] = {'period': {'type': 'month', 'year': 2026, 'month': 7}}
        return 'generate_work_time_report'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', primary)
    bot = Telegram()
    state = FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=9000, chat_id=1001, user_id=1001))
    message = Message(bot, 'vytvor vykaz hodin za jul 2026')
    await process_invoice_text(message=message, state=state, config=config, invoice_text=message.text)
    await touch_active_fsm_activity(state)
    ref = (await state.get_data())[WORK_TIME_REPORT_CHOICE_KEY]
    card = bot.messages[ref['message_id']]
    assert await state.get_state() == WorkTimeStates.waiting_lunch_break_initial_choice.state
    assert isinstance(card.reply_markup, InlineKeyboardMarkup)
    assert ref['owner_id'] == 1001 and ref['chat_id'] == 1001
    return config, service, state, bot, card


def assert_no_business_change(service, bot):
    assert not service.get_lunch_break_settings(telegram_id=1001).configured
    assert service.get_day(telegram_id=1001, work_date='2026-07-02').total_minutes == 480
    assert bot.documents == []


@pytest.mark.parametrize('exit_mode', ['command', 'text', 'voice', 'menu', 'start', 'help', 'timeout', 'stale_reset'])
def test_report_public_entry_cleanup_on_exit(tmp_path, monkeypatch, exit_mode):
    async def scenario():
        config, service, state, bot, card = await start_report(tmp_path, monkeypatch)
        message = Message(bot, '/cancel')
        if exit_mode == 'command':
            await cmd_cancel(message, state, config)
        elif exit_mode == 'help':
            await cmd_dochadzka(message, state, config)
        elif exit_mode == 'voice':
            message.voice = SimpleNamespace(file_id='cancel-fixture')
            async def stt(*args): return 'скасувати'
            monkeypatch.setattr('bot.handlers.voice.transcribe_audio', stt)
            await voice.handle_voice(message, bot, config, state)
            assert not list(tmp_path.rglob('*.ogg'))
        else:
            message.text = {'text':'скасувати', 'menu':'/menu', 'start':'/start', 'timeout':'ano', 'stale_reset':'new request'}[exit_mode]
            if exit_mode in {'timeout', 'stale_reset'}:
                await state.update_data(**{ACTIVE_FSM_LAST_ACTIVITY_AT_KEY:(datetime.now(UTC)-timedelta(hours=1)).isoformat()})
            if exit_mode == 'stale_reset':
                async def pass_through(**kwargs): return 'pass_through'
                async def idle(**kwargs): await kwargs['message'].answer('idle fixture')
                monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', pass_through)
                monkeypatch.setattr('bot.services.active_fsm_guard._route_through_idle_top_level', idle)
            # Public middleware owns command/text navigation and expiry.
            async def unexpected(*args): raise AssertionError('exit must be consumed')
            await ActiveFsmMessageMiddleware()(unexpected, message, {'state':state,'config':config})
        assert await state.get_state() is None
        assert card.reply_markup is None
        assert bot.edits == [(1001, card.message_id, None)]
        assert_no_business_change(service, bot)
        assert any(isinstance(m.reply_markup, ReplyKeyboardRemove) for m in bot.messages.values())
    asyncio.run(scenario())


@pytest.mark.parametrize('channel', ['text','voice','button'])
@pytest.mark.parametrize('decision', ['yes','no'])
def test_report_choice_channels_remove_card_and_keep_existing_effect(tmp_path, monkeypatch, channel, decision):
    async def scenario():
        config, service, state, bot, card = await start_report(tmp_path, monkeypatch)
        message = Message(bot, 'ano' if decision=='yes' else 'nie')
        if channel == 'button':
            await decision_callback(Callback(card, decision), state, config)
        elif channel == 'voice':
            message.voice = SimpleNamespace(file_id='decision-fixture')
            async def stt(*args): return message.text
            async def pass_through(**kwargs): return 'pass_through'
            monkeypatch.setattr('bot.handlers.voice.transcribe_audio', stt)
            monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', pass_through)
            await voice.handle_voice(message, bot, config, state)
        else:
            await work_time_lunch_break_initial_choice(message, state, config)
        assert card.reply_markup is None and bot.edits == [(1001,card.message_id,None)]
        if decision == 'yes':
            assert await state.get_state() == WorkTimeStates.waiting_lunch_break_value.state
            assert_no_business_change(service, bot)
        else:
            assert await state.get_state() is None
            assert service.get_lunch_break_settings(telegram_id=1001).configured
            assert not service.get_lunch_break_settings(telegram_id=1001).enabled
            assert bot.documents
            assert isinstance(bot.document_markups[-1], ReplyKeyboardRemove)
        # Duplicate cannot save or move the next step again.
        before = service.get_lunch_break_settings(telegram_id=1001)
        previous_state = await state.get_state()
        await decision_callback(Callback(card, decision), state, config)
        assert service.get_lunch_break_settings(telegram_id=1001) == before
        assert await state.get_state() == previous_state
    asyncio.run(scenario())


def test_unknown_retains_one_card_and_new_session_rejects_old_card(tmp_path, monkeypatch):
    async def scenario():
        config, service, state, bot, card = await start_report(tmp_path, monkeypatch)
        async def unknown(**kwargs): return 'unknown'
        monkeypatch.setattr('bot.handlers.work_time.resolve_yes_no', unknown)
        await work_time_lunch_break_initial_choice(Message(bot,'не знаю'), state, config)
        assert sum(isinstance(m.reply_markup,InlineKeyboardMarkup) for m in bot.messages.values()) == 1
        await cmd_cancel(Message(bot),state,config)
        await process_invoice_text(message=Message(bot),state=state,config=config,invoice_text='vytvor vykaz hodin za jul 2026')
        await touch_active_fsm_activity(state)
        ref=(await state.get_data())[WORK_TIME_REPORT_CHOICE_KEY]
        new_card=bot.messages[ref['message_id']]
        await decision_callback(Callback(card,'no'),state,config)
        assert new_card.reply_markup is not None
        assert await state.get_state() == WorkTimeStates.waiting_lunch_break_initial_choice.state
        assert_no_business_change(service,bot)
    asyncio.run(scenario())


@pytest.mark.parametrize('bad_context',['foreign_actor','foreign_chat','missing','wrong_workspace','malformed','expired','legacy'])
def test_report_callback_guards_and_owned_cleanup(tmp_path,monkeypatch,bad_context):
    async def scenario():
        config,service,state,bot,card=await start_report(tmp_path,monkeypatch)
        callback=Callback(card,'no')
        if bad_context=='foreign_actor':callback.from_user=SimpleNamespace(id=1002,is_bot=False)
        if bad_context=='foreign_chat':card.chat=SimpleNamespace(id=1002,type='private')
        if bad_context=='missing':await state.update_data(**{WORK_TIME_REPORT_CHOICE_KEY:None})
        if bad_context=='wrong_workspace':await state.update_data(work_time_workspace_id='another-workspace')
        if bad_context=='malformed':callback.data='decision:invalid'
        if bad_context=='expired':await state.update_data(**{ACTIVE_FSM_LAST_ACTIVITY_AT_KEY:(datetime.now(UTC)-timedelta(hours=1)).isoformat()})
        if bad_context=='legacy':await state.update_data(**{ACTIVE_FSM_LAST_ACTIVITY_AT_KEY:None})
        await decision_callback(callback,state,config)
        assert_no_business_change(service,bot)
        if bad_context in {'foreign_actor','foreign_chat','malformed'}:
            assert card.reply_markup is not None and not bot.edits
        else:assert card.reply_markup is None
        if bad_context in {'expired','legacy'}:assert await state.get_state() is None
    asyncio.run(scenario())


@pytest.mark.parametrize('outcome',['cancel','yes','no'])
def test_cleanup_failure_logs_without_reversing_state_or_effect(tmp_path,monkeypatch,caplog,outcome):
    async def scenario():
        config,service,state,bot,card=await start_report(tmp_path,monkeypatch)
        bot.fail_cleanup=True
        if outcome=='cancel':await cmd_cancel(Message(bot),state,config)
        else:await decision_callback(Callback(card,outcome),state,config)
        assert 'Failed to clear work-time report choice inline keyboard' in caplog.text
        assert card.reply_markup is not None
        assert await state.get_state() == (WorkTimeStates.waiting_lunch_break_value.state if outcome=='yes' else None)
        if outcome=='no':assert service.get_lunch_break_settings(telegram_id=1001).configured and bot.documents
        else:assert_no_business_change(service,bot)
        # A later owned stale click retries removal, never repeats a business save.
        bot.fail_cleanup=False
        await decision_callback(Callback(card,'no'),state,config)
        assert card.reply_markup is None
    asyncio.run(scenario())
