from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import sqlite3

import pytest

from bot.config import Config, load_config
from bot.services.accounting_document_archive_service import AccountingDocumentArchiveService
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.db import init_db
from bot.services.archive_job_service import ARCHIVE_JOB_RETRY_WAIT, ARCHIVE_JOB_UPLOADED
from bot.services.archive_worker import (
    ARCHIVE_ERROR_NOT_CONFIGURED,
    ArchiveLocalRetentionPolicy,
    ArchiveUploadNotConfiguredError,
    ArchiveWorker,
)
from bot.services.google_drive_archive_scheduler import process_google_drive_archive_once
from bot.services.invoice_drive_archive_service import InvoiceDriveArchiveService
from bot.services.invoice_followup_service import (
    DRIVE_ARCHIVE_STATUS_UPLOADED,
    InvoiceFollowupService,
)
from bot.services.invoice_service import CreateInvoiceItemPayload, InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.google_drive_connection_service import GoogleDriveConnectionService
from bot.services.google_drive_oauth_callback_service import GoogleOAuthTokenBundle
from bot.services.google_drive_owner_oauth import (
    OWNER_GOOGLE_DRIVE_OAUTH_SCOPES,
    serialize_google_oauth_token_bundle,
)
from bot.services.google_drive_owner_oauth_client import (
    GoogleDriveOwnerOAuthArchiveProvider,
    GoogleDriveOwnerOAuthClientConfig,
    _google_auth_expiry,
)
from bot.services.google_drive_service_account_client import (
    GoogleDriveServiceAccountArchiveProvider,
    GoogleDriveServiceAccountClientConfig,
)
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


NOW = datetime(2026, 6, 30, 10, 0, tzinfo=UTC)
WORKSPACE_ID = "telegram-111001"
TELEGRAM_ID = 111001


class _Executable:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def execute(self) -> dict[str, object]:
        return self._payload


class _FakeDriveFiles:
    def __init__(self) -> None:
        self.created_folders: list[dict[str, object]] = []
        self.uploads: list[dict[str, object]] = []
        self.queries: list[str] = []
        self._folders: dict[tuple[str, str], str] = {}

    def list(self, **kwargs: object) -> _Executable:
        query = str(kwargs.get("q", ""))
        self.queries.append(query)
        for (parent_id, name), folder_id in self._folders.items():
            if f"name = '{name}'" in query and f"'{parent_id}' in parents" in query:
                return _Executable({"files": [{"id": folder_id, "name": name}]})
        return _Executable({"files": []})

    def create(self, **kwargs: object) -> _Executable:
        body = kwargs.get("body")
        assert isinstance(body, dict)
        if body.get("mimeType") == "application/vnd.google-apps.folder":
            folder_name = str(body["name"])
            parent_id = str(body["parents"][0])
            folder_id = f"folder-{len(self.created_folders) + 1}"
            self._folders[(parent_id, folder_name)] = folder_id
            self.created_folders.append(body)
            return _Executable({"id": folder_id})
        file_id = f"file-{len(self.uploads) + 1}"
        self.uploads.append(body)
        return _Executable({"id": file_id, "webViewLink": "https://drive.example/file"})


class _FakeDriveService:
    def __init__(self) -> None:
        self.files_resource = _FakeDriveFiles()

    def files(self) -> _FakeDriveFiles:
        return self.files_resource


def _db_path(tmp_path: Path) -> Path:
    return tmp_path / "drive-archive.db"


def _confirmed_paths(
    tmp_path: Path,
    *,
    document_id: str = "receipt-001",
    document_type: str = "receipt",
) -> tuple[Path, Path]:
    folder = "receipts" if document_type == "receipt" else "incoming_invoices"
    suffix = "jpg" if document_type == "receipt" else "pdf"
    base = tmp_path / "workspaces" / WORKSPACE_ID / "years" / "2026" / "expenses" / "06" / folder
    original = base / "originals" / f"{document_id}.{suffix}"
    metadata = base / "metadata" / f"{document_id}.json"
    original.parent.mkdir(parents=True, exist_ok=True)
    metadata.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"document")
    metadata.write_text("{}", encoding="utf-8")
    return original, metadata


