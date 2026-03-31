from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS supplier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL UNIQUE,
    name TEXT NOT NULL,
    ico TEXT NOT NULL,
    dic TEXT NOT NULL,
    ic_dph TEXT,
    address TEXT NOT NULL,
    iban TEXT NOT NULL,
    swift TEXT NOT NULL,
    email TEXT NOT NULL,
    smtp_host TEXT NOT NULL,
    smtp_user TEXT NOT NULL,
    smtp_pass TEXT NOT NULL,
    days_due INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'telegram_id': 'INTEGER NOT NULL UNIQUE',
    'name': 'TEXT NOT NULL',
    'ico': 'TEXT NOT NULL',
    'dic': 'TEXT NOT NULL',
    'ic_dph': 'TEXT',
    'address': 'TEXT NOT NULL',
    'iban': 'TEXT NOT NULL',
    'swift': 'TEXT NOT NULL',
    'email': 'TEXT NOT NULL',
    'smtp_host': 'TEXT NOT NULL',
    'smtp_user': 'TEXT NOT NULL',
    'smtp_pass': 'TEXT NOT NULL',
    'days_due': 'INTEGER NOT NULL',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}


def _bootstrap_supplier_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(supplier)')
    }

    if not existing_columns:
        connection.execute(SCHEMA)
        return

    if set(existing_columns.keys()) == set(EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table supplier. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )



def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        _bootstrap_supplier_table(connection)
        connection.commit()
