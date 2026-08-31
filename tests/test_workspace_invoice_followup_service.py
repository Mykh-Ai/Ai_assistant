from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers.invoice_followup import (
    INVOICE_FOLLOWUP_DECISION_MARK_PAID,
    _callback_data,
    invoice_followup_callback,
)
from bot.services.access_control import AccessControlService
from bot.services.archive_job_service import ARCHIVE_JOB_RETRY_WAIT, ARCHIVE_JOB_UPLOADED
from bot.services.archive_worker import (
    ARCHIVE_ERROR_NOT_CONFIGURED,
    ArchiveUploadNotConfiguredError,
    ArchiveUploadResult,
    ArchiveWorker,
)
from bot.services.contact_service import ContactProfile
from bot.services.db import init_db
from bot.services.invoice_analytics_dataset import InvoiceAnalyticsDatasetService
from bot.services.invoice_followup_service import InvoiceFollowupService
from bot.services.invoice_followup_scheduler import send_due_invoice_followups_once
from bot.services.invoice_drive_archive_service import InvoiceDriveArchiveService
from bot.services.invoice_service import CreateInvoiceItemPayload
from bot.services.supplier_service import SupplierProfile
from bot.services.workspace_contact_service import WorkspaceContactService
from bot.services.workspace_context import WorkspaceContextService
from bot.services.workspace_invoice_analytics_dataset import (
    WorkspaceInvoiceAnalyticsDatasetService,
)
from bot.services.workspace_invoice_followup_service import (
    WorkspaceInvoiceFollowupSchemaRequired,
    WorkspaceInvoiceFollowupService,
)
from bot.services.workspace_invoice_service import WorkspaceInvoiceService
from bot.services.workspace_invoice_pdf_storage import (
    WorkspaceInvoicePdfStorageError,
    WorkspaceInvoicePdfStorageService,
)
from bot.services.workspace_profile_service import (
    CREATE_ADDITIONAL_WORKSPACE_PROFILE,
    CREATE_FIRST_WORKSPACE_PROFILE,
    WorkspaceProfileService,
)


USER_ID = 90902


class _DriveArchiveProvider:
    def __init__(self, *, configured: bool = True) -> None:
        self.configured = configured

    def upload_file(
        self,
        *,
        local_file_path: Path,
        target_folder_path: str | None,
        document_type: str,
        metadata: dict[str, object],
    ) -> ArchiveUploadResult:
        if not self.configured:
            raise ArchiveUploadNotConfiguredError('google_drive_not_configured')
        return ArchiveUploadResult(
            drive_file_id='workspace-drive-file',
            drive_folder_id='workspace-drive-folder',
        )


def _supplier(name: str) -> SupplierProfile:
    return SupplierProfile(
        telegram_id=USER_ID,
        name=name,
        ico='12345678',
        dic='1234567890',
        ic_dph=None,
        address='Address',
        iban='SK3112000000198742637541',
        swift='GIBASKBX',
        email='owner@example.test',
        smtp_host=None,
        smtp_user=None,
        smtp_pass=None,
        days_due=14,
    )


def _contact(workspace_id: str) -> ContactProfile:
    return ContactProfile(
        workspace_id=workspace_id,
        supplier_telegram_id=USER_ID,
        name='Shared Customer',
        ico='87654321',
        dic='0987654321',
        ic_dph=None,
        address='Customer',
        email='customer@example.test',
        contact_person=None,
        source_type='manual',
        source_note=None,
        contract_path=None,
    )


def _setup(db_path: Path):
    AccessControlService(db_path).approve_user(
        telegram_id=USER_ID, approved_by=999, role='owner'
    )
    profiles = WorkspaceProfileService(db_path)
    first = profiles.create_profile(
        actor_telegram_id=USER_ID,
        profile=_supplier('First'),
        mode=CREATE_FIRST_WORKSPACE_PROFILE,
        make_active=True,
        workspace_id='ws_first',
        storage_key='first',
    )
    second = profiles.create_profile(
        actor_telegram_id=USER_ID,
        profile=_supplier('Second'),
        mode=CREATE_ADDITIONAL_WORKSPACE_PROFILE,
        make_active=False,
        workspace_id='ws_second',
        storage_key='second',
    )
    contacts = WorkspaceContactService(db_path)
    first_contact = contacts.create_or_replace(first, _contact(first.workspace_id))
    second_contact = contacts.create_or_replace(second, _contact(second.workspace_id))
    invoices = WorkspaceInvoiceService(db_path)
    item = CreateInvoiceItemPayload(
        description_raw='Service',
        description_normalized='Service',
        item_description_raw=None,
        quantity=1,
        unit='ks',
        unit_price=100,
        total_price=100,
    )
    first_invoice = invoices.create_invoice_with_items(
        first,
        contact_id=int(first_contact.id),
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date='2026-06-15',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='created',
        items=[item],
        invoice_number='20260001',
    )
    second_invoice = invoices.create_invoice_with_items(
        second,
        contact_id=int(second_contact.id),
        issue_date='2026-06-01',
        delivery_date='2026-06-01',
        due_date='2026-06-15',
        due_days=14,
        total_amount=100,
        currency='EUR',
        status='created',
        items=[item],
        invoice_number='20260001',
    )
    return first, second, first_invoice, second_invoice


