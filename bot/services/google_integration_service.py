from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import hashlib
import hmac
import json
from pathlib import Path
import secrets
import sqlite3
from urllib.parse import urlencode
from uuid import uuid4

from bot.services.db import managed_connection
from bot.services.token_crypto import EncryptedToken, TokenCryptoProvider


GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SCOPES = ("openid", "email", "profile", GMAIL_READONLY_SCOPE)
EXECUTABLE_GOOGLE_SERVICES = frozenset({"gmail"})
GOOGLE_GRANT_STATUSES = frozenset(
    {"connected", "disconnected", "needs_reauth", "revoked", "error"}
)
GOOGLE_BINDING_STATUSES = frozenset({"active", "disconnected", "needs_reauth", "error"})
OAUTH_STATE_STATUSES = frozenset(
    {"pending", "consumed", "expired", "rejected", "callback_failed", "connection_saved"}
)

GOOGLE_INTEGRATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS google_accounts (
    account_id TEXT PRIMARY KEY,
    google_subject TEXT NOT NULL UNIQUE,
    google_email TEXT NOT NULL,
    created_by_telegram_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS google_oauth_grants (
    grant_id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL,
    oauth_client_key TEXT NOT NULL,
    grant_purpose TEXT NOT NULL,
    status TEXT NOT NULL,
    granted_scopes_json TEXT NOT NULL,
    encrypted_token_payload BLOB,
    token_key_id TEXT,
    token_version INTEGER,
    access_token_expires_at TEXT,
    connected_at TEXT,
    disconnected_at TEXT,
    revoked_at TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(account_id, oauth_client_key, grant_purpose),
    FOREIGN KEY(account_id) REFERENCES google_accounts(account_id)
);

CREATE TABLE IF NOT EXISTS google_workspace_service_bindings (
    binding_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    grant_id TEXT NOT NULL,
    service TEXT NOT NULL,
    status TEXT NOT NULL,
    created_by_telegram_id INTEGER NOT NULL,
    last_successful_check_at TEXT,
    last_attempt_at TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(workspace_id, service),
    FOREIGN KEY(grant_id) REFERENCES google_oauth_grants(grant_id)
);

CREATE TABLE IF NOT EXISTS google_integration_oauth_states (
    state_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    telegram_id INTEGER NOT NULL,
    requested_service TEXT NOT NULL,
    oauth_client_key TEXT NOT NULL,
    expected_google_email TEXT NOT NULL,
    requested_scopes_json TEXT NOT NULL,
    redirect_uri TEXT NOT NULL,
    state_token_hash TEXT NOT NULL UNIQUE,
    oidc_nonce_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    last_error_code TEXT
);

CREATE TABLE IF NOT EXISTS google_integration_notification_state (
    workspace_id TEXT NOT NULL,
    service TEXT NOT NULL,
    notification_type TEXT NOT NULL,
    last_notified_at TEXT NOT NULL,
    PRIMARY KEY(workspace_id, service, notification_type)
);
"""


class GoogleIntegrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class GoogleOAuthState:
    state_id: str
    workspace_id: str
    telegram_id: int
    requested_service: str
    oauth_client_key: str
    expected_google_email: str
    requested_scopes: tuple[str, ...]
    redirect_uri: str
    status: str
    created_at: str
    expires_at: str
    consumed_at: str | None
    last_error_code: str | None
    _oidc_nonce_hash: str = field(repr=False, compare=False)


@dataclass(frozen=True)
class GoogleOAuthPreparation:
    state: GoogleOAuthState
    authorization_url: str = field(repr=False)
    raw_state_token: str = field(repr=False)
    raw_oidc_nonce: str = field(repr=False)


@dataclass(frozen=True)
class VerifiedGoogleIdentity:
    subject: str
    email: str
    nonce: str


@dataclass(frozen=True)
class GoogleTokenEnvelope:
    access_token: str = field(repr=False)
    refresh_token: str | None = field(default=None, repr=False)
    id_token: str | None = field(default=None, repr=False)
    scopes: tuple[str, ...] = ()
    expires_at: str | None = None
    token_type: str = "Bearer"


@dataclass(frozen=True)
class GoogleBindingStatus:
    workspace_id: str
    google_email: str
    binding_status: str
    grant_status: str
    last_successful_check_at: str | None
    last_error_code: str | None


def ensure_google_integration_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(GOOGLE_INTEGRATION_SCHEMA)


class GoogleIntegrationService:
    def __init__(self, db_path: Path, token_crypto: TokenCryptoProvider) -> None:
        self._db_path = db_path
        self._token_crypto = token_crypto

    def ensure_schema(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.commit()

    def prepare_oauth(
        self,
        *,
        workspace_id: str,
        telegram_id: int,
        service: str,
        oauth_client_key: str,
        expected_google_email: str,
        client_id: str,
        redirect_uri: str,
        scopes: tuple[str, ...] = GMAIL_SCOPES,
        now: datetime | None = None,
        ttl_minutes: int = 10,
    ) -> GoogleOAuthPreparation:
        workspace_id = _required_text(workspace_id, "workspace_id")
        if telegram_id <= 0:
            raise GoogleIntegrationError("telegram_id_required")
        service = _validate_service(service)
        oauth_client_key = _required_text(oauth_client_key, "oauth_client_key")
        expected_email = _normalize_email(expected_google_email)
        client_id = _required_text(client_id, "client_id")
        redirect_uri = _validate_https_uri(redirect_uri)
        normalized_scopes = _validate_scopes(scopes, service)
        if ttl_minutes <= 0 or ttl_minutes > 30:
            raise GoogleIntegrationError("oauth_ttl_invalid")

        timestamp = _utc_now(now)
        raw_state = secrets.token_urlsafe(32)
        raw_nonce = secrets.token_urlsafe(32)
        state_id = str(uuid4())
        expires_at = timestamp + timedelta(minutes=ttl_minutes)
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.execute(
                """
                INSERT INTO google_integration_oauth_states
                (state_id, workspace_id, telegram_id, requested_service,
                 oauth_client_key, expected_google_email, requested_scopes_json,
                 redirect_uri, state_token_hash, oidc_nonce_hash, status,
                 created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    state_id,
                    workspace_id,
                    telegram_id,
                    service,
                    oauth_client_key,
                    expected_email,
                    json.dumps(normalized_scopes),
                    redirect_uri,
                    _token_hash(raw_state),
                    _token_hash(raw_nonce),
                    timestamp.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            connection.commit()

        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(normalized_scopes),
            "state": raw_state,
            "nonce": raw_nonce,
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent select_account",
            "login_hint": expected_email,
        }
        state = self._get_state_by_id(state_id)
        return GoogleOAuthPreparation(
            state=state,
            authorization_url=f"{GOOGLE_AUTHORIZATION_URL}?{urlencode(params)}",
            raw_state_token=raw_state,
            raw_oidc_nonce=raw_nonce,
        )

    def consume_state(
        self, raw_state_token: str, *, now: datetime | None = None
    ) -> GoogleOAuthState:
        digest = _token_hash(_required_text(raw_state_token, "state"))
        timestamp = _utc_now(now)
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM google_integration_oauth_states WHERE state_token_hash=?",
                (digest,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise GoogleIntegrationError("oauth_state_invalid")
            if row["status"] != "pending":
                connection.rollback()
                raise GoogleIntegrationError("oauth_state_reused")
            if _parse_datetime(row["expires_at"]) <= timestamp:
                connection.execute(
                    "UPDATE google_integration_oauth_states SET status='expired', "
                    "last_error_code='oauth_state_expired' WHERE state_id=?",
                    (row["state_id"],),
                )
                connection.commit()
                raise GoogleIntegrationError("oauth_state_expired")
            cursor = connection.execute(
                "UPDATE google_integration_oauth_states SET status='consumed', "
                "consumed_at=? WHERE state_id=? AND status='pending'",
                (timestamp.isoformat(), row["state_id"]),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise GoogleIntegrationError("oauth_state_reused")
            connection.commit()
            row = connection.execute(
                "SELECT * FROM google_integration_oauth_states WHERE state_id=?",
                (row["state_id"],),
            ).fetchone()
            return _state_from_row(row)

    def reject_state(
        self, raw_state_token: str, *, error_code: str = "oauth_provider_rejected"
    ) -> GoogleOAuthState:
        digest = _token_hash(_required_text(raw_state_token, "state"))
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM google_integration_oauth_states WHERE state_token_hash=?",
                (digest,),
            ).fetchone()
            if row is None:
                connection.rollback()
                raise GoogleIntegrationError("oauth_state_invalid")
            if row["status"] != "pending":
                connection.rollback()
                raise GoogleIntegrationError("oauth_state_reused")
            connection.execute(
                "UPDATE google_integration_oauth_states SET status='rejected', "
                "last_error_code=? WHERE state_id=?",
                (_bounded_error(error_code), row["state_id"]),
            )
            connection.commit()
            row = connection.execute(
                "SELECT * FROM google_integration_oauth_states WHERE state_id=?",
                (row["state_id"],),
            ).fetchone()
            return _state_from_row(row)
    def verify_nonce(self, state: GoogleOAuthState, identity: VerifiedGoogleIdentity) -> None:
        if not hmac.compare_digest(
            state._oidc_nonce_hash, _token_hash(identity.nonce)
        ):
            self.mark_state_failed(state.state_id, "oauth_nonce_mismatch")
            raise GoogleIntegrationError("oauth_nonce_mismatch")

    def save_verified_binding(
        self,
        *,
        state: GoogleOAuthState,
        identity: VerifiedGoogleIdentity,
        token: GoogleTokenEnvelope,
        now: datetime | None = None,
    ) -> GoogleBindingStatus:
        self.verify_nonce(state, identity)
        if _normalize_email(identity.email) != state.expected_google_email:
            self.mark_state_failed(state.state_id, "oauth_identity_mismatch")
            raise GoogleIntegrationError("oauth_identity_mismatch")
        _validate_scopes(token.scopes, state.requested_service)
        timestamp = _utc_now(now).isoformat()

        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            account = connection.execute(
                "SELECT * FROM google_accounts WHERE google_subject=?",
                (identity.subject,),
            ).fetchone()
            if account is None:
                account_id = str(uuid4())
                connection.execute(
                    "INSERT INTO google_accounts VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        account_id,
                        identity.subject,
                        _normalize_email(identity.email),
                        state.telegram_id,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                account_id = str(account["account_id"])
                connection.execute(
                    "UPDATE google_accounts SET google_email=?, updated_at=? "
                    "WHERE account_id=?",
                    (_normalize_email(identity.email), timestamp, account_id),
                )

            grant = connection.execute(
                "SELECT * FROM google_oauth_grants WHERE account_id=? "
                "AND oauth_client_key=? AND grant_purpose=?",
                (account_id, state.oauth_client_key, state.requested_service),
            ).fetchone()
            refresh_token = token.refresh_token
            if refresh_token is None:
                if grant is None or grant["encrypted_token_payload"] is None:
                    connection.rollback()
                    raise GoogleIntegrationError("oauth_refresh_token_required")
                old = self._decrypt_payload(grant)
                refresh_token = _required_text(
                    old.get("refresh_token"), "refresh_token"
                )
            payload = {
                "access_token": _required_text(token.access_token, "access_token"),
                "refresh_token": refresh_token,
                "id_token": token.id_token,
                "token_type": token.token_type,
                "scopes": list(token.scopes),
                "expires_at": token.expires_at,
            }
            encrypted = self._token_crypto.encrypt_token(
                json.dumps(payload, separators=(",", ":"))
            )
            if grant is None:
                grant_id = str(uuid4())
                connection.execute(
                    """
                    INSERT INTO google_oauth_grants
                    (grant_id, account_id, oauth_client_key, grant_purpose, status,
                     granted_scopes_json, encrypted_token_payload, token_key_id,
                     token_version, access_token_expires_at, connected_at,
                     created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'connected', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        grant_id,
                        account_id,
                        state.oauth_client_key,
                        state.requested_service,
                        json.dumps(token.scopes),
                        encrypted.ciphertext,
                        encrypted.key_id,
                        encrypted.version,
                        token.expires_at,
                        timestamp,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                grant_id = str(grant["grant_id"])
                connection.execute(
                    """
                    UPDATE google_oauth_grants SET status='connected',
                    granted_scopes_json=?, encrypted_token_payload=?,
                    token_key_id=?, token_version=?, access_token_expires_at=?,
                    connected_at=?, disconnected_at=NULL, revoked_at=NULL,
                    last_error_code=NULL, updated_at=? WHERE grant_id=?
                    """,
                    (
                        json.dumps(token.scopes),
                        encrypted.ciphertext,
                        encrypted.key_id,
                        encrypted.version,
                        token.expires_at,
                        timestamp,
                        timestamp,
                        grant_id,
                    ),
                )
            binding = connection.execute(
                "SELECT binding_id FROM google_workspace_service_bindings "
                "WHERE workspace_id=? AND service=?",
                (state.workspace_id, state.requested_service),
            ).fetchone()
            if binding is None:
                connection.execute(
                    """
                    INSERT INTO google_workspace_service_bindings
                    (binding_id, workspace_id, grant_id, service, status,
                     created_by_telegram_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 'active', ?, ?, ?)
                    """,
                    (
                        str(uuid4()),
                        state.workspace_id,
                        grant_id,
                        state.requested_service,
                        state.telegram_id,
                        timestamp,
                        timestamp,
                    ),
                )
            else:
                connection.execute(
                    "UPDATE google_workspace_service_bindings SET grant_id=?, "
                    "status='active', last_error_code=NULL, updated_at=? "
                    "WHERE binding_id=?",
                    (grant_id, timestamp, binding["binding_id"]),
                )
            connection.execute(
                "UPDATE google_integration_oauth_states SET "
                "status='connection_saved', last_error_code=NULL WHERE state_id=?",
                (state.state_id,),
            )
            connection.commit()
        return self.get_binding_status(state.workspace_id, state.requested_service)

    def get_binding_status(
        self, workspace_id: str, service: str = "gmail"
    ) -> GoogleBindingStatus:
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT b.workspace_id, a.google_email, b.status binding_status,
                       g.status grant_status, b.last_successful_check_at,
                       COALESCE(b.last_error_code, g.last_error_code) last_error_code
                FROM google_workspace_service_bindings b
                JOIN google_oauth_grants g ON g.grant_id=b.grant_id
                JOIN google_accounts a ON a.account_id=g.account_id
                WHERE b.workspace_id=? AND b.service=?
                """,
                (_required_text(workspace_id, "workspace_id"), _validate_service(service)),
            ).fetchone()
        if row is None:
            raise GoogleIntegrationError("google_binding_not_found")
        return GoogleBindingStatus(**dict(row))

    def disconnect(self, workspace_id: str, service: str = "gmail") -> bool:
        workspace_id = _required_text(workspace_id, "workspace_id")
        service = _validate_service(service)
        timestamp = _utc_now(None).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM google_workspace_service_bindings "
                "WHERE workspace_id=? AND service=?",
                (workspace_id, service),
            ).fetchone()
            if row is None:
                connection.rollback()
                return False
            connection.execute(
                "UPDATE google_workspace_service_bindings SET status='disconnected', "
                "updated_at=? WHERE binding_id=?",
                (timestamp, row["binding_id"]),
            )
            active = connection.execute(
                "SELECT COUNT(*) FROM google_workspace_service_bindings "
                "WHERE grant_id=? AND status='active'",
                (row["grant_id"],),
            ).fetchone()[0]
            if not active:
                connection.execute(
                    "UPDATE google_oauth_grants SET status='disconnected', "
                    "encrypted_token_payload=NULL, token_key_id=NULL, "
                    "token_version=NULL, access_token_expires_at=NULL, "
                    "disconnected_at=?, updated_at=? WHERE grant_id=?",
                    (timestamp, timestamp, row["grant_id"]),
                )
            connection.commit()
            return True

    def mark_binding_needs_reauth(
        self,
        workspace_id: str,
        service: str = "gmail",
        *,
        error_code: str = "gmail_needs_reauth",
    ) -> None:
        workspace_id = _required_text(workspace_id, "workspace_id")
        service = _validate_service(service)
        timestamp = _utc_now(None).isoformat()
        bounded_error = _bounded_error(error_code)
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            binding = connection.execute(
                "SELECT grant_id FROM google_workspace_service_bindings "
                "WHERE workspace_id=? AND service=?",
                (workspace_id, service),
            ).fetchone()
            if binding is None:
                connection.rollback()
                raise GoogleIntegrationError("google_binding_not_found")
            connection.execute(
                "UPDATE google_workspace_service_bindings SET status='needs_reauth', "
                "last_error_code=?, updated_at=? WHERE workspace_id=? AND service=?",
                (bounded_error, timestamp, workspace_id, service),
            )
            connection.execute(
                "UPDATE google_oauth_grants SET status='needs_reauth', "
                "last_error_code=?, updated_at=? WHERE grant_id=?",
                (bounded_error, timestamp, binding["grant_id"]),
            )
            connection.commit()

    def mark_state_failed(self, state_id: str, error_code: str) -> None:
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.execute(
                "UPDATE google_integration_oauth_states SET "
                "status='callback_failed', last_error_code=? WHERE state_id=?",
                (_bounded_error(error_code), state_id),
            )
            connection.commit()

    def _get_state_by_id(self, state_id: str) -> GoogleOAuthState:
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                "SELECT * FROM google_integration_oauth_states WHERE state_id=?",
                (state_id,),
            ).fetchone()
        if row is None:
            raise GoogleIntegrationError("oauth_state_not_found")
        return _state_from_row(row)

    def _decrypt_payload(self, row: sqlite3.Row) -> dict[str, object]:
        try:
            plaintext = self._token_crypto.decrypt_token(
                EncryptedToken(
                    ciphertext=bytes(row["encrypted_token_payload"]),
                    key_id=str(row["token_key_id"]),
                    version=int(row["token_version"]),
                )
            )
            value = json.loads(plaintext.decode("utf-8"))
        except Exception:
            raise GoogleIntegrationError("oauth_token_decryption_failed") from None
        if not isinstance(value, dict):
            raise GoogleIntegrationError("oauth_token_decryption_failed")
        return value


def _state_from_row(row: sqlite3.Row) -> GoogleOAuthState:
    return GoogleOAuthState(
        state_id=str(row["state_id"]),
        workspace_id=str(row["workspace_id"]),
        telegram_id=int(row["telegram_id"]),
        requested_service=str(row["requested_service"]),
        oauth_client_key=str(row["oauth_client_key"]),
        expected_google_email=str(row["expected_google_email"]),
        requested_scopes=tuple(json.loads(row["requested_scopes_json"])),
        redirect_uri=str(row["redirect_uri"]),
        status=str(row["status"]),
        created_at=str(row["created_at"]),
        expires_at=str(row["expires_at"]),
        consumed_at=row["consumed_at"],
        last_error_code=row["last_error_code"],
        _oidc_nonce_hash=str(row["oidc_nonce_hash"]),
    )


def _validate_service(value: str) -> str:
    value = _required_text(value, "service")
    if value not in EXECUTABLE_GOOGLE_SERVICES:
        raise GoogleIntegrationError("google_service_not_executable")
    return value


def _validate_scopes(scopes: tuple[str, ...], service: str) -> tuple[str, ...]:
    normalized = tuple(dict.fromkeys(_required_text(v, "scope") for v in scopes))
    required = set(GMAIL_SCOPES if service == "gmail" else ())
    if not required.issubset(normalized):
        raise GoogleIntegrationError("oauth_scope_missing")
    if service == "gmail" and any(
        scope.startswith("https://www.googleapis.com/auth/")
        and scope not in {GMAIL_READONLY_SCOPE}
        for scope in normalized
    ):
        raise GoogleIntegrationError("oauth_scope_not_allowed")
    return normalized


def _token_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_email(value: str) -> str:
    value = _required_text(value, "google_email").lower()
    if len(value) > 254 or "@" not in value or any(c in value for c in "\r\n\t"):
        raise GoogleIntegrationError("google_email_invalid")
    return value


def _validate_https_uri(value: str) -> str:
    value = _required_text(value, "redirect_uri")
    if not value.startswith("https://") or len(value) > 2048:
        raise GoogleIntegrationError("redirect_uri_invalid")
    return value


def _required_text(value: object, field: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or any(c in text for c in "\r\n\x00"):
        raise GoogleIntegrationError(f"{field}_required")
    return text


def _bounded_error(value: str) -> str:
    return _required_text(value, "error_code")[:80]


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
