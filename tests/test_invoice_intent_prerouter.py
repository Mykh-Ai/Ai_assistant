import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceStates,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    process_invoice_service_clarification,
    process_invoice_slot_clarification,
    process_invoice_text,
)
from bot.services.semantic_action_resolver import resolve_bounded_confirmation_reply, resolve_semantic_action


class _DummyMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.message_id = 1
        self.update_id = 1
        self.from_user = None
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False
        self.data: dict = {}
        self.current_state = None

    async def clear(self) -> None:
        self.cleared = True

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, new_state) -> None:
        self.current_state = new_state

    async def get_data(self) -> dict:
        return dict(self.data)


class _DummyDecisionState:
    def __init__(self) -> None:
        self.data = {'last_invoice_id': 999}
        self.cleared = False

    async def get_data(self) -> dict:
        return dict(self.data)

    async def clear(self) -> None:
        self.cleared = True


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def _config_with_api_key(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'test.db',
        storage_dir=tmp_path,
    )


def test_top_level_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='витворить фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='сделай фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='upraviť fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pošli fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'send_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pridaj novú službu',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'add_service_alias'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='blabla',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_invoice_create_not_misrouted_to_add_contact_when_company_mentioned() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'add_service_alias', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre company ZS',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'


def test_process_invoice_text_routes_add_service_alias_to_existing_service_flow(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('pridaj novú službu')
    state = _DummyState()
    calls: list[str] = []

    async def _resolver(**kwargs):
        return 'add_service_alias'

    async def _start_service(**kwargs) -> None:
        calls.append('service_flow')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _resolver)
    monkeypatch.setattr('bot.handlers.invoice.start_add_service_alias_intake', _start_service)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config(tmp_path),
            invoice_text='pridaj novú službu',
        )
    )

    assert calls == ['service_flow']
    assert message.answers == []


def test_state_semantic_resolver_actions() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='potvrdzujem',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_preview_confirmation',
            allowed_actions=['ano', 'nie', 'unknown'],
            user_input_text='cancel',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='invoice_postpdf_decision',
            allowed_actions=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='подтвердить',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_bounded_confirmation_resolver_is_conservative_for_noisy_short_replies() -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='Ah, não.',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_bounded_confirmation_resolver_positive_regressions() -> None:
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='áno',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'ano'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_preview_confirmation',
            expected_reply_type='yes_no_confirmation',
            allowed_outputs=['ano', 'nie', 'unknown'],
            user_input_text='нет',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'nie'
    assert asyncio.run(
        resolve_bounded_confirmation_reply(
            context_name='invoice_postpdf_decision',
            expected_reply_type='postpdf_decision',
            allowed_outputs=['schvalit', 'upravit', 'zrusit', 'unknown'],
            user_input_text='schváliť',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'schvalit'


def test_unknown_top_level_stops_flow(tmp_path: Path) -> None:
    message = _DummyMessage('blabla')
    state = _DummyState()
    asyncio.run(process_invoice_text(message=message, state=state, config=_config(tmp_path), invoice_text='blabla'))
    assert state.cleared is True
    assert 'Nerozumiem požadovanej akcii' in message.answers[-1]


def test_process_invoice_text_keeps_partial_draft_when_only_service_slot_is_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        partial_payload = {
            'vstup': {'povodny_text': 'faktura pre Tech Company 150 EUR', 'zisteny_jazyk': 'sk'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.9},
            'biznis_sk': {
                'odberatel_kandidat': 'Tech Company',
                'polozka_povodna': 'оправы',
                'termin_sluzby_sk': 'неясно',
                'mnozstvo': 1,
                'jednotka': 'ks',
                'suma': 150,
                'cena_za_jednotku': 150,
                'mena': 'EUR',
                'datum_dodania': None,
                'splatnost_dni': 14,
                'datum_splatnosti': None,
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }
        raise LlmInvoicePayloadError(
            'service unresolved',
            error_code='service_term_unresolved',
            partial_payload=partial_payload,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_service_clarification
    assert 'invoice_partial_draft' in state.data
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť typ služby. Spresnite ho, prosím.'


def test_process_invoice_text_keeps_partial_draft_when_customer_slot_is_unknown(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        partial_payload = {
            'vstup': {'povodny_text': 'faktura za opravu 150 EUR', 'zisteny_jazyk': 'sk'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.9},
            'biznis_sk': {
                'odberatel_kandidat': 'pre firmu',
                'polozka_povodna': 'oprava',
                'termin_sluzby_sk': 'oprava',
                'mnozstvo': 1,
                'jednotka': 'ks',
                'suma': 150,
                'cena_za_jednotku': 150,
                'mena': 'EUR',
                'datum_dodania': '2026-04-12',
                'splatnost_dni': 14,
                'datum_splatnosti': None,
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }
        raise LlmInvoicePayloadError(
            'customer unresolved',
            error_code='customer_unresolved',
            partial_payload=partial_payload,
        )

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is False
    assert state.current_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'customer_name'
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť odberateľa. Spresnite názov firmy, prosím.'


def test_service_clarification_continues_to_preview_without_restart(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('oprava')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-1',
        'raw_text': 'faktura pre Tech Company 150 EUR',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'оправы',
            'service_term_sk': 'неясно',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': None,
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_service_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='oprava',
        )
    )

    assert captured['parsed_draft']['service_term_sk'] == 'oprava'
    assert captured['parsed_draft']['item_name_raw'] == 'oprava'
    assert captured['raw_text'] == 'faktura pre Tech Company 150 EUR'


def test_slot_clarification_applies_delivery_date_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('13.04.2026')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-2',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'delivery_date',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': None,
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='13.04.2026',
        )
    )

    assert captured['parsed_draft']['delivery_date'] == '2026-04-13'


def test_slot_clarification_applies_due_days_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('21')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-3',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'due_days',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 1,
            'unit': 'ks',
            'amount': 150,
            'unit_price': 150,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': None,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='21',
        )
    )

    assert captured['parsed_draft']['due_days'] == 21


def test_slot_clarification_applies_unit_price_and_continues_to_preview(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('250')
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-4',
        'raw_text': 'faktura pre Tech Company oprava 2x',
        'unresolved_slot': 'unit_price',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': 2,
            'unit': 'ks',
            'amount': None,
            'unit_price': None,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text='250',
        )
    )

    assert captured['parsed_draft']['unit_price'] == 250.0


