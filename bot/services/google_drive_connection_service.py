from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from uuid import uuid4

from bot.services.db import ensure_google_drive_connection_schema, managed_connection
from bot.services.token_crypto import EncryptedToken, TokenCryptoProvider


GOOGLE_DRIVE_PROVIDER = 'google_drive'

GOOGLE_DRIVE_STATUS_CONNECTED = 'connected'
GOOGLE_DRIVE_STATUS_DISCONNECTED = 'disconnected'
GOOGLE_DRIVE_STATUS_REVOKED = 'revoked'
GOOGLE_DRIVE_STATUS_ERROR = 'error'
GOOGLE_DRIVE_STATUS_NEEDS_REAUTH = 'needs_reauth'

ALLOWED_GOOGLE_DRIVE_CONNECTION_STATUSES = (
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GOOGLE_DRIVE_STATUS_DISCONNECTED,
    GOOGLE_DRIVE_STATUS_REVOKED,
    GOOGLE_DRIVE_STATUS_ERROR,
    GOOGLE_DRIVE_STATUS_NEEDS_REAUTH,
)


class GoogleDriveConnectionServiceError(ValueError):
    pass


@dataclass(frozen=True)
class GoogleDriveConnectionRecord:
    connection_id: str
    workspace_id: str
    telegram_id: int
    provider: str
    status: str
    google_subject: str | None
    google_email: str | None
    scopes_granted: tuple[str, ...]
    token_key_id: str
    token_version: int
    root_folder_id: str | None
    root_folder_path: str | None
    last_error_code: str | None
    connected_at: str | None
    revoked_at: str | None
    created_at: str
    updated_at: str
    _token_ciphertext: bytes = field(default=b'', repr=False, compare=False)


@dataclass(frozen=True)
class GoogleDriveFolderCacheRecord:
    workspace_id: str
    provider: str
    folder_path: str
    folder_id: str
    parent_folder_id: str | None
    created_at: str
    updated_at: str


