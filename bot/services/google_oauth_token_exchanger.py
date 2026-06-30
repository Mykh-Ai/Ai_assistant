from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import base64
import json
from typing import Protocol
from urllib import error, parse, request

from bot.services.google_drive_connection_service import (
    GOOGLE_DRIVE_ERROR_AUTH_REVOKED,
    GOOGLE_DRIVE_ERROR_CONNECTION,
    GOOGLE_DRIVE_ERROR_NEEDS_REAUTH,
    GOOGLE_DRIVE_ERROR_SCOPE_MISSING,
    GOOGLE_DRIVE_ERROR_UNKNOWN,
)
from bot.services.google_drive_oauth_callback_service import (
    GoogleOAuthInvalidGrantError,
    GoogleOAuthProviderError,
    GoogleOAuthTokenBundle,
    GoogleOAuthTokenExchangeError,
)
from bot.services.google_drive_oauth_state_service import DEFAULT_GOOGLE_DRIVE_OAUTH_SCOPES


GOOGLE_OAUTH_TOKEN_ENDPOINT = 'https://oauth2.googleapis.com/token'
GOOGLE_DRIVE_FILE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
GOOGLE_DRIVE_FULL_SCOPE = 'https://www.googleapis.com/auth/drive'


class GoogleOAuthHTTPClient(Protocol):
    def post_form(
        self,
        *,
        url: str,
        data: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        """POST form data to an OAuth endpoint and return status/body bytes."""


@dataclass(frozen=True)
class UrllibGoogleOAuthHTTPClient:
    def post_form(
        self,
        *,
        url: str,
        data: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        encoded = parse.urlencode(data).encode('utf-8')
        oauth_request = request.Request(
            url,
            data=encoded,
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'Accept': 'application/json',
            },
            method='POST',
        )
        try:
            with request.urlopen(oauth_request, timeout=timeout_seconds) as response:
                return int(response.status), response.read()
        except error.HTTPError as exc:
            return int(exc.code), exc.read()


class GoogleOAuthTokenExchanger:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        http_client: GoogleOAuthHTTPClient | None = None,
        token_endpoint: str = GOOGLE_OAUTH_TOKEN_ENDPOINT,
        timeout_seconds: float = 10.0,
        required_scopes: tuple[str, ...] = (GOOGLE_DRIVE_FULL_SCOPE,),
        now: datetime | None = None,
    ) -> None:
        self._client_id = _required_text(client_id, 'client_id')
        self._client_secret = _required_text(client_secret, 'client_secret')
        self._http_client = http_client or UrllibGoogleOAuthHTTPClient()
        self._token_endpoint = _required_text(token_endpoint, 'token_endpoint')
        if timeout_seconds <= 0:
            raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_CONNECTION)
        self._timeout_seconds = timeout_seconds
        self._required_scopes = tuple(required_scopes)
        self._now = now

    def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        scopes: tuple[str, ...],
    ) -> GoogleOAuthTokenBundle:
        code = _required_text(code, 'code')
        redirect_uri = _required_text(redirect_uri, 'redirect_uri')
        requested_scopes = tuple(scopes)
        payload = {
            'code': code,
            'client_id': self._client_id,
            'client_secret': self._client_secret,
            'redirect_uri': redirect_uri,
            'grant_type': 'authorization_code',
        }
        try:
            status, body = self._http_client.post_form(
                url=self._token_endpoint,
                data=payload,
                timeout_seconds=self._timeout_seconds,
            )
        except (TimeoutError, OSError):
            raise GoogleOAuthProviderError() from None
        except Exception:
            raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_UNKNOWN) from None

        response = _parse_json_body(body)
        if status < 200 or status >= 300:
            _raise_for_provider_error(response, status)

        return self._bundle_from_response(response, requested_scopes)

    def _bundle_from_response(
        self,
        response: dict[str, object],
        requested_scopes: tuple[str, ...],
    ) -> GoogleOAuthTokenBundle:
        access_token = _required_response_text(response, 'access_token', GOOGLE_DRIVE_ERROR_CONNECTION)
        refresh_token = _optional_response_text(response, 'refresh_token')
        if refresh_token is None:
            raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_NEEDS_REAUTH)
        token_type = _optional_response_text(response, 'token_type') or 'Bearer'
        id_token = _optional_response_text(response, 'id_token')
        granted_scopes = _response_scopes(response, requested_scopes)
        if any(not _scope_is_granted(scope, granted_scopes) for scope in self._required_scopes):
            raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_SCOPE_MISSING)
        subject, email = _safe_id_token_metadata(id_token)
        return GoogleOAuthTokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=_expires_at(response, self._now),
            scope=granted_scopes,
            token_type=token_type,
            id_token=id_token,
            google_subject=subject,
            google_email=email,
        )



