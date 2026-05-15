from __future__ import annotations

import asyncio
from pathlib import Path

from bot.config import Config
from bot.handlers.onboarding import (
    ONBOARDING_RECOVERY_HINT,
    SUPPLIER_ONBOARDING_SAVED_NEXT_STEP_MESSAGE,
    SupplierProfileEditStates,
    OnboardingStates,
    cmd_upravit_profil,
    onboarding_address,
    onboarding_confirm,
    onboarding_days_due,
    onboarding_dic,
    onboarding_email,
    onboarding_first_invoice_number,
    onboarding_iban,
    onboarding_ic_dph,
    onboarding_ico,
    onboarding_name,
    onboarding_swift,
    supplier_profile_edit_confirm,
    supplier_profile_edit_field,
    supplier_profile_edit_value,
)
from bot.handlers.start import ADVANCED_START_MESSAGE
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db
from bot.services.invoice_service import InvoiceService
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierProfile, SupplierService


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, text: str, user_id: int = 111) -> None:
        self.text = text
        self.from_user = _DummyUser(user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.current_state = OnboardingStates.confirm
        self.data = {
            'name': 'Dodavatel',
            'ico': '12345678',
            'dic': '1234567890',
            'ic_dph': '',
            'address': 'Bratislava',
            'iban': 'SK3112000000198742637541',
            'swift': 'TATRSKBX',
            'email': 'supplier@example.com',
            'smtp_host': None,
            'smtp_user': None,
            'smtp_pass': None,
            'invoice_number_issue_year': 2026,
            'first_invoice_number': '20260025',
            'days_due': '14',
        }

    async def get_data(self) -> dict:
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, state) -> None:
        self.current_state = state

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
        db_path=tmp_path / 'onboarding.db',
        storage_dir=tmp_path,
    )


