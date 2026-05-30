from __future__ import annotations

from datetime import UTC, datetime, timedelta
import inspect
import sqlite3
from pathlib import Path

import pytest

from bot.services import archive_worker
from bot.services.accounting_document_archive_service import (
    AccountingDocumentArchiveService,
)
from bot.services.archive_job_service import (
    ARCHIVE_JOB_ABANDONED,
    ARCHIVE_JOB_FAILED,
    ARCHIVE_JOB_RETRY_WAIT,
    ARCHIVE_JOB_UPLOADED,
    ArchiveJobService,
)
from bot.services.archive_worker import (
    ARCHIVE_ERROR_PERMANENT,
    ARCHIVE_ERROR_TRANSIENT,
    ARCHIVE_ERROR_UNEXPECTED,
    ARCHIVE_WORKER_NOOP,
    ArchiveUploadPermanentError,
    ArchiveUploadResult,
    ArchiveUploadTransientError,
    ArchiveWorker,
)


NOW = datetime(2026, 5, 30, 10, 0, tzinfo=UTC)
WORKSPACE_ID = "telegram-111001"
TELEGRAM_ID = 111001


class FakeArchiveProvider:
    def __init__(self, outcome: str = "success") -> None:
        self.outcome = outcome
        self.calls: list[dict[str, object]] = []

    def upload_file(
        self,
        *,
        local_file_path: Path,
        target_folder_path: str | None,
        document_type: str,
        metadata: dict[str, object],
    ) -> ArchiveUploadResult:
        self.calls.append(
            {
                "local_file_path": local_file_path,
                "target_folder_path": target_folder_path,
                "document_type": document_type,
                "metadata": metadata,
            }
        )
        if self.outcome == "transient":
            raise ArchiveUploadTransientError("temporary provider issue")
        if self.outcome == "permanent":
            raise ArchiveUploadPermanentError("permanent provider issue")
        if self.outcome == "unexpected":
            raise RuntimeError(f"secret-token leaked in {local_file_path}")
        if self.outcome == "empty_id":
            return ArchiveUploadResult(drive_file_id="", drive_folder_id="fake-folder")
        return ArchiveUploadResult(
            drive_file_id=f"fake-drive-{metadata['document_id']}",
            drive_folder_id="fake-folder-2026-05",
        )


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / "archive-worker.sqlite3"


def _confirmed_paths(
    tmp_path: Path,
    *,
    workspace_id: str = WORKSPACE_ID,
    document_id: str = "receipt-001",
    document_type: str = "receipt",
) -> tuple[str, str]:
    leaf = "receipts" if document_type == "receipt" else "incoming_invoices"
    suffix = "jpg" if document_type == "receipt" else "pdf"
    base = tmp_path / "workspaces" / workspace_id / "years" / "2026" / "expenses" / "05" / leaf
    original = base / "originals" / f"{document_id}.{suffix}"
    metadata = base / "metadata" / f"{document_id}.json"
    original.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"document")
    metadata.write_text("{}", encoding="utf-8")
    return str(original), str(metadata)


def _enqueue_document(
    tmp_path: Path,
    *,
    db_path: Path | None = None,
    document_id: str = "receipt-001",
    document_type: str = "receipt",
) -> tuple[Path, object, str, str]:
    database = db_path or _db_path(tmp_path)
    original_path, metadata_path = _confirmed_paths(
        tmp_path,
        document_id=document_id,
        document_type=document_type,
    )
    service = AccountingDocumentArchiveService(database)
    record = service.enqueue_confirmed_document(
        workspace_id=WORKSPACE_ID,
        telegram_id=TELEGRAM_ID,
        document_id=document_id,
        document_type=document_type,
        local_file_path=original_path,
        metadata_path=metadata_path,
    )
    return database, record, original_path, metadata_path


