from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Protocol

from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
    GOOGLE_DRIVE_ERROR_SCOPE_MISSING,
    GOOGLE_DRIVE_ERROR_UNKNOWN,
    GOOGLE_DRIVE_STATUS_CONNECTED,
    GoogleDriveConnectionService,
    GoogleDriveConnectionServiceError,
)
from bot.services.google_drive_oauth_state_service import (
    DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES,
    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
    GOOGLE_DRIVE_OAUTH_ERROR_INVALID,
    GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    GOOGLE_DRIVE_OAUTH_ERROR_REUSED,
    GoogleDriveOAuthConsumedState,
    GoogleDriveOAuthStateService,
    GoogleDriveOAuthStateServiceError,
)
from bot.services.token_crypto import TokenCryptoProvider


GOOGLE_DRIVE_CALLBACK_ERROR_MISSING_CODE = 'drive_oauth_code_missing'

REQUIRED_GOOGLE_DRIVE_OAUTH_SCOPES = DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES

ALLOWED_GOOGLE_DRIVE_CALLBACK_ERROR_CODES = (
    GOOGLE_DRIVE_OAUTH_ERROR_INVALID,
    GOOGLE_DRIVE_OAUTH_ERROR_EXPIRED,
    GOOGLE_DRIVE_OAUTH_ERROR_REUSED,
    GOOGLE_DRIVE_OAUTH_ERROR_REJECTED,
    GOOGLE_DRIVE_CALLBACK_ERROR_MISSING_CODE,
    GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
    GOOGLE_DRIVE_ERROR_SCOPE_MISSING,
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GOOGLE_DRIVE_ERROR_UNKNOWN,
)


class GoogleOAuthTokenExchangeError(ValueError):
    def __init__(self, error_code: str = GOOGLE_DRIVE_ERROR_CONNECTION) -> None:
        super().__init__(_normalize_error_code(error_code))
        self.error_code = _normalize_error_code(error_code)


class GoogleOAuthInvalidGrantError(GoogleOAuthTokenExchangeError):
    def __init__(self) -> None:
        super().__init__(GOOGLE_DRIVE_ERROR_AUTH_REVOKED)


class GoogleOAuthProviderError(GoogleOAuthTokenExchangeError):
    def __init__(self) -> None:
        super().__init__(GOOGLE_DRIVE_ERROR_CONNECTION)


@dataclass(frozen=True)
class GoogleOAuthTokenBundle:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    expires_at: str | None = None
    scope: tuple[str, ...] = ()
    token_type: str = 'Bearer'
    id_token: str | None = field(default=None, repr=False)
    google_subject: str | None = None
    google_email: str | None = None


class GoogleOAuthTokenExchanger(Protocol):
    def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        scopes: tuple[str, ...],
    ) -> GoogleOAuthTokenBundle:
        """Exchange an OAuth auth code for token metadata."""


@dataclass(frozen=True)
class GoogleDriveOAuthCallbackResult:
    success: bool
    workspace_id: str | None = None
    telegram_id: int | None = None
    google_email: str | None = None
    error_code: str | None = None