def _scope_is_granted(required_scope: str, granted_scopes: tuple[str, ...]) -> bool:
    granted = set(granted_scopes)
    if required_scope in granted:
        return True
    aliases = {
        'email': {'https://www.googleapis.com/auth/userinfo.email'},
        'profile': {'https://www.googleapis.com/auth/userinfo.profile'},
    }
    return bool(aliases.get(required_scope, set()) & granted)


def _raise_for_provider_error(response: dict[str, object], status: int) -> None:
    error_code = _optional_response_text(response, 'error')
    if error_code == 'invalid_grant':
        raise GoogleOAuthInvalidGrantError()
    if error_code in {'invalid_scope', 'insufficient_scope'}:
        raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_SCOPE_MISSING)
    if error_code == 'invalid_client':
        raise GoogleOAuthProviderError()
    if status >= 500:
        raise GoogleOAuthProviderError()
    raise GoogleOAuthProviderError()


def _parse_json_body(body: bytes) -> dict[str, object]:
    try:
        parsed = json.loads(body.decode('utf-8'))
    except Exception:
        raise GoogleOAuthProviderError() from None
    if not isinstance(parsed, dict):
        raise GoogleOAuthProviderError()
    return parsed


def _response_scopes(response: dict[str, object], requested_scopes: tuple[str, ...]) -> tuple[str, ...]:
    raw_scope = _optional_response_text(response, 'scope')
    if raw_scope is None:
        return tuple(dict.fromkeys(requested_scopes))
    return tuple(dict.fromkeys(scope for scope in raw_scope.split() if scope.strip()))


def _expires_at(response: dict[str, object], now: datetime | None) -> str | None:
    raw_expires_in = response.get('expires_in')
    if raw_expires_in is None:
        return None
    try:
        expires_in = int(raw_expires_in)
    except (TypeError, ValueError):
        raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_CONNECTION) from None
    if expires_in <= 0:
        raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_CONNECTION)
    timestamp = _utc_now(now) + timedelta(seconds=expires_in)
    return timestamp.isoformat()


def _safe_id_token_metadata(id_token: str | None) -> tuple[str | None, str | None]:
    if id_token is None:
        return None, None
    parts = id_token.split('.')
    if len(parts) < 2:
        return None, None
    try:
        payload = parts[1] + '=' * (-len(parts[1]) % 4)
        decoded = base64.urlsafe_b64decode(payload.encode('ascii'))
        parsed = json.loads(decoded.decode('utf-8'))
    except Exception:
        return None, None
    if not isinstance(parsed, dict):
        return None, None
    subject = _optional_text(parsed.get('sub'))
    email = _optional_text(parsed.get('email'))
    return subject, email.lower() if email is not None else None


def _required_response_text(
    response: dict[str, object],
    field_name: str,
    error_code: str,
) -> str:
    value = _optional_response_text(response, field_name)
    if value is None:
        raise GoogleOAuthTokenExchangeError(error_code)
    return value


def _optional_response_text(response: dict[str, object], field_name: str) -> str | None:
    return _optional_text(response.get(field_name))


def _required_text(value: object, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise GoogleOAuthTokenExchangeError(GOOGLE_DRIVE_ERROR_CONNECTION)
    return text


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
