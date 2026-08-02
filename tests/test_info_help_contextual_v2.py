import asyncio
import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import pytest

from bot.services.info_help import (
    INFO_HELP_INTENT_GENUINELY_UNCLEAR,
    INFO_HELP_SPEECH_CAPABILITY_QUESTION,
    build_info_help_product_truth_view,
    parse_info_help_assistant_model_output,
    should_run_contextual_info_help,
)
from bot.services.info_help_action_registry import (
    find_exact_info_help_action,
    get_info_help_action,
)
from bot.services.info_help_context import InfoHelpConversationContextService
from bot.services.info_help_resolver import (
    build_info_help_assistant_payload,
    resolve_info_help_assistant_with_llm,
)


def _assistant_json(**overrides) -> str:
    payload = {
        'intent_kind': 'business_action_request',
        'speech_act': 'execute_request',
        'domain_id': 'invoices',
        'object_kind': 'invoice',
        'operation_id': 'delete',
        'target_reference': '10',
        'proposed_action_id': 'delete_existing_invoice',
        'proposed_capability_id': 'delete_existing_invoice',
        'probable_command_target': None,
        'intent_complete': True,
        'missing_slots': [],
        'is_correction': False,
        'negated_objects': [],
        'negated_operations': [],
        'corrected_from_object': None,
        'corrected_to_object': None,
        'refers_to_active_flow': False,
        'refers_to_explicit_reply': False,
        'confidence': 0.99,
        'acknowledgement_sk': 'Rozumiem, chcete vymazať faktúru.',
        'clarification_question_sk': '',
    }
    payload.update(overrides)
    return json.dumps(payload, ensure_ascii=False)


def test_parser_preserves_exact_receipt_delete_capability_question() -> None:
    result = parse_info_help_assistant_model_output(
        _assistant_json(
            intent_kind='capability_question',
            speech_act='capability_question',
            domain_id='accounting_documents',
            object_kind='receipt',
            operation_id='delete',
            target_reference=None,
            proposed_action_id=None,
            proposed_capability_id=None,
            intent_complete=True,
            confidence=0.97,
        )
    )

    assert result.speech_act == INFO_HELP_SPEECH_CAPABILITY_QUESTION
    assert result.domain_id == 'accounting_documents'
    assert result.object_kind == 'receipt'
    assert result.operation_id == 'delete'
    assert result.proposed_action_id is None


def test_parser_fails_closed_for_unknown_ids_and_oversized_text() -> None:
    result = parse_info_help_assistant_model_output(
        _assistant_json(
            intent_kind='invented',
            speech_act='invented',
            domain_id='invented',
            object_kind='invented',
            operation_id='invented',
            proposed_action_id='drop_everything',
            proposed_capability_id='invented',
            probable_command_target='/root',
            confidence=4,
            acknowledgement_sk='x' * 1000,
        )
    )

    assert result.intent_kind == INFO_HELP_INTENT_GENUINELY_UNCLEAR
    assert result.proposed_action_id is None
    assert result.proposed_capability_id is None
    assert result.probable_command_target is None
    assert result.confidence == 0.0
    assert len(result.acknowledgement_sk) <= 240


@pytest.mark.parametrize(
    'override',
    (
        {'proposed_action_id': 'drop_everything'},
        {'proposed_capability_id': 'invented_capability'},
        {'probable_command_target': '/root'},
    ),
)
def test_parser_fails_closed_for_each_unknown_bounded_identifier(override) -> None:
    result = parse_info_help_assistant_model_output(_assistant_json(**override))

    assert result.intent_kind == INFO_HELP_INTENT_GENUINELY_UNCLEAR
    assert result.confidence == 0.0


def test_exact_semantic_registry_never_crosses_business_objects() -> None:
    invoice_delete = find_exact_info_help_action(
        domain_id='invoices', object_kind='invoice', operation_id='delete'
    )
    receipt_delete = find_exact_info_help_action(
        domain_id='accounting_documents', object_kind='receipt', operation_id='delete'
    )
    contact_edit = find_exact_info_help_action(
        domain_id='contacts', object_kind='contact', operation_id='edit'
    )

    assert invoice_delete is not None and invoice_delete.action_id == 'delete_existing_invoice'
    assert receipt_delete is None
    assert contact_edit is None
    assert get_info_help_action('delete_user_database').infohelp_action_button_allowed is False


def test_product_truth_view_is_derived_and_contains_no_forbidden_raw_fields() -> None:
    view = build_info_help_product_truth_view()
    delete_invoice = next(item for item in view if item['capability_id'] == 'delete_existing_invoice')

    assert delete_invoice['product_status'] == 'supported'
    assert delete_invoice['dangerous'] is True
    assert delete_invoice['runtime_owner'] is True
    assert 'truth_source_refs' not in delete_invoice
    assert 'test_refs' not in delete_invoice


