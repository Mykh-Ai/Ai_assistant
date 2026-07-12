from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
import re
import sqlite3
from typing import Literal

from bot.services.db import managed_connection


@dataclass
class ContactProfile:
    supplier_telegram_id: int
    name: str
    ico: str
    dic: str
    ic_dph: str | None
    address: str
    email: str
    contact_person: str | None
    source_type: str
    source_note: str | None
    contract_path: str | None
    id: int | None = None
    workspace_id: str | None = None


ContactLookupState = Literal[
    'exact_match',
    'normalized_match',
    'alias_match',
    'fuzzy_match',
    'single_candidate_confirm_required',
    'multiple_candidates',
    'no_match',
]


@dataclass
class ContactLookupResult:
    state: ContactLookupState
    matched_contact: ContactProfile | None
    candidates: list[ContactProfile]
    raw_query: str
    normalized_query: str
    compressed_query: str


class ContactService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    _CONTACT_ALIAS_DOMAIN = 'invoice_customer'
    _CONTACT_ALIAS_TARGET_TYPE = 'contact'
    _TRAILING_COUNTRY_TOKENS = {'sk', 'cz'}
    _HIGH_CONFIDENCE_FUZZY_RATIO = 0.90
    _MIN_FUZZY_COMPRESSED_LENGTH = 6

    def get_all_by_supplier(self, telegram_id: int) -> list[ContactProfile]:
        with managed_connection(self._db_path) as connection:
            _assert_legacy_scope_unambiguous(connection, telegram_id)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
                    'contact_person, source_type, source_note, contract_path '
                    'FROM contact '
                    'WHERE supplier_telegram_id = ? '
                    'ORDER BY name COLLATE NOCASE ASC'
                ),
                (telegram_id,),
            ).fetchall()

        return [self._row_to_profile(row) for row in rows]

    def get_by_name(self, telegram_id: int, name: str) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            _assert_legacy_scope_unambiguous(connection, telegram_id)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
                    'contact_person, source_type, source_note, contract_path '
                    'FROM contact '
                    'WHERE supplier_telegram_id = ? AND name = ?'
                ),
                (telegram_id, name),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    def get_by_id(self, contact_id: int) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
                    'contact_person, source_type, source_note, contract_path '
                    'FROM contact '
                    'WHERE id = ?'
                ),
                (contact_id,),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    def get_by_id_for_supplier(self, *, telegram_id: int, contact_id: int) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            _assert_legacy_scope_unambiguous(connection, telegram_id)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
                    'contact_person, source_type, source_note, contract_path '
                    'FROM contact '
                    'WHERE id = ? AND supplier_telegram_id = ?'
                ),
                (contact_id, telegram_id),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    def get_by_name_case_insensitive(self, telegram_id: int, name: str) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            _assert_legacy_scope_unambiguous(connection, telegram_id)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
                    'contact_person, source_type, source_note, contract_path '
                    'FROM contact '
                    'WHERE supplier_telegram_id = ? AND lower(name) = lower(?)'
                ),
                (telegram_id, name),
            ).fetchone()

        if row is None:
            return None

        return self._row_to_profile(row)

    def create_contact(self, profile: ContactProfile) -> None:
        with managed_connection(self._db_path) as connection:
            has_workspace = _has_contact_workspace_column(connection)
            workspace_id = _clean_workspace_id(profile.workspace_id)
            if workspace_id is not None and not has_workspace:
                raise RuntimeError('workspace_contact_schema_migration_required')
            if workspace_id is None:
                _assert_legacy_scope_unambiguous(
                    connection,
                    profile.supplier_telegram_id,
                )
            columns = (
                'workspace_id, ' if has_workspace else ''
            ) + (
                'supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
                'contact_person, source_type, source_note, contract_path, '
                'created_at, updated_at'
            )
            placeholders = (
                '?, ' if has_workspace else ''
            ) + '?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP'
            values = _contact_values(profile, workspace_id, has_workspace)
            connection.execute(
                f'INSERT INTO contact ({columns}) VALUES ({placeholders})',
                values,
            )
            connection.commit()

    def create_or_replace(self, profile: ContactProfile) -> None:
        with managed_connection(self._db_path) as connection:
            has_workspace = _has_contact_workspace_column(connection)
            workspace_id = _clean_workspace_id(profile.workspace_id)
            if workspace_id is not None:
                if not has_workspace:
                    raise RuntimeError('workspace_contact_schema_migration_required')
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
                        'source_type=excluded.source_type, '
                        'source_note=excluded.source_note, '
                        'contract_path=excluded.contract_path, '
                        'updated_at=CURRENT_TIMESTAMP'
                    ),
                    _contact_values(profile, workspace_id, True),
                )
                connection.commit()
                return

            _assert_legacy_scope_unambiguous(
                connection,
                profile.supplier_telegram_id,
            )
            if not has_workspace:
                connection.execute(
                    (
                        'INSERT INTO contact '
                        '(supplier_telegram_id, name, ico, dic, ic_dph, address, '
                        'email, contact_person, source_type, source_note, contract_path, '
                        'created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
                        'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                        'ON CONFLICT(supplier_telegram_id, name) DO UPDATE SET '
                        'ico=excluded.ico, dic=excluded.dic, ic_dph=excluded.ic_dph, '
                        'address=excluded.address, email=excluded.email, '
                        'contact_person=excluded.contact_person, '
                        'source_type=excluded.source_type, '
                        'source_note=excluded.source_note, '
                        'contract_path=excluded.contract_path, '
                        'updated_at=CURRENT_TIMESTAMP'
                    ),
                    _contact_values(profile, None, False),
                )
                connection.commit()
                return

            row = connection.execute(
                (
                    'SELECT id FROM contact WHERE workspace_id IS NULL '
                    'AND supplier_telegram_id = ? AND name = ?'
                ),
                (profile.supplier_telegram_id, profile.name),
            ).fetchone()
            if row is None:
                connection.execute(
                    (
                        'INSERT INTO contact '
                        '(workspace_id, supplier_telegram_id, name, ico, dic, ic_dph, '
                        'address, email, contact_person, source_type, source_note, '
                        'contract_path, created_at, updated_at) '
                        'VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '
                        'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                    ),
                    _contact_values(profile, None, False),
                )
            else:
                connection.execute(
                    (
                        'UPDATE contact SET ico=?, dic=?, ic_dph=?, address=?, '
                        'email=?, contact_person=?, source_type=?, source_note=?, '
                        'contract_path=?, updated_at=CURRENT_TIMESTAMP WHERE id=?'
                    ),
                    (
                        profile.ico,
                        profile.dic,
                        profile.ic_dph,
                        profile.address,
                        profile.email,
                        profile.contact_person,
                        profile.source_type,
                        profile.source_note,
                        profile.contract_path,
                        int(row[0]),
                    ),
                )
            connection.commit()
    @staticmethod
    def _normalize_lookup_tokens(value: str) -> list[str]:
        lowered = value.casefold().strip()
        if not lowered:
            return []

        separators_normalized = re.sub(r'[.,\-/]+', ' ', lowered)
        collapsed = re.sub(r'\s+', ' ', separators_normalized).strip()
        if not collapsed:
            return []

        # token boundaries only; avoid removing fragments inside meaningful words
        tokens = re.findall(r'[0-9a-zA-ZÀ-žЀ-ӿ]+', collapsed)
        return tokens

    @staticmethod
    def _strip_legal_suffix_tokens(tokens: list[str]) -> list[str]:
        if not tokens:
            return tokens

        suffix_patterns: list[list[str]] = [
            ['spol', 's', 'r', 'o'],
            ['spol', 'sro'],
            ['s', 'r', 'o'],
            ['a', 's'],
            ['sro'],
            ['as'],
        ]

        current = list(tokens)
        while current:
            matched = False
            for pattern in suffix_patterns:
                if len(current) >= len(pattern) and current[-len(pattern):] == pattern:
                    current = current[:-len(pattern)]
                    matched = True
                    break
            if not matched:
                break

        return current if current else tokens

    @classmethod
    def normalize_lookup_forms(cls, value: str) -> tuple[str, str]:
        tokens = cls._normalize_lookup_tokens(value)
        stripped_tokens = cls._strip_legal_suffix_tokens(tokens)
        normalized = ' '.join(stripped_tokens)
        compressed = ''.join(stripped_tokens)
        return normalized, compressed

    @classmethod
    def _strip_trailing_country_tokens(cls, tokens: list[str]) -> list[str]:
        current = list(tokens)
        while current and current[-1] in cls._TRAILING_COUNTRY_TOKENS:
            current = current[:-1]
        return current if current else tokens

    @classmethod
    def _lookup_tokens_without_legal_suffix(cls, value: str) -> list[str]:
        return cls._strip_legal_suffix_tokens(cls._normalize_lookup_tokens(value))

    @classmethod
    def _has_trailing_country_token(cls, tokens: list[str]) -> bool:
        return bool(tokens) and tokens[-1] in cls._TRAILING_COUNTRY_TOKENS

    @classmethod
    def _country_sensitive_close_match(cls, query: str, profile_name: str) -> bool:
        forms = cls._country_sensitive_base_forms(query, profile_name)
        if forms is None:
            return False
        query_compressed, profile_compressed = forms
        return bool(query_compressed and profile_compressed and query_compressed == profile_compressed)

    @classmethod
    def _country_sensitive_base_forms(cls, query: str, profile_name: str) -> tuple[str, str] | None:
        query_tokens = cls._lookup_tokens_without_legal_suffix(query)
        profile_tokens = cls._lookup_tokens_without_legal_suffix(profile_name)
        if not query_tokens or not profile_tokens:
            return None

        query_has_country = cls._has_trailing_country_token(query_tokens)
        profile_has_country = cls._has_trailing_country_token(profile_tokens)
        if query_has_country:
            if not profile_has_country or query_tokens[-1] != profile_tokens[-1]:
                return None
            query_base = query_tokens[:-1]
            profile_base = profile_tokens[:-1]
        else:
            query_base = query_tokens
            profile_base = cls._strip_trailing_country_tokens(profile_tokens)

        query_compressed = ''.join(query_base)
        profile_compressed = ''.join(profile_base)
        if not query_compressed or not profile_compressed:
            return None
        return query_compressed, profile_compressed

    @classmethod
    def _country_sensitive_fuzzy_ratio(cls, query: str, profile_name: str) -> float:
        forms = cls._country_sensitive_base_forms(query, profile_name)
        if forms is None:
            return 0.0
        query_compressed, profile_compressed = forms
        if (
            len(query_compressed) < cls._MIN_FUZZY_COMPRESSED_LENGTH
            or len(profile_compressed) < cls._MIN_FUZZY_COMPRESSED_LENGTH
        ):
            return 0.0
        return SequenceMatcher(None, query_compressed, profile_compressed).ratio()

    @classmethod
    def _high_confidence_fuzzy_candidates(
        cls,
        query: str,
        profiles: list[ContactProfile],
    ) -> list[ContactProfile]:
        scored: list[tuple[float, ContactProfile]] = []
        for profile in profiles:
            ratio = cls._country_sensitive_fuzzy_ratio(query, profile.name)
            if ratio >= cls._HIGH_CONFIDENCE_FUZZY_RATIO:
                scored.append((ratio, profile))

        scored.sort(key=lambda item: (-item[0], item[1].name.casefold()))
        return [profile for _ratio, profile in scored]

    def create_confirmed_contact_alias(
        self,
        *,
        supplier_telegram_id: int,
        alias_text: str,
        contact_id: int,
        source: str,
    ) -> None:
        normalized, compressed = self.normalize_lookup_forms(alias_text)
        if not normalized or not compressed:
            return
        if self.get_by_id_for_supplier(
            telegram_id=supplier_telegram_id,
            contact_id=contact_id,
        ) is None:
            raise ValueError(
                'Cannot create contact alias for a contact outside the supplier scope.'
            )

        with managed_connection(self._db_path) as connection:
            alias_has_workspace = _has_alias_workspace_column(connection)
            if not alias_has_workspace:
                connection.execute(
                    (
                        'INSERT INTO confirmed_semantic_alias '
                        '(supplier_telegram_id, domain, alias_text, alias_normalized, '
                        'alias_compressed, target_type, target_id, source, created_at, '
                        'updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, '
                        'CURRENT_TIMESTAMP) '
                        'ON CONFLICT(supplier_telegram_id, domain, target_type, '
                        'alias_normalized) DO UPDATE SET '
                        'alias_text=excluded.alias_text, '
                        'alias_compressed=excluded.alias_compressed, '
                        'target_id=excluded.target_id, source=excluded.source, '
                        'updated_at=CURRENT_TIMESTAMP'
                    ),
                    (
                        supplier_telegram_id,
                        self._CONTACT_ALIAS_DOMAIN,
                        alias_text.strip(),
                        normalized,
                        compressed,
                        self._CONTACT_ALIAS_TARGET_TYPE,
                        contact_id,
                        source,
                    ),
                )
                connection.commit()
                return

            row = connection.execute(
                (
                    'SELECT id FROM confirmed_semantic_alias '
                    'WHERE workspace_id IS NULL AND supplier_telegram_id = ? '
                    'AND domain = ? AND target_type = ? AND alias_normalized = ?'
                ),
                (
                    supplier_telegram_id,
                    self._CONTACT_ALIAS_DOMAIN,
                    self._CONTACT_ALIAS_TARGET_TYPE,
                    normalized,
                ),
            ).fetchone()
            if row is None:
                connection.execute(
                    (
                        'INSERT INTO confirmed_semantic_alias '
                        '(workspace_id, supplier_telegram_id, domain, alias_text, '
                        'alias_normalized, alias_compressed, target_type, target_id, '
                        'source, created_at, updated_at) '
                        'VALUES (NULL, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, '
                        'CURRENT_TIMESTAMP)'
                    ),
                    (
                        supplier_telegram_id,
                        self._CONTACT_ALIAS_DOMAIN,
                        alias_text.strip(),
                        normalized,
                        compressed,
                        self._CONTACT_ALIAS_TARGET_TYPE,
                        contact_id,
                        source,
                    ),
                )
            else:
                connection.execute(
                    (
                        'UPDATE confirmed_semantic_alias SET alias_text=?, '
                        'alias_compressed=?, target_id=?, source=?, '
                        'updated_at=CURRENT_TIMESTAMP WHERE id=?'
                    ),
                    (
                        alias_text.strip(),
                        compressed,
                        contact_id,
                        source,
                        int(row[0]),
                    ),
                )
            connection.commit()
    def _find_contact_by_confirmed_alias(
        self,
        *,
        telegram_id: int,
        normalized: str,
        compressed: str,
    ) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT c.id, c.supplier_telegram_id, c.name, c.ico, c.dic, c.ic_dph, '
                    'c.address, c.email, c.contact_person, c.source_type, c.source_note, c.contract_path '
                    'FROM confirmed_semantic_alias a '
                    'JOIN contact c ON c.id = a.target_id AND c.supplier_telegram_id = a.supplier_telegram_id '
                    'WHERE a.supplier_telegram_id = ? '
                    'AND a.domain = ? '
                    'AND a.target_type = ? '
                    'AND (a.alias_normalized = ? OR a.alias_compressed = ?) '
                    'LIMIT 2'
                ),
                (
                    telegram_id,
                    self._CONTACT_ALIAS_DOMAIN,
                    self._CONTACT_ALIAS_TARGET_TYPE,
                    normalized,
                    compressed,
                ),
            ).fetchall()

        if len(row) != 1:
            return None
        return self._row_to_profile(row[0])

    def resolve_contact_lookup(self, telegram_id: int, name: str) -> ContactLookupResult:
        raw_query = name.strip()

        exact = self.get_by_name(telegram_id, raw_query)
        if exact is not None:
            normalized, compressed = self.normalize_lookup_forms(raw_query)
            return ContactLookupResult(
                state='exact_match',
                matched_contact=exact,
                candidates=[exact],
                raw_query=raw_query,
                normalized_query=normalized,
                compressed_query=compressed,
            )

        case_insensitive = self.get_by_name_case_insensitive(telegram_id, raw_query)
        if case_insensitive is not None:
            normalized, compressed = self.normalize_lookup_forms(raw_query)
            return ContactLookupResult(
                state='normalized_match',
                matched_contact=case_insensitive,
                candidates=[case_insensitive],
                raw_query=raw_query,
                normalized_query=normalized,
                compressed_query=compressed,
            )

        query_normalized, query_compressed = self.normalize_lookup_forms(raw_query)
        if not query_normalized and not query_compressed:
            return ContactLookupResult(
                state='no_match',
                matched_contact=None,
                candidates=[],
                raw_query=raw_query,
                normalized_query=query_normalized,
                compressed_query=query_compressed,
            )

        alias_match = self._find_contact_by_confirmed_alias(
            telegram_id=telegram_id,
            normalized=query_normalized,
            compressed=query_compressed,
        )
        if alias_match is not None:
            return ContactLookupResult(
                state='alias_match',
                matched_contact=alias_match,
                candidates=[alias_match],
                raw_query=raw_query,
                normalized_query=query_normalized,
                compressed_query=query_compressed,
            )

        supplier_profiles = self.get_all_by_supplier(telegram_id)
        candidates: list[ContactProfile] = []
        for profile in supplier_profiles:
            profile_normalized, profile_compressed = self.normalize_lookup_forms(profile.name)
            is_match = False
            if query_normalized and profile_normalized and query_normalized == profile_normalized:
                is_match = True
            elif query_compressed and profile_compressed and query_compressed == profile_compressed:
                is_match = True

            if is_match:
                candidates.append(profile)

        if len(candidates) == 1:
            return ContactLookupResult(
                state='normalized_match',
                matched_contact=candidates[0],
                candidates=candidates,
                raw_query=raw_query,
                normalized_query=query_normalized,
                compressed_query=query_compressed,
            )

        if len(candidates) > 1:
            return ContactLookupResult(
                state='multiple_candidates',
                matched_contact=None,
                candidates=candidates,
                raw_query=raw_query,
                normalized_query=query_normalized,
                compressed_query=query_compressed,
            )

        fuzzy_candidates = self._high_confidence_fuzzy_candidates(raw_query, supplier_profiles)
        if len(fuzzy_candidates) == 1:
            return ContactLookupResult(
                state='fuzzy_match',
                matched_contact=fuzzy_candidates[0],
                candidates=fuzzy_candidates,
                raw_query=raw_query,
                normalized_query=query_normalized,
                compressed_query=query_compressed,
            )

        if len(fuzzy_candidates) > 1:
            return ContactLookupResult(
                state='multiple_candidates',
                matched_contact=None,
                candidates=fuzzy_candidates,
                raw_query=raw_query,
                normalized_query=query_normalized,
                compressed_query=query_compressed,
            )

        return ContactLookupResult(
            state='no_match',
            matched_contact=None,
            candidates=[],
            raw_query=raw_query,
            normalized_query=query_normalized,
            compressed_query=query_compressed,
        )

    @staticmethod
    def _row_to_profile(row: sqlite3.Row) -> ContactProfile:
        return ContactProfile(
            supplier_telegram_id=row['supplier_telegram_id'],
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
            id=row['id'],
            workspace_id=(row['workspace_id'] if 'workspace_id' in row.keys() else None),
        )


