from datetime import date
from pathlib import Path

from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db, managed_connection
from bot.services.invoice_analytics_dataset import (
    INVOICE_ANALYTICS_COLUMNS,
    InvoiceAnalyticsDatasetService,
    build_invoice_analytics_data_catalog,
    resolve_payment_status_filter_hints,
)
from bot.services.invoice_followup_service import InvoiceFollowupService
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService


def _seed_invoice(
    db_path: Path,
    *,
    supplier_telegram_id: int,
    contact_id: int,
    invoice_number: str,
    issue_date: str,
    due_date: str | None = None,
    total_amount: float,
    status: str = 'created',
    pdf_path: str | None = None,
) -> int:
    invoice_id = InvoiceService(db_path).create_invoice_with_items(
        supplier_telegram_id=supplier_telegram_id,
        contact_id=contact_id,
        invoice_number=invoice_number,
        issue_date=issue_date,
        delivery_date=issue_date,
        due_date=due_date or issue_date,
        due_days=14,
        total_amount=total_amount,
        currency='EUR',
        status=status,
        items=[
            CreateInvoiceItemPayload(
                description_raw='service',
                description_normalized='Service',
                item_description_raw=None,
                quantity=1,
                unit='ks',
                unit_price=total_amount,
                total_price=total_amount,
            )
        ],
    )
    if pdf_path is not None:
        InvoiceService(db_path).save_pdf_path(invoice_id, pdf_path)
    return invoice_id


def _insert_followup_state(
    db_path: Path,
    *,
    invoice_id: int,
    supplier_telegram_id: int,
    payment_status: str,
    reminder_status: str = 'active',
) -> None:
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO invoice_followup_state '
                '(invoice_id, supplier_telegram_id, payment_status, reminder_status, '
                'drive_archive_status, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
            ),
            (invoice_id, supplier_telegram_id, payment_status, reminder_status, 'stub_not_uploaded'),
        )
        connection.commit()


def test_invoice_analytics_dataset_is_supplier_scoped_and_sanitized(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    ContactService(db_path).create_contact(
        ContactProfile(
            supplier_telegram_id=111,
            name='Tomas s.r.o.',
            ico='12345678',
            dic='1234567890',
            ic_dph=None,
            address='Hlavna 1, Kosice',
            email='',
            contact_person=None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(db_path).get_by_name(111, 'Tomas s.r.o.')
    assert contact is not None and contact.id is not None
    _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=contact.id,
        invoice_number='20260001',
        issue_date='2026-05-10',
        due_date='2026-05-24',
        total_amount=100,
        status='created',
        pdf_path=str(tmp_path / 'secret' / '20260001.pdf'),
    )
    _seed_invoice(
        db_path,
        supplier_telegram_id=222,
        contact_id=999,
        invoice_number='20260002',
        issue_date='2026-05-11',
        due_date='2026-05-25',
        total_amount=999,
    )

    dataframe = InvoiceAnalyticsDatasetService(db_path).build_invoice_dataframe_for_supplier(
        supplier_telegram_id=111,
        current_date=date(2026, 5, 20),
    )

    assert list(dataframe.columns) == list(INVOICE_ANALYTICS_COLUMNS)
    assert len(dataframe) == 1
    row = dataframe.iloc[0].to_dict()
    assert row['invoice_number'] == '20260001'
    assert row['customer_name'] == 'Tomas s.r.o.'
    assert row['total_amount'] == 100
    assert row['invoice_status_raw'] == 'created'
    assert row['payment_status_canonical'] == 'pending_payment'
    assert row['payment_status_source'] == 'derived_missing_followup_state'
    assert bool(row['has_pdf']) is True
    assert 'status' not in dataframe.columns
    assert 'pdf_path' not in dataframe.columns
    assert '20260002' not in set(dataframe['invoice_number'])


def test_invoice_analytics_dataset_normalizes_payment_statuses(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    paid_id = _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260010',
        issue_date='2026-05-01',
        due_date='2026-05-15',
        total_amount=100,
        status='created',
    )
    pending_id = _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260011',
        issue_date='2026-06-01',
        due_date='2026-06-17',
        total_amount=200,
        status='archived_raw_lifecycle_value',
    )
    _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260012',
        issue_date='2026-05-20',
        due_date='2026-06-01',
        total_amount=300,
        status='created',
    )
    unknown_id = _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260013',
        issue_date='2026-06-01',
        due_date='not-a-date',
        total_amount=400,
        status='created',
    )
    muted_unpaid_id = _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260014',
        issue_date='2026-05-25',
        due_date='2026-06-16',
        total_amount=3840,
        status='pripravena',
    )
    other_supplier_id = _seed_invoice(
        db_path,
        supplier_telegram_id=222,
        contact_id=404,
        invoice_number='20260099',
        issue_date='2026-05-01',
        due_date='2026-05-01',
        total_amount=999,
        status='created',
    )

    InvoiceFollowupService(db_path).mark_paid(
        invoice_id=paid_id,
        supplier_telegram_id=111,
        now='2026-06-17T10:00:00',
    )
    _insert_followup_state(
        db_path,
        invoice_id=pending_id,
        supplier_telegram_id=111,
        payment_status='unpaid',
    )
    _insert_followup_state(
        db_path,
        invoice_id=unknown_id,
        supplier_telegram_id=111,
        payment_status='',
    )
    _insert_followup_state(
        db_path,
        invoice_id=muted_unpaid_id,
        supplier_telegram_id=111,
        payment_status='unpaid',
        reminder_status='muted',
    )
    _insert_followup_state(
        db_path,
        invoice_id=other_supplier_id,
        supplier_telegram_id=222,
        payment_status='paid',
    )

    dataframe = InvoiceAnalyticsDatasetService(db_path).build_invoice_dataframe_for_supplier(
        supplier_telegram_id=111,
        current_date=date(2026, 6, 17),
    )
    by_number = {row['invoice_number']: row for row in dataframe.to_dict(orient='records')}

    assert by_number['20260010']['payment_status_canonical'] == 'paid'
    assert by_number['20260010']['payment_status_source'] == 'invoice_followup_state'
    assert by_number['20260011']['payment_status_canonical'] == 'pending_payment'
    assert by_number['20260012']['payment_status_canonical'] == 'overdue'
    assert by_number['20260012']['payment_status_source'] == 'derived_missing_followup_state'
    assert by_number['20260013']['payment_status_canonical'] == 'unknown'
    assert by_number['20260013']['payment_status_source'] == 'missing_payment_status'
    assert by_number['20260014']['payment_status_canonical'] == 'overdue'
    assert by_number['20260014']['payment_status_source'] == 'invoice_followup_state'
    assert by_number['20260011']['invoice_status_raw'] == 'archived_raw_lifecycle_value'
    assert '20260099' not in by_number


