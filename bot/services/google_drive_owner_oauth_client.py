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
from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GoogleDriveConnectionService,
    GoogleDriveConnectionServiceError,
)
from bot.services.google_drive_owner_oauth import (
    GOOGLE_DRIVE_FULL_SCOPE,
    parse_stored_google_oauth_token_bundle,
)
from bot.services.google_drive_service_account_client import _drive_folder_parts, _escape_drive_query_value
from bot.services.google_oauth_token_exchanger import GOOGLE_OAUTH_TOKEN_ENDPOINT
from bot.services.token_crypto import TokenCryptoError, TokenCryptoProvider


_GOOGLE_DRIVE_FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


@dataclass(frozen=True)
class GoogleDriveOwnerOAuthClientConfig:
    db_path: Path
    crypto_provider: TokenCryptoProvider
    owner_workspace_id: str
    client_id: str | None
    client_secret: str | None
    root_folder_id: str | None
    root_folder_name: str = "FakturaBot"

    @property
    def is_configured(self) -> bool:
        return bool(
            self.owner_workspace_id
            and self.client_id
            and self.client_secret
        )


class GoogleDriveOwnerOAuthArchiveProvider(ArchiveUploadProvider):
    """Google Drive archive provider for a single owner OAuth connection."""

    def __init__(
        self,
        config: GoogleDriveOwnerOAuthClientConfig,
        *,
        drive_service: Any | None = None,
        media_file_upload_factory: Any | None = None,
    ) -> None:
        self._config = config
        self._connection_service = GoogleDriveConnectionService(
            config.db_path,
            config.crypto_provider,
        )
        self._drive_service = drive_service
        self._media_file_upload_factory = media_file_upload_factory

    def __repr__(self) -> str:
        return (
            "GoogleDriveOwnerOAuthArchiveProvider("
            f"mode='owner_oauth', configured={self._config.is_configured})"
        )

    def upload_file(
        self,
        *,
        local_file_path: Path,
        target_folder_path: str | None,
        document_type: str,
        metadata: Mapping[str, Any],
    ) -> ArchiveUploadResult:
        if not local_file_path.is_file():
            raise ArchiveUploadPermanentError("local_file_missing")
        try:
            root_folder_id = self._root_folder_id()
            folder_parts = _drive_folder_parts(
                local_file_path=local_file_path,
                target_folder_path=target_folder_path,
                document_type=document_type,
                root_folder_name=self._config.root_folder_name,
            )
            service = self._get_drive_service()
            folder_id = self._ensure_folder_path(service, root_folder_id, folder_parts)
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

    def _root_folder_id(self) -> str:
        self._require_configured()
        try:
            record = self._connection_service.get_connection_for_workspace(
                workspace_id=self._config.owner_workspace_id,
            )
        except GoogleDriveConnectionServiceError as exc:
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured") from exc
        if record is None or record.status != GOOGLE_DRIVE_STATUS_CONNECTED:
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured")
        root_folder_id = record.root_folder_id or self._config.root_folder_id
        if not str(root_folder_id or "").strip():
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured")
        return str(root_folder_id).strip()

    def _require_configured(self) -> None:
        if not self._config.is_configured:
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured")

    def _get_drive_service(self) -> Any:
        if self._drive_service is not None:
            return self._drive_service
        try:
            from google.auth.exceptions import RefreshError
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
        except ImportError as exc:
            raise ArchiveUploadNotConfiguredError("google_drive_dependency_missing") from exc

        try:
            token_plaintext = self._connection_service.decrypt_token_for_workspace(
                workspace_id=self._config.owner_workspace_id,
            )
            token_bundle = parse_stored_google_oauth_token_bundle(token_plaintext)
        except (GoogleDriveConnectionServiceError, TokenCryptoError) as exc:
            raise ArchiveUploadNotConfiguredError("google_drive_not_configured") from exc

        if GOOGLE_DRIVE_FULL_SCOPE not in set(token_bundle.scopes):
            raise ArchiveUploadNotConfiguredError("google_drive_scope_missing")

        credentials = Credentials(
            token=token_bundle.access_token,
            refresh_token=token_bundle.refresh_token,
            token_uri=GOOGLE_OAUTH_TOKEN_ENDPOINT,
            client_id=self._config.client_id,
            client_secret=self._config.client_secret,
            scopes=list(token_bundle.scopes),
        )
        credentials.expiry = token_bundle.expires_at
        try:
            if not credentials.valid:
                credentials.refresh(Request())
        except RefreshError as exc:
            try:
                self._connection_service.mark_needs_reauth(
                    workspace_id=self._config.owner_workspace_id,
                    error_code=GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
                )
            except GoogleDriveConnectionServiceError:
                pass
            raise ArchiveUploadNotConfiguredError("google_drive_needs_reauth") from exc
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

    def _ensure_folder_path(
        self,
        service: Any,
        root_folder_id: str,
        folder_parts: tuple[str, ...],
    ) -> str:
        parent_id = root_folder_id
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
