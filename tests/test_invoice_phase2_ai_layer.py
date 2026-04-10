from __future__ import annotations

from pathlib import Path

import asyncio

import pytest

from bot.config import Config
from bot.handlers.invoice import _build_and_store_preview, _extract_invoice_draft_from_phase2_payload
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
        service_short_name='ремонт',
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
            'polozka_povodna': 'ремонт',
            'termin_sluzby_sk': 'oprava',
            'mnozstvo': 1,
            'jednotka': 'ks',
            'suma': 150,
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
    assert parsed['item_name_raw'] == 'ремонт'
    assert parsed['service_term_sk'] == 'oprava'
    assert parsed['amount'] == 150


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
