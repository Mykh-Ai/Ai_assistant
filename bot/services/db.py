from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
import sqlite3
from pathlib import Path


SUPPLIER_SCHEMA = """
CREATE TABLE IF NOT EXISTS supplier (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT UNIQUE,
    telegram_id INTEGER NOT NULL,
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

LEGACY_SUPPLIER_SCHEMA = """
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
    workspace_id TEXT,
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
    UNIQUE(workspace_id, name)
);
"""

INVOICE_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT,
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
    UNIQUE(workspace_id, invoice_number)
);
"""

LEGACY_INVOICE_SCHEMA = """
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

INVOICE_FOLLOWUP_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS invoice_followup_state (
    invoice_id INTEGER PRIMARY KEY,
    workspace_id TEXT,
    supplier_telegram_id INTEGER NOT NULL,
    payment_status TEXT NOT NULL DEFAULT 'unpaid',
    reminder_status TEXT NOT NULL DEFAULT 'active',
    remind_after TEXT,
    paid_at TEXT,
    muted_at TEXT,
    drive_archive_status TEXT NOT NULL DEFAULT 'stub_not_uploaded',
    drive_archive_note TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
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
    workspace_id TEXT,
    supplier_telegram_id INTEGER NOT NULL,
    issue_year INTEGER NOT NULL,
    first_invoice_number TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(workspace_id, issue_year)
);
"""

CONFIRMED_SEMANTIC_ALIAS_SCHEMA = """
CREATE TABLE IF NOT EXISTS confirmed_semantic_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT,
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
    UNIQUE(workspace_id, domain, target_type, alias_normalized)
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
    admin_response_text TEXT,
    response_kind TEXT,
    response_sent_at TEXT,
    response_sent_by INTEGER,
    response_delivery_status TEXT,
    response_attempts INTEGER NOT NULL DEFAULT 0,
    response_failed_reason TEXT,
    responded_to_request_status TEXT,
    response_updated_at TEXT,
    response_id TEXT,
    schema_version INTEGER NOT NULL DEFAULT 1
);
"""

ARCHIVE_JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_jobs (
    job_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    document_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    local_file_path TEXT NOT NULL,
    metadata_path TEXT,
    provider TEXT NOT NULL DEFAULT 'google_drive',
    target_folder_path TEXT,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 5,
    next_attempt_at TEXT,
    drive_file_id TEXT,
    drive_folder_id TEXT,
    error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    uploaded_at TEXT,
    locked_by TEXT,
    lease_until TEXT
);
"""

ACCOUNTING_DOCUMENT_ARCHIVE_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS accounting_document_archive_state (
    document_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    document_type TEXT NOT NULL,
    metadata_path TEXT,
    local_file_path TEXT NOT NULL,
    archive_status TEXT NOT NULL,
    latest_job_id TEXT,
    drive_file_id TEXT,
    drive_folder_id TEXT,
    uploaded_at TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (workspace_id, document_id)
);
"""

