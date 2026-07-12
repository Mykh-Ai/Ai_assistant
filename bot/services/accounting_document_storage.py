from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import unicodedata
from uuid import uuid4

from bot.services.accounting_document_models import (
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    AccountingDocumentCandidate,
    candidate_to_metadata_dict,
)
from bot.services.accounting_document_validation import (
    validate_accounting_document_candidate,
)


WORKSPACE_KEY = 'mykhailo-szco'


def workspace_key_for_supplier(supplier_telegram_id: int) -> str:
    if supplier_telegram_id <= 0:
        raise AccountingDocumentStorageError('supplier_telegram_id_required')
    return f'telegram-{supplier_telegram_id}'


class AccountingDocumentStorageError(ValueError):
    pass


@dataclass(frozen=True)
class AccountingDocumentConfirmedPaths:
    original_path: Path
    metadata_path: Path


@dataclass(frozen=True)
class AccountingDocumentSaveResult:
    original_path: Path
    metadata_path: Path


def vendor_slug(value: str | None) -> str:
    text = (value or '').strip().lower()
    normalized = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join(ch for ch in normalized if not unicodedata.combining(ch)).encode('ascii', 'ignore').decode()
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_text).strip('-')
    return slug or 'unknown_vendor'


def amount_for_filename(value: Decimal | str | int | float) -> str:
    amount = Decimal(str(value).replace(',', '.')).quantize(Decimal('0.01'))
    return f'{amount:.2f}'.replace('.', '-')


def normalize_extension(extension_or_filename: str) -> str:
    suffix = Path(extension_or_filename).suffix if not extension_or_filename.startswith('.') else extension_or_filename
    suffix = suffix.lower().strip()
    if not suffix:
        raise AccountingDocumentStorageError('file_extension_required')
    if not re.fullmatch(r'\.[a-z0-9]{1,10}', suffix):
        raise AccountingDocumentStorageError('file_extension_invalid')
    return suffix


def confirmed_filename(
    *,
    candidate: AccountingDocumentCandidate,
    file_unique_id: str,
    extension: str,
) -> str:
    validation = validate_accounting_document_candidate(candidate)
    if validation.normalized_issue_date is None:
        raise AccountingDocumentStorageError('issue_date_required_for_confirmed_filename')
    if validation.normalized_total_amount is None:
        raise AccountingDocumentStorageError('total_amount_required_for_confirmed_filename')
    if candidate.document_type not in {DOCUMENT_TYPE_RECEIPT, DOCUMENT_TYPE_INCOMING_INVOICE}:
        raise AccountingDocumentStorageError('document_type_invalid_for_confirmed_filename')

    safe_file_id = _safe_file_unique_id(file_unique_id)
    return (
        f'{validation.normalized_issue_date:%Y%m%d}_'
        f'{candidate.document_type}_'
        f'{vendor_slug(candidate.vendor_name)}_'
        f'{amount_for_filename(validation.normalized_total_amount)}_'
        f'{safe_file_id}'
        f'{normalize_extension(extension)}'
    )