def test_context_service_bounds_ttl_roles_and_isolation() -> None:
    now = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)
    service = InfoHelpConversationContextService(ttl=timedelta(minutes=10), max_turns_per_role=3)
    key = service.key(telegram_user_id=11, chat_id=22, workspace_id='w1')
    other = service.key(telegram_user_id=11, chat_id=23, workspace_id='w1')

    for index in range(4):
        service.capture_user(key, text=f'u{index}', channel='text', created_at=now + timedelta(seconds=index))
        service.capture_bot(key, text=f'b{index}', visible_button_labels=(f'B{index}',), created_at=now + timedelta(seconds=index))
    service.capture_user(other, text='isolated', channel='text', created_at=now)

    recent = service.recent(key, now=now + timedelta(minutes=5))
    assert [turn.text for turn in recent if turn.role == 'user'] == ['u1', 'u2', 'u3']
    assert [turn.text for turn in recent if turn.role == 'bot'] == ['b1', 'b2', 'b3']
    assert all(turn.text != 'isolated' for turn in recent)
    assert service.recent(key, now=now + timedelta(minutes=11)) == ()
    assert InfoHelpConversationContextService().recent(key, now=now) == ()


def test_payload_contains_context_product_truth_actions_and_reply() -> None:
    payload = build_info_help_assistant_payload(
        current_input_text='Чому ти це кажеш?',
        input_channel='text',
        primary_resolver_result='unknown',
        primary_resolver_diagnostics={'slots': {}},
        primary_mutation_class='informational',
        recent_conversation=({'role': 'bot', 'text': 'Predošlá odpoveď'},),
        explicit_reply={
            'replied_to_bot_text': 'Aktívny business profil nie je dostupný.',
            'replied_to_visible_button_labels': [],
            'replied_to_message_id': 9,
            'replied_to_is_our_bot': True,
        },
        active_runtime_context={'current_fsm_state_descriptor': None},
        known_command_tokens=('/contact', '/invoice'),
    )

    assert payload['current_input']['current_input_text'] == 'Чому ти це кажеш?'
    assert payload['explicit_telegram_reply']['replied_to_is_our_bot'] is True
    assert payload['recent_conversation'][0]['text'] == 'Predošlá odpoveď'
    assert payload['product_and_action_context']['product_truth']
    assert payload['product_and_action_context']['canonical_actions']


def test_payload_exposes_exact_enum_values_and_receipt_negative_space_example() -> None:
    payload = build_info_help_assistant_payload(
        current_input_text='Чи можу я видалити чек?',
        input_channel='text',
        primary_resolver_result='delete_existing_invoice',
        primary_mutation_class='destructive',
    )
    serialized = json.dumps(payload, ensure_ascii=False)
    assert 'one bounded intent kind' not in serialized
    assert 'capability_question' in payload['expected_output']['intent_kind']['allowed_values']
    example = payload['product_and_action_context']['critical_semantic_examples'][0]['result']
    assert (example['domain_id'], example['object_kind'], example['operation_id']) == ('accounting_documents', 'receipt', 'delete')
    assert payload['product_and_action_context']['primary_resolver_is_untrusted_diagnostic'] is True
    reference_example = payload['product_and_action_context']['critical_semantic_examples'][-1]['result']
    assert reference_example['target_reference'] == '10'
    assert reference_example['intent_complete'] is True
    assert reference_example['missing_slots'] == []


def test_pre_execution_gate_covers_unknown_destructive_correction_and_command() -> None:
    assert should_run_contextual_info_help(primary_action='unknown', input_text='x')
    assert should_run_contextual_info_help(primary_action='delete_existing_invoice', input_text='vymaž faktúru')
    assert should_run_contextual_info_help(primary_action='edit_supplier', input_text='kontakt, nie profil')
    assert should_run_contextual_info_help(primary_action='unknown', input_text='/contat', input_channel='command')
    assert not should_run_contextual_info_help(primary_action='show_supplier_profile', input_text='ukáž profil')


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


class _Completions:
    calls = 0

    async def create(self, **kwargs):
        type(self).calls += 1
        return _Completion(_assistant_json())


class _Client:
    def __init__(self, **kwargs) -> None:
        self.chat = SimpleNamespace(completions=_Completions())


def test_resolver_makes_exactly_one_enhanced_infohelp_call(monkeypatch) -> None:
    _Completions.calls = 0
    monkeypatch.setattr('bot.services.info_help_resolver.AsyncOpenAI', _Client)

    result = asyncio.run(
        resolve_info_help_assistant_with_llm(
            current_input_text='delete invoice 10',
            api_key='sk-test',
            model='gpt-4o',
            input_channel='text',
            primary_resolver_result='delete_existing_invoice',
        )
    )

    assert result.proposed_action_id == 'delete_existing_invoice'
    assert _Completions.calls == 1
