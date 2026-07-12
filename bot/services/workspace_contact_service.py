from __future__ import annotations

from pathlib import Path
import sqlite3

from bot.services.contact_service import (
    ContactLookupResult,
    ContactProfile,
    ContactService,
)
from bot.services.db import managed_connection
from bot.services.workspace_context import WorkspaceContext


class WorkspaceContactSchemaRequired(RuntimeError):
    pass


class WorkspaceContactService:
    _ALIAS_DOMAIN = 'invoice_customer'
    _ALIAS_TARGET_TYPE = 'contact'

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def list_contacts(self, context: WorkspaceContext) -> list[ContactProfile]:
        with managed_connection(self._db_path) as connection:
            self._require_contact_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                f'{_CONTACT_SELECT} WHERE workspace_id = ? '
                'ORDER BY name COLLATE NOCASE ASC',
                (context.workspace_id,),
            ).fetchall()
        return [_row_to_profile(row) for row in rows]

    def get_by_name(
        self,
        context: WorkspaceContext,
        name: str,
    ) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            self._require_contact_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f'{_CONTACT_SELECT} WHERE workspace_id = ? AND name = ?',
                (context.workspace_id, name),
            ).fetchone()
        return _row_to_profile(row) if row is not None else None

    def get_by_id(
        self,
        context: WorkspaceContext,
        contact_id: int,
    ) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            self._require_contact_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                f'{_CONTACT_SELECT} WHERE workspace_id = ? AND id = ?',
                (context.workspace_id, contact_id),
            ).fetchone()
        return _row_to_profile(row) if row is not None else None

    def create_or_replace(
        self,
        context: WorkspaceContext,
        profile: ContactProfile,
    ) -> ContactProfile:
        if profile.workspace_id not in {None, context.workspace_id}:
            raise ValueError('contact_workspace_mismatch')
        if profile.supplier_telegram_id != context.actor_telegram_id:
            raise ValueError('contact_actor_mismatch')
        with managed_connection(self._db_path) as connection:
            self._require_contact_schema(connection)
            connection.execute(
                (
                    'INSERT INTO contact '
                    '(workspace_id, supplier_telegram_id, name, ico, dic, ic_dph, '
                    'address, email, contact_person, source_type, source_note, '
                    'contract_path, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
                    'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(workspace_id, name) DO UPDATE SET '
                    'supplier_telegram_id=excluded.supplier_telegram_id, '
                    'ico=excluded.ico, dic=excluded.dic, ic_dph=excluded.ic_dph, '
                    'address=excluded.address, email=excluded.email, '
                    'contact_person=excluded.contact_person, '
                    'source_type=excluded.source_type, source_note=excluded.source_note, '
                    'contract_path=excluded.contract_path, updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    context.workspace_id,
                    context.actor_telegram_id,
                    profile.name,
                    profile.ico,
                    profile.dic,
                    profile.ic_dph,
                    profile.address,
                    profile.email,
                    profile.contact_person,
                    profile.source_type,
                    profile.source_note,
                    profile.contract_path,
                ),
            )
            connection.commit()
        saved = self.get_by_name(context, profile.name)
        if saved is None:
            raise RuntimeError('workspace_contact_save_failed')
        return saved

    def create_confirmed_alias(
        self,
        context: WorkspaceContext,
        *,
        alias_text: str,
        contact_id: int,
        source: str,
    ) -> None:
        normalized, compressed = ContactService.normalize_lookup_forms(alias_text)
        if not normalized or not compressed:
            return
        if self.get_by_id(context, contact_id) is None:
            raise ValueError('contact_alias_workspace_mismatch')
        with managed_connection(self._db_path) as connection:
            self._require_alias_schema(connection)
            connection.execute(
                (
                    'INSERT INTO confirmed_semantic_alias '
                    '(workspace_id, supplier_telegram_id, domain, alias_text, '
                    'alias_normalized, alias_compressed, target_type, target_id, '
                    'source, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, '
                    'CURRENT_TIMESTAMP) '
                    'ON CONFLICT(workspace_id, domain, target_type, alias_normalized) '
                    'DO UPDATE SET alias_text=excluded.alias_text, '
                    'alias_compressed=excluded.alias_compressed, '
                    'target_id=excluded.target_id, source=excluded.source, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    context.workspace_id,
                    context.actor_telegram_id,
                    self._ALIAS_DOMAIN,
                    alias_text.strip(),
                    normalized,
                    compressed,
                    self._ALIAS_TARGET_TYPE,
                    contact_id,
                    source,
                ),
            )
            connection.commit()

    def resolve_contact_lookup(
        self,
        context: WorkspaceContext,
        name: str,
    ) -> ContactLookupResult:
        raw_query = name.strip()
        normalized, compressed = ContactService.normalize_lookup_forms(raw_query)
        profiles = self.list_contacts(context)

        exact = [profile for profile in profiles if profile.name == raw_query]
        if len(exact) == 1:
            return _result('exact_match', exact[0], exact, raw_query, normalized, compressed)
        casefold = [
            profile
            for profile in profiles
            if profile.name.casefold() == raw_query.casefold()
        ]
        if len(casefold) == 1:
            return _result(
                'normalized_match',
                casefold[0],
                casefold,
                raw_query,
                normalized,
                compressed,
            )
        if not normalized and not compressed:
            return _result('no_match', None, [], raw_query, normalized, compressed)

        alias = self._find_by_alias(context, normalized, compressed)
        if alias is not None:
            return _result('alias_match', alias, [alias], raw_query, normalized, compressed)

        normalized_matches: list[ContactProfile] = []
        for profile in profiles:
            profile_normalized, profile_compressed = ContactService.normalize_lookup_forms(
                profile.name
            )
            if (
                normalized
                and profile_normalized
                and normalized == profile_normalized
            ) or (
                compressed
                and profile_compressed
                and compressed == profile_compressed
            ):
                normalized_matches.append(profile)
        if len(normalized_matches) == 1:
            return _result(
                'normalized_match',
                normalized_matches[0],
                normalized_matches,
                raw_query,
                normalized,
                compressed,
            )
        if len(normalized_matches) > 1:
            return _result(
                'multiple_candidates',
                None,
                normalized_matches,
                raw_query,
                normalized,
                compressed,
            )

        fuzzy = ContactService._high_confidence_fuzzy_candidates(raw_query, profiles)
        if len(fuzzy) == 1:
            return _result('fuzzy_match', fuzzy[0], fuzzy, raw_query, normalized, compressed)
        if len(fuzzy) > 1:
            return _result(
                'multiple_candidates',
                None,
                fuzzy,
                raw_query,
                normalized,
                compressed,
            )
        return _result('no_match', None, [], raw_query, normalized, compressed)

    def _find_by_alias(
        self,
        context: WorkspaceContext,
        normalized: str,
        compressed: str,
    ) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            self._require_alias_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    f'{_CONTACT_JOIN_SELECT} '
                    'JOIN confirmed_semantic_alias AS a ON a.target_id = c.id '
                    'AND a.workspace_id = c.workspace_id '
                    'WHERE a.workspace_id = ? AND a.domain = ? '
                    'AND a.target_type = ? '
                    'AND (a.alias_normalized = ? OR a.alias_compressed = ?) '
                    'LIMIT 2'
                ),
                (
                    context.workspace_id,
                    self._ALIAS_DOMAIN,
                    self._ALIAS_TARGET_TYPE,
                    normalized,
                    compressed,
                ),
            ).fetchall()
        if len(rows) != 1:
            return None
        return _row_to_profile(rows[0])

    @staticmethod
    def _require_contact_schema(connection: sqlite3.Connection) -> None:
        _require_workspace_column(connection, 'contact', 'workspace_contact_schema_migration_required')

    @staticmethod
    def _require_alias_schema(connection: sqlite3.Connection) -> None:
        _require_workspace_column(
            connection,
            'confirmed_semantic_alias',
            'workspace_alias_schema_migration_required',
        )


