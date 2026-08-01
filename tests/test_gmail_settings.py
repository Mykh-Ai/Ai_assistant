from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

from bot.config import Config
from bot.handlers import gmail_settings
from bot.services.workspace_context import WorkspaceContext


ADMIN_ID = 42


class Message:
    def __init__(self, user_id: int = ADMIN_ID) -> None:
        self.from_user = SimpleNamespace(id=user_id)
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


class WorkspaceService:
    def __init__(self, _db_path: Path) -> None:
        pass

    def require_membership(self, telegram_id: int, workspace_id: str):
        assert telegram_id == ADMIN_ID
        assert workspace_id == "workspace-zevs"
        return WorkspaceContext(
            actor_telegram_id=ADMIN_ID,
            workspace_id=workspace_id,
            workspace_display_name="Zevs <b>x</b>",
            storage_key="zevs",
            drive_folder_name="Zevs",
            membership_role="owner",
            supplier_id=1,
        )


class Service:
    disconnected = False

    def prepare_oauth(self, **kwargs):
        assert kwargs["workspace_id"] == "workspace-zevs"
        assert kwargs["service"] == "gmail"
        return SimpleNamespace(
            authorization_url="https://accounts.google.com/o/oauth2/v2/auth?safe=1"
        )

    def get_binding_status(self, workspace_id: str):
        assert workspace_id == "workspace-zevs"
        return SimpleNamespace(
            google_email="office@example.test",
            grant_status="connected",
            binding_status="active",
            last_successful_check_at=None,
            last_error_code=None,
        )

    def disconnect(self, workspace_id: str):
        assert workspace_id == "workspace-zevs"
        self.disconnected = True
        return True


def config(tmp_path: Path) -> Config:
    return Config(
        bot_token="token",
        openai_api_key=None,
        openai_stt_model="whisper-1",
        openai_llm_model="gpt-4o",
        debug_invoice_transparency=False,
        db_path=tmp_path / "db.sqlite",
        storage_dir=tmp_path / "storage",
        admin_telegram_user_ids=frozenset({ADMIN_ID}),
    )


def gmail_config():
    return SimpleNamespace(
        enabled=True,
        target_workspace_id="workspace-zevs",
        expected_email="office@example.test",
        client_id="client-id",
        public_redirect_uri="https://zevsflow.sk/oauth/google/integration/callback",
        token_crypto_secret="not-used-by-test",
    )


def _patch(monkeypatch, service: Service) -> None:
    monkeypatch.setattr(gmail_settings, "is_admin_telegram_user", lambda *_: True)
    monkeypatch.setattr(gmail_settings, "load_google_gmail_config", gmail_config)
    monkeypatch.setattr(gmail_settings, "WorkspaceContextService", WorkspaceService)
    monkeypatch.setattr(gmail_settings, "_service", lambda *_: service)


def test_non_admin_connect_has_no_setup_side_effect(tmp_path, monkeypatch) -> None:
    message = Message(user_id=999)
    monkeypatch.setattr(gmail_settings, "is_admin_telegram_user", lambda *_: False)
    monkeypatch.setattr(
        gmail_settings,
        "load_google_gmail_config",
        lambda: (_ for _ in ()).throw(AssertionError("must not load Gmail config")),
    )

    asyncio.run(gmail_settings.cmd_gmail_connect(message, config(tmp_path)))

    assert message.answers == [gmail_settings.ADMIN_ONLY]


def test_admin_connect_status_and_disconnect_are_bounded(
    tmp_path, monkeypatch
) -> None:
    service = Service()
    _patch(monkeypatch, service)
    cfg = config(tmp_path)

    connect = Message()
    asyncio.run(gmail_settings.cmd_gmail_connect(connect, cfg))
    assert "https://accounts.google.com/" in connect.answers[0]
    assert "Zevs &lt;b&gt;x&lt;/b&gt;" in connect.answers[0]
    assert "refresh_token" not in connect.answers[0]

    status = Message()
    asyncio.run(gmail_settings.cmd_gmail_status(status, cfg))
    assert "office@example.test" in status.answers[0]
    assert "Zevs &lt;b&gt;x&lt;/b&gt;" in status.answers[0]
    assert "spracovanie obsahu: nepodporované" in status.answers[0]
    assert "token" not in status.answers[0].lower()
    assert "message_id" not in status.answers[0]

    disconnect = Message()
    asyncio.run(gmail_settings.cmd_gmail_disconnect(disconnect, cfg))
    assert service.disconnected is True
    assert "nevymazali" in disconnect.answers[0]
