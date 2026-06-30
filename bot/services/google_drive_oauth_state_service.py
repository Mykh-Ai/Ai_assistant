from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlencode
from uuid import uuid4

from bot.services.db import ensure_google_drive_connection_schema, managed_connection


GOOGLE_DRIVE_OAUTH_AUTHORIZATION_URL = 'https://accounts.google.com/o/oauth2/v2/auth'

GOOGLE_DRIVE_OAUTH_STATUS_PENDING = 'pending'
GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED = 'consumed'
GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED = 'expired'
GOOGLE_DRIVE_OAUTH_STATUS_REJECTED = 'rejected'

ALLOWED_GOOGLE_DRIVE_OAUTH_STATE_STATUSES = (
    GOOGLE_DRIVE_OAUTH_STATUS_PENDING,
    GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED,
    GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED,
    GOOGLE_DRIVE_OAUTH_STATUS_REJECTED,
)

GOOGLE_DRIVE_OAUTH_ERROR_INVALID = 'drive_oauth_state_invalid'
GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED = 'drive_oauth_state_expired'
GOOGLE_DRIVE_OAUTH_ERROR_REUSED = 'drive_oauth_state_reused'
GOOGLE_DRIVE_OAUTH_ERROR_REJECTED = 'drive_oauth_state_rejected'
GOOGLE_DRIVE_OAUTH_ERROR_CODE_MISSING = 'drive_oauth_code_missing'
GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN = 'drive_unknown_error'

ALLOWED_GOOGLE_DRIVE_OAUTH_STATE_ERROR_CODES = (
    GOOGLE_DRIVE_OAUTH_ERROR_INVALID,
    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
    GOOGLE_DRIVE_OAUTH_ERROR_REUSED,
    GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    GOOGLE_DRIVE_OAUTH_ERROR_CODE_MISSING,
    GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN,
)

DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES = (
    'openid',
    'email',
    'profile',
    'https://www.googleapis.com/auth/drive',
)
DEFAULT_GOOGLE_DRIVE_OAUTH_TTL_MINUTES = 10


class GoogleDriveOAuthStateServiceError(ValueError):
    pass


@dataclass(frozen=True)
class GoogleDriveOAuthStateRecord:
    state_id: str
    workspace_id: str
    telegram_id: int
    scopes_requested: tuple[str, ...]
    redirect_uri: str
    status: str
    created_at: str
    expires_at: str
    consumed_at: str | None
    last_error_code: str | None
    _state_token_hash: str = field(repr=False, compare=False)


@dataclass(frozen=True)
class GoogleDriveOAuthStateCreateResult:
    record: GoogleDriveOAuthStateRecord
    raw_state_token: str = field(repr=False)


@dataclass(frozen=True)
class GoogleDriveOAuthConsumedState:
    state_id: str
    workspace_id: str
    telegram_id: int
    scopes_requested: tuple[str, ...]
    redirect_uri: str


