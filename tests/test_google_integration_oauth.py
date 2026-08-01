from __future__ import annotations

from datetime import UTC, datetime
import json

import pytest

from bot.services.google_integration_oauth import (
    GoogleIntegrationOAuthError,
    GoogleIntegrationOAuthNeedsReauth,
    GoogleIntegrationTokenClient,
    OfficialGoogleIdentityVerifier,
)
from bot.services.google_integration_service import GMAIL_SCOPES


class Transport:
    def __init__(self, status=200, payload=None):
        self.status = status
        self.payload = payload or {}
        self.calls = []

    def post_form(self, **kwargs):
        self.calls.append(kwargs)
        return self.status, json.dumps(self.payload).encode()


def test_exchange_and_refresh_are_bounded_and_redacted():
    transport = Transport(
        payload={
            "access_token": "access-secret",
            "refresh_token": "refresh-secret",
            "id_token": "id-secret",
            "scope": " ".join(GMAIL_SCOPES),
            "expires_in": 3600,
        }
    )
    client = GoogleIntegrationTokenClient(
        client_id="client",
        client_secret="client-secret",
        transport=transport,
        now=lambda: datetime(2026, 7, 30, tzinfo=UTC),
    )
    token = client.exchange_code(
        code="auth-secret",
        redirect_uri="https://example.test/callback",
        requested_scopes=GMAIL_SCOPES,
    )
    assert token.refresh_token == "refresh-secret"
    assert "access-secret" not in repr(token)
    assert "refresh-secret" not in repr(token)
    assert transport.calls[0]["timeout_seconds"] == 10


def test_invalid_grant_is_needs_reauth():
    client = GoogleIntegrationTokenClient(
        client_id="client",
        client_secret="secret",
        transport=Transport(status=400, payload={"error": "invalid_grant"}),
    )
    with pytest.raises(GoogleIntegrationOAuthNeedsReauth):
        client.exchange_code(
            code="code",
            redirect_uri="https://example.test/callback",
            requested_scopes=GMAIL_SCOPES,
        )


def test_official_identity_verifier_requires_verified_email_and_nonce():
    def verified(_token, _request, *, audience):
        assert audience == "client"
        return {
            "iss": "https://accounts.google.com",
            "sub": "subject",
            "email": "Office@Example.com",
            "email_verified": True,
            "nonce": "nonce",
        }

    verifier = OfficialGoogleIdentityVerifier(
        client_id="client", verify_fn=verified, request_factory=object
    )
    identity = verifier.verify("signed-token")
    assert identity.email == "office@example.com"
    assert identity.subject == "subject"

    def unverified(*_args, **_kwargs):
        return {
            "iss": "accounts.google.com",
            "sub": "subject",
            "email": "office@example.com",
            "email_verified": False,
            "nonce": "nonce",
        }

    verifier = OfficialGoogleIdentityVerifier(
        client_id="client", verify_fn=unverified, request_factory=object
    )
    with pytest.raises(GoogleIntegrationOAuthError, match="oauth_email_unverified"):
        verifier.verify("signed-token")
