from __future__ import annotations

from dataclasses import replace
import asyncio
import inspect
import json
from datetime import datetime, date
from pathlib import Path

from bot.config import Config
from bot.handlers import voice
from bot.handlers.work_time import (
    WorkTimeStates,
    start_add_work_time_entry,
    start_close_work_day,
    start_delete_work_time_month,
    start_generate_work_time_report,
    start_update_work_time_lunch_break,
    work_time_delete_month_confirm,
    work_time_lunch_break_initial_choice,
    work_time_lunch_break_update_confirm,
    work_time_lunch_break_value,
    work_time_close_preview_confirm,
    work_time_close_input,
    work_time_manual_range_confirm,
    work_time_manual_range_input,
)
from bot.services.db import init_db
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import get_capability, get_safe_answer_payload
from bot.services.semantic_action_resolver import resolve_semantic_action
from bot.services.work_time import WorkTimeCandidate, WorkTimeService


class _DummyMessage:
    def __init__(self, text: str, telegram_id: int = 1001) -> None:
        self.text = text
        self.from_user = type('_User', (), {'id': telegram_id})()
        self.message_id = 88
        self.answers: list[str] = []
        self.documents: list[tuple[object, str | None]] = []
        self.reply_markups: list[object | None] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)
        self.reply_markups.append(kwargs.get('reply_markup'))

    async def answer_document(self, document, caption: str | None = None, **kwargs) -> None:
        self.documents.append((document, caption))


class _DummyState:
    def __init__(self) -> None:
        self.current_state: str | None = None
        self.data: dict = {}

    async def set_state(self, state) -> None:
        self.current_state = state.state if hasattr(state, 'state') else state

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def get_data(self) -> dict:
        return dict(self.data)

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
        db_path=tmp_path / 'work_time.db',
        storage_dir=tmp_path,
    )


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type('_Message', (), {'content': content})()


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _TopLevelActionOpenAIFake:
    output = '{"canonical_action":"unknown"}'
    last_payload: dict | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _TopLevelActionOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(_TopLevelActionOpenAIFake.output)


class _WorkTimeSlotOpenAIFake:
    output = '{"canonical":"unknown"}'
    last_payload: dict | None = None

    def __init__(self, *, api_key: str) -> None:
        self.api_key = api_key
        self.chat = type('_Chat', (), {'completions': self})()

    async def create(self, **kwargs):
        _WorkTimeSlotOpenAIFake.last_payload = json.loads(kwargs['messages'][1]['content'])
        return _FakeResponse(_WorkTimeSlotOpenAIFake.output)


WORK_TIME_ALLOWED = [
    'create_invoice',
    'open_work_day',
    'close_work_day',
    'add_work_time_entry',
    'generate_work_time_report',
    'delete_work_time_month',
    'update_work_time_lunch_break',
    'unknown',
]


def _resolve(text: str) -> str:
    return asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=WORK_TIME_ALLOWED,
            user_input_text=text,
            api_key=None,
            model='gpt-4o',
        )
    )


def test_top_level_work_time_open_routes_from_slovak_text() -> None:
    assert _resolve('zacinam pracovny den') == 'open_work_day'


def test_top_level_work_time_close_routes_from_slovak_text() -> None:
    assert _resolve('zatvor pracovny den 10 hodin') == 'close_work_day'


def test_top_level_work_time_manual_range_routes_from_text() -> None:
    assert _resolve('pracoval som dnes od 5:30 do 17:00') == 'add_work_time_entry'


def test_top_level_work_time_duration_only_routes_through_bounded_llm(monkeypatch) -> None:
    _TopLevelActionOpenAIFake.output = json.dumps({'canonical_action': 'add_work_time_entry'})
    monkeypatch.setattr('bot.services.semantic_action_resolver.AsyncOpenAI', _TopLevelActionOpenAIFake)

    result = asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=WORK_TIME_ALLOWED,
            user_input_text='record today nine and a half hours',
            api_key='sk-test',
            model='gpt-4o',
            action_hints={
                'add_work_time_entry': {
                    'meaning': 'manual work-time entry as range or duration-only total hours',
                },
            },
        )
    )

    assert result == 'add_work_time_entry'
    assert _TopLevelActionOpenAIFake.last_payload is not None
    assert 'add_work_time_entry' in _TopLevelActionOpenAIFake.last_payload['allowed_actions']


def test_top_level_work_time_report_routes_from_month_request() -> None:
    assert _resolve('vytvor vykaz hodin za jun') == 'generate_work_time_report'



