from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from bot.services.accounting_document_archive_path import (
    AccountingDocumentArchivePathError,
    normalize_relative_drive_target_path,
    validate_workspace_drive_folder_name,
)


DOCUMENT_TYPE_BANK_STATEMENT_ORIGINAL = "bank_statement_original"


@dataclass(frozen=True)
class GmailStatementArchivePathParts:
    year: str
    month: str
    import_id: str


def validate_gmail_statement_archive_paths(
    *,
    local_file_path: str | Path,
    metadata_path: str | Path | None,
    workspace_storage_key: str,
) -> GmailStatementArchivePathParts:
    storage_key = str(workspace_storage_key).strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", storage_key):
        raise AccountingDocumentArchivePathError("workspace_storage_key_invalid")

    original = Path(local_file_path)
    parts = original.parts
    if len(parts) < 8 or any(
        part in {".", ".."} or _has_control_character(part) for part in parts
    ):
        raise AccountingDocumentArchivePathError(
            "local_file_path_invalid_gmail_statement_path"
        )
    relative = parts[-8:]
    if (
        relative[0].lower() != "workspaces"
        or relative[1] != storage_key
        or relative[2].lower() != "bank_statement_imports"
        or relative[3].lower() != "gmail"
        or not relative[6]
        or not relative[7].lower().startswith("original.")
    ):
        raise AccountingDocumentArchivePathError(
            "local_file_path_invalid_gmail_statement_path"
        )
    year, month, import_id = relative[4], relative[5], relative[6]
    if not (len(year) == 4 and year.isdigit()):
        raise AccountingDocumentArchivePathError(
            "local_file_path_invalid_gmail_statement_path"
        )
    if not (len(month) == 2 and month.isdigit() and 1 <= int(month) <= 12):
        raise AccountingDocumentArchivePathError(
            "local_file_path_invalid_gmail_statement_path"
        )

    if metadata_path is not None:
        metadata = Path(metadata_path)
        if metadata.name != "metadata.json" or metadata.parent != original.parent:
            raise AccountingDocumentArchivePathError(
                "metadata_path_invalid_gmail_statement_path"
            )
    return GmailStatementArchivePathParts(
        year=year, month=month, import_id=import_id
    )


def derive_gmail_statement_drive_target_path(
    *,
    local_file_path: str | Path,
    metadata_path: str | Path | None,
    workspace_storage_key: str,
    workspace_drive_folder_name: str,
) -> str:
    parts = validate_gmail_statement_archive_paths(
        local_file_path=local_file_path,
        metadata_path=metadata_path,
        workspace_storage_key=workspace_storage_key,
    )
    folder = validate_workspace_drive_folder_name(workspace_drive_folder_name)
    return normalize_relative_drive_target_path(
        f"{folder}/{parts.year}/bankove_vypisy/{parts.year}-{parts.month}"
    )


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
