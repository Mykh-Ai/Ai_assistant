from __future__ import annotations

from pathlib import Path

import pytest

from bot.services.accounting_document_archive_service import (
    AccountingDocumentArchiveService,
)
from bot.services.gmail_statement_archive_path import (
    DOCUMENT_TYPE_BANK_STATEMENT_ORIGINAL,
    derive_gmail_statement_drive_target_path,
)


def _paths(tmp_path: Path) -> tuple[Path, Path]:
    root = (
        tmp_path
        / "storage"
        / "workspaces"
        / "zevs"
        / "bank_statement_imports"
        / "gmail"
        / "2026"
        / "07"
        / "import-1"
    )
    root.mkdir(parents=True)
    original = root / "original.pdf"
    metadata = root / "metadata.json"
    original.write_bytes(b"statement")
    metadata.write_text("{}", encoding="utf-8")
    return original, metadata


def test_bank_statement_archive_target_and_enqueue_are_idempotent(tmp_path: Path) -> None:
    original, metadata = _paths(tmp_path)
    target = derive_gmail_statement_drive_target_path(
        local_file_path=original,
        metadata_path=metadata,
        workspace_storage_key="zevs",
        workspace_drive_folder_name="Zevs sro",
    )
    assert target == "Zevs sro/2026/bankove_vypisy/2026-07"

    service = AccountingDocumentArchiveService(tmp_path / "db.sqlite")
    first = service.enqueue_confirmed_document(
        workspace_id="workspace-zevs",
        telegram_id=42,
        document_id="import-1",
        document_type=DOCUMENT_TYPE_BANK_STATEMENT_ORIGINAL,
        local_file_path=original,
        metadata_path=metadata,
        workspace_storage_key="zevs",
        workspace_drive_folder_name="Zevs sro",
    )
    second = service.enqueue_confirmed_document(
        workspace_id="workspace-zevs",
        telegram_id=42,
        document_id="import-1",
        document_type=DOCUMENT_TYPE_BANK_STATEMENT_ORIGINAL,
        local_file_path=original,
        metadata_path=metadata,
        workspace_storage_key="zevs",
        workspace_drive_folder_name="Zevs sro",
    )

    assert first.job.job_id == second.job.job_id
    assert first.job.target_folder_path == target
    assert first.state.archive_status == "pending"
    assert original.is_file()


def test_bank_statement_archive_rejects_workspace_mismatch(tmp_path: Path) -> None:
    original, metadata = _paths(tmp_path)

    with pytest.raises(ValueError, match="local_file_path_invalid_gmail_statement_path"):
        derive_gmail_statement_drive_target_path(
            local_file_path=original,
            metadata_path=metadata,
            workspace_storage_key="another-workspace",
            workspace_drive_folder_name="Zevs sro",
        )
