from __future__ import annotations

from datetime import date
from pathlib import Path

import asyncio

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    InvoiceStates,
    _build_and_store_preview,
    _extract_invoice_draft_from_phase2_payload,
    _format_preview,
    _looks_like_item_boundary_split,
    _SLOT_ITEMS,
    _resolve_delivery_date,
    _resolve_service_alias_bounded,
    process_invoice_slot_clarification,
)
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db
from bot.services.llm_invoice_parser import LlmInvoicePayloadError, validate_invoice_phase2_payload
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, user_id: int) -> None:
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.data: dict = {}
        self.last_state = None
        self.cleared = False

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, new_state) -> None:
        self.last_state = new_state

    async def clear(self) -> None:
        self.cleared = True

    async def get_data(self) -> dict:
        return dict(self.data)


@pytest.fixture()
def configured_db(tmp_path: Path) -> tuple[Path, int, int]:
    db_path = tmp_path / 'phase2.db'
    init_db(db_path)

    telegram_id = 555
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=telegram_id,
            name='Dodavatel SK',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Bratislava 1',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='supplier@example.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )

    ContactService(db_path).create_or_replace(
        ContactProfile(
            supplier_telegram_id=telegram_id,
            name='Tech Company s.r.o.',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Kosice 2',
            email='contact@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )

    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None
    assert supplier.id is not None
    ServiceAliasService(db_path).create_mapping(
        supplier.id,
        service_short_name='oprava',
        service_display_name='Servis a oprava zariadenia',
    )

    contact = ContactService(db_path).get_by_name(telegram_id, 'Tech Company s.r.o.')
    assert contact is not None
    assert contact.id is not None

    return db_path, telegram_id, contact.id


def _valid_payload(original_text: str) -> dict:
    return {
        'vstup': {'povodny_text': original_text, 'zisteny_jazyk': 'mixed'},
        'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.93},
        'biznis_sk': {
            'odberatel_kandidat': 'Tech Company',
            'polozka_povodna': 'oprava',
            'termin_sluzby_sk': 'oprava',
            'mnozstvo': 1,
            'jednotka': 'ks',
            'suma': 150,
            'cena_za_jednotku': 150,
            'mena': 'EUR',
            'datum_dodania': '2026-04-12',
            'splatnost_dni': 7,
            'datum_splatnosti': None,
        },
        'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': ['ремонт -> oprava']},
    }


def test_extract_payload_preserves_original_text_and_sk_fields() -> None:
    payload = _valid_payload('сделай фактуру для Tech Company, ремонт 150 EUR')

    raw_text, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    assert raw_text == 'сделай фактуру для Tech Company, ремонт 150 EUR'
    assert parsed['customer_name'] == 'Tech Company'
    assert parsed['item_name_raw'] == 'oprava'
    assert parsed['service_term_sk'] == 'oprava'
    assert parsed['amount'] == 150
    assert parsed['unit_price'] == 150
    assert isinstance(parsed['items'], list)
    assert len(parsed['items']) == 1


def test_extract_payload_uses_items_list_when_present() -> None:
    payload = _valid_payload('oprava 3000 a montáž 1000')
    payload['biznis_sk']['items'] = [
        {
            'polozka_povodna': 'oprava',
            'termin_sluzby_sk': 'oprava',
            'mnozstvo': 1,
            'jednotka': 'ks',
            'cena_za_jednotku': 3000,
            'suma': 3000,
            'item_description_raw': None,
        },
        {
            'polozka_povodna': 'montáž',
            'termin_sluzby_sk': 'montáž',
            'mnozstvo': 1,
            'jednotka': 'ks',
            'cena_za_jednotku': 1000,
            'suma': 1000,
            'item_description_raw': None,
        },
    ]

    raw_text, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    assert raw_text == 'oprava 3000 a montáž 1000'
    assert len(parsed['items']) == 2
    assert parsed['items'][1]['service_term_sk'] == 'montáž'


@pytest.mark.parametrize(
    'text,expected_item_count',
    [
        ('polozka 1 oprava 2000 polozka 2 stavebne prace 1000', 2),
        ('pozicia 1 oprava 2000 pozicia 2 montaz 1000 pozicia 3 servis 500', 3),
        ('item number 1 service 200 item number 2 maintenance 100', 2),
    ],
)
def test_numbered_item_markers_count_as_item_boundaries(text: str, expected_item_count: int) -> None:
    assert _looks_like_item_boundary_split(text, expected_item_count=expected_item_count) is True


@pytest.mark.parametrize(
    'text,lang,term',
    [
        ('ремонт для Tech Company', 'ru', 'oprava'),
        ('рахунок pre Tech Company, opravy 220', 'mixed', 'oprava'),
        ('faktura pre Tech Company za opravy', 'sk', 'oprava'),
    ],
)
def test_validate_payload_accepts_multilingual_invoice_like_samples(text: str, lang: str, term: str) -> None:
    payload = _valid_payload(text)
    payload['vstup']['zisteny_jazyk'] = lang
    payload['biznis_sk']['termin_sluzby_sk'] = term

    validated = validate_invoice_phase2_payload(payload)

    assert validated['vstup']['povodny_text'] == text
    assert validated['biznis_sk']['termin_sluzby_sk'] == term


def test_validate_payload_fails_loudly_on_malformed_shape() -> None:
    with pytest.raises(LlmInvoicePayloadError):
        validate_invoice_phase2_payload({'vstup': {'povodny_text': 'x', 'zisteny_jazyk': 'sk'}})


@pytest.mark.parametrize(
    'bad_candidate',
    [
        '   ',
        '---',
        '!!!',
        '()',
    ],
)
def test_validate_payload_rejects_structurally_invalid_customer_candidate(bad_candidate: str) -> None:
    payload = _valid_payload('сделай фактуру на техкомпании за ремонт 150 eur')
    payload['biznis_sk']['odberatel_kandidat'] = bad_candidate

    with pytest.raises(LlmInvoicePayloadError) as exc_info:
        validate_invoice_phase2_payload(payload)
    assert exc_info.value.error_code == 'customer_unresolved'
    assert exc_info.value.partial_payload is not None


def test_validate_payload_accepts_noisy_phrase_like_customer_candidate() -> None:
    payload = _valid_payload('sprav fakturu pre firmu tech company za opravu')
    payload['biznis_sk']['odberatel_kandidat'] = 'pre firmu tech company'

    validated = validate_invoice_phase2_payload(payload)

    assert validated['biznis_sk']['odberatel_kandidat'] == 'pre firmu tech company'


def test_validate_payload_accepts_lookup_ready_latin_customer_candidate() -> None:
    payload = _valid_payload('сделай фактуру на техкомпании за ремонт 150 eur')
    payload['biznis_sk']['odberatel_kandidat'] = 'Tech Company s.r.o.'

    validated = validate_invoice_phase2_payload(payload)

    assert validated['biznis_sk']['odberatel_kandidat'] == 'Tech Company s.r.o.'
    assert validated['vstup']['povodny_text'] == 'сделай фактуру на техкомпании за ремонт 150 eur'


def test_validate_payload_keeps_service_term_and_repairs_missing_item_label() -> None:
    payload = _valid_payload('faktura pre Tech Company, random service 150 eur')
    payload['biznis_sk']['polozka_povodna'] = '   '
    payload['biznis_sk']['termin_sluzby_sk'] = 'random service'

    validated = validate_invoice_phase2_payload(payload)

    assert validated['biznis_sk']['termin_sluzby_sk'] == 'random service'
    assert validated['biznis_sk']['polozka_povodna'] == 'random service'


def test_validate_payload_accepts_optional_items_up_to_three() -> None:
    payload = _valid_payload('oprava 3000, montáž 2x1000')
    payload['biznis_sk']['items'] = [
        {
            'polozka_povodna': 'oprava',
            'termin_sluzby_sk': 'oprava',
            'mnozstvo': 1,
            'jednotka': 'ks',
            'cena_za_jednotku': 3000,
            'suma': 3000,
            'item_description_raw': None,
        },
        {
            'polozka_povodna': 'montáž',
            'termin_sluzby_sk': 'montáž',
            'mnozstvo': 2,
            'jednotka': 'ks',
            'cena_za_jednotku': 1000,
            'suma': 2000,
            'item_description_raw': None,
        },
    ]

    validated = validate_invoice_phase2_payload(payload)

    assert isinstance(validated['biznis_sk']['items'], list)
    assert len(validated['biznis_sk']['items']) == 2


def test_validate_payload_rejects_items_count_over_phase1_bound() -> None:
    payload = _valid_payload('multi')
    payload['biznis_sk']['items'] = [
        {'polozka_povodna': 'oprava', 'termin_sluzby_sk': 'oprava', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1, 'suma': 1},
        {'polozka_povodna': 'montáž', 'termin_sluzby_sk': 'montáž', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1, 'suma': 1},
        {'polozka_povodna': 'servis', 'termin_sluzby_sk': 'servis', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1, 'suma': 1},
        {'polozka_povodna': 'revizia', 'termin_sluzby_sk': 'revizia', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1, 'suma': 1},
    ]

    with pytest.raises(LlmInvoicePayloadError) as exc_info:
        validate_invoice_phase2_payload(payload)

    assert exc_info.value.error_code == 'items_count_exceeded'


def test_preview_flow_uses_python_truth_for_contact_and_display_name(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, contact_id = configured_db

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('сделай фактуру для Tech Company, ремонт 150 EUR')
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(int(supplier.id), 'montáž', 'Montáž zariadenia')

    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    draft = state.data['invoice_draft']
    assert draft['contact_id'] == contact_id
    assert draft['customer_name'] == 'Tech Company s.r.o.'
    assert draft['item_term_canonical_internal'] == 'oprava'
    assert draft['service_short_name'] == 'oprava'
    assert draft['service_display_name'] == 'Servis a oprava zariadenia'


def test_customer_resolution_uses_bounded_candidates_when_lookup_is_noisy(configured_db: tuple[Path, int, int], monkeypatch) -> None:
    db_path, telegram_id, contact_id = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('faktura pre tek kompaniu za opravu 150')
    payload['biznis_sk']['odberatel_kandidat'] = 'tek kompaniu'
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    async def _fake_resolver(**kwargs):
        assert kwargs['context_name'] == 'invoice_customer_term_resolution'
        assert 'Tech Company s.r.o.' in kwargs['allowed_actions']
        return 'Tech Company s.r.o.'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_resolver)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    draft = state.data['invoice_draft']
    assert draft['contact_id'] == contact_id
    assert draft['customer_name'] == 'Tech Company s.r.o.'


def test_service_resolution_uses_bounded_alias_selection_for_noisy_variant(configured_db: tuple[Path, int, int], monkeypatch) -> None:
    db_path, telegram_id, _ = configured_db
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(
        int(supplier.id),
        service_short_name='stavebné práce',
        service_display_name='Stavebné práce',
    )

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )

    async def _fake_resolver(**kwargs):
        assert kwargs['context_name'] == 'invoice_service_term_resolution'
        assert 'stavebné práce' in kwargs['allowed_actions']
        assert kwargs['user_input_text'] == 'stavbné práce'
        return 'stavebné práce'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_resolver)
    resolved_alias, resolved_display, allowed = asyncio.run(
        _resolve_service_alias_bounded(
            alias_service=ServiceAliasService(db_path),
            supplier_id=int(supplier.id),
            candidate_text='stavbné práce',
            config=config,
            context_name='invoice_service_term_resolution',
        )
    )

    assert 'stavebné práce' in allowed
    assert resolved_alias == 'stavebné práce'
    assert resolved_display == 'Stavebné práce'


