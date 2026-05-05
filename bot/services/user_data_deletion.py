from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import sqlite3

from bot.services.access_control import mark_deleted_database_in_connection
from bot.services.accounting_document_storage import workspace_key_for_supplier
from bot.services.db import managed_connection


@dataclass(frozen=True)
class UserDataDeletionResult:
    telegram_id: int
    supplier_deleted: bool
    contacts_deleted: int
    invoices_deleted: int
    invoice_items_deleted: int
    service_aliases_deleted: int
    invoice_number_settings_deleted: int
    confirmed_aliases_deleted: int
    filesystem_paths_deleted: tuple[str, ...]
    filesystem_paths_skipped: tuple[str, ...]
    filesystem_errors: tuple[str, ...]


class UserDataDeletionService:
    def __init__(self, db_path: Path, storage_dir: Path) -> None:
        self._db_path = db_path
        self._storage_dir = storage_dir

    def delete_user_database(self, *, telegram_id: int) -> UserDataDeletionResult:
        if telegram_id <= 0:
            raise ValueError('telegram_id_required')

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            supplier_row = connection.execute(
                'SELECT id FROM supplier WHERE telegram_id = ?',
                (telegram_id,),
            ).fetchone()
            supplier_id = int(supplier_row['id']) if supplier_row is not None else None
            invoice_ids = [
                int(row['id'])
                for row in connection.execute(
                    'SELECT id FROM invoice WHERE supplier_telegram_id = ?',
                    (telegram_id,),
                ).fetchall()
            ]
            contract_paths = [
                str(row['contract_path'])
                for row in connection.execute(
                    (
                        'SELECT contract_path FROM contact '
                        'WHERE supplier_telegram_id = ? '
                        "AND contract_path IS NOT NULL AND trim(contract_path) != ''"
                    ),
                    (telegram_id,),
                ).fetchall()
            ]

            invoice_items_deleted = _delete_invoice_items(connection, invoice_ids)
            invoices_deleted = connection.execute(
                'DELETE FROM invoice WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            contacts_deleted = connection.execute(
                'DELETE FROM contact WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            if supplier_id is None:
                service_aliases_deleted = 0
            else:
                service_aliases_deleted = connection.execute(
                    'DELETE FROM supplier_service_alias WHERE supplier_id = ?',
                    (supplier_id,),
                ).rowcount
            invoice_number_settings_deleted = connection.execute(
                'DELETE FROM invoice_number_settings WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            confirmed_aliases_deleted = connection.execute(
                'DELETE FROM confirmed_semantic_alias WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            supplier_deleted = (
                connection.execute('DELETE FROM supplier WHERE telegram_id = ?', (telegram_id,)).rowcount > 0
            )

            mark_deleted_database_in_connection(connection, telegram_id=telegram_id)
            connection.commit()

        deleted, skipped, errors = self._delete_scoped_filesystem_paths(
            telegram_id=telegram_id,
            contract_paths=contract_paths,
        )
        return UserDataDeletionResult(
            telegram_id=telegram_id,
            supplier_deleted=supplier_deleted,
            contacts_deleted=contacts_deleted,
            invoices_deleted=invoices_deleted,
            invoice_items_deleted=invoice_items_deleted,
            service_aliases_deleted=service_aliases_deleted,
            invoice_number_settings_deleted=invoice_number_settings_deleted,
            confirmed_aliases_deleted=confirmed_aliases_deleted,
            filesystem_paths_deleted=tuple(deleted),
            filesystem_paths_skipped=tuple(skipped),
            filesystem_errors=tuple(errors),
        )

    def _delete_scoped_filesystem_paths(
        self,
        *,
        telegram_id: int,
        contract_paths: list[str],
    ) -> tuple[list[str], list[str], list[str]]:
        deleted: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        scoped_dirs = [
            self._storage_dir / 'invoices' / str(telegram_id),
            self._storage_dir / 'workspaces' / workspace_key_for_supplier(telegram_id),
            self._storage_dir / 'uploads' / 'accounting_intake' / str(telegram_id),
            self._storage_dir / 'uploads' / 'attachment_intake' / str(telegram_id),
        ]
        for directory in scoped_dirs:
            self._delete_directory(directory, deleted=deleted, skipped=skipped, errors=errors)

        for contract_path in contract_paths:
            self._delete_contract_file(contract_path, deleted=deleted, skipped=skipped, errors=errors)
        return deleted, skipped, errors

    def _delete_directory(
        self,
        directory: Path,
        *,
        deleted: list[str],
        skipped: list[str],
        errors: list[str],
    ) -> None:
        try:
            resolved = directory.resolve()
            storage_root = self._storage_dir.resolve()
        except OSError as exc:
            errors.append(f'{directory}: {exc}')
            return
        if resolved == storage_root or storage_root not in resolved.parents:
            skipped.append(str(directory))
            return
        if not directory.exists():
            return
        if not directory.is_dir():
            skipped.append(str(directory))
            return
        try:
            shutil.rmtree(directory)
            deleted.append(str(directory))
        except OSError as exc:
            errors.append(f'{directory}: {exc}')

    def _delete_contract_file(
        self,
        raw_path: str,
        *,
        deleted: list[str],
        skipped: list[str],
        errors: list[str],
    ) -> None:
        path = Path(raw_path)
        try:
            resolved = path.resolve()
            contracts_root = (self._storage_dir / 'contracts').resolve()
        except OSError as exc:
            errors.append(f'{raw_path}: {exc}')
            return
        if resolved.name == '.gitkeep' or (resolved != contracts_root and contracts_root not in resolved.parents):
            skipped.append(raw_path)
            return
        if not resolved.exists():
            return
        if not resolved.is_file():
            skipped.append(raw_path)
            return
        try:
            resolved.unlink()
            deleted.append(str(resolved))
        except OSError as exc:
            errors.append(f'{raw_path}: {exc}')


def _delete_invoice_items(connection: sqlite3.Connection, invoice_ids: list[int]) -> int:
    if not invoice_ids:
        return 0
    placeholders = ','.join('?' for _ in invoice_ids)
    return connection.execute(
        f'DELETE FROM invoice_item WHERE invoice_id IN ({placeholders})',
        tuple(invoice_ids),
    ).rowcount
