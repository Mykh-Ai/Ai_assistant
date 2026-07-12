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
TERMINAL_ARCHIVE_JOB_STATUSES = (
    ARCHIVE_JOB_UPLOADED,
    ARCHIVE_JOB_FAILED,
    ARCHIVE_JOB_ABANDONED,
)
ALLOWED_ARCHIVE_JOB_STATUSES = ACTIVE_ARCHIVE_JOB_STATUSES + TERMINAL_ARCHIVE_JOB_STATUSES
ACCOUNTING_ORIGINAL_FOLDERS = {'receipts', 'incoming_invoices'}


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
    locked_by: str | None
    lease_until: str | None


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
        invoice_storage_key: str | None = None,
        max_attempts: int = 5,
        now: datetime | None = None,
    ) -> ArchiveJobRecord:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        document_id = _required_text(document_id, 'document_id')
        document_type = _required_text(document_type, 'document_type')
        provider = _required_text(provider, 'provider')
        local_file_path_text = _required_text(str(local_file_path), 'local_file_path')
        metadata_path_text = _optional_text(metadata_path)
        if document_type == 'invoice_pdf':
            _validate_invoice_pdf_path(
                local_file_path_text,
                owner_segment=(
                    _required_text(invoice_storage_key, 'invoice_storage_key')
                    if invoice_storage_key is not None
                    else str(telegram_id)
                ),
                owner_mismatch_code=(
                    'invoice_storage_key_mismatch'
                    if invoice_storage_key is not None
                    else 'telegram_mismatch'
                ),
                field_name='local_file_path',
            )
            if metadata_path_text is not None:
                raise ArchiveJobServiceError('metadata_path_invoice_pdf_rejected')
        else:
            _validate_confirmed_accounting_path(
                local_file_path_text,
                workspace_id=workspace_id,
                expected_leaf='originals',
                field_name='local_file_path',
            )
            if metadata_path_text is not None:
                _validate_confirmed_accounting_path(
                    metadata_path_text,
                    workspace_id=workspace_id,
                    expected_leaf='metadata',
                    field_name='metadata_path',
                )
        if telegram_id <= 0:
            raise ArchiveJobServiceError('telegram_id_required')
        if max_attempts <= 0:
            raise ArchiveJobServiceError('max_attempts_must_be_positive')

        timestamp = _format_timestamp(now)
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            existing = self._get_document_job_row(
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
                    'next_attempt_at, drive_file_id, drive_folder_id, error_code, created_at, updated_at, '
                    'uploaded_at, locked_by, lease_until) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, NULL, NULL, NULL, NULL, ?, ?, NULL, NULL, NULL)'
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

    def claim_next_runnable_job(
        self,
        *,
        worker_id: str,
        provider: str = ARCHIVE_PROVIDER_GOOGLE_DRIVE,
        lease_seconds: int = 300,
        now: datetime | None = None,
    ) -> ArchiveJobRecord | None:
        worker_id = _required_text(worker_id, 'worker_id')
        if lease_seconds <= 0:
            raise ArchiveJobServiceError('lease_seconds_must_be_positive')
        current_dt = _utc_now(now)
        current = current_dt.isoformat()
        lease_until = (current_dt + timedelta(seconds=lease_seconds)).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute(
                (
                    'SELECT * FROM archive_jobs '
                    'WHERE provider = ? AND ('
                    'status = ? OR '
                    '(status = ? AND (next_attempt_at IS NULL OR next_attempt_at <= ?)) OR '
                    '(status = ? AND lease_until IS NOT NULL AND lease_until <= ?)'
                    ') ORDER BY created_at ASC LIMIT 1'
                ),
                (
                    provider,
                    ARCHIVE_JOB_PENDING,
                    ARCHIVE_JOB_RETRY_WAIT,
                    current,
                    ARCHIVE_JOB_UPLOADING,
                    current,
                ),
            ).fetchone()
            if row is None:
                connection.commit()
                return None
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, locked_by = ?, lease_until = ?, '
                    'next_attempt_at = NULL, error_code = NULL, updated_at = ? '
                    'WHERE job_id = ?'
                ),
                (ARCHIVE_JOB_UPLOADING, worker_id, lease_until, current, row['job_id']),
            )
            connection.commit()
            updated = self._get_job_row(connection, row['job_id'])
            if updated is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(updated)

    def mark_uploading(
        self,
        job_id: str,
        *,
        now: datetime | None = None,
        worker_id: str | None = None,
        lease_seconds: int | None = None,
    ) -> ArchiveJobRecord:
        if lease_seconds is not None and lease_seconds <= 0:
            raise ArchiveJobServiceError('lease_seconds_must_be_positive')
        timestamp = _format_timestamp(now)
        lease_until = None
        if worker_id is not None:
            worker_id = _required_text(worker_id, 'worker_id')
            lease_until = (_utc_now(now) + timedelta(seconds=lease_seconds or 300)).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found')
            _ensure_transition(
                current_status=row['status'],
                target_status=ARCHIVE_JOB_UPLOADING,
                allowed_from=(ARCHIVE_JOB_PENDING, ARCHIVE_JOB_RETRY_WAIT),
            )
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, locked_by = ?, lease_until = ?, '
                    'next_attempt_at = NULL, error_code = NULL, updated_at = ? WHERE job_id = ?'
                ),
                (ARCHIVE_JOB_UPLOADING, worker_id, lease_until, timestamp, job_id),
            )
            connection.commit()
            updated = self._get_job_row(connection, job_id)
            if updated is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(updated)

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
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found')
            _ensure_transition(
                current_status=row['status'],
                target_status=ARCHIVE_JOB_UPLOADED,
                allowed_from=(ARCHIVE_JOB_UPLOADING,),
            )
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, drive_file_id = ?, drive_folder_id = ?, '
                    'uploaded_at = ?, error_code = NULL, next_attempt_at = NULL, locked_by = NULL, '
                    'lease_until = NULL, updated_at = ? WHERE job_id = ?'
                ),
                (ARCHIVE_JOB_UPLOADED, drive_file_id, drive_folder_id, timestamp, timestamp, job_id),
            )
            connection.commit()
            updated = self._get_job_row(connection, job_id)
            if updated is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(updated)

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
            _ensure_transition(
                current_status=row['status'],
                target_status=status,
                allowed_from=(ARCHIVE_JOB_UPLOADING,),
            )
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, attempts = ?, error_code = ?, next_attempt_at = ?, '
                    'locked_by = NULL, lease_until = NULL, updated_at = ? WHERE job_id = ?'
                ),
                (
                    status,
                    attempts,
                    error_code,
                    retry_at if status == ARCHIVE_JOB_RETRY_WAIT else None,
                    timestamp,
                    job_id,
                ),
            )
            connection.commit()
            updated = self._get_job_row(connection, job_id)
            if updated is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(updated)

    def mark_failed(self, job_id: str, *, error_code: str, now: datetime | None = None) -> ArchiveJobRecord:
        return self._update_status(
            job_id,
            status=ARCHIVE_JOB_FAILED,
            allowed_from=(ARCHIVE_JOB_UPLOADING,),
            error_code=error_code,
            now=now,
        )

    def mark_abandoned(self, job_id: str, *, error_code: str, now: datetime | None = None) -> ArchiveJobRecord:
        return self._update_status(
            job_id,
            status=ARCHIVE_JOB_ABANDONED,
            allowed_from=(ARCHIVE_JOB_UPLOADING, ARCHIVE_JOB_RETRY_WAIT),
            error_code=error_code,
            now=now,
        )

    def _update_status(
        self,
        job_id: str,
        *,
        status: str,
        allowed_from: tuple[str, ...],
        error_code: str | None = None,
        now: datetime | None = None,
    ) -> ArchiveJobRecord:
        timestamp = _format_timestamp(now)
        if error_code is not None:
            error_code = _required_text(error_code, 'error_code')
        with managed_connection(self._db_path) as connection:
            ensure_archive_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_job_row(connection, job_id)
            if row is None:
                raise ArchiveJobServiceError('job_not_found')
            _ensure_transition(
                current_status=row['status'],
                target_status=status,
                allowed_from=allowed_from,
            )
            connection.execute(
                (
                    'UPDATE archive_jobs SET status = ?, error_code = ?, next_attempt_at = NULL, '
                    'locked_by = NULL, lease_until = NULL, updated_at = ? WHERE job_id = ?'
                ),
                (status, error_code, timestamp, job_id),
            )
            connection.commit()
            updated = self._get_job_row(connection, job_id)
            if updated is None:
                raise ArchiveJobServiceError('job_not_found')
            return _job_from_row(updated)

    def _get_document_job_row(
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
                'ORDER BY CASE status '
                'WHEN ? THEN 0 WHEN ? THEN 1 WHEN ? THEN 2 WHEN ? THEN 3 '
                'WHEN ? THEN 4 WHEN ? THEN 5 ELSE 6 END, created_at ASC LIMIT 1'
            ),
            (
                workspace_id,
                document_id,
                provider,
                ARCHIVE_JOB_PENDING,
                ARCHIVE_JOB_UPLOADING,
                ARCHIVE_JOB_RETRY_WAIT,
                ARCHIVE_JOB_UPLOADED,
                ARCHIVE_JOB_FAILED,
                ARCHIVE_JOB_ABANDONED,
            ),
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
        locked_by=row['locked_by'],
        lease_until=row['lease_until'],
    )