def _job(db_path: Path, job_id: str):
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT status, attempts, max_attempts, local_file_path, drive_file_id,
                   drive_folder_id, error_code, lease_until
            FROM archive_jobs
            WHERE job_id = ?
            """,
            (job_id,),
        ).fetchone()
    return row


def _set_max_attempts(db_path: Path, job_id: str, max_attempts: int) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "UPDATE archive_jobs SET max_attempts = ? WHERE job_id = ?",
            (max_attempts, job_id),
        )


def test_worker_no_runnable_job_returns_noop(tmp_path: Path) -> None:
    provider = FakeArchiveProvider()
    worker = ArchiveWorker(_db_path(tmp_path), provider)

    result = worker.process_one(now=NOW)

    assert result.status == ARCHIVE_WORKER_NOOP
    assert provider.calls == []


def test_worker_claims_pending_and_uploads_updates_job_and_state(tmp_path: Path) -> None:
    db_path, record, original_path, _metadata_path = _enqueue_document(tmp_path)
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider).process_one(now=NOW)

    assert result.status == ARCHIVE_JOB_UPLOADED
    assert result.job_id == record.job.job_id
    job = _job(db_path, record.job.job_id)
    assert job[0] == ARCHIVE_JOB_UPLOADED
    assert job[4] == f"fake-drive-{record.job.document_id}"
    assert job[5] == "fake-folder-2026-05"
    assert job[7] is None
    state = AccountingDocumentArchiveService(db_path).get_state(
        workspace_id=WORKSPACE_ID,
        document_id=record.job.document_id,
    )
    assert state is not None
    assert state.archive_status == ARCHIVE_JOB_UPLOADED
    assert state.drive_file_id == f"fake-drive-{record.job.document_id}"
    assert Path(original_path).exists()
    assert provider.calls[0]["local_file_path"] == Path(original_path)


def test_worker_claims_due_retry_wait_job(tmp_path: Path) -> None:
    db_path, record, _original_path, _metadata_path = _enqueue_document(tmp_path)
    archive_service = AccountingDocumentArchiveService(db_path)
    archive_service.mark_uploading(record.job.job_id, now=NOW - timedelta(hours=2))
    archive_service.mark_retry_wait(
        record.job.job_id,
        error_code=ARCHIVE_ERROR_TRANSIENT,
        next_attempt_at=NOW - timedelta(minutes=1),
        now=NOW - timedelta(hours=1),
    )
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider).process_one(now=NOW)

    assert result.status == ARCHIVE_JOB_UPLOADED
    assert len(provider.calls) == 1


def test_worker_does_not_claim_retry_wait_before_due(tmp_path: Path) -> None:
    db_path, record, _original_path, _metadata_path = _enqueue_document(tmp_path)
    archive_service = AccountingDocumentArchiveService(db_path)
    archive_service.mark_uploading(record.job.job_id, now=NOW - timedelta(hours=2))
    archive_service.mark_retry_wait(
        record.job.job_id,
        error_code=ARCHIVE_ERROR_TRANSIENT,
        next_attempt_at=NOW + timedelta(minutes=10),
        now=NOW - timedelta(hours=1),
    )
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider).process_one(now=NOW)

    assert result.status == ARCHIVE_WORKER_NOOP
    assert provider.calls == []


def test_transient_failure_sets_retry_wait_and_preserves_local_file(tmp_path: Path) -> None:
    db_path, record, original_path, _metadata_path = _enqueue_document(tmp_path)

    result = ArchiveWorker(db_path, FakeArchiveProvider("transient")).process_one(now=NOW)

    job = _job(db_path, record.job.job_id)
    assert result.status == ARCHIVE_JOB_RETRY_WAIT
    assert result.error_code == ARCHIVE_ERROR_TRANSIENT
    assert job[0] == ARCHIVE_JOB_RETRY_WAIT
    assert job[1] == 1
    assert job[3] == original_path
    assert job[6] == ARCHIVE_ERROR_TRANSIENT
    assert Path(original_path).exists()
    state = AccountingDocumentArchiveService(db_path).get_state(
        workspace_id=WORKSPACE_ID,
        document_id=record.job.document_id,
    )
    assert state is not None
    assert state.archive_status == ARCHIVE_JOB_RETRY_WAIT


def test_permanent_failure_sets_failed_and_preserves_local_file(tmp_path: Path) -> None:
    db_path, record, original_path, _metadata_path = _enqueue_document(tmp_path)

    result = ArchiveWorker(db_path, FakeArchiveProvider("permanent")).process_one(now=NOW)

    job = _job(db_path, record.job.job_id)
    assert result.status == ARCHIVE_JOB_FAILED
    assert result.error_code == ARCHIVE_ERROR_PERMANENT
    assert job[0] == ARCHIVE_JOB_FAILED
    assert job[3] == original_path
    assert job[6] == ARCHIVE_ERROR_PERMANENT
    assert Path(original_path).exists()


def test_max_attempts_transient_failure_becomes_failed(tmp_path: Path) -> None:
    db_path, record, original_path, _metadata_path = _enqueue_document(tmp_path)
    _set_max_attempts(db_path, record.job.job_id, 1)

    result = ArchiveWorker(db_path, FakeArchiveProvider("transient")).process_one(now=NOW)

    job = _job(db_path, record.job.job_id)
    assert result.status == ARCHIVE_JOB_FAILED
    assert job[0] == ARCHIVE_JOB_FAILED
    assert job[1] == 1
    assert job[2] == 1
    assert job[3] == original_path
    assert Path(original_path).exists()


def test_terminal_jobs_are_not_processed(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    archive_service = AccountingDocumentArchiveService(db_path)
    statuses = [
        ("uploaded-doc", ARCHIVE_JOB_UPLOADED),
        ("failed-doc", ARCHIVE_JOB_FAILED),
        ("abandoned-doc", ARCHIVE_JOB_ABANDONED),
    ]
    for document_id, status in statuses:
        _database, record, _original_path, _metadata_path = _enqueue_document(
            tmp_path,
            db_path=db_path,
            document_id=document_id,
        )
        archive_service.mark_uploading(record.job.job_id, now=NOW - timedelta(minutes=5))
        if status == ARCHIVE_JOB_UPLOADED:
            archive_service.mark_uploaded(
                record.job.job_id,
                drive_file_id="done",
                drive_folder_id="folder",
                uploaded_at=NOW - timedelta(minutes=4),
            )
        elif status == ARCHIVE_JOB_FAILED:
            archive_service.mark_failed(
                record.job.job_id,
                error_code=ARCHIVE_ERROR_PERMANENT,
                now=NOW - timedelta(minutes=4),
            )
        else:
            archive_service.mark_abandoned(
                record.job.job_id,
                error_code=ARCHIVE_ERROR_PERMANENT,
                now=NOW - timedelta(minutes=4),
            )
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider).process_one(now=NOW)

    assert result.status == ARCHIVE_WORKER_NOOP
    assert provider.calls == []


def test_active_lease_prevents_second_worker_claim(tmp_path: Path) -> None:
    db_path, _record, _original_path, _metadata_path = _enqueue_document(tmp_path)
    ArchiveJobService(db_path).claim_next_runnable_job(
        worker_id="worker-a",
        lease_seconds=60,
        now=NOW,
    )
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider, worker_id="worker-b").process_one(now=NOW)

    assert result.status == ARCHIVE_WORKER_NOOP
    assert provider.calls == []


def test_expired_lease_can_be_reclaimed(tmp_path: Path) -> None:
    db_path, record, _original_path, _metadata_path = _enqueue_document(tmp_path)
    ArchiveJobService(db_path).claim_next_runnable_job(
        worker_id="worker-a",
        lease_seconds=60,
        now=NOW,
    )
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider, worker_id="worker-b").process_one(
        now=NOW + timedelta(seconds=61),
    )

    assert result.status == ARCHIVE_JOB_UPLOADED
    assert _job(db_path, record.job.job_id)[0] == ARCHIVE_JOB_UPLOADED
    assert len(provider.calls) == 1


def test_direct_job_without_archive_state_fails_safe(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    original_path, metadata_path = _confirmed_paths(tmp_path, document_id="direct-doc")
    job = ArchiveJobService(db_path).enqueue_job(
        workspace_id=WORKSPACE_ID,
        telegram_id=TELEGRAM_ID,
        document_id="direct-doc",
        document_type="receipt",
        local_file_path=original_path,
        metadata_path=metadata_path,
    )
    provider = FakeArchiveProvider()

    result = ArchiveWorker(db_path, provider).process_one(now=NOW)

    assert result.status == ARCHIVE_JOB_FAILED
    assert result.error_code == ARCHIVE_ERROR_UNEXPECTED
    assert provider.calls == []
    assert _job(db_path, job.job_id)[0] == ARCHIVE_JOB_FAILED
    assert Path(original_path).exists()


def test_unexpected_provider_failure_uses_bounded_log_and_error_code(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    db_path, record, original_path, _metadata_path = _enqueue_document(tmp_path)

    with caplog.at_level("WARNING", logger="bot.services.archive_worker"):
        result = ArchiveWorker(db_path, FakeArchiveProvider("unexpected")).process_one(now=NOW)

    assert result.status == ARCHIVE_JOB_RETRY_WAIT
    assert result.error_code == ARCHIVE_ERROR_UNEXPECTED
    assert _job(db_path, record.job.job_id)[6] == ARCHIVE_ERROR_UNEXPECTED
    assert "upload_unexpected_failed" in caplog.text
    assert "secret-token" not in caplog.text
    assert original_path not in caplog.text


def test_empty_provider_file_id_is_treated_as_unexpected_retry(tmp_path: Path) -> None:
    db_path, record, _original_path, _metadata_path = _enqueue_document(tmp_path)

    result = ArchiveWorker(db_path, FakeArchiveProvider("empty_id")).process_one(now=NOW)

    assert result.status == ARCHIVE_JOB_RETRY_WAIT
    assert result.error_code == ARCHIVE_ERROR_UNEXPECTED
    assert _job(db_path, record.job.job_id)[0] == ARCHIVE_JOB_RETRY_WAIT


def test_archive_worker_has_no_google_or_network_runtime_imports() -> None:
    source = inspect.getsource(archive_worker)

    forbidden = [
        "googleapiclient",
        "google.auth",
        "requests",
        "httpx",
        "aiohttp",
        "socket",
    ]
    assert all(token not in source for token in forbidden)
    assert "claim_next_runnable_job" in source