class GoogleDriveOAuthStateService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.commit()

    def create_oauth_state(
        self,
        *,
        workspace_id: str,
        telegram_id: int,
        scopes: str | list[str] | tuple[str, ...] = DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
        redirect_uri: str,
        now: datetime | None = None,
        ttl_minutes: int = DEFAULT_GOOGLE_DRIVE_OAUTH_TTL_MINUTES,
    ) -> GoogleDriveOAuthStateCreateResult:
        workspace_id = _required_text(workspace_id, 'workspace_id')
        _validate_telegram_id(telegram_id)
        scopes_requested = _normalize_scopes(scopes)
        redirect_uri = _validate_redirect_uri(redirect_uri)
        if ttl_minutes <= 0:
            raise GoogleDriveOAuthStateServiceError('ttl_minutes_must_be_positive')

        created_at = _utc_now(now)
        expires_at = created_at + timedelta(minutes=ttl_minutes)
        raw_state_token = secrets.token_urlsafe(32)
        state_token_hash = _hash_state_token(raw_state_token)
        state_id = str(uuid4())

        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute(
                (
                    'INSERT INTO google_drive_oauth_states '
                    '(state_id, workspace_id, telegram_id, state_token_hash, scopes_requested, '
                    'redirect_uri, status, created_at, expires_at, consumed_at, last_error_code) '
                    'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)'
                ),
                (
                    state_id,
                    workspace_id,
                    telegram_id,
                    state_token_hash,
                    scopes_requested,
                    redirect_uri,
                    GOOGLE_DRIVE_OAUTH_STATUS_PENDING,
                    created_at.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()
            row = self._get_state_row_by_id(connection, state_id)
            if row is None:
                raise GoogleDriveOAuthStateServiceError('oauth_state_not_found_after_create')

        return GoogleDriveOAuthStateCreateResult(
            record=_state_record_from_row(row),
            raw_state_token=raw_state_token,
        )

    def build_authorization_url(
        self,
        *,
        client_id: str,
        redirect_uri: str,
        scopes: str | list[str] | tuple[str, ...],
        state_token: str,
        prompt_consent: bool = True,
        authorization_url: str = GOOGLE_DRIVE_OAUTH_AUTHORIZATION_URL,
    ) -> str:
        client_id = _required_text(client_id, 'client_id')
        redirect_uri = _validate_redirect_uri(redirect_uri)
        scopes_requested = _normalize_scopes(scopes)
        state_token = _required_text(state_token, 'state_token')
        authorization_url = _required_text(authorization_url, 'authorization_url')

        params = {
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'scope': scopes_requested,
            'state': state_token,
            'access_type': 'offline',
            'include_granted_scopes': 'true',
        }
        if prompt_consent:
            params['prompt'] = 'consent'
        return f'{authorization_url}?{urlencode(params)}'

    def consume_oauth_state(
        self,
        *,
        raw_state_token: str,
        now: datetime | None = None,
    ) -> GoogleDriveOAuthConsumedState:
        state_token_hash = _hash_state_token(_required_text(raw_state_token, 'state_token'))
        timestamp = _utc_now(now)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = self._get_state_row_by_hash(connection, state_token_hash)
            if row is None:
                connection.rollback()
                raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_INVALID)

            self._raise_if_not_consumable(connection, row, timestamp)
            consumed_at = timestamp.isoformat()
            cursor = connection.execute(
                (
                    'UPDATE google_drive_oauth_states '
                    'SET status = ?, consumed_at = ?, last_error_code = NULL '
                    'WHERE state_id = ? AND status = ?'
                ),
                (
                    GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED,
                    consumed_at,
                    row['state_id'],
                    GOOGLE_DRIVE_OAUTH_STATUS_PENDING,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_REUSED)
            connection.commit()
            updated = self._get_state_row_by_id(connection, row['state_id'])
            if updated is None:
                raise GoogleDriveOAuthStateServiceError('oauth_state_not_found_after_consume')
            return GoogleDriveOAuthConsumedState(
                state_id=updated['state_id'],
                workspace_id=updated['workspace_id'],
                telegram_id=int(updated['telegram_id']),
                scopes_requested=tuple(updated['scopes_requested'].split()),
                redirect_uri=updated['redirect_uri'],
            )

    def mark_oauth_state_rejected(
        self,
        *,
        raw_state_token: str,
        error_code: str = GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    ) -> GoogleDriveOAuthStateRecord:
        state_token_hash = _hash_state_token(_required_text(raw_state_token, 'state_token'))
        error_code = _normalize_error_code(error_code)
        with managed_connection(self._db_path) as connection:
            ensure_google_drive_connection_schema(connection)
            connection.row_factory = sqlite3.Row
            row = self._get_state_row_by_hash(connection, state_token_hash)
            if row is None:
                raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_INVALID)
            if row['status'] != GOOGLE_DRIVE_OAUTH_STATUS_PENDING:
                return _state_record_from_row(row)
            cursor = connection.execute(
                (
                    'UPDATE google_drive_oauth_states SET status = ?, last_error_code = ? '
                    'WHERE state_id = ? AND status = ?'
                ),
                (
                    GOOGLE_DRIVE_OAUTH_STATUS_REJECTED,
                    error_code,
                    row['state_id'],
                    GOOGLE_DRIVE_OAUTH_STATUS_PENDING,
                ),
            )
            connection.commit()
            if cursor.rowcount != 1:
                updated = self._get_state_row_by_id(connection, row['state_id'])
                if updated is None:
                    raise GoogleDriveOAuthStateServiceError('oauth_state_not_found_after_reject')
                return _state_record_from_row(updated)
            updated = self._get_state_row_by_id(connection, row['state_id'])
            if updated is None:
                raise GoogleDriveOAuthStateServiceError('oauth_state_not_found_after_reject')
            return _state_record_from_row(updated)

    def _raise_if_not_consumable(
        self,
        connection: sqlite3.Connection,
        row: sqlite3.Row,
        now: datetime,
    ) -> None:
        status = row['status']
        if status == GOOGLE_DRIVE_OAUTH_STATUS_CONSUMED:
            self._mark_error(connection, row['state_id'], GOOGLE_DRIVE_OAUTH_ERROR_REUSED)
            connection.commit()
            raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_REUSED)
        if status == GOOGLE_DRIVE_OAUTH_STATUS_REJECTED:
            self._mark_error(connection, row['state_id'], GOOGLE_DRIVE_OAUTH_ERROR_REJECTED)
            connection.commit()
            raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_REJECTED)
        if status == GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED or _parse_timestamp(row['expires_at']) <= now:
            connection.execute(
                (
                    'UPDATE google_drive_oauth_states SET status = ?, last_error_code = ? '
                    'WHERE state_id = ?'
                ),
                (
                    GOOGLE_DRIVE_OAUTH_STATUS_EXPIRED,
                    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
                    row['state_id'],
                ),
            )
            connection.commit()
            raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED)
        if status != GOOGLE_DRIVE_OAUTH_STATUS_PENDING:
            self._mark_error(connection, row['state_id'], GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN)
            connection.commit()
            raise GoogleDriveOAuthStateServiceError(GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN)

    def _mark_error(self, connection: sqlite3.Connection, state_id: str, error_code: str) -> None:
        connection.execute(
            'UPDATE google_drive_oauth_states SET last_error_code = ? WHERE state_id = ?',
            (_normalize_error_code(error_code), state_id),
        )

    def _get_state_row_by_id(
        self,
        connection: sqlite3.Connection,
        state_id: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            'SELECT * FROM google_drive_oauth_states WHERE state_id = ?',
            (state_id,),
        ).fetchone()

    def _get_state_row_by_hash(
        self,
        connection: sqlite3.Connection,
        state_token_hash: str,
    ) -> sqlite3.Row | None:
        return connection.execute(
            'SELECT * FROM google_drive_oauth_states WHERE state_token_hash = ?',
            (state_token_hash,),
        ).fetchone()


