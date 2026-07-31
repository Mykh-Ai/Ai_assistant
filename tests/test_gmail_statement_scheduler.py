from __future__ import annotations

from datetime import UTC, datetime

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
