from __future__ import annotations

import asyncio
import inspect
import json
from datetime import date
from pathlib import Path

from bot.config import Config
from bot.handlers import voice
from bot.handlers.work_time import WorkTimeStates, start_delete_work_time_month, work_time_delete_month_confirm
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

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


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


WORK_TIME_ALLOWED = [
    'create_invoice',
    'open_work_day',
    'close_work_day',
    'add_work_time_entry',
    'generate_work_time_report',
    'delete_work_time_month',
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


def test_product_truth_work_time_tracking_is_partial() -> None:
    payload = get_safe_answer_payload('work_time_tracking')
    result = get_capability('work_time_tracking')
    assert payload['product_status'] == 'partial'
    assert 'open_work_day' in result.capability.canonical_actions
    assert 'delete_work_time_month' in result.capability.canonical_actions
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
