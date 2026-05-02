from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from bot.services.accounting_document_models import AccountingDocumentCandidate, AccountingDocumentSource
from bot.services.accounting_document_storage import (
    AccountingDocumentStorageError,
    cleanup_temp_staging_path,
    confirmed_filename,
    confirmed_paths,
    save_confirmed_accounting_document,
    stage_original_file,
    temp_staging_dir,
    vendor_slug,
    workspace_key_for_supplier,
)


def _receipt_candidate(*, issue_date='2026-05-01') -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type='receipt',
        vendor_name='Tesco Slovensko s.r.o.',
        issue_date=issue_date,
        total_amount=Decimal('24.90'),
        currency='EUR',
        source=AccountingDocumentSource(
            input_type='photo',
            original_filename='receipt.jpg',
            file_unique_id='ABC123',
            upload_date='2026-05-02',
        ),
    )


def _incoming_invoice_candidate() -> AccountingDocumentCandidate:
    return AccountingDocumentCandidate(
        document_type='incoming_invoice',
        vendor_name='Stredoslovenska energetika',
        document_number='202605001',
        issue_date='2026-05-01',
        due_date='2026-05-15',
        total_amount='118.42',
        currency='EUR',
        iban='SK3112000000198742637541',
        variable_symbol='202605001',
        source=AccountingDocumentSource(
            input_type='pdf',
            original_filename='invoice.pdf',
            file_unique_id='EFGH5678',
            upload_date='2026-05-02',
        ),
    )


def test_filename_slugging_is_deterministic() -> None:
    assert vendor_slug('Stredoslovenska energetika, a.s.') == 'stredoslovenska-energetika-a-s'
    assert confirmed_filename(
        candidate=_receipt_candidate(),
        file_unique_id='ABCD 1234',
        extension='.jpg',
    ) == '20260501_receipt_tesco-slovensko-s-r-o_24-90_ABCD-1234.jpg'


def test_path_derives_from_issue_date_year_month(tmp_path: Path) -> None:
    paths = confirmed_paths(
        storage_dir=tmp_path,
        candidate=_incoming_invoice_candidate(),
        file_unique_id='EFGH5678',
        extension='.pdf',
    )

    expected_part = Path('workspaces/mykhailo-szco/years/2026/expenses/05/incoming_invoices')
    assert expected_part in paths.original_path.relative_to(tmp_path).parents
    assert paths.original_path.parent.name == 'originals'
    assert paths.metadata_path.parent.name == 'metadata'


def test_missing_issue_date_cannot_confirmed_save(tmp_path: Path) -> None:
    candidate = _receipt_candidate(issue_date=None)
    source = tmp_path / 'source.jpg'
    source.write_bytes(b'jpg')

    with pytest.raises(AccountingDocumentStorageError):
        save_confirmed_accounting_document(
            storage_dir=tmp_path,
            source_path=source,
            candidate=candidate,
            file_unique_id='ABC123',
        )


def test_storage_does_not_touch_storage_invoices(tmp_path: Path) -> None:
    source = tmp_path / 'source.jpg'
    source.write_bytes(b'jpg')

    save_confirmed_accounting_document(
        storage_dir=tmp_path,
        source_path=source,
        candidate=_receipt_candidate(),
        file_unique_id='ABC123',
    )

    assert not (tmp_path / 'invoices').exists()


def test_metadata_json_written_next_to_confirmed_original(tmp_path: Path) -> None:
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'%PDF')

    result = save_confirmed_accounting_document(
        storage_dir=tmp_path,
        source_path=source,
        candidate=_incoming_invoice_candidate(),
        file_unique_id='EFGH5678',
    )

    assert result.original_path.exists()
    assert result.metadata_path.exists()
    assert result.original_path.parent.name == 'originals'
    assert result.metadata_path.parent.name == 'metadata'
    assert result.original_path.read_bytes() == b'%PDF'

    metadata = json.loads(result.metadata_path.read_text(encoding='utf-8'))
    assert metadata['document_type'] == 'incoming_invoice'
    assert metadata['business']['vendor_name'] == 'Stredoslovenska energetika'
    assert metadata['business']['total_amount'] == '118.42'
    assert metadata['storage']['original_path'] == str(result.original_path)


def test_confirmed_storage_can_be_scoped_by_supplier_telegram_id(tmp_path: Path) -> None:
    source = tmp_path / 'source.pdf'
    source.write_bytes(b'%PDF')

    result = save_confirmed_accounting_document(
        storage_dir=tmp_path,
        source_path=source,
        candidate=_incoming_invoice_candidate(),
        file_unique_id='EFGH5678',
        supplier_telegram_id=111001,
    )

    relative = result.original_path.relative_to(tmp_path)
    assert relative.parts[:2] == ('workspaces', workspace_key_for_supplier(111001))

    metadata = json.loads(result.metadata_path.read_text(encoding='utf-8'))
    assert metadata['storage']['workspace_key'] == workspace_key_for_supplier(111001)
    assert metadata['storage']['supplier_telegram_id'] == 111001


def test_stage_original_file_uses_temp_accounting_intake_area(tmp_path: Path) -> None:
    source = tmp_path / 'upload.pdf'
    source.write_bytes(b'%PDF')

    staged = stage_original_file(
        storage_dir=tmp_path,
        source_path=source,
        file_unique_id='TEMP123',
    )

    assert staged == tmp_path / 'uploads' / 'accounting_intake' / 'TEMP123' / 'original.pdf'
    assert staged.read_bytes() == b'%PDF'


def test_temp_staging_dir_can_be_scoped_by_supplier_telegram_id(tmp_path: Path) -> None:
    assert temp_staging_dir(tmp_path, 'TEMP123', supplier_telegram_id=111001) == (
        tmp_path / 'uploads' / 'accounting_intake' / '111001' / 'TEMP123'
    )


def test_cleanup_temp_staging_path_removes_only_accounting_intake_file(tmp_path: Path) -> None:
    staged = tmp_path / 'uploads' / 'accounting_intake' / 'TEMP123' / 'original.pdf'
    staged.parent.mkdir(parents=True)
    staged.write_bytes(b'%PDF')

    cleanup_temp_staging_path(storage_dir=tmp_path, staged_path=staged)

    assert not staged.exists()
    assert not staged.parent.exists()


def test_cleanup_temp_staging_path_rejects_non_intake_path(tmp_path: Path) -> None:
    invoice_file = tmp_path / 'invoices' / 'x.pdf'
    invoice_file.parent.mkdir()
    invoice_file.write_bytes(b'%PDF')

    with pytest.raises(AccountingDocumentStorageError, match='refusing_to_cleanup_non_accounting_intake_path'):
        cleanup_temp_staging_path(storage_dir=tmp_path, staged_path=invoice_file)

    assert invoice_file.exists()
