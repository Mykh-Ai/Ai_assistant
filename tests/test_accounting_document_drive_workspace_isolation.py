from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3

import pytest

from bot.handlers.accounting_document_intake import _enqueue_archive_after_confirmed_save
from bot.services.accounting_document_archive_path import (
    AccountingDocumentArchivePathError,
    build_accounting_document_drive_target_path,
    normalize_relative_drive_target_path,
)
from bot.services.accounting_document_archive_service import (
    AccountingDocumentArchiveService,
    AccountingDocumentArchiveServiceError,
)
from bot.services.accounting_document_drive_audit import (
    audit_accounting_document_drive_targets,
)
from bot.services.accounting_document_models import (
    AccountingDocumentCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
)
from bot.services.accounting_document_storage import AccountingDocumentSaveResult
from bot.services.archive_job_service import ArchiveJobService
from bot.services.db import init_db
from bot.services.google_drive_service_account_client import _drive_folder_parts


def _paths(
    tmp_path: Path,
    *,
    storage_key: str,
    document_type: str = 'receipt',
    year: str = '2026',
    month: str = '07',
    stem: str = 'document-1',
) -> tuple[Path, Path]:
    local_folder = 'receipts' if document_type == 'receipt' else 'incoming_invoices'
    base = (
        tmp_path
        / 'storage'
        / 'workspaces'
        / storage_key
        / 'years'
        / year
        / 'expenses'
        / month
        / local_folder
    )
    original = base / 'originals' / f'{stem}.jpg'
    metadata = base / 'metadata' / f'{stem}.json'
    original.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b'test-original')
    metadata.write_text('{}', encoding='utf-8')
    return original, metadata


def _enqueue(
    db_path: Path,
    tmp_path: Path,
    *,
    workspace_id: str,
    storage_key: str,
    drive_folder_name: str,
    document_id: str,
    document_type: str = 'receipt',
    year: str = '2026',
    month: str = '07',
):
    original, metadata = _paths(
        tmp_path,
        storage_key=storage_key,
        document_type=document_type,
        year=year,
        month=month,
        stem=document_id,
    )
    result = AccountingDocumentArchiveService(db_path).enqueue_confirmed_document(
        workspace_id=workspace_id,
        telegram_id=900001,
        document_id=document_id,
        document_type=document_type,
        local_file_path=original,
        metadata_path=metadata,
        workspace_storage_key=storage_key,
        workspace_drive_folder_name=drive_folder_name,
    )
    return result, original, metadata


def test_existing_profile_receipt_persists_exact_workspace_target(tmp_path: Path) -> None:
    result, _, _ = _enqueue(
        tmp_path / 'bot.db',
        tmp_path,
        workspace_id='ws-primary',
        storage_key='primary-storage',
        drive_folder_name='Testovacia živnosť, s. r. o.',
        document_id='receipt-primary',
    )

    assert result.job.workspace_id == 'ws-primary'
    assert result.job.target_folder_path == (
        'Testovacia živnosť, s. r. o./2026/blocky/2026-07'
    )


def test_second_profile_receipt_has_no_telegram_or_first_profile_segment(tmp_path: Path) -> None:
    result, _, _ = _enqueue(
        tmp_path / 'bot.db',
        tmp_path,
        workspace_id='ws-second',
        storage_key='second-storage',
        drive_folder_name='Druhý profil & Partneri',
        document_id='receipt-second',
    )

    assert result.job.workspace_id == 'ws-second'
    assert result.job.target_folder_path == 'Druhý profil & Partneri/2026/blocky/2026-07'
    assert 'telegram-' not in result.job.target_folder_path
    assert 'Testovacia živnosť' not in result.job.target_folder_path


