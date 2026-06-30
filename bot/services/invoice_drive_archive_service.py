from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.config import Config
from bot.services.archive_job_service import ArchiveJobRecord, ArchiveJobService
from bot.services.google_drive_archive_stub import GoogleDriveArchiveStubService
from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_PENDING,
    InvoiceFollowupService,
)
from bot.services.invoice_service import InvoiceRecord


@dataclass(frozen=True)
class InvoiceDriveArchiveRequestResult:
    invoice_id: int
    supplier_telegram_id: int
    status: str
    user_message: str
    job: ArchiveJobRecord | None = None


class InvoiceDriveArchiveService:
    def __init__(self, config: Config) -> None:
        self._config = config
        self._jobs = ArchiveJobService(config.db_path)
        self._followup = InvoiceFollowupService(config.db_path)
        self._stub = GoogleDriveArchiveStubService(config.db_path)

    def request_after_paid(self, *, invoice: InvoiceRecord) -> InvoiceDriveArchiveRequestResult:
        if not self._config.google_drive_enabled:
            stub = self._stub.request_invoice_archive_stub(
                invoice_id=invoice.id,
                supplier_telegram_id=invoice.supplier_telegram_id,
            )
            return InvoiceDriveArchiveRequestResult(
                invoice_id=stub.invoice_id,
                supplier_telegram_id=stub.supplier_telegram_id,
                status=stub.status,
                user_message=stub.user_message,
            )
        if not invoice.pdf_path or not Path(invoice.pdf_path).is_file():
            state = self._followup.record_drive_archive_status(
                invoice_id=invoice.id,
                supplier_telegram_id=invoice.supplier_telegram_id,
                status="failed",
                note="PDF faktury sa nenasiel, preto sa Drive archivacia nespustila.",
            )
            return InvoiceDriveArchiveRequestResult(
                invoice_id=invoice.id,
                supplier_telegram_id=invoice.supplier_telegram_id,
                status=state.drive_archive_status,
                user_message="PDF faktury sa nenasiel, preto sa Google Drive archivacia nespustila.",
            )

        target_folder_path = _invoice_target_folder_path(invoice.issue_date)
        job = self._jobs.enqueue_job(
            workspace_id=f"telegram-{invoice.supplier_telegram_id}",
            telegram_id=invoice.supplier_telegram_id,
            document_id=str(invoice.id),
            document_type="invoice_pdf",
            local_file_path=invoice.pdf_path,
            metadata_path=None,
            target_folder_path=target_folder_path,
        )
        state = self._followup.record_drive_archive_status(
            invoice_id=invoice.id,
            supplier_telegram_id=invoice.supplier_telegram_id,
            status=DRIVE_ARCHIVE_STATUS_PENDING,
            note="PDF faktury je zaradeny do Google Drive archivacie. Lokalny PDF ostava ulozeny v bote.",
        )
        return InvoiceDriveArchiveRequestResult(
            invoice_id=invoice.id,
            supplier_telegram_id=invoice.supplier_telegram_id,
            status=state.drive_archive_status,
            user_message=(
                "PDF faktury som zaradil do Google Drive archivacie. "
                "Lokalny PDF ostava ulozeny v bote, kym archivacia prebehne cez worker."
            ),
            job=job,
        )


def _invoice_target_folder_path(issue_date: str) -> str:
    year = issue_date[:4]
    month = issue_date[5:7] if len(issue_date) >= 7 else "01"
    if not (year.isdigit() and len(year) == 4 and month.isdigit() and len(month) == 2):
        year = "unknown"
        month = "unknown"
    return f"{year}/faktury/{year}-{month}"
