from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

from bot.services.db import managed_connection


@dataclass
class ServiceAliasMapping:
    id: int
    supplier_id: int
    service_short_name: str
    service_display_name: str
    is_active: int
    created_at: str


class ServiceAliasService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @staticmethod
    def _normalize_service_short_name(value: str) -> str:
        return value.strip().lower()

    def create_mapping(self, supplier_id: int, service_short_name: str, service_display_name: str) -> None:
        short_name_clean = service_short_name.strip()
        display_name_clean = service_display_name.strip()
        if not short_name_clean:
            raise ValueError('Service short name cannot be empty.')
        if not display_name_clean:
            raise ValueError('Service display name cannot be empty.')

        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO supplier_service_alias '
                    '(supplier_id, alias, canonical_title, is_active, created_at) '
                    'VALUES (?, ?, ?, 1, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(supplier_id, alias) DO UPDATE SET '
                    'canonical_title=excluded.canonical_title, is_active=1'
                ),
                (supplier_id, short_name_clean, display_name_clean),
            )
            connection.commit()

    def list_mappings(self, supplier_id: int, include_inactive: bool = False) -> list[ServiceAliasMapping]:
        where_clause = 'WHERE supplier_id = ?'
        if not include_inactive:
            where_clause += ' AND is_active = 1'

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT id, supplier_id, alias, canonical_title, is_active, created_at '
                    'FROM supplier_service_alias '
                    f'{where_clause} '
                    'ORDER BY canonical_title ASC, alias ASC'
                ),
                (supplier_id,),
            ).fetchall()

        return [
            ServiceAliasMapping(
                id=row['id'],
                supplier_id=row['supplier_id'],
                service_short_name=row['alias'],
                service_display_name=row['canonical_title'],
                is_active=row['is_active'],
                created_at=row['created_at'],
            )
            for row in rows
        ]

    def resolve_service_display_name(self, supplier_id: int, service_short_name: str) -> str | None:
        normalized_short_name = self._normalize_service_short_name(service_short_name)
        if not normalized_short_name:
            return None

        with managed_connection(self._db_path) as connection:
            row = connection.execute(
                (
                    'SELECT canonical_title '
                    'FROM supplier_service_alias '
                    'WHERE supplier_id = ? AND alias = ? AND is_active = 1 '
                    'LIMIT 1'
                ),
                (supplier_id, normalized_short_name),
            ).fetchone()

        if row is None:
            return None

        return str(row[0])

    def resolve_alias(self, supplier_id: int, alias: str) -> str | None:
        return self.resolve_service_display_name(supplier_id, alias)

    def deactivate_mapping(self, mapping_id: int, supplier_id: int) -> bool:
        with managed_connection(self._db_path) as connection:
            cursor = connection.execute(
                (
                    'UPDATE supplier_service_alias '
                    'SET is_active = 0 '
                    'WHERE id = ? AND supplier_id = ?'
                ),
                (mapping_id, supplier_id),
            )
            connection.commit()
            return cursor.rowcount > 0
