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
    invoice_followup_states_deleted: int
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
            supplier_columns = {
                str(row[1])
                for row in connection.execute('PRAGMA table_info(supplier)').fetchall()
            }
            supplier_select = 'SELECT id, workspace_id FROM supplier WHERE telegram_id = ?'
            if 'workspace_id' not in supplier_columns:
                supplier_select = 'SELECT id, NULL AS workspace_id FROM supplier WHERE telegram_id = ?'
            supplier_rows = connection.execute(supplier_select, (telegram_id,)).fetchall()
            supplier_ids = [int(row['id']) for row in supplier_rows]
            workspace_ids = [
                str(row['workspace_id'])
                for row in supplier_rows
                if row['workspace_id'] is not None
            ]
            storage_keys = _workspace_storage_keys(connection, workspace_ids)
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
            invoice_followup_states_deleted = _delete_invoice_followup_states(connection, invoice_ids)
            invoices_deleted = connection.execute(
                'DELETE FROM invoice WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            contacts_deleted = connection.execute(
                'DELETE FROM contact WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            service_aliases_deleted = _delete_supplier_service_aliases(
                connection,
                supplier_ids,
            )
            invoice_number_settings_deleted = connection.execute(
                'DELETE FROM invoice_number_settings WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            confirmed_aliases_deleted = connection.execute(
                'DELETE FROM confirmed_semantic_alias WHERE supplier_telegram_id = ?',
                (telegram_id,),
            ).rowcount
            _delete_optional_user_rows(connection, telegram_id=telegram_id)
            supplier_deleted = (
                connection.execute('DELETE FROM supplier WHERE telegram_id = ?', (telegram_id,)).rowcount > 0
            )
            _delete_workspace_foundation_rows(connection, telegram_id=telegram_id, workspace_ids=workspace_ids)

            mark_deleted_database_in_connection(connection, telegram_id=telegram_id)
            connection.commit()

        deleted, skipped, errors = self._delete_scoped_filesystem_paths(
            telegram_id=telegram_id,
            contract_paths=contract_paths,
            storage_keys=storage_keys,
        )
        return UserDataDeletionResult(
            telegram_id=telegram_id,
            supplier_deleted=supplier_deleted,
            contacts_deleted=contacts_deleted,
            invoices_deleted=invoices_deleted,
            invoice_items_deleted=invoice_items_deleted,
            invoice_followup_states_deleted=invoice_followup_states_deleted,
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
        storage_keys: list[str],
    ) -> tuple[list[str], list[str], list[str]]:
        deleted: list[str] = []
        skipped: list[str] = []
        errors: list[str] = []
        scoped_dirs = [
            self._storage_dir / 'invoices' / str(telegram_id),
            self._storage_dir / 'workspaces' / workspace_key_for_supplier(telegram_id),
            self._storage_dir / 'uploads' / 'accounting_intake' / str(telegram_id),
            self._storage_dir / 'uploads' / 'attachment_intake' / str(telegram_id),
            self._storage_dir / 'work_time_reports' / str(telegram_id),
        ]
        for storage_key in storage_keys:
            scoped_dirs.extend(
                [
                    self._storage_dir / 'invoices' / storage_key,
                    self._storage_dir / 'workspaces' / storage_key,
                    self._storage_dir / 'uploads' / 'accounting_intake' / storage_key,
                    self._storage_dir / 'uploads' / 'attachment_intake' / storage_key,
                    self._storage_dir / 'work_time_reports' / storage_key,
                ]
            )
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


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table,),
    ).fetchone() is not None


def _workspace_storage_keys(
    connection: sqlite3.Connection,
    workspace_ids: list[str],
) -> list[str]:
    if not workspace_ids or not _table_exists(connection, 'workspace'):
        return []
    placeholders = ','.join('?' for _ in workspace_ids)
    return [
        str(row[0])
        for row in connection.execute(
            f'SELECT storage_key FROM workspace WHERE workspace_id IN ({placeholders})',
            workspace_ids,
        ).fetchall()
    ]


def _delete_supplier_service_aliases(
    connection: sqlite3.Connection,
    supplier_ids: list[int],
) -> int:
    if not supplier_ids:
        return 0
    placeholders = ','.join('?' for _ in supplier_ids)
    return connection.execute(
        f'DELETE FROM supplier_service_alias WHERE supplier_id IN ({placeholders})',
        supplier_ids,
    ).rowcount


def _delete_optional_user_rows(
    connection: sqlite3.Connection,
    *,
    telegram_id: int,
) -> None:
    for table in (
        'work_time_events',
        'work_time_days',
        'work_time_settings',
        'archive_jobs',
        'accounting_document_archive_state',
        'customization_requests',
    ):
        if _table_exists(connection, table):
            connection.execute(f'DELETE FROM {table} WHERE telegram_id = ?', (telegram_id,))


def _delete_workspace_foundation_rows(
    connection: sqlite3.Connection,
    *,
    telegram_id: int,
    workspace_ids: list[str],
) -> None:
    if _table_exists(connection, 'active_workspace_selection'):
        connection.execute(
            'DELETE FROM active_workspace_selection WHERE telegram_id = ?',
            (telegram_id,),
        )
    if _table_exists(connection, 'workspace_membership'):
        connection.execute(
            'DELETE FROM workspace_membership WHERE telegram_id = ?',
            (telegram_id,),
        )
        if workspace_ids:
            placeholders = ','.join('?' for _ in workspace_ids)
            connection.execute(
                f'DELETE FROM workspace_membership WHERE workspace_id IN ({placeholders})',
                workspace_ids,
            )
    if workspace_ids and _table_exists(connection, 'workspace'):
        placeholders = ','.join('?' for _ in workspace_ids)
        connection.execute(
            f'DELETE FROM workspace WHERE workspace_id IN ({placeholders})',
            workspace_ids,
        )

def _delete_invoice_items(connection: sqlite3.Connection, invoice_ids: list[int]) -> int:
    if not invoice_ids:
        return 0
    placeholders = ','.join('?' for _ in invoice_ids)
    return connection.execute(
        f'DELETE FROM invoice_item WHERE invoice_id IN ({placeholders})',
        tuple(invoice_ids),
    ).rowcount


def _delete_invoice_followup_states(connection: sqlite3.Connection, invoice_ids: list[int]) -> int:
    if not invoice_ids:
        return 0
    placeholders = ','.join('?' for _ in invoice_ids)
    return connection.execute(
        f'DELETE FROM invoice_followup_state WHERE invoice_id IN ({placeholders})',
        tuple(invoice_ids),
    ).rowcount
