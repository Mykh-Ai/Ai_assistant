from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any

from bot.services.accounting_document_models import DOCUMENT_TYPE_INCOMING_INVOICE, DOCUMENT_TYPE_RECEIPT
from bot.services.accounting_document_storage import WORKSPACE_KEY


CONFIRMED_ACCOUNTING_DOCUMENT_FOLDERS = {
    DOCUMENT_TYPE_RECEIPT: 'receipts',
    DOCUMENT_TYPE_INCOMING_INVOICE: 'incoming_invoices',
}


@dataclass(frozen=True)
class AccountingDocumentSummary:
    document_type: str
    vendor_name: str | None
    issue_date: str | None
    total_amount: str | None
    currency: str | None
    purchase_subject: str | None
    upload_date: str | None
    metadata_path: str
    original_path: str | None


@dataclass(frozen=True)
class _ScoredAccountingDocumentSummary:
    summary: AccountingDocumentSummary
    sort_key: tuple[int, float]


def list_recent_accounting_documents(
    *,
    storage_dir: Path,
    workspace_key: str = WORKSPACE_KEY,
    limit: int = 5,
) -> list[AccountingDocumentSummary]:
    """Return recent confirmed accounting documents from the whitelisted metadata tree only."""

    if limit <= 0:
        return []

    scored: list[_ScoredAccountingDocumentSummary] = []
    for metadata_path in _iter_confirmed_metadata_paths(storage_dir=storage_dir, workspace_key=workspace_key):
        summary = _summary_from_metadata_path(metadata_path)
        if summary is None:
            continue
        scored.append(_ScoredAccountingDocumentSummary(summary=summary, sort_key=_sort_key(summary, metadata_path)))

    scored.sort(key=lambda item: item.sort_key, reverse=True)
    return [item.summary for item in scored[:limit]]


def _iter_confirmed_metadata_paths(*, storage_dir: Path, workspace_key: str) -> list[Path]:
    storage_root = storage_dir.resolve()
    years_root = storage_root / 'workspaces' / workspace_key / 'years'
    if not years_root.exists():
        return []

    paths: list[Path] = []
    for folder in CONFIRMED_ACCOUNTING_DOCUMENT_FOLDERS.values():
        pattern = f'*/expenses/*/{folder}/metadata/*.json'
        for metadata_path in years_root.glob(pattern):
            if _is_allowed_confirmed_metadata_path(
                storage_root=storage_root,
                workspace_key=workspace_key,
                metadata_path=metadata_path,
            ):
                paths.append(metadata_path)
    return paths


def _is_allowed_confirmed_metadata_path(*, storage_root: Path, workspace_key: str, metadata_path: Path) -> bool:
    try:
        resolved = metadata_path.resolve()
        relative = resolved.relative_to(storage_root)
    except (OSError, ValueError):
        return False

    parts = relative.parts
    if len(parts) != 9:
        return False
    return (
        parts[0] == 'workspaces'
        and parts[1] == workspace_key
        and parts[2] == 'years'
        and parts[4] == 'expenses'
        and parts[6] in set(CONFIRMED_ACCOUNTING_DOCUMENT_FOLDERS.values())
        and parts[7] == 'metadata'
        and resolved.suffix.lower() == '.json'
    )


def _summary_from_metadata_path(metadata_path: Path) -> AccountingDocumentSummary | None:
    try:
        payload = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    business = payload.get('business')
    source = payload.get('source')
    storage = payload.get('storage')
    if not isinstance(business, dict):
        business = {}
    if not isinstance(source, dict):
        source = {}
    if not isinstance(storage, dict):
        storage = {}

    document_type = _optional_string(payload.get('document_type')) or 'unknown'
    purchase_subject = _optional_string(business.get('purchase_subject')) or _optional_string(
        business.get('category_candidate')
    )
    return AccountingDocumentSummary(
        document_type=document_type,
        vendor_name=_optional_string(business.get('vendor_name')),
        issue_date=_optional_string(business.get('issue_date')),
        total_amount=_optional_string(business.get('total_amount')),
        currency=_optional_string(business.get('currency')),
        purchase_subject=purchase_subject,
        upload_date=_optional_string(source.get('upload_date')),
        metadata_path=str(metadata_path),
        original_path=_optional_string(storage.get('original_path')),
    )


def _sort_key(summary: AccountingDocumentSummary, metadata_path: Path) -> tuple[int, float]:
    upload_datetime = _parse_upload_datetime(summary.upload_date)
    if upload_datetime is not None:
        return (1, upload_datetime.timestamp())
    try:
        return (0, metadata_path.stat().st_mtime)
    except OSError:
        return (0, 0.0)


def _parse_upload_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        parsed_date = date.fromisoformat(text)
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace('Z', '+00:00'))
        except ValueError:
            return None
    return datetime.combine(parsed_date, datetime.min.time())


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
