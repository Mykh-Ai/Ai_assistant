import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceStates,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    process_invoice_service_clarification,
    process_invoice_text,
)
from bot.services.semantic_action_resolver import resolve_semantic_action


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
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='витворить фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='сделай фактуру для Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre Tech Company',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='upraviť fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'edit_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='pošli fakturu 20260001',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'send_invoice'
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='blabla',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'unknown'


def test_invoice_create_not_misrouted_to_add_contact_when_company_mentioned() -> None:
    assert asyncio.run(
        resolve_semantic_action(
            context_name='top_level_action',
            allowed_actions=['create_invoice', 'add_contact', 'send_invoice', 'edit_invoice', 'unknown'],
            user_input_text='sprav fakturu pre company ZS',
            api_key=None,
            model='gpt-4o',
        )
    ) == 'create_invoice'


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