class GoogleDriveOAuthCallbackService:
    def __init__(
        self,
        *,
        db_path: Path,
        crypto_provider: TokenCryptoProvider,
        token_exchanger: GoogleOAuthTokenExchanger,
        required_scopes: tuple[str, ...] = REQUIRED_GOOGLE_DRIVE_OAUTH_SCOPES,
    ) -> None:
        self._state_service = GoogleDriveOAuthStateService(db_path)
        self._connection_service = GoogleDriveConnectionService(db_path, crypto_provider)
        self._token_exchanger = token_exchanger
        self._required_scopes = tuple(required_scopes)

    def handle_callback(
        self,
        *,
        state_token: str,
        code: str,
        now: datetime | None = None,
    ) -> GoogleDriveOAuthCallbackResult:
        timestamp = _utc_now(now)
        code = _optional_text(code)
        if code is None:
            return self._reject_missing_code(state_token=state_token)

        try:
            consumed = self._state_service.consume_oauth_state(
                raw_state_token=state_token,
                now=timestamp,
            )
        except GoogleDriveOAuthStateServiceError as exc:
            return GoogleDriveOAuthCallbackResult(
                success=False,
                error_code=_normalize_error_code(str(exc)),
            )

        try:
            token_bundle = self._token_exchanger.exchange_code(
                code=code,
                redirect_uri=consumed.redirect_uri,
                scopes=consumed.scopes_requested,
            )
            self._validate_token_bundle(token_bundle)
            token_plaintext = _serialize_token_bundle(token_bundle)
            record = self._connection_service.create_or_update_connection(
                workspace_id=consumed.workspace_id,
                telegram_id=consumed.telegram_id,
                scopes_granted=token_bundle.scope,
                token_plaintext=token_plaintext,
                status=GOOGLE_DRIVE_STATUS_CONNECTED,
                google_subject=token_bundle.google_subject,
                google_email=token_bundle.google_email,
                now=timestamp,
            )
        except GoogleOAuthInvalidGrantError:
            self._mark_existing_connection_needs_reauth(consumed, GOOGLE_DRIVE_ERROR_AUTH_REVOKED, timestamp)
            return _failure_from_consumed(consumed, GOOGLE_DRIVE_ERROR_AUTH_REVOKED)
        except GoogleOAuthTokenExchangeError as exc:
            return _failure_from_consumed(consumed, exc.error_code)
        except GoogleDriveConnectionServiceError:
            return _failure_from_consumed(consumed, GOOGLE_DRIVE_ERROR_UNKNOWN)

        return GoogleDriveOAuthCallbackResult(
            success=True,
            workspace_id=record.workspace_id,
            telegram_id=record.telegram_id,
            google_email=record.google_email,
            error_code=None,
        )

    def _reject_missing_code(self, *, state_token: str) -> GoogleDriveOAuthCallbackResult:
        try:
            state = self._state_service.mark_oauth_state_rejected(
                raw_state_token=state_token,
                error_code=GOOGLE_DRIVE_CALLBACK_ERROR_MISSING_CODE,
            )
        except GoogleDriveOAuthStateServiceError as exc:
            return GoogleDriveOAuthCallbackResult(
                success=False,
                error_code=_normalize_error_code(str(exc)),
            )
        return GoogleDriveOAuthCallbackResult(
            success=False,
            workspace_id=state.workspace_id,
            telegram_id=state.telegram_id,
            error_code=GOOGLE_DRIVE_CALLBACK_ERROR_MISSING_CODE,
        )

    def _validate_token_bundle(self, token_bundle: GoogleOAuthTokenBundle) -> None:
        if _optional_text(token_bundle.refresh_token) is None:
            raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_NEEDS_REAUTH)
        granted_scopes = set(token_bundle.scope)
        if any(scope not in granted_scopes for scope in self._required_scopes):
            raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_SCOPE_MISSING)

    def _mark_existing_connection_needs_reauth(
        self,
        consumed: GoogleOAuthConsumedState,
        error_code: str,
        now: datetime,
    ) -> None:
        if self._connection_service.get_connection_for_workspace(workspace_id=consumed.workspace_id) is None:
            return
        self._connection_service.mark_needs_reauth(
            workspace_id=consumed.workspace_id,
            error_code=error_code,
            now=now,
        )


def _failure_from_consumed(
    consumed: GoogleOAuthConsumedState,
    error_code: str,
) -> GoogleDriveOAuthCallbackResult:
    return GoogleDriveOAuthCallbackResult(
        success=False,
        workspace_id=consumed.workspace_id,
        telegram_id=consumed.telegram_id,
        error_code=_normalize_error_code(error_code),
    )


def _serialize_token_bundle(token_bundle: GoogleOAuthTokenBundle) -> str:
    return json.dumps(
        {
            'access_token': token_bundle.access_token,
            'refresh_token': token_bundle.refresh_token,
            'expires_at': token_bundle.expires_at,
            'scope': list(token_bundle.scope),
            'token_type': token_bundle.token_type,
            'id_token': token_bundle.id_token,
        },
        sort_keys=True,
        separators=(',', ':'),
    )


def _normalize_error_code(error_code: str | None) -> str:
    text = _optional_text(error_code)
    if text in ALLOWED_GOOGLE_DRIVE_CALLBACK_ERROR_CODES:
        return text
    return GOOGLE_DRIVE_ERROR_UNKNOWN


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
