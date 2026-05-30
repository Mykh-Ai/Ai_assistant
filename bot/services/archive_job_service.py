from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
import sqlite3
from uuid import uuid4

from bot.services.db import ensure_archive_schema, managed_connection


ARCHIVE_PROVIDER_GOOGLE_DRIVE = 'google_drive'

ARCHIVE_JOB_PENDING = 'pending'
ARCHIVE_JOB_UPLOADING = 'uploading'
ARCHIVE_JOB_UPLOADED = 'uploaded'
ARCHIVE_JOB_RETRY_WAIT = 'retry_wait'
ARCHIVE_JOB_FAILED = 'failed'
ARCHIVE_JOB_ABANDONED = 'abandoned'

ACTIVE_ARCHIVE_JOB_STATUSES = (
    ARCHIVE_JOB_PENDING,
    ARCHIVE_JOB_UPLOADING,
    ARCHIVE_JOB_RETRY_WAIT,
)


class ArchiveJobServiceError(ValueError):
    pass


@dataclass(frozen=True)
class ArchiveJobRecord:
    job_id: str
    workspace_id: str
    telegram_id: int
    document_id: str
    document_type: str
    local_file_path: str
    metadata_path: str | None
    provider: str
    target_folder_path: str | None
    status: str
    attempts: int
    max_attempts: int
    next_attempt_at: str | None
    drive_file_id: str | None
    drive_folder_id: str | None
    error_code: str | None
    created_at: str
    updated_at: str
    uploaded_at: str | None


