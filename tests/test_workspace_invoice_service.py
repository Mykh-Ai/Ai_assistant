from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice import _finalize_invoice_draft
from bot.services.access_control import AccessControlService
from bot.services.contact_service import ContactProfile
from bot.services.db import init_db
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import WorkspaceContextService
from bot.services.workspace_invoice_service import WorkspaceInvoiceService
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_ID = 90901


def _supplier(name: str) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=USER_ID, name=name, ico='12345678', dic='1234567890',
        ic_dph=None, address='Address', iban='SK3112000000198742637541',
        swift='GIBASKBX', email='owner@example.test', smtp_host=None,
        smtp_user=None, smtp_pass=None, days_due=14,
    )


def _contact(workspace_id: str) -> ContactProfile:
    return ContactProfile(
        workspace_id=workspace_id, supplier_telegram_id=USER_ID,
        name='Shared Customer', ico='87654321', dic='0987654321',
        ic_dph=None, address='Customer', email='customer@example.test',
        contact_person=None, source_type='manual', source_note=None,
        contract_path=None,
    )


def _item() -> CreateInvoiceItemPayload:
    return CreateInvoiceItemPayload(
        description_raw='Service', description_normalized='Service',
        item_description_raw=None, quantity=1, unit='ks',
        unit_price=100, total_price=100,
    )


def _setup(db_path: Path):
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID, approved_by=999, role='owner'
    )
    profiles = WorkspaceProfileService(db_path)
    first = profiles.create_profile(
        actor_telegram_id=USER_ID, profile=_supplier('First'),
        mode=CREATE_FIRST_WORKSPACE_PROFILE, make_active=True,
        workspace_id='ws_first', storage_key='first',
    )
    second = profiles.create_profile(
        actor_telegram_id=USER_ID, profile=_supplier('Second'),
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE, make_active=False,
        workspace_id='ws_second', storage_key='second',
    )
    contacts = WorkspaceContactService(db_path)
    first_contact = contacts.create_or_replace(first, _contact(first.workspace_id))
    second_contact = contacts.create_or_replace(second, _contact(second.workspace_id))
    return first, second, first_contact, second_contact


def _create(service, context, contact_id, number):
    return service.create_invoice_with_items(
        context, contact_id=contact_id, issue_date='2026-07-01',
        delivery_date='2026-07-01', due_date='2026-07-15', due_days=14,
        total_amount=100, currency='EUR', status='created',
        items=[_item()], invoice_number=number,
    )