def _has_contact_workspace_column(connection: sqlite3.Connection) -> bool:
    return any(
        row[1] == 'workspace_id'
        for row in connection.execute('PRAGMA table_info(contact)').fetchall()
    )


def _clean_workspace_id(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _assert_legacy_scope_unambiguous(
    connection: sqlite3.Connection,
    telegram_id: int,
) -> None:
    supplier_columns = {
        row[1] for row in connection.execute('PRAGMA table_info(supplier)')
    }
    if 'workspace_id' not in supplier_columns:
        return
    count = int(
        connection.execute(
            'SELECT COUNT(*) FROM supplier WHERE telegram_id = ?',
            (telegram_id,),
        ).fetchone()[0]
    )
    if count > 1:
        raise RuntimeError('ambiguous_contact_scope_requires_workspace')


def _contact_values(
    profile: ContactProfile,
    workspace_id: str | None,
    include_workspace: bool,
) -> tuple[object, ...]:
    values: tuple[object, ...] = (
        profile.supplier_telegram_id,
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
    )
    return (workspace_id, *values) if include_workspace else values

def _has_alias_workspace_column(connection: sqlite3.Connection) -> bool:
    return any(
        row[1] == 'workspace_id'
        for row in connection.execute(
            'PRAGMA table_info(confirmed_semantic_alias)'
        ).fetchall()
    )