class ArchiveJobService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.commit()

    def enqueue_job(
        self,
        *,
        workspace_id: str,
        telegram_id: int,
        document_id: str,
        document_type: str,
        local_file_path: str | Path,
        metadata_path: str | Path | None = None,
        provider: str = ARCHIVE_PROVIDER_GOOGLE_DRIVE,
        target_folder_path: str | None = None,
        max_attempts: int = 5,
        now: datetime | None = None,
    ) -> ArchiveJobRecord:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        document_id = _required_text(document_id, 'document_id')
        document_type = _required_text(document_type, 'document_type')
        provider = _required_text(provider, 'provider')
        local_file_path_text = _required_text(str(local_file_path), 'local_file_path')
        metadata_path_text = _optional_text(metadata_path)
        if telegram_id <= 0:
            raise ArchiveJobServiceError('telegram_id_required')
        if max_attempts <= 0:
            raise ArchiveJobServiceError('max_attempts_must_be_positive')

        timestamp = _format_timestamp(now)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            existing = self._get_active_job_row(
                connection,
                workspace_id=workspace_id,
                document_id=document_id,
                provider=provider,
            )
            if existing is not None:
                return _job_from_row(existing)

            job_id = str(uuid4())
            connection.execute(
                (
                    'INSERT INTO archive_jobs '
                    '(job_id, workspace_id, telegram_id, document_id, document_type, local_file_path, '
                    'metadata_path, provider, target_folder_path, status, attempts, max_attempts, '
                    'next_attempt_at, drive_file_id, drive_folder_id, error_code, created_at, updated_at, uploaded_at) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, NULL, ?, ?, NULL)'
                ),
                (
                    job_id,
                    workspace_id,
                    telegram_id,
                    document_id,
                    document_type,
                    local_file_path_text,
                    metadata_path_text,
                    provider,
                    target_folder_path,
                    ARCHIVE_JOB_PENDING,
                    max_attempts,
                    timestamp,
                    timestamp,
                ),
            )
            connection.commit()
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found_after_insert')
            return _job_from_row(row)

    def get_job(self, job_id: str) -> ArchiveJobRecord | None:
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_job_row(connection, job_id)
        return _job_from_row(row) if row is not None else None

    def list_runnable_jobs(
        self,
        *,
        provider: str = ARCHIVE_PROVIDER_GOOGLE_DRIVE,
        limit: int = 20,
        now: datetime | None = None,
    ) -> list[ArchiveJobRecord]:
        if limit <= 0:
            return []
        current = _format_timestamp(now)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            rows = connection.execute(
                (
                    'SELECT * FROM archive_jobs '
                    'WHERE provider = ? AND (status = ? OR (status = ? AND (next_attempt_at IS NULL OR next_attempt_at <= ?))) '
                    'ORDER BY created_at ASC LIMIT ?'
                ),
                (provider, ARCHIVE_JOB_PENDING, ARCHIVE_JOB_RETRY_WAIT, current, limit),
            ).fetchall()
        return [_job_from_row(row) for row in rows]

    def mark_uploading(self, job_id: str, *, now: datetime | None = None) -> ArchiveJobRecord:
        return self._update_status(
            job_id,
            status=ARCHIVE_JOB_UPLOADING,
            now=now,
            clear_next_attempt=True,
            clear_error=True,
        )

    def mark_uploaded(
        self,
        job_id: str,
        *,
        drive_file_id: str,
        drive_folder_id: str | None = None,
        uploaded_at: datetime | None = None,
    ) -> ArchiveJobRecord:
        drive_file_id = _required_text(drive_file_id, 'drive_file_id')
        timestamp = _format_timestamp(uploaded_at)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, drive_file_id = ?, drive_folder_id = ?, '
                    'uploaded_at = ?, error_code = NULL, next_attempt_at = NULL, updated_at = ? '
                    'WHERE job_id = ?'
                ),
                (ARCHIVE_JOB_UPLOADED, drive_file_id, drive_folder_id, timestamp, timestamp, job_id),
            )
            connection.commit()
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(row)

    def mark_retry_wait(
        self,
        job_id: str,
        *,
        error_code: str,
        next_attempt_at: datetime | None = None,
        now: datetime | None = None,
    ) -> ArchiveJobRecord:
        error_code = _required_text(error_code, 'error_code')
        timestamp = _format_timestamp(now)
        retry_at = _format_timestamp(next_attempt_at or (_utc_now(now) + timedelta(minutes=15)))
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found')
            attempts = int(row['attempts']) + 1
            status = ARCHIVE_JOB_FAILED if attempts >= int(row['max_attempts']) else ARCHIVE_JOB_RETRY_WAIT
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, attempts = ?, error_code = ?, '
                    'next_attempt_at = ?, updated_at = ? WHERE job_id = ?'
                ),
                (status, attempts, error_code, retry_at if status == ARCHIVE_JOB_RETRY_WAIT else None, timestamp, job_id),
            )
            connection.commit()
            updated = self._get_job_row(connection, job_id)
            if updated is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(updated)

    def mark_failed(self, job_id: str, *, error_code: str, now: datetime | None = None) -> ArchiveJobRecord:
        return self._update_status(job_id, status=ARCHIVE_JOB_FAILED, error_code=error_code, now=now)

    def mark_abandoned(self, job_id: str, *, error_code: str, now: datetime | None = None) -> ArchiveJobRecord:
        return self._update_status(job_id, status=ARCHIVE_JOB_ABANDONED, error_code=error_code, now=now)

    def _update_status(
        self,
        job_id: str,
        *,
        status: str,
        error_code: str | None = None,
        now: datetime | None = None,
        clear_next_attempt: bool = True,
        clear_error: bool = False,
    ) -> ArchiveJobRecord:
        timestamp = _format_timestamp(now)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, error_code = ?, '
                    'next_attempt_at = CASE WHEN ? THEN NULL ELSE next_attempt_at END, updated_at = ? '
                    'WHERE job_id = ?'
                ),
                (status, None if clear_error else error_code, 1 if clear_next_attempt else 0, timestamp, job_id),
            )
            connection.commit()
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(row)

    def _get_active_job_row(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        document_id: str,
        provider: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            (
                'SELECT * FROM archive_jobs '
                'WHERE workspace_id = ? AND document_id = ? AND provider = ? '
                'AND status IN (?, ?, ?) ORDER BY created_at ASC LIMIT 1'
            ),
            (workspace_id, document_id, provider, *ACTIVE_ARCHIVE_JOB_STATUSES),
        ).fetchone()

    def _get_job_row(self, connection: sqlite3.Connection, job_id: str) -> sqlite3.Row | None:
        return connection.execute('SELECT * FROM archive_jobs WHERE job_id = ?', (job_id,)).fetchone()


def _job_from_row(row: sqlite3.Row) -> ArchiveJobRecord:
    return ArchiveJobRecord(
        job_id=row['job_id'],
        workspace_id=row['workspace_id'],
        telegram_id=int(row['telegram_id']),
        document_id=row['document_id'],
        document_type=row['document_type'],
        local_file_path=row['local_file_path'],
        metadata_path=row['metadata_path'],
        provider=row['provider'],
        target_folder_path=row['target_folder_path'],
        status=row['status'],
        attempts=int(row['attempts']),
        max_attempts=int(row['max_attempts']),
        next_attempt_at=row['next_attempt_at'],
        drive_file_id=row['drive_file_id'],
        drive_folder_id=row['drive_folder_id'],
        error_code=row['error_code'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        uploaded_at=row['uploaded_at'],
    )


def _required_text(value: object, field_name: str) -> str:
    text = str(value).strip() if value is not None else ''
    if not text:
        raise ArchiveJobServiceError(f'{field_name}_required')
    return text


def _optional_text(value: str | Path | None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_timestamp(value: datetime | None) -> str:
    return _utc_now(value).isoformat()


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
