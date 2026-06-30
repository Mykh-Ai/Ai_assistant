from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
import json
from typing import Any

from bot.config import Config
from bot.services.google_drive_oauth_callback_service import GoogleOAuthTokenBundle
from bot.services.token_crypto import FernetTokenCryptoProvider, TokenCryptoError, TokenCryptoProvider


GOOGLE_DRIVE_FULL_SCOPE = "https://www.googleapis.com/auth/drive"
OWNER_GOOGLE_DRIVE_OAUTH_SCOPES = (
    "openid",
    "email",
    "profile",
    GOOGLE_DRIVE_FULL_SCOPE,
)
GOOGLE_DRIVE_OWNER_TOKEN_KEY_ID = "google-drive-owner-oauth-v1"


@dataclass(frozen=True)
class StoredGoogleOAuthTokenBundle:
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: datetime | None
    scopes: tuple[str, ...]
    token_type: str = "Bearer"
    id_token: str | None = field(default=None, repr=False)


def build_google_token_crypto_provider(config: Config) -> TokenCryptoProvider:
    return FernetTokenCryptoProvider(
        secret=config.google_token_crypto_secret,
        key_id=GOOGLE_DRIVE_OWNER_TOKEN_KEY_ID,
    )


def serialize_google_oauth_token_bundle(token_bundle: GoogleOAuthTokenBundle) -> str:
    return json.dumps(
        {
            "access_token": token_bundle.access_token,
            "refresh_token": token_bundle.refresh_token,
            "expires_at": token_bundle.expires_at,
            "scope": list(token_bundle.scope),
            "token_type": token_bundle.token_type,
            "id_token": token_bundle.id_token,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def parse_stored_google_oauth_token_bundle(token_plaintext: bytes | str) -> StoredGoogleOAuthTokenBundle:
    if isinstance(token_plaintext, bytes):
        token_plaintext = token_plaintext.decode("utf-8")
    try:
        parsed = json.loads(token_plaintext)
    except Exception as exc:
        raise TokenCryptoError("google_oauth_token_bundle_invalid") from exc
    if not isinstance(parsed, dict):
        raise TokenCryptoError("google_oauth_token_bundle_invalid")
    access_token = _required_text(parsed.get("access_token"), "access_token")
    refresh_token = _required_text(parsed.get("refresh_token"), "refresh_token")
    scopes = _parse_scopes(parsed.get("scope"))
    return StoredGoogleOAuthTokenBundle(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_at=_parse_optional_timestamp(parsed.get("expires_at")),
        scopes=scopes,
        token_type=_optional_text(parsed.get("token_type")) or "Bearer",
        id_token=_optional_text(parsed.get("id_token")),
    )


def _parse_scopes(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        scopes = [scope for scope in value.split() if scope.strip()]
    elif isinstance(value, list):
        scopes = [str(scope).strip() for scope in value if str(scope).strip()]
    else:
        scopes = []
    if not scopes:
        raise TokenCryptoError("google_oauth_token_scopes_missing")
    return tuple(dict.fromkeys(scopes))


def _parse_optional_timestamp(value: Any) -> datetime | None:
    text = _optional_text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TokenCryptoError("google_oauth_token_expires_at_invalid") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _required_text(value: Any, field_name: str) -> str:
    text = _optional_text(value)
    if text is None:
        raise TokenCryptoError(f"google_oauth_token_{field_name}_missing")
    return text


def _optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
