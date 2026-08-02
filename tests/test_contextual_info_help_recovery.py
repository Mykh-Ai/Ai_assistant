from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from bot.services import contextual_info_help_recovery as recovery_module
from bot.services.contextual_info_help_recovery import (
    ContextualRecoveryStore,
    GENUINELY_UNCLEAR_MESSAGE,
    build_contextual_recovery_payload,
    parse_contextual_recovery_result,
    resolve_contextual_recovery,
)


def test_payload_contains_bounded_metadata_and_no_execution_authority() -> None:
    payload = build_contextual_recovery_payload(
        user_input='pošli ju tam',
        input_channel='text',
        recent_turns=[{'role': 'user', 'text': 'faktúra', 'channel': 'text'}],
        active_state_descriptor=None,
        action_ids=['create_invoice', 'add_contact'],
        capability_ids=['invoices', 'contacts'],
    )

    assert payload['current_input'] == 'pošli ju tam'
    assert payload['allowed_outcomes'][-1] == 'genuinely_unclear'
    assert {item['action_id'] for item in payload['canonical_actions']} == {
        'create_invoice', 'add_contact'
    }
    assert 'execute' not in json.dumps(payload).casefold()
    assert all('status' in item for item in payload['product_truth_capabilities'])


def test_payload_normalizes_voice_channel_and_strips_unapproved_turn_fields() -> None:
    payload = build_contextual_recovery_payload(
        user_input='tam', input_channel='voice', active_state_descriptor=None,
        action_ids=['create_invoice'], capability_ids=['invoices'],
        recent_turns=[{'role': 'user', 'text': 'pošli faktúru', 'channel': 'voice_stt',
                       'workspace_id': 'must-not-leave-python', 'secret': 'drop'}],
    )
    assert payload['input_channel'] == 'voice_stt'
    assert payload['recent_turns'] == [{'role': 'user', 'text': 'pošli faktúru', 'channel': 'voice_stt'}]


def test_parser_accepts_known_candidates_and_caps_at_four() -> None:
    parsed = parse_contextual_recovery_result(
        {
            'recovery_outcome': 'clarify_candidates',
            'failure_cause': 'ambiguous_between_actions',
            'action_id': None,
            'candidate_action_ids': [
                'create_invoice', 'show_existing_invoice', 'invoice_analytics',
                'mark_existing_invoice_paid', 'add_contact'
            ],
            'capability_id': None,
            'object_domain': 'invoice',
            'operation': 'unknown',
            'refers_to_active_flow': False,
            'confidence': 0.6,
            'needs_clarification': True,
        }
    )

    assert parsed.outcome == 'clarify_candidates'
    assert len(parsed.candidate_action_ids) == 4
    assert 'add_contact' not in parsed.candidate_action_ids


def test_parser_rejects_unknown_action_and_cross_domain_candidates() -> None:
    parsed = parse_contextual_recovery_result(
        {
            'recovery_outcome': 'clarify_candidates',
            'failure_cause': 'missing_operation',
            'candidate_action_ids': ['invent_action', 'send_invoice', 'create_invoice', 'add_contact'],
            'object_domain': 'invoice',
            'operation': 'create',
        }
    )

    assert parsed.candidate_action_ids == ('create_invoice',)


def test_resolved_action_with_unknown_id_fails_closed() -> None:
    parsed = parse_contextual_recovery_result(
        {'recovery_outcome': 'resolved_action', 'failure_cause': 'primary_resolver_miss', 'action_id': 'invent_action'}
    )

    assert parsed.outcome == 'genuinely_unclear'
    assert parsed.action_id is None


def test_unknown_outcome_fails_closed() -> None:
    parsed = parse_contextual_recovery_result({'recovery_outcome': 'free_form_answer'})
    assert parsed.outcome == 'genuinely_unclear'


def test_unsupported_unknown_capability_is_safe_unknown() -> None:
    parsed = parse_contextual_recovery_result(
        {'recovery_outcome': 'unsupported_capability', 'failure_cause': 'unsupported_capability', 'capability_id': 'made_up'}
    )
    assert parsed.outcome == 'genuinely_unclear'


def test_recovery_failure_uses_narrow_fallback_without_retry(monkeypatch) -> None:
    calls = []

    async def _call(**kwargs):
        calls.append(kwargs)
        raise RuntimeError('offline')

    monkeypatch.setattr(
        'bot.services.contextual_info_help_recovery._call_contextual_recovery_model', _call
    )
    result = asyncio.run(
        resolve_contextual_recovery(
            user_input='???', input_channel='text', recent_turns=[],
            active_state_descriptor=None, action_ids=['create_invoice'],
            capability_ids=['invoices'], api_key='sk-test', model='test',
        )
    )

    assert result.outcome == 'genuinely_unclear'
    assert len(calls) == 1
    assert GENUINELY_UNCLEAR_MESSAGE == (
        'Tejto správe som nerozumel.\n'
        'Skúste prosím stručne napísať, čo chcete urobiť.'
    )


