from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import inspect
import sqlite3

import pytest

from bot.services import google_drive_connection_service
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_PROVIDER,
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GOOGLE_DRIVE_STATUS_DISCONNECTED,
    GOOGLE_DRIVE_STATUS_NEEDS_REAUTH,
    GoogleDriveConnectionService,
    GoogleDriveConnectionServiceError,
)
from bot.services.info_help import build_product_truth_guidance
from bot.services.product_truth import ProductTruthStatus, get_capability
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / 'google-drive-connections.db'


def _service(tmp_path: Path) -> GoogleDriveConnectionService:
    return GoogleDriveConnectionService(
        _db_path(tmp_path),
        DeterministicFakeTokenCryptoProvider(key_id='test-key'),
    )


def _create_connection(
    service: GoogleDriveConnectionService,
    *,
    workspace_id: str = 'telegram-111001',
    token_plaintext: str = 'refresh-token-secret',
):
    return service.create_or_update_connection(
        workspace_id=workspace_id,
        telegram_id=111001,
        scopes_granted=[
            'openid',
            'email',
            'profile',
            'https://www.googleapis.com/auth/drive.file',
        ],
        token_plaintext=token_plaintext,
        google_subject='google-subject-1',
        google_email='USER@Example.COM',
        root_folder_id='root-folder-id',
        root_folder_path='OfficeFlow Accounting Archive',
        now=datetime(2026, 5, 30, 12, 0, tzinfo=UTC),
    )


def test_google_drive_connection_schema_bootstrap_is_idempotent(tmp_path: Path) -> None:
    service = _service(tmp_path)

    service.ensure_schema()
    service.ensure_schema()

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert 'google_drive_connections' in tables
    assert 'google_drive_folder_cache' in tables


def test_create_connected_connection_stores_ciphertext_not_plaintext(tmp_path: Path) -> None:
    service = _service(tmp_path)

    record = _create_connection(service)

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        row = connection.execute(
            'SELECT token_ciphertext, token_key_id, token_version FROM google_drive_connections'
        ).fetchone()

    assert record.status == GOOGLE_DRIVE_STATUS_CONNECTED
    assert record.provider == GOOGLE_DRIVE_PROVIDER
    assert record.google_email == 'user@example.com'
    assert record.scopes_granted == (
        'openid',
        'email',
        'profile',
        'https://www.googleapis.com/auth/drive.file',
    )
    assert row[0] != b'refresh-token-secret'
    assert b'refresh-token-secret' not in row[0]
    assert row[1] == 'test-key'
    assert row[2] == 1


def test_get_connection_returns_metadata_and_decrypts_only_via_crypto(tmp_path: Path) -> None:
    service = _service(tmp_path)
    created = _create_connection(service)

    record = service.get_connection_for_workspace(workspace_id='telegram-111001')
    decrypted = service.decrypt_token_for_workspace(workspace_id='telegram-111001')

    assert record is not None
    assert record == created
    assert decrypted == b'refresh-token-secret'


def test_plaintext_token_never_appears_in_record_repr(tmp_path: Path) -> None:
    service = _service(tmp_path)

    record = _create_connection(service)

    assert 'refresh-token-secret' not in repr(record)
    assert 'terces-nekot-hserfer' not in repr(record)


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('workspace_id', ''),
        ('telegram_id', 0),
        ('scopes_granted', []),
        ('token_plaintext', ''),
    ],
)
def test_create_connection_rejects_missing_required_fields(
    tmp_path: Path,
    field: str,
    value: object,
) -> None:
    payload = {
        'workspace_id': 'telegram-111001',
        'telegram_id': 111001,
        'scopes_granted': ['openid'],
        'token_plaintext': 'refresh-token-secret',
    }
    payload[field] = value

    with pytest.raises((GoogleDriveConnectionServiceError, ValueError)):
        _service(tmp_path).create_or_update_connection(**payload)


def test_create_connection_rejects_invalid_status(tmp_path: Path) -> None:
    with pytest.raises(GoogleDriveConnectionServiceError, match='unsupported_connection_status'):
        _service(tmp_path).create_or_update_connection(
            workspace_id='telegram-111001',
            telegram_id=111001,
            scopes_granted=['openid'],
            token_plaintext='refresh-token-secret',
            status='uploaded',
        )


