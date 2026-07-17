from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3
from typing import Literal

from bot.services.contact_service import ContactProfile
from bot.services.db import managed_connection
from bot.services.validation import validate_contact_address, validate_dic, validate_ico
from bot.services.workspace_context import WorkspaceContext


RegistrySaveMode = Literal['insert', 'update', 'name_conflict', 'split_conflict', 'ico_conflict']


class RegistryContactConflict(RuntimeError):
    pass


@dataclass(frozen=True)
class RegistryContactDraft:
    name: str
    ico: str
    dic: str
    ic_dph: str | None
    address: str
    email: str | None
    iban: str | None
    contact_person: str | None
    provider_sources: tuple[str, ...]
    email_supplied: bool = False
    iban_supplied: bool = False
    contact_person_supplied: bool = False


@dataclass(frozen=True)
class RegistrySaveInspection:
    mode: RegistrySaveMode
    existing: ContactProfile | None


@dataclass(frozen=True)
class RegistrySaveResult:
    mode: Literal['insert', 'update']
    contact: ContactProfile


class RegistryContactSaveService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def inspect(self, context: WorkspaceContext, draft: RegistryContactDraft) -> RegistrySaveInspection:
        self._validate_draft(draft)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            return self._inspect_connection(connection, context, draft)

    def save(self, context: WorkspaceContext, draft: RegistryContactDraft) -> RegistrySaveResult:
        self._validate_draft(draft)
        with managed_connection(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            inspection = self._inspect_connection(connection, context, draft)
            if inspection.mode in {'name_conflict', 'split_conflict', 'ico_conflict'}:
                raise RegistryContactConflict(inspection.mode)

            source_note = ','.join(sorted(set(draft.provider_sources)))[:200]
            if inspection.mode == 'insert':
                cursor = connection.execute(
                    (
                        'INSERT INTO contact '
                        '(workspace_id, supplier_telegram_id, name, ico, dic, ic_dph, address, '
                        'email, iban, contact_person, source_type, source_note, contract_path, '
                        'created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, '
                        'CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                    ),
                    (
                        context.workspace_id,
                        context.actor_telegram_id,
                        draft.name,
                        draft.ico,
                        draft.dic,
                        draft.ic_dph,
                        draft.address,
                        draft.email or '',
                        draft.iban,
                        draft.contact_person,
                        'registry',
                        source_note,
                    ),
                )
                contact_id = int(cursor.lastrowid)
                mode: Literal['insert', 'update'] = 'insert'
            else:
                existing = inspection.existing
                if existing is None or existing.id is None:
                    raise RegistryContactConflict('registry_existing_contact_missing')
                email = draft.email if draft.email_supplied else existing.email
                iban = draft.iban if draft.iban_supplied else existing.iban
                contact_person = (
                    draft.contact_person
                    if draft.contact_person_supplied
                    else existing.contact_person
                )
                ic_dph = draft.ic_dph if draft.ic_dph is not None else existing.ic_dph
                connection.execute(
                    (
                        'UPDATE contact SET supplier_telegram_id=?, name=?, ico=?, dic=?, '
                        'ic_dph=?, address=?, email=?, iban=?, contact_person=?, '
                        'source_type=?, source_note=?, updated_at=CURRENT_TIMESTAMP '
                        'WHERE id=? AND workspace_id=?'
                    ),
                    (
                        context.actor_telegram_id,
                        draft.name,
                        draft.ico,
                        draft.dic,
                        ic_dph,
                        draft.address,
                        email or '',
                        iban,
                        contact_person,
                        'registry',
                        source_note,
                        existing.id,
                        context.workspace_id,
                    ),
                )
                contact_id = existing.id
                mode = 'update'

            row = connection.execute(
                f'{_CONTACT_SELECT} WHERE id = ? AND workspace_id = ?',
                (contact_id, context.workspace_id),
            ).fetchone()
            if row is None:
                raise RuntimeError('registry_contact_save_failed')
            connection.commit()
            return RegistrySaveResult(mode=mode, contact=_row_to_profile(row))

    @staticmethod
    def _inspect_connection(
        connection: sqlite3.Connection,
        context: WorkspaceContext,
        draft: RegistryContactDraft,
    ) -> RegistrySaveInspection:
        ico_rows = connection.execute(
            f'{_CONTACT_SELECT} WHERE workspace_id = ? AND ico = ? ORDER BY id',
            (context.workspace_id, draft.ico),
        ).fetchall()
        if len(ico_rows) > 1:
            return RegistrySaveInspection(mode='ico_conflict', existing=None)
        name_row = connection.execute(
            f'{_CONTACT_SELECT} WHERE workspace_id = ? AND name = ?',
            (context.workspace_id, draft.name),
        ).fetchone()
        ico_row = ico_rows[0] if ico_rows else None
        if ico_row is not None and name_row is not None and int(ico_row['id']) != int(name_row['id']):
            return RegistrySaveInspection(mode='split_conflict', existing=None)
        if ico_row is not None:
            return RegistrySaveInspection(mode='update', existing=_row_to_profile(ico_row))
        if name_row is not None:
            return RegistrySaveInspection(mode='name_conflict', existing=_row_to_profile(name_row))
        return RegistrySaveInspection(mode='insert', existing=None)

    @staticmethod
    def _validate_draft(draft: RegistryContactDraft) -> None:
        if not draft.name.strip():
            raise ValueError('registry_contact_name_required')
        if not validate_ico(draft.ico):
            raise ValueError('registry_contact_ico_invalid')
        if not validate_dic(draft.dic):
            raise ValueError('registry_contact_dic_invalid')
        if not validate_contact_address(draft.address):
            raise ValueError('registry_contact_address_invalid')


_CONTACT_SELECT = (
    'SELECT id, workspace_id, supplier_telegram_id, name, ico, dic, ic_dph, '
    'address, email, iban, contact_person, source_type, source_note, contract_path '
    'FROM contact'
)


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
        iban=row['iban'],
        contact_person=row['contact_person'],
        source_type=row['source_type'],
        source_note=row['source_note'],
        contract_path=row['contract_path'],
    )