GOOGLE_DRIVE_CONNECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS google_drive_connections (
    connection_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL UNIQUE,
    telegram_id INTEGER NOT NULL,
    provider TEXT NOT NULL DEFAULT 'google_drive',
    status TEXT NOT NULL,
    google_subject TEXT,
    google_email TEXT,
    scopes_granted TEXT NOT NULL,
    token_ciphertext BLOB NOT NULL,
    token_key_id TEXT NOT NULL,
    token_version INTEGER NOT NULL DEFAULT 1,
    root_folder_id TEXT,
    root_folder_path TEXT,
    last_error_code TEXT,
    connected_at TEXT,
    revoked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

GOOGLE_DRIVE_FOLDER_CACHE_SCHEMA = """
CREATE TABLE IF NOT EXISTS google_drive_folder_cache (
    workspace_id TEXT NOT NULL,
    provider TEXT NOT NULL DEFAULT 'google_drive',
    folder_path TEXT NOT NULL,
    folder_id TEXT NOT NULL,
    parent_folder_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, provider, folder_path)
);
"""

GOOGLE_DRIVE_OAUTH_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS google_drive_oauth_states (
    state_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    state_token_hash TEXT NOT NULL UNIQUE,
    scopes_requested TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    last_error_code TEXT
);
"""

WORK_TIME_DAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_time_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id TEXT,
    telegram_id INTEGER NOT NULL,
    work_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    total_minutes INTEGER,
    status TEXT NOT NULL,
    source TEXT NOT NULL,
    note TEXT,
    gross_minutes INTEGER,
    lunch_break_minutes_snapshot INTEGER,
    net_work_minutes_override INTEGER,
    close_input_mode TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(workspace_id, work_date)
);
"""

WORK_TIME_SETTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_time_settings (
    workspace_id TEXT UNIQUE,
    telegram_id INTEGER NOT NULL,
    lunch_break_configured INTEGER NOT NULL DEFAULT 0,
    lunch_break_enabled INTEGER NOT NULL DEFAULT 0,
    lunch_break_minutes INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

WORK_TIME_EVENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_time_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_time_day_id INTEGER,
    workspace_id TEXT,
    telegram_id INTEGER,
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source_message_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

WORKSPACE_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace (
    workspace_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    storage_key TEXT NOT NULL UNIQUE,
    drive_folder_name TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

WORKSPACE_MEMBERSHIP_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_membership (
    workspace_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    role TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, telegram_id)
);
"""

ACTIVE_WORKSPACE_SELECTION_SCHEMA = """
CREATE TABLE IF NOT EXISTS active_workspace_selection (
    telegram_id INTEGER PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""
SUPPLIER_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'workspace_id': 'TEXT UNIQUE',
    'telegram_id': 'INTEGER NOT NULL',
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

SUPPLIER_LEGACY_EXPECTED_COLUMN_NAMES = set(SUPPLIER_EXPECTED_COLUMNS) - {'workspace_id'}

CONTACT_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'workspace_id': 'TEXT',
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

CONTACT_LEGACY_EXPECTED_COLUMN_NAMES = set(CONTACT_EXPECTED_COLUMNS) - {'workspace_id'}

INVOICE_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'workspace_id': 'TEXT',
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

INVOICE_LEGACY_EXPECTED_COLUMN_NAMES = set(INVOICE_EXPECTED_COLUMNS) - {'workspace_id'}

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

INVOICE_FOLLOWUP_STATE_EXPECTED_COLUMNS = {
    'invoice_id': 'INTEGER PRIMARY KEY',
    'workspace_id': 'TEXT',
    'supplier_telegram_id': 'INTEGER NOT NULL',
    'payment_status': 'TEXT NOT NULL',
    'reminder_status': 'TEXT NOT NULL',
    'remind_after': 'TEXT',
    'paid_at': 'TEXT',
    'muted_at': 'TEXT',
    'drive_archive_status': 'TEXT NOT NULL',
    'drive_archive_note': 'TEXT',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}

INVOICE_FOLLOWUP_STATE_LEGACY_EXPECTED_COLUMN_NAMES = (
    set(INVOICE_FOLLOWUP_STATE_EXPECTED_COLUMNS) - {'workspace_id'}
)

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
    'workspace_id': 'TEXT',
    'supplier_telegram_id': 'INTEGER NOT NULL',
    'issue_year': 'INTEGER NOT NULL',
    'first_invoice_number': 'TEXT NOT NULL',
    'created_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
    'updated_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
}

INVOICE_NUMBER_SETTINGS_LEGACY_EXPECTED_COLUMN_NAMES = set(INVOICE_NUMBER_SETTINGS_EXPECTED_COLUMNS) - {'workspace_id'}

CONFIRMED_SEMANTIC_ALIAS_EXPECTED_COLUMNS = {
    'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
    'workspace_id': 'TEXT',
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

CONFIRMED_SEMANTIC_ALIAS_LEGACY_EXPECTED_COLUMN_NAMES = set(CONFIRMED_SEMANTIC_ALIAS_EXPECTED_COLUMNS) - {'workspace_id'}

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
    'admin_response_text': 'TEXT',
    'response_kind': 'TEXT',
    'response_sent_at': 'TEXT',
    'response_sent_by': 'INTEGER',
    'response_delivery_status': 'TEXT',
    'response_attempts': 'INTEGER NOT NULL',
    'response_failed_reason': 'TEXT',
    'responded_to_request_status': 'TEXT',
    'response_updated_at': 'TEXT',
    'response_id': 'TEXT',
    'schema_version': 'INTEGER NOT NULL',
}

_CUSTOMIZATION_REQUEST_ADDITIVE_COLUMNS = {
    'admin_response_text': 'TEXT',
    'response_kind': 'TEXT',
    'response_sent_at': 'TEXT',
    'response_sent_by': 'INTEGER',
    'response_delivery_status': 'TEXT',
    'response_attempts': 'INTEGER NOT NULL DEFAULT 0',
    'response_failed_reason': 'TEXT',
    'responded_to_request_status': 'TEXT',
    'response_updated_at': 'TEXT',
    'response_id': 'TEXT',
}

_ARCHIVE_JOB_ADDITIVE_COLUMNS = {
    'locked_by': 'TEXT',
    'lease_until': 'TEXT',
}

_WORK_TIME_DAY_ADDITIVE_COLUMNS = {
    'gross_minutes': 'INTEGER',
    'lunch_break_minutes_snapshot': 'INTEGER',
    'net_work_minutes_override': 'INTEGER',
    'close_input_mode': 'TEXT',
}

def _bootstrap_supplier_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(supplier)')
    }

    if not existing_columns:
        connection.execute(SUPPLIER_SCHEMA)
        return

    existing_column_names = set(existing_columns.keys())
    if (
        existing_column_names == set(SUPPLIER_EXPECTED_COLUMNS.keys())
        or existing_column_names == SUPPLIER_LEGACY_EXPECTED_COLUMN_NAMES
    ):
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

    existing_column_names = set(existing_columns.keys())
    if (
        existing_column_names == set(CONTACT_EXPECTED_COLUMNS.keys())
        or existing_column_names == CONTACT_LEGACY_EXPECTED_COLUMN_NAMES
    ):
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

    existing_column_names = set(existing_columns.keys())
    if existing_column_names == set(INVOICE_EXPECTED_COLUMNS.keys()):
        _ensure_invoice_workspace_unique_index(connection)
        return
    if existing_column_names == INVOICE_LEGACY_EXPECTED_COLUMN_NAMES:
        _ensure_invoice_tenant_unique_index(connection)
        return

    raise RuntimeError(
        'Incompatible local schema for table invoice. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def _ensure_supplier_smtp_nullable(connection: sqlite3.Connection) -> None:
    table_info = connection.execute('PRAGMA table_info(supplier)').fetchall()
    column_by_name = {row[1]: row for row in table_info}
    if not any(
        column_by_name[column_name][3]
        for column_name in ('smtp_host', 'smtp_user', 'smtp_pass')
    ):
        return

    has_workspace_id = 'workspace_id' in column_by_name
    connection.execute('ALTER TABLE supplier RENAME TO supplier_legacy_smtp_notnull')
    connection.execute(SUPPLIER_SCHEMA if has_workspace_id else LEGACY_SUPPLIER_SCHEMA)
    if has_workspace_id:
        connection.execute(
            (
                'INSERT INTO supplier '
                '(id, workspace_id, telegram_id, name, ico, dic, ic_dph, address, '
                'iban, swift, email, smtp_host, smtp_user, smtp_pass, days_due, '
                'created_at, updated_at) '
                'SELECT id, workspace_id, telegram_id, name, ico, dic, ic_dph, '
                'address, iban, swift, email, smtp_host, smtp_user, smtp_pass, '
                'days_due, created_at, updated_at '
                'FROM supplier_legacy_smtp_notnull'
            )
        )
    else:
        connection.execute(
            (
                'INSERT INTO supplier '
                '(id, telegram_id, name, ico, dic, ic_dph, address, iban, swift, '
                'email, smtp_host, smtp_user, smtp_pass, days_due, created_at, '
                'updated_at) '
                'SELECT id, telegram_id, name, ico, dic, ic_dph, address, iban, '
                'swift, email, smtp_host, smtp_user, smtp_pass, days_due, '
                'created_at, updated_at FROM supplier_legacy_smtp_notnull'
            )
        )
    connection.execute('DROP TABLE supplier_legacy_smtp_notnull')

def _ensure_invoice_workspace_unique_index(connection: sqlite3.Connection) -> None:
    connection.execute(
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_invoice_workspace_number '
        'ON invoice (workspace_id, invoice_number)'
    )

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
    connection.execute(LEGACY_INVOICE_SCHEMA)
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


def _bootstrap_invoice_followup_state_table(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]: row[2] for row in connection.execute('PRAGMA table_info(invoice_followup_state)')
    }

    if not existing_columns:
        connection.execute(INVOICE_FOLLOWUP_STATE_SCHEMA)
        _ensure_invoice_followup_state_indexes(connection)
        return

    existing_column_names = set(existing_columns.keys())
    if (
        existing_column_names == set(INVOICE_FOLLOWUP_STATE_EXPECTED_COLUMNS.keys())
        or existing_column_names == INVOICE_FOLLOWUP_STATE_LEGACY_EXPECTED_COLUMN_NAMES
    ):
        _ensure_invoice_followup_state_indexes(connection)
        return

    raise RuntimeError(
        'Incompatible local schema for table invoice_followup_state. '
        'Manual migration/intervention is required; automatic DROP is disabled.'
    )


def ensure_invoice_followup_state_schema(connection: sqlite3.Connection) -> None:
    _bootstrap_invoice_followup_state_table(connection)


def _ensure_invoice_followup_state_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_invoice_followup_supplier_reminder '
        'ON invoice_followup_state (supplier_telegram_id, payment_status, reminder_status, remind_after)'
    )
    columns = {
        row[1] for row in connection.execute('PRAGMA table_info(invoice_followup_state)')
    }
    if 'workspace_id' in columns:
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_invoice_followup_workspace_reminder '
            'ON invoice_followup_state '
            '(workspace_id, payment_status, reminder_status, remind_after)'
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

    existing_column_names = set(existing_columns.keys())
    if (
        existing_column_names == set(INVOICE_NUMBER_SETTINGS_EXPECTED_COLUMNS.keys())
        or existing_column_names == INVOICE_NUMBER_SETTINGS_LEGACY_EXPECTED_COLUMN_NAMES
    ):
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

    existing_column_names = set(existing_columns.keys())
    if (
        existing_column_names == set(CONFIRMED_SEMANTIC_ALIAS_EXPECTED_COLUMNS.keys())
        or existing_column_names == CONFIRMED_SEMANTIC_ALIAS_LEGACY_EXPECTED_COLUMN_NAMES
    ):
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

    existing_keys = set(existing_columns.keys())
    expected_keys = set(CUSTOMIZATION_REQUEST_EXPECTED_COLUMNS.keys())
    if existing_keys == expected_keys:
        _ensure_customization_request_indexes(connection)
        return

    missing_keys = expected_keys - existing_keys
    extra_keys = existing_keys - expected_keys
    if not extra_keys and missing_keys and missing_keys <= set(_CUSTOMIZATION_REQUEST_ADDITIVE_COLUMNS.keys()):
        for column_name in CUSTOMIZATION_REQUEST_EXPECTED_COLUMNS:
            if column_name in missing_keys:
                connection.execute(
                    f'ALTER TABLE customization_requests ADD COLUMN {column_name} '
                    f'{_CUSTOMIZATION_REQUEST_ADDITIVE_COLUMNS[column_name]}'
                )
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


