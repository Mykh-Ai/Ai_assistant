from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import sqlite3

from bot.services.db import managed_connection
from bot.services.google_integration_service import (
    GoogleIntegrationError,
    ensure_google_integration_schema,
)
from bot.services.token_crypto import EncryptedToken, TokenCryptoProvider


@dataclass(frozen=True)
class ActiveGmailGrant:
    workspace_id: str
    connection_id: str
    google_email: str
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    scopes: tuple[str, ...] = ()
    expires_at: str | None = None


class GoogleGmailRuntimeService:
    def __init__(self, db_path: Path, token_crypto: TokenCryptoProvider) -> None:
        self._db_path = db_path
        self._token_crypto = token_crypto

    def last_successful_check(self, workspace_id: str) -> str | None:
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            row = connection.execute(
                "SELECT last_successful_check_at FROM google_workspace_service_bindings "
                "WHERE workspace_id=? AND service='gmail'",
                (workspace_id.strip(),),
            ).fetchone()
        return str(row[0]) if row is not None and row[0] else None

    def mark_check_succeeded(self, workspace_id: str, timestamp: str) -> None:
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.execute(
                "UPDATE google_workspace_service_bindings SET "
                "last_attempt_at=?, last_successful_check_at=?, last_error_code=NULL, "
                "updated_at=? WHERE workspace_id=? AND service='gmail' "
                "AND status='active'",
                (timestamp, timestamp, timestamp, workspace_id.strip()),
            )
            connection.commit()

    def mark_needs_reauth(self, workspace_id: str) -> None:
        from bot.services.google_integration_service import GoogleIntegrationService

        GoogleIntegrationService(
            self._db_path, self._token_crypto
        ).mark_binding_needs_reauth(workspace_id, "gmail")

    def load_active_grant(self, workspace_id: str) -> ActiveGmailGrant:
        with managed_connection(self._db_path) as connection:
            ensure_google_integration_schema(connection)
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """
                SELECT b.workspace_id, g.grant_id, a.google_email,
                       g.encrypted_token_payload, g.token_key_id,
                       g.token_version, g.granted_scopes_json,
                       g.access_token_expires_at
                FROM google_workspace_service_bindings b
                JOIN google_oauth_grants g ON g.grant_id=b.grant_id
                JOIN google_accounts a ON a.account_id=g.account_id
                WHERE b.workspace_id=? AND b.service='gmail'
                      AND b.status='active' AND g.status='connected'
                """,
                (workspace_id.strip(),),
            ).fetchone()
        if row is None:
            raise GoogleIntegrationError("gmail_binding_inactive")
        try:
            decrypted = self._token_crypto.decrypt_token(
                EncryptedToken(
                    ciphertext=bytes(row["encrypted_token_payload"]),
                    key_id=str(row["token_key_id"]),
                    version=int(row["token_version"]),
                )
            )
            payload = json.loads(decrypted.decode("utf-8"))
            access_token = str(payload["access_token"]).strip()
            refresh_token = str(payload["refresh_token"]).strip()
        except Exception:
            raise GoogleIntegrationError("oauth_token_decryption_failed") from None
        if not access_token or not refresh_token:
            raise GoogleIntegrationError("oauth_token_decryption_failed")
        return ActiveGmailGrant(
            workspace_id=str(row["workspace_id"]),
            connection_id=str(row["grant_id"]),
            google_email=str(row["google_email"]),
            access_token=access_token,
            refresh_token=refresh_token,
            scopes=tuple(json.loads(row["granted_scopes_json"])),
            expires_at=row["access_token_expires_at"],
        )
