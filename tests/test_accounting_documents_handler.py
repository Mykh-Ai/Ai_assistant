from __future__ import annotations

import asyncio
from datetime import UTC, datetime
import inspect
import json
import sqlite3
from pathlib import Path

import pytest

from bot.config import Config
from bot.handlers import routers
from bot.handlers import accounting_documents
from bot.handlers.accounting_documents import cmd_blocky, recent_accounting_documents_alias, router as accounting_documents_router
from bot.handlers.invoice import router as invoice_router
from bot.services.accounting_document_archive_service import AccountingDocumentArchiveService
from bot.services.archive_job_service import ARCHIVE_JOB_PENDING
from bot.services.accounting_document_storage import workspace_key_for_supplier


class _DummyMessage:
    def __init__(self, text: str = '/blocky') -> None:
        self.text = text
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class _DummyState:
    def __init__(self) -> None:
        self.cleared = False

    async def clear(self) -> None:
        self.cleared = True


def _config(tmp_path: Path) -> Config:
    return Config(
        bot_token='token',
        openai_api_key=None,
        openai_stt_model='whisper-1',
        openai_llm_model='gpt-4o',
        debug_invoice_transparency=False,
        db_path=tmp_path / 'fakturabot.db',
        storage_dir=tmp_path,
    )


def _write_metadata(
    storage_dir: Path,
    *,
    stem: str,
    document_type: str = 'receipt',
    folder: str = 'receipts',
    vendor_name: str | None = 'ASFINAG',
    issue_date: str | None = '2026-03-14',
    total_amount: str | None = '9.60',
    currency: str | None = 'EUR',
    purchase_subject: str | None = '1-dnova dialnicna znamka Rakusko - osobne vozidlo',
    upload_date: str = '2026-03-14',
) -> Path:
    metadata_dir = storage_dir / 'workspaces' / 'mykhailo-szco' / 'years' / '2026' / 'expenses' / '03' / folder / 'metadata'
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata_path = metadata_dir / f'{stem}.json'
    metadata_path.write_text(
        json.dumps(
            {
                'document_type': document_type,
                'source': {'upload_date': upload_date},
                'business': {
                    'vendor_name': vendor_name,
                    'issue_date': issue_date,
                    'total_amount': total_amount,
                    'currency': currency,
                    'purchase_subject': purchase_subject,
                },
                'storage': {'original_path': str(metadata_dir.parent / 'originals' / f'{stem}.jpg')},
            },
            ensure_ascii=False,
        ),
        encoding='utf-8',
    )
    return metadata_path


def _create_archive_state(
    storage_dir: Path,
    db_path: Path,
    *,
    stem: str,
    status: str,
    workspace_id: str = 'mykhailo-szco',
) -> None:
    metadata_path = storage_dir / 'workspaces' / workspace_id / 'years' / '2026' / 'expenses' / '03' / 'receipts' / 'metadata' / f'{stem}.json'
    original_path = metadata_path.parent.parent / 'originals' / f'{stem}.jpg'
    original_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(b'document')
    service = AccountingDocumentArchiveService(db_path)
    result = service.enqueue_confirmed_document(
        workspace_id=workspace_id,
        telegram_id=111001,
        document_id=stem,
        document_type='receipt',
        local_file_path=original_path,
        metadata_path=metadata_path,
    )
    if status == 'pending':
        return
    service.mark_uploading(result.job.job_id, now=datetime(2026, 5, 30, 10, 0, tzinfo=UTC))
    if status == 'uploading':
        return
    if status == 'uploaded':
        service.mark_uploaded(
            result.job.job_id,
            drive_file_id='fake-drive-file',
            drive_folder_id='fake-folder',
            uploaded_at=datetime(2026, 5, 30, 10, 1, tzinfo=UTC),
        )
        return
    if status == 'retry_wait':
        service.mark_retry_wait(
            result.job.job_id,
            error_code='upload_transient_failed',
            next_attempt_at=datetime(2026, 5, 30, 10, 15, tzinfo=UTC),
            now=datetime(2026, 5, 30, 10, 2, tzinfo=UTC),
        )
        return
    if status == 'failed':
        service.mark_failed(
            result.job.job_id,
            error_code='upload_permanent_failed',
            now=datetime(2026, 5, 30, 10, 2, tzinfo=UTC),
        )
        return
    if status == 'abandoned':
        service.mark_abandoned(
            result.job.job_id,
            error_code='manual_stop',
            now=datetime(2026, 5, 30, 10, 2, tzinfo=UTC),
        )
        return
    raise AssertionError(f'Unsupported test archive status: {status}')


def test_blocky_command_shows_last_5_documents(tmp_path: Path) -> None:
    for index in range(6):
        _write_metadata(
            tmp_path,
            stem=f'doc-{index}',
            vendor_name=f'Vendor {index}',
            issue_date=f'2026-03-{index + 1:02d}',
            upload_date=f'2026-03-{index + 1:02d}',
        )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    answer = message.answers[-1]
    assert answer.startswith('Posledné bločky a prijaté doklady:')
    assert 'Vendor 5' in answer
    assert 'Vendor 1' in answer
    assert 'Vendor 0' not in answer


def test_blocky_command_with_no_documents_shows_empty_response(tmp_path: Path) -> None:
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    assert message.answers[-1] == 'Zatiaľ nemáte uložené žiadne bločky ani prijaté doklady.'


