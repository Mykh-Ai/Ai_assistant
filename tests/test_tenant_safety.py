from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice import _invoice_pdf_path
from bot.services.authorization import TelegramUserAuthorizationMiddleware, UNAUTHORIZED_MESSAGE
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService


USER_A = 111001
USER_B = 222002
USER_BLOCKED = 333003


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self, user_id: int | None) -> None:
        self.from_user = _DummyUser(user_id) if user_id is not None else None
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def _config(tmp_path: Path, *, allowed: frozenset[int] = frozenset({USER_A, USER_B})) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'tenant.db',
        storage_dir=tmp_path,
        allowed_telegram_user_ids=allowed,
    )


def _supplier(user_id: int, suffix: str) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=user_id,
        name=f'Supplier {suffix}',
        ico=f'12345{suffix[-3:]}',
        dic=f'1234567{suffix[-3:]}',
        ic_dph=None,
        address=f'Address {suffix}',
        iban='SK3112000000198742637541',
        swift='TATRSKBX',
        email=f'supplier-{suffix}@example.com',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
    )


def _contact(user_id: int, name: str) -> ContactProfile:
    return ContactProfile(
        supplier_telegram_id=user_id,
        name=name,
        ico='87654321',
        dic='1234567890',
        ic_dph=None,
        address='Customer address',
        email='customer@example.com',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=None,
    )


def _item() -> CreateInvoiceItemPayload:
    return CreateInvoiceItemPayload(
        description_raw='service',
        description_normalized='Service',
        item_description_raw=None,
        quantity=1,
        unit='ks',
        unit_price=100,
        total_price=100,
    )


def _create_invoice(
    service: InvoiceService,
    *,
    supplier_telegram_id: int,
    contact_id: int,
    invoice_number: str | None = None,
) -> int:
    return service.create_invoice_with_items(
        supplier_telegram_id=supplier_telegram_id,
        contact_id=contact_id,
        issue_date='2026-05-02',
        delivery_date='2026-05-02',
        due_date='2026-05-16',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='draft',
        items=[_item()],
        invoice_number=invoice_number,
    )


def test_unauthorized_user_is_blocked_before_any_user_flow_or_llm_work(tmp_path: Path) -> None:
    config = _config(tmp_path)
    state = _DummyState()
    message = _DummyMessage(USER_BLOCKED)
    calls: list[str] = []

    async def _handler(event, data):
        calls.append('handler-called')
        return 'called'

    middleware = TelegramUserAuthorizationMiddleware()
    result = asyncio.run(middleware(_handler, message, {'config': config, 'state': state}))

    assert result is None
    assert calls == []
    assert state.cleared is True
    assert message.answers == [UNAUTHORIZED_MESSAGE]


def test_empty_allowlist_preserves_local_test_behavior(tmp_path: Path) -> None:
    config = _config(tmp_path, allowed=frozenset())
    message = _DummyMessage(USER_BLOCKED)
    calls: list[int] = []

    async def _handler(event, data):
        calls.append(event.from_user.id)
        return 'ok'

    result = asyncio.run(TelegramUserAuthorizationMiddleware()(_handler, message, {'config': config}))

    assert result == 'ok'
    assert calls == [USER_BLOCKED]
    assert message.answers == []


