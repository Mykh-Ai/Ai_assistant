from __future__ import annotations

import sqlite3
from pathlib import Path


SUPPLIER_SCHEMA = """
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

CONTACT_SCHEMA = """
CREATE TABLE IF NOT EXISTS contact (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_telegram_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    ico TEXT NOT NULL,
    dic TEXT NOT NULL,
    ic_dph TEXT,
    address TEXT NOT NULL,
    email TEXT NOT NULL,
    contact_person TEXT,
    source_type TEXT NOT NULL,
    source_note TEXT,
    contract_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_telegram_id, name)
);
"""

INVOICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_telegram_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    invoice_number TEXT NOT NULL UNIQUE,
    issue_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    due_days INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    pdf_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

INVOICE_ITEM_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    description_raw TEXT NOT NULL,
    description_normalized TEXT,
    quantity REAL NOT NULL,
    unit TEXT,
    unit_price REAL NOT NULL,
    total_price REAL NOT NULL
);
"""

SUPPLIER_SERVICE_ALIAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS supplier_service_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_id INTEGER NOT NULL,
    alias TEXT NOT NULL COLLATE NOCASE,
    canonical_title TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_id, alias)
);
"""

SUPPLIER_EXPECTED_COLUMNS = {
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

CONTACT_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'supplier_telegram_id': 'INTEGER NOT NULL',
    'name': 'TEXT NOT NULL',
    'ico': 'TEXT NOT NULL',
    'dic': 'TEXT NOT NULL',
    'ic_dph': 'TEXT',
    'address': 'TEXT NOT NULL',
    'email': 'TEXT NOT NULL',
    'contact_person': 'TEXT',
    'source_type': 'TEXT NOT NULL',
    'source_note': 'TEXT',
    'contract_path': 'TEXT',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}

INVOICE_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'supplier_telegram_id': 'INTEGER NOT NULL',
    'contact_id': 'INTEGER NOT NULL',
    'invoice_number': 'TEXT NOT NULL',
    'issue_date': 'TEXT NOT NULL',
    'delivery_date': 'TEXT NOT NULL',
    'due_date': 'TEXT NOT NULL',
    'due_days': 'INTEGER NOT NULL',
    'total_amount': 'REAL NOT NULL',
    'currency': 'TEXT NOT NULL',
    'status': 'TEXT NOT NULL',
    'pdf_path': 'TEXT',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}

INVOICE_ITEM_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'invoice_id': 'INTEGER NOT NULL',
    'description_raw': 'TEXT NOT NULL',
    'description_normalized': 'TEXT',
    'quantity': 'REAL NOT NULL',
    'unit': 'TEXT',
    'unit_price': 'REAL NOT NULL',
    'total_price': 'REAL NOT NULL',
}

SUPPLIER_SERVICE_ALIAS_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'supplier_id': 'INTEGER NOT NULL',
    'alias': 'TEXT NOT NULL',
    'canonical_title': 'TEXT NOT NULL',
    'is_active': 'INTEGER NOT NULL',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}


def _bootstrap_supplier_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(supplier)')
    }

    if not existing_columns:
        connection.execute(SUPPLIER_SCHEMA)
        return

    if set(existing_columns.keys()) == set(SUPPLIER_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table supplier. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_contact_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(contact)')
    }

    if not existing_columns:
        connection.execute(CONTACT_SCHEMA)
        return

    if set(existing_columns.keys()) == set(CONTACT_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table contact. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_invoice_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(invoice)')
    }

    if not existing_columns:
        connection.execute(INVOICE_SCHEMA)
        return

    if set(existing_columns.keys()) == set(INVOICE_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table invoice. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_invoice_item_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(invoice_item)')
    }

    if not existing_columns:
        connection.execute(INVOICE_ITEM_SCHEMA)
        return

    if set(existing_columns.keys()) == set(INVOICE_ITEM_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table invoice_item. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_supplier_service_alias_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(supplier_service_alias)')
    }

    if not existing_columns:
        connection.execute(SUPPLIER_SERVICE_ALIAS_SCHEMA)
        return

    if set(existing_columns.keys()) == set(SUPPLIER_SERVICE_ALIAS_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table supplier_service_alias. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        _bootstrap_supplier_table(connection)
        _bootstrap_contact_table(connection)
        _bootstrap_invoice_table(connection)
        _bootstrap_invoice_item_table(connection)
        _bootstrap_supplier_service_alias_table(connection)
        connection.commit()
