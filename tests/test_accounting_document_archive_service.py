from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import inspect

import pytest

from bot.services import accounting_document_archive_service
from bot.services.accounting_document_archive_service import (
    ARCHIVE_STATUS_ABANDONED,
    ARCHIVE_STATUS_FAILED,
    ARCHIVE_STATUS_PENDING,
    ARCHIVE_STATUS_RETRY_WAIT,
    ARCHIVE_STATUS_UPLOADED,
    ARCHIVE_STATUS_UPLOADING,
    AccountingDocumentArchiveService,
    AccountingDocumentArchiveServiceError,
)
from bot.services.accounting_document_storage import workspace_key_for_supplier
from bot.services.archive_job_service import ArchiveJobService
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import ProductTruthStatus, get_capability


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'archive-state.db'


def _confirmed_document_paths(tmp_path: Path) -> tuple[Path, Path]:
    base = (
        tmp_path
        / 'workspaces'
        / workspace_key_for_supplier(111001)
        / 'years'
        / '2026'
        / 'expenses'
        / '05'
        / 'receipts'
    )
    original_path = base / 'originals' / '20260530_receipt_shop_12-30_FILE123.jpg'
    metadata_path = base / 'metadata' / '20260530_receipt_shop_12-30_FILE123.json'
    original_path.parent.mkdir(parents=True, exist_ok=True)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(b'jpeg')
    metadata_path.write_text('{}', encoding='utf-8')
    return original_path, metadata_path


def _enqueue(service: AccountingDocumentArchiveService, tmp_path: Path):
    original_path, metadata_path = _confirmed_document_paths(tmp_path)
    return service.enqueue_confirmed_document(
        workspace_id=workspace_key_for_supplier(111001),
        telegram_id=111001,
        document_id='20260530_receipt_shop_12-30_FILE123',
        document_type='receipt',
        local_file_path=original_path,
        metadata_path=metadata_path,
    )


def test_accounting_document_archive_schema_bootstrap_is_idempotent(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))

    service.ensure_schema()
    service.ensure_schema()

    assert service.get_state(
        workspace_id=workspace_key_for_supplier(111001),
        document_id='missing',
    ) is None


def test_enqueue_confirmed_document_creates_pending_job_and_state(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))
    original_path, metadata_path = _confirmed_document_paths(tmp_path)

    result = service.enqueue_confirmed_document(
        workspace_id=workspace_key_for_supplier(111001),
        telegram_id=111001,
        document_id='20260530_receipt_shop_12-30_FILE123',
        document_type='receipt',
        local_file_path=original_path,
        metadata_path=metadata_path,
    )

    assert result.job.status == ARCHIVE_STATUS_PENDING
    assert result.state.archive_status == ARCHIVE_STATUS_PENDING
    assert result.state.latest_job_id == result.job.job_id
    assert result.state.local_file_path == str(original_path)
    assert result.state.metadata_path == str(metadata_path)


def test_enqueue_confirmed_document_is_idempotent_for_same_document(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))

    first = _enqueue(service, tmp_path)
    second = _enqueue(service, tmp_path)

    assert second.job.job_id == first.job.job_id
    assert second.state.latest_job_id == first.job.job_id


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('workspace_id', ''),
        ('telegram_id', 0),
        ('document_id', ''),
        ('document_type', ''),
        ('local_file_path', ''),
    ],
)
def test_enqueue_confirmed_document_rejects_missing_required_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    original_path, metadata_path = _confirmed_document_paths(tmp_path)
    payload = {
        'workspace_id': workspace_key_for_supplier(111001),
        'telegram_id': 111001,
        'document_id': '20260530_receipt_shop_12-30_FILE123',
        'document_type': 'receipt',
        'local_file_path': str(original_path),
        'metadata_path': str(metadata_path),
    }
    payload[field] = value

    with pytest.raises(AccountingDocumentArchiveServiceError):
        AccountingDocumentArchiveService(_db_path(tmp_path)).enqueue_confirmed_document(**payload)


def test_archive_state_can_be_read_by_workspace_and_document_id(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))
    result = _enqueue(service, tmp_path)

    state = service.get_state(
        workspace_id=workspace_key_for_supplier(111001),
        document_id='20260530_receipt_shop_12-30_FILE123',
    )

    assert state == result.state
    assert service.get_state(workspace_id=workspace_key_for_supplier(222002), document_id=result.state.document_id) is None