def ensure_archive_schema(connection: sqlite3.Connection) -> None:
    connection.execute(ARCHIVE_JOB_SCHEMA)
    connection.execute(ACCOUNTING_DOCUMENT_ARCHIVE_STATE_SCHEMA)
    _ensure_archive_job_additive_columns(connection)
    _ensure_archive_indexes(connection)


def ensure_google_drive_connection_schema(connection: sqlite3.Connection) -> None:
    connection.execute(GOOGLE_DRIVE_CONNECTION_SCHEMA)
    connection.execute(GOOGLE_DRIVE_FOLDER_CACHE_SCHEMA)
    connection.execute(GOOGLE_DRIVE_OAUTH_STATE_SCHEMA)
    _ensure_google_drive_connection_indexes(connection)



def ensure_work_time_schema(connection: sqlite3.Connection) -> None:
    connection.execute(WORK_TIME_DAY_SCHEMA)
    _ensure_work_time_day_additive_columns(connection)
    connection.execute(WORK_TIME_SETTINGS_SCHEMA)
    connection.execute(WORK_TIME_EVENT_SCHEMA)
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_work_time_days_user_month '
        'ON work_time_days (telegram_id, work_date, status)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_work_time_events_day_created '
        'ON work_time_events (work_time_day_id, created_at)'
    )


