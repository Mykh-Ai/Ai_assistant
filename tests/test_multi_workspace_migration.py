from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path

import pytest

from bot.services.db import (
    LEGACY_INVOICE_SCHEMA,
    LEGACY_SUPPLIER_SCHEMA,
    init_db,
    managed_connection,
)
from bot.services.multi_workspace_migration import (
    MigrationAuditError,
    MultiWorkspaceMigrationAuditor,
)


LEGACY_USER_ID = 987654321

LEGACY_WORK_TIME_DAY_SCHEMA = """
CREATE TABLE IF NOT EXISTS work_time_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER NOT NULL,
    work_date TEXT NOT NULL,
    start_time TEXT,
    end_time TEXT,
    lunch_break_minutes INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    active_since TEXT,
    total_seconds INTEGER NOT NULL DEFAULT 0,
    close_reason TEXT,
    close_input_mode TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(telegram_id, work_date)
);
"""


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / 'fakturabot.db'
    storage_root = tmp_path / 'storage'
    init_db(db_path)
    with managed_connection(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO authorized_users '
                '(telegram_id, role, status, created_at) '
                'VALUES (?, ?, ?, CURRENT_TIMESTAMP)'
            ),
            (LEGACY_USER_ID, 'owner', 'active'),
        )
        connection.execute(
            (
                'INSERT INTO supplier '
                '(telegram_id, name, ico, dic, address, iban, swift, email, days_due) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (
                LEGACY_USER_ID,
                'Legacy Business',
                '12345678',
                '1234567890',
                'Address',
                'SK3112000000198742637541',
                'GIBASKBX',
                'owner@example.test',
                14,
            ),
        )
        connection.execute(
            (
                'INSERT INTO invoice '
                '(supplier_telegram_id, contact_id, invoice_number, issue_date, '
                'delivery_date, due_date, due_days, total_amount, currency, '
                'status, pdf_path) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (
                LEGACY_USER_ID,
                1,
                '20260001',
                '2026-07-01',
                '2026-07-01',
                '2026-07-15',
                14,
                100.0,
                'EUR',
                'created',
                r'D:legacyinvoice.pdf',
            ),
        )
        connection.commit()
    metadata_dir = (
        storage_root
        / 'workspaces'
        / 'mykhailo-szco'
        / 'years'
        / '2026'
        / 'expenses'
        / '07'
        / 'receipts'
        / 'metadata'
    )
    originals_dir = metadata_dir.parent / 'originals'
    metadata_dir.mkdir(parents=True)
    originals_dir.mkdir(parents=True)
    (metadata_dir / 'doc.json').write_text('{}', encoding='utf-8')
    (originals_dir / 'doc.pdf').write_bytes(b'pdf')
    return db_path, storage_root


def _replace_work_time_days_with_legacy_schema(db_path: Path) -> None:
    with managed_connection(db_path) as connection:
        connection.execute('DROP TABLE work_time_days')
        connection.execute(LEGACY_WORK_TIME_DAY_SCHEMA)
        connection.commit()


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def test_audit_is_read_only_and_redacts_tenant_ids(tmp_path: Path) -> None:
    db_path, storage_root = _fixture(tmp_path)
    before = _digest(db_path)

    report = MultiWorkspaceMigrationAuditor(
        db_path=db_path,
        storage_root=storage_root,
    ).audit()

    assert _digest(db_path) == before
    assert report['mode'] == 'audit'
    assert report['tables']['supplier']['tenant_groups']['telegram_id'] == {
        'tenant_1': 1
    }
    assert report['invoice_pdf_paths'] == {'windows_absolute': 1}
    assert report['accounting_storage']['key_classes'] == {'legacy_named': 1}
    assert report['accounting_storage']['metadata_files'] == 1
    assert report['accounting_storage']['original_files'] == 1
    assert str(LEGACY_USER_ID) not in json.dumps(report, sort_keys=True)


def test_dry_run_reports_schema_plan_without_apply(tmp_path: Path) -> None:
    db_path, storage_root = _fixture(tmp_path)
    _replace_work_time_days_with_legacy_schema(db_path)
    before = _digest(db_path)

    report = MultiWorkspaceMigrationAuditor(
        db_path=db_path,
        storage_root=storage_root,
    ).dry_run()

    assert _digest(db_path) == before
    assert report['mode'] == 'dry-run'
    assert report['plan']['writes_performed'] is False
    assert report['plan']['apply_available'] is False
    assert report['plan']['preserve_invoice_pdf_paths'] is True
    planned_tables = {
        change['table'] for change in report['plan']['schema_changes']
    }
    assert {'work_time_days'} <= planned_tables
    assert 'invoice' not in planned_tables
    assert 'supplier' not in planned_tables
    assert report['migration_state']['public_profile_switch_ready'] is False


def test_missing_database_fails_without_creating_it(tmp_path: Path) -> None:
    db_path = tmp_path / 'missing.db'
    auditor = MultiWorkspaceMigrationAuditor(
        db_path=db_path,
        storage_root=tmp_path / 'storage',
    )

    with pytest.raises(MigrationAuditError, match='database_not_found'):
        auditor.audit()

    assert not db_path.exists()

def test_legacy_supplier_is_planned_for_workspace_backfill(tmp_path: Path) -> None:
    db_path, storage_root = _fixture(tmp_path)
    with managed_connection(db_path) as connection:
        connection.execute('ALTER TABLE supplier RENAME TO supplier_workspace_target')
        connection.execute(LEGACY_SUPPLIER_SCHEMA)
        connection.execute(
            (
                'INSERT INTO supplier '
                '(id, telegram_id, name, ico, dic, ic_dph, address, iban, swift, '
                'email, smtp_host, smtp_user, smtp_pass, days_due, created_at, updated_at) '
                'SELECT id, telegram_id, name, ico, dic, ic_dph, address, iban, '
                'swift, email, smtp_host, smtp_user, smtp_pass, days_due, '
                'created_at, updated_at FROM supplier_workspace_target'
            )
        )
        connection.execute('DROP TABLE supplier_workspace_target')
        connection.commit()

    report = MultiWorkspaceMigrationAuditor(
        db_path=db_path,
        storage_root=storage_root,
    ).dry_run()

    planned_tables = {
        change['table'] for change in report['plan']['schema_changes']
    }
    assert 'supplier' in planned_tables
    assert report['tables']['supplier']['row_count'] == 1

def test_legacy_invoice_is_planned_for_workspace_backfill(tmp_path: Path) -> None:
    db_path, storage_root = _fixture(tmp_path)
    with managed_connection(db_path) as connection:
        connection.execute('ALTER TABLE invoice RENAME TO invoice_workspace_target')
        connection.execute(LEGACY_INVOICE_SCHEMA)
        connection.execute(
            (
                'INSERT INTO invoice '
                '(id, supplier_telegram_id, contact_id, invoice_number, issue_date, '
                'delivery_date, due_date, due_days, total_amount, currency, status, '
                'pdf_path, created_at, updated_at) '
                'SELECT id, supplier_telegram_id, contact_id, invoice_number, '
                'issue_date, delivery_date, due_date, due_days, total_amount, '
                'currency, status, pdf_path, created_at, updated_at '
                'FROM invoice_workspace_target'
            )
        )
        connection.execute('DROP TABLE invoice_workspace_target')
        connection.commit()

    report = MultiWorkspaceMigrationAuditor(
        db_path=db_path,
        storage_root=storage_root,
    ).dry_run()

    planned_tables = {
        change['table'] for change in report['plan']['schema_changes']
    }
    assert 'invoice' in planned_tables
    assert report['tables']['invoice']['row_count'] == 1