def test_invoice_analytics_question_uses_normalized_payment_status_not_raw_status(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    paid_id = _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260020',
        issue_date='2026-06-01',
        due_date='2026-06-30',
        total_amount=100,
        status='created',
    )
    _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260021',
        issue_date='2026-05-01',
        due_date='2026-05-15',
        total_amount=200,
        status='paid',
    )
    _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260022',
        issue_date='2026-06-01',
        due_date='2026-06-30',
        total_amount=300,
        status='paid',
    )
    InvoiceFollowupService(db_path).mark_paid(
        invoice_id=paid_id,
        supplier_telegram_id=111,
        now='2026-06-17T10:00:00',
    )

    dataframe = InvoiceAnalyticsDatasetService(db_path).build_invoice_dataframe_for_supplier(
        supplier_telegram_id=111,
        current_date=date(2026, 6, 17),
    )

    counts = dataframe.groupby('payment_status_canonical')['invoice_id'].count().to_dict()
    assert counts == {'overdue': 1, 'paid': 1, 'pending_payment': 1}
    assert 'status' not in dataframe.columns


def test_invoice_analytics_dataset_missing_contact_and_missing_db_are_safe(tmp_path: Path) -> None:
    db_path = tmp_path / 'test.db'
    init_db(db_path)
    _seed_invoice(
        db_path,
        supplier_telegram_id=111,
        contact_id=404,
        invoice_number='20260003',
        issue_date='2026-06-01',
        due_date='2026-06-15',
        total_amount=50,
    )

    dataframe = InvoiceAnalyticsDatasetService(db_path).build_invoice_dataframe_for_supplier(
        supplier_telegram_id=111,
        current_date=date(2026, 6, 17),
    )
    assert dataframe.iloc[0]['customer_name'] == 'Neznamy odberatel'
    assert dataframe.iloc[0]['payment_status_canonical'] == 'overdue'
    assert bool(dataframe.iloc[0]['has_pdf']) is False

    missing = InvoiceAnalyticsDatasetService(tmp_path / 'missing.db').build_invoice_dataframe_for_supplier(
        supplier_telegram_id=111,
        current_date=date(2026, 6, 17),
    )
    assert list(missing.columns) == list(INVOICE_ANALYTICS_COLUMNS)
    assert missing.empty

def test_invoice_analytics_payment_status_filter_hints_define_unpaid_as_pending_plus_overdue() -> None:
    hints = resolve_payment_status_filter_hints('\u043f\u043e\u043a\u0430\u0436\u0438 \u043d\u0435\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u0456 \u0444\u0430\u043a\u0442\u0443\u0440\u0438')

    assert hints == [
        {
            'filter_group': 'unpaid',
            'canonical_values': ['pending_payment', 'overdue'],
            'matched_alias': '\u043d\u0435\u043e\u043f\u043b\u0430\u0447\u0435\u043d\u0456',
        }
    ]

    catalog = build_invoice_analytics_data_catalog(user_question='ktore faktury su neuhradene?')
    assert catalog['payment_status_filter_hints'][0]['filter_group'] == 'unpaid'
    assert catalog['payment_status_filter_hints'][0]['canonical_values'] == ['pending_payment', 'overdue']
    assert 'pending_payment only' in catalog['payment_status_filter_contract']


def test_invoice_analytics_payment_status_filter_hints_keep_overdue_specific() -> None:
    hints = resolve_payment_status_filter_hints('ktore faktury su po splatnosti?')

    assert hints == [
        {
            'filter_group': 'overdue',
            'canonical_values': ['overdue'],
            'matched_alias': 'po splatnosti',
        }
    ]