def _ensure_transition(
    *,
    current_status: str,
    target_status: str,
    allowed_from: tuple[str, ...],
) -> None:
    if current_status not in ALLOWED_ARCHIVE_JOB_STATUSES:
        raise ArchiveJobServiceError('unsupported_job_status')
    if target_status not in ALLOWED_ARCHIVE_JOB_STATUSES:
        raise ArchiveJobServiceError('unsupported_job_status')
    if current_status in TERMINAL_ARCHIVE_JOB_STATUSES:
        raise ArchiveJobServiceError('terminal_job_transition_rejected')
    if current_status not in allowed_from:
        raise ArchiveJobServiceError('invalid_job_status_transition')


def _validate_invoice_pdf_path(
    path_text: str,
    *,
    owner_segment: str,
    owner_mismatch_code: str,
    field_name: str,
) -> None:
    path = Path(path_text)
    parts = path.parts
    if not parts or any(part == '..' for part in parts):
        raise ArchiveJobServiceError(f'{field_name}_invalid_invoice_path')
    lower_parts = [part.lower() for part in parts]
    try:
        index = lower_parts.index('invoices')
    except ValueError as exc:
        raise ArchiveJobServiceError(f'{field_name}_invalid_invoice_path') from exc
    relative = parts[index:]
    if len(relative) != 3:
        raise ArchiveJobServiceError(f'{field_name}_invalid_invoice_path')
    if relative[1] != owner_segment:
        raise ArchiveJobServiceError(f'{field_name}_{owner_mismatch_code}')
    if Path(relative[2]).suffix.lower() != '.pdf':
        raise ArchiveJobServiceError(f'{field_name}_invalid_invoice_path')


