from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3
import unicodedata

from bot.services.db import managed_connection


_CANONICAL_ELECTRICAL_REPAIR_TITLE = 'Opravy vyhradených technických zariadení elektrických'


def _display_lookup_key(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', value.strip().casefold())
    without_marks = ''.join(character for character in normalized if not unicodedata.combining(character))
    return ' '.join(without_marks.split())


_CANONICAL_SERVICE_DISPLAY_NAMES = {
    _display_lookup_key(_CANONICAL_ELECTRICAL_REPAIR_TITLE): _CANONICAL_ELECTRICAL_REPAIR_TITLE,
}


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

    _SERVICE_ALIAS_DOMAIN = 'invoice_service'
    _SERVICE_ALIAS_TARGET_TYPE = 'supplier_service_alias'
    _MAX_CONFIRMED_ALIASES_PER_SERVICE = 10

    @staticmethod
    def _normalize_service_short_name(value: str) -> str:
        return value.strip().lower()

    @staticmethod
    def _normalize_service_display_name(value: str) -> str:
        display_name = value.strip()
        return _CANONICAL_SERVICE_DISPLAY_NAMES.get(_display_lookup_key(display_name), display_name)

    @staticmethod
    def _normalize_lookup_tokens(value: str) -> list[str]:
        lowered = value.casefold().strip()
        if not lowered:
            return []
        separators_normalized = re.sub(r'[.,\-/]+', ' ', lowered)
        collapsed = re.sub(r'\s+', ' ', separators_normalized).strip()
        if not collapsed:
            return []
        return re.findall(r'[0-9a-zA-ZÀ-žА-я]+', collapsed)

    @classmethod
    def normalize_lookup_forms(cls, value: str) -> tuple[str, str]:
        tokens = cls._normalize_lookup_tokens(value)
        normalized = ' '.join(tokens)
        compressed = ''.join(tokens)
        return normalized, compressed

    def create_mapping(self, supplier_id: int, service_short_name: str, service_display_name: str) -> None:
        short_name_clean = service_short_name.strip()
        display_name_clean = self._normalize_service_display_name(service_display_name)
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
                service_display_name=self._normalize_service_display_name(row['canonical_title']),
                is_active=row['is_active'],
                created_at=row['created_at'],
            )
            for row in rows
        ]

    def get_mapping_by_id(self, *, supplier_id: int, mapping_id: int) -> ServiceAliasMapping | None:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_id, alias, canonical_title, is_active, created_at '
                    'FROM supplier_service_alias '
                    'WHERE id = ? AND supplier_id = ? AND is_active = 1'
                ),
                (mapping_id, supplier_id),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_mapping(row)

    def get_mapping_by_alias(self, *, supplier_id: int, service_short_name: str) -> ServiceAliasMapping | None:
        normalized_short_name = self._normalize_service_short_name(service_short_name)
        if not normalized_short_name:
            return None

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_id, alias, canonical_title, is_active, created_at '
                    'FROM supplier_service_alias '
                    'WHERE supplier_id = ? AND alias = ? AND is_active = 1 '
                    'LIMIT 1'
                ),
                (supplier_id, normalized_short_name),
            ).fetchone()

        if row is None:
            return None
        return self._row_to_mapping(row)

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

        return self._normalize_service_display_name(str(row[0]))

    def resolve_alias(self, supplier_id: int, alias: str) -> str | None:
        return self.resolve_service_display_name(supplier_id, alias)

    def resolve_confirmed_service_alias(
        self,
        *,
        supplier_telegram_id: int,
        supplier_id: int,
        alias_text: str,
        workspace_id: str | None = None,
    ) -> ServiceAliasMapping | None:
        normalized, compressed = self.normalize_lookup_forms(alias_text)
        if not normalized or not compressed:
            return None

        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            has_workspace = _confirmed_alias_has_workspace(connection)
            if workspace_id is not None and not has_workspace:
                raise RuntimeError('workspace_alias_schema_migration_required')
            workspace_clause = (
                'AND a.workspace_id = ? '
                if workspace_id is not None
                else 'AND a.workspace_id IS NULL '
                if has_workspace
                else ''
            )
            params: list[object] = [supplier_telegram_id]
            if workspace_id is not None:
                params.append(workspace_id)
            params.extend(
                [
                    self._SERVICE_ALIAS_DOMAIN,
                    self._SERVICE_ALIAS_TARGET_TYPE,
                    supplier_id,
                    normalized,
                    compressed,
                ]
            )
            rows = connection.execute(
                (
                    'SELECT s.id, s.supplier_id, s.alias, s.canonical_title, '
                    's.is_active, s.created_at '
                    'FROM confirmed_semantic_alias a '
                    'JOIN supplier_service_alias s ON s.id = a.target_id '
                    'WHERE a.supplier_telegram_id = ? '
                    f'{workspace_clause}'
                    'AND a.domain = ? AND a.target_type = ? '
                    'AND s.supplier_id = ? AND s.is_active = 1 '
                    'AND (a.alias_normalized = ? OR a.alias_compressed = ?) '
                    'LIMIT 2'
                ),
                params,
            ).fetchall()

        if len(rows) != 1:
            return None
        return self._row_to_mapping(rows[0])
    def create_confirmed_service_alias(
        self,
        *,
        supplier_telegram_id: int,
        supplier_id: int,
        alias_text: str,
        service_alias_id: int,
        source: str,
        workspace_id: str | None = None,
    ) -> bool:
        normalized, compressed = self.normalize_lookup_forms(alias_text)
        if not normalized or not compressed:
            return False
        if self.get_mapping_by_id(
            supplier_id=supplier_id,
            mapping_id=service_alias_id,
        ) is None:
            raise ValueError(
                'Cannot create service alias for a service mapping outside the supplier scope.'
            )

        with managed_connection(self._db_path) as connection:
            has_workspace = _confirmed_alias_has_workspace(connection)
            if workspace_id is not None and not has_workspace:
                raise RuntimeError('workspace_alias_schema_migration_required')
            workspace_clause = (
                'AND workspace_id = ? '
                if workspace_id is not None
                else 'AND workspace_id IS NULL '
                if has_workspace
                else ''
            )
            scope_params: list[object] = [supplier_telegram_id]
            if workspace_id is not None:
                scope_params.append(workspace_id)
            existing = connection.execute(
                (
                    'SELECT id, target_id FROM confirmed_semantic_alias '
                    'WHERE supplier_telegram_id = ? '
                    f'{workspace_clause}'
                    'AND domain = ? AND target_type = ? AND alias_normalized = ?'
                ),
                (
                    *scope_params,
                    self._SERVICE_ALIAS_DOMAIN,
                    self._SERVICE_ALIAS_TARGET_TYPE,
                    normalized,
                ),
            ).fetchone()
            if existing is not None and int(existing[1]) != service_alias_id:
                return False
            if existing is None:
                count = connection.execute(
                    (
                        'SELECT COUNT(*) FROM confirmed_semantic_alias '
                        'WHERE supplier_telegram_id = ? '
                        f'{workspace_clause}'
                        'AND domain = ? AND target_type = ? AND target_id = ?'
                    ),
                    (
                        *scope_params,
                        self._SERVICE_ALIAS_DOMAIN,
                        self._SERVICE_ALIAS_TARGET_TYPE,
                        service_alias_id,
                    ),
                ).fetchone()[0]
                if count >= self._MAX_CONFIRMED_ALIASES_PER_SERVICE:
                    return False

            if existing is not None:
                connection.execute(
                    (
                        'UPDATE confirmed_semantic_alias SET alias_text=?, '
                        'alias_compressed=?, target_id=?, source=?, '
                        'updated_at=CURRENT_TIMESTAMP WHERE id=?'
                    ),
                    (
                        alias_text.strip(),
                        compressed,
                        service_alias_id,
                        source,
                        int(existing[0]),
                    ),
                )
            elif has_workspace:
                connection.execute(
                    (
                        'INSERT INTO confirmed_semantic_alias '
                        '(workspace_id, supplier_telegram_id, domain, alias_text, '
                        'alias_normalized, alias_compressed, target_type, target_id, '
                        'source, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, '
                        'CURRENT_TIMESTAMP)'
                    ),
                    (
                        workspace_id,
                        supplier_telegram_id,
                        self._SERVICE_ALIAS_DOMAIN,
                        alias_text.strip(),
                        normalized,
                        compressed,
                        self._SERVICE_ALIAS_TARGET_TYPE,
                        service_alias_id,
                        source,
                    ),
                )
            else:
                connection.execute(
                    (
                        'INSERT INTO confirmed_semantic_alias '
                        '(supplier_telegram_id, domain, alias_text, alias_normalized, '
                        'alias_compressed, target_type, target_id, source, created_at, '
                        'updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '
                        'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                    ),
                    (
                        supplier_telegram_id,
                        self._SERVICE_ALIAS_DOMAIN,
                        alias_text.strip(),
                        normalized,
                        compressed,
                        self._SERVICE_ALIAS_TARGET_TYPE,
                        service_alias_id,
                        source,
                    ),
                )
            connection.commit()
        return True
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

    def _row_to_mapping(self, row: sqlite3.Row) -> ServiceAliasMapping:
        return ServiceAliasMapping(
            id=row['id'],
            supplier_id=row['supplier_id'],
            service_short_name=row['alias'],
            service_display_name=self._normalize_service_display_name(row['canonical_title']),
            is_active=row['is_active'],
            created_at=row['created_at'],
        )


def _confirmed_alias_has_workspace(connection: sqlite3.Connection) -> bool:
    return any(
        row[1] == 'workspace_id'
        for row in connection.execute(
            'PRAGMA table_info(confirmed_semantic_alias)'
        ).fetchall()
    )