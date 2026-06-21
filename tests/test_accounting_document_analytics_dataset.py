import json
from pathlib import Path

from bot.services.accounting_document_analytics_dataset import (
    ACCOUNTING_DOCUMENT_ANALYTICS_COLUMNS,
    AccountingDocumentAnalyticsDatasetService,
)


def _write_metadata(storage_dir: Path, workspace_key: str, document_type: str, document_id: str, payload: dict) -> None:
    folder = 'receipts' if document_type == 'receipt' else 'incoming_invoices'
    metadata_dir = storage_dir / 'workspaces' / workspace_key / 'years' / '2026' / 'expenses' / '06' / folder / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    (metadata_dir / f'{document_id}.json').write_text(json.dumps(payload), encoding='utf-8')


def test_accounting_document_analytics_dataset_is_workspace_scoped_and_sanitized(tmp_path: Path) -> None:
    storage_dir = tmp_path / 'storage'
    _write_metadata(
        storage_dir,
        'telegram-111',
        'receipt',
        'r1',
        {
            'document_type': 'receipt',
            'business': {
                'issue_date': '2026-06-03',
                'vendor_name': 'BAUHAUS',
                'total_amount': '13.83',
                'currency': 'eur',
                'vat_amount': '2.30',
                'payment_method': 'card',
                'purchase_subject': 'spotrebny material',
            },
            'category': {
                'category_id': 'small_consumables',
                'label_snapshot': 'Drobne rozchodniky',
                'source': 'confirmed_existing',
                'review_required': False,
            },
            'line_items': [{'name': 'screws'}, {'name': 'glue'}],
            'storage': {'original_path': '/secret/path/photo.jpg'},
        },
    )
    _write_metadata(
        storage_dir,
        'telegram-222',
        'receipt',
        'other',
        {
            'document_type': 'receipt',
            'business': {'issue_date': '2026-06-04', 'vendor_name': 'Other', 'total_amount': 99, 'currency': 'EUR'},
        },
    )

    dataframe = AccountingDocumentAnalyticsDatasetService(storage_dir).build_dataframe_for_workspace(
        workspace_key='telegram-111'
    )

    assert tuple(dataframe.columns) == ACCOUNTING_DOCUMENT_ANALYTICS_COLUMNS
    assert len(dataframe) == 1
    row = dataframe.iloc[0].to_dict()
    assert row['document_id'] == 'r1'
    assert row['document_type'] == 'receipt'
    assert row['vendor_name'] == 'BAUHAUS'
    assert row['total_amount'] == 13.83
    assert row['currency'] == 'EUR'
    assert row['category_id'] == 'small_consumables'
    assert row['line_item_count'] == 2
    assert not any('path' in column.lower() or 'storage' in column.lower() for column in dataframe.columns)


def test_accounting_document_analytics_dataset_keeps_old_metadata_readable(tmp_path: Path) -> None:
    storage_dir = tmp_path / 'storage'
    _write_metadata(
        storage_dir,
        'telegram-111',
        'incoming_invoice',
        'legacy',
        {
            'business': {
                'issue_date': '2026-06-07',
                'vendor_name': 'Legacy supplier',
                'document_number': 'IN-1',
                'total_amount': 44,
                'currency': 'EUR',
            }
        },
    )

    dataframe = AccountingDocumentAnalyticsDatasetService(storage_dir).build_dataframe_for_workspace(
        workspace_key='telegram-111'
    )

    assert len(dataframe) == 1
    row = dataframe.iloc[0].to_dict()
    assert row['document_type'] == 'incoming_invoice'
    assert row['category_id'] == 'uncategorized'
    assert row['category_label'] == 'Bez kategorie'
    assert row['category_source'] == 'missing_category'
    assert row['line_item_count'] == 0


def test_accounting_document_analytics_dataset_empty_workspace_has_stable_columns(tmp_path: Path) -> None:
    dataframe = AccountingDocumentAnalyticsDatasetService(tmp_path / 'storage').build_dataframe_for_workspace(
        workspace_key='telegram-111'
    )

    assert dataframe.empty
    assert tuple(dataframe.columns) == ACCOUNTING_DOCUMENT_ANALYTICS_COLUMNS
