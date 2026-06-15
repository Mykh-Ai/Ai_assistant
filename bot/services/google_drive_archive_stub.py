from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
    DRIVE_ARCHIVE_STUB_NOTE,
    DRIVE_ARCHIVE_STUB_USER_MESSAGE,
    InvoiceFollowupService,
)


@dataclass(frozen=True)
class GoogleDriveArchiveStubResult:
    invoice_id: int
    supplier_telegram_id: int
    status: str
    user_message: str


class GoogleDriveArchiveStubService:
    """Deterministic placeholder for future invoice archive integration."""

    def __init__(self, db_path: Path) -> None:
        self._followup_service = InvoiceFollowupService(db_path)

    def request_invoice_archive_stub(
        self,
        *,
        invoice_id: int,
        supplier_telegram_id: int,
    ) -> GoogleDriveArchiveStubResult:
        state = self._followup_service.record_drive_archive_stub(
            invoice_id=invoice_id,
            supplier_telegram_id=supplier_telegram_id,
            status=DRIVE_ARCHIVE_STATUS_STUB_REQUESTED_AFTER_PAID,
            note=DRIVE_ARCHIVE_STUB_NOTE,
        )
        return GoogleDriveArchiveStubResult(
            invoice_id=state.invoice_id,
            supplier_telegram_id=state.supplier_telegram_id,
            status=state.drive_archive_status,
            user_message=DRIVE_ARCHIVE_STUB_USER_MESSAGE,
        )