def _enqueue(
    tmp_path: Path,
    *,
    db_path: Path | None = None,
    document_id: str = "receipt-001",
    document_type: str = "receipt",
):
    database = db_path or _db_path(tmp_path)
    original, metadata = _confirmed_paths(
        tmp_path,
        document_id=document_id,
        document_type=document_type,
    )
    result = AccountingDocumentArchiveService(database).enqueue_confirmed_document(
        workspace_id=WORKSPACE_ID,
        telegram_id=TELEGRAM_ID,
        document_id=document_id,
        document_type=document_type,
        local_file_path=original,
        metadata_path=metadata,
    )
    return database, result, original, metadata


def _job_error_code(db_path: Path, job_id: str) -> str | None:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT error_code FROM archive_jobs WHERE job_id = ?",
            (job_id,),
        ).fetchone()
    return row[0] if row else None


def _set_base_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_TOKEN", "123:test")
    monkeypatch.setenv("DB_PATH", str(tmp_path / "fakturabot.db"))
    monkeypatch.setenv("STORAGE_DIR", str(tmp_path / "storage"))
    for name in (
        "GOOGLE_DRIVE_ENABLED",
        "GOOGLE_DRIVE_MODE",
        "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_PATH",
        "GOOGLE_DRIVE_OWNER_WORKSPACE_ID",
        "GOOGLE_TOKEN_CRYPTO_SECRET",
        "GOOGLE_DRIVE_ROOT_FOLDER_ID",
        "GOOGLE_DRIVE_ROOT_FOLDER_NAME",
        "GOOGLE_DRIVE_DELETE_LOCAL_RECEIPT_ORIGINAL_AFTER_UPLOAD",
        "GOOGLE_DRIVE_DELETE_LOCAL_INCOMING_INVOICE_ORIGINAL_AFTER_UPLOAD",
        "GOOGLE_DRIVE_DELETE_LOCAL_INVOICE_PDF_AFTER_UPLOAD",
    ):
        monkeypatch.delenv(name, raising=False)


def test_google_drive_config_defaults_disabled(monkeypatch, tmp_path: Path) -> None:
    _set_base_env(monkeypatch, tmp_path)

    config = load_config()

    assert config.google_drive_enabled is False
    assert config.google_drive_mode == "owner_oauth"
    assert config.google_drive_service_account_json_path is None
    assert config.google_drive_owner_workspace_id == "owner"
    assert config.google_drive_root_folder_id is None
    assert config.google_drive_root_folder_name == "FakturaBot"
    assert config.google_drive_delete_local_receipt_original_after_upload is True
    assert config.google_drive_delete_local_incoming_invoice_original_after_upload is True
    assert config.google_drive_delete_local_invoice_pdf_after_upload is False


def test_google_drive_config_parses_owner_run_service_account_env(monkeypatch, tmp_path: Path) -> None:
    _set_base_env(monkeypatch, tmp_path)
    json_path = tmp_path / "service-account.json"
    monkeypatch.setenv("GOOGLE_DRIVE_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_DRIVE_MODE", "service_account")
    monkeypatch.setenv("GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON_PATH", str(json_path))
    monkeypatch.setenv("GOOGLE_DRIVE_ROOT_FOLDER_ID", "root-folder")
    monkeypatch.setenv("GOOGLE_DRIVE_ROOT_FOLDER_NAME", "OwnerArchive")
    monkeypatch.setenv("GOOGLE_DRIVE_DELETE_LOCAL_RECEIPT_ORIGINAL_AFTER_UPLOAD", "0")
    monkeypatch.setenv("GOOGLE_DRIVE_DELETE_LOCAL_INCOMING_INVOICE_ORIGINAL_AFTER_UPLOAD", "1")

    config = load_config()

    assert config.google_drive_enabled is True
    assert config.google_drive_mode == "service_account"
    assert config.google_drive_service_account_json_path == json_path.resolve()
    assert config.google_drive_root_folder_id == "root-folder"
    assert config.google_drive_root_folder_name == "OwnerArchive"
    assert config.google_drive_owner_workspace_id == "owner"
    assert config.google_drive_delete_local_receipt_original_after_upload is False
    assert config.google_drive_delete_local_incoming_invoice_original_after_upload is True


