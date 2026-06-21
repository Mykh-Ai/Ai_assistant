from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

import pandas as pd

from bot.services.accounting_document_categories import allowed_categories_payload
from bot.services.accounting_document_models import DOCUMENT_TYPE_INCOMING_INVOICE, DOCUMENT_TYPE_RECEIPT
from bot.services.accounting_document_registry import CONFIRMED_ACCOUNTING_DOCUMENT_FOLDERS
from bot.services.accounting_document_storage import workspace_key_for_supplier


ACCOUNTING_DOCUMENT_ANALYTICS_COLUMNS = (
    'document_id',
    'document_type',
    'document_type_label',
    'issue_date',
    'tax_date',
    'due_date',
    'vendor_name',
    'document_number',
    'total_amount',
    'currency',
    'vat_amount',
    'payment_method',
    'purchase_subject',
    'category_id',
    'category_label',
    'category_source',
    'category_review_required',
    'line_item_count',
)

_DOCUMENT_TYPE_LABELS = {
    DOCUMENT_TYPE_RECEIPT: 'blocek',
    DOCUMENT_TYPE_INCOMING_INVOICE: 'prijata faktura',
}


@dataclass(frozen=True)
class AccountingDocumentAnalyticsDatasetMetadata:
    workspace_key: str
    row_count: int
    columns: tuple[str, ...]


class AccountingDocumentAnalyticsDatasetService:
    def __init__(self, storage_dir: Path) -> None:
        self._storage_dir = storage_dir

    def build_dataframe_for_supplier(self, *, supplier_telegram_id: int) -> pd.DataFrame:
        workspace_key = workspace_key_for_supplier(supplier_telegram_id)
        return self.build_dataframe_for_workspace(workspace_key=workspace_key)

    def build_dataframe_for_workspace(self, *, workspace_key: str) -> pd.DataFrame:
        records: list[dict[str, Any]] = []
        for metadata_path in _iter_confirmed_metadata_paths(storage_dir=self._storage_dir, workspace_key=workspace_key):
            record = _record_from_metadata(metadata_path)
            if record is not None:
                records.append(record)

        dataframe = pd.DataFrame.from_records(records, columns=ACCOUNTING_DOCUMENT_ANALYTICS_COLUMNS)
        if not dataframe.empty:
            dataframe['total_amount'] = pd.to_numeric(dataframe['total_amount'], errors='coerce').fillna(0.0)
            dataframe['vat_amount'] = pd.to_numeric(dataframe['vat_amount'], errors='coerce').fillna(0.0)
            dataframe['category_review_required'] = dataframe['category_review_required'].astype(bool)
            dataframe['line_item_count'] = pd.to_numeric(
                dataframe['line_item_count'], errors='coerce'
            ).fillna(0).astype(int)
        return dataframe


def _iter_confirmed_metadata_paths(*, storage_dir: Path, workspace_key: str) -> list[Path]:
    storage_root = storage_dir.resolve()
    years_root = storage_root / 'workspaces' / workspace_key / 'years'
    if not years_root.exists():
        return []

    paths: list[Path] = []
    for folder in CONFIRMED_ACCOUNTING_DOCUMENT_FOLDERS.values():
        for metadata_path in years_root.glob(f'*/expenses/*/{folder}/metadata/*.json'):
            if _is_allowed_confirmed_metadata_path(
                storage_root=storage_root,
                workspace_key=workspace_key,
                metadata_path=metadata_path,
            ):
                paths.append(metadata_path)
    return sorted(paths)


def _is_allowed_confirmed_metadata_path(*, storage_root: Path, workspace_key: str, metadata_path: Path) -> bool:
    try:
        resolved = metadata_path.resolve()
        relative = resolved.relative_to(storage_root)
    except (OSError, ValueError):
        return False

    parts = relative.parts
    return (
        len(parts) == 9
        and parts[0] == 'workspaces'
        and parts[1] == workspace_key
        and parts[2] == 'years'
        and parts[4] == 'expenses'
        and parts[6] in set(CONFIRMED_ACCOUNTING_DOCUMENT_FOLDERS.values())
        and parts[7] == 'metadata'
        and resolved.suffix.lower() == '.json'
    )


