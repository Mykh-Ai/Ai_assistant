from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
import re

from bot.services.accounting_document_models import (
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
)


_DOCUMENT_TYPE_FOLDERS = {
    DOCUMENT_TYPE_RECEIPT: ('receipts', 'blocky'),
    DOCUMENT_TYPE_INCOMING_INVOICE: ('incoming_invoices', 'prijate_faktury'),
}
_MAX_SEGMENT_LENGTH = 150
_MAX_TARGET_LENGTH = 1024


class AccountingDocumentArchivePathError(ValueError):
    pass


@dataclass(frozen=True)
class AccountingDocumentPathParts:
    year: str
    month: str


def normalize_relative_drive_target_path(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise AccountingDocumentArchivePathError('target_folder_path_required')
    if _has_control_character(text):
        raise AccountingDocumentArchivePathError('target_folder_path_control_character')
    if PurePosixPath(text).is_absolute() or PureWindowsPath(text).is_absolute() or re.match(r'^[A-Za-z]:', text):
        raise AccountingDocumentArchivePathError('target_folder_path_absolute')

    normalized = text.replace('\\', '/')
    segments = normalized.split('/')
    if any(not segment for segment in segments):
        raise AccountingDocumentArchivePathError('target_folder_path_empty_segment')
    if any(segment in {'.', '..'} for segment in segments):
        raise AccountingDocumentArchivePathError('target_folder_path_traversal')
    if any(len(segment) > _MAX_SEGMENT_LENGTH for segment in segments):
        raise AccountingDocumentArchivePathError('target_folder_path_segment_too_long')
    if len(normalized) > _MAX_TARGET_LENGTH:
        raise AccountingDocumentArchivePathError('target_folder_path_too_long')
    return '/'.join(segments)


def validate_workspace_drive_folder_name(value: str) -> str:
    text = str(value).strip()
    if not text:
        raise AccountingDocumentArchivePathError('workspace_drive_folder_name_required')
    if '/' in text or '\\' in text:
        raise AccountingDocumentArchivePathError('workspace_drive_folder_name_separator')
    normalized = normalize_relative_drive_target_path(text)
    if '/' in normalized:
        raise AccountingDocumentArchivePathError('workspace_drive_folder_name_single_segment_required')
    return normalized


def build_accounting_document_drive_target_path(
    *,
    workspace_drive_folder_name: str,
    document_type: str,
    year: str | int,
    month: str | int,
) -> str:
    workspace_folder = validate_workspace_drive_folder_name(workspace_drive_folder_name)
    _, drive_folder = _folders_for_document_type(document_type)
    year_text = str(year).strip()
    month_text = str(month).strip().zfill(2)
    if not (len(year_text) == 4 and year_text.isdigit()):
        raise AccountingDocumentArchivePathError('accounting_document_year_invalid')
    if not (len(month_text) == 2 and month_text.isdigit() and 1 <= int(month_text) <= 12):
        raise AccountingDocumentArchivePathError('accounting_document_month_invalid')
    return normalize_relative_drive_target_path(
        f'{workspace_folder}/{year_text}/{drive_folder}/{year_text}-{month_text}'
    )


def validate_confirmed_accounting_document_path(
    path_value: str | Path,
    *,
    workspace_storage_key: str,
    document_type: str,
    expected_leaf: str,
    field_name: str,
) -> AccountingDocumentPathParts:
    storage_key = str(workspace_storage_key).strip()
    if not storage_key or storage_key in {'.', '..'} or '/' in storage_key or '\\' in storage_key:
        raise AccountingDocumentArchivePathError('workspace_storage_key_invalid')
    local_folder, _ = _folders_for_document_type(document_type)
    if expected_leaf not in {'originals', 'metadata'}:
        raise AccountingDocumentArchivePathError('accounting_document_leaf_invalid')

    path = Path(path_value)
    parts = path.parts
    if not parts or any(part in {'.', '..'} or _has_control_character(part) for part in parts):
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')
    if any(part.lower() == 'invoices' for part in parts):
        raise AccountingDocumentArchivePathError(f'{field_name}_invoice_path_rejected')
    if len(parts) < 9:
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')

    relative = parts[-9:]
    if relative[0].lower() != 'workspaces':
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')
    if relative[1] != storage_key:
        raise AccountingDocumentArchivePathError(f'{field_name}_workspace_mismatch')
    if (
        relative[2].lower() != 'years'
        or relative[4].lower() != 'expenses'
        or relative[6] != local_folder
        or relative[7].lower() != expected_leaf
        or not relative[8]
    ):
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')

    year = relative[3]
    month = relative[5]
    if not (len(year) == 4 and year.isdigit()):
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')
    if not (len(month) == 2 and month.isdigit() and 1 <= int(month) <= 12):
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')
    if expected_leaf == 'metadata' and Path(relative[8]).suffix.lower() != '.json':
        raise AccountingDocumentArchivePathError(f'{field_name}_invalid_accounting_path')
    return AccountingDocumentPathParts(year=year, month=month)


def derive_accounting_document_drive_target_path(
    *,
    local_file_path: str | Path,
    metadata_path: str | Path | None,
    workspace_storage_key: str,
    workspace_drive_folder_name: str,
    document_type: str,
) -> str:
    original_parts = validate_confirmed_accounting_document_path(
        local_file_path,
        workspace_storage_key=workspace_storage_key,
        document_type=document_type,
        expected_leaf='originals',
        field_name='local_file_path',
    )
    if metadata_path is not None:
        metadata_parts = validate_confirmed_accounting_document_path(
            metadata_path,
            workspace_storage_key=workspace_storage_key,
            document_type=document_type,
            expected_leaf='metadata',
            field_name='metadata_path',
        )
        if metadata_parts != original_parts:
            raise AccountingDocumentArchivePathError('accounting_document_path_period_mismatch')
    return build_accounting_document_drive_target_path(
        workspace_drive_folder_name=workspace_drive_folder_name,
        document_type=document_type,
        year=original_parts.year,
        month=original_parts.month,
    )


def _folders_for_document_type(document_type: str) -> tuple[str, str]:
    try:
        return _DOCUMENT_TYPE_FOLDERS[document_type]
    except KeyError as exc:
        raise AccountingDocumentArchivePathError('unsupported_accounting_document_type') from exc


def _has_control_character(value: str) -> bool:
    return any(ord(character) < 32 or ord(character) == 127 for character in value)
