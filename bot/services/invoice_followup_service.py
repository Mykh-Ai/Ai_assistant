from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3

from bot.services.db import ensure_invoice_followup_state_schema, managed_connection


PAYMENT_STATUS_UNPAID = 'unpaid'
PAYMENT_STATUS_PAID = 'paid'

REMINDER_STATUS_ACTIVE = 'active'
REMINDER_STATUS_SNOOZED = 'snoozed'
REMINDER_STATUS_MUTED = 'muted'

DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED = 'stub_not_uploaded'
DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID = 'stub_requested_after_paid'
DRIVE_ARCHIVE_STATUS_STUB_SKIPPED_NO_DRIVE_RUNTIME = 'stub_skipped_no_drive_runtime'
DRIVE_ARCHIVE_STATUS_PENDING = 'pending'
DRIVE_ARCHIVE_STATUS_UPLOADED = 'uploaded'
DRIVE_ARCHIVE_STATUS_RETRY_WAIT = 'retry_wait'
DRIVE_ARCHIVE_STATUS_FAILED = 'failed'

DRIVE_ARCHIVE_STUB_NOTE = (
    'Archivacia na Google Drive este nie je aktivna. Faktura ostava ulozena lokalne. '
    'Po zapnuti Drive integracie ju bude mozne archivovat podla pravidiel.'
)

DRIVE_ARCHIVE_STUB_USER_MESSAGE = (
    'Archivacia na Google Drive este nie je aktivna. Faktura ostava ulozena lokalne. '
    'Po zapnuti Drive integracie ju bude mozne archivovat podla pravidiel.'
)


@dataclass(frozen=True)
class InvoiceFollowupState:
    invoice_id: int
    supplier_telegram_id: int
    payment_status: str
    reminder_status: str
    remind_after: str | None
    paid_at: str | None
    muted_at: str | None
    drive_archive_status: str
    drive_archive_note: str | None
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class OverdueInvoiceReminder:
    invoice_id: int
    supplier_telegram_id: int
    invoice_number: str
    customer_name: str
    total_amount: float
    currency: str
    due_date: str
    payment_status: str
    reminder_status: str
    remind_after: str | None