@pytest.mark.parametrize(
    'clarification_text,expected_quantity,expected_unit_price',
    [
        ('3 1500', 3.0, 1500.0),
        ('3 * 1500', 3.0, 1500.0),
        ('3 po 1500', 3.0, 1500.0),
        ('три kusy по 1500', 3.0, 1500.0),
        ('množstvo 3, cena za kus 1500', 3.0, 1500.0),
        ('количество 3, цена 1500', 3.0, 1500.0),
        ('2 крат по 1500', 2.0, 1500.0),
        ('два крат по 1500', 2.0, 1500.0),
        ('dva krát po 1500', 2.0, 1500.0),
        ('1500', 1.0, 1500.0),
        ('3000', 1.0, 3000.0),
    ],
)
def test_slot_clarification_applies_quantity_unit_price_pair_and_continues_to_preview(
    tmp_path: Path, monkeypatch, clarification_text: str, expected_quantity: float, expected_unit_price: float
) -> None:
    message = _DummyMessage(clarification_text)
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-qp',
        'raw_text': 'faktura pre Tech Company oprava',
        'unresolved_slot': 'quantity_unit_price_pair',
        'parsed_draft': {
            'customer_name': 'Tech Company',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': None,
            'unit': 'ks',
            'amount': None,
            'unit_price': None,
            'currency': 'EUR',
            'delivery_date': '2026-04-12',
            'due_days': 14,
            'due_date': None,
        },
    }
    captured: dict = {}

    async def _fake_build_and_store_preview(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=_config(tmp_path),
            clarification_text=clarification_text,
        )
    )

    assert captured['parsed_draft']['quantity'] == expected_quantity
    assert captured['parsed_draft']['unit_price'] == expected_unit_price


def test_process_invoice_text_fails_loudly_on_fatal_payload_error(tmp_path: Path, monkeypatch) -> None:
    message = _DummyMessage('sprav fakturu')
    state = _DummyState()

    async def _fake_action(**kwargs):
        return 'create_invoice'

    async def _fake_parse(*args, **kwargs):
        from bot.services.llm_invoice_parser import LlmInvoicePayloadError

        raise LlmInvoicePayloadError('fatal shape issue', error_code='fatal_payload')

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_action)
    monkeypatch.setattr('bot.handlers.invoice.parse_invoice_phase2_payload', _fake_parse)

    asyncio.run(
        process_invoice_text(
            message=message,
            state=state,
            config=_config_with_api_key(tmp_path),
            invoice_text='sprav fakturu',
        )
    )

    assert state.cleared is True
    assert message.answers[-1] == 'AI návrh faktúry bol neplatný. Skúste vstup poslať znova.'


def test_preview_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('maybe')
    state = _DummyState()
    asyncio.run(
        process_invoice_preview_confirmation(
            message=message,
            state=state,
            config=_config(tmp_path),
            confirmation_text='maybe',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte áno alebo nie.'


def test_postpdf_unknown_reply(tmp_path: Path) -> None:
    message = _DummyMessage('later')
    state = _DummyDecisionState()
    asyncio.run(
        process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=_config(tmp_path),
            decision_text='later',
        )
    )
    assert message.answers[-1] == 'Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.'