def _create_supplier(config: Config, telegram_id: int = 111) -> SupplierProfile:
    service = SupplierService(config.db_path)
    service.create_or_replace(
        SupplierProfile(
            telegram_id=telegram_id,
            name='Dodavatel',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Stara adresa 1',
            iban='SK3112000000198742637541',
            swift='TATRSKBX',
            email='supplier@example.com',
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    supplier = service.get_by_telegram_id(telegram_id)
    assert supplier is not None
    return supplier


def test_onboarding_confirm_accepts_shared_yes_alias(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('ok')
    state = _DummyState()

    asyncio.run(onboarding_confirm(message, state, config))

    saved = SupplierService(config.db_path).get_by_telegram_id(111)
    assert saved is not None
    assert saved.name == 'Dodavatel'
    assert saved.smtp_host is None
    assert saved.smtp_user is None
    assert saved.smtp_pass is None
    assert InvoiceService(config.db_path).get_first_invoice_number(
        supplier_telegram_id=111,
        issue_year=2026,
    ) == '20260025'
    assert state.current_state is None
    assert message.answers[-1] == SUPPLIER_ONBOARDING_SAVED_NEXT_STEP_MESSAGE
    assert '/sluzbu' in message.answers[-1]
    assert '/contact' not in message.answers[-1]
    assert '/invoice' not in message.answers[-1]


def test_onboarding_confirm_accepts_shared_no_alias(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    message = _DummyMessage('no')
    state = _DummyState()

    asyncio.run(onboarding_confirm(message, state, config))

    assert SupplierService(config.db_path).get_by_telegram_id(111) is None
    assert state.current_state is None
    assert '/moj_profil' in message.answers[-1]


def test_onboarding_invalid_values_keep_state_and_include_recovery_hint() -> None:
    cases = [
        (onboarding_name, '', OnboardingStates.name),
        (onboarding_ico, '123', OnboardingStates.ico),
        (onboarding_dic, '123', OnboardingStates.dic),
        (onboarding_ic_dph, 'SK123', OnboardingStates.ic_dph),
        (onboarding_address, '', OnboardingStates.address),
        (onboarding_iban, 'SK_BAD', OnboardingStates.iban),
        (onboarding_swift, '', OnboardingStates.swift),
        (onboarding_email, 'not-email', OnboardingStates.email),
        (onboarding_first_invoice_number, '42', OnboardingStates.first_invoice_number),
        (onboarding_days_due, '0', OnboardingStates.days_due),
    ]

    for handler, invalid_value, expected_state in cases:
        state = _DummyState()
        state.current_state = expected_state
        message = _DummyMessage(invalid_value)

        asyncio.run(handler(message, state))

        assert state.current_state == expected_state
        assert ONBOARDING_RECOVERY_HINT in message.answers[-1]


def test_upravit_profil_updates_one_field_with_shared_confirmation(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    _create_supplier(config)
    state = _DummyState()

    asyncio.run(cmd_upravit_profil(_DummyMessage('/upravit_profil'), state, config))
    assert state.current_state == SupplierProfileEditStates.field

    asyncio.run(supplier_profile_edit_field(_DummyMessage('adresa'), state, config))
    assert state.current_state == SupplierProfileEditStates.value

    asyncio.run(supplier_profile_edit_value(_DummyMessage('Nova adresa 22'), state))
    assert state.current_state == SupplierProfileEditStates.confirm

    confirm_message = _DummyMessage('ano')
    asyncio.run(supplier_profile_edit_confirm(confirm_message, state, config))

    saved = SupplierService(config.db_path).get_by_telegram_id(111)
    assert saved is not None
    assert saved.address == 'Nova adresa 22'
    assert saved.ico == '12345678'
    assert state.current_state is None
    assert '/sluzbu' in confirm_message.answers[-1]


def test_upravit_profil_returns_advanced_menu_for_ready_user(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    supplier = _create_supplier(config)
    assert supplier.id is not None
    ServiceAliasService(config.db_path).create_mapping(supplier.id, 'opravy', 'Opravy')
    ContactService(config.db_path).create_or_replace(
        ContactProfile(
            supplier_telegram_id=111,
            name='Odberatel',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Kosice 1',
            email='odberatel@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    state = _DummyState()
    state.current_state = SupplierProfileEditStates.confirm
    state.data = {'supplier_edit_field': 'address', 'supplier_edit_value': 'Nova adresa 22'}

    confirm_message = _DummyMessage('ano')
    asyncio.run(supplier_profile_edit_confirm(confirm_message, state, config))

    assert state.current_state is None
    assert ADVANCED_START_MESSAGE in confirm_message.answers[-1]
    assert '/invoice' in confirm_message.answers[-1]
    assert 'zobraz faktúru 04' in confirm_message.answers[-1]
    assert '/sluzbu' not in confirm_message.answers[-1]


def test_supplier_profile_edit_field_accepts_voice_like_phrase_fast_path(tmp_path: Path) -> None:
    config = _config(tmp_path)
    state = _DummyState()

    asyncio.run(supplier_profile_edit_field(_DummyMessage('chcem zmeniť IBAN'), state, config))

    assert state.current_state == SupplierProfileEditStates.value
    assert state.data['supplier_edit_field'] == 'iban'


def test_supplier_profile_edit_field_uses_bounded_resolver_fallback(tmp_path: Path, monkeypatch) -> None:
    config = _config(tmp_path)
    state = _DummyState()
    captured: dict[str, object] = {}

    async def _resolve(**kwargs) -> str:
        captured.update(kwargs)
        return 'email'

    monkeypatch.setattr('bot.handlers.onboarding.resolve_semantic_action', _resolve)

    asyncio.run(supplier_profile_edit_field(_DummyMessage('kontaktné údaje'), state, config))

    assert state.current_state == SupplierProfileEditStates.value
    assert state.data['supplier_edit_field'] == 'email'
    assert captured['context_name'] == 'supplier_profile_edit_field'
    assert 'email' in captured['allowed_actions']
    assert 'unknown' in captured['allowed_actions']