class GoogleDriveConnectionService:
    def __init__(self, db_path: Path, crypto_provider: TokenCryptoProvider) -> None:
        self._db_path = db_path
        self._crypto = crypto_provider

    def ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.commit()

    def create_or_update_connection(
        self,
        *,
        workspace_id: str,
        telegram_id: int,
        scopes_granted: str | list[str] | tuple[str, ...],
        token_plaintext: bytes | str,
        status: str = GOOGLE_DRIVE_STATUS_CONNECTED,
        google_subject: str | None = None,
        google_email: str | None = None,
        root_folder_id: str | None = None,
        root_folder_path: str | None = None,
        now: datetime | None = None,
    ) -> GoogleDriveConnectionRecord:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        _validate_telegram_id(telegram_id)
        status = _validate_status(status)
        scopes_text = _normalize_scopes(scopes_granted)
        google_subject = _optional_text(google_subject)
        google_email = _sanitize_email(google_email)
        root_folder_id = _optional_text(root_folder_id)
        root_folder_path = _optional_text(root_folder_path)
        encrypted = self._crypto.encrypt_token(token_plaintext)
        if not encrypted.ciphertext:
            raise GoogleDriveConnectionServiceError('token_ciphertext_required')
        token_key_id = _required_text(encrypted.key_id, 'token_key_id')
        if encrypted.version <= 0:
            raise GoogleDriveConnectionServiceError('token_version_must_be_positive')

        timestamp = _format_timestamp(now)
        connected_at = timestamp if status == GOOGLE_DRIVE_STATUS_CONNECTED else None
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            existing = self._get_connection_row(connection, workspace_id)
            if existing is None:
                connection_id = str(uuid4())
                connection.execute(
                    (
                        'INSERT INTO google_drive_connections '
                        '(connection_id, workspace_id, telegram_id, provider, status, google_subject, '
                        'google_email, scopes_granted, token_ciphertext, token_key_id, token_version, '
                        'root_folder_id, root_folder_path, last_error_code, connected_at, revoked_at, '
                        'created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, NULL, ?, ?)'
                    ),
                    (
                        connection_id,
                        workspace_id,
                        telegram_id,
                        GOOGLE_DRIVE_PROVIDER,
                        status,
                        google_subject,
                        google_email,
                        scopes_text,
                        encrypted.ciphertext,
                        token_key_id,
                        encrypted.version,
                        root_folder_id,
                        root_folder_path,
                        connected_at,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                connection.execute(
                    (
                        'UPDATE google_drive_connections SET telegram_id = ?, provider = ?, status = ?, '
                        'google_subject = ?, google_email = ?, scopes_granted = ?, token_ciphertext = ?, '
                        'token_key_id = ?, token_version = ?, root_folder_id = ?, root_folder_path = ?, '
                        'last_error_code = NULL, connected_at = ?, revoked_at = NULL, updated_at = ? '
                        'WHERE workspace_id = ?'
                    ),
                    (
                        telegram_id,
                        GOOGLE_DRIVE_PROVIDER,
                        status,
                        google_subject,
                        google_email,
                        scopes_text,
                        encrypted.ciphertext,
                        token_key_id,
                        encrypted.version,
                        root_folder_id,
                        root_folder_path,
                        connected_at or existing['connected_at'],
                        timestamp,
                        workspace_id,
                    ),
                )
            connection.commit()
            row = self._get_connection_row(connection, workspace_id)
            if row is None:
                raise GoogleDriveConnectionServiceError('connection_not_found_after_upsert')
            return _connection_from_row(row)

    def get_connection_for_workspace(self, *, workspace_id: str) -> GoogleDriveConnectionRecord | None:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_connection_row(connection, workspace_id)
        return _connection_from_row(row) if row is not None else None

    def decrypt_token_for_workspace(self, *, workspace_id: str) -> bytes:
        record = self.get_connection_for_workspace(workspace_id=workspace_id)
        if record is None:
            raise GoogleDriveConnectionServiceError('connection_not_found')
        return self._crypto.decrypt_token(
            EncryptedToken(
                ciphertext=record._token_ciphertext,
                key_id=record.token_key_id,
                version=record.token_version,
            )
        )

    def mark_needs_reauth(
        self,
        *,
        workspace_id: str,
        error_code: str,
        now: datetime | None = None,
    ) -> GoogleDriveConnectionRecord:
        return self._update_connection_status(
            workspace_id=workspace_id,
            status=GOOGLE_DRIVE_STATUS_NEEDS_REAUTH,
            last_error_code=error_code,
            revoked_at=None,
            now=now,
        )

    def mark_disconnected(
        self,
        *,
        workspace_id: str,
        now: datetime | None = None,
    ) -> GoogleDriveConnectionRecord:
        timestamp = _format_timestamp(now)
        return self._update_connection_status(
            workspace_id=workspace_id,
            status=GOOGLE_DRIVE_STATUS_DISCONNECTED,
            last_error_code=None,
            revoked_at=timestamp,
            now=now,
        )

    def update_folder_cache(
        self,
        *,
        workspace_id: str,
        folder_path: str,
        folder_id: str,
        parent_folder_id: str | None = None,
        provider: str = GOOGLE_DRIVE_PROVIDER,
        now: datetime | None = None,
    ) -> GoogleDriveFolderCacheRecord:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        provider = _validate_provider(provider)
        folder_path = _validate_folder_path(folder_path)
        folder_id = _required_text(folder_id, 'folder_id')
        parent_folder_id = _optional_text(parent_folder_id)
        timestamp = _format_timestamp(now)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            existing = self._get_folder_row(
                connection,
                workspace_id=workspace_id,
                provider=provider,
                folder_path=folder_path,
            )
            if existing is None:
                connection.execute(
                    (
                        'INSERT INTO google_drive_folder_cache '
                        '(workspace_id, provider, folder_path, folder_id, parent_folder_id, created_at, updated_at) '
                        'VALUES (?, ?, ?, ?, ?, ?, ?)'
                    ),
                    (
                        workspace_id,
                        provider,
                        folder_path,
                        folder_id,
                        parent_folder_id,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                connection.execute(
                    (
                        'UPDATE google_drive_folder_cache SET folder_id = ?, parent_folder_id = ?, '
                        'updated_at = ? WHERE workspace_id = ? AND provider = ? AND folder_path = ?'
                    ),
                    (
                        folder_id,
                        parent_folder_id,
                        timestamp,
                        workspace_id,
                        provider,
                        folder_path,
                    ),
                )
            connection.commit()
            row = self._get_folder_row(
                connection,
                workspace_id=workspace_id,
                provider=provider,
                folder_path=folder_path,
            )
            if row is None:
                raise GoogleDriveConnectionServiceError('folder_cache_not_found_after_upsert')
            return _folder_from_row(row)

    def get_cached_folder(
        self,
        *,
        workspace_id: str,
        folder_path: str,
        provider: str = GOOGLE_DRIVE_PROVIDER,
    ) -> GoogleDriveFolderCacheRecord | None:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        provider = _validate_provider(provider)
        folder_path = _validate_folder_path(folder_path)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_folder_row(
                connection,
                workspace_id=workspace_id,
                provider=provider,
                folder_path=folder_path,
            )
        return _folder_from_row(row) if row is not None else None

    def clear_folder_cache_for_workspace(
        self,
        *,
        workspace_id: str,
        provider: str = GOOGLE_DRIVE_PROVIDER,
    ) -> int:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        provider = _validate_provider(provider)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            cursor = connection.execute(
                'DELETE FROM google_drive_folder_cache WHERE workspace_id = ? AND provider = ?',
                (workspace_id, provider),
            )
            connection.commit()
            return int(cursor.rowcount)

    def _update_connection_status(
        self,
        *,
        workspace_id: str,
        status: str,
        last_error_code: str | None,
        revoked_at: str | None,
        now: datetime | None,
    ) -> GoogleDriveConnectionRecord:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        status = _validate_status(status)
        last_error_code = _optional_text(last_error_code)
        timestamp = _format_timestamp(now)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_connection_row(connection, workspace_id)
            if row is None:
                raise GoogleDriveConnectionServiceError('connection_not_found')
            connection.execute(
                (
                    'UPDATE google_drive_connections SET status = ?, last_error_code = ?, '
                    'revoked_at = ?, updated_at = ? WHERE workspace_id = ?'
                ),
                (status, last_error_code, revoked_at, timestamp, workspace_id),
            )
            connection.commit()
            updated = self._get_connection_row(connection, workspace_id)
            if updated is None:
                raise GoogleDriveConnectionServiceError('connection_not_found')
            return _connection_from_row(updated)

    def _get_connection_row(self, connection: sqlite3.Connection, workspace_id: str) -> sqlite3.Row | None:
        return connection.execute(
            'SELECT * FROM google_drive_connections WHERE workspace_id = ?',
            (workspace_id,),
        ).fetchone()

    def _get_folder_row(
        self,
        connection: sqlite3.Connection,
        *,
        workspace_id: str,
        provider: str,
        folder_path: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            (
                'SELECT * FROM google_drive_folder_cache '
                'WHERE workspace_id = ? AND provider = ? AND folder_path = ?'
            ),
            (workspace_id, provider, folder_path),
        ).fetchone()


def _connection_from_row(row: sqlite3.Row) -> GoogleDriveConnectionRecord:
    return GoogleDriveConnectionRecord(
        connection_id=row['connection_id'],
        workspace_id=row['workspace_id'],
        telegram_id=int(row['telegram_id']),
        provider=row['provider'],
        status=row['status'],
        google_subject=row['google_subject'],
        google_email=row['google_email'],
        scopes_granted=tuple(row['scopes_granted'].split()),
        token_key_id=row['token_key_id'],
        token_version=int(row['token_version']),
        root_folder_id=row['root_folder_id'],
        root_folder_path=row['root_folder_path'],
        last_error_code=row['last_error_code'],
        connected_at=row['connected_at'],
        revoked_at=row['revoked_at'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
        _token_ciphertext=bytes(row['token_ciphertext']),
    )


def _folder_from_row(row: sqlite3.Row) -> GoogleDriveFolderCacheRecord:
    return GoogleDriveFolderCacheRecord(
        workspace_id=row['workspace_id'],
        provider=row['provider'],
        folder_path=row['folder_path'],
        folder_id=row['folder_id'],
        parent_folder_id=row['parent_folder_id'],
        created_at=row['created_at'],
        updated_at=row['updated_at'],
    )


def _validate_status(status: str) -> str:
    status = _required_text(status, 'status')
    if status not in ALLOWED_GOOGLE_DRIVE_CONNECTION_STATUSES:
        raise GoogleDriveConnectionServiceError('unsupported_connection_status')
    return status


def _validate_provider(provider: str) -> str:
    provider = _required_text(provider, 'provider')
    if provider != GOOGLE_DRIVE_PROVIDER:
        raise GoogleDriveConnectionServiceError('unsupported_provider')
    return provider


def _normalize_scopes(scopes: str | list[str] | tuple[str, ...]) -> str:
    if isinstance(scopes, str):
        values = [scope for scope in scopes.split() if scope.strip()]
    else:
        values = [str(scope).strip() for scope in scopes if str(scope).strip()]
    if not values:
        raise GoogleDriveConnectionServiceError('scopes_granted_required')
    return ' '.join(dict.fromkeys(values))


def _sanitize_email(value: str | None) -> str | None:
    text = _optional_text(value)
    if text is None:
        return None
    if any(char in text for char in ('\r', '\n', '\t')):
        raise GoogleDriveConnectionServiceError('google_email_invalid')
    return text.lower()


def _validate_folder_path(folder_path: str) -> str:
    text = _required_text(folder_path, 'folder_path')
    parts = [part for part in text.replace('\\', '/').split('/') if part]
    if not parts or any(part == '..' for part in parts):
        raise GoogleDriveConnectionServiceError('folder_path_invalid')
    return '/'.join(parts)


def _validate_telegram_id(telegram_id: int) -> None:
    if telegram_id <= 0:
        raise GoogleDriveConnectionServiceError('telegram_id_required')


def _required_text(value: object, field_name: str) -> str:
    text = str(value).strip() if value is not None else ''
    if not text:
        raise GoogleDriveConnectionServiceError(f'{field_name}_required')
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _format_timestamp(value: datetime | None) -> str:
    return _utc_now(value).isoformat()


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
