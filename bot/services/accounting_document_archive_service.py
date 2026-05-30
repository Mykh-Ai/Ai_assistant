from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import sqlite3
from urllib.parse import quote

from bot.services.archive_job_service import (
    ARCHIVE_JOB_ABANDONED,
    ARCHIVE_JOB_FAILED,
    ARCHIVE_JOB_PENDING,
    ARCHIVE_JOB_RETRY_WAIT,
    ARCHIVE_JOB_UPLOADED,
    ARCHIVE_JOB_UPLOADING,
    ArchiveJobRecord,
    ArchiveJobService,
    ArchiveJobServiceError,
)
from bot.services.db import ensure_archive_schema, managed_connection


ARCHIVE_STATUS_PENDING = 'pending'
ARCHIVE_STATUS_UPLOADING = 'uploading'
ARCHIVE_STATUS_UPLOADED = 'uploaded'
ARCHIVE_STATUS_RETRY_WAIT = 'retry_wait'
ARCHIVE_STATUS_FAILED = 'failed'
ARCHIVE_STATUS_ABANDONED = 'abandoned'


class AccountingDocumentArchiveServiceError(ValueError):
    pass


@dataclass(frozen=True)
class AccountingDocumentArchiveState:
    document_id: str
    workspace_id: str
    telegram_id: int
    document_type: str
    metadata_path: str | None
    local_file_path: str
    archive_status: str
    latest_job_id: str | None
    drive_file_id: str | None
    drive_folder_id: str | None
    uploaded_at: str | None
    last_error_code: str | None
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class AccountingDocumentArchiveEnqueueResult:
    job: ArchiveJobRecord
    state: AccountingDocumentArchiveState