def test_disabled_mode_does_not_start_upload(monkeypatch, tmp_path: Path) -> None:
    _set_base_env(monkeypatch, tmp_path)
    config = load_config()
    db_path, record, _original, _metadata = _enqueue(tmp_path, db_path=config.db_path)
    fake_drive = _FakeDriveService()
    provider = GoogleDriveServiceAccountArchiveProvider(
        GoogleDriveServiceAccountClientConfig(
            service_account_json_path=tmp_path / "missing.json",
            root_folder_id="root-folder",
        ),
        drive_service=fake_drive,
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    result = process_google_drive_archive_once(config=config, provider=provider, now=NOW)

    assert result.status == "noop"
    assert fake_drive.files_resource.uploads == []
    assert _job_error_code(db_path, record.job.job_id) is None


def test_missing_service_account_config_sets_not_configured_and_keeps_original(monkeypatch, tmp_path: Path) -> None:
    _set_base_env(monkeypatch, tmp_path)
    monkeypatch.setenv("GOOGLE_DRIVE_ENABLED", "1")
    monkeypatch.setenv("GOOGLE_DRIVE_MODE", "service_account")
    config = load_config()
    db_path, record, original, metadata = _enqueue(tmp_path, db_path=config.db_path)

    result = process_google_drive_archive_once(config=config, now=NOW)

    assert result.status == ARCHIVE_JOB_RETRY_WAIT
    assert result.error_code == ARCHIVE_ERROR_NOT_CONFIGURED
    assert _job_error_code(db_path, record.job.job_id) == ARCHIVE_ERROR_NOT_CONFIGURED
    assert original.exists()
    assert metadata.exists()


def test_service_account_provider_creates_stable_folder_path_and_uploads_file(tmp_path: Path) -> None:
    json_path = tmp_path / "service-account.json"
    json_path.write_text("{}", encoding="utf-8")
    original, _metadata = _confirmed_paths(tmp_path)
    fake_drive = _FakeDriveService()
    provider = GoogleDriveServiceAccountArchiveProvider(
        GoogleDriveServiceAccountClientConfig(
            service_account_json_path=json_path,
            root_folder_id="root-folder",
            root_folder_name="FakturaBot",
        ),
        drive_service=fake_drive,
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    result = provider.upload_file(
        local_file_path=original,
        target_folder_path=None,
        document_type="receipt",
        metadata={"document_id": "receipt-001"},
    )

    assert result.drive_file_id == "file-1"
    assert result.drive_folder_id == "folder-3"
    assert [folder["name"] for folder in fake_drive.files_resource.created_folders] == [
        "2026",
        "blocky",
        "2026-06",
    ]
    assert fake_drive.files_resource.uploads == [
        {"name": original.name, "parents": ["folder-3"]}
    ]


def test_worker_deletes_original_only_after_uploaded_state_and_keeps_metadata(tmp_path: Path) -> None:
    db_path, record, original, metadata = _enqueue(tmp_path)
    json_path = tmp_path / "service-account.json"
    json_path.write_text("{}", encoding="utf-8")
    provider = GoogleDriveServiceAccountArchiveProvider(
        GoogleDriveServiceAccountClientConfig(
            service_account_json_path=json_path,
            root_folder_id="root-folder",
        ),
        drive_service=_FakeDriveService(),
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    result = ArchiveWorker(
        db_path,
        provider,
        retention_policy=ArchiveLocalRetentionPolicy(delete_receipt_original_after_upload=True),
    ).process_one(now=NOW)

    assert result.status == ARCHIVE_JOB_UPLOADED
    state = AccountingDocumentArchiveService(db_path).get_state(
        workspace_id=WORKSPACE_ID,
        document_id=record.job.document_id,
    )
    assert state is not None
    assert state.archive_status == ARCHIVE_JOB_UPLOADED
    assert state.drive_file_id == "file-1"
    assert not original.exists()
    assert metadata.exists()


def test_invoice_pdf_retention_policy_is_always_keep() -> None:
    policy = ArchiveLocalRetentionPolicy(
        delete_receipt_original_after_upload=True,
        delete_incoming_invoice_original_after_upload=True,
    )

    assert policy.should_delete_original("invoice_pdf") is False

def _config_object(tmp_path: Path, *, google_drive_enabled: bool = True) -> Config:
    return Config(
        bot_token="token",
        openai_api_key=None,
        openai_stt_model="whisper-1",
        openai_llm_model="gpt-4o",
        debug_invoice_transparency=False,
        db_path=tmp_path / "invoice-drive.db",
        storage_dir=tmp_path,
        google_drive_enabled=google_drive_enabled,
        google_drive_mode="owner_oauth",
        google_drive_service_account_json_path=tmp_path / "service-account.json",
        google_drive_root_folder_id="root-folder",
    )


def _setup_invoice_with_pdf(config: Config) -> tuple[int, Path]:
    init_db(config.db_path)
    SupplierService(config.db_path).create_or_replace(
        SupplierProfile(
            telegram_id=TELEGRAM_ID,
            name="Dodavatel",
            ico="12345678",
            dic="1234567890",
            ic_dph=None,
            address="Hlavna 1, Bratislava",
            iban="SK3112000000198742637541",
            swift="TATRSKBX",
            email="supplier@example.com",
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=14,
        )
    )
    ContactService(config.db_path).create_or_replace(
        ContactProfile(
            supplier_telegram_id=TELEGRAM_ID,
            name="Odberatel",
            ico="87654321",
            dic="0987654321",
            ic_dph=None,
            address="Dlha 2, Kosice",
            email="customer@example.com",
            contact_person=None,
            source_type="manual",
            source_note=None,
            contract_path=None,
        )
    )
    contact = ContactService(config.db_path).get_by_name(TELEGRAM_ID, "Odberatel")
    assert contact is not None and contact.id is not None
    invoice_id = InvoiceService(config.db_path).create_invoice_with_items(
        supplier_telegram_id=TELEGRAM_ID,
        contact_id=contact.id,
        issue_date="2026-06-01",
        delivery_date="2026-06-01",
        due_date="2026-06-15",
        due_days=14,
        total_amount=120.0,
        currency="EUR",
        status="pripravena",
        invoice_number="20260006",
        items=[
            CreateInvoiceItemPayload(
                description_raw="servis",
                description_normalized="Servis",
                item_description_raw=None,
                quantity=1,
                unit="ks",
                unit_price=120.0,
                total_price=120.0,
            )
        ],
    )
    pdf_path = config.storage_dir / "invoices" / str(TELEGRAM_ID) / "20260006.pdf"
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    pdf_path.write_bytes(b"%PDF")
    InvoiceService(config.db_path).save_pdf_path(invoice_id, str(pdf_path))
    InvoiceFollowupService(config.db_path).mark_paid(
        invoice_id=invoice_id,
        supplier_telegram_id=TELEGRAM_ID,
        now=NOW,
    )
    return invoice_id, pdf_path


def test_paid_invoice_pdf_archive_upload_keeps_local_pdf_and_updates_followup_state(tmp_path: Path) -> None:
    config = _config_object(tmp_path)
    config.google_drive_service_account_json_path.write_text("{}", encoding="utf-8")
    invoice_id, pdf_path = _setup_invoice_with_pdf(config)
    invoice = InvoiceService(config.db_path).get_invoice_for_supplier_by_id(
        supplier_telegram_id=TELEGRAM_ID,
        invoice_id=invoice_id,
    )
    assert invoice is not None

    request_result = InvoiceDriveArchiveService(config).request_after_paid(invoice=invoice)
    provider = GoogleDriveServiceAccountArchiveProvider(
        GoogleDriveServiceAccountClientConfig(
            service_account_json_path=config.google_drive_service_account_json_path,
            root_folder_id="root-folder",
        ),
        drive_service=_FakeDriveService(),
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )
    worker_result = ArchiveWorker(config.db_path, provider).process_one(now=NOW)

    assert request_result.status == "pending"
    assert worker_result.status == ARCHIVE_JOB_UPLOADED
    state = InvoiceFollowupService(config.db_path).get_state(invoice_id=invoice_id)
    assert state is not None
    assert state.drive_archive_status == DRIVE_ARCHIVE_STATUS_UPLOADED
    assert pdf_path.exists()



def _store_owner_oauth_connection(
    db_path: Path,
    *,
    workspace_id: str = "owner",
    root_folder_id: str = "root-folder",
) -> DeterministicFakeTokenCryptoProvider:
    crypto = DeterministicFakeTokenCryptoProvider()
    token_bundle = GoogleOAuthTokenBundle(
        access_token="owner-access-token",
        refresh_token="owner-refresh-token",
        expires_at="2026-06-30T09:00:00+00:00",
        scope=OWNER_GOOGLE_DRIVE_OAUTH_SCOPES,
        token_type="Bearer",
        id_token=None,
        google_subject="owner-subject",
        google_email="owner@example.test",
    )
    GoogleDriveConnectionService(db_path, crypto).create_or_update_connection(
        workspace_id=workspace_id,
        telegram_id=TELEGRAM_ID,
        scopes_granted=token_bundle.scope,
        token_plaintext=serialize_google_oauth_token_bundle(token_bundle),
        google_subject=token_bundle.google_subject,
        google_email=token_bundle.google_email,
        root_folder_id=root_folder_id,
        root_folder_path="FakturaBot",
        now=NOW,
    )
    return crypto


def test_owner_oauth_provider_uses_encrypted_connection_and_uploads_file(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    crypto = _store_owner_oauth_connection(db_path)
    original, _metadata = _confirmed_paths(tmp_path)
    fake_drive = _FakeDriveService()
    provider = GoogleDriveOwnerOAuthArchiveProvider(
        GoogleDriveOwnerOAuthClientConfig(
            db_path=db_path,
            crypto_provider=crypto,
            owner_workspace_id="owner",
            client_id="client-id",
            client_secret="client-secret",
            root_folder_id=None,
        ),
        drive_service=fake_drive,
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    result = provider.upload_file(
        local_file_path=original,
        target_folder_path=None,
        document_type="receipt",
        metadata={"document_id": "receipt-001"},
    )

    assert result.drive_file_id == "file-1"
    assert result.drive_folder_id == "folder-3"
    assert [folder["name"] for folder in fake_drive.files_resource.created_folders] == [
        "2026",
        "blocky",
        "2026-06",
    ]
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT token_ciphertext, root_folder_id, google_email FROM google_drive_connections WHERE workspace_id = ?",
            ("owner",),
        ).fetchone()
    assert row is not None
    assert row[1] == "root-folder"
    assert row[2] == "owner@example.test"
    assert b"owner-refresh-token" not in bytes(row[0])
    assert "owner-refresh-token" not in repr(provider)


def test_owner_oauth_provider_without_connection_is_not_configured(tmp_path: Path) -> None:
    original, _metadata = _confirmed_paths(tmp_path)
    provider = GoogleDriveOwnerOAuthArchiveProvider(
        GoogleDriveOwnerOAuthClientConfig(
            db_path=_db_path(tmp_path),
            crypto_provider=DeterministicFakeTokenCryptoProvider(),
            owner_workspace_id="owner",
            client_id="client-id",
            client_secret="client-secret",
            root_folder_id="root-folder",
        ),
        drive_service=_FakeDriveService(),
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    with pytest.raises(ArchiveUploadNotConfiguredError):
        provider.upload_file(
            local_file_path=original,
            target_folder_path=None,
            document_type="receipt",
            metadata={"document_id": "receipt-001"},
        )


def test_owner_oauth_provider_without_client_secret_is_not_configured(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    crypto = _store_owner_oauth_connection(db_path)
    original, _metadata = _confirmed_paths(tmp_path)
    provider = GoogleDriveOwnerOAuthArchiveProvider(
        GoogleDriveOwnerOAuthClientConfig(
            db_path=db_path,
            crypto_provider=crypto,
            owner_workspace_id="owner",
            client_id="client-id",
            client_secret=None,
            root_folder_id="root-folder",
        ),
        drive_service=_FakeDriveService(),
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    with pytest.raises(ArchiveUploadNotConfiguredError):
        provider.upload_file(
            local_file_path=original,
            target_folder_path=None,
            document_type="receipt",
            metadata={"document_id": "receipt-001"},
        )


def test_owner_oauth_provider_without_folder_id_is_not_configured(tmp_path: Path) -> None:
    db_path = _db_path(tmp_path)
    crypto = _store_owner_oauth_connection(db_path, root_folder_id="")
    original, _metadata = _confirmed_paths(tmp_path)
    provider = GoogleDriveOwnerOAuthArchiveProvider(
        GoogleDriveOwnerOAuthClientConfig(
            db_path=db_path,
            crypto_provider=crypto,
            owner_workspace_id="owner",
            client_id="client-id",
            client_secret="client-secret",
            root_folder_id=None,
        ),
        drive_service=_FakeDriveService(),
        media_file_upload_factory=lambda *_args, **_kwargs: object(),
    )

    with pytest.raises(ArchiveUploadNotConfiguredError):
        provider.upload_file(
            local_file_path=original,
            target_folder_path=None,
            document_type="receipt",
            metadata={"document_id": "receipt-001"},
        )

def test_owner_oauth_google_auth_expiry_is_naive_utc() -> None:
    aware = datetime(2026, 6, 30, 9, 0, tzinfo=UTC)

    expiry = _google_auth_expiry(aware)

    assert expiry == datetime(2026, 6, 30, 9, 0)
    assert expiry.tzinfo is None


def test_owner_oauth_google_auth_expiry_keeps_naive_datetime() -> None:
    naive = datetime(2026, 6, 30, 9, 0)

    assert _google_auth_expiry(naive) is naive
    assert _google_auth_expiry(None) is None