def ensure_workspace_foundation_schema(connection: sqlite3.Connection) -> None:
    connection.execute(WORKSPACE_SCHEMA)
    connection.execute(WORKSPACE_MEMBERSHIP_SCHEMA)
    connection.execute(ACTIVE_WORKSPACE_SELECTION_SCHEMA)
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_workspace_membership_user_status '
        'ON workspace_membership (telegram_id, status, workspace_id)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_workspace_status '
        'ON workspace (status, created_at)'
    )

def _ensure_work_time_day_additive_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute('PRAGMA table_info(work_time_days)').fetchall()
    }
    for column_name, column_definition in _WORK_TIME_DAY_ADDITIVE_COLUMNS.items():
        if column_name not in existing_columns:
            connection.execute(
                f'ALTER TABLE work_time_days ADD COLUMN {column_name} {column_definition}'
            )


def _ensure_archive_job_additive_columns(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1] for row in connection.execute('PRAGMA table_info(archive_jobs)').fetchall()
    }
    for column_name, column_definition in _ARCHIVE_JOB_ADDITIVE_COLUMNS.items():
        if column_name not in existing_columns:
            connection.execute(
                f'ALTER TABLE archive_jobs ADD COLUMN {column_name} {column_definition}'
            )


def _ensure_archive_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_archive_jobs_runnable '
        'ON archive_jobs (provider, status, next_attempt_at, created_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_archive_jobs_claim '
        'ON archive_jobs (provider, status, next_attempt_at, lease_until, created_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_archive_jobs_document '
        'ON archive_jobs (workspace_id, document_id, provider, status)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_accounting_archive_state_status '
        'ON accounting_document_archive_state (workspace_id, archive_status, updated_at)'
    )


def _ensure_google_drive_connection_indexes(connection: sqlite3.Connection) -> None:
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_google_drive_connections_status '
        'ON google_drive_connections (provider, status, updated_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_google_drive_folder_cache_workspace '
        'ON google_drive_folder_cache (workspace_id, provider, folder_path)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_google_drive_oauth_states_status_expires '
        'ON google_drive_oauth_states (status, expires_at)'
    )
    connection.execute(
        'CREATE INDEX IF NOT EXISTS idx_google_drive_oauth_states_workspace '
        'ON google_drive_oauth_states (workspace_id, telegram_id, created_at)'
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
        _bootstrap_invoice_followup_state_table(connection)
        _bootstrap_supplier_service_alias_table(connection)
        _bootstrap_access_request_table(connection)
        _bootstrap_authorized_user_table(connection)
        _bootstrap_invoice_number_settings_table(connection)
        _bootstrap_confirmed_semantic_alias_table(connection)
        _bootstrap_customization_request_table(connection)
        ensure_workspace_foundation_schema(connection)
        ensure_archive_schema(connection)
        ensure_google_drive_connection_schema(connection)
        ensure_work_time_schema(connection)
        connection.commit()
