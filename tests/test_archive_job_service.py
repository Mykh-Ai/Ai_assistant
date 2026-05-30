from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import inspect
import sqlite3

import pytest

from bot.services import archive_job_service
from bot.services.archive_job_service import (
    ARCHIVE_JOB_ABANDONED,
    ARCHIVE_JOB_FAILED,
    ARCHIVE_JOB_PENDING,
    ARCHIVE_JOB_RETRY_WAIT,
    ARCHIVE_JOB_UPLOADED,
    ARCHIVE_JOB_UPLOADING,
    ArchiveJobService,
    ArchiveJobServiceError,
)
from bot.services.db import init_db


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'archive.db'


def _local_file(tmp_path: Path) -> Path:
    path = tmp_path / 'workspaces' / 'telegram-111001' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'originals' / 'receipt.jpg'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'jpeg')
    return path


def test_archive_schema_bootstrap_is_idempotent(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    init_db(db_path)
    service = ArchiveJobService(db_path)

    service.ensure_schema()
    service.ensure_schema()

    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert 'archive_jobs' in tables
    assert 'accounting_document_archive_state' in tables


def test_enqueue_creates_pending_archive_job(tmp_path: Path) -> None:
    service = ArchiveJobService(_db_path(tmp_path))
    local_file = _local_file(tmp_path)

    job = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-1',
        document_type='receipt',
        local_file_path=local_file,
        metadata_path=tmp_path / 'metadata.json',
    )

    assert job.status == ARCHIVE_JOB_PENDING
    assert job.workspace_id == 'telegram-111001'
    assert job.document_id == 'receipt-1'
    assert job.local_file_path == str(local_file)
    assert job.metadata_path == str(tmp_path / 'metadata.json')
    assert job.provider == 'google_drive'
    assert job.attempts == 0


def test_enqueue_is_idempotent_for_same_active_document(tmp_path: Path) -> None:
    service = ArchiveJobService(_db_path(tmp_path))
    local_file = _local_file(tmp_path)

    first = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-1',
        document_type='receipt',
        local_file_path=local_file,
    )
    second = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-1',
        document_type='receipt',
        local_file_path=local_file,
    )

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        count = connection.execute('SELECT COUNT(*) FROM archive_jobs').fetchone()[0]

    assert second.job_id == first.job_id
    assert count == 1


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('workspace_id', ''),
        ('telegram_id', 0),
        ('document_id', ''),
        ('document_type', ''),
        ('local_file_path', ''),
    ],
)
def test_enqueue_rejects_missing_required_fields(tmp_path: Path, field: str, value: object) -> None:
    payload = {
        'workspace_id': 'telegram-111001',
        'telegram_id': 111001,
        'document_id': 'receipt-1',
        'document_type': 'receipt',
        'local_file_path': str(_local_file(tmp_path)),
    }
    payload[field] = value

    with pytest.raises(ArchiveJobServiceError):
        ArchiveJobService(_db_path(tmp_path)).enqueue_job(**payload)


def test_list_runnable_jobs_includes_pending_and_due_retry_wait(tmp_path: Path) -> None:
    service = ArchiveJobService(_db_path(tmp_path))
    local_file = _local_file(tmp_path)
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
    pending = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-pending',
        document_type='receipt',
        local_file_path=local_file,
        now=now,
    )
    retry = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-retry',
        document_type='receipt',
        local_file_path=local_file,
        now=now,
    )
    service.mark_retry_wait(
        retry.job_id,
        error_code='temporary_error',
        next_attempt_at=now - timedelta(minutes=1),
        now=now,
    )

    jobs = service.list_runnable_jobs(now=now, limit=10)

    assert [job.job_id for job in jobs] == [pending.job_id, retry.job_id]


def test_mark_uploading_and_uploaded_store_drive_ids(tmp_path: Path) -> None:
    service = ArchiveJobService(_db_path(tmp_path))
    job = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-1',
        document_type='receipt',
        local_file_path=_local_file(tmp_path),
    )

    uploading = service.mark_uploading(job.job_id)
    uploaded_at = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
    uploaded = service.mark_uploaded(
        job.job_id,
        drive_file_id='fake-drive-file-id',
        drive_folder_id='fake-drive-folder-id',
        uploaded_at=uploaded_at,
    )

    assert uploading.status == ARCHIVE_JOB_UPLOADING
    assert uploaded.status == ARCHIVE_JOB_UPLOADED
    assert uploaded.drive_file_id == 'fake-drive-file-id'
    assert uploaded.drive_folder_id == 'fake-drive-folder-id'
    assert uploaded.uploaded_at == uploaded_at.isoformat()


def test_transient_failure_sets_retry_wait_and_keeps_local_file(tmp_path: Path) -> None:
    service = ArchiveJobService(_db_path(tmp_path))
    local_file = _local_file(tmp_path)
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
    job = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-1',
        document_type='receipt',
        local_file_path=local_file,
        now=now,
    )

    retry = service.mark_retry_wait(
        job.job_id,
        error_code='rate_limited',
        next_attempt_at=now + timedelta(minutes=30),
        now=now,
    )

    assert retry.status == ARCHIVE_JOB_RETRY_WAIT
    assert retry.attempts == 1
    assert retry.error_code == 'rate_limited'
    assert retry.next_attempt_at == (now + timedelta(minutes=30)).isoformat()
    assert local_file.exists()


def test_max_attempts_sets_failed_and_permanent_failure_can_be_abandoned(tmp_path: Path) -> None:
    service = ArchiveJobService(_db_path(tmp_path))
    local_file = _local_file(tmp_path)
    job = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-1',
        document_type='receipt',
        local_file_path=local_file,
        max_attempts=1,
    )

    failed = service.mark_retry_wait(job.job_id, error_code='quota_exceeded')
    abandoned_seed = service.enqueue_job(
        workspace_id='telegram-111001',
        telegram_id=111001,
        document_id='receipt-2',
        document_type='receipt',
        local_file_path=local_file,
    )
    abandoned = service.mark_abandoned(abandoned_seed.job_id, error_code='permission_denied')

    assert failed.status == ARCHIVE_JOB_FAILED
    assert failed.next_attempt_at is None
    assert abandoned.status == ARCHIVE_JOB_ABANDONED
    assert abandoned.error_code == 'permission_denied'
    assert local_file.exists()


def test_archive_job_service_has_no_google_or_network_imports() -> None:
    source = inspect.getsource(archive_job_service)

    forbidden = ('googleapiclient', 'google.auth', 'requests', 'httpx', 'aiohttp')

    assert not any(name in source for name in forbidden)