def test_mark_needs_reauth_updates_status_and_error_safely(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create_connection(service)
    now = datetime(2026, 5, 30, 13, 0, tzinfo=UTC)

    record = service.mark_needs_reauth(
        workspace_id='telegram-111001',
        error_code='drive_auth_revoked',
        now=now,
    )

    assert record.status == GOOGLE_DRIVE_STATUS_NEEDS_REAUTH
    assert record.last_error_code == 'drive_auth_revoked'
    assert record.updated_at == now.isoformat()
    assert 'refresh-token-secret' not in repr(record)


def test_mark_disconnected_updates_status_and_revoked_at(tmp_path: Path) -> None:
    service = _service(tmp_path)
    _create_connection(service)
    now = datetime(2026, 5, 30, 13, 0, tzinfo=UTC)

    record = service.mark_disconnected(workspace_id='telegram-111001', now=now)

    assert record.status == GOOGLE_DRIVE_STATUS_DISCONNECTED
    assert record.revoked_at == now.isoformat()
    assert record.last_error_code is None


def test_folder_cache_create_read_update_works(tmp_path: Path) -> None:
    service = _service(tmp_path)
    now = datetime(2026, 5, 30, 12, 0, tzinfo=UTC)

    created = service.update_folder_cache(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-a',
        parent_folder_id='parent-a',
        now=now,
    )
    updated = service.update_folder_cache(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-b',
        parent_folder_id='parent-b',
        now=datetime(2026, 5, 30, 13, 0, tzinfo=UTC),
    )
    read_back = service.get_cached_folder(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
    )

    assert created.folder_id == 'folder-a'
    assert updated.folder_id == 'folder-b'
    assert updated.parent_folder_id == 'parent-b'
    assert read_back == updated


def test_folder_cache_is_unique_per_workspace_provider_and_path(tmp_path: Path) -> None:
    service = _service(tmp_path)

    first = service.update_folder_cache(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-a',
    )
    other_workspace = service.update_folder_cache(
        workspace_id='telegram-222002',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-b',
    )

    with sqlite3.connect(_db_path(tmp_path)) as connection:
        count = connection.execute('SELECT COUNT(*) FROM google_drive_folder_cache').fetchone()[0]

    assert first.folder_id == 'folder-a'
    assert other_workspace.folder_id == 'folder-b'
    assert count == 2


def test_workspace_cannot_read_another_workspace_folder_cache(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.update_folder_cache(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-a',
    )

    assert service.get_cached_folder(
        workspace_id='telegram-222002',
        folder_path='OfficeFlow Accounting Archive/years/2026',
    ) is None


def test_clear_folder_cache_for_workspace_is_scoped(tmp_path: Path) -> None:
    service = _service(tmp_path)
    service.update_folder_cache(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-a',
    )
    service.update_folder_cache(
        workspace_id='telegram-222002',
        folder_path='OfficeFlow Accounting Archive/years/2026',
        folder_id='folder-b',
    )

    deleted_count = service.clear_folder_cache_for_workspace(workspace_id='telegram-111001')

    assert deleted_count == 1
    assert service.get_cached_folder(
        workspace_id='telegram-111001',
        folder_path='OfficeFlow Accounting Archive/years/2026',
    ) is None
    assert service.get_cached_folder(
        workspace_id='telegram-222002',
        folder_path='OfficeFlow Accounting Archive/years/2026',
    ) is not None


def test_google_drive_connection_service_has_no_google_or_network_imports() -> None:
    source = inspect.getsource(google_drive_connection_service)

    forbidden = ('googleapiclient', 'google.auth', 'requests', 'httpx', 'aiohttp', 'socket')

    assert not any(name in source for name in forbidden)


def test_google_drive_product_truth_stays_unsupported() -> None:
    result = get_capability('google_drive_invoice_storage')
    answer = build_product_truth_guidance(user_input_text='Vie bot ukladať faktúry na Google Drive?')

    assert result.capability is not None
    assert result.capability.status == ProductTruthStatus.UNSUPPORTED
    assert result.capability.runtime_owner is None
    assert answer is not None
    assert 'nepodporované' in answer
    assert 'nie je v aktuálnej verzii implementovaná' in answer