def test_customer_clarification_reuses_bounded_candidates(tmp_path: Path, monkeypatch) -> None:
    db_path = tmp_path / 'phase2.db'
    init_db(db_path)
    telegram_id = 999
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=telegram_id,
            name='Dodavatel SK',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Bratislava 1',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='supplier@example.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    ContactService(db_path).create_or_replace(
        ContactProfile(
            supplier_telegram_id=telegram_id,
            name='Tech Company s.r.o.',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Kosice 2',
            email='contact@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    ContactService(db_path).create_or_replace(
        ContactProfile(
            supplier_telegram_id=telegram_id,
            name='Tesla Slovakia s.r.o.',
            ico='12341234',
            dic='1010101010',
            ic_dph=None,
            address='Bratislava 2',
            email='tesla@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )

    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()
    awaitable_data = {
        'invoice_partial_draft': {
            'request_id': 'req',
            'raw_text': 'faktura',
            'parsed_draft': {
                'customer_name': 'tech',
                'service_term_sk': 'oprava',
                'item_name_raw': 'oprava',
                'quantity': 1,
                'unit_price': 10,
                'amount': 10,
                'unit': 'ks',
                'currency': 'EUR',
            },
            'unresolved_slot': 'customer_name',
            'bounded_choices': ['Tech Company s.r.o.', 'Tesla Slovakia s.r.o.'],
        }
    }
    state.data.update(awaitable_data)

    captured_allowed: list[str] = []

    async def _fake_resolver(**kwargs):
        captured_allowed.extend(kwargs['allowed_actions'])
        return 'Tech Company s.r.o.'

    async def _fake_build_and_store_preview(**kwargs):
        state.data['resolved_customer'] = kwargs['parsed_draft']['customer_name']

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_resolver)
    monkeypatch.setattr('bot.handlers.invoice._build_and_store_preview', _fake_build_and_store_preview)

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            clarification_text='tek kompany',
        )
    )

    assert captured_allowed == ['Tech Company s.r.o.', 'Tesla Slovakia s.r.o.']
    assert state.data['resolved_customer'] == 'Tech Company s.r.o.'


