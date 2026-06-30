from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from bot.services.archive_worker import (
    ArchiveUploadNotConfiguredError,
    ArchiveUploadPermanentError,
    ArchiveUploadProvider,
    ArchiveUploadResult,
    ArchiveUploadTransientError,
)


_GOOGLE_DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"
_GOOGLE_DRIVE_SCOPES = ("https://www.googleapis.com/auth/drive.file",)
_DOCUMENT_TYPE_TO_DRIVE_FOLDER = {
    "receipt": "blocky",
    "incoming_invoice": "prijate_faktury",
    "invoice_pdf": "faktury",
}


@dataclass(frozen=True)
class GoogleDriveServiceAccountClientConfig:
    service_account_json_path: Path | None
    root_folder_id: str | None
    root_folder_name: str = "FakturaBot"

    @property
    def is_configured(self) -> bool:
        return bool(self.service_account_json_path and self.root_folder_id)


class GoogleDriveServiceAccountArchiveProvider(ArchiveUploadProvider):
    """Google Drive archive provider for the owner-run service-account MVP."""

    def __init__(
        self,
        config: GoogleDriveServiceAccountClientConfig,
        *,
        drive_service: Any | None = None,
        media_file_upload_factory: Any | None = None,
    ) -> None:
        self._config = config
        self._drive_service = drive_service
        self._media_file_upload_factory = media_file_upload_factory

    def __repr__(self) -> str:
        return (
            "GoogleDriveServiceAccountArchiveProvider("
            f"mode='service_account', configured={self._config.is_configured})"
        )

    def upload_file(
        self,
        *,
        local_file_path: Path,
        target_folder_path: str | None,
        document_type: str,
        metadata: Mapping[str, Any],
    ) -> ArchiveUploadResult:
        self._require_configured()
        if not local_file_path.is_file():
            raise ArchiveUploadPermanentError("local_file_missing")

        folder_parts = _drive_folder_parts(
            local_file_path=local_file_path,
            target_folder_path=target_folder_path,
            document_type=document_type,
            root_folder_name=self._config.root_folder_name,
        )
        try:
            service = self._get_drive_service()
            folder_id = self._ensure_folder_path(service, folder_parts)
            file_id = self._upload_to_folder(
                service,
                local_file_path=local_file_path,
                folder_id=folder_id,
            )
        except ArchiveUploadPermanentError:
            raise
        except ArchiveUploadNotConfiguredError:
            raise
        except Exception as exc:
            raise ArchiveUploadTransientError("google_drive_upload_failed") from exc

        return ArchiveUploadResult(drive_file_id=file_id, drive_folder_id=folder_id)

    def _require_configured(self) -> None:
        if not self._config.is_configured:
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured")
        json_path = self._config.service_account_json_path
        if json_path is None or not json_path.is_file():
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured")
        if not str(self._config.root_folder_id or "").strip():
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured")

    def _get_drive_service(self) -> Any:
        if self._drive_service is not None:
            return self._drive_service
        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ArchiveUploadNotConfiguredError("google_drive_dependency_missing") from exc

        credentials = service_account.Credentials.from_service_account_file(
            str(self._config.service_account_json_path),
            scopes=list(_GOOGLE_DRIVE_SCOPES),
        )
        self._drive_service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return self._drive_service

    def _media_file_upload(self, local_file_path: Path) -> Any:
        if self._media_file_upload_factory is not None:
            return self._media_file_upload_factory(str(local_file_path), resumable=False)
        try:
            from googleapiclient.http import MediaFileUpload
        except ImportError as exc:
            raise ArchiveUploadNotConfiguredError("google_drive_dependency_missing") from exc
        return MediaFileUpload(str(local_file_path), resumable=False)

    def _ensure_folder_path(self, service: Any, folder_parts: tuple[str, ...]) -> str:
        parent_id = str(self._config.root_folder_id or "").strip()
        for folder_name in folder_parts:
            existing_id = self._find_child_folder(service, parent_id=parent_id, folder_name=folder_name)
            if existing_id:
                parent_id = existing_id
                continue
            parent_id = self._create_child_folder(service, parent_id=parent_id, folder_name=folder_name)
        return parent_id

    def _find_child_folder(self, service: Any, *, parent_id: str, folder_name: str) -> str | None:
        escaped_name = _escape_drive_query_value(folder_name)
        escaped_parent = _escape_drive_query_value(parent_id)
        query = (
            f"name = '{escaped_name}' and mimeType = '{_GOOGLE_DRIVE_FOLDER_MIME_TYPE}' "
            f"and '{escaped_parent}' in parents and trashed = false"
        )
        response = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id,name)",
            pageSize=10,
        ).execute()
        files = response.get("files", []) if isinstance(response, dict) else []
        if not files:
            return None
        first = files[0]
        folder_id = str(first.get("id", "")).strip() if isinstance(first, dict) else ""
        return folder_id or None

    def _create_child_folder(self, service: Any, *, parent_id: str, folder_name: str) -> str:
        response = service.files().create(
            body={
                "name": folder_name,
                "mimeType": _GOOGLE_DRIVE_FOLDER_MIME_TYPE,
                "parents": [parent_id],
            },
            fields="id",
        ).execute()
        folder_id = str(response.get("id", "")).strip() if isinstance(response, dict) else ""
        if not folder_id:
            raise ArchiveUploadTransientError("google_drive_folder_create_failed")
        return folder_id

    def _upload_to_folder(self, service: Any, *, local_file_path: Path, folder_id: str) -> str:
        response = service.files().create(
            body={"name": local_file_path.name, "parents": [folder_id]},
            media_body=self._media_file_upload(local_file_path),
            fields="id,webViewLink",
        ).execute()
        file_id = str(response.get("id", "")).strip() if isinstance(response, dict) else ""
        if not file_id:
            raise ArchiveUploadTransientError("google_drive_upload_empty_file_id")
        return file_id


def _drive_folder_parts(
    *,
    local_file_path: Path,
    target_folder_path: str | None,
    document_type: str,
    root_folder_name: str,
) -> tuple[str, ...]:
    if target_folder_path and target_folder_path.strip():
        parts = tuple(part for part in target_folder_path.replace("\\", "/").split("/") if part)
        if parts and parts[0] == root_folder_name:
            return parts[1:]
        return parts

    expected_drive_folder = _DOCUMENT_TYPE_TO_DRIVE_FOLDER.get(document_type)
    if expected_drive_folder is None:
        raise ArchiveUploadPermanentError("unsupported_document_type")

    path_parts = local_file_path.parts
    lower_parts = [part.lower() for part in path_parts]
    if document_type == "invoice_pdf":
        raise ArchiveUploadPermanentError("invoice_pdf_target_folder_required")
    try:
        years_index = lower_parts.index("years")
    except ValueError as exc:
        raise ArchiveUploadPermanentError("invalid_accounting_document_path") from exc
    if len(path_parts) <= years_index + 3:
        raise ArchiveUploadPermanentError("invalid_accounting_document_path")
    year = path_parts[years_index + 1]
    month = path_parts[years_index + 3]
    if not (year.isdigit() and len(year) == 4 and month.isdigit() and len(month) == 2):
        raise ArchiveUploadPermanentError("invalid_accounting_document_path")
    return (year, expected_drive_folder, f"{year}-{month}")


def _escape_drive_query_value(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
