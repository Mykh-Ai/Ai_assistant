from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
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
    smtp_host TEXT,
    smtp_user TEXT,
    smtp_pass TEXT,
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
    invoice_number TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    delivery_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    due_days INTEGER NOT NULL,
    total_amount REAL NOT NULL,
    currency TEXT NOT NULL,
    status TEXT NOT NULL,
    pdf_path TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_telegram_id, invoice_number)
);
"""

INVOICE_ITEM_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    description_raw TEXT NOT NULL,
    description_normalized TEXT,
    item_description_raw TEXT,
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

ACCESS_REQUEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS access_requests (
    telegram_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    last_name TEXT,
    status TEXT NOT NULL,
    requested_at TEXT NOT NULL,
    decided_at TEXT,
    decided_by INTEGER
);
"""

AUTHORIZED_USER_SCHEMA = """
CREATE TABLE IF NOT EXISTS authorized_users (
    telegram_id INTEGER PRIMARY KEY,
    role TEXT NOT NULL DEFAULT 'user',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    approved_by INTEGER
);
"""

INVOICE_NUMBER_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice_number_settings (
    supplier_telegram_id INTEGER NOT NULL,
    issue_year INTEGER NOT NULL,
    first_invoice_number TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_telegram_id, issue_year)
);
"""

CONFIRMED_SEMANTIC_ALIAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS confirmed_semantic_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    supplier_telegram_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    alias_text TEXT NOT NULL,
    alias_normalized TEXT NOT NULL,
    alias_compressed TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_telegram_id, domain, target_type, alias_normalized)
);
"""