def test_preview_returns_clean_retry_message_when_amount_missing(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('invoice for Tech Company without amount')
    payload['biznis_sk']['suma'] = None
    payload['biznis_sk']['cena_za_jednotku'] = None
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    assert state.cleared is False
    assert state.last_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'quantity_unit_price_pair'
    assert (
        message.answers[-1]
        == 'Uveďte množstvo a cenu za jednotku, napr. 3 po 1500 alebo 3 1500. '
        'Ak je množstvo 1, môžete zadať len cenu, napr. 1500.'
    )


def test_preview_missing_delivery_date_uses_issue_date_without_clarification(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('invoice for Tech Company')
    payload['biznis_sk']['datum_dodania'] = None
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    assert 'invoice_draft' in state.data
    draft = state.data['invoice_draft']
    assert draft['delivery_date'] == draft['issue_date']
    assert state.last_state == InvoiceStates.waiting_confirm


def test_preview_missing_due_days_uses_supplier_default_without_clarification(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('invoice for Tech Company')
    payload['biznis_sk']['splatnost_dni'] = None
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    assert 'invoice_draft' in state.data
    draft = state.data['invoice_draft']
    assert draft['due_days'] == 14
    assert state.last_state == InvoiceStates.waiting_confirm


def test_preview_invalid_due_days_keeps_clarification_path(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('invoice for Tech Company')
    payload['biznis_sk']['splatnost_dni'] = 'abc'
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    assert state.last_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'due_days'
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť splatnosť. Zadajte počet dní, prosím.'


def test_preview_inconsistent_delivery_date_keeps_clarification_path(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('dodanie 4 apríla pre Tech Company')
    payload['biznis_sk']['datum_dodania'] = '2026-05-04'
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=payload['vstup']['povodny_text'],
        parsed_draft=parsed,
    ))

    assert state.last_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'delivery_date'
    assert message.answers[-1] == 'Nepodarilo sa jednoznačne určiť dátum dodania. Spresnite ho, prosím.'


@pytest.mark.parametrize(
    'text,quantity,unit_price,total',
    [
        ('za opravu 2 razy po 1500', 2.0, 1500.0, 3000.0),
        ('za opravu 2 kusy po 1500 eur', 2.0, 1500.0, 3000.0),
        ('za opravu 2x 1500', 2.0, 1500.0, 3000.0),
        ('za opravu 2 krát po 1500 eur', 2.0, 1500.0, 3000.0),
        ('za opravu 2 раза по 1500', 2.0, 1500.0, 3000.0),
        ('za opravu 2 рази по 1500', 2.0, 1500.0, 3000.0),
        ('za opravu 2 крат по 1500', 2.0, 1500.0, 3000.0),
        ('za opravu 2 по 1500', 2.0, 1500.0, 3000.0),
        ('сделай fakturu за ремонт 2 рази по 1500 євро', 2.0, 1500.0, 3000.0),
    ],
)
def test_preview_amount_semantics_follow_n_times_unit_price_patterns(
    configured_db: tuple[Path, int, int], text: str, quantity: float, unit_price: float, total: float
) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload(text)
    payload['biznis_sk']['mnozstvo'] = 2
    payload['biznis_sk']['suma'] = 1500
    payload['biznis_sk']['cena_za_jednotku'] = None
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text=text,
        parsed_draft=parsed,
    ))

    draft = state.data['invoice_draft']
    assert draft['quantity'] == quantity
    assert draft['unit_price'] == unit_price
    assert draft['amount'] == total


def test_preview_amount_semantics_fail_loud_on_multiplier_hint_without_unit_price(
    configured_db: tuple[Path, int, int]
) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('za opravu 2 po sume 1500')
    payload['biznis_sk']['mnozstvo'] = 2
    payload['biznis_sk']['suma'] = 1500
    payload['biznis_sk']['cena_za_jednotku'] = None
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text='za opravu 2 po sume 1500',
        parsed_draft=parsed,
    ))

    assert state.cleared is False
    assert state.last_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'quantity_unit_price_pair'
    assert (
        message.answers[-1]
        == 'Uveďte množstvo a cenu za jednotku, napr. 3 po 1500 alebo 3 1500. '
        'Ak je množstvo 1, môžete zadať len cenu, napr. 1500.'
    )


