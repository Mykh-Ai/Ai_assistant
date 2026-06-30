"""Local archive worker for accounting document archive jobs.

The worker is intentionally provider-injected. This module contains no Google
runtime integration and does not perform network I/O on its own.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
from typing import Any, Mapping, Protocol

from bot.services.accounting_document_archive_service import (
    AccountingDocumentArchiveService,
    AccountingDocumentArchiveServiceError,
)
from bot.services.archive_job_service import ArchiveJobRecord, ArchiveJobService
from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_FAILED,
    DRIVE_ARCHIVE_STATUS_RETRY_WAIT,
    DRIVE_ARCHIVE_STATUS_UPLOADED,
    InvoiceFollowupService,
)


ARCHIVE_WORKER_NOOP = "noop"

ARCHIVE_ERROR_TRANSIENT = "upload_transient_failed"
ARCHIVE_ERROR_PERMANENT = "upload_permanent_failed"
ARCHIVE_ERROR_PROVIDER_UNAVAILABLE = "provider_unavailable"
ARCHIVE_ERROR_NOT_CONFIGURED = "google_drive_not_configured"
ARCHIVE_ERROR_UNEXPECTED = "upload_unexpected_failed"

DEFAULT_ARCHIVE_WORKER_ID = "archive-worker"
DEFAULT_ARCHIVE_LEASE_SECONDS = 300
DEFAULT_ARCHIVE_RETRY_DELAY = timedelta(minutes=15)

logger = logging.getLogger(__name__)


class ArchiveUploadError(Exception):
    """Base class for bounded provider upload failures."""


class ArchiveUploadTransientError(ArchiveUploadError):
    """Provider failure that may succeed on retry."""


class ArchiveUploadPermanentError(ArchiveUploadError):
    """Provider failure that should not be retried automatically."""


class ArchiveUploadNotConfiguredError(ArchiveUploadError):
    """Provider is disabled or lacks required credentials/folder setup."""


class ArchiveUploadProvider(Protocol):
    """Injected upload provider used by the local worker lifecycle."""

    def upload_file(
        self,
        *,
        local_file_path: Path,
        target_folder_path: str | None,
        document_type: str,
        metadata: Mapping[str, Any],
    ) -> "ArchiveUploadResult":
        """Upload a local file and return provider-side archive identifiers."""


@dataclass(frozen=True)
class ArchiveUploadResult:
    drive_file_id: str
    drive_folder_id: str | None = None


@dataclass(frozen=True)
class ArchiveWorkerResult:
    status: str
    job_id: str | None = None
    archive_status: str | None = None
    error_code: str | None = None


@dataclass(frozen=True)
class ArchiveLocalRetentionPolicy:
    delete_receipt_original_after_upload: bool = False
    delete_incoming_invoice_original_after_upload: bool = False

    def should_delete_original(self, document_type: str) -> bool:
        if document_type == "receipt":
            return self.delete_receipt_original_after_upload
        if document_type == "incoming_invoice":
            return self.delete_incoming_invoice_original_after_upload
        return False


class ArchiveWorker:
    """Claim and process one runnable accounting archive job."""

    def __init__(
        self,
        db_path: Path,
        provider: ArchiveUploadProvider | None,
        *,
        worker_id: str = DEFAULT_ARCHIVE_WORKER_ID,
        lease_seconds: int = DEFAULT_ARCHIVE_LEASE_SECONDS,
        retry_delay: timedelta = DEFAULT_ARCHIVE_RETRY_DELAY,
        retention_policy: ArchiveLocalRetentionPolicy | None = None,
    ) -> None:
        self._db_path = db_path
        self._jobs = ArchiveJobService(db_path)
        self._archive = AccountingDocumentArchiveService(db_path)
        self._provider = provider
        self._worker_id = worker_id
        self._lease_seconds = lease_seconds
        self._retry_delay = retry_delay
        self._retention_policy = retention_policy or ArchiveLocalRetentionPolicy()

    def process_one(self, *, now: datetime | None = None) -> ArchiveWorkerResult:
        current_time = _utc_now(now)
        job = self._jobs.claim_next_runnable_job(
            worker_id=self._worker_id,
            lease_seconds=self._lease_seconds,
            now=current_time,
        )
        if job is None:
            return ArchiveWorkerResult(status=ARCHIVE_WORKER_NOOP)

        if job.document_type == "invoice_pdf":
            return self._process_invoice_pdf_job(job, now=current_time)

        state = self._archive.get_state(
            workspace_id=job.workspace_id,
            document_id=job.document_id,
        )
        if state is None:
            return self._mark_job_failed_without_state(
                job,
                error_code=ARCHIVE_ERROR_UNEXPECTED,
                now=current_time,
            )

        if self._provider is None:
            return self._mark_retry_wait(
                job,
                error_code=ARCHIVE_ERROR_PROVIDER_UNAVAILABLE,
                now=current_time,
            )

        try:
            upload_result = self._provider.upload_file(
                local_file_path=Path(job.local_file_path),
                target_folder_path=job.target_folder_path,
                document_type=job.document_type,
                metadata=_provider_metadata(job),
            )
            if not upload_result.drive_file_id.strip():
                return self._mark_retry_wait(
                    job,
                    error_code=ARCHIVE_ERROR_UNEXPECTED,
                    now=current_time,
                )
        except ArchiveUploadTransientError:
            return self._mark_retry_wait(
                job,
                error_code=ARCHIVE_ERROR_TRANSIENT,
                now=current_time,
            )
        except ArchiveUploadPermanentError:
            return self._mark_failed(
                job,
                error_code=ARCHIVE_ERROR_PERMANENT,
                now=current_time,
            )
        except ArchiveUploadNotConfiguredError:
            return self._mark_retry_wait(
                job,
                error_code=ARCHIVE_ERROR_NOT_CONFIGURED,
                now=current_time,
            )
        except Exception:
            return self._mark_retry_wait(
                job,
                error_code=ARCHIVE_ERROR_UNEXPECTED,
                now=current_time,
            )

        try:
            uploaded_state = self._archive.mark_uploaded(
                job.job_id,
                drive_file_id=upload_result.drive_file_id,
                drive_folder_id=upload_result.drive_folder_id,
                uploaded_at=current_time,
            )
        except AccountingDocumentArchiveServiceError:
            return self._mark_job_failed_without_state(
                job,
                error_code=ARCHIVE_ERROR_UNEXPECTED,
                now=current_time,
            )

        self._delete_uploaded_original_if_allowed(job, uploaded_state.archive_status)

        return ArchiveWorkerResult(
            status=uploaded_state.archive_status,
            job_id=job.job_id,
            archive_status=uploaded_state.archive_status,
        )

    def _process_invoice_pdf_job(self, job: ArchiveJobRecord, *, now: datetime) -> ArchiveWorkerResult:
        invoice_id = _invoice_id_from_job(job)
        if invoice_id is None:
            return self._mark_job_failed_without_state(
                job,
                error_code=ARCHIVE_ERROR_UNEXPECTED,
                now=now,
            )
        if self._provider is None:
            return self._mark_invoice_retry_wait(
                job,
                invoice_id=invoice_id,
                error_code=ARCHIVE_ERROR_PROVIDER_UNAVAILABLE,
                now=now,
            )
        try:
            upload_result = self._provider.upload_file(
                local_file_path=Path(job.local_file_path),
                target_folder_path=job.target_folder_path,
                document_type=job.document_type,
                metadata=_provider_metadata(job),
            )
            if not upload_result.drive_file_id.strip():
                return self._mark_invoice_retry_wait(
                    job,
                    invoice_id=invoice_id,
                    error_code=ARCHIVE_ERROR_UNEXPECTED,
                    now=now,
                )
        except ArchiveUploadTransientError:
            return self._mark_invoice_retry_wait(
                job,
                invoice_id=invoice_id,
                error_code=ARCHIVE_ERROR_TRANSIENT,
                now=now,
            )
        except ArchiveUploadPermanentError:
            return self._mark_invoice_failed(
                job,
                invoice_id=invoice_id,
                error_code=ARCHIVE_ERROR_PERMANENT,
                now=now,
            )
        except ArchiveUploadNotConfiguredError:
            return self._mark_invoice_retry_wait(
                job,
                invoice_id=invoice_id,
                error_code=ARCHIVE_ERROR_NOT_CONFIGURED,
                now=now,
            )
        except Exception:
            return self._mark_invoice_retry_wait(
                job,
                invoice_id=invoice_id,
                error_code=ARCHIVE_ERROR_UNEXPECTED,
                now=now,
            )

        uploaded_job = self._jobs.mark_uploaded(
            job.job_id,
            drive_file_id=upload_result.drive_file_id,
            drive_folder_id=upload_result.drive_folder_id,
            uploaded_at=now,
        )
        InvoiceFollowupService(self._db_path).record_drive_archive_status(
            invoice_id=invoice_id,
            supplier_telegram_id=job.telegram_id,
            status=DRIVE_ARCHIVE_STATUS_UPLOADED,
            note="PDF faktury bol nahraty na Google Drive. Lokalny PDF ostava ulozeny v bote.",
        )
        return ArchiveWorkerResult(
            status=uploaded_job.status,
            job_id=job.job_id,
            archive_status=uploaded_job.status,
        )

    def _mark_invoice_retry_wait(
        self,
        job: ArchiveJobRecord,
        *,
        invoice_id: int,
        error_code: str,
        now: datetime,
    ) -> ArchiveWorkerResult:
        next_attempt_at = now + self._retry_delay
        _log_worker_failure(job, error_code)
        updated_job = self._jobs.mark_retry_wait(
            job.job_id,
            error_code=error_code,
            next_attempt_at=next_attempt_at,
            now=now,
        )
        InvoiceFollowupService(self._db_path).record_drive_archive_status(
            invoice_id=invoice_id,
            supplier_telegram_id=job.telegram_id,
            status=DRIVE_ARCHIVE_STATUS_RETRY_WAIT if updated_job.status == "retry_wait" else DRIVE_ARCHIVE_STATUS_FAILED,
            note="Archivacia PDF faktury na Google Drive zatial nepresla. Lokalny PDF ostava ulozeny v bote.",
        )
        return ArchiveWorkerResult(
            status=updated_job.status,
            job_id=job.job_id,
            archive_status=updated_job.status,
            error_code=error_code,
        )

    def _mark_invoice_failed(
        self,
        job: ArchiveJobRecord,
        *,
        invoice_id: int,
        error_code: str,
        now: datetime,
    ) -> ArchiveWorkerResult:
        _log_worker_failure(job, error_code)
        updated_job = self._jobs.mark_failed(job.job_id, error_code=error_code, now=now)
        InvoiceFollowupService(self._db_path).record_drive_archive_status(
            invoice_id=invoice_id,
            supplier_telegram_id=job.telegram_id,
            status=DRIVE_ARCHIVE_STATUS_FAILED,
            note="Archivacia PDF faktury na Google Drive zlyhala. Lokalny PDF ostava ulozeny v bote.",
        )
        return ArchiveWorkerResult(
            status=updated_job.status,
            job_id=job.job_id,
            archive_status=updated_job.status,
            error_code=error_code,
        )

    def _delete_uploaded_original_if_allowed(self, job: ArchiveJobRecord, archive_status: str) -> None:
        if archive_status != "uploaded":
            return
        if not self._retention_policy.should_delete_original(job.document_type):
            return
        local_path = Path(job.local_file_path)
        if local_path.suffix.lower() == ".json":
            return
        try:
            local_path.unlink(missing_ok=True)
        except OSError:
            logger.warning(
                "archive_worker_local_original_delete_failed job_ref=%s",
                _safe_ref(job.job_id),
            )

    def _mark_retry_wait(
        self,
        job: ArchiveJobRecord,
        *,
        error_code: str,
        now: datetime,
    ) -> ArchiveWorkerResult:
        next_attempt_at = now + self._retry_delay
        _log_worker_failure(job, error_code)
        try:
            updated_state = self._archive.mark_retry_wait(
                job.job_id,
                error_code=error_code,
                next_attempt_at=next_attempt_at,
                now=now,
            )
            return ArchiveWorkerResult(
                status=updated_state.archive_status,
                job_id=job.job_id,
                archive_status=updated_state.archive_status,
                error_code=error_code,
            )
        except AccountingDocumentArchiveServiceError:
            updated_job = self._jobs.mark_retry_wait(
                job.job_id,
                error_code=error_code,
                next_attempt_at=next_attempt_at,
                now=now,
            )
            return ArchiveWorkerResult(
                status=updated_job.status,
                job_id=job.job_id,
                archive_status=updated_job.status,
                error_code=error_code,
            )

    def _mark_failed(
        self,
        job: ArchiveJobRecord,
        *,
        error_code: str,
        now: datetime,
    ) -> ArchiveWorkerResult:
        _log_worker_failure(job, error_code)
        try:
            updated_state = self._archive.mark_failed(
                job.job_id,
                error_code=error_code,
                now=now,
            )
            return ArchiveWorkerResult(
                status=updated_state.archive_status,
                job_id=job.job_id,
                archive_status=updated_state.archive_status,
                error_code=error_code,
            )
        except AccountingDocumentArchiveServiceError:
            updated_job = self._jobs.mark_failed(
                job.job_id,
                error_code=error_code,
                now=now,
            )
            return ArchiveWorkerResult(
                status=updated_job.status,
                job_id=job.job_id,
                archive_status=updated_job.status,
                error_code=error_code,
            )

    def _mark_job_failed_without_state(
        self,
        job: ArchiveJobRecord,
        *,
        error_code: str,
        now: datetime,
    ) -> ArchiveWorkerResult:
        _log_worker_failure(job, error_code)
        updated_job = self._jobs.mark_failed(
            job.job_id,
            error_code=error_code,
            now=now,
        )
        return ArchiveWorkerResult(
            status=updated_job.status,
            job_id=job.job_id,
            archive_status=updated_job.status,
            error_code=error_code,
        )


def _invoice_id_from_job(job: ArchiveJobRecord) -> int | None:
    try:
        invoice_id = int(job.document_id)
    except ValueError:
        return None
    return invoice_id if invoice_id > 0 else None


def _provider_metadata(job: ArchiveJobRecord) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "workspace_id": job.workspace_id,
        "telegram_id": job.telegram_id,
        "document_id": job.document_id,
        "document_type": job.document_type,
        "metadata_path": job.metadata_path,
        "provider": job.provider,
    }


def _log_worker_failure(job: ArchiveJobRecord, error_code: str) -> None:
    logger.warning(
        "archive_worker_failed job_ref=%s error_code=%s",
        _safe_ref(job.job_id),
        error_code,
    )


def _safe_ref(value: str) -> str:
    return value[:12]


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
