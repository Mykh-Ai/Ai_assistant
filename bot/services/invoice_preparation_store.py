"""Workspace- or supplier-scoped persistence for invoice preparation."""

from decimal import Decimal
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from bot.services.db import managed_connection
from bot.services.invoice_preparation import invalidate_calculation, money


def table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in connection.execute(f'PRAGMA table_info({table})')}


def attach_calculation(connection, *, invoice_id: int, bundle: dict | None, total_amount) -> None:
    if bundle is None:
        return
    amount_key = {'valid': 'net', 'invalidated': 'effective_invoice_total'}[bundle['status']]
    if Decimal(bundle[amount_key]) != money(Decimal(str(total_amount))):
        raise ValueError('invoice_calculation_total_mismatch')
    connection.execute(
        'UPDATE invoice SET calculation_bundle_json = ? WHERE id = ?',
        (json.dumps({**bundle, 'invoice_id': invoice_id}, ensure_ascii=False), invoice_id),
    )


class InvoicePreparationStore:
    def __init__(self, db_path: Path, *, actor_id: int, workspace_id: str | None) -> None:
        self.db_path = db_path
        self.actor_id = actor_id
        self.workspace_id = workspace_id

    def scope(self, connection: sqlite3.Connection, table: str) -> tuple[str, object]:
        if self.workspace_id is not None:
            return 'workspace_id = ?', self.workspace_id
        where = 'supplier_telegram_id = ?'
        if 'workspace_id' in table_columns(connection, table):
            where += ' AND workspace_id IS NULL'
        return where, self.actor_id

    def schema_ready(self) -> bool:
        with managed_connection(self.db_path) as connection:
            return (
                'default_hourly_rate_eur' in table_columns(connection, 'contact')
                and 'calculation_bundle_json' in table_columns(connection, 'invoice')
            )

    def contact_rate(self, contact_id: int) -> str | None:
        with managed_connection(self.db_path) as connection:
            if 'default_hourly_rate_eur' not in table_columns(connection, 'contact'):
                return None
            where, owner = self.scope(connection, 'contact')
            row = connection.execute(
                f'SELECT default_hourly_rate_eur FROM contact WHERE id = ? AND {where}',
                (contact_id, owner),
            ).fetchone()
        return row[0] if row else None

    def change_contact_rate(self, contact_id: int, *, expected: str, replacement: str) -> bool:
        with managed_connection(self.db_path) as connection:
            where, owner = self.scope(connection, 'contact')
            result = connection.execute(
                f'UPDATE contact SET default_hourly_rate_eur = ?, updated_at = CURRENT_TIMESTAMP '
                f'WHERE id = ? AND {where} AND default_hourly_rate_eur = ?',
                (replacement, contact_id, owner, expected),
            )
            connection.commit()
            return result.rowcount == 1

    def latest_contact_service(self, contact_id: int) -> tuple[str, str] | None:
        with managed_connection(self.db_path) as connection:
            where, owner = self.scope(connection, 'invoice')
            row = connection.execute(
                f'SELECT id, invoice_number FROM invoice WHERE contact_id = ? AND {where} '
                'ORDER BY issue_date DESC, id DESC LIMIT 1',
                (contact_id, owner),
            ).fetchone()
            if row is None:
                return None
            items = connection.execute(
                'SELECT description_normalized, description_raw FROM invoice_item WHERE invoice_id = ?',
                (row[0],),
            ).fetchall()
        names = {str(item[0] or item[1] or '').strip() for item in items}
        if len(names) != 1 or '' in names:
            return None
        return names.pop(), str(row[1])

    def overlaps(self, contact_id: int, weeks: list[dict]) -> list[str]:
        expected = {(week['iso_year'], week['kw']) for week in weeks}
        if not expected:
            return []
        with managed_connection(self.db_path) as connection:
            where, owner = self.scope(connection, 'invoice')
            rows = connection.execute(
                f'SELECT invoice_number, calculation_bundle_json FROM invoice '
                f'WHERE contact_id = ? AND {where} AND calculation_bundle_json IS NOT NULL '
                'ORDER BY issue_date DESC, id DESC',
                (contact_id, owner),
            ).fetchall()
        conflicts = []
        for number, raw in rows:
            bundle = json.loads(raw)
            if bundle.get('schema_version') != 1 or bundle.get('status') != 'valid':
                continue
            known = {(week['iso_year'], week['kw']) for week in bundle.get('iso_weeks', ())}
            if expected & known:
                conflicts.append(str(number))
        return conflicts

    def edit_with_calculation(
        self, invoice_id: int, *, pdf_path: Path, render_pdf,
        invoice_changes: dict | None = None, item_id: int | None = None, item_changes: dict | None = None,
    ) -> bool | None:
        """Return None for legacy invoices, otherwise whether the stored invoice changed."""
        invoice_changes = invoice_changes or {}
        item_changes = item_changes or {}
        if invoice_changes.keys() - {'issue_date', 'delivery_date', 'due_date', 'due_days'}:
            raise ValueError('Invalid invoice edit columns')
        if item_changes.keys() - {'quantity', 'unit_price', 'total_price', 'description_raw', 'description_normalized'}:
            raise ValueError('Invalid invoice item edit columns')
        with managed_connection(self.db_path) as connection:
            if 'calculation_bundle_json' not in table_columns(connection, 'invoice'):
                return None
            connection.row_factory = sqlite3.Row
            where, owner = self.scope(connection, 'invoice')
            connection.execute('BEGIN IMMEDIATE')
            invoice = connection.execute(
                f'SELECT * FROM invoice WHERE id = ? AND {where}', (invoice_id, owner),
            ).fetchone()
            if invoice is None:
                raise ValueError('Invoice is no longer in scope')
            if invoice['calculation_bundle_json'] is None:
                return None
            if pdf_path.name != f"{invoice['invoice_number']}.pdf":
                raise ValueError('Invoice number changed concurrently')

            changed = any(invoice[field] != value for field, value in invoice_changes.items())
            if item_changes:
                item = connection.execute(
                    'SELECT * FROM invoice_item WHERE id = ? AND invoice_id = ?', (item_id, invoice_id),
                ).fetchone()
                if item is None:
                    raise ValueError('Invoice item is no longer in scope')
                if any(item[field] != value for field, value in item_changes.items()):
                    assignments = ', '.join(f'{field} = ?' for field in item_changes)
                    connection.execute(
                        f'UPDATE invoice_item SET {assignments} WHERE id = ? AND invoice_id = ?',
                        (*item_changes.values(), item_id, invoice_id),
                    )
                    changed = True
            if not changed:
                return False

            items = connection.execute(
                'SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY id', (invoice_id,),
            ).fetchall()
            total = money(sum((Decimal(str(item['total_price'])) for item in items), Decimal(0)))
            revised = {**dict(invoice), **invoice_changes, 'total_amount': float(total)}
            bundle = invalidate_calculation(json.loads(invoice['calculation_bundle_json']), effective_total=total)
            updates = {
                **invoice_changes, 'total_amount': float(total), 'pdf_path': str(pdf_path),
                'calculation_bundle_json': json.dumps(bundle, ensure_ascii=False),
            }
            assignments = ', '.join(f'{field} = ?' for field in updates)
            connection.execute(
                f'UPDATE invoice SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND {where}',
                (*updates.values(), invoice_id, owner),
            )
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            with TemporaryDirectory(prefix='.invoice-edit-', dir=pdf_path.parent) as temp_dir:
                staged_pdf = Path(temp_dir) / pdf_path.name
                previous_pdf = Path(temp_dir) / 'previous.pdf'
                render_pdf(revised, items, staged_pdf)
                if pdf_path.exists():
                    os.link(pdf_path, previous_pdf)
                installed = False
                try:
                    os.replace(staged_pdf, pdf_path)
                    installed = True
                    connection.commit()
                except Exception:
                    if installed and previous_pdf.exists():
                        os.replace(previous_pdf, pdf_path)
                    elif installed:
                        pdf_path.unlink(missing_ok=True)
                    raise
            return True