def _record_from_metadata(metadata_path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(metadata_path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    business = _dict_value(payload.get('business'))
    category = _dict_value(payload.get('category'))
    line_items = payload.get('line_items')
    document_type = _document_type_from_payload(payload, metadata_path)
    if document_type not in {DOCUMENT_TYPE_RECEIPT, DOCUMENT_TYPE_INCOMING_INVOICE}:
        return None

    category_id = _optional_string(category.get('category_id')) or 'uncategorized'
    category_label = _optional_string(category.get('label_snapshot')) or 'Bez kategorie'
    category_source = _optional_string(category.get('source')) or 'missing_category'

    return {
        'document_id': metadata_path.stem,
        'document_type': document_type,
        'document_type_label': _DOCUMENT_TYPE_LABELS.get(document_type, document_type),
        'issue_date': _optional_string(business.get('issue_date')) or '',
        'tax_date': _optional_string(business.get('tax_date')) or '',
        'due_date': _optional_string(business.get('due_date')) or '',
        'vendor_name': _optional_string(business.get('vendor_name')) or 'Neznamy dodavatel',
        'document_number': _optional_string(business.get('document_number')) or '',
        'total_amount': _float_value(business.get('total_amount')),
        'currency': (_optional_string(business.get('currency')) or 'UNKNOWN').upper(),
        'vat_amount': _float_value(business.get('vat_amount')),
        'payment_method': _optional_string(business.get('payment_method')) or 'unknown',
        'purchase_subject': _optional_string(business.get('purchase_subject')) or '',
        'category_id': category_id,
        'category_label': category_label,
        'category_source': category_source,
        'category_review_required': bool(category.get('review_required')) if category else False,
        'line_item_count': len(line_items) if isinstance(line_items, list) else 0,
    }


def _document_type_from_payload(payload: dict[str, Any], metadata_path: Path) -> str:
    document_type = _optional_string(payload.get('document_type')) or ''
    if document_type:
        return document_type
    parts = metadata_path.parts
    if 'receipts' in parts:
        return DOCUMENT_TYPE_RECEIPT
    if 'incoming_invoices' in parts:
        return DOCUMENT_TYPE_INCOMING_INVOICE
    return ''


def _dict_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_value(value: Any) -> float:
    if value is None:
        return 0.0
    try:
        return float(str(value).replace(',', '.'))
    except ValueError:
        return 0.0


_CATEGORY_ALIASES_BY_ID = {
    'materials': ('material', 'materiál', 'матеріал', 'материалы'),
    'tools': ('naradie', 'náradie', 'tools', 'інструмент', 'инструмент'),
    'small_equipment': ('drobne vybavenie', 'drobné vybavenie', 'small equipment'),
    'protective_equipment': ('ochranne pomocky', 'ochranné pomôcky', 'ppe'),
    'consumables': ('spotrebny material', 'spotrebný materiál', 'rozchodniky', 'расходники', 'розхідники'),
    'vehicle_fuel': (
        'palivo',
        'pohonne latky',
        'pohonné látky',
        'fuel',
        'benzín',
        'benzin',
        'diesel',
        'nafta',
        'phm',
        'pálne',
        'пальне',
        'паливо',
        'топливо',
    ),
    'vehicle_service_labor': ('servis auta', 'auto servis', 'praca servis', 'práca servis'),
    'vehicle_parts': ('auto diely', 'autodiely', 'car parts'),
    'vehicle_consumables': ('auto kvapaliny', 'prevadzkove kvapaliny', 'prevádzkové kvapaliny'),
    'vehicle_wash_parking_toll': (
        'parkovanie',
        'parking',
        'umyvanie',
        'umývanie',
        'dialnica',
        'diaľnica',
        'myto',
        'mýto',
        'toll',
    ),
    'office_supplies': ('kancelarske potreby', 'kancelárske potreby', 'office supplies'),
    'software_subscriptions': ('softver', 'softvér', 'subscription', 'predplatne', 'predplatné'),
    'phone_internet': ('telefon', 'telefón', 'internet', 'phone'),
    'travel_accommodation': ('cestovanie', 'ubytovanie', 'travel', 'accommodation'),
    'food_refreshments': ('jedlo', 'voda', 'obcerstvenie', 'občerstvenie', 'food', 'refreshments'),
    'bank_fees': ('bankove poplatky', 'bankové poplatky', 'bank fees'),
    'client_project_expense': ('zakazka', 'zákazka', 'klient', 'project expense'),
    'personal_or_non_business': ('osobne', 'osobné', 'nefiremne', 'nefiremné', 'personal'),
    'mixed_business_expense': ('zmiesany', 'zmiešaný', 'mixed'),
    'unknown_review': ('na kontrolu', 'unknown', 'review'),
}


def _analytics_alias_key(value: str) -> str:
    normalized = unicodedata.normalize('NFKD', str(value).casefold().strip())
    without_diacritics = ''.join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r'\s+', ' ', re.sub(r'[^\w]+', ' ', without_diacritics, flags=re.UNICODE)).strip('_ ')


def _category_alias_payload(item: dict[str, Any]) -> dict[str, Any]:
    category_id = str(item.get('category_id') or '').strip()
    label = str(item.get('label_sk') or category_id).strip()
    aliases = {_analytics_alias_key(label), _analytics_alias_key(category_id)}
    aliases.update(_analytics_alias_key(value) for value in _CATEGORY_ALIASES_BY_ID.get(category_id, ()))
    aliases.discard('')
    return {
        **item,
        'aliases': sorted(aliases),
    }


def _resolve_category_filter_hints(user_question: str, categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized_question = _analytics_alias_key(user_question)
    if not normalized_question:
        return []
    padded_question = f' {normalized_question} '
    matches: list[dict[str, Any]] = []
    for item in categories:
        for alias in item.get('aliases', []):
            normalized_alias = _analytics_alias_key(alias)
            if normalized_alias and f' {normalized_alias} ' in padded_question:
                matches.append(
                    {
                        'category_id': item['category_id'],
                        'label_sk': item.get('label_sk'),
                        'matched_alias': normalized_alias,
                    }
                )
                break
    return matches


def build_accounting_document_analytics_data_catalog(
    *,
    storage_dir: Path | None = None,
    workspace_key: str | None = None,
    user_question: str = '',
) -> dict[str, Any]:
    categories: list[dict[str, Any]] = []
    if storage_dir is not None:
        categories = [
            _category_alias_payload(item)
            for item in allowed_categories_payload(storage_dir=storage_dir, workspace_key=workspace_key)
        ]
    return {
        'datasets': {
            'accounting_documents_df': {
                'description': (
                    'Confirmed expense-side accounting documents for the current workspace only: '
                    'receipts/bloceky and incoming invoices/prijate faktury.'
                ),
                'columns': {
                    'document_id': 'Stable metadata-stem id inside the current workspace dataset.',
                    'document_type': 'receipt or incoming_invoice.',
                    'document_type_label': 'Slovak label for the document type.',
                    'issue_date': 'Document issue date as ISO date string YYYY-MM-DD.',
                    'tax_date': 'Tax/delivery date as ISO date string when present.',
                    'due_date': 'Due date as ISO date string when present.',
                    'vendor_name': 'Vendor/supplier name from confirmed metadata.',
                    'document_number': 'Incoming invoice/document number when present.',
                    'total_amount': 'Document total amount as numeric value.',
                    'currency': 'Currency code, normalized uppercase where possible.',
                    'vat_amount': 'Visible VAT amount as numeric value; not VAT-reporting truth.',
                    'payment_method': 'cash, card, bank_transfer, unknown, or blank-derived unknown.',
                    'purchase_subject': 'Short factual purchase subject from metadata.',
                    'category_id': 'Confirmed category id or Python-derived uncategorized.',
                    'category_label': 'Category label snapshot or Bez kategorie.',
                    'category_source': 'Category source or Python-derived missing_category.',
                    'category_review_required': 'Boolean flag from confirmed category metadata.',
                    'line_item_count': 'Count of stored line items in metadata.',
                },
            }
        },
        'allowed_categories': categories,
        'category_filter_hints': _resolve_category_filter_hints(user_question, categories),
        'category_filter_contract': (
            'For category questions, use only category_id values listed in allowed_categories. '
            'If category_filter_hints is non-empty, generated code must filter category_id by those ids. '
            'Do not invent translated category_label values.'
        ),
        'forbidden': [
            'No outgoing invoice analytics in this dataset.',
            'No bank movements or bank matching.',
            'No tax deductibility, VAT reporting, legal/accounting advice, or accounting export.',
            'No DB writes, file access, SQL, storage paths, raw OCR text, or cross-tenant data.',
            'No category creation or category id mutation.',
        ],
    }