CUSTOMIZATION_REQUEST_SCHEMA = """
CREATE TABLE IF NOT EXISTS customization_requests (
    request_id TEXT PRIMARY KEY,
    telegram_id INTEGER NOT NULL,
    supplier_telegram_id INTEGER,
    workspace_id TEXT,
    source_channel TEXT NOT NULL,
    source_triage_class TEXT NOT NULL,
    source_capability_id TEXT,
    source_topic_id TEXT,
    normalized_title TEXT NOT NULL,
    normalized_summary TEXT NOT NULL,
    redacted_original_text TEXT,
    raw_text_hash TEXT,
    language_hint TEXT,
    confidence REAL,
    status TEXT NOT NULL,
    risk_level TEXT,
    requires_human_approval INTEGER NOT NULL DEFAULT 1,
    product_truth_relation TEXT,
    privacy_redaction_flags TEXT,
    admin_note TEXT,
    reviewed_by INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    reviewed_at TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1
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
    'smtp_host': 'TEXT',
    'smtp_user': 'TEXT',
    'smtp_pass': 'TEXT',
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
    'item_description_raw': 'TEXT',
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

ACCESS_REQUEST_EXPECTED_COLUMNS = {
    'telegram_id': 'INTEGER PRIMARY KEY',
    'username': 'TEXT',
    'first_name': 'TEXT',
    'last_name': 'TEXT',
    'status': 'TEXT NOT NULL',
    'requested_at': 'TEXT NOT NULL',
    'decided_at': 'TEXT',
    'decided_by': 'INTEGER',
}

AUTHORIZED_USER_EXPECTED_COLUMNS = {
    'telegram_id': 'INTEGER PRIMARY KEY',
    'role': 'TEXT NOT NULL',
    'status': 'TEXT NOT NULL',
    'created_at': 'TEXT NOT NULL',
    'approved_by': 'INTEGER',
}

INVOICE_NUMBER_SETTINGS_EXPECTED_COLUMNS = {
    'supplier_telegram_id': 'INTEGER NOT NULL',
    'issue_year': 'INTEGER NOT NULL',
    'first_invoice_number': 'TEXT NOT NULL',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}

CONFIRMED_SEMANTIC_ALIAS_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'supplier_telegram_id': 'INTEGER NOT NULL',
    'domain': 'TEXT NOT NULL',
    'alias_text': 'TEXT NOT NULL',
    'alias_normalized': 'TEXT NOT NULL',
    'alias_compressed': 'TEXT NOT NULL',
    'target_type': 'TEXT NOT NULL',
    'target_id': 'INTEGER NOT NULL',
    'source': 'TEXT NOT NULL',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}

CUSTOMIZATION_REQUEST_EXPECTED_COLUMNS = {
    'request_id': 'TEXT PRIMARY KEY',
    'telegram_id': 'INTEGER NOT NULL',
    'supplier_telegram_id': 'INTEGER',
    'workspace_id': 'TEXT',
    'source_channel': 'TEXT NOT NULL',
    'source_triage_class': 'TEXT NOT NULL',
    'source_capability_id': 'TEXT',
    'source_topic_id': 'TEXT',
    'normalized_title': 'TEXT NOT NULL',
    'normalized_summary': 'TEXT NOT NULL',
    'redacted_original_text': 'TEXT',
    'raw_text_hash': 'TEXT',
    'language_hint': 'TEXT',
    'confidence': 'REAL',
    'status': 'TEXT NOT NULL',
    'risk_level': 'TEXT',
    'requires_human_approval': 'INTEGER NOT NULL',
    'product_truth_relation': 'TEXT',
    'privacy_redaction_flags': 'TEXT',
    'admin_note': 'TEXT',
    'reviewed_by': 'INTEGER',
    'created_at': 'TEXT NOT NULL',
    'updated_at': 'TEXT NOT NULL',
    'confirmed_at': 'TEXT',
    'reviewed_at': 'TEXT',
    'schema_version': 'INTEGER NOT NULL',
}


def _bootstrap_supplier_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(supplier)')
    }

    if not existing_columns:
        connection.execute(SUPPLIER_SCHEMA)
        return

    if set(existing_columns.keys()) == set(SUPPLIER_EXPECTED_COLUMNS.keys()):
        _ensure_supplier_smtp_nullable(connection)
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
        _ensure_invoice_tenant_unique_index(connection)
        return

    raise RuntimeError(
        'Incompatible local schema for table invoice. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _ensure_supplier_smtp_nullable(connection: sqlite3.Connection) -> None:
    table_info = connection.execute('PRAGMA table_info(supplier)').fetchall()
    column_by_name = {row[1]: row for row in table_info}
    if not any(column_by_name[column_name][3] for column_name in ('smtp_host', 'smtp_user', 'smtp_pass')):
        return

    connection.execute('ALTER TABLE supplier RENAME TO supplier_legacy_smtp_notnull')
    connection.execute(SUPPLIER_SCHEMA)
    connection.execute(
        (
            'INSERT INTO supplier '
            '(id, telegram_id, name, ico, dic, ic_dph, address, iban, swift, email, '
            'smtp_host, smtp_user, smtp_pass, days_due, created_at, updated_at) '
            'SELECT id, telegram_id, name, ico, dic, ic_dph, address, iban, swift, email, '
            'smtp_host, smtp_user, smtp_pass, days_due, created_at, updated_at '
            'FROM supplier_legacy_smtp_notnull'
        )
    )
    connection.execute('DROP TABLE supplier_legacy_smtp_notnull')


def _ensure_invoice_tenant_unique_index(connection: sqlite3.Connection) -> None:
    index_rows = connection.execute('PRAGMA index_list(invoice)').fetchall()
    unique_indexes = [row for row in index_rows if row[2]]
    has_tenant_unique = False
    has_global_invoice_number_unique = False
    for index_row in unique_indexes:
        index_name = index_row[1]
        columns = [
            info_row[2]
            for info_row in connection.execute(f'PRAGMA index_info({index_name})').fetchall()
        ]
        if columns == ['supplier_telegram_id', 'invoice_number']:
            has_tenant_unique = True
        if columns == ['invoice_number']:
            has_global_invoice_number_unique = True

    if has_tenant_unique and not has_global_invoice_number_unique:
        return

    if has_global_invoice_number_unique:
        _migrate_invoice_global_unique_to_tenant_unique(connection)
        return

    connection.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_supplier_number '
        'ON invoice (supplier_telegram_id, invoice_number)'
    )


def _migrate_invoice_global_unique_to_tenant_unique(connection: sqlite3.Connection) -> None:
    connection.execute('ALTER TABLE invoice RENAME TO invoice_legacy_global_unique')
    connection.execute(INVOICE_SCHEMA)
    connection.execute(
        (
            'INSERT INTO invoice '
            '(id, supplier_telegram_id, contact_id, invoice_number, issue_date, delivery_date, due_date, '
            'due_days, total_amount, currency, status, pdf_path, created_at, updated_at) '
            'SELECT id, supplier_telegram_id, contact_id, invoice_number, issue_date, delivery_date, due_date, '
            'due_days, total_amount, currency, status, pdf_path, created_at, updated_at '
            'FROM invoice_legacy_global_unique'
        )
    )
    connection.execute('DROP TABLE invoice_legacy_global_unique')


def _bootstrap_invoice_item_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(invoice_item)')
    }

    if not existing_columns:
        connection.execute(INVOICE_ITEM_SCHEMA)
        return

    if set(existing_columns.keys()) == set(INVOICE_ITEM_EXPECTED_COLUMNS.keys()):
        return

    legacy_columns_without_item_detail = {
        'id',
        'invoice_id',
        'description_raw',
        'description_normalized',
        'quantity',
        'unit',
        'unit_price',
        'total_price',
    }
    if set(existing_columns.keys()) == legacy_columns_without_item_detail:
        connection.execute('ALTER TABLE invoice_item ADD COLUMN item_description_raw TEXT')
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


def _bootstrap_access_request_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(access_requests)')
    }

    if not existing_columns:
        connection.execute(ACCESS_REQUEST_SCHEMA)
        return

    if set(existing_columns.keys()) == set(ACCESS_REQUEST_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table access_requests. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_authorized_user_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(authorized_users)')
    }

    if not existing_columns:
        connection.execute(AUTHORIZED_USER_SCHEMA)
        return

    if set(existing_columns.keys()) == set(AUTHORIZED_USER_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table authorized_users. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_invoice_number_settings_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(invoice_number_settings)')
    }

    if not existing_columns:
        connection.execute(INVOICE_NUMBER_SETTINGS_SCHEMA)
        return

    if set(existing_columns.keys()) == set(INVOICE_NUMBER_SETTINGS_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table invoice_number_settings. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_confirmed_semantic_alias_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(confirmed_semantic_alias)')
    }

    if not existing_columns:
        connection.execute(CONFIRMED_SEMANTIC_ALIAS_SCHEMA)
        return

    if set(existing_columns.keys()) == set(CONFIRMED_SEMANTIC_ALIAS_EXPECTED_COLUMNS.keys()):
        return

    raise RuntimeError(
        'Incompatible local schema for table confirmed_semantic_alias. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _bootstrap_customization_request_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(customization_requests)')
    }

    if not existing_columns:
        connection.execute(CUSTOMIZATION_REQUEST_SCHEMA)
        _ensure_customization_request_indexes(connection)
        return

    if set(existing_columns.keys()) == set(CUSTOMIZATION_REQUEST_EXPECTED_COLUMNS.keys()):
        _ensure_customization_request_indexes(connection)
        return

    raise RuntimeError(
        'Incompatible local schema for table customization_requests. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def ensure_customization_request_schema(connection: sqlite3.Connection) -> None:
    _bootstrap_customization_request_table(connection)


def _ensure_customization_request_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_customization_requests_user_status_created '
        'ON customization_requests (telegram_id, status, created_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_customization_requests_supplier_status_created '
        'ON customization_requests (supplier_telegram_id, status, created_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_customization_requests_status_created '
        'ON customization_requests (status, created_at)'
    )


@contextmanager
def managed_connection(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(db_path)
    try:
        yield connection
    finally:
        connection.close()


def init_db(db_path: Path) -> None:
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with managed_connection(db_path) as connection:
        _bootstrap_supplier_table(connection)
        _bootstrap_contact_table(connection)
        _bootstrap_invoice_table(connection)
        _bootstrap_invoice_item_table(connection)
        _bootstrap_supplier_service_alias_table(connection)
        _bootstrap_access_request_table(connection)
        _bootstrap_authorized_user_table(connection)
        _bootstrap_invoice_number_settings_table(connection)
        _bootstrap_confirmed_semantic_alias_table(connection)
        _bootstrap_customization_request_table(connection)
        connection.commit()
