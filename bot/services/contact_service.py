from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3

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


class ContactService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def get_all_by_supplier(self, telegram_id: int) -> list[ContactProfile]:
        with managed_connection(self._db_path) as connection:
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

    def get_by_name_case_insensitive(self, telegram_id: int, name: str) -> ContactProfile | None:
        with managed_connection(self._db_path) as connection:
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
            connection.execute(
                (
                    'INSERT INTO contact '
                    '(supplier_telegram_id, name, ico, dic, ic_dph, address, email, contact_person, '
                    'source_type, source_note, contract_path, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)'
                ),
                (
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
                ),
            )
            connection.commit()

    def create_or_replace(self, profile: ContactProfile) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO contact '
                    '(supplier_telegram_id, name, ico, dic, ic_dph, address, email, contact_person, '
                    'source_type, source_note, contract_path, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(supplier_telegram_id, name) DO UPDATE SET '
                    'ico=excluded.ico, '
                    'dic=excluded.dic, '
                    'ic_dph=excluded.ic_dph, '
                    'address=excluded.address, '
                    'email=excluded.email, '
                    'contact_person=excluded.contact_person, '
                    'source_type=excluded.source_type, '
                    'source_note=excluded.source_note, '
                    'contract_path=excluded.contract_path, '
                    'updated_at=CURRENT_TIMESTAMP'
                ),
                (
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
                ),
            )
            connection.commit()

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
        )