def test_same_invoice_number_is_isolated_between_workspaces(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_contact, second_contact = _setup(db_path)
    service = WorkspaceInvoiceService(db_path)

    first_invoice = _create(service, first, first_contact.id, '20260001')
    second_invoice = _create(service, second, second_contact.id, '20260001')

    assert first_invoice.id != second_invoice.id
    assert service.get_by_number(first, '20260001').id == first_invoice.id
    assert service.get_by_number(second, '20260001').id == second_invoice.id
    assert service.get_by_id(first, second_invoice.id) is None
    assert service.get_by_id(second, first_invoice.id) is None


def test_numbering_settings_and_sequence_are_workspace_scoped(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_contact, _second_contact = _setup(db_path)
    service = WorkspaceInvoiceService(db_path)
    service.set_first_invoice_number(
        first, issue_year=2026, first_invoice_number='20260025'
    )

    assert service.generate_next_invoice_number(first, 2026) == '20260025'
    assert service.generate_next_invoice_number(second, 2026) == '20260001'
    _create(service, first, first_contact.id, '20260025')
    assert service.generate_next_invoice_number(first, 2026) == '20260026'
    assert service.generate_next_invoice_number(second, 2026) == '20260001'


def test_foreign_workspace_contact_is_rejected_without_invoice(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, _first_contact, second_contact = _setup(db_path)
    service = WorkspaceInvoiceService(db_path)

    with pytest.raises(ValueError, match='invoice_contact_workspace_mismatch'):
        _create(service, first, second_contact.id, '20260001')

    assert service.get_by_number(first, '20260001') is None


def test_duplicate_number_in_same_workspace_fails(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, first_contact, _second_contact = _setup(db_path)
    service = WorkspaceInvoiceService(db_path)
    _create(service, first, first_contact.id, '20260001')

    with pytest.raises(RuntimeError, match='already exists for this workspace'):
        _create(service, first, first_contact.id, '20260001')


def test_legacy_invoice_number_settings_still_work_for_single_profile(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    legacy = InvoiceService(db_path)
    legacy.set_first_invoice_number(
        supplier_telegram_id=123,
        issue_year=2026,
        first_invoice_number='20260010',
    )
    assert legacy.get_first_invoice_number(
        supplier_telegram_id=123,
        issue_year=2026,
    ) == '20260010'

def test_workspace_edit_and_delete_reject_foreign_invoice(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_contact, _second_contact = _setup(db_path)
    service = WorkspaceInvoiceService(db_path)
    invoice = _create(service, first, first_contact.id, '20260001')
    item = service.get_items(first, invoice.id)[0]

    with pytest.raises(ValueError, match='invoice_not_found_for_workspace'):
        service.update_invoice_due_date(
            second,
            invoice_id=invoice.id,
            due_date='2026-07-20',
        )
    with pytest.raises(ValueError, match='invoice_item_not_found_for_workspace'):
        service.update_item_description(
            second,
            item_id=item.id,
            item_description_raw='foreign',
        )
    with pytest.raises(ValueError, match='invoice_not_found_for_workspace'):
        service.delete_invoice_with_items(second, invoice_id=invoice.id)

    assert service.get_by_id(first, invoice.id) is not None
    assert service.get_items(first, invoice.id)[0].item_description_raw is None


class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self) -> None:
        self.from_user = _DummyUser(USER_ID)
        self.answers: list[str] = []
        self.documents: list[Path] = []

    async def answer(self, text: str, **_kwargs) -> None:
        self.answers.append(text)

    async def answer_document(self, document, **_kwargs) -> None:
        self.documents.append(Path(document.path))


class _DummyState:
    def __init__(self, data: dict) -> None:
        self.data = dict(data)
        self.state = None

    async def get_data(self):
        return dict(self.data)

    async def update_data(self, **kwargs) -> None:
        self.data.update(kwargs)

    async def set_state(self, value) -> None:
        self.state = value

    async def get_state(self):
        return self.state

    async def clear(self) -> None:
        self.data = {}
        self.state = None


def test_invoice_finalize_keeps_starting_workspace_after_active_switch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_contact, _second_contact = _setup(db_path)
    WorkspaceContextService(db_path).set_active_workspace(USER_ID, second.workspace_id)
    config = Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=tmp_path / 'storage',
        allowed_telegram_user_ids=frozenset({USER_ID}),
        admin_telegram_user_ids=frozenset(),
    )
    message = _DummyMessage()
    state = _DummyState({'invoice_workspace_id': first.workspace_id})

    def _fake_pdf(*, target_path: Path, **_kwargs) -> None:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b'%PDF-1.4 workspace')

    monkeypatch.setattr('bot.handlers.invoice.generate_invoice_pdf', _fake_pdf)
    draft = {
        'customer_name': first_contact.name,
        'contact_id': first_contact.id,
        'service_short_name': 'Service',
        'service_display_name': 'Service',
        'quantity': 1,
        'unit_price': 100,
        'unit': 'ks',
        'amount': 100,
        'currency': 'EUR',
        'issue_date': '2026-07-01',
        'delivery_date': '2026-07-01',
        'due_days': 14,
        'due_date': '2026-07-15',
    }

    asyncio.run(
        _finalize_invoice_draft(
            message=message,
            state=state,
            config=config,
            draft=draft,
        )
    )

    service = WorkspaceInvoiceService(db_path)
    saved = service.get_by_number(first, '20260001')
    assert saved is not None
    assert service.get_by_number(second, '20260001') is None
    assert saved.pdf_path == str(
        config.storage_dir / 'invoices' / first.storage_key / '20260001.pdf'
    )
    assert message.documents == [Path(saved.pdf_path)]