from __future__ import annotations

from datetime import UTC, datetime, timedelta
import json
import sqlite3

import pytest

from bot.services.google_integration_service import (
    GMAIL_SCOPES,
    GoogleIntegrationError,
    GoogleIntegrationService,
    GoogleTokenEnvelope,
    VerifiedGoogleIdentity,
)
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


def service(tmp_path):
    return GoogleIntegrationService(
        tmp_path / "google.db", DeterministicFakeTokenCryptoProvider()
    )


def prepare(target, *, now=None):
    return target.prepare_oauth(
        workspace_id="workspace-zevs",
        telegram_id=42,
        service="gmail",
        oauth_client_key="primary",
        expected_google_email="Office@Example.com",
        client_id="client-id",
        redirect_uri="https://zevsflow.sk/oauth/google/integration/callback",
        now=now,
    )


def test_schema_is_additive_idempotent_and_separate_from_drive(tmp_path):
    target = service(tmp_path)
    with sqlite3.connect(target._db_path) as connection:  # noqa: SLF001
        connection.execute(
            "CREATE TABLE google_drive_connections (workspace_id TEXT PRIMARY KEY)"
        )
        connection.execute(
            "INSERT INTO google_drive_connections VALUES ('owner')"
        )
        connection.commit()
    target.ensure_schema()
    target.ensure_schema()
    with sqlite3.connect(target._db_path) as connection:  # noqa: SLF001
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "google_accounts",
            "google_oauth_grants",
            "google_workspace_service_bindings",
            "google_integration_oauth_states",
        }.issubset(tables)
        assert connection.execute(
            "SELECT workspace_id FROM google_drive_connections"
        ).fetchone() == ("owner",)


def test_prepare_stores_hashes_not_raw_state_or_nonce(tmp_path):
    target = service(tmp_path)
    created = prepare(target)
    assert "scope=openid+email+profile+" in created.authorization_url
    assert "nonce=" in created.authorization_url
    assert created.raw_state_token not in repr(created)
    assert created.raw_oidc_nonce not in repr(created)
    with sqlite3.connect(target._db_path) as connection:  # noqa: SLF001
        row = connection.execute(
            "SELECT state_token_hash, oidc_nonce_hash, expected_google_email "
            "FROM google_integration_oauth_states"
        ).fetchone()
    assert created.raw_state_token not in row
    assert created.raw_oidc_nonce not in row
    assert row[2] == "office@example.com"


def test_state_is_atomic_single_use_and_expires(tmp_path):
    target = service(tmp_path)
    now = datetime(2026, 7, 30, tzinfo=UTC)
    created = prepare(target, now=now)
    consumed = target.consume_state(created.raw_state_token, now=now)
    assert consumed.status == "consumed"
    with pytest.raises(GoogleIntegrationError, match="oauth_state_reused"):
        target.consume_state(created.raw_state_token, now=now)

    expired = prepare(target, now=now)
    with pytest.raises(GoogleIntegrationError, match="oauth_state_expired"):
        target.consume_state(
            expired.raw_state_token, now=now + timedelta(minutes=11)
        )


def test_verified_binding_encrypts_tokens_and_requires_nonce(tmp_path):
    target = service(tmp_path)
    created = prepare(target)
    state = target.consume_state(created.raw_state_token)
    token = GoogleTokenEnvelope(
        access_token="access-secret",
        refresh_token="refresh-secret",
        id_token="id-secret",
        scopes=GMAIL_SCOPES,
        expires_at="2026-07-30T10:00:00+00:00",
    )
    with pytest.raises(GoogleIntegrationError, match="oauth_nonce_mismatch"):
        target.save_verified_binding(
            state=state,
            identity=VerifiedGoogleIdentity(
                subject="subject-1",
                email="office@example.com",
                nonce="wrong",
            ),
            token=token,
        )

    created = prepare(target)
    state = target.consume_state(created.raw_state_token)
    status = target.save_verified_binding(
        state=state,
        identity=VerifiedGoogleIdentity(
            subject="subject-1",
            email="office@example.com",
            nonce=created.raw_oidc_nonce,
        ),
        token=token,
    )
    assert status.binding_status == "active"
    assert status.grant_status == "connected"
    with sqlite3.connect(target._db_path) as connection:  # noqa: SLF001
        payload, scopes = connection.execute(
            "SELECT encrypted_token_payload, granted_scopes_json "
            "FROM google_oauth_grants"
        ).fetchone()
    assert b"access-secret" not in payload
    assert b"refresh-secret" not in payload
    assert tuple(json.loads(scopes)) == GMAIL_SCOPES


def test_wrong_email_and_disallowed_scope_fail_closed(tmp_path):
    target = service(tmp_path)
    created = prepare(target)
    state = target.consume_state(created.raw_state_token)
    with pytest.raises(GoogleIntegrationError, match="oauth_identity_mismatch"):
        target.save_verified_binding(
            state=state,
            identity=VerifiedGoogleIdentity(
                subject="subject-1",
                email="other@example.com",
                nonce=created.raw_oidc_nonce,
            ),
            token=GoogleTokenEnvelope(
                access_token="a", refresh_token="r", scopes=GMAIL_SCOPES
            ),
        )

    with pytest.raises(GoogleIntegrationError, match="oauth_scope_not_allowed"):
        target.prepare_oauth(
            workspace_id="w",
            telegram_id=1,
            service="gmail",
            oauth_client_key="primary",
            expected_google_email="a@example.com",
            client_id="client",
            redirect_uri="https://example.com/callback",
            scopes=(*GMAIL_SCOPES, "https://www.googleapis.com/auth/drive"),
        )


def test_needs_reauth_updates_binding_and_grant_without_clearing_token(tmp_path):
    target = service(tmp_path)
    created = prepare(target)
    state = target.consume_state(created.raw_state_token)
    target.save_verified_binding(
        state=state,
        identity=VerifiedGoogleIdentity(
            subject='subject-1',
            email='office@example.com',
            nonce=created.raw_oidc_nonce,
        ),
        token=GoogleTokenEnvelope(
            access_token='a', refresh_token='r', scopes=GMAIL_SCOPES
        ),
    )

    target.mark_binding_needs_reauth('workspace-zevs')

    status = target.get_binding_status('workspace-zevs')
    assert status.binding_status == 'needs_reauth'
    assert status.grant_status == 'needs_reauth'
    assert status.last_error_code == 'gmail_needs_reauth'
    with sqlite3.connect(target._db_path) as connection:  # noqa: SLF001
        payload = connection.execute(
            'SELECT encrypted_token_payload FROM google_oauth_grants'
        ).fetchone()[0]
    assert payload is not None


def test_disconnect_is_idempotent_and_clears_unused_token(tmp_path):
    target = service(tmp_path)
    created = prepare(target)
    state = target.consume_state(created.raw_state_token)
    target.save_verified_binding(
        state=state,
        identity=VerifiedGoogleIdentity(
            subject="subject-1",
            email="office@example.com",
            nonce=created.raw_oidc_nonce,
        ),
        token=GoogleTokenEnvelope(
            access_token="a", refresh_token="r", scopes=GMAIL_SCOPES
        ),
    )
    assert target.disconnect("workspace-zevs") is True
    assert target.disconnect("workspace-zevs") is True
    with sqlite3.connect(target._db_path) as connection:  # noqa: SLF001
        status, payload = connection.execute(
            "SELECT status, encrypted_token_payload FROM google_oauth_grants"
        ).fetchone()
    assert status == "disconnected"
    assert payload is None
