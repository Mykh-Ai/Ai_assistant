from __future__ import annotations

import json
from pathlib import Path

from bot.services.accounting_document_duplicates import find_duplicate_accounting_document, normalize_vendor_name
from bot.services.accounting_document_models import AccountingDocumentCandidate
from bot.services.accounting_document_storage import workspace_key_for_supplier


def _candidate(
    *,
    document_type: str = 'receipt',
    vendor_name: str = 'ASFINAG',
    issue_date: str = '2026-03-14',
    total_amount: str = '9.60',
    currency: str = 'EUR',
) -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type=document_type,
        vendor_name=vendor_name,
        issue_date=issue_date,
        total_amount=total_amount,
        currency=currency,
        purchase_subject='1-dňová diaľničná známka Rakúsko - osobné vozidlo',
    )


def _write_metadata(
    tmp_path: Path,
    *,
    document_type: str = 'receipt',
    vendor_name: str = 'ASFINAG',
    issue_date: str = '2026-03-14',
    total_amount: str = '9.60',
    currency: str = 'EUR',
    base: str = 'workspaces/mykhailo-szco/years/2026/expenses/03/receipts/metadata',
) -> Path:
    metadata_dir = tmp_path / base
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / 'existing.json'
    metadata_path.write_text(
        json.dumps(
            {
                'document_type': document_type,
                'business': {
                    'vendor_name': vendor_name,
                    'issue_date': issue_date,
                    'total_amount': total_amount,
                    'currency': currency,
                    'purchase_subject': '1-dňová diaľničná známka Rakúsko - osobné vozidlo',
                },
                'storage': {
                    'original_path': str(tmp_path / 'workspaces/original.jpg'),
                    'metadata_path': str(metadata_path),
                },
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    return metadata_path


def test_duplicate_found_for_matching_confirmed_metadata(tmp_path: Path) -> None:
    metadata_path = _write_metadata(tmp_path)

    match = find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate())

    assert match is not None
    assert match.vendor_name == 'ASFINAG'
    assert match.metadata_path == str(metadata_path)


def test_duplicate_detection_is_scoped_to_workspace_key(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        base=f'workspaces/{workspace_key_for_supplier(222002)}/years/2026/expenses/03/receipts/metadata',
    )

    assert find_duplicate_accounting_document(
        storage_dir=tmp_path,
        candidate=_candidate(),
        workspace_key=workspace_key_for_supplier(111001),
    ) is None
    assert find_duplicate_accounting_document(
        storage_dir=tmp_path,
        candidate=_candidate(),
        workspace_key=workspace_key_for_supplier(222002),
    ) is not None


def test_no_duplicate_when_amount_differs(tmp_path: Path) -> None:
    _write_metadata(tmp_path, total_amount='9.70')

    assert find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate()) is None


def test_no_duplicate_when_vendor_differs(tmp_path: Path) -> None:
    _write_metadata(tmp_path, vendor_name='OMV')

    assert find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate()) is None


def test_no_duplicate_when_document_type_differs(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        document_type='incoming_invoice',
        base='workspaces/mykhailo-szco/years/2026/expenses/03/incoming_invoices/metadata',
    )

    assert find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate()) is None


def test_no_duplicate_when_issue_date_differs(tmp_path: Path) -> None:
    _write_metadata(tmp_path, issue_date='2026-03-15', base='workspaces/mykhailo-szco/years/2026/expenses/03/receipts/metadata')

    assert find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate()) is None


def test_malformed_metadata_skipped_safely(tmp_path: Path) -> None:
    metadata_dir = tmp_path / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '03' / 'receipts' / 'metadata'
    metadata_dir.mkdir(parents=True)
    (metadata_dir / 'bad.json').write_text('{bad json', encoding='utf-8')

    assert find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate()) is None


def test_scanner_ignores_uploads_invoices_and_contracts(tmp_path: Path) -> None:
    payload = {
        'document_type': 'receipt',
        'business': {
            'vendor_name': 'ASFINAG',
            'issue_date': '2026-03-14',
            'total_amount': '9.60',
            'currency': 'EUR',
        },
    }
    for base in ('uploads/accounting_intake/X', 'invoices', 'contracts'):
        path = tmp_path / base / 'existing.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload), encoding='utf-8')

    assert find_duplicate_accounting_document(storage_dir=tmp_path, candidate=_candidate()) is None


def test_normalized_vendor_equality_handles_case_punctuation_and_diacritics(tmp_path: Path) -> None:
    _write_metadata(tmp_path, vendor_name='Železničná, a.s.')

    match = find_duplicate_accounting_document(
        storage_dir=tmp_path,
        candidate=_candidate(vendor_name='zeleznična a s'),
    )

    assert normalize_vendor_name('Železničná, a.s.') == normalize_vendor_name('zeleznična a s')
    assert match is not None