def test_due_lists_and_payment_state_are_workspace_isolated(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, second_invoice = _setup(db_path)
    service = WorkspaceInvoiceFollowupService(db_path)

    assert [row.invoice_id for row in service.list_due_invoices(
        first, today=date(2026, 7, 1), now=datetime(2026, 7, 1, 9)
    )] == [first_invoice.id]
    assert [row.invoice_id for row in service.list_due_invoices(
        second, today=date(2026, 7, 1), now=datetime(2026, 7, 1, 9)
    )] == [second_invoice.id]

    service.mark_paid(first, invoice_id=int(first_invoice.id), now='2026-07-01T10:00:00')
    assert service.list_due_invoices(
        first, today='2026-07-01', now='2026-07-01T11:00:00'
    ) == []
    assert len(service.list_due_invoices(
        second, today='2026-07-01', now='2026-07-01T11:00:00'
    )) == 1


def test_cross_workspace_followup_mutation_is_rejected(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, _second_invoice = _setup(db_path)
    service = WorkspaceInvoiceFollowupService(db_path)

    with pytest.raises(ValueError, match='invoice_not_found_for_workspace'):
        service.mark_paid(second, invoice_id=int(first_invoice.id))

    assert service.get_state(first, invoice_id=int(first_invoice.id)) is None


def test_background_due_scan_does_not_depend_on_active_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, _second_invoice = _setup(db_path)
    contexts = WorkspaceContextService(db_path)
    contexts.set_active_workspace(USER_ID, second.workspace_id)
    service = WorkspaceInvoiceFollowupService(db_path)

    assert service.list_workspace_ids_with_due_invoices(
        today='2026-07-01', now='2026-07-01T09:00:00'
    ) == ['ws_first', 'ws_second']

    service.mark_paid(first, invoice_id=int(first_invoice.id), now='2026-07-01T10:00:00')
    assert contexts.resolve_for_user(USER_ID).workspace_id == second.workspace_id
    assert service.list_workspace_ids_with_due_invoices(
        today='2026-07-01', now='2026-07-01T11:00:00'
    ) == ['ws_second']


def test_drive_status_update_preserves_snoozed_reminder(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, first_invoice, _second_invoice = _setup(db_path)
    service = WorkspaceInvoiceFollowupService(db_path)
    service.remind_later(
        first,
        invoice_id=int(first_invoice.id),
        remind_after='2026-07-05T09:00:00',
    )

    state = service.record_drive_archive_status(
        first,
        invoice_id=int(first_invoice.id),
        status='pending',
        note='queued',
    )

    assert state.reminder_status == 'snoozed'
    assert state.remind_after == '2026-07-05T09:00:00'
    assert state.drive_archive_status == 'pending'


def test_analytics_dataset_is_scoped_to_workspace(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, second_invoice = _setup(db_path)
    followup = WorkspaceInvoiceFollowupService(db_path)
    followup.mark_paid(first, invoice_id=int(first_invoice.id), now='2026-07-01T10:00:00')
    analytics = WorkspaceInvoiceAnalyticsDatasetService(db_path)

    first_df = analytics.build_invoice_dataframe(first, current_date=date(2026, 7, 1))
    second_df = analytics.build_invoice_dataframe(second, current_date=date(2026, 7, 1))

    assert first_df['invoice_id'].tolist() == [first_invoice.id]
    assert second_df['invoice_id'].tolist() == [second_invoice.id]
    assert first_df.iloc[0]['payment_status_canonical'] == 'paid'
    assert second_df.iloc[0]['payment_status_canonical'] == 'overdue'


def test_pdf_paths_use_storage_key_and_reject_cross_workspace_write(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, _second_invoice = _setup(db_path)
    storage = WorkspaceInvoicePdfStorageService(db_path, tmp_path / 'storage')
    first_path = storage.target_path(first, invoice_number=first_invoice.invoice_number)
    second_path = storage.target_path(second, invoice_number=first_invoice.invoice_number)

    assert first_path == tmp_path / 'storage' / 'invoices' / 'first' / '20260001.pdf'
    assert second_path == tmp_path / 'storage' / 'invoices' / 'second' / '20260001.pdf'
    assert first_path != second_path

    with pytest.raises(
        WorkspaceInvoicePdfStorageError, match='invoice_not_found_for_workspace'
    ):
        storage.persist_path(
            second,
            invoice_id=int(first_invoice.id),
            pdf_path=second_path,
        )


def test_existing_persisted_pdf_path_is_preserved(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, first_invoice, _second_invoice = _setup(db_path)
    legacy_path = tmp_path / 'legacy' / '20260001.pdf'
    from bot.services.db import managed_connection

    with managed_connection(db_path) as connection:
        connection.execute(
            'UPDATE invoice SET pdf_path = ? WHERE id = ?',
            (str(legacy_path), first_invoice.id),
        )
        connection.commit()
    reloaded = WorkspaceInvoiceService(db_path).get_by_id(first, int(first_invoice.id))
    assert reloaded is not None

    storage = WorkspaceInvoicePdfStorageService(db_path, tmp_path / 'storage')
    assert storage.resolve_path(first, reloaded) == legacy_path

def test_legacy_invoice_readers_exclude_workspace_rows(tmp_path: Path) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    _setup(db_path)

    assert InvoiceFollowupService(db_path).list_due_invoices_for_supplier(
        supplier_telegram_id=USER_ID,
        today='2026-07-01',
        now='2026-07-01T09:00:00',
    ) == []
    dataframe = InvoiceAnalyticsDatasetService(
        db_path
    ).build_invoice_dataframe_for_supplier(
        supplier_telegram_id=USER_ID,
        current_date=date(2026, 7, 1),
    )
    assert dataframe.empty

class _DummyUser:
    def __init__(self, user_id: int) -> None:
        self.id = user_id


class _DummyMessage:
    def __init__(self) -> None:
        self.answers: list[str] = []
        self.cleared = False

    async def answer(self, text: str, **_kwargs) -> None:
        self.answers.append(text)

    async def edit_reply_markup(self, **_kwargs) -> None:
        self.cleared = True


class _DummyCallback:
    def __init__(self, data: str) -> None:
        self.data = data
        self.from_user = _DummyUser(USER_ID)
        self.message = _DummyMessage()
        self.answers: list[tuple[str | None, bool | None]] = []

    async def answer(
        self,
        text: str | None = None,
        show_alert: bool | None = None,
        **_kwargs,
    ) -> None:
        self.answers.append((text, show_alert))


class _DummyBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str, object | None]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> None:
        self.sent_messages.append((chat_id, text, kwargs.get('reply_markup')))


def _config(db_path: Path, storage_dir: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key='key',
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=db_path,
        storage_dir=storage_dir,
        allowed_telegram_user_ids=frozenset({USER_ID}),
        admin_telegram_user_ids=frozenset(),
        invoice_followup_check_interval_seconds=60,
        invoice_followup_notification_cooldown_hours=24,
    )


def test_workspace_callback_uses_invoice_workspace_not_active_selection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, _second_invoice = _setup(db_path)
    WorkspaceContextService(db_path).set_active_workspace(USER_ID, second.workspace_id)
    callback = _DummyCallback(
        _callback_data(INVOICE_FOLLOWUP_DECISION_MARK_PAID, int(first_invoice.id))
    )

    asyncio.run(invoice_followup_callback(callback, _config(db_path, tmp_path)))

    state = WorkspaceInvoiceFollowupService(db_path).get_state(
        first,
        invoice_id=int(first_invoice.id),
    )
    assert state is not None
    assert state.payment_status == 'paid'
    assert state.drive_archive_status == 'stub_requested_after_paid'
    assert WorkspaceContextService(db_path).resolve_for_user(
        USER_ID
    ).workspace_id == second.workspace_id
    assert callback.message.cleared is True


def test_scheduler_sends_each_workspace_without_using_active_selection(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, second, first_invoice, second_invoice = _setup(db_path)
    WorkspaceContextService(db_path).set_active_workspace(USER_ID, second.workspace_id)
    bot = _DummyBot()

    result = asyncio.run(
        send_due_invoice_followups_once(
            bot=bot,
            config=_config(db_path, tmp_path),
            now=datetime(2026, 7, 1, 9),
        )
    )

    assert result.eligible_suppliers == 1
    assert result.notified_suppliers == 1
    assert result.reminders_sent == 2
    assert len(bot.sent_messages) == 2
    assert any('Profil: First' in message[1] for message in bot.sent_messages)
    assert any('Profil: Second' in message[1] for message in bot.sent_messages)
    service = WorkspaceInvoiceFollowupService(db_path)
    assert service.get_state(first, invoice_id=int(first_invoice.id)) is not None
    assert service.get_state(second, invoice_id=int(second_invoice.id)) is not None

def test_scheduler_keeps_legacy_path_when_workspace_schema_is_not_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)

    def _raise_schema_required(*_args, **_kwargs):
        raise WorkspaceInvoiceFollowupSchemaRequired(
            'workspace_invoice_schema_migration_required'
        )

    monkeypatch.setattr(
        WorkspaceInvoiceFollowupService,
        'list_workspace_ids_with_due_invoices',
        _raise_schema_required,
    )
    result = asyncio.run(
        send_due_invoice_followups_once(
            bot=_DummyBot(),
            config=_config(db_path, tmp_path),
            now=datetime(2026, 7, 1, 9),
        )
    )
    assert result.reminders_sent == 0

def test_workspace_drive_enqueue_uses_storage_key_and_real_workspace_id(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, first_invoice, _second_invoice = _setup(db_path)
    storage = WorkspaceInvoicePdfStorageService(db_path, tmp_path / 'storage')
    pdf_path = storage.target_path(first, invoice_number=first_invoice.invoice_number)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b'%PDF-1.4 test')
    storage.persist_path(
        first,
        invoice_id=int(first_invoice.id),
        pdf_path=pdf_path,
    )
    invoice = WorkspaceInvoiceService(db_path).get_by_id(first, int(first_invoice.id))
    assert invoice is not None
    config = replace(_config(db_path, tmp_path / 'storage'), google_drive_enabled=True)

    result = InvoiceDriveArchiveService(config).request_after_paid_for_workspace(
        first,
        invoice=invoice,
    )

    assert result.job is not None
    assert result.job.workspace_id == first.workspace_id
    assert result.job.telegram_id == USER_ID
    assert result.job.local_file_path == str(pdf_path)
    state = WorkspaceInvoiceFollowupService(db_path).get_state(
        first,
        invoice_id=int(first_invoice.id),
    )
    assert state is not None
    assert state.drive_archive_status == 'pending'


def test_workspace_invoice_archive_worker_records_uploaded_state(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, first_invoice, _second_invoice = _setup(db_path)
    storage = WorkspaceInvoicePdfStorageService(db_path, tmp_path / 'storage')
    pdf_path = storage.target_path(first, invoice_number=first_invoice.invoice_number)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b'%PDF-1.4 test')
    storage.persist_path(first, invoice_id=int(first_invoice.id), pdf_path=pdf_path)
    invoice = WorkspaceInvoiceService(db_path).get_by_id(first, int(first_invoice.id))
    assert invoice is not None
    config = replace(_config(db_path, tmp_path / 'storage'), google_drive_enabled=True)
    request = InvoiceDriveArchiveService(config).request_after_paid_for_workspace(
        first,
        invoice=invoice,
    )

    result = ArchiveWorker(db_path, _DriveArchiveProvider()).process_one()

    assert request.job is not None
    assert result.status == ARCHIVE_JOB_UPLOADED
    state = WorkspaceInvoiceFollowupService(db_path).get_state(
        first,
        invoice_id=int(first_invoice.id),
    )
    assert state is not None
    assert state.drive_archive_status == 'uploaded'
    assert pdf_path.exists()


def test_workspace_invoice_archive_worker_records_retry_wait_without_legacy_error(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'bot.db'
    init_db(db_path)
    first, _second, first_invoice, _second_invoice = _setup(db_path)
    storage = WorkspaceInvoicePdfStorageService(db_path, tmp_path / 'storage')
    pdf_path = storage.target_path(first, invoice_number=first_invoice.invoice_number)
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b'%PDF-1.4 test')
    storage.persist_path(first, invoice_id=int(first_invoice.id), pdf_path=pdf_path)
    invoice = WorkspaceInvoiceService(db_path).get_by_id(first, int(first_invoice.id))
    assert invoice is not None
    config = replace(_config(db_path, tmp_path / 'storage'), google_drive_enabled=True)
    request = InvoiceDriveArchiveService(config).request_after_paid_for_workspace(
        first,
        invoice=invoice,
    )

    result = ArchiveWorker(
        db_path,
        _DriveArchiveProvider(configured=False),
    ).process_one()

    assert request.job is not None
    assert result.status == ARCHIVE_JOB_RETRY_WAIT
    assert result.error_code == ARCHIVE_ERROR_NOT_CONFIGURED
    state = WorkspaceInvoiceFollowupService(db_path).get_state(
        first,
        invoice_id=int(first_invoice.id),
    )
    assert state is not None
    assert state.drive_archive_status == 'retry_wait'
    assert pdf_path.exists()
