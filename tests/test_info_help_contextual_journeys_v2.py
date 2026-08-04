import asyncio
import json
import logging
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    CustomizationRequestStates,
    InvoiceReferenceContinuationStates,
    InvoiceStates,
    _observable_resolver_diagnostics,
    info_help_admin_offer_text_fallback,
    process_invoice_text,
    unknown_slash_command,
)
from bot.services.active_fsm_guard import handle_active_fsm_text_update
from bot.services.db import init_db
from bot.services.customization_requests import CustomizationRequestService
from bot.services.info_help_assistant import InfoHelpAssistantResult
from bot.services.info_help_rollout import contextual_info_help_v2_enabled
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _Message:
    def __init__(self, text: str, telegram_id: int = 111) -> None:
        self.text = text
        self.message_id = 1
        self.from_user = type('User', (), {'id': telegram_id})()
        self.chat = type('Chat', (), {'id': telegram_id + 1000})()
        self.answers: list[str] = []
        self.answer_kwargs: list[dict] = []

    async def answer(self, text: str, **kwargs):
        self.answers.append(text)
        self.answer_kwargs.append(kwargs)
        return type('SentMessage', (), {'message_id': len(self.answers) + 500})()

    async def answer_document(self, *args, **kwargs) -> None:
        return None


class _State:
    def __init__(self, current_state=None, data=None) -> None:
        self.current_state = current_state
        self.data = dict(data or {})
        self.cleared = False

    async def get_state(self):
        return self.current_state

    async def set_state(self, value) -> None:
        self.current_state = getattr(value, 'state', value)

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def clear(self) -> None:
        self.current_state = None
        self.data.clear()
        self.cleared = True


def _config(
    tmp_path: Path,
    *,
    rollout: str = 'enabled',
    admins=(),
    debug_invoice_transparency: bool = False,
) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=debug_invoice_transparency,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
        admin_telegram_user_ids=frozenset(admins),
        infohelp_contextual_v2_rollout=rollout,
    )


def _result(**overrides) -> InfoHelpAssistantResult:
    values = {
        'intent_kind': 'business_action_request',
        'speech_act': 'execute_request',
        'domain_id': 'invoices',
        'object_kind': 'invoice',
        'operation_id': 'delete',
        'proposed_action_id': 'delete_existing_invoice',
        'intent_complete': True,
        'confidence': 0.99,
    }
    values.update(overrides)
    return InfoHelpAssistantResult(**values)


def test_infohelp_raw_model_output_is_hidden_without_debug_transparency() -> None:
    visible = _observable_resolver_diagnostics(
        {
            'call_status': 'completed',
            'raw_model_output': '{"intent_kind":"genuinely_unclear"}',
            'parsed_model_output': {'intent_kind': 'genuinely_unclear'},
            'parse': {'status': 'accepted'},
        },
        include_raw_model_output=False,
    )

    assert visible == {
        'call_status': 'completed',
        'parse': {'status': 'accepted'},
    }


