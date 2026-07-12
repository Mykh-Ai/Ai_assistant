from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from bot.services.db import managed_connection


@dataclass
class SupplierProfile:
    telegram_id: int
    name: str
    ico: str
    dic: str
    ic_dph: str | None
    address: str
    iban: str
    swift: str
    email: str
    smtp_host: str | None
    smtp_user: str | None
    smtp_pass: str | None
    days_due: int
    id: int | None = None
    workspace_id: str | None = None


class SupplierService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @staticmethod
    def normalize_optional_smtp(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @staticmethod
    def has_complete_smtp_config(profile: SupplierProfile) -> bool:
        return all(
            (
                SupplierService.normalize_optional_smtp(profile.smtp_host),
                SupplierService.normalize_optional_smtp(profile.smtp_user),
                SupplierService.normalize_optional_smtp(profile.smtp_pass),
            )
        )

    def get_by_workspace_id(self, workspace_id: str) -> SupplierProfile | None:
        normalized_workspace_id = str(workspace_id).strip()
        if not normalized_workspace_id:
            return None
        with managed_connection(self._db_path) as connection:
            if not _has_workspace_column(connection):
                return None
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f'{_supplier_select(True)} WHERE workspace_id = ?',
                (normalized_workspace_id,),
            ).fetchone()
        return _profile_from_row(row) if row is not None else None

    def get_by_telegram_id(self, telegram_id: int) -> SupplierProfile | None:
        with managed_connection(self._db_path) as connection:
            has_workspace = _has_workspace_column(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f'{_supplier_select(has_workspace)} '
                'WHERE telegram_id = ? ORDER BY id LIMIT 2',
                (telegram_id,),
            ).fetchall()
        if not rows:
            return None
        if len(rows) > 1:
            raise RuntimeError('ambiguous_supplier_profile_requires_workspace')
        return _profile_from_row(rows[0])

    def create_or_replace(self, profile: SupplierProfile) -> None:
        with managed_connection(self._db_path) as connection:
            self.save_in_connection(connection, profile)
            connection.commit()

    def save_in_connection(
        self,
        connection: sqlite3.Connection,
        profile: SupplierProfile,
    ) -> int:
        workspace_id = _clean_workspace_id(profile.workspace_id)
        has_workspace = _has_workspace_column(connection)
        if not has_workspace:
            if workspace_id is not None:
                raise RuntimeError('workspace_supplier_schema_migration_required')
            return self._save_legacy_in_connection(connection, profile)
        if workspace_id is not None:
            connection.execute(
                (
                    'INSERT INTO supplier '
                    '(workspace_id, telegram_id, name, ico, dic, ic_dph, address, '
                    'iban, swift, email, smtp_host, smtp_user, smtp_pass, days_due, '
                    'created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
                    'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(workspace_id) DO UPDATE SET '
                    'telegram_id=excluded.telegram_id, name=excluded.name, '
                    'ico=excluded.ico, dic=excluded.dic, ic_dph=excluded.ic_dph, '
                    'address=excluded.address, iban=excluded.iban, swift=excluded.swift, '
                    'email=excluded.email, smtp_host=excluded.smtp_host, '
                    'smtp_user=excluded.smtp_user, smtp_pass=excluded.smtp_pass, '
                    'days_due=excluded.days_due, updated_at=CURRENT_TIMESTAMP'
                ),
                self._values(profile, workspace_id),
            )
            row = connection.execute(
                'SELECT id FROM supplier WHERE workspace_id = ?',
                (workspace_id,),
            ).fetchone()
            if row is None:
                raise RuntimeError('supplier_profile_save_failed')
            return int(row[0])

        rows = connection.execute(
            'SELECT id FROM supplier WHERE telegram_id = ? ORDER BY id LIMIT 2',
            (profile.telegram_id,),
        ).fetchall()
        if len(rows) > 1:
            raise RuntimeError('ambiguous_supplier_profile_requires_workspace')
        if rows:
            supplier_id = int(rows[0][0])
            self._update_by_id(connection, profile, supplier_id)
            return supplier_id
        cursor = connection.execute(
            (
                'INSERT INTO supplier '
                '(workspace_id, telegram_id, name, ico, dic, ic_dph, address, iban, '
                'swift, email, smtp_host, smtp_user, smtp_pass, days_due, '
                'created_at, updated_at) '
                'VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
                'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
            ),
            self._values(profile, None)[1:],
        )
        return int(cursor.lastrowid)

    def _save_legacy_in_connection(
        self,
        connection: sqlite3.Connection,
        profile: SupplierProfile,
    ) -> int:
        connection.execute(
            (
                'INSERT INTO supplier '
                '(telegram_id, name, ico, dic, ic_dph, address, iban, swift, email, '
                'smtp_host, smtp_user, smtp_pass, days_due, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
                'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                'ON CONFLICT(telegram_id) DO UPDATE SET '
                'name=excluded.name, ico=excluded.ico, dic=excluded.dic, '
                'ic_dph=excluded.ic_dph, address=excluded.address, '
                'iban=excluded.iban, swift=excluded.swift, email=excluded.email, '
                'smtp_host=excluded.smtp_host, smtp_user=excluded.smtp_user, '
                'smtp_pass=excluded.smtp_pass, days_due=excluded.days_due, '
                'updated_at=CURRENT_TIMESTAMP'
            ),
            self._values(profile, None)[1:],
        )
        row = connection.execute(
            'SELECT id FROM supplier WHERE telegram_id = ?',
            (profile.telegram_id,),
        ).fetchone()
        if row is None:
            raise RuntimeError('supplier_profile_save_failed')
        return int(row[0])

    def _update_by_id(
        self,
        connection: sqlite3.Connection,
        profile: SupplierProfile,
        supplier_id: int,
    ) -> None:
        connection.execute(
            (
                'UPDATE supplier SET name=?, ico=?, dic=?, ic_dph=?, address=?, '
                'iban=?, swift=?, email=?, smtp_host=?, smtp_user=?, smtp_pass=?, '
                'days_due=?, updated_at=CURRENT_TIMESTAMP WHERE id=?'
            ),
            (
                profile.name,
                profile.ico,
                profile.dic,
                profile.ic_dph,
                profile.address,
                profile.iban,
                profile.swift,
                profile.email,
                self.normalize_optional_smtp(profile.smtp_host),
                self.normalize_optional_smtp(profile.smtp_user),
                self.normalize_optional_smtp(profile.smtp_pass),
                profile.days_due,
                supplier_id,
            ),
        )

    def update_profile(self, profile: SupplierProfile) -> None:
        self.create_or_replace(profile)

    def _values(
        self,
        profile: SupplierProfile,
        workspace_id: str | None,
    ) -> tuple[object, ...]:
        return (
            workspace_id,
            profile.telegram_id,
            profile.name,
            profile.ico,
            profile.dic,
            profile.ic_dph,
            profile.address,
            profile.iban,
            profile.swift,
            profile.email,
            self.normalize_optional_smtp(profile.smtp_host),
            self.normalize_optional_smtp(profile.smtp_user),
            self.normalize_optional_smtp(profile.smtp_pass),
            profile.days_due,
        )


