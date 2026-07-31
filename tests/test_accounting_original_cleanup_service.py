from __future__ import annotations

from datetime import UTC, datetime, timedelta
import inspect
import os
from pathlib import Path
import shutil
import sqlite3

import pytest

from bot.services import accounting_original_cleanup_service
from bot.services.accounting_original_cleanup_service import (
    CLEANUP_ACTION_EXCLUDE,
    CLEANUP_ACTION_KEEP,
    CLEANUP_ACTION_WOULD_DELETE,
    CLEANUP_REASON_EXCLUDE_FILE_MISSING,
    CLEANUP_REASON_EXCLUDE_INVALID_PATH,
    CLEANUP_REASON_EXCLUDE_INVOICE_PATH,
    CLEANUP_REASON_EXCLUDE_METADATA_PATH,
    CLEANUP_REASON_EXCLUDE_MISSING_DRIVE_FILE_ID,
    CLEANUP_REASON_EXCLUDE_MISSING_UPLOADED_AT,
    CLEANUP_REASON_EXCLUDE_NOT_UPLOADED,
    CLEANUP_REASON_EXCLUDE_TEMP_OR_UPLOAD_PATH,
    CLEANUP_REASON_EXCLUDE_UNKNOWN_DOCUMENT_TYPE,
    CLEANUP_REASON_KEEP_LATEST_5,
    CLEANUP_REASON_WOULD_DELETE_UPLOADED_BEYOND_LATEST_5,
    AccountingOriginalCleanupService,
)
from bot.services.db import ensure_archive_schema


NOW = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'cleanup.db'


def _ensure_schema(db_path: Path) -> None:
    with sqlite3.connect(db_path) as connection:
        ensure_archive_schema(connection)


def _original_path(
    storage_dir: Path,
    *,
    workspace_id: str = 'telegram-111001',
    document_type: str = 'receipt',
    document_id: str = 'doc-001',
) -> Path:
    folder = 'receipts' if document_type == 'receipt' else 'incoming_invoices'
    suffix = 'jpg' if document_type == 'receipt' else 'pdf'
    return (
        storage_dir
        / 'workspaces'
        / workspace_id
        / 'years'
        / '2026'
        / 'expenses'
        / '05'
        / folder
        / 'originals'
        / f'{document_id}.{suffix}'
    )


def _metadata_path(
    storage_dir: Path,
    *,
    workspace_id: str = 'telegram-111001',
    document_type: str = 'receipt',
    document_id: str = 'doc-001',
) -> Path:
    folder = 'receipts' if document_type == 'receipt' else 'incoming_invoices'
    return (
        storage_dir
        / 'workspaces'
        / workspace_id
        / 'years'
        / '2026'
        / 'expenses'
        / '05'
        / folder
        / 'metadata'
        / f'{document_id}.json'
    )


def _write_original(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'document')


def _write_metadata(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('{}', encoding='utf-8')


def _insert_state(
    db_path: Path,
    storage_dir: Path,
    *,
    document_id: str,
    workspace_id: str = 'telegram-111001',
    document_type: str = 'receipt',
    archive_status: str = 'uploaded',
    local_file_path: Path | None = None,
    metadata_path: Path | None = None,
    drive_file_id: str | None = 'drive-file',
    uploaded_at: datetime | str | None = NOW,
    create_file: bool = True,
) -> Path:
    _ensure_schema(db_path)
    original = local_file_path or _original_path(
        storage_dir,
        workspace_id=workspace_id,
        document_type=document_type,
        document_id=document_id,
    )
    metadata = metadata_path or _metadata_path(
        storage_dir,
        workspace_id=workspace_id,
        document_type=document_type,
        document_id=document_id,
    )
    if create_file:
        _write_original(original)
    _write_metadata(metadata)
    uploaded_at_text = uploaded_at.isoformat() if isinstance(uploaded_at, datetime) else uploaded_at
    timestamp = NOW.isoformat()
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            (
                'INSERT INTO accounting_document_archive_state '
                '(document_id, workspace_id, telegram_id, document_type, metadata_path, local_file_path, '
                'archive_status, latest_job_id, drive_file_id, drive_folder_id, uploaded_at, '
                'last_error_code, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
            ),
            (
                document_id,
                workspace_id,
                111001,
                document_type,
                str(metadata),
                str(original),
                archive_status,
                f'job-{document_id}',
                drive_file_id,
                'drive-folder',
                uploaded_at_text,
                None,
                timestamp,
                timestamp,
            ),
        )
    return original