def test_preview_amount_semantics_total_only_defaults_to_one_times_total(
    configured_db: tuple[Path, int, int]
) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('za opravu spolu 1500')
    payload['biznis_sk']['mnozstvo'] = None
    payload['biznis_sk']['suma'] = 1500
    payload['biznis_sk']['cena_za_jednotku'] = None
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text='za opravu spolu 1500',
        parsed_draft=parsed,
    ))

    draft = state.data['invoice_draft']
    assert draft['quantity'] == 1.0
    assert draft['unit_price'] == 1500.0
    assert draft['amount'] == 1500.0


def test_preview_message_hides_short_service_name_field() -> None:
    preview = _format_preview(
        'test input',
        {
            'customer_name': 'Tech Company s.r.o.',
            'service_short_name': 'oprava',
            'service_display_name': 'Servis a oprava zariadenia',
            'quantity': 2.0,
            'unit_price': 1500.0,
            'unit': 'ks',
            'amount': 3000.0,
            'currency': 'EUR',
            'issue_date': '2026-04-11',
            'delivery_date': '2026-04-03',
            'due_date': '2026-04-25',
        },
    )

    assert 'Krátky názov služby' not in preview
    assert 'Plný názov služby' in preview


def test_preview_multi_item_builds_total_and_item_list(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(int(supplier.id), 'montáž', 'Montáž zariadenia')

    payload = _valid_payload('oprava 3000, montáž 2x1000')
    payload['biznis_sk']['items'] = [
        {
            'polozka_povodna': 'oprava',
            'termin_sluzby_sk': 'oprava',
            'mnozstvo': 1,
            'jednotka': 'ks',
            'cena_za_jednotku': 3000,
            'suma': 3000,
            'item_description_raw': None,
        },
        {
            'polozka_povodna': 'montáž',
            'termin_sluzby_sk': 'montáž',
            'mnozstvo': 2,
            'jednotka': 'ks',
            'cena_za_jednotku': 1000,
            'suma': 2000,
            'item_description_raw': None,
        },
    ]
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text='oprava 3000, montáž 2x1000',
        parsed_draft=parsed,
    ))

    draft = state.data['invoice_draft']
    assert len(draft['items']) == 2
    assert draft['amount'] == 5000.0