def _validate_confirmed_accounting_path(
    path_text: str,
    *,
    workspace_id: str,
    expected_leaf: str,
    field_name: str,
) -> None:
    path = Path(path_text)
    parts = path.parts
    if not parts or any(part == '..' for part in parts):
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if any(part.lower() == 'invoices' for part in parts):
        raise ArchiveJobServiceError(f'{field_name}_invoice_path_rejected')

    lower_parts = [part.lower() for part in parts]
    try:
        index = lower_parts.index('workspaces')
    except ValueError as exc:
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path') from exc

    relative = parts[index:]
    if len(relative) != 9:
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if relative[1] != workspace_id:
        raise ArchiveJobServiceError(f'{field_name}_workspace_mismatch')
    if (
        relative[0].lower() != 'workspaces'
        or relative[2].lower() != 'years'
        or relative[4].lower() != 'expenses'
        or relative[7].lower() != expected_leaf
    ):
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if not (relative[3].isdigit() and len(relative[3]) == 4):
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if not (relative[5].isdigit() and len(relative[5]) == 2):
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if relative[6] not in ACCOUNTING_ORIGINAL_FOLDERS:
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if not relative[8]:
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')
    if expected_leaf == 'metadata' and Path(relative[8]).suffix.lower() != '.json':
        raise ArchiveJobServiceError(f'{field_name}_invalid_accounting_path')


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