def _dry_run(db_path: Path, storage_dir: Path):
    return AccountingOriginalCleanupService(db_path, storage_dir).dry_run()


def _items_by_document(result):
    return {item.document_id: item for item in result.items}


def test_uploaded_originals_beyond_latest_5_become_would_delete(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    for index in range(7):
        _insert_state(
            db_path,
            tmp_path,
            document_id=f'doc-{index}',
            uploaded_at=NOW + timedelta(minutes=index),
        )

    result = _dry_run(db_path, tmp_path)
    items = _items_by_document(result)

    assert result.scanned_count == 7
    assert result.keep_count == 5
    assert result.would_delete_count == 2
    assert items['doc-0'].action == CLEANUP_ACTION_WOULD_DELETE
    assert items['doc-0'].reason == CLEANUP_REASON_WOULD_DELETE_UPLOADED_BEYOND_LATEST_5
    assert items['doc-1'].action == CLEANUP_ACTION_WOULD_DELETE
    assert items['doc-6'].action == CLEANUP_ACTION_KEEP
    assert items['doc-6'].reason == CLEANUP_REASON_KEEP_LATEST_5


def test_receipts_and_incoming_invoices_are_grouped_separately(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    for index in range(6):
        _insert_state(
            db_path,
            tmp_path,
            document_id=f'receipt-{index}',
            document_type='receipt',
            uploaded_at=NOW + timedelta(minutes=index),
        )
        _insert_state(
            db_path,
            tmp_path,
            document_id=f'invoice-{index}',
            document_type='incoming_invoice',
            uploaded_at=NOW + timedelta(minutes=index),
        )

    result = _dry_run(db_path, tmp_path)
    items = _items_by_document(result)

    assert result.keep_count == 10
    assert result.would_delete_count == 2
    assert items['receipt-0'].action == CLEANUP_ACTION_WOULD_DELETE
    assert items['invoice-0'].action == CLEANUP_ACTION_WOULD_DELETE


def test_workspace_groups_do_not_affect_each_other(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    for workspace_id in ('telegram-111001', 'telegram-222002'):
        for index in range(6):
            _insert_state(
                db_path,
                tmp_path,
                workspace_id=workspace_id,
                document_id=f'{workspace_id}-doc-{index}',
                uploaded_at=NOW + timedelta(minutes=index),
            )

    result = _dry_run(db_path, tmp_path)
    items = _items_by_document(result)

    assert result.keep_count == 10
    assert result.would_delete_count == 2
    assert items['telegram-111001-doc-0'].action == CLEANUP_ACTION_WOULD_DELETE
    assert items['telegram-222002-doc-0'].action == CLEANUP_ACTION_WOULD_DELETE


def test_metadata_json_is_never_selected(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    metadata = _metadata_path(tmp_path, document_id='metadata-doc')
    _insert_state(
        db_path,
        tmp_path,
        document_id='metadata-doc',
        local_file_path=metadata,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_METADATA_PATH


@pytest.mark.parametrize(
    'status',
    ['pending', 'uploading', 'retry_wait', 'failed', 'abandoned', 'not_configured', 'unknown'],
)
def test_non_uploaded_statuses_are_excluded(tmp_path: Path, status: str) -> None:
    db_path = _db_path(tmp_path)
    _insert_state(
        db_path,
        tmp_path,
        document_id=f'{status}-doc',
        archive_status=status,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_NOT_UPLOADED


def test_missing_archive_state_scans_no_items(tmp_path: Path) -> None:
    result = _dry_run(_db_path(tmp_path), tmp_path)

    assert result.scanned_count == 0
    assert result.items == ()


def test_uploaded_without_drive_file_id_is_excluded(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    _insert_state(
        db_path,
        tmp_path,
        document_id='missing-drive',
        drive_file_id='',
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_MISSING_DRIVE_FILE_ID


def test_uploaded_without_uploaded_at_is_excluded(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    _insert_state(
        db_path,
        tmp_path,
        document_id='missing-uploaded-at',
        uploaded_at=None,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_MISSING_UPLOADED_AT


def test_invalid_path_outside_storage_dir_is_excluded(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    outside = tmp_path.parent / 'outside-receipt.jpg'
    outside.write_bytes(b'document')
    _insert_state(
        db_path,
        tmp_path,
        document_id='outside',
        local_file_path=outside,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_INVALID_PATH


def test_storage_invoices_path_is_rejected(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    invoice_path = tmp_path / 'invoices' / '2026' / 'invoice.pdf'
    invoice_path.parent.mkdir(parents=True)
    invoice_path.write_bytes(b'pdf')
    _insert_state(
        db_path,
        tmp_path,
        document_id='invoice-path',
        local_file_path=invoice_path,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_INVOICE_PATH


@pytest.mark.parametrize(
    'path_parts',
    [
        ('temp', 'accounting', 'receipt.jpg'),
        ('uploads', 'accounting_intake', 'receipt.jpg'),
        ('uploads', 'other', 'receipt.jpg'),
    ],
)
def test_temp_upload_and_accounting_intake_paths_are_rejected(
    tmp_path: Path,
    path_parts: tuple[str, ...],
) -> None:
    db_path = _db_path(tmp_path)
    local_path = tmp_path.joinpath(*path_parts)
    local_path.parent.mkdir(parents=True)
    local_path.write_bytes(b'document')
    _insert_state(
        db_path,
        tmp_path,
        document_id='temp-upload',
        local_file_path=local_path,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_TEMP_OR_UPLOAD_PATH


def test_missing_local_file_is_excluded_not_would_delete(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    _insert_state(
        db_path,
        tmp_path,
        document_id='missing-file',
        create_file=False,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_FILE_MISSING


def test_unknown_document_type_is_excluded(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    local_path = _original_path(
        tmp_path,
        document_id='unknown-type',
    )
    _insert_state(
        db_path,
        tmp_path,
        document_id='unknown-type',
        document_type='other',
        local_file_path=local_path,
    )

    item = _dry_run(db_path, tmp_path).items[0]

    assert item.action == CLEANUP_ACTION_EXCLUDE
    assert item.reason == CLEANUP_REASON_EXCLUDE_UNKNOWN_DOCUMENT_TYPE


def test_dry_run_does_not_call_delete_functions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = _db_path(tmp_path)
    for index in range(6):
        _insert_state(
            db_path,
            tmp_path,
            document_id=f'doc-{index}',
            uploaded_at=NOW + timedelta(minutes=index),
        )

    def fail_delete(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('dry-run cleanup must not delete files')

    monkeypatch.setattr(Path, 'unlink', fail_delete)
    monkeypatch.setattr(os, 'remove', fail_delete)
    monkeypatch.setattr(shutil, 'rmtree', fail_delete)

    result = _dry_run(db_path, tmp_path)

    assert result.would_delete_count == 1


def test_dry_run_does_not_mutate_db_rows(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    for index in range(6):
        _insert_state(
            db_path,
            tmp_path,
            document_id=f'doc-{index}',
            uploaded_at=NOW + timedelta(minutes=index),
        )
    with sqlite3.connect(db_path) as connection:
        before = list(connection.iterdump())

    _dry_run(db_path, tmp_path)

    with sqlite3.connect(db_path) as connection:
        after = list(connection.iterdump())
    assert after == before




def test_ordering_is_deterministic_on_equal_timestamps(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    for document_id in ('doc-a', 'doc-b', 'doc-c', 'doc-d', 'doc-e', 'doc-f'):
        _insert_state(
            db_path,
            tmp_path,
            document_id=document_id,
            uploaded_at=NOW,
        )

    result = _dry_run(db_path, tmp_path)
    items = _items_by_document(result)

    assert [item.document_id for item in result.items if item.action == CLEANUP_ACTION_KEEP] == [
        'doc-f',
        'doc-e',
        'doc-d',
        'doc-c',
        'doc-b',
    ]
    assert items['doc-a'].action == CLEANUP_ACTION_WOULD_DELETE
    assert items['doc-a'].rank_in_group == 6


def test_summary_counts_scanned_keep_would_delete_and_excluded(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    for index in range(6):
        _insert_state(
            db_path,
            tmp_path,
            document_id=f'uploaded-{index}',
            uploaded_at=NOW + timedelta(minutes=index),
        )
    _insert_state(
        db_path,
        tmp_path,
        document_id='pending',
        archive_status='pending',
    )

    result = _dry_run(db_path, tmp_path)

    assert result.scanned_count == 7
    assert result.keep_count == 5
    assert result.would_delete_count == 1
    assert result.excluded_count == 1