def test_yearly_invoice_analytics_logs_infohelp_raw_result_and_unclear_outcome(
    tmp_path: Path,
    monkeypatch,
    caplog,
) -> None:
    config = _config(tmp_path, debug_invoice_transparency=True)
    init_db(config.db_path)
    message = _Message('На яку суму я виставив фактур цього року?')
    state = _State()
    raw_model_output = json.dumps(
        {
            'intent_kind': 'genuinely_unclear',
            'speech_act': 'unknown',
            'domain_id': 'unknown',
            'object_kind': 'unknown',
            'operation_id': 'unknown',
            'confidence': 0.0,
        },
        ensure_ascii=False,
    )

    async def _primary(**kwargs):
        return 'invoice_analytics'

    async def _assistant(**kwargs):
        kwargs['diagnostics'].update(
            {
                'call_status': 'completed',
                'fallback_reason': None,
                'model': config.openai_llm_model,
                'input_channel': 'voice_stt',
                'primary_resolver_result': 'invoice_analytics',
                'recent_turn_count': 1,
                'explicit_reply_present': False,
                'active_runtime_context_present': False,
                'duration_ms': 123,
                'raw_model_output': raw_model_output,
                'parse': {
                    'status': 'accepted',
                    'reason': None,
                    'invalid_fields': [],
                },
            }
        )
        return _result(
            intent_kind='genuinely_unclear',
            speech_act='unknown',
            domain_id='unknown',
            object_kind='unknown',
            operation_id='unknown',
            proposed_action_id=None,
            intent_complete=False,
            confidence=0.0,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    with caplog.at_level(logging.INFO, logger='bot.handlers.invoice'):
        asyncio.run(
            process_invoice_text(
                message=message,
                state=state,
                config=config,
                invoice_text=message.text,
                request_id='repeat-analytics-question',
                input_channel='voice',
                telegram_update_id=77,
            )
        )

    events = [json.loads(record.message) for record in caplog.records if record.message.startswith('{')]
    model_event = next(item for item in events if item.get('event') == 'contextual_info_help_model_result')
    outcome_event = next(item for item in events if item.get('event') == 'contextual_info_help_outcome')

    assert model_event['request_id'] == 'repeat-analytics-question'
    assert model_event['telegram_update_id'] == 77
    assert model_event['primary_action'] == 'invoice_analytics'
    assert model_event['primary_product_status'] == 'partial'
    assert model_event['primary_runtime_owner'] is True
    assert model_event['contextual_info_help_routing'] == {
        'primary_action': 'invoice_analytics',
        'input_channel': 'voice',
        'decision': True,
        'trigger_reason': 'question_form',
        'semantic_registry_match': False,
        'primary_product_status': None,
        'primary_runtime_owner': None,
    }
    assert model_event['info_help_model_diagnostics']['raw_model_output'] == raw_model_output
    assert model_event['info_help_model_diagnostics']['parse']['status'] == 'accepted'
    assert model_event['info_help_validated_result']['intent_kind'] == 'genuinely_unclear'
    assert outcome_event['outcome'] == 'unclear_fallback'
    assert outcome_event['handled'] is True
    assert outcome_event['validated_action'] == 'invoice_analytics'
    assert outcome_event['response_text'] == message.answers[-1]
    assert 'nerozumel' in outcome_event['response_text']


@pytest.mark.parametrize('input_channel', ('text', 'voice'))
def test_receipt_delete_capability_question_blocks_false_invoice_delete(
    tmp_path: Path, monkeypatch, input_channel: str
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('Чи можу я видалити чек?')
    state = _State()

    async def _primary(**kwargs):
        return 'delete_existing_invoice'

    async def _assistant(**kwargs):
        return _result(
            intent_kind='capability_question',
            speech_act='capability_question',
            domain_id='accounting_documents',
            object_kind='receipt',
            operation_id='delete',
            proposed_action_id=None,
            confidence=0.98,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=message.text,
            input_channel=input_channel,
        )
    )

    answer = message.answers[-1].casefold()
    assert 'nepodporujem' in answer
    assert 'inú deštruktívnu akciu' in answer
    assert state.current_state == CustomizationRequestStates.waiting_admin_offer_decision.state
    labels = [
        button.text
        for row in message.answer_kwargs[-1]['reply_markup'].inline_keyboard
        for button in row
    ]
    assert labels == ['Požiadať správcu', 'Hlavné menu']
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=111,
    ) == []
    assert state.data['customization_request_draft']['source_channel'] == input_channel
    assert state.data['info_help_offer_message_id'] == 501
    assert state.data['info_help_offer_chat_id'] == 111 + 1000
    assert 'číslo faktúry' not in answer