_CONTACT_SELECT = (
    'SELECT id, workspace_id, supplier_telegram_id, name, ico, dic, ic_dph, '
    'address, email, contact_person, source_type, source_note, contract_path '
    'FROM contact'
)

_CONTACT_JOIN_SELECT = (
    'SELECT c.id, c.workspace_id, c.supplier_telegram_id, c.name, c.ico, c.dic, '
    'c.ic_dph, c.address, c.email, c.contact_person, c.source_type, '
    'c.source_note, c.contract_path FROM contact AS c'
)


def _require_workspace_column(
    connection: sqlite3.Connection,
    table: str,
    error: str,
) -> None:
    columns = {
        row[1] for row in connection.execute(f'PRAGMA table_info({table})')
    }
    if 'workspace_id' not in columns:
        raise WorkspaceContactSchemaRequired(error)


def _row_to_profile(row: sqlite3.Row) -> ContactProfile:
    return ContactProfile(
        id=int(row['id']),
        workspace_id=row['workspace_id'],
        supplier_telegram_id=int(row['supplier_telegram_id']),
        name=row['name'],
        ico=row['ico'],
        dic=row['dic'],
        ic_dph=row['ic_dph'],
        address=row['address'],
        email=row['email'],
        contact_person=row['contact_person'],
        source_type=row['source_type'],
        source_note=row['source_note'],
        contract_path=row['contract_path'],
    )


def _result(
    state,
    matched_contact,
    candidates,
    raw_query,
    normalized,
    compressed,
) -> ContactLookupResult:
    return ContactLookupResult(
        state=state,
        matched_contact=matched_contact,
        candidates=candidates,
        raw_query=raw_query,
        normalized_query=normalized,
        compressed_query=compressed,
    )