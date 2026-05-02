from __future__ import annotations

import json
import os
from pathlib import Path

from bot.services.accounting_document_registry import list_recent_accounting_documents
from bot.services.accounting_document_storage import workspace_key_for_supplier


def _write_metadata(
    storage_dir: Path,
    *,
    stem: str,
    document_type: str = 'receipt',
    folder: str = 'receipts',
    year: str = '2026',
    month: str = '05',
    vendor_name: str | None = 'ASFINAG',
    issue_date: str | None = '2026-05-02',
    total_amount: str | None = '9.60',
    currency: str | None = 'EUR',
    purchase_subject: str | None = '1-dnova dialnicna znamka Rakusko - osobne vozidlo',
    category_candidate: str | None = None,
    upload_date: str | None = '2026-05-02',
    mtime: int | None = None,
    workspace_key: str = 'mykhailo-szco',
) -> Path:
    metadata_dir = storage_dir / 'workspaces' / workspace_key / 'years' / year / 'expenses' / month / folder / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f'{stem}.json'
    business = {
        'vendor_name': vendor_name,
        'issue_date': issue_date,
        'total_amount': total_amount,
        'currency': currency,
    }
    if purchase_subject is not None:
        business['purchase_subject'] = purchase_subject
    if category_candidate is not None:
        business['category_candidate'] = category_candidate
    metadata_path.write_text(
        json.dumps(
            {
                'document_type': document_type,
                'source': {'upload_date': upload_date},
                'business': business,
                'storage': {
                    'original_path': str(metadata_dir.parent / 'originals' / f'{stem}.jpg'),
                    'metadata_path': str(metadata_path),
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    if mtime is not None:
        os.utime(metadata_path, (mtime, mtime))
    return metadata_path


def test_registry_returns_last_5_confirmed_documents_sorted_by_upload_date(tmp_path: Path) -> None:
    for index in range(7):
        _write_metadata(
            tmp_path,
            stem=f'doc-{index}',
            upload_date=f'2026-05-{index + 1:02d}',
            vendor_name=f'Vendor {index}',
        )

    summaries = list_recent_accounting_documents(storage_dir=tmp_path)

    assert len(summaries) == 5
    assert [summary.vendor_name for summary in summaries] == ['Vendor 6', 'Vendor 5', 'Vendor 4', 'Vendor 3', 'Vendor 2']


def test_registry_recent_documents_are_scoped_to_workspace_key(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        stem='user-a',
        vendor_name='User A Vendor',
        workspace_key=workspace_key_for_supplier(111001),
    )
    _write_metadata(
        tmp_path,
        stem='user-b',
        vendor_name='User B Vendor',
        workspace_key=workspace_key_for_supplier(222002),
    )

    summaries = list_recent_accounting_documents(
        storage_dir=tmp_path,
        workspace_key=workspace_key_for_supplier(111001),
    )

    assert [summary.vendor_name for summary in summaries] == ['User A Vendor']


def test_registry_falls_back_to_metadata_mtime_when_upload_date_missing_or_bad(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='old', upload_date='bad-date', vendor_name='Old', mtime=100)
    _write_metadata(tmp_path, stem='new', upload_date=None, vendor_name='New', mtime=200)

    summaries = list_recent_accounting_documents(storage_dir=tmp_path)

    assert [summary.vendor_name for summary in summaries] == ['New', 'Old']


def test_registry_includes_receipts_and_incoming_invoices(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', document_type='receipt', folder='receipts', vendor_name='Receipt Vendor')
    _write_metadata(
        tmp_path,
        stem='incoming',
        document_type='incoming_invoice',
        folder='incoming_invoices',
        vendor_name='Invoice Vendor',
        upload_date='2026-05-03',
    )

    summaries = list_recent_accounting_documents(storage_dir=tmp_path)

    assert {summary.document_type for summary in summaries} == {'receipt', 'incoming_invoice'}
    assert summaries[0].vendor_name == 'Invoice Vendor'


def test_registry_skips_malformed_metadata_safely(tmp_path: Path) -> None:
    metadata_dir = tmp_path / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'metadata'
    metadata_dir.mkdir(parents=True)
    (metadata_dir / 'bad.json').write_text('{bad json', encoding='utf-8')

    assert list_recent_accounting_documents(storage_dir=tmp_path) == []


def test_registry_keeps_missing_fields_as_none(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        stem='missing',
        vendor_name=None,
        issue_date=None,
        total_amount=None,
        currency=None,
        purchase_subject=None,
    )

    summary = list_recent_accounting_documents(storage_dir=tmp_path)[0]

    assert summary.vendor_name is None
    assert summary.issue_date is None
    assert summary.total_amount is None
    assert summary.currency is None
    assert summary.purchase_subject is None


def test_registry_purchase_subject_falls_back_to_legacy_category_candidate(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        stem='legacy',
        purchase_subject=None,
        category_candidate='legacy raw subject',
    )

    summary = list_recent_accounting_documents(storage_dir=tmp_path)[0]

    assert summary.purchase_subject == 'legacy raw subject'


def test_registry_ignores_uploads_invoices_and_contracts(tmp_path: Path) -> None:
    payload = {
        'document_type': 'receipt',
        'source': {'upload_date': '2026-05-05'},
        'business': {'vendor_name': 'Wrong tree'},
    }
    for base in ('uploads/accounting_intake/X', 'invoices', 'contracts'):
        path = tmp_path / base / 'existing.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')

    assert list_recent_accounting_documents(storage_dir=tmp_path) == []


def test_registry_does_not_escape_confirmed_metadata_whitelist(tmp_path: Path) -> None:
    wrong = tmp_path / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'other' / 'x.json'
    wrong.parent.mkdir(parents=True)
    wrong.write_text(json.dumps({'business': {'vendor_name': 'Wrong'}}), encoding='utf-8')

    assert list_recent_accounting_documents(storage_dir=tmp_path) == []