class AccountingDocumentArchiveService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._jobs = ArchiveJobService(db_path)

    def ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.commit()

    def enqueue_confirmed_document(
        self,
        *,
        workspace_id: str,
        telegram_id: int,
        document_id: str,
        document_type: str,
        local_file_path: str | Path,
        metadata_path: str | Path | None = None,
        target_folder_path: str | None = None,
        now: datetime | None = None,
    ) -> AccountingDocumentArchiveEnqueueResult:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        document_id = _required_text(document_id, 'document_id')
        document_type = _required_text(document_type, 'document_type')
        local_file_path_text = _required_text(str(local_file_path), 'local_file_path')
        metadata_path_text = _optional_text(metadata_path)
        if telegram_id <= 0:
            raise AccountingDocumentArchiveServiceError('telegram_id_required')

        job = self._jobs.enqueue_job(
            workspace_id=workspace_id,
            telegram_id=telegram_id,
            document_id=document_id,
            document_type=document_type,
            local_file_path=local_file_path_text,
            metadata_path=metadata_path_text,
            target_folder_path=target_folder_path,
            now=now,
        )
        state = self._upsert_state_for_job(
            job,
            archive_status=_state_status_for_job_status(job.status),
            last_error_code=job.error_code,
            now_text=job.updated_at,
        )
        return AccountingDocumentArchiveEnqueueResult(job=job, state=state)

    def get_state(self, *, workspace_id: str, document_id: str) -> AccountingDocumentArchiveState | None:
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                (
                    'SELECT * FROM accounting_document_archive_state '
                    'WHERE workspace_id = ? AND document_id = ?'
                ),
                (workspace_id, document_id),
            ).fetchone()
        return _state_from_row(row) if row is not None else None

    def get_state_read_only(self, *, workspace_id: str, document_id: str) -> AccountingDocumentArchiveState | None:
        if not self._db_path.exists():
            return None
        db_uri = f"file:{quote(self._db_path.resolve().as_posix(), safe='/:')}?mode=ro"
        try:
            with sqlite3.connect(db_uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                row = connection.execute(
                    (
                        'SELECT * FROM accounting_document_archive_state '
                        'WHERE workspace_id = ? AND document_id = ?'
                    ),
                    (workspace_id, document_id),
                ).fetchone()
        except sqlite3.OperationalError:
            return None
        return _state_from_row(row) if row is not None else None

    def mark_uploading(self, job_id: str, *, now: datetime | None = None) -> AccountingDocumentArchiveState:
        self._require_existing_state(job_id)
        job = self._jobs.mark_uploading(job_id, now=now)
        return self._update_state_from_job(job, archive_status=ARCHIVE_STATUS_UPLOADING)

    def mark_uploaded(
        self,
        job_id: str,
        *,
        drive_file_id: str,
        drive_folder_id: str | None = None,
        uploaded_at: datetime | None = None,
    ) -> AccountingDocumentArchiveState:
        self._require_existing_state(job_id)
        job = self._jobs.mark_uploaded(
            job_id,
            drive_file_id=drive_file_id,
            drive_folder_id=drive_folder_id,
            uploaded_at=uploaded_at,
        )
        return self._update_state_from_job(
            job,
            archive_status=ARCHIVE_STATUS_UPLOADED,
            drive_file_id=job.drive_file_id,
            drive_folder_id=job.drive_folder_id,
            uploaded_at=job.uploaded_at,
            last_error_code=None,
        )

    def mark_retry_wait(
        self,
        job_id: str,
        *,
        error_code: str,
        next_attempt_at: datetime | None = None,
        now: datetime | None = None,
    ) -> AccountingDocumentArchiveState:
        self._require_existing_state(job_id)
        job = self._jobs.mark_retry_wait(
            job_id,
            error_code=error_code,
            next_attempt_at=next_attempt_at,
            now=now,
        )
        return self._update_state_from_job(
            job,
            archive_status=_state_status_for_job_status(job.status),
            last_error_code=job.error_code,
        )

    def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        now: datetime | None = None,
    ) -> AccountingDocumentArchiveState:
        self._require_existing_state(job_id)
        job = self._jobs.mark_failed(job_id, error_code=error_code, now=now)
        return self._update_state_from_job(
            job,
            archive_status=ARCHIVE_STATUS_FAILED,
            last_error_code=job.error_code,
        )

    def mark_abandoned(
        self,
        job_id: str,
        *,
        error_code: str,
        now: datetime | None = None,
    ) -> AccountingDocumentArchiveState:
        self._require_existing_state(job_id)
        job = self._jobs.mark_abandoned(job_id, error_code=error_code, now=now)
        return self._update_state_from_job(
            job,
            archive_status=ARCHIVE_STATUS_ABANDONED,
            last_error_code=job.error_code,
        )

    def _upsert_state_for_job(
        self,
        job: ArchiveJobRecord,
        *,
        archive_status: str,
        last_error_code: str | None,
        now_text: str,
    ) -> AccountingDocumentArchiveState:
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            existing = connection.execute(
                (
                    'SELECT * FROM accounting_document_archive_state '
                    'WHERE workspace_id = ? AND document_id = ?'
                ),
                (job.workspace_id, job.document_id),
            ).fetchone()
            if existing is None:
                connection.execute(
                    (
                        'INSERT INTO accounting_document_archive_state '
                        '(document_id, workspace_id, telegram_id, document_type, metadata_path, local_file_path, '
                        'archive_status, latest_job_id, drive_file_id, drive_folder_id, uploaded_at, '
                        'last_error_code, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
                    ),
                    (
                        job.document_id,
                        job.workspace_id,
                        job.telegram_id,
                        job.document_type,
                        job.metadata_path,
                        job.local_file_path,
                        archive_status,
                        job.job_id,
                        job.drive_file_id,
                        job.drive_folder_id,
                        job.uploaded_at,
                        last_error_code,
                        now_text,
                        now_text,
                    ),
                )
            else:
                connection.execute(
                    (
                        'UPDATE accounting_document_archive_state SET telegram_id = ?, document_type = ?, '
                        'metadata_path = ?, local_file_path = ?, archive_status = ?, latest_job_id = ?, '
                        'drive_file_id = ?, drive_folder_id = ?, uploaded_at = ?, last_error_code = ?, '
                        'updated_at = ? WHERE workspace_id = ? AND document_id = ?'
                    ),
                    (
                        job.telegram_id,
                        job.document_type,
                        job.metadata_path,
                        job.local_file_path,
                        archive_status,
                        job.job_id,
                        job.drive_file_id,
                        job.drive_folder_id,
                        job.uploaded_at,
                        last_error_code,
                        now_text,
                        job.workspace_id,
                        job.document_id,
                    ),
                )
            connection.commit()
            row = connection.execute(
                (
                    'SELECT * FROM accounting_document_archive_state '
                    'WHERE workspace_id = ? AND document_id = ?'
                ),
                (job.workspace_id, job.document_id),
            ).fetchone()
            if row is None:
                raise AccountingDocumentArchiveServiceError('state_not_found_after_upsert')
            return _state_from_row(row)

    def _update_state_from_job(
        self,
        job: ArchiveJobRecord,
        *,
        archive_status: str,
        drive_file_id: str | None = None,
        drive_folder_id: str | None = None,
        uploaded_at: str | None = None,
        last_error_code: str | None = None,
    ) -> AccountingDocumentArchiveState:
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute(
                (
                    'UPDATE accounting_document_archive_state SET archive_status = ?, latest_job_id = ?, '
                    'drive_file_id = ?, drive_folder_id = ?, uploaded_at = ?, last_error_code = ?, '
                    'updated_at = ? WHERE workspace_id = ? AND document_id = ?'
                ),
                (
                    archive_status,
                    job.job_id,
                    drive_file_id if drive_file_id is not None else job.drive_file_id,
                    drive_folder_id if drive_folder_id is not None else job.drive_folder_id,
                    uploaded_at if uploaded_at is not None else job.uploaded_at,
                    last_error_code,
                    job.updated_at,
                    job.workspace_id,
                    job.document_id,
                ),
            )
            connection.commit()
            row = connection.execute(
                (
                    'SELECT * FROM accounting_document_archive_state '
                    'WHERE workspace_id = ? AND document_id = ?'
                ),
                (job.workspace_id, job.document_id),
            ).fetchone()
            if row is None:
                raise AccountingDocumentArchiveServiceError('state_not_found')
            return _state_from_row(row)

    def _require_existing_state(self, job_id: str) -> AccountingDocumentArchiveState:
        job = self._jobs.get_job(job_id)
        if job is None:
            raise AccountingDocumentArchiveServiceError('job_not_found')
        state = self.get_state(workspace_id=job.workspace_id, document_id=job.document_id)
        if state is None:
            raise AccountingDocumentArchiveServiceError('archive_state_missing')
        return state