def temp_staging_dir(
    storage_dir: Path,
    file_unique_id: str | None = None,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> Path:
    safe_id = _safe_file_unique_id(file_unique_id or str(uuid4()))
    if workspace_key is not None:
        return storage_dir / 'uploads' / 'accounting_intake' / _safe_workspace_key(workspace_key) / safe_id
    if supplier_telegram_id is None:
        return storage_dir / 'uploads' / 'accounting_intake' / safe_id
    return storage_dir / 'uploads' / 'accounting_intake' / str(supplier_telegram_id) / safe_id


def stage_original_file(
    *,
    storage_dir: Path,
    source_path: Path,
    file_unique_id: str | None = None,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> Path:
    target_dir = temp_staging_dir(
        storage_dir,
        file_unique_id,
        supplier_telegram_id,
        workspace_key,
    )
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f'original{normalize_extension(source_path.name)}'
    shutil.copy2(source_path, target_path)
    return target_path


def cleanup_temp_staging_path(*, storage_dir: Path, staged_path: Path) -> None:
    accounting_intake_dir = (storage_dir / 'uploads' / 'accounting_intake').resolve()
    resolved_path = staged_path.resolve()
    if accounting_intake_dir != resolved_path and accounting_intake_dir not in resolved_path.parents:
        raise AccountingDocumentStorageError('refusing_to_cleanup_non_accounting_intake_path')

    if staged_path.is_file():
        staged_path.unlink()

    _remove_empty_upload_parents(staged_path.parent, accounting_intake_dir)


def confirmed_paths(
    *,
    storage_dir: Path,
    candidate: AccountingDocumentCandidate,
    file_unique_id: str,
    extension: str,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> AccountingDocumentConfirmedPaths:
    validation = validate_accounting_document_candidate(candidate)
    if not validation.can_save or validation.normalized_issue_date is None:
        raise AccountingDocumentStorageError('candidate_cannot_be_confirmed_saved')

    issue_date = validation.normalized_issue_date
    plural_folder = _document_type_folder(candidate.document_type)
    filename = confirmed_filename(candidate=candidate, file_unique_id=file_unique_id, extension=extension)
    resolved_workspace_key = workspace_key or (
        workspace_key_for_supplier(supplier_telegram_id)
        if supplier_telegram_id is not None
        else WORKSPACE_KEY
    )
    base_dir = (
        storage_dir
        / 'workspaces'
        / resolved_workspace_key
        / 'years'
        / f'{issue_date.year:04d}'
        / 'expenses'
        / f'{issue_date.month:02d}'
        / plural_folder
    )
    original_path = base_dir / 'originals' / filename
    metadata_path = base_dir / 'metadata' / f'{Path(filename).stem}.json'
    _assert_not_invoice_path(storage_dir, original_path)
    _assert_not_invoice_path(storage_dir, metadata_path)
    return AccountingDocumentConfirmedPaths(original_path=original_path, metadata_path=metadata_path)


def save_confirmed_accounting_document(
    *,
    storage_dir: Path,
    source_path: Path,
    candidate: AccountingDocumentCandidate,
    file_unique_id: str,
    extension: str | None = None,
    supplier_telegram_id: int | None = None,
    workspace_key: str | None = None,
) -> AccountingDocumentSaveResult:
    selected_extension = extension or source_path.suffix
    paths = confirmed_paths(
        storage_dir=storage_dir,
        candidate=candidate,
        file_unique_id=file_unique_id,
        extension=selected_extension,
        supplier_telegram_id=supplier_telegram_id,
        workspace_key=workspace_key,
    )
    paths.original_path.parent.mkdir(parents=True, exist_ok=True)
    paths.metadata_path.parent.mkdir(parents=True, exist_ok=True)

    shutil.copy2(source_path, paths.original_path)
    metadata = candidate_to_metadata_dict(candidate)
    resolved_workspace_key = workspace_key or (
        workspace_key_for_supplier(supplier_telegram_id)
        if supplier_telegram_id is not None
        else WORKSPACE_KEY
    )
    metadata['storage'] = {
        'workspace_key': resolved_workspace_key,
        'supplier_telegram_id': supplier_telegram_id,
        'original_path': str(paths.original_path),
        'metadata_path': str(paths.metadata_path),
    }
    paths.metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True),
        encoding='utf-8',
    )
    return AccountingDocumentSaveResult(original_path=paths.original_path, metadata_path=paths.metadata_path)


def _document_type_folder(document_type: str) -> str:
    if document_type == DOCUMENT_TYPE_RECEIPT:
        return 'receipts'
    if document_type == DOCUMENT_TYPE_INCOMING_INVOICE:
        return 'incoming_invoices'
    raise AccountingDocumentStorageError('document_type_invalid_for_storage')


def _safe_workspace_key(value: str) -> str:
    normalized = str(value).strip()
    if not normalized or normalized in {'.', '..'} or '/' in normalized or '\\' in normalized:
        raise AccountingDocumentStorageError('workspace_key_invalid')
    return normalized


def _safe_file_unique_id(value: str) -> str:
    safe = re.sub(r'[^A-Za-z0-9_-]+', '-', value.strip()).strip('-')
    if not safe:
        raise AccountingDocumentStorageError('file_unique_id_required')
    return safe[:96]


def _assert_not_invoice_path(storage_dir: Path, path: Path) -> None:
    invoices_dir = (storage_dir / 'invoices').resolve()
    resolved_path = path.resolve()
    if resolved_path == invoices_dir or invoices_dir in resolved_path.parents:
        raise AccountingDocumentStorageError('refusing_to_write_to_invoice_storage')


def _remove_empty_upload_parents(start_dir: Path, stop_dir: Path) -> None:
    current = start_dir
    while current.exists() and current.resolve() != stop_dir:
        try:
            parent = current.parent
            current.rmdir()
        except OSError:
            return
        if parent.resolve() == stop_dir:
            return
        current = parent