def test_same_date_receipts_in_two_workspaces_have_different_targets(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    first, _, _ = _enqueue(
        db_path,
        tmp_path,
        workspace_id='ws-first',
        storage_key='first-storage',
        drive_folder_name='Prvý profil',
        document_id='receipt-first',
    )
    second, _, _ = _enqueue(
        db_path,
        tmp_path,
        workspace_id='ws-second',
        storage_key='second-storage',
        drive_folder_name='Druhý profil',
        document_id='receipt-second',
    )

    assert first.job.target_folder_path != second.job.target_folder_path


def test_second_profile_incoming_invoice_uses_expected_folder(tmp_path: Path) -> None:
    result, _, _ = _enqueue(
        tmp_path / 'bot.db',
        tmp_path,
        workspace_id='ws-second',
        storage_key='second-storage',
        drive_folder_name='Druhý profil',
        document_id='incoming-second',
        document_type='incoming_invoice',
    )

    assert result.job.target_folder_path == (
        'Druhý profil/2026/prijate_faktury/2026-07'
    )


def test_active_workspace_switch_after_enqueue_does_not_retarget_job(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    result, _, _ = _enqueue(
        db_path,
        tmp_path,
        workspace_id='ws-first',
        storage_key='first-storage',
        drive_folder_name='Prvý profil',
        document_id='receipt-first',
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO active_workspace_selection (telegram_id, workspace_id, updated_at) '
            "VALUES (900001, 'ws-second', CURRENT_TIMESTAMP)"
        )
        connection.commit()

    persisted = ArchiveJobService(db_path).get_job(result.job.job_id)

    assert persisted is not None
    assert persisted.target_folder_path == 'Prvý profil/2026/blocky/2026-07'


def test_retry_and_duplicate_enqueue_reuse_first_persisted_target(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    first, original, metadata = _enqueue(
        db_path,
        tmp_path,
        workspace_id='ws-first',
        storage_key='first-storage',
        drive_folder_name='Pôvodný názov',
        document_id='receipt-first',
    )
    archive = AccountingDocumentArchiveService(db_path)
    archive.mark_uploading(first.job.job_id)
    archive.mark_retry_wait(
        first.job.job_id,
        error_code='temporary_failure',
        now=datetime(2026, 7, 16, tzinfo=UTC),
    )
    duplicate = archive.enqueue_confirmed_document(
        workspace_id='ws-first',
        telegram_id=900001,
        document_id='receipt-first',
        document_type='receipt',
        local_file_path=original,
        metadata_path=metadata,
        workspace_storage_key='first-storage',
        workspace_drive_folder_name='Neskorší názov',
    )

    with sqlite3.connect(db_path) as connection:
        count = connection.execute('SELECT COUNT(*) FROM archive_jobs').fetchone()[0]

    assert duplicate.job.job_id == first.job.job_id
    assert duplicate.job.target_folder_path == 'Pôvodný názov/2026/blocky/2026-07'
    assert count == 1


@pytest.mark.parametrize('drive_folder_name', ['', '   ', '../escape', 'folder/subfolder', 'C:\\escape'])
def test_missing_or_unsafe_workspace_folder_fails_before_enqueue(
    tmp_path: Path,
    drive_folder_name: str,
) -> None:
    db_path = tmp_path / 'bot.db'
    original, metadata = _paths(tmp_path, storage_key='safe-storage')

    with pytest.raises(AccountingDocumentArchiveServiceError):
        AccountingDocumentArchiveService(db_path).enqueue_confirmed_document(
            workspace_id='ws-safe',
            telegram_id=900001,
            document_id='receipt-safe',
            document_type='receipt',
            local_file_path=original,
            metadata_path=metadata,
            workspace_storage_key='safe-storage',
            workspace_drive_folder_name=drive_folder_name,
        )

    assert original.exists()
    assert metadata.exists()
    assert not db_path.exists()


@pytest.mark.parametrize(
    'target',
    ['/absolute/path', '../escape', 'safe//escape', 'safe/./escape', 'safe/../escape', 'C:\\escape'],
)
def test_target_normalization_rejects_absolute_empty_and_traversal_segments(target: str) -> None:
    with pytest.raises(AccountingDocumentArchivePathError):
        normalize_relative_drive_target_path(target)


def test_handler_keeps_confirmed_files_when_target_construction_fails(tmp_path: Path) -> None:
    original, metadata = _paths(tmp_path, storage_key='safe-storage')
    candidate = AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Test vendor',
        vendor_ico=None,
        document_number=None,
        issue_date='2026-07-16',
        total_amount='12.00',
        currency='EUR',
        vat_amount=None,
        payment_method=None,
        purchase_subject='Test',
        document_category_candidate=None,
        source=AccountingDocumentSource(input_type='photo'),
        quality=AccountingDocumentQuality(),
    )

    _enqueue_archive_after_confirmed_save(
        db_path=tmp_path / 'bot.db',
        result=AccountingDocumentSaveResult(original_path=original, metadata_path=metadata),
        candidate=candidate,
        supplier_telegram_id=900001,
        workspace_id='ws-safe',
        workspace_key='safe-storage',
        workspace_drive_folder_name='../unsafe',
    )

    assert original.exists()
    assert metadata.exists()
    assert not (tmp_path / 'bot.db').exists()


def test_read_only_audit_blocks_active_legacy_job_with_missing_target(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    original, metadata = _paths(tmp_path, storage_key='legacy-storage')
    ArchiveJobService(db_path).enqueue_job(
        workspace_id='legacy-storage',
        telegram_id=900001,
        document_id='legacy-receipt',
        document_type='receipt',
        local_file_path=original,
        metadata_path=metadata,
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO workspace '
            '(workspace_id, display_name, storage_key, drive_folder_name, status, created_at, updated_at) '
            "VALUES ('legacy-storage', 'Legacy', 'legacy-storage', 'Legacy profil', "
            "'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.commit()

    report = audit_accounting_document_drive_targets(db_path)

    assert report.active_accounting_jobs == 1
    assert report.valid_target_jobs == 0
    assert report.blocker_categories == {'target_folder_path_missing': 1}
    assert report.blocker_count == 1
    assert report.deployment_ready is False
    assert report.writes_performed is False
    assert report.database_unchanged is True
    assert report.database_sha256_before == report.database_sha256_after


def test_read_only_audit_blocks_unsafe_active_target(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    result, _, _ = _enqueue(
        db_path,
        tmp_path,
        workspace_id='ws-audit',
        storage_key='audit-storage',
        drive_folder_name='Audit profil',
        document_id='audit-receipt',
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'INSERT INTO workspace '
            '(workspace_id, display_name, storage_key, drive_folder_name, status, created_at, updated_at) '
            "VALUES ('ws-audit', 'Audit', 'audit-storage', 'Audit profil', "
            "'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        )
        connection.execute(
            "UPDATE archive_jobs SET target_folder_path = '../escape' WHERE job_id = ?",
            (result.job.job_id,),
        )
        connection.commit()

    report = audit_accounting_document_drive_targets(db_path)

    assert report.blocker_categories == {'unsafe_or_inconsistent_path': 1}
    assert report.deployment_ready is False
    assert report.writes_performed is False


def test_shared_builder_does_not_duplicate_configured_drive_root() -> None:
    target = build_accounting_document_drive_target_path(
        workspace_drive_folder_name='Profil',
        document_type='receipt',
        year=2026,
        month=7,
    )

    assert target == 'Profil/2026/blocky/2026-07'
    assert not target.startswith('FakturaBot/')


def test_explicit_workspace_segment_equal_to_root_name_is_not_stripped(tmp_path: Path) -> None:
    parts = _drive_folder_parts(
        local_file_path=tmp_path / 'unused.jpg',
        target_folder_path='FakturaBot/2026/blocky/2026-07',
        document_type='receipt',
        root_folder_name='FakturaBot',
    )

    assert parts == ('FakturaBot', '2026', 'blocky', '2026-07')