def test_top_level_work_time_lunch_break_update_routes_from_examples() -> None:
    assert _resolve('zmeň obednú prestávku na 30 minút') == 'update_work_time_lunch_break'
    assert _resolve('nastav obednú prestávku 1 hodina') == 'update_work_time_lunch_break'
    assert _resolve('\u0437\u043c\u0456\u043d\u0438 \u043e\u0431\u0456\u0434\u043d\u044e \u043f\u0435\u0440\u0435\u0440\u0432\u0443 \u043d\u0430 30 \u0445\u0432\u0438\u043b\u0438\u043d') == 'update_work_time_lunch_break'
    assert _resolve('\u0438\u0437\u043c\u0435\u043d\u0438 \u043e\u0431\u0435\u0434\u0435\u043d\u043d\u044b\u0439 \u043f\u0435\u0440\u0435\u0440\u044b\u0432 \u043d\u0430 45 \u043c\u0438\u043d\u0443\u0442') == 'update_work_time_lunch_break'
    assert _resolve('\u043d\u0435 \u0432\u0456\u0434\u043d\u0456\u043c\u0430\u0442\u0438 \u043e\u0431\u0456\u0434') == 'update_work_time_lunch_break'
def test_top_level_work_time_delete_month_routes_from_slovak_text() -> None:
    assert _resolve('vymaz dochadzku za jul') == 'delete_work_time_month'
    assert _resolve('zmaz vykaz hodin za maj') == 'delete_work_time_month'


def test_top_level_work_time_delete_month_routes_from_ukrainian_and_russian_text() -> None:
    assert _resolve('\u0432\u0438\u0434\u0430\u043b\u0438 \u0442\u0430\u0431\u0435\u043b\u044c \u0437\u0430 \u043b\u0438\u043f\u0435\u043d\u044c') == 'delete_work_time_month'
    assert _resolve('\u0443\u0434\u0430\u043b\u0438 \u0442\u0430\u0431\u0435\u043b\u044c \u0440\u0430\u0431\u043e\u0447\u0435\u0433\u043e \u0432\u0440\u0435\u043c\u0435\u043d\u0438 \u0437\u0430 \u0438\u044e\u043b\u044c') == 'delete_work_time_month'


def test_work_time_request_does_not_route_to_invoice() -> None:
    assert _resolve('vytvor vykaz hodin za jun') != 'create_invoice'


def test_voice_router_has_no_work_time_phrase_dictionary() -> None:
    source = inspect.getsource(voice)
    assert 'zacinam pracovny den' not in source
    assert 'zatvor pracovny den' not in source
    assert 'vykaz hodin' not in source


def test_top_level_work_time_delete_month_beats_invoice_delete_for_mixed_dochadzka_text() -> None:
    allowed = [*WORK_TIME_ALLOWED, 'delete_existing_invoice']
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='видали dochadzku',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_work_time_month'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='видалити dochádzku',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_work_time_month'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=allowed,
            user_input_text='видалити фактуру 02',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'delete_existing_invoice'

def test_product_truth_work_time_tracking_is_partial() -> None:
    payload = get_safe_answer_payload('work_time_tracking')
    result = get_capability('work_time_tracking')
    assert payload['product_status'] == 'partial'
    assert 'open_work_day' in result.capability.canonical_actions
    assert 'delete_work_time_month' in result.capability.canonical_actions
    assert 'update_work_time_lunch_break' in result.capability.canonical_actions
    assert any('lunch' in limitation.lower() for limitation in result.capability.current_limitations)
    forbidden = ' '.join(payload['forbidden_claims'])
    assert 'payroll' in forbidden.lower()
    assert 'salary' in forbidden.lower()
    assert 'legal hr attendance compliance' in forbidden.lower()
    assert 'multi-employee dochadzka' in forbidden.lower()
    assert 'export' in forbidden.lower()
    assert 'automatic work-time detection' in forbidden.lower()


def test_info_help_answers_work_time_and_refuses_payroll_overclaim() -> None:
    answer = build_product_truth_guidance(user_input_text='Vie bot evidovat odpracovane hodiny?')
    assert answer is not None
    assert 'ciastocne' in answer.lower() or 'ciasto' in answer.lower()
    assert 'mzdova dochadzka' in answer.lower() or 'mzdova dochadzka' in answer.lower()
    assert 'vypocet mzdy' in answer.lower() or 'vypocet mzdy' in answer.lower()
    lunch_answer = build_product_truth_guidance(user_input_text='Vie bot nastavit obednu prestavku?')
    assert lunch_answer is not None
    assert 'obed' in lunch_answer.lower()
    assert 'ciastocne' in lunch_answer.lower() or 'ciasto' in lunch_answer.lower()




