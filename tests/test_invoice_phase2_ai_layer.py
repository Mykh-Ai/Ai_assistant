from __future__ import annotations

from datetime import date
from pathlib import Path

import asyncio

import pytest

from bot.config import Config
from bot.handlers.invoice import (
    _build_and_store_preview,
    _extract_invoice_draft_from_phase2_payload,
    _format_preview,
    _resolve_delivery_date,
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
            'datum_dodania': None,
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
        'техкомпании',
        '   ',
        'на техкомпании',
        'для компании',
        'pre firmu',
        'kompanii',
    ],
)
def test_validate_payload_rejects_non_lookup_ready_customer_candidate(bad_candidate: str) -> None:
    payload = _valid_payload('сделай фактуру на техкомпании за ремонт 150 eur')
    payload['biznis_sk']['odberatel_kandidat'] = bad_candidate

    with pytest.raises(LlmInvoicePayloadError):
        validate_invoice_phase2_payload(payload)


def test_validate_payload_accepts_lookup_ready_latin_customer_candidate() -> None:
    payload = _valid_payload('сделай фактуру на техкомпании за ремонт 150 eur')
    payload['biznis_sk']['odberatel_kandidat'] = 'Tech Company s.r.o.'

    validated = validate_invoice_phase2_payload(payload)

    assert validated['biznis_sk']['odberatel_kandidat'] == 'Tech Company s.r.o.'
    assert validated['vstup']['povodny_text'] == 'сделай фактуру на техкомпании за ремонт 150 eur'


@pytest.mark.parametrize('bad_text', ['ремонт', 'монтаж'])
def test_validate_payload_rejects_cyrillic_in_biznis_sk_fields(bad_text: str) -> None:
    payload = _valid_payload('сделай фактуру на техкомпании за ремонт 150 eur')
    payload['biznis_sk']['polozka_povodna'] = bad_text

    with pytest.raises(LlmInvoicePayloadError):
        validate_invoice_phase2_payload(payload)


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

    assert state.cleared is True
    assert any('AI návrh je neúplný' in text for text in message.answers)


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

    assert state.cleared is True
    assert any('Nejednoznačná suma' in text for text in message.answers)


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