def test_authorized_users_have_independent_suppliers_contacts_and_invoice_numbers(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    supplier_service = SupplierService(config.db_path)
    contact_service = ContactService(config.db_path)
    invoice_service = InvoiceService(config.db_path)

    supplier_service.create_or_replace(_supplier(USER_A, '001'))
    supplier_service.create_or_replace(_supplier(USER_B, '002'))
    contact_service.create_or_replace(_contact(USER_A, 'Shared Customer'))
    contact_service.create_or_replace(_contact(USER_B, 'Shared Customer'))
    contact_a = contact_service.get_by_name(USER_A, 'Shared Customer')
    contact_b = contact_service.get_by_name(USER_B, 'Shared Customer')
    assert contact_a is not None
    assert contact_b is not None

    invoice_a = _create_invoice(
        invoice_service,
        supplier_telegram_id=USER_A,
        contact_id=int(contact_a.id),
        invoice_number='20260001',
    )
    invoice_b = _create_invoice(
        invoice_service,
        supplier_telegram_id=USER_B,
        contact_id=int(contact_b.id),
        invoice_number='20260001',
    )

    assert invoice_a != invoice_b
    assert invoice_service.generate_next_invoice_number(2026, supplier_telegram_id=USER_A) == '20260002'
    assert invoice_service.generate_next_invoice_number(2026, supplier_telegram_id=USER_B) == '20260002'
    assert contact_service.get_by_name(USER_A, 'Shared Customer').supplier_telegram_id == USER_A
    assert contact_service.get_by_name(USER_B, 'Shared Customer').supplier_telegram_id == USER_B
    assert [contact.name for contact in contact_service.get_all_by_supplier(USER_A)] == ['Shared Customer']
    assert [contact.name for contact in contact_service.get_all_by_supplier(USER_B)] == ['Shared Customer']


def test_invoice_full_number_and_last_digits_resolution_are_supplier_scoped(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    contact_service = ContactService(config.db_path)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A, '001'))
    SupplierService(config.db_path).create_or_replace(_supplier(USER_B, '002'))
    contact_service.create_or_replace(_contact(USER_A, 'Customer A'))
    contact_service.create_or_replace(_contact(USER_B, 'Customer B'))
    contact_a = contact_service.get_by_name(USER_A, 'Customer A')
    contact_b = contact_service.get_by_name(USER_B, 'Customer B')
    assert contact_a is not None
    assert contact_b is not None
    invoice_service = InvoiceService(config.db_path)

    _create_invoice(invoice_service, supplier_telegram_id=USER_A, contact_id=int(contact_a.id), invoice_number='20260001')
    _create_invoice(invoice_service, supplier_telegram_id=USER_B, contact_id=int(contact_b.id), invoice_number='20269999')

    assert invoice_service.get_invoice_by_number_for_supplier(
        supplier_telegram_id=USER_A,
        invoice_number='20269999',
    ) is None
    assert invoice_service.find_invoices_for_supplier_by_number_reference(
        supplier_telegram_id=USER_A,
        invoice_reference='20269999',
    ) == []
    assert invoice_service.find_invoices_for_supplier_by_number_reference(
        supplier_telegram_id=USER_A,
        invoice_reference='9999',
    ) == []
    assert len(
        invoice_service.find_invoices_for_supplier_by_number_reference(
            supplier_telegram_id=USER_B,
            invoice_reference='9999',
        )
    ) == 1


def test_invoice_number_availability_and_unique_constraint_are_tenant_aware(tmp_path: Path) -> None:
    config = _config(tmp_path)
    init_db(config.db_path)
    contact_service = ContactService(config.db_path)
    SupplierService(config.db_path).create_or_replace(_supplier(USER_A, '001'))
    SupplierService(config.db_path).create_or_replace(_supplier(USER_B, '002'))
    contact_service.create_or_replace(_contact(USER_A, 'Customer A'))
    contact_service.create_or_replace(_contact(USER_B, 'Customer B'))
    contact_a = contact_service.get_by_name(USER_A, 'Customer A')
    contact_b = contact_service.get_by_name(USER_B, 'Customer B')
    assert contact_a is not None
    assert contact_b is not None
    invoice_service = InvoiceService(config.db_path)

    _create_invoice(invoice_service, supplier_telegram_id=USER_A, contact_id=int(contact_a.id), invoice_number='20260001')

    assert invoice_service.is_invoice_number_available(
        invoice_number='20260001',
        supplier_telegram_id=USER_A,
    ) is False
    assert invoice_service.is_invoice_number_available(
        invoice_number='20260001',
        supplier_telegram_id=USER_B,
    ) is True

    _create_invoice(invoice_service, supplier_telegram_id=USER_B, contact_id=int(contact_b.id), invoice_number='20260001')
    with pytest.raises(RuntimeError, match='already exists for this supplier'):
        _create_invoice(invoice_service, supplier_telegram_id=USER_A, contact_id=int(contact_a.id), invoice_number='20260001')


def test_invoice_pdf_paths_are_tenant_scoped(tmp_path: Path) -> None:
    path_a = _invoice_pdf_path(tmp_path, USER_A, '20260001')
    path_b = _invoice_pdf_path(tmp_path, USER_B, '20260001')

    assert path_a == tmp_path / 'invoices' / str(USER_A) / '20260001.pdf'
    assert path_b == tmp_path / 'invoices' / str(USER_B) / '20260001.pdf'
    assert path_a != path_b