def test_first_report_without_lunch_setting_asks_and_stores_pending_request(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('vytvor vykaz hodin za jul 2026')
    state = _DummyState()

    asyncio.run(start_generate_work_time_report(message=message, state=state, config=config, text=message.text, source_channel='voice'))

    assert state.current_state == WorkTimeStates.waiting_lunch_break_initial_choice.state
    assert state.data['work_time_pending_report_year'] == 2026
    assert state.data['work_time_pending_report_month'] == 7
    assert state.data['work_time_pending_report_source_channel'] == 'voice'
    assert 'obed' in message.answers[-1].lower()
    assert message.documents == []


def test_first_report_no_saves_disabled_and_generates_pending_report(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.add_duration_entry(telegram_id=1001, candidate=WorkTimeCandidate(work_date=date(2026, 7, 2), duration_minutes=600)).ok
    message = _DummyMessage('vytvor vykaz hodin za jul 2026')
    state = _DummyState()

    asyncio.run(start_generate_work_time_report(message=message, state=state, config=config, text=message.text))
    asyncio.run(work_time_lunch_break_initial_choice(message=_DummyMessage('nie'), state=state, config=config, canonical_decision='no'))

    settings = service.get_lunch_break_settings(telegram_id=1001)
    assert settings.configured is True
    assert settings.enabled is False
    assert settings.minutes == 0
    assert state.current_state is None


def test_first_report_yes_then_value_saves_and_generates_pending_report(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('vytvor vykaz hodin za jul 2026')
    state = _DummyState()

    asyncio.run(start_generate_work_time_report(message=message, state=state, config=config, text=message.text))
    asyncio.run(work_time_lunch_break_initial_choice(message=_DummyMessage('ano'), state=state, config=config, canonical_decision='yes'))
    assert state.current_state == WorkTimeStates.waiting_lunch_break_value.state
    value_message = _DummyMessage('60')
    asyncio.run(work_time_lunch_break_value(message=value_message, state=state, config=config))

    settings = WorkTimeService(config.db_path).get_lunch_break_settings(telegram_id=1001)
    assert settings.configured is True
    assert settings.enabled is True
    assert settings.minutes == 60
    assert state.current_state is None
    assert value_message.documents


def test_second_report_after_lunch_setting_generates_directly(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    service.save_lunch_break_settings(telegram_id=1001, enabled=True, minutes=60)
    message = _DummyMessage('vytvor vykaz hodin za jul 2026')
    state = _DummyState()

    asyncio.run(start_generate_work_time_report(message=message, state=state, config=config, text=message.text))

    assert state.current_state is None
    assert message.documents
    assert 'obed' not in ''.join(message.answers).lower()


def test_lunch_break_update_and_disable_are_confirmation_gated(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _DummyMessage('zmen obednu prestavku na 30 minut')

    asyncio.run(start_update_work_time_lunch_break(message=message, state=state, config=config, text=message.text))
    assert state.current_state == WorkTimeStates.waiting_lunch_break_update_confirm.state
    asyncio.run(work_time_lunch_break_update_confirm(message=_DummyMessage('ulozit'), state=state, config=config, canonical_decision='approve'))
    settings = WorkTimeService(config.db_path).get_lunch_break_settings(telegram_id=1001)
    assert settings.enabled is True
    assert settings.minutes == 30

    state = _DummyState()
    disable = _DummyMessage('zrus odpocitavanie obednej prestavky')
    asyncio.run(start_update_work_time_lunch_break(message=disable, state=state, config=config, text=disable.text))
    asyncio.run(work_time_lunch_break_update_confirm(message=_DummyMessage('ulozit'), state=state, config=config, canonical_decision='approve'))
    disabled = WorkTimeService(config.db_path).get_lunch_break_settings(telegram_id=1001)
    assert disabled.enabled is False
    assert disabled.minutes == 0


def test_manual_preview_edit_then_vcera_input_returns_full_preview_and_buttons(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    initial = _DummyMessage('dnes 10 hodin')

    asyncio.run(start_add_work_time_entry(message=initial, state=state, config=config, text=initial.text))
    assert state.current_state == WorkTimeStates.waiting_manual_range_confirm.state

    asyncio.run(work_time_manual_range_confirm(message=_DummyMessage('upravit'), state=state, config=config, canonical_decision='edit'))
    assert state.current_state == WorkTimeStates.waiting_manual_range_input.state

    corrected = _DummyMessage('včera od 6:00 do 16:30')
    asyncio.run(work_time_manual_range_input(message=corrected, state=state, config=config))

    assert state.current_state == WorkTimeStates.waiting_manual_range_confirm.state
    assert 'Skontrolujte doplnenie pracovneho casu' in corrected.answers[-1]
    assert 'Datum:' in corrected.answers[-1]
    assert 'Prichod: 06:00' in corrected.answers[-1]
    assert 'Odchod: 16:30' in corrected.answers[-1]
    assert corrected.reply_markups[-1] is not None


def test_unknown_manual_preview_decision_repeats_full_context_and_buttons(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    message = _DummyMessage('pracoval som dnes od 6:00 do 16:30')

    asyncio.run(start_add_work_time_entry(message=message, state=state, config=config, text=message.text))
    unclear = _DummyMessage('vytvor vykaz hodin za jul')
    asyncio.run(work_time_manual_range_confirm(message=unclear, state=state, config=config, canonical_decision='unknown'))

    assert state.current_state == WorkTimeStates.waiting_manual_range_confirm.state
    assert 'Mate rozpracovany nahlad doplnenia pracovneho casu' in unclear.answers[-1]
    assert 'Datum:' in unclear.answers[-1]
    assert 'Prichod: 06:00' in unclear.answers[-1]
    assert 'Odchod: 16:30' in unclear.answers[-1]
    assert 'Hodiny:' in unclear.answers[-1]
    assert unclear.reply_markups[-1] is not None
    assert unclear.documents == []


def test_unknown_close_preview_decision_repeats_full_context_and_buttons(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    service.save_lunch_break_settings(telegram_id=1001, enabled=True, minutes=60)
    assert service.open_day(telegram_id=1001, now=datetime(2026, 7, 2, 7, 12)).ok
    state = _DummyState()
    close = _DummyMessage('zatvor den 10 hodin')

    asyncio.run(start_close_work_day(message=close, state=state, config=config, text=close.text))
    unclear = _DummyMessage('pokaž dochadzku')
    asyncio.run(work_time_close_preview_confirm(message=unclear, state=state, config=config, canonical_decision='unknown'))

    assert state.current_state == WorkTimeStates.waiting_close_preview_confirm.state
    assert 'Mate rozpracovany nahlad doplnenia pracovneho casu' in unclear.answers[-1]
    assert 'Prichod: 07:12' in unclear.answers[-1]
    assert 'Odchod: 18:12' in unclear.answers[-1]
    assert 'Hodiny: 10:00' in unclear.answers[-1]
    assert unclear.reply_markups[-1] is not None


def test_manual_preview_missing_candidate_clears_state_and_asks_for_range(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    state = _DummyState()
    asyncio.run(state.set_state(WorkTimeStates.waiting_manual_range_confirm))
    message = _DummyMessage('neviem')

    asyncio.run(work_time_manual_range_confirm(message=message, state=state, config=config, canonical_decision='unknown'))

    assert state.current_state is None
    assert 'Nahlad uz nie je dostupny' in message.answers[-1]



def test_manual_entry_uses_bounded_llm_before_duration_fallback_for_date_range(monkeypatch, tmp_path: Path) -> None:
    config = replace(_config(tmp_path), openai_api_key='sk-test')
    init_db(config.db_path)
    _WorkTimeSlotOpenAIFake.output = json.dumps(
        {
            'canonical': 'work_time_entry',
            'mode': 'manual_range',
            'date': '2026-07-01',
            'start_time': '06:00',
            'end_time': '11:00',
            'duration_minutes': None,
        }
    )
    _WorkTimeSlotOpenAIFake.last_payload = None
    monkeypatch.setattr('bot.services.work_time.AsyncOpenAI', _WorkTimeSlotOpenAIFake)

    message = _DummyMessage('1 na 7 pracoval 6 hodin do 11')
    state = _DummyState()
    asyncio.run(start_add_work_time_entry(message=message, state=state, config=config, text=message.text))

    assert state.current_state == WorkTimeStates.waiting_manual_range_confirm.state
    assert _WorkTimeSlotOpenAIFake.last_payload is not None
    assert 'Prichod: 06:00' in message.answers[-1]
    assert 'Odchod: 11:00' in message.answers[-1]
    assert 'Typ: pocet hodin bez presneho prichodu/odchodu' not in message.answers[-1]

def test_delete_work_time_month_missing_month_asks_without_deleting(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.add_duration_entry(
        telegram_id=1001,
        candidate=WorkTimeCandidate(work_date=date(2026, 7, 2), duration_minutes=600),
    ).ok
    message = _DummyMessage('vymaz dochadzku')
    state = _DummyState()

    asyncio.run(start_delete_work_time_month(message=message, state=state, config=config, text=message.text))

    assert state.current_state == WorkTimeStates.waiting_delete_month_input.state
    assert 'Za ktory mesiac' in message.answers[-1]
    assert len(service.list_days_for_month(telegram_id=1001, year=2026, month=7)) == 1


def test_delete_work_time_month_empty_month_exits_without_confirmation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('vymaz dochadzku za maj 2026')
    state = _DummyState()

    asyncio.run(start_delete_work_time_month(message=message, state=state, config=config, text=message.text))

    assert state.current_state is None
    assert 'Nie je co vymazat' in message.answers[-1]


def test_delete_work_time_month_cancel_does_not_delete(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.add_duration_entry(
        telegram_id=1001,
        candidate=WorkTimeCandidate(work_date=date(2026, 7, 2), duration_minutes=600),
    ).ok
    message = _DummyMessage('vymaz dochadzku za jul 2026')
    state = _DummyState()

    asyncio.run(start_delete_work_time_month(message=message, state=state, config=config, text=message.text))
    assert state.current_state == WorkTimeStates.waiting_delete_month_confirm.state
    asyncio.run(work_time_delete_month_confirm(message=message, state=state, config=config, canonical_decision='no'))

    assert state.current_state is None
    assert len(service.list_days_for_month(telegram_id=1001, year=2026, month=7)) == 1


def test_unknown_close_input_does_not_close_open_day(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.open_day(telegram_id=1001, now=datetime(2026, 7, 3, 7, 0)).ok
    state = _DummyState()
    message = _DummyMessage('neviem ako vcera')

    asyncio.run(start_close_work_day(message=message, state=state, config=config, text=message.text))

    open_day = WorkTimeService(config.db_path).get_open_day(telegram_id=1001)
    assert open_day is not None
    assert open_day.end_time is None
    assert state.current_state == WorkTimeStates.waiting_close_input.state
    assert 'Napiste cas odchodu alebo trvanie' in message.answers[-1]


def test_close_command_with_ambiguous_dot_time_keeps_state_and_accepts_plain_hhmm(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.open_day(telegram_id=1001, now=datetime(2026, 7, 8, 6, 33)).ok
    state = _DummyState()
    first = _DummyMessage('\u0417\u0430\u043a\u0440\u0438\u0439 \u043c\u0435\u043d\u0456 \u043f\u0440\u0430\u0446\u044c\u043e\u0432\u043d\u0438\u0439 \u0434\u0435\u043d\u044c 16.07')

    asyncio.run(start_close_work_day(message=first, state=state, config=config, text=first.text))

    assert state.current_state == WorkTimeStates.waiting_close_input.state
    assert WorkTimeService(config.db_path).get_open_day(telegram_id=1001) is not None
    assert 'Napiste cas odchodu alebo trvanie' in first.answers[-1]

    second = _DummyMessage('16:07')
    asyncio.run(work_time_close_input(message=second, state=state, config=config))

    assert state.current_state == WorkTimeStates.waiting_close_preview_confirm.state
    assert WorkTimeService(config.db_path).get_open_day(telegram_id=1001) is not None
    assert 'Prichod: 06:33' in second.answers[-1]
    assert 'Odchod: 16:07' in second.answers[-1]
    assert second.reply_markups[-1] is not None

def test_explicit_close_now_closes_open_day(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.open_day(telegram_id=1001, now=datetime(2026, 7, 3, 7, 0)).ok
    state = _DummyState()
    message = _DummyMessage('zatvor pracovny den teraz')

    asyncio.run(start_close_work_day(message=message, state=state, config=config, text=message.text))

    assert WorkTimeService(config.db_path).get_open_day(telegram_id=1001) is None
    day = WorkTimeService(config.db_path).get_day(telegram_id=1001, work_date='2026-07-03')
    assert day is not None
    assert day.status == 'closed'
    assert state.current_state is None
    assert 'Pracovny den je uzavrety' in message.answers[-1]


def test_close_at_exact_time_previews_and_saves_only_after_approve(monkeypatch, tmp_path: Path) -> None:
    config = replace(_config(tmp_path), openai_api_key='sk-test')
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    assert service.open_day(telegram_id=1001, now=datetime(2026, 7, 3, 7, 0)).ok
    _WorkTimeSlotOpenAIFake.output = json.dumps(
        {
            'canonical': 'work_time_entry',
            'mode': 'close_at_time',
            'date': None,
            'start_time': None,
            'end_time': '17:00',
            'duration_minutes': None,
        }
    )
    monkeypatch.setattr('bot.services.work_time.AsyncOpenAI', _WorkTimeSlotOpenAIFake)
    state = _DummyState()
    message = _DummyMessage('zatvor den o 17:00')

    asyncio.run(start_close_work_day(message=message, state=state, config=config, text=message.text))

    assert state.current_state == WorkTimeStates.waiting_close_preview_confirm.state
    assert WorkTimeService(config.db_path).get_open_day(telegram_id=1001) is not None
    assert 'Prichod: 07:00' in message.answers[-1]
    assert 'Odchod: 17:00' in message.answers[-1]

    asyncio.run(work_time_close_preview_confirm(message=_DummyMessage('schvalit'), state=state, config=config, canonical_decision='approve'))
    day = WorkTimeService(config.db_path).get_day(telegram_id=1001, work_date='2026-07-03')
    assert day is not None
    assert day.status == 'closed'
    assert day.end_time == '17:00'


def test_close_by_duration_previews_and_saves_only_after_approve(monkeypatch, tmp_path: Path) -> None:
    config = replace(_config(tmp_path), openai_api_key='sk-test')
    init_db(config.db_path)
    service = WorkTimeService(config.db_path)
    service.save_lunch_break_settings(telegram_id=1001, enabled=True, minutes=60)
    assert service.open_day(telegram_id=1001, now=datetime(2026, 7, 3, 7, 12)).ok
    _WorkTimeSlotOpenAIFake.output = json.dumps(
        {
            'canonical': 'work_time_entry',
            'mode': 'close_with_duration',
            'date': None,
            'start_time': None,
            'end_time': None,
            'duration_minutes': 600,
        }
    )
    monkeypatch.setattr('bot.services.work_time.AsyncOpenAI', _WorkTimeSlotOpenAIFake)
    state = _DummyState()
    message = _DummyMessage('zatvor den 10 hodin')

    asyncio.run(start_close_work_day(message=message, state=state, config=config, text=message.text))

    assert state.current_state == WorkTimeStates.waiting_close_preview_confirm.state
    assert WorkTimeService(config.db_path).get_open_day(telegram_id=1001) is not None
    assert 'Prichod: 07:12' in message.answers[-1]
    assert 'Odchod: 18:12' in message.answers[-1]
    assert 'Hodiny: 10:00' in message.answers[-1]

    asyncio.run(work_time_close_preview_confirm(message=_DummyMessage('schvalit'), state=state, config=config, canonical_decision='approve'))
    day = WorkTimeService(config.db_path).get_day(telegram_id=1001, work_date='2026-07-03')
    assert day is not None
    assert day.status == 'closed'
    assert day.end_time == '18:12'


def test_manual_cyrillic_range_from_llm_is_not_duration_only(monkeypatch, tmp_path: Path) -> None:
    config = replace(_config(tmp_path), openai_api_key='sk-test')
    init_db(config.db_path)
    _WorkTimeSlotOpenAIFake.output = json.dumps(
        {
            'canonical': 'work_time_entry',
            'mode': 'manual_range',
            'date': '2026-07-02',
            'start_time': '06:00',
            'end_time': '11:00',
            'duration_minutes': None,
        }
    )
    monkeypatch.setattr('bot.services.work_time.AsyncOpenAI', _WorkTimeSlotOpenAIFake)
    state = _DummyState()
    message = _DummyMessage('вчора од 6-ї до 11-ї')

    asyncio.run(start_add_work_time_entry(message=message, state=state, config=config, text=message.text))

    assert state.current_state == WorkTimeStates.waiting_manual_range_confirm.state
    data = asyncio.run(state.get_data())
    candidate = data['work_time_manual_candidate']
    assert candidate['work_date'] == '2026-07-02'
    assert candidate['start_time'] == '06:00'
    assert candidate['end_time'] == '11:00'
    assert candidate['duration_minutes'] is None
    assert candidate['close_mode'] == 'manual_range'
    assert 'Prichod: 06:00' in message.answers[-1]
    assert 'Odchod: 11:00' in message.answers[-1]
    assert 'Typ: pocet hodin bez presneho prichodu/odchodu' not in message.answers[-1]