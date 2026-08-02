from __future__ import annotations

from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class GoogleGmailConfig:
    enabled: bool = False
    callback_enabled: bool = False
    callback_host: str = "127.0.0.1"
    callback_port: int = 8081
    callback_proxy_secret: str | None = field(default=None, repr=False)
    public_redirect_uri: str | None = None
    client_id: str | None = None
    client_secret: str | None = field(default=None, repr=False)
    token_crypto_secret: str | None = field(default=None, repr=False)
    target_workspace_id: str | None = None
    expected_email: str | None = None
    statement_query: str | None = field(default=None, repr=False)
    check_interval_seconds: int = 86400
    initial_lookback_days: int = 30
    overlap_hours: int = 24
    batch_size: int = 50
    max_attachment_bytes: int = 20 * 1024 * 1024
    allowed_mime_types: frozenset[str] = frozenset(
        {"application/pdf", "application/octet-stream", "text/csv", "application/xml", "text/xml"}
    )
    allowed_extensions: frozenset[str] = frozenset(
        {".pdf", ".csv", ".xml"}
    )
    notification_cooldown_seconds: int = 86400

    def validate_enabled(self) -> None:
        if self.callback_enabled and not self.enabled:
            raise RuntimeError(
                "GOOGLE_INTEGRATION_CALLBACK_ENABLED requires GOOGLE_GMAIL_ENABLED"
            )
        if not self.enabled:
            return
        required = {
            "GOOGLE_GMAIL_TARGET_WORKSPACE_ID": self.target_workspace_id,
            "GOOGLE_GMAIL_EXPECTED_EMAIL": self.expected_email,
            "GOOGLE_GMAIL_STATEMENT_QUERY": self.statement_query,
            "GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI": self.public_redirect_uri,
            "GOOGLE_GMAIL_OAUTH_CLIENT_ID": self.client_id,
            "GOOGLE_GMAIL_OAUTH_CLIENT_SECRET": self.client_secret,
            "GOOGLE_TOKEN_CRYPTO_SECRET": self.token_crypto_secret,
            "GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET": self.callback_proxy_secret,
        }
        missing = [name for name, value in required.items() if not value]
        if not self.callback_enabled:
            missing.append("GOOGLE_INTEGRATION_CALLBACK_ENABLED")
        if missing:
            raise RuntimeError(
                "Google Gmail integration configuration missing: "
                + ", ".join(sorted(missing))
            )
        if len(self.callback_proxy_secret or "") < 32:
            raise RuntimeError(
                "GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET must be at least 32 characters"
            )
        if not str(self.public_redirect_uri).startswith("https://"):
            raise RuntimeError(
                "GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI must use https"
            )


def load_google_gmail_config() -> GoogleGmailConfig:
    config = GoogleGmailConfig(
        enabled=_bool("GOOGLE_GMAIL_ENABLED"),
        callback_enabled=_bool("GOOGLE_INTEGRATION_CALLBACK_ENABLED"),
        callback_host=_text("GOOGLE_INTEGRATION_CALLBACK_HOST") or "127.0.0.1",
        callback_port=_integer(
            "GOOGLE_INTEGRATION_CALLBACK_PORT", 8081, minimum=1, maximum=65535
        ),
        callback_proxy_secret=_text(
            "GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET"
        ),
        public_redirect_uri=_text("GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI"),
        client_id=_text("GOOGLE_GMAIL_OAUTH_CLIENT_ID"),
        client_secret=_text("GOOGLE_GMAIL_OAUTH_CLIENT_SECRET"),
        token_crypto_secret=_text("GOOGLE_TOKEN_CRYPTO_SECRET"),
        target_workspace_id=_text("GOOGLE_GMAIL_TARGET_WORKSPACE_ID"),
        expected_email=_text("GOOGLE_GMAIL_EXPECTED_EMAIL"),
        statement_query=_text("GOOGLE_GMAIL_STATEMENT_QUERY"),
        check_interval_seconds=_integer(
            "GOOGLE_GMAIL_CHECK_INTERVAL_SECONDS", 86400, minimum=60, maximum=604800
        ),
        initial_lookback_days=_integer(
            "GOOGLE_GMAIL_INITIAL_LOOKBACK_DAYS", 30, minimum=1, maximum=365
        ),
        overlap_hours=_integer(
            "GOOGLE_GMAIL_OVERLAP_HOURS", 24, minimum=1, maximum=168
        ),
        batch_size=_integer(
            "GOOGLE_GMAIL_BATCH_SIZE", 50, minimum=1, maximum=500
        ),
        max_attachment_bytes=_integer(
            "GOOGLE_GMAIL_MAX_ATTACHMENT_BYTES",
            20 * 1024 * 1024,
            minimum=1024,
            maximum=100 * 1024 * 1024,
        ),
        allowed_mime_types=_set(
            "GOOGLE_GMAIL_ALLOWED_MIME_TYPES",
            {"application/pdf", "application/octet-stream", "text/csv", "application/xml", "text/xml"},
        ),
        allowed_extensions=_extensions(
            "GOOGLE_GMAIL_ALLOWED_EXTENSIONS", {".pdf", ".csv", ".xml"}
        ),
        notification_cooldown_seconds=_integer(
            "GOOGLE_GMAIL_NOTIFICATION_COOLDOWN_SECONDS",
            86400,
            minimum=60,
            maximum=604800,
        ),
    )
    config.validate_enabled()
    return config


def _text(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def _bool(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _integer(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        raise RuntimeError(f"{name} must be an integer") from None
    if value < minimum or value > maximum:
        raise RuntimeError(f"{name} must be between {minimum} and {maximum}")
    return value


def _set(name: str, default: set[str]) -> frozenset[str]:
    raw = os.getenv(name, "")
    values = {item.strip().lower() for item in raw.split(",") if item.strip()}
    return frozenset(values or default)


def _extensions(name: str, default: set[str]) -> frozenset[str]:
    values = _set(name, default)
    if any(not value.startswith(".") for value in values):
        raise RuntimeError(f"{name} must contain dot-prefixed extensions")
    return values