def test_preview_multi_item_ambiguous_boundaries_requires_clarification(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('oprava montáž 3000 1000')
    payload['biznis_sk']['items'] = [
        {'polozka_povodna': 'oprava', 'termin_sluzby_sk': 'oprava', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 3000, 'suma': 3000},
        {'polozka_povodna': 'montáž', 'termin_sluzby_sk': 'montáž', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1000, 'suma': 1000},
    ]
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text='oprava montáž 3000 1000',
        parsed_draft=parsed,
    ))

    assert state.last_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'items'


def test_preview_multi_item_with_single_amount_token_requires_clarification(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()

    payload = _valid_payload('oprava a montáž zariadenia 3000')
    payload['biznis_sk']['items'] = [
        {'polozka_povodna': 'oprava', 'termin_sluzby_sk': 'oprava', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1500, 'suma': 1500},
        {'polozka_povodna': 'montáž', 'termin_sluzby_sk': 'montáž', 'mnozstvo': 1, 'jednotka': 'ks', 'cena_za_jednotku': 1500, 'suma': 1500},
    ]
    _, parsed = _extract_invoice_draft_from_phase2_payload(payload)

    asyncio.run(_build_and_store_preview(
        message=message,
        state=state,
        config=config,
        request_id='test-request-id',
        raw_text='oprava a montáž zariadenia 3000',
        parsed_draft=parsed,
    ))

    assert state.last_state == InvoiceStates.waiting_slot_clarification
    assert state.data['invoice_partial_draft']['unresolved_slot'] == 'items'


def test_items_slot_clarification_keeps_existing_customer_context(
    configured_db: tuple[Path, int, int],
    monkeypatch,
) -> None:
    db_path, telegram_id, _ = configured_db
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    message = _DummyMessage(telegram_id)
    state = _DummyState()
    state.data['invoice_partial_draft'] = {
        'request_id': 'req-items',
        'raw_text': 'vytvor fakturu pre Tech Company',
        'unresolved_slot': _SLOT_ITEMS,
        'parsed_draft': {
            'customer_name': 'TECH COMPANY, s.r.o.',
            'item_name_raw': 'oprava',
            'service_term_sk': 'oprava',
            'quantity': None,
            'unit': None,
            'amount': 2000,
            'unit_price': None,
            'items': [
                {
                    'item_name_raw': 'oprava',
                    'service_term_sk': 'oprava',
                    'quantity': None,
                    'unit': None,
                    'amount': 2000,
                    'unit_price': None,
                    'item_description_raw': None,
                },
                {
                    'item_name_raw': 'stavebne prace',
                    'service_term_sk': 'stavebné práce',
                    'quantity': None,
                    'unit': None,
                    'amount': 1000,
                    'unit_price': None,
                    'item_description_raw': None,
                },
            ],
            'currency': 'EUR',
            'delivery_date': '2026-04-14',
            'due_days': None,
            'due_date': None,
        },
    }

    async def _fake_parse_invoice_phase2_payload(text: str, api_key: str, model: str) -> dict:
        assert text == 'polozka 1 oprava 2000, polozka 2 stavebne prace 1000'
        return {
            'vstup': {'povodny_text': text, 'zisteny_jazyk': 'mixed'},
            'zamer': {'nazov': 'vytvor_fakturu', 'istota': 0.91},
            'biznis_sk': {
                'odberatel_kandidat': '   ',
                'polozka_povodna': 'oprava',
                'termin_sluzby_sk': 'oprava',
                'mnozstvo': None,
                'jednotka': None,
                'suma': 2000,
                'cena_za_jednotku': None,
                'mena': 'EUR',
                'datum_dodania': None,
                'splatnost_dni': None,
                'datum_splatnosti': None,
                'items': [
                    {
                        'polozka_povodna': 'oprava',
                        'termin_sluzby_sk': 'oprava',
                        'mnozstvo': 1,
                        'jednotka': 'ks',
                        'cena_za_jednotku': 2000,
                        'suma': 2000,
                        'item_description_raw': None,
                    },
                    {
                        'polozka_povodna': 'stavebne prace',
                        'termin_sluzby_sk': 'stavebné práce',
                        'mnozstvo': 1,
                        'jednotka': 'ks',
                        'cena_za_jednotku': 1000,
                        'suma': 1000,
                        'item_description_raw': None,
                    },
                ],
            },
            'stopa': {'chyba_udaje': [], 'nejasnosti': [], 'poznamky_normalizacie': []},
        }

    captured: dict[str, object] = {}

    async def _fake_build_and_store_preview(*, message, state, config, request_id, raw_text, parsed_draft):
        captured['request_id'] = request_id
        captured['raw_text'] = raw_text
        captured['parsed_draft'] = parsed_draft

    monkeypatch.setattr(
        'bot.handlers.invoice.parse_invoice_phase2_payload',
        _fake_parse_invoice_phase2_payload,
    )
    monkeypatch.setattr(
        'bot.handlers.invoice._build_and_store_preview',
        _fake_build_and_store_preview,
    )

    asyncio.run(
        process_invoice_slot_clarification(
            message=message,
            state=state,
            config=config,
            clarification_text='polozka 1 oprava 2000, polozka 2 stavebne prace 1000',
        )
    )

    merged = captured['parsed_draft']
    assert isinstance(merged, dict)
    assert merged['customer_name'] == 'TECH COMPANY, s.r.o.'
    assert len(merged['items']) == 2
    assert merged['items'][1]['service_term_sk'] == 'stavebné práce'


def test_delivery_date_year_anchor_for_ru_day_month_without_year() -> None:
    resolved = _resolve_delivery_date(
        raw_text='додания 4 апреля',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value='2023-04-04',
    )

    assert resolved.isoformat() == '2026-04-04'


def test_delivery_date_year_anchor_for_sk_day_month_without_year() -> None:
    resolved = _resolve_delivery_date(
        raw_text='datum dodania 4 apríla',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value='2025-04-04',
    )

    assert resolved.isoformat() == '2026-04-04'


def test_delivery_date_year_anchor_for_mixed_voice_like_input_without_year() -> None:
    resolved = _resolve_delivery_date(
        raw_text='ok sprav fakturu tech company, dodania 4 apríla po servise',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value=None,
    )

    assert resolved.isoformat() == '2026-04-04'


def test_delivery_date_explicit_year_is_respected() -> None:
    resolved = _resolve_delivery_date(
        raw_text='datum dodania 4 apríla 2025',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value='2025-04-04',
    )

    assert resolved.isoformat() == '2025-04-04'


def test_delivery_date_year_anchor_still_applies_when_unrelated_year_exists_elsewhere() -> None:
    resolved = _resolve_delivery_date(
        raw_text='faktura za rok 2023, ale dodania 4 apríla',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value='2023-04-04',
    )

    assert resolved.isoformat() == '2026-04-04'


def test_delivery_date_year_anchor_supports_ukrainian_month_form() -> None:
    resolved = _resolve_delivery_date(
        raw_text='додання 4 квітня',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value='2023-04-04',
    )

    assert resolved.isoformat() == '2026-04-04'


def test_delivery_date_explicit_local_year_disables_anchoring() -> None:
    resolved = _resolve_delivery_date(
        raw_text='додання 4 квітня 2025',
        issue_date_obj=date(2026, 4, 11),
        llm_delivery_value='2025-04-04',
    )

    assert resolved.isoformat() == '2025-04-04'


def test_resolve_service_alias_bounded_prefers_deterministic_direct_match(configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _contact_id = configured_db
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None

    config = Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )
    alias_service = ServiceAliasService(db_path)

    alias, display, allowed = asyncio.run(_resolve_service_alias_bounded(
        alias_service=alias_service,
        supplier_id=int(supplier.id),
        candidate_text='  OPRAVA ',
        config=config,
        context_name='invoice_service_term_resolution',
    ))

    assert alias == 'oprava'
    assert display == 'Servis a oprava zariadenia'
    assert 'oprava' in allowed


def test_resolve_service_alias_bounded_uses_bounded_llm_result(monkeypatch: pytest.MonkeyPatch, configured_db: tuple[Path, int, int]) -> None:
    db_path, telegram_id, _contact_id = configured_db
    supplier = SupplierService(db_path).get_by_telegram_id(telegram_id)
    assert supplier is not None and supplier.id is not None
    ServiceAliasService(db_path).create_mapping(int(supplier.id), 'montaz', 'Montáž zariadenia')

    async def _fake_resolve_semantic_action(**kwargs):
        assert kwargs['context_name'] == 'invoice_service_term_resolution'
        assert 'oprava' in kwargs['allowed_actions']
        assert 'montaz' in kwargs['allowed_actions']
        return 'montaz'

    monkeypatch.setattr('bot.handlers.invoice.resolve_semantic_action', _fake_resolve_semantic_action)

    config = Config(
        bot_token='token',
        openai_api_key='sk-test',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=db_path.parent,
    )

    alias, display, allowed = asyncio.run(_resolve_service_alias_bounded(
        alias_service=ServiceAliasService(db_path),
        supplier_id=int(supplier.id),
        candidate_text='montáž',
        config=config,
        context_name='invoice_service_term_resolution',
    ))

    assert alias == 'montaz'
    assert display == 'Montáž zariadenia'
    assert set(allowed) >= {'oprava', 'montaz'}
