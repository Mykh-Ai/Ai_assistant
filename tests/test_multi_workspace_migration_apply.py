from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

import bot.multi_workspace_migration as migration_cli
import bot.services.multi_workspace_migration_apply as migration_apply_module

from bot.services.db import (
    LEGACY_INVOICE_SCHEMA,
    LEGACY_SUPPLIER_SCHEMA,
    init_db,
)
from bot.services.multi_workspace_migration_apply import (
    APPLY_CONFIRMATION,
    ROLLBACK_CONFIRMATION,
    MigrationApplyError,
    MultiWorkspaceMigrationManager,
)

USER_ID = 77112233

LEGACY_CONTACT_SCHEMA = """
CREATE TABLE contact (
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
LEGACY_NUMBERING_SCHEMA = """
CREATE TABLE invoice_number_settings (
    supplier_telegram_id INTEGER NOT NULL,
    issue_year INTEGER NOT NULL,
    first_invoice_number TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(supplier_telegram_id, issue_year)
);
"""
LEGACY_FOLLOWUP_SCHEMA = """
CREATE TABLE invoice_followup_state (
    invoice_id INTEGER PRIMARY KEY,
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
LEGACY_ALIAS_SCHEMA = """
CREATE TABLE confirmed_semantic_alias (
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
LEGACY_WORK_SCHEMAS = """
CREATE TABLE work_time_days (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    UNIQUE(telegram_id, work_date)
);
CREATE TABLE work_time_settings (
    telegram_id INTEGER PRIMARY KEY,
    lunch_break_configured INTEGER NOT NULL DEFAULT 0,
    lunch_break_enabled INTEGER NOT NULL DEFAULT 0,
    lunch_break_minutes INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE work_time_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    work_time_day_id INTEGER,
    telegram_id INTEGER,
    event_type TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    source_message_id INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _legacy_fixture(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / 'legacy.db'
    storage_root = tmp_path / 'storage'
    init_db(db_path)
    connection = sqlite3.connect(db_path)
    try:
        for table in (
            'supplier', 'contact', 'invoice', 'invoice_number_settings',
            'invoice_followup_state', 'confirmed_semantic_alias',
            'work_time_events', 'work_time_days', 'work_time_settings',
        ):
            connection.execute(f'DROP TABLE {table}')
        connection.executescript(LEGACY_SUPPLIER_SCHEMA)
        connection.executescript(LEGACY_CONTACT_SCHEMA)
        connection.executescript(LEGACY_INVOICE_SCHEMA)
        connection.executescript(LEGACY_NUMBERING_SCHEMA)
        connection.executescript(LEGACY_FOLLOWUP_SCHEMA)
        connection.executescript(LEGACY_ALIAS_SCHEMA)
        connection.executescript(LEGACY_WORK_SCHEMAS)
        connection.executescript(
            """
            CREATE TABLE legacy_extra (
                id INTEGER PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE INDEX legacy_extra_value_idx ON legacy_extra(value);
            CREATE TRIGGER legacy_extra_uppercase
            AFTER INSERT ON legacy_extra
            BEGIN
                UPDATE legacy_extra SET value = upper(NEW.value) WHERE id = NEW.id;
            END;
            INSERT INTO legacy_extra (id, value) VALUES (1, 'kept');
            """
        )
        connection.execute(
            'INSERT INTO authorized_users '
            '(telegram_id, role, status, created_at) '
            'VALUES (?, ?, ?, CURRENT_TIMESTAMP)',
            (USER_ID, 'owner', 'active'),
        )
        connection.execute(
            'INSERT INTO supplier '
            '(id, telegram_id, name, ico, dic, address, iban, swift, email, days_due) '
            'VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (
                USER_ID, 'Legacy Company', '12345678', '1234567890', 'Address',
                'SK3112000000198742637541', 'GIBASKBX', 'owner@example.test', 14,
            ),
        )
        connection.execute(
            'INSERT INTO contact '
            '(id, supplier_telegram_id, name, ico, dic, address, email, source_type) '
            'VALUES (1, ?, ?, ?, ?, ?, ?, ?)',
            (USER_ID, 'Customer', '87654321', '0987654321', 'Customer address', 'customer@example.test', 'manual'),
        )
        connection.execute(
            'INSERT INTO invoice '
            '(id, supplier_telegram_id, contact_id, invoice_number, issue_date, '
            'delivery_date, due_date, due_days, total_amount, currency, status, pdf_path) '
            'VALUES (1, ?, 1, ?, ?, ?, ?, 14, 125.0, ?, ?, ?)',
            (
                USER_ID, '20260001', '2026-07-01', '2026-07-01', '2026-07-15',
                'EUR', 'created', 'storage/invoices/legacy/20260001.pdf',
            ),
        )
        connection.execute(
            'INSERT INTO invoice_item '
            '(id, invoice_id, description_raw, quantity, unit_price, total_price) '
            'VALUES (1, 1, ?, 1, 125.0, 125.0)',
            ('Service',),
        )
        connection.execute(
            'INSERT INTO invoice_number_settings '
            '(supplier_telegram_id, issue_year, first_invoice_number) VALUES (?, 2026, ?)',
            (USER_ID, '20260001'),
        )
        connection.execute(
            'INSERT INTO invoice_followup_state '
            '(invoice_id, supplier_telegram_id, payment_status, reminder_status) '
            'VALUES (1, ?, ?, ?)',
            (USER_ID, 'unpaid', 'active'),
        )
        connection.execute(
            'INSERT INTO supplier_service_alias '
            '(id, supplier_id, alias, canonical_title) VALUES (1, 1, ?, ?)',
            ('servis', 'Service'),
        )
        connection.execute(
            'INSERT INTO confirmed_semantic_alias '
            '(id, supplier_telegram_id, domain, alias_text, alias_normalized, '
            'alias_compressed, target_type, target_id, source) '
            'VALUES (1, ?, ?, ?, ?, ?, ?, 1, ?)',
            (USER_ID, 'contact', 'klient', 'klient', 'klient', 'contact', 'confirmed'),
        )
        connection.execute(
            'INSERT INTO work_time_days '
            '(id, telegram_id, work_date, start_time, status, source) '
            'VALUES (1, ?, ?, ?, ?, ?)',
            (USER_ID, '2026-07-01', '08:00', 'open', 'opened_live'),
        )
        connection.execute(
            'INSERT INTO work_time_settings '
            '(telegram_id, lunch_break_configured, lunch_break_enabled, lunch_break_minutes) '
            'VALUES (?, 1, 1, 30)',
            (USER_ID,),
        )
        connection.execute(
            'INSERT INTO work_time_events '
            '(id, work_time_day_id, telegram_id, event_type) VALUES (1, 1, ?, ?)',
            (USER_ID, 'open'),
        )
        connection.execute(
            'INSERT INTO customization_requests '
            '(request_id, telegram_id, supplier_telegram_id, workspace_id, source_channel, '
            'source_triage_class, normalized_title, normalized_summary, status, '
            'requires_human_approval, created_at, updated_at) '
            'VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
            ('req-1', USER_ID, USER_ID, 'text', 'feature', 'Title', 'Summary', 'pending'),
        )
        connection.execute(
            'INSERT INTO archive_jobs '
            '(job_id, workspace_id, telegram_id, document_id, document_type, '
            'local_file_path, status, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
            ('job-1', f'telegram-{USER_ID}', USER_ID, 'doc-1', 'receipt', 'local.pdf', 'pending'),
        )
        connection.execute(
            'INSERT INTO accounting_document_archive_state '
            '(document_id, workspace_id, telegram_id, document_type, local_file_path, '
            'archive_status, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
            ('doc-1', f'telegram-{USER_ID}', USER_ID, 'receipt', 'local.pdf', 'pending'),
        )
        connection.commit()
    finally:
        connection.close()

    named = storage_root / 'workspaces' / 'legacy-company'
    (named / 'years' / '2026').mkdir(parents=True)
    (named / 'years' / '2026' / 'keep.txt').write_text('keep', encoding='utf-8')
    invoice_dir = storage_root / 'invoices' / 'legacy'
    invoice_dir.mkdir(parents=True)
    (invoice_dir / '20260001.pdf').write_bytes(b'pdf')
    return db_path, storage_root

def _columns(db_path: Path, table: str) -> set[str]:
    connection = sqlite3.connect(db_path)
    try:
        return {str(row[1]) for row in connection.execute(f'PRAGMA table_info({table})')}
    finally:
        connection.close()


def test_apply_backup_post_audit_and_rollback_round_trip(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    dry_run = manager.dry_run()

    assert dry_run['writes_performed'] is False
    assert dry_run['plan']['apply_available'] is True
    assert dry_run['plan']['blocker_count'] == 0
    assert str(USER_ID) not in json.dumps(dry_run, sort_keys=True)
    pre_fingerprint = dry_run['plan']['database_fingerprint']
    assert 'workspace_id' not in _columns(db_path, 'supplier')

    result = manager.apply(
        expected_fingerprint=pre_fingerprint,
        backup_dir=tmp_path / 'backups',
        confirmation=APPLY_CONFIRMATION,
        service_stopped=True,
    )

    assert result['post_apply_audit']['ready'] is True
    assert result['post_apply_audit']['public_profile_switch_ready'] is True
    assert result['post_apply_audit']['workspace_count'] == 1
    assert result['rollback_available'] is True
    assert 'workspace_id' in _columns(db_path, 'supplier')
    assert 'workspace_id' in _columns(db_path, 'work_time_days')
    connection = sqlite3.connect(db_path)
    try:
        workspace_id = connection.execute('SELECT workspace_id FROM supplier').fetchone()[0]
        assert workspace_id
        for table in (
            'contact', 'invoice', 'invoice_number_settings', 'invoice_followup_state',
            'confirmed_semantic_alias', 'work_time_days', 'work_time_settings',
            'work_time_events', 'customization_requests', 'archive_jobs',
            'accounting_document_archive_state',
        ):
            assert connection.execute(
                f'SELECT COUNT(*) FROM {table} WHERE workspace_id = ?',
                (workspace_id,),
            ).fetchone()[0] == 1
        assert connection.execute('SELECT pdf_path FROM invoice').fetchone()[0] == 'storage/invoices/legacy/20260001.pdf'
        assert connection.execute(
            "SELECT COUNT(*) FROM sqlite_master "
            "WHERE name IN ('legacy_extra_value_idx', 'legacy_extra_uppercase')"
        ).fetchone()[0] == 2
        connection.execute(
            'INSERT INTO legacy_extra (id, value) VALUES (2, ?)',
            ('mixed',),
        )
        assert connection.execute(
            'SELECT value FROM legacy_extra WHERE id = 2'
        ).fetchone()[0] == 'MIXED'
        assert connection.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
    finally:
        connection.close()
    assert (storage_root / 'workspaces' / 'legacy-company' / 'years' / '2026' / 'keep.txt').read_text(encoding='utf-8') == 'keep'
    manifest_path = Path(result['manifest_path'])
    assert manifest_path.is_file()
    assert (manifest_path.parent / 'database.sqlite3').is_file()
    assert (manifest_path.parent / 'storage' / 'invoices' / 'legacy' / '20260001.pdf').is_file()
    assert (manifest_path.parent / 'storage' / 'workspaces' / 'legacy-company').is_dir()

    rollback = manager.rollback(
        manifest_path=manifest_path,
        expected_current_fingerprint=result['post_apply_fingerprint'],
        confirmation=ROLLBACK_CONFIRMATION,
        service_stopped=True,
    )
    assert rollback['integrity_check'] == 'ok'
    assert rollback['restored_fingerprint'] == pre_fingerprint
    assert 'workspace_id' not in _columns(db_path, 'supplier')


def test_apply_refuses_drift_missing_confirmation_and_running_service(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    fingerprint = manager.dry_run()['plan']['database_fingerprint']

    with pytest.raises(MigrationApplyError, match='apply_confirmation_required'):
        manager.apply(
            expected_fingerprint=fingerprint,
            backup_dir=tmp_path / 'backups-a',
            confirmation='',
            service_stopped=True,
        )
    with pytest.raises(MigrationApplyError, match='service_stopped_confirmation_required'):
        manager.apply(
            expected_fingerprint=fingerprint,
            backup_dir=tmp_path / 'backups-b',
            confirmation=APPLY_CONFIRMATION,
            service_stopped=False,
        )
    with pytest.raises(MigrationApplyError, match='database_fingerprint_changed'):
        manager.apply(
            expected_fingerprint='0' * 64,
            backup_dir=tmp_path / 'backups-c',
            confirmation=APPLY_CONFIRMATION,
            service_stopped=True,
        )
    assert not (tmp_path / 'backups-a').exists()
    assert not (tmp_path / 'backups-b').exists()
    assert not (tmp_path / 'backups-c').exists()


def test_dry_run_blocks_orphan_invoice_without_writes(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute('UPDATE invoice SET contact_id = 999')
        connection.commit()
    finally:
        connection.close()
    before = db_path.read_bytes()

    report = MultiWorkspaceMigrationManager(
        db_path=db_path,
        storage_root=storage_root,
    ).dry_run()

    assert report['plan']['apply_available'] is False
    assert report['plan']['blockers']['invoice_contact_owner_mismatch'] == 1
    assert db_path.read_bytes() == before

def test_apply_refuses_backup_inside_managed_storage(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    fingerprint = manager.dry_run()['plan']['database_fingerprint']

    with pytest.raises(MigrationApplyError, match='backup_directory_inside_source_tree'):
        manager.apply(
            expected_fingerprint=fingerprint,
            backup_dir=storage_root / 'workspaces' / 'backups',
            confirmation=APPLY_CONFIRMATION,
            service_stopped=True,
        )


def test_apply_refuses_when_another_writer_holds_sqlite_lock(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    fingerprint = manager.dry_run()['plan']['database_fingerprint']
    writer = sqlite3.connect(db_path, isolation_level=None)
    try:
        writer.execute('BEGIN IMMEDIATE')
        with pytest.raises(MigrationApplyError, match='database_exclusive_lock_unavailable'):
            manager.apply(
                expected_fingerprint=fingerprint,
                backup_dir=tmp_path / 'backups',
                confirmation=APPLY_CONFIRMATION,
                service_stopped=True,
            )
    finally:
        writer.execute('ROLLBACK')
        writer.close()
    assert not (tmp_path / 'backups').exists()


def test_rollback_refuses_changed_storage_inventory(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    fingerprint = manager.dry_run()['plan']['database_fingerprint']
    result = manager.apply(
        expected_fingerprint=fingerprint,
        backup_dir=tmp_path / 'backups',
        confirmation=APPLY_CONFIRMATION,
        service_stopped=True,
    )
    changed_file = storage_root / 'workspaces' / 'legacy-company' / 'changed.txt'
    changed_file.write_text('changed', encoding='utf-8')

    with pytest.raises(MigrationApplyError, match='rollback_storage_inventory_changed'):
        manager.rollback(
            manifest_path=Path(result['manifest_path']),
            expected_current_fingerprint=result['post_apply_fingerprint'],
            confirmation=ROLLBACK_CONFIRMATION,
            service_stopped=True,
        )


def test_apply_preserves_existing_foundation_and_is_not_repeatable(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            'INSERT INTO workspace '
            '(workspace_id, display_name, storage_key, drive_folder_name, status, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
            ('ws_existing', 'Existing profile', 'existing-profile', 'Existing profile', 'active'),
        )
        connection.execute(
            'INSERT INTO workspace_membership '
            '(workspace_id, telegram_id, role, status, created_at, updated_at) '
            'VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)',
            ('ws_existing', USER_ID, 'owner', 'active'),
        )
        connection.execute(
            'INSERT INTO active_workspace_selection '
            '(telegram_id, workspace_id, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)',
            (USER_ID, 'ws_existing'),
        )
        connection.commit()
    finally:
        connection.close()
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    fingerprint = manager.dry_run()['plan']['database_fingerprint']
    result = manager.apply(
        expected_fingerprint=fingerprint,
        backup_dir=tmp_path / 'backups',
        confirmation=APPLY_CONFIRMATION,
        service_stopped=True,
    )

    connection = sqlite3.connect(db_path)
    try:
        assert connection.execute(
            'SELECT workspace_id FROM active_workspace_selection WHERE telegram_id = ?',
            (USER_ID,),
        ).fetchone()[0] == 'ws_existing'
        assert connection.execute(
            'SELECT COUNT(*) FROM workspace WHERE workspace_id = ?',
            ('ws_existing',),
        ).fetchone()[0] == 1
    finally:
        connection.close()
    repeat_report = manager.dry_run()['plan']
    assert repeat_report['migration_required'] is False
    assert repeat_report['apply_available'] is False
    with pytest.raises(MigrationApplyError, match='database_already_migrated'):
        manager.apply(
            expected_fingerprint=result['post_apply_fingerprint'],
            backup_dir=tmp_path / 'repeat-backups',
            confirmation=APPLY_CONFIRMATION,
            service_stopped=True,
        )


def test_dry_run_blocks_empty_supplier_database(tmp_path: Path) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute('DELETE FROM invoice_item')
        connection.execute('DELETE FROM invoice_followup_state')
        connection.execute('DELETE FROM invoice')
        connection.execute('DELETE FROM confirmed_semantic_alias')
        connection.execute('DELETE FROM contact')
        connection.execute('DELETE FROM supplier_service_alias')
        connection.execute('DELETE FROM supplier')
        connection.commit()
    finally:
        connection.close()

    report = MultiWorkspaceMigrationManager(
        db_path=db_path,
        storage_root=storage_root,
    ).dry_run()['plan']
    assert report['apply_available'] is False
    assert report['blockers']['no_supplier_profiles_to_migrate'] == 1

def test_post_swap_fingerprint_failure_restores_original_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    manager = MultiWorkspaceMigrationManager(db_path=db_path, storage_root=storage_root)
    pre_fingerprint = manager.dry_run()['plan']['database_fingerprint']
    real_fingerprint = migration_apply_module._fingerprint_path
    calls = 0

    def fault_injected_fingerprint(path: Path) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            return 'f' * 64
        return real_fingerprint(path)

    monkeypatch.setattr(
        migration_apply_module,
        '_fingerprint_path',
        fault_injected_fingerprint,
    )
    with pytest.raises(
        MigrationApplyError,
        match='post_swap_fingerprint_mismatch_rolled_back',
    ):
        manager.apply(
            expected_fingerprint=pre_fingerprint,
            backup_dir=tmp_path / 'backups',
            confirmation=APPLY_CONFIRMATION,
            service_stopped=True,
        )

    assert real_fingerprint(db_path) == pre_fingerprint
    assert 'workspace_id' not in _columns(db_path, 'supplier')
    manifests = list((tmp_path / 'backups').glob('*/manifest.json'))
    assert len(manifests) == 1
    manifest = json.loads(manifests[0].read_text(encoding='utf-8'))
    assert manifest['status'] == 'apply_failed_rolled_back'

def test_cli_dry_run_is_redacted_and_read_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    db_path, storage_root = _legacy_fixture(tmp_path)
    before = db_path.read_bytes()
    monkeypatch.setattr(
        'sys.argv',
        [
            'multi_workspace_migration',
            '--mode',
            'dry-run',
            '--db-path',
            str(db_path),
            '--storage-root',
            str(storage_root),
        ],
    )

    assert migration_cli.main() == 0

    report = json.loads(capsys.readouterr().out)
    assert report['mode'] == 'dry-run'
    assert report['plan']['writes_performed'] is False
    assert report['plan']['database_fingerprint']
    assert report['plan']['apply_available'] is True
    assert len(report['plan']['workspace_candidates']) == (
        report['plan']['workspace_candidate_count']
    )
    assert str(USER_ID) not in json.dumps(report, sort_keys=True)
    assert db_path.read_bytes() == before