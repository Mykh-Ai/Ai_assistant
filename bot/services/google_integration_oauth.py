from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import json
from typing import Callable, Protocol
from urllib import error, parse, request

from bot.services.google_integration_service import (
    GoogleTokenEnvelope,
    VerifiedGoogleIdentity,
)


GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
MAX_TOKEN_RESPONSE_BYTES = 64 * 1024


class GoogleIntegrationOAuthError(RuntimeError):
    pass


class GoogleIntegrationOAuthRetryableError(GoogleIntegrationOAuthError):
    pass


class GoogleIntegrationOAuthNeedsReauth(GoogleIntegrationOAuthError):
    pass


class OAuthHTTPTransport(Protocol):
    def post_form(
        self, *, url: str, fields: dict[str, str], timeout_seconds: float
    ) -> tuple[int, bytes]:
        ...


@dataclass(frozen=True)
class UrllibOAuthHTTPTransport:
    def post_form(
        self, *, url: str, fields: dict[str, str], timeout_seconds: float
    ) -> tuple[int, bytes]:
        outbound = request.Request(
            url,
            data=parse.urlencode(fields).encode("utf-8"),
            headers={
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            method="POST",
        )
        try:
            with request.urlopen(outbound, timeout=timeout_seconds) as response:
                return int(response.status), response.read(MAX_TOKEN_RESPONSE_BYTES + 1)
        except error.HTTPError as exc:
            return int(exc.code), exc.read(MAX_TOKEN_RESPONSE_BYTES + 1)


class GoogleIntegrationTokenClient:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: str,
        transport: OAuthHTTPTransport | None = None,
        timeout_seconds: float = 10,
        token_endpoint: str = GOOGLE_TOKEN_ENDPOINT,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._client_id = _required(client_id, "client_id")
        self._client_secret = _required(client_secret, "client_secret")
        self._transport = transport or UrllibOAuthHTTPTransport()
        self._timeout_seconds = timeout_seconds
        self._token_endpoint = _required(token_endpoint, "token_endpoint")
        self._now = now or (lambda: datetime.now(UTC))
        if timeout_seconds <= 0 or timeout_seconds > 60:
            raise GoogleIntegrationOAuthError("oauth_timeout_invalid")

    def exchange_code(
        self,
        *,
        code: str,
        redirect_uri: str,
        requested_scopes: tuple[str, ...],
    ) -> GoogleTokenEnvelope:
        response = self._post(
            {
                "code": _required(code, "code"),
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "redirect_uri": _required(redirect_uri, "redirect_uri"),
                "grant_type": "authorization_code",
            }
        )
        return self._envelope(response, requested_scopes=requested_scopes)

    def refresh(
        self, *, refresh_token: str, requested_scopes: tuple[str, ...]
    ) -> GoogleTokenEnvelope:
        response = self._post(
            {
                "refresh_token": _required(refresh_token, "refresh_token"),
                "client_id": self._client_id,
                "client_secret": self._client_secret,
                "grant_type": "refresh_token",
            }
        )
        envelope = self._envelope(response, requested_scopes=requested_scopes)
        return GoogleTokenEnvelope(
            access_token=envelope.access_token,
            refresh_token=refresh_token,
            id_token=envelope.id_token,
            scopes=envelope.scopes,
            expires_at=envelope.expires_at,
            token_type=envelope.token_type,
        )

    def _post(self, fields: dict[str, str]) -> dict[str, object]:
        try:
            status, body = self._transport.post_form(
                url=self._token_endpoint,
                fields=fields,
                timeout_seconds=self._timeout_seconds,
            )
        except (TimeoutError, OSError):
            raise GoogleIntegrationOAuthRetryableError("oauth_provider_unavailable") from None
        except GoogleIntegrationOAuthError:
            raise
        except Exception:
            raise GoogleIntegrationOAuthError("oauth_transport_failed") from None
        if len(body) > MAX_TOKEN_RESPONSE_BYTES:
            raise GoogleIntegrationOAuthError("oauth_response_too_large")
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            raise GoogleIntegrationOAuthError("oauth_response_invalid") from None
        if not isinstance(payload, dict):
            raise GoogleIntegrationOAuthError("oauth_response_invalid")
        if status < 200 or status >= 300:
            provider_code = str(payload.get("error", "")).strip()
            if provider_code == "invalid_grant":
                raise GoogleIntegrationOAuthNeedsReauth("oauth_needs_reauth")
            if status >= 500:
                raise GoogleIntegrationOAuthRetryableError("oauth_provider_unavailable")
            raise GoogleIntegrationOAuthError("oauth_provider_rejected")
        return payload

    def _envelope(
        self, payload: dict[str, object], *, requested_scopes: tuple[str, ...]
    ) -> GoogleTokenEnvelope:
        granted = tuple(
            dict.fromkeys(
                part
                for part in str(payload.get("scope") or " ".join(requested_scopes)).split()
                if part
            )
        )
        expires_at = None
        if payload.get("expires_in") is not None:
            try:
                expires_in = int(payload["expires_in"])
            except (TypeError, ValueError):
                raise GoogleIntegrationOAuthError("oauth_response_invalid") from None
            if expires_in <= 0 or expires_in > 86400:
                raise GoogleIntegrationOAuthError("oauth_response_invalid")
            expires_at = (self._now() + timedelta(seconds=expires_in)).isoformat()
        return GoogleTokenEnvelope(
            access_token=_required(payload.get("access_token"), "access_token"),
            refresh_token=_optional(payload.get("refresh_token")),
            id_token=_optional(payload.get("id_token")),
            scopes=granted,
            expires_at=expires_at,
            token_type=_optional(payload.get("token_type")) or "Bearer",
        )


class OfficialGoogleIdentityVerifier:
    """Verify Google ID tokens using google-auth, never unsigned decoding."""

    def __init__(
        self,
        *,
        client_id: str,
        verify_fn: Callable[..., dict[str, object]] | None = None,
        request_factory: Callable[[], object] | None = None,
    ) -> None:
        self._client_id = _required(client_id, "client_id")
        if verify_fn is None or request_factory is None:
            try:
                from google.auth.transport.requests import Request
                from google.oauth2.id_token import verify_oauth2_token
            except ImportError:
                raise GoogleIntegrationOAuthError(
                    "google_identity_verifier_dependency_missing"
                ) from None
            verify_fn = verify_oauth2_token
            request_factory = Request
        self._verify_fn = verify_fn
        self._request_factory = request_factory

    def verify(self, id_token_value: str) -> VerifiedGoogleIdentity:
        raw = _required(id_token_value, "id_token")
        try:
            claims = self._verify_fn(
                raw, self._request_factory(), audience=self._client_id
            )
        except Exception:
            raise GoogleIntegrationOAuthError("oauth_identity_invalid") from None
        if not isinstance(claims, dict):
            raise GoogleIntegrationOAuthError("oauth_identity_invalid")
        issuer = str(claims.get("iss", "")).strip()
        if issuer not in {"accounts.google.com", "https://accounts.google.com"}:
            raise GoogleIntegrationOAuthError("oauth_identity_invalid")
        if claims.get("email_verified") is not True:
            raise GoogleIntegrationOAuthError("oauth_email_unverified")
        subject = _required(claims.get("sub"), "google_subject")
        email = _required(claims.get("email"), "google_email").lower()
        nonce = _required(claims.get("nonce"), "oauth_nonce")
        return VerifiedGoogleIdentity(subject=subject, email=email, nonce=nonce)


def _required(value: object, field: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or any(char in text for char in "\r\n\x00"):
        raise GoogleIntegrationOAuthError(f"{field}_required")
    return text


def _optional(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
