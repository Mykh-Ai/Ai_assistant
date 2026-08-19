from __future__ import annotations

from pathlib import Path
import sqlite3

from bot.services.db import managed_connection
from bot.services.invoice_service import InvoiceRecord
from bot.services.workspace_context import WorkspaceContext


class WorkspaceInvoicePdfStorageError(RuntimeError):
    pass


MAX_API_INVOICE_PDF_BYTES = 25 * 1024 * 1024


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

    def resolve_existing_read_path(
        self,
        context: WorkspaceContext,
        invoice: InvoiceRecord,
    ) -> Path:
        """Resolve one persisted invoice PDF pointer for bounded read-only use."""

        self._assert_invoice_context(context, invoice)
        pointer = str(invoice.pdf_path or '').strip()
        if not pointer or len(pointer) > 2048 or '\x00' in pointer:
            raise WorkspaceInvoicePdfStorageError('invoice_pdf_unavailable')
        invoice_root = (self._storage_dir / 'invoices').resolve()
        workspace_root = (
            invoice_root
            / _safe_path_segment(context.storage_key, field='storage_key')
        ).resolve()
        expected_filename = (
            _safe_path_segment(invoice.invoice_number, field='invoice_number')
            + '.pdf'
        )
        allowed_parents = {workspace_root}
        legacy_actor_root = invoice_root / str(invoice.supplier_telegram_id)
        if self._legacy_actor_root_is_unambiguous(context, invoice):
            allowed_parents.add(legacy_actor_root.resolve())
        raw_path = Path(pointer)
        candidates = (
            (raw_path,)
            if raw_path.is_absolute()
            else (
                Path.cwd() / raw_path,
                self._storage_dir / raw_path,
                self._storage_dir.parent / raw_path,
            )
        )
        for candidate in candidates:
            try:
                resolved = candidate.resolve(strict=True)
                resolved.relative_to(invoice_root)
            except (OSError, RuntimeError, ValueError):
                continue
            if (
                resolved.parent not in allowed_parents
                or resolved.name != expected_filename
                or resolved.suffix.casefold() != '.pdf'
                or not resolved.is_file()
            ):
                continue
            size = resolved.stat().st_size
            if size < 5 or size > MAX_API_INVOICE_PDF_BYTES:
                continue
            try:
                with resolved.open('rb') as handle:
                    if handle.read(5) != b'%PDF-':
                        continue
            except OSError:
                continue
            return resolved
        raise WorkspaceInvoicePdfStorageError('invoice_pdf_unavailable')

    def _legacy_actor_root_is_unambiguous(
        self,
        context: WorkspaceContext,
        invoice: InvoiceRecord,
    ) -> bool:
        """Permit the old numeric owner root only for one provable workspace."""

        if invoice.supplier_telegram_id <= 0:
            return False
        with managed_connection(self._db_path) as connection:
            rows = connection.execute(
                'SELECT workspace_id FROM supplier WHERE telegram_id = ? '
                'UNION SELECT workspace_id FROM invoice '
                'WHERE supplier_telegram_id = ?',
                (
                    invoice.supplier_telegram_id,
                    invoice.supplier_telegram_id,
                ),
            ).fetchall()
        workspace_ids = {
            str(row[0]) if row[0] is not None else None for row in rows
        }
        return workspace_ids == {context.workspace_id}

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
