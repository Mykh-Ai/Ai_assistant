import pytest

from bot.services.google_gmail_config import load_google_gmail_config


def test_gmail_disabled_by_default(monkeypatch):
    for name in (
        "GOOGLE_GMAIL_ENABLED",
        "GOOGLE_INTEGRATION_CALLBACK_ENABLED",
        "GOOGLE_GMAIL_STATEMENT_QUERY",
    ):
        monkeypatch.delenv(name, raising=False)
    config = load_google_gmail_config()
    assert config.enabled is False
    assert config.check_interval_seconds == 86400


def test_enabled_gmail_fails_closed_when_required_config_missing(monkeypatch):
    monkeypatch.setenv("GOOGLE_GMAIL_ENABLED", "true")
    monkeypatch.delenv("GOOGLE_GMAIL_STATEMENT_QUERY", raising=False)
    with pytest.raises(RuntimeError, match="configuration missing"):
        load_google_gmail_config()


def test_enabled_gmail_accepts_only_complete_bounded_config(monkeypatch):
    values = {
        "GOOGLE_GMAIL_ENABLED": "true",
        "GOOGLE_INTEGRATION_CALLBACK_ENABLED": "true",
        "GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET": "s" * 32,
        "GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI":
            "https://zevsflow.sk/oauth/google/integration/callback",
        "GOOGLE_GMAIL_OAUTH_CLIENT_ID": "client",
        "GOOGLE_GMAIL_OAUTH_CLIENT_SECRET": "secret",
        "GOOGLE_TOKEN_CRYPTO_SECRET": "crypto",
        "GOOGLE_GMAIL_TARGET_WORKSPACE_ID": "workspace-zevs",
        "GOOGLE_GMAIL_EXPECTED_EMAIL": "office@example.com",
        "GOOGLE_GMAIL_STATEMENT_QUERY": "has:attachment newer_than:30d",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    config = load_google_gmail_config()
    assert config.enabled is True
    assert config.target_workspace_id == "workspace-zevs"
    assert "secret" not in repr(config)
    assert "has:attachment" not in repr(config)


def test_gmail_credentials_do_not_fall_back_to_owner_drive_oauth(monkeypatch):
    values = {
        "GOOGLE_GMAIL_ENABLED": "true",
        "GOOGLE_INTEGRATION_CALLBACK_ENABLED": "true",
        "GOOGLE_INTEGRATION_CALLBACK_PROXY_SECRET": "s" * 32,
        "GOOGLE_INTEGRATION_PUBLIC_REDIRECT_URI":
            "https://zevsflow.sk/oauth/google/integration/callback",
        "GOOGLE_OAUTH_CLIENT_ID": "owner-drive-client",
        "GOOGLE_OAUTH_CLIENT_SECRET": "owner-drive-secret",
        "GOOGLE_TOKEN_CRYPTO_SECRET": "crypto",
        "GOOGLE_GMAIL_TARGET_WORKSPACE_ID": "workspace-zevs",
        "GOOGLE_GMAIL_EXPECTED_EMAIL": "office@example.com",
        "GOOGLE_GMAIL_STATEMENT_QUERY": "has:attachment newer_than:30d",
    }
    for name, value in values.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GOOGLE_GMAIL_OAUTH_CLIENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_GMAIL_OAUTH_CLIENT_SECRET", raising=False)

    with pytest.raises(RuntimeError, match="GOOGLE_GMAIL_OAUTH_CLIENT_ID"):
        load_google_gmail_config()


def test_callback_cannot_start_when_gmail_integration_is_disabled(monkeypatch):
    monkeypatch.setenv("GOOGLE_INTEGRATION_CALLBACK_ENABLED", "1")

    with pytest.raises(RuntimeError, match="requires GOOGLE_GMAIL_ENABLED"):
        load_google_gmail_config()