def test_archive_state_read_only_does_not_create_missing_db_file(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    service = AccountingDocumentArchiveService(db_path)

    state = service.get_state_read_only(
        workspace_id=workspace_key_for_supplier(111001),
        document_id='missing',
    )

    assert state is None
    assert not db_path.exists()


def test_mark_uploading_and_uploaded_updates_archive_state(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))
    result = _enqueue(service, tmp_path)
    uploaded_at = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

    uploading = service.mark_uploading(result.job.job_id)
    uploaded = service.mark_uploaded(
        result.job.job_id,
        drive_file_id='fake-drive-file-id',
        drive_folder_id='fake-folder-id',
        uploaded_at=uploaded_at,
    )

    assert uploading.archive_status == ARCHIVE_STATUS_UPLOADING
    assert uploaded.archive_status == ARCHIVE_STATUS_UPLOADED
    assert uploaded.drive_file_id == 'fake-drive-file-id'
    assert uploaded.drive_folder_id == 'fake-folder-id'
    assert uploaded.uploaded_at == uploaded_at.isoformat()
    assert uploaded.last_error_code is None


def test_retry_wait_and_failed_states_keep_local_file(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))
    original_path, _ = _confirmed_document_paths(tmp_path)
    result = _enqueue(service, tmp_path)
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

    service.mark_uploading(result.job.job_id, now=now)
    retry = service.mark_retry_wait(
        result.job.job_id,
        error_code='temporary_error',
        next_attempt_at=now + timedelta(minutes=15),
        now=now,
    )
    failed_result = service.enqueue_confirmed_document(
        workspace_id=workspace_key_for_supplier(111001),
        telegram_id=111001,
        document_id='20260530_receipt_shop_12-30_FILE456',
        document_type='receipt',
        local_file_path=original_path,
        metadata_path=_confirmed_document_paths(tmp_path)[1],
    )
    service.mark_uploading(failed_result.job.job_id, now=now)
    failed = service.mark_failed(failed_result.job.job_id, error_code='manual_stop', now=now)

    assert retry.archive_status == ARCHIVE_STATUS_RETRY_WAIT
    assert retry.last_error_code == 'temporary_error'
    assert failed.archive_status == ARCHIVE_STATUS_FAILED
    assert failed.last_error_code == 'manual_stop'
    assert original_path.exists()


def test_abandoned_state_keeps_local_file(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))
    original_path, _ = _confirmed_document_paths(tmp_path)
    result = _enqueue(service, tmp_path)

    service.mark_uploading(result.job.job_id)
    abandoned = service.mark_abandoned(result.job.job_id, error_code='permission_denied')

    assert abandoned.archive_status == ARCHIVE_STATUS_ABANDONED
    assert abandoned.last_error_code == 'permission_denied'
    assert original_path.exists()


def test_enqueue_confirmed_document_after_uploaded_terminal_keeps_existing_state(tmp_path: Path) -> None:
    service = AccountingDocumentArchiveService(_db_path(tmp_path))
    result = _enqueue(service, tmp_path)
    uploaded_at = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)
    service.mark_uploading(result.job.job_id, now=uploaded_at)
    service.mark_uploaded(
        result.job.job_id,
        drive_file_id='fake-drive-file-id',
        drive_folder_id='fake-folder-id',
        uploaded_at=uploaded_at,
    )

    second = _enqueue(service, tmp_path)

    assert second.job.job_id == result.job.job_id
    assert second.state.archive_status == ARCHIVE_STATUS_UPLOADED
    assert second.state.drive_file_id == 'fake-drive-file-id'
    assert second.state.uploaded_at == uploaded_at.isoformat()


def test_mark_methods_fail_safely_when_archive_state_is_missing(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    jobs = ArchiveJobService(db_path)
    service = AccountingDocumentArchiveService(db_path)
    original_path, metadata_path = _confirmed_document_paths(tmp_path)
    job = jobs.enqueue_job(
        workspace_id=workspace_key_for_supplier(111001),
        telegram_id=111001,
        document_id='20260530_receipt_shop_12-30_FILE123',
        document_type='receipt',
        local_file_path=original_path,
        metadata_path=metadata_path,
    )

    with pytest.raises(AccountingDocumentArchiveServiceError, match='archive_state_missing'):
        service.mark_uploading(job.job_id)

    assert jobs.get_job(job.job_id).status == ARCHIVE_STATUS_PENDING


def test_accounting_handlers_do_not_call_google_or_archive_worker() -> None:
    handler_paths = [
        Path('bot/handlers/accounting_document_intake.py'),
        Path('bot/handlers/accounting_documents.py'),
    ]
    forbidden = (
        'archive_job_service',
        'claim_next_runnable_job',
        'mark_uploading',
        'mark_uploaded',
        'googleapiclient',
        'google.auth',
        'requests',
        'httpx',
        'aiohttp',
    )

    for handler_path in handler_paths:
        source = handler_path.read_text(encoding='utf-8')
        assert not any(token in source for token in forbidden), handler_path


def test_google_drive_product_truth_is_partial_owner_run_service_account() -> None:
    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Vie bot ukladat faktury na Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.PARTIAL
    assert result.capability.runtime_owner is not None
    assert result.capability.requires_external_credentials is True
    assert answer is not None
    assert '\u010diasto\u010dn\u00e9' in answer
    assert 'owner OAuth' in answer