class InvoiceFollowupService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def list_due_invoices_for_supplier(
        self,
        *,
        supplier_telegram_id: int,
        today: date | str | None = None,
        now: datetime | str | None = None,
    ) -> list[OverdueInvoiceReminder]:
        if supplier_telegram_id <= 0:
            return []
        today_value = _date_string(today or date.today())
        now_value = _datetime_string(now or datetime.now())
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT i.id AS invoice_id, i.supplier_telegram_id, i.invoice_number, '
                    'COALESCE(NULLIF(TRIM(c.name), \'\'), \'nezisteny odberatel\') AS customer_name, '
                    'i.total_amount, i.currency, i.due_date, '
                    'COALESCE(s.payment_status, ?) AS payment_status, '
                    'COALESCE(s.reminder_status, ?) AS reminder_status, '
                    's.remind_after '
                    'FROM invoice i '
                    'LEFT JOIN invoice_followup_state s ON s.invoice_id = i.id '
                    'LEFT JOIN contact c ON c.id = i.contact_id AND c.supplier_telegram_id = i.supplier_telegram_id '
                    'WHERE i.supplier_telegram_id = ? '
                    + _legacy_invoice_scope_sql(connection, alias='i') +
                    'AND i.due_date < ? '
                    'AND COALESCE(s.payment_status, ?) != ? '
                    'AND COALESCE(s.reminder_status, ?) != ? '
                    'AND (s.remind_after IS NULL OR s.remind_after <= ?) '
                    'ORDER BY i.due_date ASC, i.invoice_number ASC'
                ),
                (
                    PAYMENT_STATUS_UNPAID,
                    REMINDER_STATUS_ACTIVE,
                    supplier_telegram_id,
                    today_value,
                    PAYMENT_STATUS_UNPAID,
                    PAYMENT_STATUS_PAID,
                    REMINDER_STATUS_ACTIVE,
                    REMINDER_STATUS_MUTED,
                    now_value,
                ),
            ).fetchall()
        return [_reminder_from_row(row) for row in rows]

    def list_supplier_telegram_ids_with_due_invoices(
        self,
        *,
        today: date | str | None = None,
        now: datetime | str | None = None,
    ) -> list[int]:
        today_value = _date_string(today or date.today())
        now_value = _datetime_string(now or datetime.now())
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            rows = connection.execute(
                (
                    'SELECT DISTINCT i.supplier_telegram_id '
                    'FROM invoice i '
                    'LEFT JOIN invoice_followup_state s ON s.invoice_id = i.id '
                    'WHERE i.due_date < ? '
                    + _legacy_invoice_scope_sql(connection, alias='i') +
                    'AND COALESCE(s.payment_status, ?) != ? '
                    'AND COALESCE(s.reminder_status, ?) != ? '
                    'AND (s.remind_after IS NULL OR s.remind_after <= ?) '
                    'ORDER BY i.supplier_telegram_id ASC'
                ),
                (
                    today_value,
                    PAYMENT_STATUS_UNPAID,
                    PAYMENT_STATUS_PAID,
                    REMINDER_STATUS_ACTIVE,
                    REMINDER_STATUS_MUTED,
                    now_value,
                ),
            ).fetchall()
        return [int(row[0]) for row in rows]

    def get_state(self, *, invoice_id: int) -> InvoiceFollowupState | None:
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                'SELECT * FROM invoice_followup_state WHERE invoice_id = ? '
                + _legacy_followup_scope_sql(connection),
                (invoice_id,),
            ).fetchone()
        return _state_from_row(row) if row is not None else None

    def get_effective_state_for_invoice(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
    ) -> InvoiceFollowupState:
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            _assert_invoice_owner(
                connection,
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
        existing = self.get_state(invoice_id=invoice_id)
        if existing is not None:
            return existing
        return InvoiceFollowupState(
            invoice_id=invoice_id,
            supplier_telegram_id=supplier_telegram_id,
            payment_status=PAYMENT_STATUS_UNPAID,
            reminder_status=REMINDER_STATUS_ACTIVE,
            remind_after=None,
            paid_at=None,
            muted_at=None,
            drive_archive_status=DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
            drive_archive_note=None,
            created_at=None,
            updated_at=None,
        )

    def mark_paid(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
        now: datetime | str | None = None,
    ) -> InvoiceFollowupState:
        timestamp = _datetime_string(now or datetime.now())
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            _assert_invoice_owner(connection, invoice_id=invoice_id, supplier_telegram_id=supplier_telegram_id)
            connection.execute(
                (
                    'INSERT INTO invoice_followup_state '
                    '(invoice_id, supplier_telegram_id, payment_status, reminder_status, remind_after, '
                    'paid_at, muted_at, drive_archive_status, drive_archive_note, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, NULL, ?, NULL, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(invoice_id) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'payment_status=excluded.payment_status, '
                    'reminder_status=excluded.reminder_status, '
                    'remind_after=NULL, '
                    'paid_at=excluded.paid_at, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    invoice_id,
                    supplier_telegram_id,
                    PAYMENT_STATUS_PAID,
                    REMINDER_STATUS_MUTED,
                    timestamp,
                    DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
                ),
            )
            connection.commit()
        state = self.get_state(invoice_id=invoice_id)
        if state is None:
            raise RuntimeError('invoice_followup_state_missing_after_mark_paid')
        return state

    def remind_later(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
        now: datetime | str | None = None,
        remind_after: datetime | str | None = None,
    ) -> InvoiceFollowupState:
        base_now = _coerce_datetime(now or datetime.now())
        remind_after_value = _datetime_string(remind_after or (base_now + timedelta(hours=24)))
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            _assert_invoice_owner(connection, invoice_id=invoice_id, supplier_telegram_id=supplier_telegram_id)
            connection.execute(
                (
                    'INSERT INTO invoice_followup_state '
                    '(invoice_id, supplier_telegram_id, payment_status, reminder_status, remind_after, '
                    'paid_at, muted_at, drive_archive_status, drive_archive_note, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(invoice_id) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'payment_status=excluded.payment_status, '
                    'reminder_status=excluded.reminder_status, '
                    'remind_after=excluded.remind_after, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    invoice_id,
                    supplier_telegram_id,
                    PAYMENT_STATUS_UNPAID,
                    REMINDER_STATUS_SNOOZED,
                    remind_after_value,
                    DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
                ),
            )
            connection.commit()
        state = self.get_state(invoice_id=invoice_id)
        if state is None:
            raise RuntimeError('invoice_followup_state_missing_after_remind_later')
        return state

    def record_reminder_sent(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
        now: datetime | str | None = None,
        next_reminder_after: datetime | str | None = None,
    ) -> InvoiceFollowupState:
        base_now = _coerce_datetime(now or datetime.now())
        next_after_value = _datetime_string(next_reminder_after or (base_now + timedelta(hours=24)))
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            _assert_invoice_owner(connection, invoice_id=invoice_id, supplier_telegram_id=supplier_telegram_id)
            connection.execute(
                (
                    'INSERT INTO invoice_followup_state '
                    '(invoice_id, supplier_telegram_id, payment_status, reminder_status, remind_after, '
                    'paid_at, muted_at, drive_archive_status, drive_archive_note, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(invoice_id) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'payment_status=excluded.payment_status, '
                    'reminder_status=excluded.reminder_status, '
                    'remind_after=excluded.remind_after, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    invoice_id,
                    supplier_telegram_id,
                    PAYMENT_STATUS_UNPAID,
                    REMINDER_STATUS_ACTIVE,
                    next_after_value,
                    DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
                ),
            )
            connection.commit()
        state = self.get_state(invoice_id=invoice_id)
        if state is None:
            raise RuntimeError('invoice_followup_state_missing_after_record_sent')
        return state

    def mute(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
        now: datetime | str | None = None,
    ) -> InvoiceFollowupState:
        timestamp = _datetime_string(now or datetime.now())
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            _assert_invoice_owner(connection, invoice_id=invoice_id, supplier_telegram_id=supplier_telegram_id)
            connection.execute(
                (
                    'INSERT INTO invoice_followup_state '
                    '(invoice_id, supplier_telegram_id, payment_status, reminder_status, remind_after, '
                    'paid_at, muted_at, drive_archive_status, drive_archive_note, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(invoice_id) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'payment_status=excluded.payment_status, '
                    'reminder_status=excluded.reminder_status, '
                    'remind_after=NULL, '
                    'muted_at=excluded.muted_at, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    invoice_id,
                    supplier_telegram_id,
                    PAYMENT_STATUS_UNPAID,
                    REMINDER_STATUS_MUTED,
                    timestamp,
                    DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
                ),
            )
            connection.commit()
        state = self.get_state(invoice_id=invoice_id)
        if state is None:
            raise RuntimeError('invoice_followup_state_missing_after_mute')
        return state

    def record_drive_archive_stub(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
        status: str,
        note: str,
    ) -> InvoiceFollowupState:
        return self.record_drive_archive_status(
            invoice_id=invoice_id,
            supplier_telegram_id=supplier_telegram_id,
            status=status,
            note=note,
        )

    def record_drive_archive_status(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
        status: str,
        note: str,
    ) -> InvoiceFollowupState:
        if status not in {
            DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
            DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
            DRIVE_ARCHIVE_STATUS_STUB_SKIPPED_NO_DRIVE_RUNTIME,
            DRIVE_ARCHIVE_STATUS_PENDING,
            DRIVE_ARCHIVE_STATUS_UPLOADED,
            DRIVE_ARCHIVE_STATUS_RETRY_WAIT,
            DRIVE_ARCHIVE_STATUS_FAILED,
        }:
            raise ValueError('unsupported_drive_archive_status')
        with managed_connection(self._db_path) as connection:
            ensure_invoice_followup_state_schema(connection)
            _assert_invoice_owner(connection, invoice_id=invoice_id, supplier_telegram_id=supplier_telegram_id)
            connection.execute(
                (
                    'INSERT INTO invoice_followup_state '
                    '(invoice_id, supplier_telegram_id, payment_status, reminder_status, remind_after, '
                    'paid_at, muted_at, drive_archive_status, drive_archive_note, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, NULL, NULL, NULL, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(invoice_id) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'drive_archive_status=excluded.drive_archive_status, '
                    'drive_archive_note=excluded.drive_archive_note, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    invoice_id,
                    supplier_telegram_id,
                    PAYMENT_STATUS_UNPAID,
                    REMINDER_STATUS_ACTIVE,
                    status,
                    note,
                ),
            )
            connection.commit()
        state = self.get_state(invoice_id=invoice_id)
        if state is None:
            raise RuntimeError('invoice_followup_state_missing_after_drive_stub')
        return state


def _assert_invoice_owner(
    connection: sqlite3.Connection,
    *,
    invoice_id: int,
    supplier_telegram_id: int,
) -> None:
    row = connection.execute(
        'SELECT id FROM invoice WHERE id = ? AND supplier_telegram_id = ? '
        + _legacy_invoice_scope_sql(connection),
        (invoice_id, supplier_telegram_id),
    ).fetchone()
    if row is None:
        raise ValueError('invoice_not_found_for_supplier')


def _legacy_invoice_scope_sql(
    connection: sqlite3.Connection,
    *,
    alias: str = 'invoice',
) -> str:
    columns = {row[1] for row in connection.execute('PRAGMA table_info(invoice)')}
    return f'AND {alias}.workspace_id IS NULL ' if 'workspace_id' in columns else ''


def _legacy_followup_scope_sql(connection: sqlite3.Connection) -> str:
    columns = {
        row[1] for row in connection.execute('PRAGMA table_info(invoice_followup_state)')
    }
    return 'AND workspace_id IS NULL' if 'workspace_id' in columns else ''

def _state_from_row(row: sqlite3.Row) -> InvoiceFollowupState:
    return InvoiceFollowupState(
        invoice_id=int(row['invoice_id']),
        supplier_telegram_id=int(row['supplier_telegram_id']),
        payment_status=str(row['payment_status']),
        reminder_status=str(row['reminder_status']),
        remind_after=row['remind_after'],
        paid_at=row['paid_at'],
        muted_at=row['muted_at'],
        drive_archive_status=str(row['drive_archive_status']),
        drive_archive_note=row['drive_archive_note'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def _reminder_from_row(row: sqlite3.Row) -> OverdueInvoiceReminder:
    return OverdueInvoiceReminder(
        invoice_id=int(row['invoice_id']),
        supplier_telegram_id=int(row['supplier_telegram_id']),
        invoice_number=str(row['invoice_number']),
        customer_name=str(row['customer_name']),
        total_amount=float(row['total_amount']),
        currency=str(row['currency']),
        due_date=str(row['due_date']),
        payment_status=str(row['payment_status']),
        reminder_status=str(row['reminder_status']),
        remind_after=row['remind_after'],
    )


def _date_string(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _datetime_string(value: datetime | str) -> str:
    if isinstance(value, str):
        return value
    return value.replace(microsecond=0).isoformat()


def _coerce_datetime(value: datetime | str) -> datetime:
    if isinstance(value, datetime):
        return value.replace(microsecond=0)
    return datetime.fromisoformat(value)