def test_blocek_command_uses_recent_blocky_view(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    message = _DummyMessage('/blocek')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    assert 'ASFINAG' in message.answers[-1]


def test_blocky_output_maps_document_type_labels(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', document_type='receipt', folder='receipts', vendor_name='Receipt')
    _write_metadata(
        tmp_path,
        stem='invoice',
        document_type='incoming_invoice',
        folder='incoming_invoices',
        vendor_name='Invoice',
        upload_date='2026-03-15',
    )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    answer = message.answers[-1]
    assert 'Typ: bloček' in answer
    assert 'Typ: prijatá faktúra' in answer


def test_blocky_output_displays_missing_fields_as_nezistene(tmp_path: Path) -> None:
    _write_metadata(
        tmp_path,
        stem='missing',
        vendor_name=None,
        issue_date=None,
        total_amount=None,
        currency=None,
        purchase_subject=None,
    )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, _config(tmp_path)))

    assert '1. nezistené — nezistené — nezistené' in message.answers[-1]
    assert 'Predmet nákupu: nezistené' in message.answers[-1]


def test_blocky_output_shows_not_configured_without_archive_state(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    config = _config(tmp_path)
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, config))

    assert 'Archív: Google Drive archív zatiaľ nie je pripojený' in message.answers[-1]
    assert not config.db_path.exists()


def test_blocky_read_view_does_not_create_archive_job(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    config = _config(tmp_path)
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, config))

    assert 'ASFINAG' in message.answers[-1]
    assert not config.db_path.exists()


@pytest.mark.parametrize(
    ('archive_status', 'expected_label'),
    [
        ('pending', 'Archív: čaká na spracovanie'),
        ('uploading', 'Archív: spracúva sa'),
        ('uploaded', 'Archív: pripravené v archíve / nahraté podľa evidencie'),
        ('retry_wait', 'Archív: čaká na opakovanie'),
        ('failed', 'Archív: zlyhalo'),
        ('abandoned', 'Archív: zastavené'),
    ],
)
def test_blocky_output_displays_archive_statuses(
    tmp_path: Path,
    archive_status: str,
    expected_label: str,
) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    config = _config(tmp_path)
    _create_archive_state(tmp_path, config.db_path, stem='receipt', status=archive_status)
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, config))

    assert expected_label in message.answers[-1]


def test_blocky_unknown_archive_status_falls_back_to_not_configured(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    config = _config(tmp_path)
    _create_archive_state(tmp_path, config.db_path, stem='receipt', status=ARCHIVE_JOB_PENDING)
    with sqlite3.connect(config.db_path) as connection:
        connection.execute(
            (
                'UPDATE accounting_document_archive_state SET archive_status = ? '
                'WHERE workspace_id = ? AND document_id = ?'
            ),
            ('unexpected_status', 'mykhailo-szco', 'receipt'),
        )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, config))

    answer = message.answers[-1]
    assert 'Archív: Google Drive archív zatiaľ nie je pripojený' in answer
    assert 'unexpected_status' not in answer


def test_blocky_does_not_display_archive_state_from_another_workspace(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    config = _config(tmp_path)
    _create_archive_state(
        tmp_path,
        config.db_path,
        stem='receipt',
        status=ARCHIVE_JOB_PENDING,
        workspace_id=workspace_key_for_supplier(222002),
    )
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, config))

    answer = message.answers[-1]
    assert 'Archív: Google Drive archív zatiaľ nie je pripojený' in answer
    assert 'Archív: čaká na spracovanie' not in answer


def test_blocky_read_view_does_not_mutate_archive_state(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    config = _config(tmp_path)
    _create_archive_state(tmp_path, config.db_path, stem='receipt', status=ARCHIVE_JOB_PENDING)
    service = AccountingDocumentArchiveService(config.db_path)
    before = service.get_state(workspace_id='mykhailo-szco', document_id='receipt')
    message = _DummyMessage('/blocky')

    asyncio.run(cmd_blocky(message, config))

    after = service.get_state(workspace_id='mykhailo-szco', document_id='receipt')
    assert before == after


def test_blocky_read_view_does_not_import_worker_or_network_clients() -> None:
    source = inspect.getsource(accounting_documents)

    forbidden = [
        'ArchiveWorker',
        'archive_worker',
        'upload_file',
        'googleapiclient',
        'google.auth',
        'requests',
        'httpx',
        'aiohttp',
        'socket',
    ]
    assert all(token not in source for token in forbidden)


def test_blocky_deterministic_aliases_work(tmp_path: Path) -> None:
    _write_metadata(tmp_path, stem='receipt', vendor_name='ASFINAG')
    for alias in ('posledné bločky', 'покажи останні чеки', 'последние чеки'):
        message = _DummyMessage(alias)

        asyncio.run(recent_accounting_documents_alias(message, _config(tmp_path)))

        assert 'ASFINAG' in message.answers[-1]


def test_blocky_router_is_registered_before_invoice_router() -> None:
    assert routers.index(accounting_documents_router) < routers.index(invoice_router)


def test_blocky_command_clears_active_state(tmp_path: Path) -> None:
    message = _DummyMessage('/blocek')
    state = _DummyState()

    asyncio.run(cmd_blocky(message, _config(tmp_path), state))

    assert state.cleared is True
    assert message.answers[-1] == 'Zatiaľ nemáte uložené žiadne bločky ani prijaté doklady.'


def test_blocky_alias_filter_does_not_match_generic_invoice_text() -> None:
    alias_handler = accounting_documents_router.message.handlers[1]
    generic_message = _DummyMessage('vystav fakturu pre ACME za servis 100 eur')

    assert alias_handler.filters[0].callback(generic_message) is False
