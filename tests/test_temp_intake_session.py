from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os
from pathlib import Path

import pytest

from bot.services.temp_intake_session import (
    TempIntakeSessionError,
    build_intake_session_metadata,
    cleanup_intake_temp_paths,
    cleanup_old_intake_temp_dirs,
    is_intake_session_expired,
)


def test_intake_session_expiry_metadata() -> None:
    now = datetime(2026, 5, 2, 10, 0, tzinfo=UTC)
    data = build_intake_session_metadata(
        temp_paths=['storage/uploads/accounting_intake/abc/original.jpg'],
        cleanup_kind='accounting_document_preview',
        now=now,
    )

    assert is_intake_session_expired(data, now=now + timedelta(minutes=4, seconds=59)) is False
    assert is_intake_session_expired(data, now=now + timedelta(minutes=5)) is True


def test_cleanup_refuses_paths_outside_allowed_temp_roots(tmp_path: Path) -> None:
    confirmed = tmp_path / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'originals' / 'file.jpg'
    confirmed.parent.mkdir(parents=True)
    confirmed.write_bytes(b'confirmed')

    with pytest.raises(TempIntakeSessionError, match='refusing_to_cleanup_non_intake_temp_path'):
        cleanup_intake_temp_paths(storage_dir=tmp_path, temp_paths=[confirmed])

    assert confirmed.exists()


@pytest.mark.parametrize(
    'protected_path',
    [
        ('invoices', '20260001.pdf'),
        ('contracts', 'contract.pdf'),
    ],
)
def test_cleanup_does_not_touch_invoice_or_contract_paths(tmp_path: Path, protected_path: tuple[str, str]) -> None:
    protected = tmp_path / protected_path[0] / protected_path[1]
    protected.parent.mkdir(parents=True)
    protected.write_bytes(b'protected')

    with pytest.raises(TempIntakeSessionError):
        cleanup_intake_temp_paths(storage_dir=tmp_path, temp_paths=[protected])

    assert protected.exists()


def test_filesystem_orphan_cleanup_removes_only_old_allowed_dirs(tmp_path: Path) -> None:
    now = datetime(2026, 5, 2, 10, 0, tzinfo=UTC)
    old_attachment = tmp_path / 'uploads' / 'attachment_intake' / 'old' / 'original.jpg'
    fresh_accounting = tmp_path / 'uploads' / 'accounting_intake' / 'fresh' / 'original.jpg'
    confirmed = tmp_path / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '05' / 'receipts' / 'originals' / 'file.jpg'
    invoice = tmp_path / 'invoices' / '20260001.pdf'
    contract = tmp_path / 'contracts' / 'contract.pdf'

    for path in (old_attachment, fresh_accounting, confirmed, invoice, contract):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'data')

    old_mtime = (now - timedelta(hours=25)).timestamp()
    fresh_mtime = (now - timedelta(minutes=10)).timestamp()
    os.utime(old_attachment.parent, (old_mtime, old_mtime))
    os.utime(old_attachment, (old_mtime, old_mtime))
    os.utime(fresh_accounting.parent, (fresh_mtime, fresh_mtime))
    os.utime(fresh_accounting, (fresh_mtime, fresh_mtime))

    removed = cleanup_old_intake_temp_dirs(storage_dir=tmp_path, now=now)

    assert old_attachment.parent in removed
    assert not old_attachment.parent.exists()
    assert fresh_accounting.exists()
    assert confirmed.exists()
    assert invoice.exists()
    assert contract.exists()
