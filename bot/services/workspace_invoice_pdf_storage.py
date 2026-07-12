from __future__ import annotations

from pathlib import Path
import sqlite3

from bot.services.db import managed_connection
from bot.services.invoice_service import InvoiceRecord
from bot.services.workspace_context import WorkspaceContext


class WorkspaceInvoicePdfStorageError(RuntimeError):
    pass


def workspace_invoice_pdf_path(
    storage_dir: Path,
    context: WorkspaceContext,
    invoice_number: str,
) -> Path:
    storage_key = _safe_path_segment(context.storage_key, field='storage_key')
    filename = _safe_path_segment(invoice_number, field='invoice_number')
    return storage_dir / 'invoices' / storage_key / f'{filename}.pdf'


class WorkspaceInvoicePdfStorageService:
    def __init__(self, db_path: Path, storage_dir: Path) -> None:
        self._db_path = db_path
        self._storage_dir = storage_dir

    def target_path(
        self,
        context: WorkspaceContext,
        *,
        invoice_number: str,
    ) -> Path:
        return workspace_invoice_pdf_path(self._storage_dir, context, invoice_number)

    def resolve_path(
        self,
        context: WorkspaceContext,
        invoice: InvoiceRecord,
    ) -> Path:
        self._assert_invoice_context(context, invoice)
        if invoice.pdf_path and str(invoice.pdf_path).strip():
            return Path(invoice.pdf_path)
        return self.target_path(context, invoice_number=invoice.invoice_number)

    def persist_path(
        self,
        context: WorkspaceContext,
        *,
        invoice_id: int,
        pdf_path: Path,
    ) -> None:
        expected_root = (
            self._storage_dir
            / 'invoices'
            / _safe_path_segment(context.storage_key, field='storage_key')
        ).resolve()
        resolved_path = pdf_path.resolve()
        if resolved_path.parent != expected_root:
            raise WorkspaceInvoicePdfStorageError('invoice_pdf_path_outside_workspace')
        with managed_connection(self._db_path) as connection:
            self._require_schema(connection)
            cursor = connection.execute(
                'UPDATE invoice SET pdf_path = ?, updated_at = CURRENT_TIMESTAMP '
                'WHERE id = ? AND workspace_id = ?',
                (str(pdf_path), invoice_id, context.workspace_id),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise WorkspaceInvoicePdfStorageError('invoice_not_found_for_workspace')
            connection.commit()

    @staticmethod
    def _assert_invoice_context(
        context: WorkspaceContext,
        invoice: InvoiceRecord,
    ) -> None:
        if invoice.workspace_id != context.workspace_id:
            raise WorkspaceInvoicePdfStorageError('invoice_workspace_mismatch')

    @staticmethod
    def _require_schema(connection: sqlite3.Connection) -> None:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(invoice)')}
        if 'workspace_id' not in columns:
            raise WorkspaceInvoicePdfStorageError(
                'workspace_invoice_schema_migration_required'
            )


def _safe_path_segment(value: str, *, field: str) -> str:
    normalized = str(value).strip()
    if (
        not normalized
        or normalized in {'.', '..'}
        or '/' in normalized
        or '\\' in normalized
        or Path(normalized).name != normalized
    ):
        raise WorkspaceInvoicePdfStorageError(f'invalid_{field}')
    return normalized