def _state_record_from_row(row: sqlite3.Row) -> GoogleDriveOAuthStateRecord:
    return GoogleDriveOAuthStateRecord(
        state_id=row['state_id'],
        workspace_id=row['workspace_id'],
        telegram_id=int(row['telegram_id']),
        scopes_requested=tuple(row['scopes_requested'].split()),
        redirect_uri=row['redirect_uri'],
        status=row['status'],
        created_at=row['created_at'],
        expires_at=row['expires_at'],
        consumed_at=row['consumed_at'],
        last_error_code=row['last_error_code'],
        _state_token_hash=row['state_token_hash'],
    )


def _normalize_scopes(scopes: str | list[str] | tuple[str, ...]) -> str:
    if isinstance(scopes, str):
        values = [scope for scope in scopes.split() if scope.strip()]
    else:
        values = [str(scope).strip() for scope in scopes if str(scope).strip()]
    if not values:
        raise GoogleDriveOAuthStateServiceError('scopes_required')
    return ' '.join(dict.fromkeys(values))


def _validate_redirect_uri(redirect_uri: str) -> str:
    text = _required_text(redirect_uri, 'redirect_uri')
    if not (
        text.startswith('https://')
        or text.startswith('http://localhost')
        or text.startswith('http://127.0.0.1')
    ):
        raise GoogleDriveOAuthStateServiceError('redirect_uri_invalid')
    return text


def _validate_telegram_id(telegram_id: int) -> None:
    if telegram_id <= 0:
        raise GoogleDriveOAuthStateServiceError('telegram_id_required')


def _normalize_error_code(error_code: str | None) -> str:
    text = _optional_text(error_code)
    if text in ALLOWED_GOOGLE_DRIVE_OAUTH_STATE_ERROR_CODES:
        return text
    return GOOGLE_DRIVE_OAUTH_ERROR_UNKNOWN


def _hash_state_token(raw_state_token: str) -> str:
    return hashlib.sha256(_required_text(raw_state_token, 'state_token').encode('utf-8')).hexdigest()


def _required_text(value: object, field_name: str) -> str:
    text = str(value).strip() if value is not None else ''
    if not text:
        raise GoogleDriveOAuthStateServiceError(f'{field_name}_required')
    return text


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
