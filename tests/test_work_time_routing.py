from __future__ import annotations

import asyncio
import inspect
import json

from bot.handlers import voice
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import get_capability, get_safe_answer_payload
from bot.services.semantic_action_resolver import resolve_semantic_action


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