def test_model_transport_sends_one_bounded_json_call(monkeypatch) -> None:
    calls = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
                content='{"recovery_outcome":"genuinely_unclear","failure_cause":"insufficient_signal"}'
            ))])

    class _Client:
        def __init__(self, *, api_key):
            assert api_key == 'sk-test'
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(recovery_module, 'AsyncOpenAI', _Client)
    payload = build_contextual_recovery_payload(
        user_input='pošli ju tam', input_channel='text',
        recent_turns=[{'role': 'bot', 'text': 'Faktúra je pripravená.', 'channel': 'bot_message'}],
        active_state_descriptor=None, action_ids=['send_invoice'],
        capability_ids=['send_invoice_email'],
    )
    raw = asyncio.run(recovery_module._call_contextual_recovery_model(
        payload=payload, api_key='sk-test', model='test-model', timeout_seconds=1.0,
    ))

    assert raw == '{"recovery_outcome":"genuinely_unclear","failure_cause":"insufficient_signal"}'
    assert len(calls) == 1
    assert calls[0]['model'] == 'test-model'
    assert calls[0]['temperature'] == 0
    assert calls[0]['response_format'] == {'type': 'json_object'}
    assert len(calls[0]['messages']) == 2
    sent_payload = json.loads(calls[0]['messages'][1]['content'])
    assert sent_payload['current_input'] == 'pošli ju tam'
    assert sent_payload['recent_turns'][0]['text'] == 'Faktúra je pripravená.'


def test_model_transport_timeout_fails_closed_without_retry(monkeypatch) -> None:
    calls = []

    class _Completions:
        async def create(self, **kwargs):
            calls.append(kwargs)
            await asyncio.sleep(0.05)
            return SimpleNamespace(choices=[])

    class _Client:
        def __init__(self, *, api_key):
            self.chat = SimpleNamespace(completions=_Completions())

    monkeypatch.setattr(recovery_module, 'AsyncOpenAI', _Client)
    result = asyncio.run(resolve_contextual_recovery(
        user_input='???', input_channel='text', recent_turns=[],
        active_state_descriptor=None, action_ids=['create_invoice'],
        capability_ids=['invoices'], api_key='sk-test', model='test',
        timeout_seconds=0.001,
    ))

    assert result.outcome == 'genuinely_unclear'
    assert result.validation_error == 'model_failure'
    assert len(calls) == 1


def test_no_api_key_fails_closed_without_call(monkeypatch) -> None:
    async def _call(**kwargs):
        raise AssertionError('model must not be called')

    monkeypatch.setattr(
        'bot.services.contextual_info_help_recovery._call_contextual_recovery_model', _call
    )
    result = asyncio.run(
        resolve_contextual_recovery(
            user_input='???', input_channel='text', recent_turns=[],
            active_state_descriptor=None, action_ids=['create_invoice'],
            capability_ids=['invoices'], api_key=None, model='test',
        )
    )
    assert result.outcome == 'genuinely_unclear'


def test_ephemeral_record_is_actor_chat_index_and_ttl_bounded() -> None:
    clock = [datetime(2026, 8, 2, 10, tzinfo=UTC)]
    store = ContextualRecoveryStore(clock=lambda: clock[0])
    token = store.create(user_id=1, chat_id=10, workspace_id=100,
                         candidate_action_ids=['create_invoice', 'add_contact'])

    assert store.consume(token, user_id=2, chat_id=10, index=0) is None
    assert store.consume(token, user_id=1, chat_id=20, index=0) is None
    assert store.consume(token, user_id=1, chat_id=10, index=9) is None
    assert store.consume(token, user_id=1, chat_id=10, workspace_id=100, index=0) == 'create_invoice'
    assert store.consume(token, user_id=1, chat_id=10, index=0) is None

    expired = store.create(user_id=1, chat_id=10, workspace_id=100,
                           candidate_action_ids=['add_contact'])
    clock[0] += timedelta(minutes=10, seconds=1)
    assert store.consume(expired, user_id=1, chat_id=10, index=0) is None


def test_ephemeral_record_rejects_workspace_mismatch_without_consuming() -> None:
    store = ContextualRecoveryStore()
    token = store.create(user_id=1, chat_id=10, workspace_id=100,
                         candidate_action_ids=['create_invoice'])

    assert store.consume(token, user_id=1, chat_id=10, workspace_id=200, index=0) is None
    assert store.consume(token, user_id=1, chat_id=10, workspace_id=100, index=0) == 'create_invoice'
