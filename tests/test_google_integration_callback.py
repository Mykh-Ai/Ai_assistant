from __future__ import annotations

from datetime import UTC, datetime
import json

from bot.services.google_integration_callback_service import (
    GoogleIntegrationCallbackPayload,
    GoogleIntegrationCallbackService,
)
from bot.services.google_integration_oauth import (
    GoogleIntegrationTokenClient,
    OfficialGoogleIdentityVerifier,
)
from bot.services.google_integration_service import (
    GMAIL_SCOPES,
    GoogleIntegrationService,
)
from bot.services.token_crypto import DeterministicFakeTokenCryptoProvider


class Transport:
    def __init__(self, nonce):
        self.nonce = nonce

    def post_form(self, **_kwargs):
        return 200, json.dumps(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "id_token": "signed",
                "scope": " ".join(GMAIL_SCOPES),
            }
        ).encode()


def test_callback_verifies_identity_context_and_commits(tmp_path):
    integration = GoogleIntegrationService(
        tmp_path / "db.sqlite", DeterministicFakeTokenCryptoProvider()
    )
    prepared = integration.prepare_oauth(
        workspace_id="workspace",
        telegram_id=42,
        service="gmail",
        oauth_client_key="primary",
        expected_google_email="office@example.com",
        client_id="client",
        redirect_uri="https://zevsflow.sk/oauth/google/integration/callback",
    )

    def verify(_token, _request, *, audience):
        assert audience == "client"
        return {
            "iss": "accounts.google.com",
            "sub": "subject",
            "email": "office@example.com",
            "email_verified": True,
            "nonce": prepared.raw_oidc_nonce,
        }

    service = GoogleIntegrationCallbackService(
        integration=integration,
        tokens=GoogleIntegrationTokenClient(
            client_id="client",
            client_secret="secret",
            transport=Transport(prepared.raw_oidc_nonce),
        ),
        identities=OfficialGoogleIdentityVerifier(
            client_id="client", verify_fn=verify, request_factory=object
        ),
        validate_context=lambda state: (
            None if state.workspace_id == "workspace" else (_ for _ in ()).throw(ValueError())
        ),
    )
    result = service.handle(
        GoogleIntegrationCallbackPayload(
            state=prepared.raw_state_token, code="authorization-code"
        )
    )
    assert result.success is True
    assert result.status is not None
    assert result.status.google_email == "office@example.com"

    reused = service.handle(
        GoogleIntegrationCallbackPayload(
            state=prepared.raw_state_token, code="authorization-code"
        )
    )
    assert reused.success is False
    assert reused.error_code == "oauth_state_reused"


def test_provider_rejection_consumes_pending_state_as_rejected(tmp_path):
    integration = GoogleIntegrationService(
        tmp_path / "db.sqlite", DeterministicFakeTokenCryptoProvider()
    )
    prepared = integration.prepare_oauth(
        workspace_id="workspace",
        telegram_id=42,
        service="gmail",
        oauth_client_key="primary",
        expected_google_email="office@example.com",
        client_id="client",
        redirect_uri="https://zevsflow.sk/oauth/google/integration/callback",
    )
    service = GoogleIntegrationCallbackService(
        integration=integration,
        tokens=object(),
        identities=object(),
        validate_context=lambda _state: None,
    )
    result = service.handle(
        GoogleIntegrationCallbackPayload(
            state=prepared.raw_state_token, error="access_denied"
        )
    )
    assert result.success is False
    assert result.error_code == "oauth_provider_rejected"
