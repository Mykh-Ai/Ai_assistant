from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
import sqlite3

from bot.services.db import ensure_invoice_followup_state_schema, managed_connection
from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_FAILED,
    DRIVE_ARCHIVE_STATUS_PENDING,
    DRIVE_ARCHIVE_STATUS_RETRY_WAIT,
    DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
    DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
    DRIVE_ARCHIVE_STATUS_STUB_SKIPPED_NO_DRIVE_RUNTIME,
    DRIVE_ARCHIVE_STATUS_UPLOADED,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_UNPAID,
    REMINDER_STATUS_ACTIVE,
    REMINDER_STATUS_MUTED,
    REMINDER_STATUS_SNOOZED,
)
from bot.services.workspace_context import WorkspaceContext


_DRIVE_ARCHIVE_STATUSES = {
    DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
    DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
    DRIVE_ARCHIVE_STATUS_STUB_SKIPPED_NO_DRIVE_RUNTIME,
    DRIVE_ARCHIVE_STATUS_PENDING,
    DRIVE_ARCHIVE_STATUS_UPLOADED,
    DRIVE_ARCHIVE_STATUS_RETRY_WAIT,
    DRIVE_ARCHIVE_STATUS_FAILED,
}


class WorkspaceInvoiceFollowupSchemaRequired(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkspaceInvoiceFollowupState:
    invoice_id: int
    workspace_id: str
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
class WorkspaceOverdueInvoiceReminder:
    invoice_id: int
    workspace_id: str
    supplier_telegram_id: int
    invoice_number: str
    customer_name: str
    total_amount: float
    currency: str
    due_date: str
    payment_status: str
    reminder_status: str
    remind_after: str | None


class WorkspaceInvoiceFollowupService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def list_due_invoices(
        self,
        context: WorkspaceContext,
        *,
        today: date | str | None = None,
        now: datetime | str | None = None,
    ) -> list[WorkspaceOverdueInvoiceReminder]:
        today_value = _date_string(today or date.today())
        now_value = _datetime_string(now or datetime.now())
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT i.id AS invoice_id, i.workspace_id, '
                    'i.supplier_telegram_id, i.invoice_number, '
                    "COALESCE(NULLIF(TRIM(c.name), ''), 'nezisteny odberatel') AS customer_name, "
                    'i.total_amount, i.currency, i.due_date, '
                    'COALESCE(s.payment_status, ?) AS payment_status, '
                    'COALESCE(s.reminder_status, ?) AS reminder_status, s.remind_after '
                    'FROM invoice i '
                    'LEFT JOIN invoice_followup_state s '
                    'ON s.invoice_id = i.id AND s.workspace_id = i.workspace_id '
                    'LEFT JOIN contact c '
                    'ON c.id = i.contact_id AND c.workspace_id = i.workspace_id '
                    'WHERE i.workspace_id = ? AND i.due_date < ? '
                    'AND COALESCE(s.payment_status, ?) != ? '
                    'AND COALESCE(s.reminder_status, ?) != ? '
                    'AND (s.remind_after IS NULL OR s.remind_after <= ?) '
                    'ORDER BY i.due_date ASC, i.invoice_number ASC'
                ),
                (
                    PAYMENT_STATUS_UNPAID,
                    REMINDER_STATUS_ACTIVE,
                    context.workspace_id,
                    today_value,
                    PAYMENT_STATUS_UNPAID,
                    PAYMENT_STATUS_PAID,
                    REMINDER_STATUS_ACTIVE,
                    REMINDER_STATUS_MUTED,
                    now_value,
                ),
            ).fetchall()
        return [_reminder_from_row(row) for row in rows]

    def list_workspace_ids_with_due_invoices(
        self,
        *,
        today: date | str | None = None,
        now: datetime | str | None = None,
    ) -> list[str]:
        """Return persisted workspaces for background jobs; active selection is irrelevant."""
        today_value = _date_string(today or date.today())
        now_value = _datetime_string(now or datetime.now())
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            rows = connection.execute(
                (
                    'SELECT DISTINCT i.workspace_id FROM invoice i '
                    'LEFT JOIN invoice_followup_state s '
                    'ON s.invoice_id = i.id AND s.workspace_id = i.workspace_id '
                    'WHERE i.workspace_id IS NOT NULL AND i.due_date < ? '
                    'AND COALESCE(s.payment_status, ?) != ? '
                    'AND COALESCE(s.reminder_status, ?) != ? '
                    'AND (s.remind_after IS NULL OR s.remind_after <= ?) '
                    'ORDER BY i.workspace_id ASC'
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
        return [str(row[0]) for row in rows]

    def get_state(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
    ) -> WorkspaceInvoiceFollowupState | None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                'SELECT * FROM invoice_followup_state '
                'WHERE invoice_id = ? AND workspace_id = ?',
                (invoice_id, context.workspace_id),
            ).fetchone()
        return _state_from_row(row) if row is not None else None

    def get_effective_state_for_invoice(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
    ) -> WorkspaceInvoiceFollowupState:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            self._assert_invoice_owner(connection, context, invoice_id)
        existing = self.get_state(context, invoice_id=invoice_id)
        if existing is not None:
            return existing
        return WorkspaceInvoiceFollowupState(
            invoice_id=invoice_id,
            workspace_id=context.workspace_id,
            supplier_telegram_id=context.actor_telegram_id,
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
        context: WorkspaceContext,
        *,
        invoice_id: int,
        now: datetime | str | None = None,
    ) -> WorkspaceInvoiceFollowupState:
        return self._upsert(
            context,
            invoice_id=invoice_id,
            payment_status=PAYMENT_STATUS_PAID,
            reminder_status=REMINDER_STATUS_MUTED,
            remind_after=None,
            paid_at=_datetime_string(now or datetime.now()),
            muted_at=None,
            replace_remind_after=True,
        )

    def remind_later(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        now: datetime | str | None = None,
        remind_after: datetime | str | None = None,
    ) -> WorkspaceInvoiceFollowupState:
        base_now = _coerce_datetime(now or datetime.now())
        return self._upsert(
            context,
            invoice_id=invoice_id,
            payment_status=PAYMENT_STATUS_UNPAID,
            reminder_status=REMINDER_STATUS_SNOOZED,
            remind_after=_datetime_string(remind_after or base_now + timedelta(hours=24)),
            replace_remind_after=True,
        )

    def record_reminder_sent(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        now: datetime | str | None = None,
        next_reminder_after: datetime | str | None = None,
    ) -> WorkspaceInvoiceFollowupState:
        base_now = _coerce_datetime(now or datetime.now())
        return self._upsert(
            context,
            invoice_id=invoice_id,
            payment_status=PAYMENT_STATUS_UNPAID,
            reminder_status=REMINDER_STATUS_ACTIVE,
            remind_after=_datetime_string(
                next_reminder_after or base_now + timedelta(hours=24)
            ),
            replace_remind_after=True,
        )

    def mute(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        now: datetime | str | None = None,
    ) -> WorkspaceInvoiceFollowupState:
        return self._upsert(
            context,
            invoice_id=invoice_id,
            payment_status=PAYMENT_STATUS_UNPAID,
            reminder_status=REMINDER_STATUS_MUTED,
            remind_after=None,
            muted_at=_datetime_string(now or datetime.now()),
            replace_remind_after=True,
        )

    def record_drive_archive_status(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        status: str,
        note: str,
    ) -> WorkspaceInvoiceFollowupState:
        if status not in _DRIVE_ARCHIVE_STATUSES:
            raise ValueError('unsupported_drive_archive_status')
        return self._upsert(
            context,
            invoice_id=invoice_id,
            drive_archive_status=status,
            drive_archive_note=note,
        )

    def _upsert(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        payment_status: str | None = None,
        reminder_status: str | None = None,
        remind_after: str | None = None,
        paid_at: str | None = None,
        muted_at: str | None = None,
        drive_archive_status: str | None = None,
        drive_archive_note: str | None = None,
        replace_remind_after: bool = False,
    ) -> WorkspaceInvoiceFollowupState:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            self._assert_invoice_owner(connection, context, invoice_id)
            connection.execute(
                (
                    'INSERT INTO invoice_followup_state '
                    '(invoice_id, workspace_id, supplier_telegram_id, payment_status, '
                    'reminder_status, remind_after, paid_at, muted_at, '
                    'drive_archive_status, drive_archive_note, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(invoice_id) DO UPDATE SET '
                    'workspace_id=excluded.workspace_id, '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'payment_status=COALESCE(?, invoice_followup_state.payment_status), '
                    'reminder_status=COALESCE(?, invoice_followup_state.reminder_status), '
                    'remind_after=CASE WHEN ? THEN ? ELSE invoice_followup_state.remind_after END, '
                    'paid_at=COALESCE(?, invoice_followup_state.paid_at), '
                    'muted_at=COALESCE(?, invoice_followup_state.muted_at), '
                    'drive_archive_status=COALESCE(?, invoice_followup_state.drive_archive_status), '
                    'drive_archive_note=COALESCE(?, invoice_followup_state.drive_archive_note), '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    invoice_id,
                    context.workspace_id,
                    context.actor_telegram_id,
                    payment_status or PAYMENT_STATUS_UNPAID,
                    reminder_status or REMINDER_STATUS_ACTIVE,
                    remind_after,
                    paid_at,
                    muted_at,
                    drive_archive_status or DRIVE_ARCHIVE_STATUS_STUB_NOT_UPLOADED,
                    drive_archive_note,
                    payment_status,
                    reminder_status,
                    int(replace_remind_after),
                    remind_after,
                    paid_at,
                    muted_at,
                    drive_archive_status,
                    drive_archive_note,
                ),
            )
            connection.commit()
        state = self.get_state(context, invoice_id=invoice_id)
        if state is None:
            raise RuntimeError('workspace_invoice_followup_state_missing_after_write')
        return state

    @staticmethod
    def _assert_invoice_owner(
        connection: sqlite3.Connection,
        context: WorkspaceContext,
        invoice_id: int,
    ) -> None:
        row = connection.execute(
            'SELECT id FROM invoice WHERE id = ? AND workspace_id = ?',
            (invoice_id, context.workspace_id),
        ).fetchone()
        if row is None:
            raise ValueError('invoice_not_found_for_workspace')

    @staticmethod
    def _require_schema(connection: sqlite3.Connection) -> None:
        ensure_invoice_followup_state_schema(connection)
        for table in ('invoice', 'contact', 'invoice_followup_state'):
            columns = {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}
            if 'workspace_id' not in columns:
                raise WorkspaceInvoiceFollowupSchemaRequired(
                    f'workspace_{table}_schema_migration_required'
                )


def _state_from_row(row: sqlite3.Row) -> WorkspaceInvoiceFollowupState:
    return WorkspaceInvoiceFollowupState(
        invoice_id=int(row['invoice_id']),
        workspace_id=str(row['workspace_id']),
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


def _reminder_from_row(row: sqlite3.Row) -> WorkspaceOverdueInvoiceReminder:
    return WorkspaceOverdueInvoiceReminder(
        invoice_id=int(row['invoice_id']),
        workspace_id=str(row['workspace_id']),
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
    return value.isoformat() if isinstance(value, date) else str(value)


def _datetime_string(value: datetime | str) -> str:
    return value.isoformat(timespec='seconds') if isinstance(value, datetime) else str(value)


def _coerce_datetime(value: datetime | str) -> datetime:
    return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
