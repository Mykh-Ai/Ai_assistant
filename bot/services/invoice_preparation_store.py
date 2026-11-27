"""Workspace- or supplier-scoped persistence for invoice preparation."""

from decimal import Decimal
import hashlib
import json
import logging
import os
from pathlib import Path
from shutil import copyfile
import sqlite3

from bot.services.db import managed_connection
from bot.services.invoice_preparation import invalidate_calculation, money


logger = logging.getLogger(__name__)
_PDF_REVISION_FIELDS = (
    'invoice_number', 'pdf_path', 'issue_date', 'delivery_date', 'due_date', 'due_days',
    'total_amount', 'calculation_bundle_json',
)


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


def _file_digest(path: Path) -> str | None:
    if path.is_symlink():
        raise ValueError('Unexpected symlink in invoice edit storage')
    try:
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()
    except FileNotFoundError:
        return None


def _sync_path(path: Path) -> None:
    if os.name == 'nt' and path.is_dir():
        return  # Windows does not expose directory fsync through os.open.
    descriptor = os.open(path, os.O_RDONLY if os.name != 'nt' else os.O_RDWR | os.O_BINARY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _invoice_revision(connection: sqlite3.Connection, invoice_id: int) -> str:
    row = connection.execute(
        f'SELECT {", ".join(_PDF_REVISION_FIELDS)} FROM invoice WHERE id = ?', (invoice_id,),
    ).fetchone()
    items = connection.execute(
        'SELECT * FROM invoice_item WHERE invoice_id = ? ORDER BY id', (invoice_id,),
    ).fetchall()
    return hashlib.sha256(json.dumps([tuple(row), [tuple(item) for item in items]]).encode()).hexdigest()


def _journal_path(target: Path) -> Path:
    return target.with_name(f'.invoice-edit-{target.name}')


def _remove_journal(journal: Path) -> None:
    (journal / 'pending.json').unlink(missing_ok=True)
    _sync_path(journal)
    for name in ('pending.tmp', 'previous.pdf', 'next.pdf'):
        (journal / name).unlink(missing_ok=True)
    journal.rmdir()
    _sync_path(journal.parent)


def _recover_edit(connection: sqlite3.Connection, target: Path) -> None:
    """Reconcile an edit under the same SQLite write lock used to publish it."""
    journal = _journal_path(target)
    if journal.is_symlink():
        raise ValueError('Unexpected invoice edit journal symlink')
    if not journal.exists():
        return
    marker = journal / 'pending.json'
    if marker.is_symlink():
        raise ValueError('Unexpected invoice edit marker symlink')
    if not marker.exists():
        # A replacement is only allowed after publication of the marker.
        _remove_journal(journal)
        return
    record = json.loads(marker.read_text(encoding='utf-8'))
    invoice_id = record['invoice_id']
    invoice = connection.execute('SELECT * FROM invoice WHERE id = ?', (invoice_id,)).fetchone()
    if invoice is None:
        raise ValueError('Invoice edit journal has no invoice')
    storage_key = str(invoice['supplier_telegram_id'])
    if 'workspace_id' in invoice.keys() and invoice['workspace_id'] is not None:
        workspace = connection.execute(
            'SELECT storage_key FROM workspace WHERE workspace_id = ?', (invoice['workspace_id'],),
        ).fetchone()
        storage_key = workspace[0] if workspace else None
    if target.parent.name != storage_key or target.name != f"{invoice['invoice_number']}.pdf":
        raise ValueError('Invoice edit journal is outside the invoice scope')

    revision = _invoice_revision(connection, invoice_id)
    digest = _file_digest(target)
    if revision == record['after_revision'] and digest == record['after_pdf']:
        pass  # The committed SQLite edit owns the installed PDF.
    elif revision == record['before_revision']:
        if digest != record['before_pdf']:
            if digest != record['after_pdf']:
                raise ValueError('Invoice PDF changed outside its pending edit')
            backup = journal / 'previous.pdf'
            if record['before_pdf'] is None:
                target.unlink()
            elif _file_digest(backup) == record['before_pdf']:
                os.replace(backup, target)
            else:
                raise ValueError('Invoice edit backup failed verification')
            _sync_path(target.parent)
    else:
        raise ValueError('Pending invoice edit does not match SQLite and PDF')
    _remove_journal(journal)


def recover_pending_invoice_edits(db_path: Path, storage_dir: Path) -> None:
    root = (storage_dir / 'invoices').resolve()
    for journal in root.glob('*/.invoice-edit-*.pdf'):
        if journal.parent.is_symlink():
            raise ValueError('Unexpected symlink at invoice edit journal owner')
        target = journal.with_name(journal.name.removeprefix('.invoice-edit-'))
        with managed_connection(db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            _recover_edit(connection, target)


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

    def change_contact_rate(self, contact_id: int, *, expected: str | None, replacement: str) -> bool:
        with managed_connection(self.db_path) as connection:
            where, owner = self.scope(connection, 'contact')
            result = connection.execute(
                f'UPDATE contact SET default_hourly_rate_eur = ?, updated_at = CURRENT_TIMESTAMP '
                f'WHERE id = ? AND {where} AND default_hourly_rate_eur IS ?',
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
        names = {str(normalized or '').strip() or str(raw or '').strip() for normalized, raw in items}
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
            _recover_edit(connection, pdf_path)
            before_revision = _invoice_revision(connection, invoice_id)

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
            journal = _journal_path(pdf_path)
            journal.mkdir()
            staged_pdf = journal / 'next.pdf'
            try:
                render_pdf(revised, items, staged_pdf)
                _sync_path(staged_pdf)
                before_pdf = _file_digest(pdf_path)
                if before_pdf is not None:
                    backup = journal / 'previous.pdf'
                    copyfile(pdf_path, backup)
                    _sync_path(backup)
                marker = journal / 'pending.tmp'
                marker.write_text(json.dumps({
                    'invoice_id': invoice_id,
                    'before_revision': before_revision,
                    'after_revision': _invoice_revision(connection, invoice_id),
                    'before_pdf': before_pdf,
                    'after_pdf': _file_digest(staged_pdf),
                }), encoding='utf-8')
                _sync_path(marker)
                os.replace(marker, journal / 'pending.json')
                _sync_path(journal)
                _sync_path(pdf_path.parent)
                os.replace(staged_pdf, pdf_path)
                _sync_path(pdf_path.parent)
                connection.commit()
            except Exception:
                connection.rollback()
                connection.execute('BEGIN IMMEDIATE')
                _recover_edit(connection, pdf_path)
                raise
            try:
                connection.execute('BEGIN IMMEDIATE')
                _recover_edit(connection, pdf_path)
            except (OSError, sqlite3.Error, ValueError):
                logger.exception('Committed invoice edit needs journal reconciliation for invoice %s', invoice_id)
            return True
