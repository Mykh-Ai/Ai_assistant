from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sqlite3


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
    smtp_host: str
    smtp_user: str
    smtp_pass: str
    days_due: int
    id: int | None = None


class SupplierService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def get_by_telegram_id(self, telegram_id: int) -> SupplierProfile | None:
        with sqlite3.connect(self._db_path) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT id, telegram_id, name, ico, dic, ic_dph, address, iban, swift, '
                    'email, smtp_host, smtp_user, smtp_pass, days_due '
                    'FROM supplier WHERE telegram_id = ?'
                ),
                (telegram_id,),
            ).fetchone()

        if row is None:
            return None

        return SupplierProfile(
            id=row['id'],
            telegram_id=row['telegram_id'],
            name=row['name'],
            ico=row['ico'],
            dic=row['dic'],
            ic_dph=row['ic_dph'],
            address=row['address'],
            iban=row['iban'],
            swift=row['swift'],
            email=row['email'],
            smtp_host=row['smtp_host'],
            smtp_user=row['smtp_user'],
            smtp_pass=row['smtp_pass'],
            days_due=row['days_due'],
        )

    def create_or_replace(self, profile: SupplierProfile) -> None:
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                (
                    'INSERT INTO supplier '
                    '(telegram_id, name, ico, dic, ic_dph, address, iban, swift, email, '
                    'smtp_host, smtp_user, smtp_pass, days_due, created_at, updated_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(telegram_id) DO UPDATE SET '
                    'name=excluded.name, ico=excluded.ico, dic=excluded.dic, ic_dph=excluded.ic_dph, '
                    'address=excluded.address, iban=excluded.iban, swift=excluded.swift, email=excluded.email, '
                    'smtp_host=excluded.smtp_host, smtp_user=excluded.smtp_user, smtp_pass=excluded.smtp_pass, '
                    'days_due=excluded.days_due, updated_at=CURRENT_TIMESTAMP'
                ),
                (
                    profile.telegram_id,
                    profile.name,
                    profile.ico,
                    profile.dic,
                    profile.ic_dph,
                    profile.address,
                    profile.iban,
                    profile.swift,
                    profile.email,
                    profile.smtp_host,
                    profile.smtp_user,
                    profile.smtp_pass,
                    profile.days_due,
                ),
            )
            connection.commit()

    def update_profile(self, profile: SupplierProfile) -> None:
        self.create_or_replace(profile)
