from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from bot.services.db import managed_connection


@dataclass
class InvoiceRecord:
    id: int
    supplier_telegram_id: int
    contact_id: int
    invoice_number: str
    issue_date: str
    delivery_date: str
    due_date: str
    due_days: int
    total_amount: float
    currency: str
    status: str
    pdf_path: str | None


@dataclass
class InvoiceItemRecord:
    id: int
    invoice_id: int
    description_raw: str
    description_normalized: str | None
    item_description_raw: str | None
    quantity: float
    unit: str | None
    unit_price: float
    total_price: float


@dataclass
class CreateInvoicePayload:
    supplier_telegram_id: int
    contact_id: int
    issue_date: str
    delivery_date: str
    due_date: str
    due_days: int
    total_amount: float
    currency: str
    status: str
    item_description_raw: str
    item_description_normalized: str | None
    item_quantity: float
    item_unit: str | None
    item_unit_price: float
    item_total_price: float


@dataclass
class CreateInvoiceItemPayload:
    description_raw: str
    description_normalized: str | None
    item_description_raw: str | None
    quantity: float
    unit: str | None
    unit_price: float
    total_price: float


class InvoiceService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def generate_next_invoice_number(self, issue_year: int) -> str:
        with managed_connection(self._db_path) as connection:
            return self._generate_next_invoice_number(connection, issue_year)


    @staticmethod
    def _generate_next_invoice_number(connection: sqlite3.Connection, issue_year: int) -> str:
        prefix = f'{issue_year}'
        row = connection.execute(
            (
                'SELECT invoice_number FROM invoice '
                'WHERE invoice_number LIKE ? '
                'ORDER BY invoice_number DESC '
                'LIMIT 1'
            ),
            (f'{prefix}%',),
        ).fetchone()

        if row is None:
            return f'{prefix}0001'

        last_num = int(str(row[0])[4:])
        return f'{prefix}{last_num + 1:04d}'

    def create_invoice_with_one_item(self, payload: CreateInvoicePayload) -> int:
        return self.create_invoice_with_items(
            supplier_telegram_id=payload.supplier_telegram_id,
            contact_id=payload.contact_id,
            issue_date=payload.issue_date,
            delivery_date=payload.delivery_date,
            due_date=payload.due_date,
            due_days=payload.due_days,
            total_amount=payload.total_amount,
            currency=payload.currency,
            status=payload.status,
            items=[
                CreateInvoiceItemPayload(
                    description_raw=payload.item_description_raw,
                    description_normalized=payload.item_description_normalized,
                    item_description_raw=None,
                    quantity=payload.item_quantity,
                    unit=payload.item_unit,
                    unit_price=payload.item_unit_price,
                    total_price=payload.item_total_price,
                )
            ],
        )

    def create_invoice_with_items(
        self,
        *,
        supplier_telegram_id: int,
        contact_id: int,
        issue_date: str,
        delivery_date: str,
        due_date: str,
        due_days: int,
        total_amount: float,
        currency: str,
        status: str,
        items: list[CreateInvoiceItemPayload],
    ) -> int:
        if not items:
            raise RuntimeError('Invoice save failed: at least one item is required.')
        computed_total = round(sum(item.total_price for item in items), 2)
        if abs(computed_total - round(total_amount, 2)) > 0.01:
            raise RuntimeError('Invoice save failed: invoice total does not match sum of item totals.')

        issue_year = int(issue_date[:4])

        with managed_connection(self._db_path) as connection:
            invoice_number = self._generate_next_invoice_number(connection, issue_year)
            cursor = connection.execute(
                (
                    'INSERT INTO invoice '
                    '(supplier_telegram_id, contact_id, invoice_number, issue_date, delivery_date, due_date, '
                    'due_days, total_amount, currency, status, pdf_path, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                ),
                (
                    supplier_telegram_id,
                    contact_id,
                    invoice_number,
                    issue_date,
                    delivery_date,
                    due_date,
                    due_days,
                    total_amount,
                    currency,
                    status,
                ),
            )
            invoice_id = cursor.lastrowid
            if invoice_id is None:
                raise RuntimeError('Invoice save failed: missing invoice id after insert.')

            for item in items:
                connection.execute(
                    (
                        'INSERT INTO invoice_item '
                        '(invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price) '
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

        return int(invoice_id)

    def get_invoice_by_id(self, invoice_id: int) -> InvoiceRecord | None:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, contact_id, invoice_number, issue_date, delivery_date, '
                    'due_date, due_days, total_amount, currency, status, pdf_path '
                    'FROM invoice WHERE id = ?'
                ),
                (invoice_id,),
            ).fetchone()

        if row is None:
            return None

        return InvoiceRecord(
            id=row['id'],
            supplier_telegram_id=row['supplier_telegram_id'],
            contact_id=row['contact_id'],
            invoice_number=row['invoice_number'],
            issue_date=row['issue_date'],
            delivery_date=row['delivery_date'],
            due_date=row['due_date'],
            due_days=row['due_days'],
            total_amount=row['total_amount'],
            currency=row['currency'],
            status=row['status'],
            pdf_path=row['pdf_path'],
        )

    def get_invoice_by_number(self, invoice_number: str) -> InvoiceRecord | None:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, contact_id, invoice_number, issue_date, delivery_date, '
                    'due_date, due_days, total_amount, currency, status, pdf_path '
                    'FROM invoice WHERE invoice_number = ?'
                ),
                (invoice_number,),
            ).fetchone()

        if row is None:
            return None

        return InvoiceRecord(
            id=row['id'],
            supplier_telegram_id=row['supplier_telegram_id'],
            contact_id=row['contact_id'],
            invoice_number=row['invoice_number'],
            issue_date=row['issue_date'],
            delivery_date=row['delivery_date'],
            due_date=row['due_date'],
            due_days=row['due_days'],
            total_amount=row['total_amount'],
            currency=row['currency'],
            status=row['status'],
            pdf_path=row['pdf_path'],
        )

    def is_invoice_number_available(self, *, invoice_number: str, exclude_invoice_id: int | None = None) -> bool:
        with managed_connection(self._db_path) as connection:
            if exclude_invoice_id is None:
                row = connection.execute(
                    'SELECT id FROM invoice WHERE invoice_number = ? LIMIT 1',
                    (invoice_number,),
                ).fetchone()
            else:
                row = connection.execute(
                    'SELECT id FROM invoice WHERE invoice_number = ? AND id != ? LIMIT 1',
                    (invoice_number, exclude_invoice_id),
                ).fetchone()
        return row is None

    def get_items_by_invoice_id(self, invoice_id: int) -> list[InvoiceItemRecord]:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT id, invoice_id, description_raw, description_normalized, item_description_raw, quantity, unit, unit_price, total_price '
                    'FROM invoice_item WHERE invoice_id = ? ORDER BY id ASC'
                ),
                (invoice_id,),
            ).fetchall()

        return [
            InvoiceItemRecord(
                id=row['id'],
                invoice_id=row['invoice_id'],
                description_raw=row['description_raw'],
                description_normalized=row['description_normalized'],
                item_description_raw=row['item_description_raw'],
                quantity=row['quantity'],
                unit=row['unit'],
                unit_price=row['unit_price'],
                total_price=row['total_price'],
            )
            for row in rows
        ]

    def update_item_service(
        self,
        *,
        item_id: int,
        service_short_name: str,
        service_display_name: str,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'UPDATE invoice_item '
                    'SET description_raw = ?, description_normalized = ? '
                    'WHERE id = ?'
                ),
                (service_short_name, service_display_name, item_id),
            )
            connection.commit()

    def update_item_main_description(
        self,
        *,
        item_id: int,
        description_raw: str,
        description_normalized: str,
    ) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'UPDATE invoice_item '
                    'SET description_raw = ?, description_normalized = ? '
                    'WHERE id = ?'
                ),
                (description_raw, description_normalized, item_id),
            )
            connection.commit()

    def update_item_description(self, *, item_id: int, item_description_raw: str | None) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                'UPDATE invoice_item SET item_description_raw = ? WHERE id = ?',
                (item_description_raw, item_id),
            )
            connection.commit()

    def save_pdf_path(self, invoice_id: int, pdf_path: str) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                'UPDATE invoice SET pdf_path = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (pdf_path, invoice_id),
            )
            connection.commit()

    def update_invoice_number(self, *, invoice_id: int, invoice_number: str) -> bool:
        with managed_connection(self._db_path) as connection:
            try:
                connection.execute(
                    'UPDATE invoice SET invoice_number = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                    (invoice_number, invoice_id),
                )
                connection.commit()
                return True
            except sqlite3.IntegrityError:
                connection.rollback()
                return False

    def update_invoice_issue_date(self, *, invoice_id: int, issue_date: str) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                'UPDATE invoice SET issue_date = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (issue_date, invoice_id),
            )
            connection.commit()

    def update_invoice_status(self, invoice_id: int, status: str) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                'UPDATE invoice SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?',
                (status, invoice_id),
            )
            connection.commit()

    def delete_invoice_with_items(self, invoice_id: int) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute('DELETE FROM invoice_item WHERE invoice_id = ?', (invoice_id,))
            connection.execute('DELETE FROM invoice WHERE id = ?', (invoice_id,))
            connection.commit()
