from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

import bot.services.gmail_statement_scheduler as scheduler
from bot.services.gmail_readonly_adapter import GmailReadonlyNeedsReauth
from bot.services.gmail_statement_collector import GmailStatementImportResult
from bot.services.gmail_statement_scheduler import (
    _bounded_query,
    _mark_reauth_notified,
    _notification_text,
    _reauth_notification_due,
)


NOW = datetime(2026, 7, 30, 12, 0, tzinfo=UTC)


def test_first_query_uses_bounded_initial_lookback() -> None:
    query = _bounded_query(
        "has:attachment",
        last_successful=None,
        initial_lookback_days=30,
        overlap_hours=24,
        now=NOW,
    )

    assert query == f"(has:attachment) after:{int(datetime(2026, 6, 30, 12, 0, tzinfo=UTC).timestamp())}"


def test_later_query_uses_bounded_overlap() -> None:
    query = _bounded_query(
        "from:bank@example.test has:attachment",
        last_successful="2026-07-30T10:00:00+00:00",
        initial_lookback_days=30,
        overlap_hours=24,
        now=NOW,
    )

    assert query.endswith(
        f"after:{int(datetime(2026, 7, 29, 10, 0, tzinfo=UTC).timestamp())}"
    )


def test_notification_is_bounded_and_does_not_claim_parsing() -> None:
    text = _notification_text(
        GmailStatementImportResult(
            import_id="import-1",
            status="stored",
            safe_display_filename="<b>statement</b>.pdf",
            size_bytes=123,
        )
    )

    assert "&lt;b&gt;statement&lt;/b&gt;.pdf" in text
    assert "<b>" not in text
    assert "123 B" in text
    assert "nebol parsovaný ani spárovaný" in text
    assert "message" not in text.lower()
    assert "token" not in text.lower()


def test_notification_reports_detected_archive_period() -> None:
    text = _notification_text(
        GmailStatementImportResult(
            import_id="import-1",
            status="stored",
            statement_period_status="detected",
            statement_period_year=2026,
            statement_period_month=6,
        )
    )

    assert "2026-06" in text
    assert "nebol parsovaný ani spárovaný" in text

def test_reauth_notification_is_cooldown_protected(tmp_path) -> None:
    db_path = tmp_path / "db.sqlite"
    assert _reauth_notification_due(
        db_path, "workspace-zevs", 3600, now=NOW
    ) is True
    _mark_reauth_notified(db_path, "workspace-zevs", now=NOW)
    assert _reauth_notification_due(
        db_path, "workspace-zevs", 3600, now=NOW
    ) is False
    assert _reauth_notification_due(
        db_path,
        "workspace-zevs",
        3600,
        now=datetime(2026, 7, 30, 13, 0, tzinfo=UTC),
    ) is True


def test_run_tick_returns_reauth_signal_after_marking_binding(
    monkeypatch, tmp_path
) -> None:
    gmail = SimpleNamespace(
        target_workspace_id="workspace-zevs",
        token_crypto_secret="unused",
        client_id="client",
        client_secret="secret",
        statement_query="has:attachment",
        batch_size=10,
        initial_lookback_days=30,
        overlap_hours=24,
        max_attachment_bytes=1024,
        allowed_mime_types=frozenset({"application/pdf"}),
        allowed_extensions=frozenset({".pdf"}),
    )
    workspace = SimpleNamespace(
        workspace_id="workspace-zevs",
        actor_telegram_id=123,
        storage_key="workspace-zevs",
        drive_folder_name="Zevs",
    )
    grant = SimpleNamespace(
        access_token="access",
        refresh_token="refresh",
        connection_id="grant-1",
        scopes=("https://www.googleapis.com/auth/gmail.readonly",),
    )

    class Runtime:
        marked: list[str] = []

        def load_active_grant(self, workspace_id):
            assert workspace_id == workspace.workspace_id
            return grant

        def last_successful_check(self, workspace_id):
            assert workspace_id == workspace.workspace_id
            return None

        def mark_needs_reauth(self, workspace_id):
            self.marked.append(workspace_id)

    runtime = Runtime()

    class Collector:
        def __init__(self, **kwargs):
            pass

        def run_once(self):
            raise GmailReadonlyNeedsReauth("gmail_needs_reauth")

    monkeypatch.setattr(scheduler, "load_google_gmail_config", lambda: gmail)
    monkeypatch.setattr(
        scheduler, "load_statement_pdf_open_password", lambda config: None
    )
    monkeypatch.setattr(
        scheduler,
        "WorkspaceContextService",
        lambda db_path: SimpleNamespace(
            resolve_for_background_workspace=lambda workspace_id: workspace
        ),
    )
    monkeypatch.setattr(scheduler, "FernetTokenCryptoProvider", lambda **kwargs: object())
    monkeypatch.setattr(
        scheduler, "GoogleGmailRuntimeService", lambda db_path, crypto: runtime
    )
    monkeypatch.setattr(
        scheduler, "GoogleAPIGmailReadonlyTransport", lambda **kwargs: object()
    )
    monkeypatch.setattr(scheduler, "GmailReadonlyAdapter", lambda *args, **kwargs: object())
    monkeypatch.setattr(scheduler, "GmailStatementStore", lambda *args: object())
    monkeypatch.setattr(scheduler, "GmailStatementCollector", Collector)

    config = SimpleNamespace(
        db_path=tmp_path / "db.sqlite",
        storage_dir=tmp_path / "storage",
        google_drive_enabled=False,
    )

    assert scheduler._run_tick(config) == ("needs_reauth", None, workspace)
    assert runtime.marked == [workspace.workspace_id]


def test_scheduler_notifies_once_then_sleeps_on_reauth(monkeypatch, tmp_path) -> None:
    gmail = SimpleNamespace(
        enabled=True,
        notification_cooldown_seconds=3600,
        check_interval_seconds=86400,
    )
    workspace = SimpleNamespace(workspace_id="workspace-zevs", actor_telegram_id=123)
    messages: list[tuple[int, str]] = []
    marked: list[str] = []

    class Bot:
        async def send_message(self, telegram_id, text):
            messages.append((telegram_id, text))

    async def stop_after_first_tick(seconds):
        assert seconds == gmail.check_interval_seconds
        raise asyncio.CancelledError

    monkeypatch.setattr(scheduler, "load_google_gmail_config", lambda: gmail)
    monkeypatch.setattr(
        scheduler,
        "_run_tick",
        lambda config: ("needs_reauth", None, workspace),
    )
    monkeypatch.setattr(scheduler, "_reauth_notification_due", lambda *args: True)
    monkeypatch.setattr(
        scheduler,
        "_mark_reauth_notified",
        lambda db_path, workspace_id: marked.append(workspace_id),
    )
    monkeypatch.setattr(scheduler.asyncio, "sleep", stop_after_first_tick)

    config = SimpleNamespace(db_path=tmp_path / "db.sqlite")
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(scheduler.run_gmail_statement_scheduler(bot=Bot(), config=config))

    assert len(messages) == 1
    assert messages[0][0] == 123
    assert "/gmail_connect" in messages[0][1]
    assert marked == [workspace.workspace_id]