def _has_workspace_column(connection: sqlite3.Connection) -> bool:
    return any(
        row[1] == 'workspace_id'
        for row in connection.execute('PRAGMA table_info(supplier)').fetchall()
    )


def _supplier_select(has_workspace: bool) -> str:
    workspace_expression = 'workspace_id' if has_workspace else 'NULL AS workspace_id'
    return (
        f'SELECT id, {workspace_expression}, telegram_id, name, ico, dic, ic_dph, '
        'address, iban, swift, email, smtp_host, smtp_user, smtp_pass, days_due '
        'FROM supplier'
    )


def _clean_workspace_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _profile_from_row(row: sqlite3.Row) -> SupplierProfile:
    return SupplierProfile(
        id=int(row['id']),
        workspace_id=row['workspace_id'],
        telegram_id=int(row['telegram_id']),
        name=row['name'],
        ico=row['ico'],
        dic=row['dic'],
        ic_dph=row['ic_dph'],
        address=row['address'],
        iban=row['iban'],
        swift=row['swift'],
        email=row['email'],
        smtp_host=SupplierService.normalize_optional_smtp(row['smtp_host']),
        smtp_user=SupplierService.normalize_optional_smtp(row['smtp_user']),
        smtp_pass=SupplierService.normalize_optional_smtp(row['smtp_pass']),
        days_due=int(row['days_due']),
    )