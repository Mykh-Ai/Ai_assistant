from __future__ import annotations

from datetime import datetime
import inspect
from pathlib import Path

from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db, managed_connection
from bot.services.google_drive_archive_stub import GoogleDriveArchiveStubService
from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
    PAYMENT_STATUS_PAID,
    REMINDER_STATUS_ACTIVE,
    REMINDER_STATUS_MUTED,
    REMINDER_STATUS_SNOOZED,
    InvoiceFollowupService,
)
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService


USER_A = 111001
USER_B = 222002


def _setup_account(db_path: Path, telegram_id: int) -> int:
    SupplierService(db_path).create_or_replace(
        SupplierProfile(
            telegram_id=telegram_id,
            name=f'Dodavatel {telegram_id}',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Hlavna 1, Bratislava',
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
            name=f'Odberatel {telegram_id}',
            ico='87654321',
            dic='0987654321',
            ic_dph=None,
            address='Dlha 2, Kosice',
            email='customer@example.com',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(db_path).get_by_name(telegram_id, f'Odberatel {telegram_id}')
    assert contact is not None and contact.id is not None
    return contact.id


def _create_invoice(
    db_path: Path,
    *,
    supplier_telegram_id: int,
    contact_id: int,
    invoice_number: str,
    due_date: str,
) -> int:
    return InvoiceService(db_path).create_invoice_with_items(
        supplier_telegram_id=supplier_telegram_id,
        contact_id=contact_id,
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date=due_date,
        due_days=14,
        total_amount=120.0,
        currency='EUR',
        status='pripravena',
        invoice_number=invoice_number,
        items=[
            CreateInvoiceItemPayload(
                description_raw='servis',
                description_normalized='Servis',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=120.0,
                total_price=120.0,
            )
        ],
    )


def _service_with_invoice(tmp_path: Path, *, due_date: str = '2026-06-10') -> tuple[Path, InvoiceFollowupService, int]:
    db_path = tmp_path / 'followup.db'
    init_db(db_path)
    contact_id = _setup_account(db_path, USER_A)
    invoice_id = _create_invoice(
        db_path,
        supplier_telegram_id=USER_A,
        contact_id=contact_id,
        invoice_number='20260001',
        due_date=due_date,
    )
    return db_path, InvoiceFollowupService(db_path), invoice_id


def test_invoice_with_due_date_in_past_is_selected_for_reminder(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path, due_date='2026-06-10')

    reminders = service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-15',
        now='2026-06-15T10:00:00',
    )

    assert [item.invoice_id for item in reminders] == [invoice_id]
    assert reminders[0].payment_status == 'unpaid'
    assert reminders[0].reminder_status == 'active'


def test_invoice_due_today_or_future_is_not_selected(tmp_path: Path) -> None:
    _db_path, service, _invoice_id = _service_with_invoice(tmp_path, due_date='2026-06-15')

    assert service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-15',
        now='2026-06-15T10:00:00',
    ) == []


def test_paid_invoice_is_not_selected(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)
    service.mark_paid(invoice_id=invoice_id, supplier_telegram_id=USER_A, now='2026-06-15T10:00:00')

    assert service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-16',
        now='2026-06-16T10:00:00',
    ) == []


def test_muted_invoice_is_not_selected(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)
    service.mute(invoice_id=invoice_id, supplier_telegram_id=USER_A, now='2026-06-15T10:00:00')

    assert service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-16',
        now='2026-06-16T10:00:00',
    ) == []


def test_snoozed_invoice_before_remind_after_is_not_selected(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)
    service.remind_later(
        invoice_id=invoice_id,
        supplier_telegram_id=USER_A,
        now='2026-06-15T10:00:00',
        remind_after='2026-06-16T10:00:00',
    )

    assert service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-16',
        now='2026-06-16T09:59:00',
    ) == []


def test_snoozed_invoice_after_remind_after_is_selected(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)
    service.remind_later(
        invoice_id=invoice_id,
        supplier_telegram_id=USER_A,
        now='2026-06-15T10:00:00',
        remind_after='2026-06-16T10:00:00',
    )

    reminders = service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-16',
        now='2026-06-16T10:01:00',
    )

    assert [item.invoice_id for item in reminders] == [invoice_id]


def test_mark_as_paid_decision_persists_payment_status_and_paid_at(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)

    state = service.mark_paid(invoice_id=invoice_id, supplier_telegram_id=USER_A, now='2026-06-15T10:00:00')

    assert state.payment_status == PAYMENT_STATUS_PAID
    assert state.reminder_status == REMINDER_STATUS_MUTED
    assert state.paid_at == '2026-06-15T10:00:00'


def test_remind_later_persists_reminder_status_and_remind_after(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)

    state = service.remind_later(
        invoice_id=invoice_id,
        supplier_telegram_id=USER_A,
        now=datetime(2026, 6, 15, 10, 0, 0),
    )

    assert state.payment_status == 'unpaid'
    assert state.reminder_status == REMINDER_STATUS_SNOOZED
    assert state.remind_after == '2026-06-16T10:00:00'


