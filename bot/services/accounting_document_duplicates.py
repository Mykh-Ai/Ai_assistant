from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from bot.services.accounting_document_models import (
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    AccountingDocumentCandidate,
)
from bot.services.accounting_document_storage import WORKSPACE_KEY
from bot.services.accounting_document_validation import parse_iso_date, parse_positive_decimal


@dataclass(frozen=True)
class DuplicateMatch:
    document_type: str
    vendor_name: str | None
    issue_date: str
    total_amount: str
    currency: str
    purchase_subject: str | None
    metadata_path: str
    original_path: str | None

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def find_duplicate_accounting_document(
    *,
    storage_dir: Path,
    candidate: AccountingDocumentCandidate,
    workspace_key: str = WORKSPACE_KEY,
) -> DuplicateMatch | None:
    candidate_key = _candidate_duplicate_key(candidate)
    if candidate_key is None:
        return None

    metadata_dir = _metadata_dir_for_candidate(
        storage_dir=storage_dir,
        candidate=candidate,
        workspace_key=workspace_key,
    )
    if metadata_dir is None or not metadata_dir.exists():
        return None

    for metadata_path in sorted(metadata_dir.glob('*.json')):
        match = _match_from_metadata_path(metadata_path)
        if match is None:
            continue
        if _match_duplicate_key(match) == candidate_key:
            return match
    return None


def normalize_vendor_name(value: str | None) -> str | None:
    text = (value or '').strip().lower()
    if not text:
        return None
    normalized = unicodedata.normalize('NFKD', text)
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    compact = re.sub(r'[^a-z0-9]+', ' ', without_diacritics).strip()
    return re.sub(r'\s+', ' ', compact) or None


def _candidate_duplicate_key(candidate: AccountingDocumentCandidate) -> tuple[str, str, str, Decimal, str] | None:
    if candidate.document_type not in {DOCUMENT_TYPE_RECEIPT, DOCUMENT_TYPE_INCOMING_INVOICE}:
        return None

    issue_date = parse_iso_date(candidate.issue_date)
    vendor = normalize_vendor_name(candidate.vendor_name)
    amount = parse_positive_decimal(candidate.total_amount)
    currency = _normalize_currency(candidate.currency)
    if issue_date is None or vendor is None or amount is None or currency is None:
        return None
    return (candidate.document_type, issue_date.isoformat(), vendor, amount, currency)


def _match_duplicate_key(match: DuplicateMatch) -> tuple[str, str, str, Decimal, str] | None:
    vendor = normalize_vendor_name(match.vendor_name)
    amount = _parse_decimal(match.total_amount)
    currency = _normalize_currency(match.currency)
    if vendor is None or amount is None or currency is None:
        return None
    return (match.document_type, match.issue_date, vendor, amount, currency)


def _metadata_dir_for_candidate(
    *,
    storage_dir: Path,
    candidate: AccountingDocumentCandidate,
    workspace_key: str,
) -> Path | None:
    issue_date = parse_iso_date(candidate.issue_date)
    if issue_date is None:
        return None
    folder = _document_type_folder(candidate.document_type)
    if folder is None:
        return None
    return (
        storage_dir
        / 'workspaces'
        / workspace_key
        / 'years'
        / f'{issue_date.year:04d}'
        / 'expenses'
        / f'{issue_date.month:02d}'
        / folder
        / 'metadata'
    )


def _match_from_metadata_path(metadata_path: Path) -> DuplicateMatch | None:
    try:
        payload = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    business = payload.get('business')
    storage = payload.get('storage')
    if not isinstance(business, dict):
        return None
    if not isinstance(storage, dict):
        storage = {}

    document_type = _optional_string(payload.get('document_type'))
    issue_date = parse_iso_date(_optional_string(business.get('issue_date')))
    amount = _parse_decimal(business.get('total_amount'))
    currency = _normalize_currency(_optional_string(business.get('currency')))
    if document_type not in {DOCUMENT_TYPE_RECEIPT, DOCUMENT_TYPE_INCOMING_INVOICE}:
        return None
    if issue_date is None or amount is None or currency is None:
        return None

    return DuplicateMatch(
        document_type=document_type,
        vendor_name=_optional_string(business.get('vendor_name')),
        issue_date=issue_date.isoformat(),
        total_amount=str(amount),
        currency=currency,
        purchase_subject=_optional_string(business.get('purchase_subject')),
        metadata_path=str(metadata_path),
        original_path=_optional_string(storage.get('original_path')),
    )


def _document_type_folder(document_type: str) -> str | None:
    if document_type == DOCUMENT_TYPE_RECEIPT:
        return 'receipts'
    if document_type == DOCUMENT_TYPE_INCOMING_INVOICE:
        return 'incoming_invoices'
    return None


def _normalize_currency(value: str | None) -> str | None:
    text = (value or '').strip().upper()
    if not re.fullmatch(r'[A-Z]{3}', text):
        return None
    return text


def _parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value).replace(',', '.').strip())
    except (InvalidOperation, AttributeError):
        return None


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