def _state_status_for_job_status(status: str) -> str:
    mapping = {
        ARCHIVE_JOB_PENDING: ARCHIVE_STATUS_PENDING,
        ARCHIVE_JOB_UPLOADING: ARCHIVE_STATUS_UPLOADING,
        ARCHIVE_JOB_UPLOADED: ARCHIVE_STATUS_UPLOADED,
        ARCHIVE_JOB_RETRY_WAIT: ARCHIVE_STATUS_RETRY_WAIT,
        ARCHIVE_JOB_FAILED: ARCHIVE_STATUS_FAILED,
        ARCHIVE_JOB_ABANDONED: ARCHIVE_STATUS_ABANDONED,
    }
    try:
        return mapping[status]
    except KeyError as exc:
        raise ArchiveJobServiceError('unsupported_job_status') from exc


def _state_from_row(row: sqlite3.Row) -> AccountingDocumentArchiveState:
    return AccountingDocumentArchiveState(
        document_id=row['document_id'],
        workspace_id=row['workspace_id'],
        telegram_id=int(row['telegram_id']),
        document_type=row['document_type'],
        metadata_path=row['metadata_path'],
        local_file_path=row['local_file_path'],
        archive_status=row['archive_status'],
        latest_job_id=row['latest_job_id'],
        drive_file_id=row['drive_file_id'],
        drive_folder_id=row['drive_folder_id'],
        uploaded_at=row['uploaded_at'],
        last_error_code=row['last_error_code'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def _required_text(value: object, field_name: str) -> str:
    text = str(value).strip() if value is not None else ''
    if not text:
        raise AccountingDocumentArchiveServiceError(f'{field_name}_required')
    return text


def _optional_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