def test_do_not_remind_persists_muted_state(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path)

    state = service.mute(invoice_id=invoice_id, supplier_telegram_id=USER_A, now='2026-06-15T10:00:00')

    assert state.payment_status == 'unpaid'
    assert state.reminder_status == REMINDER_STATUS_MUTED
    assert state.muted_at == '2026-06-15T10:00:00'


def test_google_drive_stub_never_calls_external_apis_and_never_claims_upload_success(tmp_path: Path) -> None:
    db_path, service, invoice_id = _service_with_invoice(tmp_path)
    service.mark_paid(invoice_id=invoice_id, supplier_telegram_id=USER_A, now='2026-06-15T10:00:00')

    result = GoogleDriveArchiveStubService(db_path).request_invoice_archive_stub(
        invoice_id=invoice_id,
        supplier_telegram_id=USER_A,
    )

    source = inspect.getsource(GoogleDriveArchiveStubService)
    assert 'googleapiclient' not in source
    assert 'requests' not in source
    assert 'httpx' not in source
    assert 'aiohttp' not in source
    assert result.status == DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID
    assert 'nie je aktivna' in result.user_message
    assert 'ostava ulozena lokalne' in result.user_message
    assert 'nahrata' not in result.user_message.lower()
    assert 'uploaded' not in result.user_message.lower()


def test_tenant_isolation_supplier_a_never_receives_supplier_b_invoice(tmp_path: Path) -> None:
    db_path = tmp_path / 'tenant.db'
    init_db(db_path)
    contact_a = _setup_account(db_path, USER_A)
    contact_b = _setup_account(db_path, USER_B)
    invoice_a = _create_invoice(
        db_path,
        supplier_telegram_id=USER_A,
        contact_id=contact_a,
        invoice_number='20260001',
        due_date='2026-06-10',
    )
    invoice_b = _create_invoice(
        db_path,
        supplier_telegram_id=USER_B,
        contact_id=contact_b,
        invoice_number='20260001',
        due_date='2026-06-10',
    )

    reminders = InvoiceFollowupService(db_path).list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-15',
        now='2026-06-15T10:00:00',
    )

    assert [item.invoice_id for item in reminders] == [invoice_a]
    assert invoice_b not in [item.invoice_id for item in reminders]


def test_existing_invoices_without_followup_row_are_unpaid_active_safely(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path, due_date='2026-06-10')

    state = service.get_effective_state_for_invoice(invoice_id=invoice_id, supplier_telegram_id=USER_A)

    assert state.payment_status == 'unpaid'
    assert state.reminder_status == REMINDER_STATUS_ACTIVE
    assert state.remind_after is None


def test_automatic_supplier_scan_returns_only_suppliers_with_due_active_invoices(tmp_path: Path) -> None:
    db_path = tmp_path / 'scan.db'
    init_db(db_path)
    contact_a = _setup_account(db_path, USER_A)
    contact_b = _setup_account(db_path, USER_B)
    _create_invoice(
        db_path,
        supplier_telegram_id=USER_A,
        contact_id=contact_a,
        invoice_number='20260001',
        due_date='2026-06-10',
    )
    _create_invoice(
        db_path,
        supplier_telegram_id=USER_B,
        contact_id=contact_b,
        invoice_number='20260002',
        due_date='2026-06-16',
    )

    supplier_ids = InvoiceFollowupService(db_path).list_supplier_telegram_ids_with_due_invoices(
        today='2026-06-15',
        now='2026-06-15T10:00:00',
    )

    assert supplier_ids == [USER_A]


def test_record_reminder_sent_keeps_invoice_unpaid_active_and_delays_next_notification(tmp_path: Path) -> None:
    _db_path, service, invoice_id = _service_with_invoice(tmp_path, due_date='2026-06-10')

    state = service.record_reminder_sent(
        invoice_id=invoice_id,
        supplier_telegram_id=USER_A,
        now='2026-06-15T10:00:00',
        next_reminder_after='2026-06-16T10:00:00',
    )

    assert state.payment_status == 'unpaid'
    assert state.reminder_status == REMINDER_STATUS_ACTIVE
    assert state.remind_after == '2026-06-16T10:00:00'
    assert service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-16',
        now='2026-06-16T09:59:00',
    ) == []


def test_deleted_invoice_is_not_selected_even_if_followup_state_remains(tmp_path: Path) -> None:
    db_path, service, invoice_id = _service_with_invoice(tmp_path, due_date='2026-06-10')
    service.remind_later(
        invoice_id=invoice_id,
        supplier_telegram_id=USER_A,
        now='2026-06-15T10:00:00',
        remind_after='2026-06-14T10:00:00',
    )
    with managed_connection(db_path) as connection:
        connection.execute('DELETE FROM invoice WHERE id = ?', (invoice_id,))
        connection.commit()

    assert service.list_due_invoices_for_supplier(
        supplier_telegram_id=USER_A,
        today='2026-06-16',
        now='2026-06-16T10:00:00',
    ) == []
