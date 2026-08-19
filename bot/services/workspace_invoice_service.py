from __future__ import annotations

from pathlib import Path
import sqlite3

from bot.services.db import managed_connection
from bot.services.invoice_service import (
    CreateInvoiceItemPayload,
    InvoiceCurrencySummary,
    InvoiceItemRecord,
    InvoicePeriodSummary,
    InvoiceRecord,
)
from bot.services.validation import validate_invoice_number_for_year
from bot.services.workspace_context import WorkspaceContext


class WorkspaceInvoiceSchemaRequired(RuntimeError):
    pass


class WorkspaceInvoiceService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def set_first_invoice_number(
        self,
        context: WorkspaceContext,
        *,
        issue_year: int,
        first_invoice_number: str,
    ) -> None:
        normalized = first_invoice_number.strip()
        if not validate_invoice_number_for_year(normalized, issue_year):
            raise ValueError('invalid_first_invoice_number')
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.execute(
                (
                    'INSERT INTO invoice_number_settings '
                    '(workspace_id, supplier_telegram_id, issue_year, '
                    'first_invoice_number, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(workspace_id, issue_year) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'first_invoice_number=excluded.first_invoice_number, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    context.workspace_id,
                    context.actor_telegram_id,
                    issue_year,
                    normalized,
                ),
            )
            connection.commit()

    def generate_next_invoice_number(
        self,
        context: WorkspaceContext,
        issue_year: int,
    ) -> str:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            return self._next_number(connection, context.workspace_id, issue_year)

    def create_invoice_with_items(
        self,
        context: WorkspaceContext,
        *,
        contact_id: int,
        issue_date: str,
        delivery_date: str,
        due_date: str,
        due_days: int,
        total_amount: float,
        currency: str,
        status: str,
        items: list[CreateInvoiceItemPayload],
        invoice_number: str | None = None,
    ) -> InvoiceRecord:
        if not items:
            raise RuntimeError('Invoice save failed: at least one item is required.')
        computed_total = round(sum(item.total_price for item in items), 2)
        if abs(computed_total - round(total_amount, 2)) > 0.01:
            raise RuntimeError(
                'Invoice save failed: invoice total does not match sum of item totals.'
            )
        issue_year = int(issue_date[:4])
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            contact = connection.execute(
                'SELECT id FROM contact WHERE id = ? AND workspace_id = ?',
                (contact_id, context.workspace_id),
            ).fetchone()
            if contact is None:
                raise ValueError('invoice_contact_workspace_mismatch')
            number = invoice_number or self._next_number(
                connection,
                context.workspace_id,
                issue_year,
            )
            try:
                cursor = connection.execute(
                    (
                        'INSERT INTO invoice '
                        '(workspace_id, supplier_telegram_id, contact_id, invoice_number, '
                        'issue_date, delivery_date, due_date, due_days, total_amount, '
                        'currency, status, pdf_path, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '
                        'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                    ),
                    (
                        context.workspace_id,
                        context.actor_telegram_id,
                        contact_id,
                        number,
                        issue_date,
                        delivery_date,
                        due_date,
                        due_days,
                        total_amount,
                        currency,
                        status,
                    ),
                )
                invoice_id = int(cursor.lastrowid)
                for item in items:
                    connection.execute(
                        (
                            'INSERT INTO invoice_item '
                            '(invoice_id, description_raw, description_normalized, '
                            'item_description_raw, quantity, unit, unit_price, total_price) '
                            'VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
                        ),
                        (
                            invoice_id,
                            item.description_raw,
                            item.description_normalized,
                            item.item_description_raw,
                            item.quantity,
                            item.unit,
                            item.unit_price,
                            item.total_price,
                        ),
                    )
                connection.commit()
            except sqlite3.IntegrityError as exc:
                connection.rollback()
                raise RuntimeError(
                    'Invoice save failed: invoice number already exists for this workspace.'
                ) from exc
        saved = self.get_by_id(context, invoice_id)
        if saved is None:
            raise RuntimeError('workspace_invoice_save_failed')
        return saved

    def get_by_number(
        self,
        context: WorkspaceContext,
        invoice_number: str,
    ) -> InvoiceRecord | None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f'{_INVOICE_SELECT} WHERE workspace_id = ? AND invoice_number = ?',
                (context.workspace_id, invoice_number),
            ).fetchone()
        return _row_to_invoice(row) if row is not None else None

    def list_invoices(
        self,
        context: WorkspaceContext,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[InvoiceRecord]:
        if isinstance(limit, bool) or limit < 1 or limit > 100:
            raise ValueError('invoice_read_limit_invalid')
        if isinstance(offset, bool) or offset < 0 or offset > 100_000:
            raise ValueError('invoice_read_offset_invalid')
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f'{_INVOICE_SELECT} WHERE workspace_id = ? '
                'ORDER BY issue_date DESC, id DESC LIMIT ? OFFSET ?',
                (context.workspace_id, limit, offset),
            ).fetchall()
        return [_row_to_invoice(row) for row in rows]

    def get_by_id(
        self,
        context: WorkspaceContext,
        invoice_id: int,
    ) -> InvoiceRecord | None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f'{_INVOICE_SELECT} WHERE workspace_id = ? AND id = ?',
                (context.workspace_id, invoice_id),
            ).fetchone()
        return _row_to_invoice(row) if row is not None else None

    def find_by_number_reference(
        self,
        context: WorkspaceContext,
        invoice_reference: str,
    ) -> list[InvoiceRecord]:
        normalized = ''.join(ch for ch in invoice_reference.strip() if ch.isdigit())
        if not normalized:
            return []
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f'{_INVOICE_SELECT} WHERE workspace_id = ? '
                'AND invoice_number LIKE ? ORDER BY invoice_number DESC',
                (context.workspace_id, f'%{normalized}'),
            ).fetchall()
        return [_row_to_invoice(row) for row in rows]

    def summarize_period(
        self,
        context: WorkspaceContext,
        *,
        start_date: str,
        end_date: str,
    ) -> InvoicePeriodSummary:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT UPPER(TRIM(currency)) AS currency, '
                    'COUNT(*) AS invoice_count, '
                    'COALESCE(SUM(total_amount), 0) AS total_amount '
                    'FROM invoice WHERE workspace_id = ? '
                    'AND issue_date >= ? AND issue_date <= ? '
                    'GROUP BY UPPER(TRIM(currency)) ORDER BY currency ASC'
                ),
                (context.workspace_id, start_date, end_date),
            ).fetchall()
        totals = tuple(
            InvoiceCurrencySummary(
                currency=str(row['currency'] or '').strip().upper() or 'UNKNOWN',
                invoice_count=int(row['invoice_count'] or 0),
                total_amount=round(float(row['total_amount'] or 0), 2),
            )
            for row in rows
        )
        return InvoicePeriodSummary(
            supplier_telegram_id=context.actor_telegram_id,
            start_date=start_date,
            end_date=end_date,
            invoice_count=sum(item.invoice_count for item in totals),
            totals_by_currency=totals,
        )

    def is_invoice_number_available(
        self,
        context: WorkspaceContext,
        *,
        invoice_number: str,
        exclude_invoice_id: int | None = None,
    ) -> bool:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            if exclude_invoice_id is None:
                row = connection.execute(
                    'SELECT id FROM invoice WHERE workspace_id = ? '
                    'AND invoice_number = ? LIMIT 1',
                    (context.workspace_id, invoice_number),
                ).fetchone()
            else:
                row = connection.execute(
                    'SELECT id FROM invoice WHERE workspace_id = ? '
                    'AND invoice_number = ? AND id != ? LIMIT 1',
                    (context.workspace_id, invoice_number, exclude_invoice_id),
                ).fetchone()
        return row is None

    def get_items(
        self,
        context: WorkspaceContext,
        invoice_id: int,
    ) -> list[InvoiceItemRecord]:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT ii.id, ii.invoice_id, ii.description_raw, '
                    'ii.description_normalized, ii.item_description_raw, '
                    'ii.quantity, ii.unit, ii.unit_price, ii.total_price '
                    'FROM invoice_item ii JOIN invoice i ON i.id = ii.invoice_id '
                    'WHERE ii.invoice_id = ? AND i.workspace_id = ? ORDER BY ii.id ASC'
                ),
                (invoice_id, context.workspace_id),
            ).fetchall()
        return [
            InvoiceItemRecord(
                id=int(row['id']),
                invoice_id=int(row['invoice_id']),
                description_raw=row['description_raw'],
                description_normalized=row['description_normalized'],
                item_description_raw=row['item_description_raw'],
                quantity=float(row['quantity']),
                unit=row['unit'],
                unit_price=float(row['unit_price']),
                total_price=float(row['total_price']),
            )
            for row in rows
        ]

    def update_item_service(
        self,
        context: WorkspaceContext,
        *,
        item_id: int,
        service_short_name: str,
        service_display_name: str,
    ) -> None:
        self._update_item(
            context,
            item_id=item_id,
            assignments='description_raw = ?, description_normalized = ?',
            values=(service_short_name, service_display_name),
        )

    def update_item_main_description(
        self,
        context: WorkspaceContext,
        *,
        item_id: int,
        description_raw: str,
        description_normalized: str,
    ) -> None:
        self._update_item(
            context,
            item_id=item_id,
            assignments='description_raw = ?, description_normalized = ?',
            values=(description_raw, description_normalized),
        )

    def update_item_description(
        self,
        context: WorkspaceContext,
        *,
        item_id: int,
        item_description_raw: str | None,
    ) -> None:
        self._update_item(
            context,
            item_id=item_id,
            assignments='item_description_raw = ?',
            values=(item_description_raw,),
        )

    def update_item_financials(
        self,
        context: WorkspaceContext,
        *,
        item_id: int,
        quantity: float,
        unit_price: float,
        total_price: float,
    ) -> None:
        self._update_item(
            context,
            item_id=item_id,
            assignments='quantity = ?, unit_price = ?, total_price = ?',
            values=(quantity, unit_price, total_price),
        )

    def update_invoice_total_amount(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            self._assert_invoice_owner(connection, context, invoice_id)
            total = connection.execute(
                'SELECT COALESCE(SUM(total_price), 0) FROM invoice_item '
                'WHERE invoice_id = ?',
                (invoice_id,),
            ).fetchone()
            connection.execute(
                'UPDATE invoice SET total_amount = ?, updated_at = CURRENT_TIMESTAMP '
                'WHERE id = ? AND workspace_id = ?',
                (round(float((total or [0])[0] or 0), 2), invoice_id, context.workspace_id),
            )
            connection.commit()

    def save_pdf_path(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        pdf_path: str,
    ) -> None:
        self._update_invoice(
            context,
            invoice_id=invoice_id,
            assignments='pdf_path = ?',
            values=(pdf_path,),
        )

    def update_invoice_number(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        invoice_number: str,
    ) -> bool:
        try:
            self._update_invoice(
                context,
                invoice_id=invoice_id,
                assignments='invoice_number = ?',
                values=(invoice_number,),
            )
            return True
        except sqlite3.IntegrityError:
            return False

    def update_invoice_issue_date(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        issue_date: str,
    ) -> None:
        self._update_invoice(
            context, invoice_id=invoice_id, assignments='issue_date = ?', values=(issue_date,)
        )

    def update_invoice_delivery_date(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        delivery_date: str,
    ) -> None:
        self._update_invoice(
            context,
            invoice_id=invoice_id,
            assignments='delivery_date = ?',
            values=(delivery_date,),
        )

    def update_invoice_due_date(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        due_date: str,
    ) -> None:
        self._update_invoice(
            context, invoice_id=invoice_id, assignments='due_date = ?', values=(due_date,)
        )

    def update_invoice_status(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        status: str,
    ) -> None:
        self._update_invoice(
            context, invoice_id=invoice_id, assignments='status = ?', values=(status,)
        )

    def delete_invoice_with_items(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            self._assert_invoice_owner(connection, context, invoice_id)
            connection.execute(
                'DELETE FROM invoice_item WHERE invoice_id = ?',
                (invoice_id,),
            )
            connection.execute(
                'DELETE FROM invoice_followup_state '
                'WHERE invoice_id = ? AND workspace_id = ?',
                (invoice_id, context.workspace_id),
            )
            connection.execute(
                'DELETE FROM invoice WHERE id = ? AND workspace_id = ?',
                (invoice_id, context.workspace_id),
            )
            connection.commit()

    def _update_item(
        self,
        context: WorkspaceContext,
        *,
        item_id: int,
        assignments: str,
        values: tuple,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            cursor = connection.execute(
                f'UPDATE invoice_item SET {assignments} WHERE id = ? '
                'AND EXISTS (SELECT 1 FROM invoice i '
                'WHERE i.id = invoice_item.invoice_id AND i.workspace_id = ?)',
                (*values, item_id, context.workspace_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise ValueError('invoice_item_not_found_for_workspace')
            connection.commit()

    def _update_invoice(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        assignments: str,
        values: tuple,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            try:
                cursor = connection.execute(
                    f'UPDATE invoice SET {assignments}, updated_at = CURRENT_TIMESTAMP '
                    'WHERE id = ? AND workspace_id = ?',
                    (*values, invoice_id, context.workspace_id),
                )
                if cursor.rowcount != 1:
                    connection.rollback()
                    raise ValueError('invoice_not_found_for_workspace')
                connection.commit()
            except sqlite3.IntegrityError:
                connection.rollback()
                raise

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
    def _next_number(
        connection: sqlite3.Connection,
        workspace_id: str,
        issue_year: int,
    ) -> str:
        prefix = str(issue_year)
        configured = connection.execute(
            (
                'SELECT first_invoice_number FROM invoice_number_settings '
                'WHERE workspace_id = ? AND issue_year = ?'
            ),
            (workspace_id, issue_year),
        ).fetchone()
        configured_first = str(configured[0]) if configured is not None else None
        row = connection.execute(
            (
                'SELECT invoice_number FROM invoice '
                'WHERE workspace_id = ? AND invoice_number LIKE ? '
                'ORDER BY invoice_number DESC LIMIT 1'
            ),
            (workspace_id, f'{prefix}%'),
        ).fetchone()
        if row is None:
            return configured_first or f'{prefix}0001'
        next_number = f'{prefix}{int(str(row[0])[4:]) + 1:04d}'
        return max(next_number, configured_first) if configured_first else next_number

    @staticmethod
    def _require_schema(connection: sqlite3.Connection) -> None:
        for table in ('invoice', 'invoice_number_settings', 'contact'):
            columns = {
                row[1] for row in connection.execute(f'PRAGMA table_info({table})')
            }
            if 'workspace_id' not in columns:
                raise WorkspaceInvoiceSchemaRequired(
                    f'workspace_{table}_schema_migration_required'
                )


_INVOICE_SELECT = (
    'SELECT id, workspace_id, supplier_telegram_id, contact_id, invoice_number, '
    'issue_date, delivery_date, due_date, due_days, total_amount, currency, '
    'status, pdf_path FROM invoice'
)


def _row_to_invoice(row: sqlite3.Row) -> InvoiceRecord:
    return InvoiceRecord(
        id=int(row['id']),
        workspace_id=row['workspace_id'],
        supplier_telegram_id=int(row['supplier_telegram_id']),
        contact_id=int(row['contact_id']),
        invoice_number=row['invoice_number'],
        issue_date=row['issue_date'],
        delivery_date=row['delivery_date'],
        due_date=row['due_date'],
        due_days=int(row['due_days']),
        total_amount=float(row['total_amount']),
        currency=row['currency'],
        status=row['status'],
        pdf_path=row['pdf_path'],
    )