def test_correction_negates_invoice_and_blocks_delete_flow(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('Я хочу чек видалити, а не фактуру!')
    state = _State()

    async def _primary(**kwargs):
        return 'delete_existing_invoice'

    async def _assistant(**kwargs):
        return _result(
            speech_act='correction',
            domain_id='accounting_documents',
            object_kind='receipt',
            operation_id='delete',
            proposed_action_id=None,
            is_correction=True,
            negated_objects=('invoice',),
            corrected_from_object='invoice',
            corrected_to_object='receipt',
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert 'nepodporujem' in message.answers[-1].casefold()
    assert state.current_state == CustomizationRequestStates.waiting_admin_offer_decision.state
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=111,
    ) == []


def test_info_help_admin_offer_free_text_repeats_buttons_without_local_route_or_save(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('зроби щось інше')
    state = _State(
        current_state=CustomizationRequestStates.waiting_admin_offer_decision.state,
    )

    asyncio.run(info_help_admin_offer_text_fallback(message))

    assert state.current_state == CustomizationRequestStates.waiting_admin_offer_decision.state
    assert 'jednu z možností' in message.answers[-1]
    labels = [
        button.text
        for row in message.answer_kwargs[-1]['reply_markup'].inline_keyboard
        for button in row
    ]
    assert labels == ['Požiadať správcu', 'Hlavné menu']
    assert CustomizationRequestService(config.db_path).list_customization_requests_for_user(
        telegram_id=111,
    ) == []


def test_supported_invoice_delete_without_reference_bypasses_infohelp_and_enters_continuation(
    tmp_path: Path, monkeypatch
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('Vymazať faktúru')
    state = _State()

    async def _primary(**kwargs):
        return 'delete_existing_invoice'

    assistant_calls: list[str] = []

    async def _assistant(**kwargs):
        assistant_calls.append(kwargs['current_input_text'])
        return _result(
            intent_complete=False,
            missing_slots=('invoice_reference',),
            confidence=0.97,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state == InvoiceReferenceContinuationStates.waiting_reference.state
    assert state.data['pending_invoice_reference_action'] == 'delete_existing_invoice'
    assert assistant_calls == []


@pytest.mark.parametrize('input_channel', ('text', 'voice'))
def test_supported_invoice_delete_reaches_existing_owner_once_without_infohelp(
    tmp_path: Path, monkeypatch, input_channel: str
) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(
            telegram_id=111,
            name='Supplier',
            ico='1',
            dic='1',
            ic_dph='',
            address='Address',
            iban='SK1',
            swift='ABCD',
            email='supplier@example.test',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    invoice_service = InvoiceService(config.db_path)
    invoice_id = invoice_service.create_invoice_with_items(
        supplier_telegram_id=111,
        contact_id=1,
        issue_date='2026-08-04',
        delivery_date='2026-08-04',
        due_date='2026-08-18',
        due_days=14,
        total_amount=10,
        currency='EUR',
        status='draft',
        items=[
            CreateInvoiceItemPayload(
                description_raw='service',
                description_normalized='service',
                item_description_raw='',
                quantity=1,
                unit='ks',
                unit_price=10,
                total_price=10,
            )
        ],
        invoice_number='20260010',
    )
    message = _Message('Видалити фактуру 10')
    state = _State()
    assistant_calls: list[str] = []
    owner_calls: list[tuple[str, str]] = []

    async def _primary(**kwargs):
        return 'delete_existing_invoice'

    async def _assistant(**kwargs):
        assistant_calls.append(kwargs['current_input_text'])
        return _result(confidence=0.97)

    from bot.handlers import invoice as invoice_handler

    real_owner = invoice_handler._execute_invoice_reference_action

    async def _owner(**kwargs):
        owner_calls.append((kwargs['action_id'], kwargs['invoice_reference']))
        await real_owner(**kwargs)

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    monkeypatch.setattr('bot.handlers.invoice._execute_invoice_reference_action', _owner)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=message.text,
            input_channel=input_channel,
        )
    )

    assert assistant_calls == []
    assert owner_calls == [('delete_existing_invoice', '10')]
    assert state.current_state == InvoiceStates.waiting_delete_existing_invoice_confirm.state
    assert invoice_service.get_invoice_by_id(invoice_id) is not None
    assert message.answers[-1] == (
        'Naozaj chcete vymazať faktúru 20260010? Odpovedzte: áno / nie'
    )


def test_unsupported_contact_edit_uses_infohelp_without_supplier_profile_edit(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _Message('Редагувати контакт')
    state = _State()
    supplier_calls: list[str] = []
    assistant_calls: list[str] = []

    async def _primary(**kwargs):
        return 'unknown'

    async def _assistant(**kwargs):
        assistant_calls.append(kwargs['current_input_text'])
        return _result(
            domain_id='contacts', object_kind='contact', operation_id='edit',
            proposed_action_id=None, confidence=0.97,
        )

    async def _supplier(**kwargs):
        supplier_calls.append('called')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    monkeypatch.setattr('bot.handlers.invoice.cmd_upravit_profil', _supplier)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert supplier_calls == []
    assert assistant_calls == [message.text]
    assert 'nepodporujem' in message.answers[-1].casefold()


def test_vague_delete_is_clarified_without_destructive_route(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    message = _Message('видалити')
    state = _State()

    async def _primary(**kwargs):
        return 'delete_user_database'

    async def _assistant(**kwargs):
        return _result(
            intent_kind='incomplete_intent',
            domain_id='unknown',
            object_kind='unknown',
            operation_id='delete',
            proposed_action_id=None,
            intent_complete=False,
            clarification_question_sk='Čo presne chcete vymazať?',
            confidence=0.96,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert message.answers == ['Čo presne chcete vymazať?']
    assert state.current_state is None


def test_vague_delete_cannot_replace_conflicting_primary_destructive_action(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    message = _Message('видалити')
    state = _State()

    async def _primary(**kwargs):
        return 'delete_user_database'

    async def _assistant(**kwargs):
        return _result(
            intent_kind='business_action_request',
            domain_id='invoices',
            object_kind='invoice',
            operation_id='delete',
            proposed_action_id='delete_existing_invoice',
            intent_complete=False,
            missing_slots=('invoice_reference',),
            confidence=0.99,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert state.current_state is None
    assert message.answers[-1] == 'Spresnite prosím presný objekt a úkon. Nič som nevykonal.'


def test_explicit_reply_unclear_result_explains_proven_quoted_bot_message(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    message = _Message('Чому ти це кажеш?')
    message.bot = type('Bot', (), {'id': 999})()
    message.reply_to_message = type(
        'Reply',
        (),
        {
            'chat': message.chat,
            'from_user': type('BotUser', (), {'id': 999, 'is_bot': True})(),
            'message_id': 77,
            'text': 'Aktívny business profil nie je dostupný alebo nie je vybraný.',
            'reply_markup': None,
        },
    )()
    state = _State()

    async def _primary(**kwargs):
        return 'unknown'

    async def _assistant(**kwargs):
        return _result(
            intent_kind='genuinely_unclear',
            speech_act='unknown',
            domain_id='unknown',
            object_kind='unknown',
            operation_id='unknown',
            proposed_action_id=None,
            intent_complete=False,
            refers_to_explicit_reply=True,
            confidence=0.0,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _primary)
    monkeypatch.setattr('bot.handlers.invoice.resolve_info_help_assistant_with_llm', _assistant)
    asyncio.run(process_invoice_text(message=message, state=state, config=config, invoice_text=message.text))

    assert 'Citovaná správa bola' in message.answers[-1]
    assert 'Aktívny business profil' in message.answers[-1]
    assert 'sama nič nevytvorila, nezmenila ani nevymazala' in message.answers[-1]
    assert 'nerozumel' not in message.answers[-1]
    assert state.current_state is None


def test_unknown_command_route_is_final_and_uses_command_channel(tmp_path: Path, monkeypatch) -> None:
    message = _Message('/contat')
    state = _State()
    captured: dict[str, object] = {}

    async def _process(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice.process_invoice_text', _process)
    asyncio.run(unknown_slash_command(message, state, _config(tmp_path)))

    assert captured['invoice_text'] == '/contat'
    assert captured['input_channel'] == 'command'


def test_active_fsm_help_keeps_state_and_calls_contextual_assistant_once(tmp_path: Path, monkeypatch) -> None:
    state_name = 'InvoiceStates:waiting_service_clarification'
    state = _State(current_state=state_name)
    message = _Message('Що треба ввести?')
    calls: list[str] = []

    async def _navigation(**kwargs):
        return 'describe_expected_input'

    async def _assistant(**kwargs):
        calls.append(kwargs['current_input_text'])
        return _result(intent_kind='active_expected_input_question', speech_act='informational_question')

    monkeypatch.setattr('bot.services.active_fsm_guard.resolve_active_fsm_navigation', _navigation)
    monkeypatch.setattr('bot.services.info_help_resolver.resolve_info_help_assistant_with_llm', _assistant)
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
    assert state.current_state == state_name
    assert calls == [message.text]
    assert 'stručný opis služby' in message.answers[-1]
    assert message.answer_kwargs[-1]['reply_markup'] is not None


def test_rollout_modes_fail_closed_and_admin_pilot_is_scoped(tmp_path: Path) -> None:
    assert contextual_info_help_v2_enabled(_config(tmp_path, rollout='disabled'), 111) is False
    assert contextual_info_help_v2_enabled(_config(tmp_path, rollout='invalid'), 111) is False
    pilot = _config(tmp_path, rollout='admin_pilot', admins=(111,))
    assert contextual_info_help_v2_enabled(pilot, 111) is True
    assert contextual_info_help_v2_enabled(pilot, 222) is False
    assert contextual_info_help_v2_enabled(_config(tmp_path, rollout='enabled'), 222) is True
