from __future__ import annotations

import base64
import json
import sqlite3

import pytest

from bot.services.gmail_readonly_adapter import (
    GmailReadonlyAdapter,
    GmailReadonlyNeedsReauth,
)
from bot.services.gmail_statement_collector import (
    GmailStatementCollector,
    GmailStatementPolicy,
    GmailStatementStore,
)
from bot.services.workspace_context import WorkspaceContext


class Transport:
    def __init__(self, message):
        self.message = message
        self.list_calls = []
        self.downloads = 0

    def list_messages(self, **kwargs):
        self.list_calls.append(kwargs)
        return (("message-1",), None)

    def get_message(self, message_id):
        assert message_id == "message-1"
        return self.message

    def get_attachment(self, message_id, attachment_id):
        self.downloads += 1
        assert (message_id, attachment_id) == ("message-1", "attachment-1")
        return base64.urlsafe_b64encode(b"statement-one").decode()


def message_payload():
    return {
        "id": "message-1",
        "threadId": "thread-1",
        "internalDate": "1785402000000",
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": "bank@example.test"},
                {"name": "Subject", "value": "Statement"},
            ],
            "parts": [
                {
                    "partId": "0",
                    "filename": "",
                    "mimeType": "text/plain",
                    "body": {
                        "data": base64.urlsafe_b64encode(b"private body").decode()
                    },
                },
                {
                    "partId": "1",
                    "filename": "statement.pdf",
                    "mimeType": "application/pdf",
                    "body": {"attachmentId": "attachment-1", "size": 13},
                },
                {
                    "partId": "2",
                    "filename": "inline.csv",
                    "mimeType": "text/csv",
                    "body": {
                        "data": base64.urlsafe_b64encode(b"a,b\n1,2").decode(),
                        "size": 7,
                    },
                },
            ],
        },
    }


def policy():
    return GmailStatementPolicy(
        maximum_bytes=1024,
        allowed_mime_types=frozenset({"application/pdf", "text/csv"}),
        allowed_extensions=frozenset({".pdf", ".csv"}),
    )


def workspace():
    return WorkspaceContext(
        actor_telegram_id=42,
        workspace_id="workspace-zevs",
        workspace_display_name="Zevs",
        storage_key="zevs",
        drive_folder_name="Zevs",
        membership_role="owner",
        supplier_id=1,
    )


def test_nested_mime_attachment_and_inline_are_bounded():
    transport = Transport(message_payload())
    adapter = GmailReadonlyAdapter(
        transport, trusted_query="has:attachment newer_than:30d", batch_size=10
    )
    assert adapter.list_message_ids() == ("message-1",)
    assert transport.list_calls[0]["query"] == "has:attachment newer_than:30d"
    candidates = adapter.attachment_candidates("message-1")
    assert [candidate.source_attachment_key for candidate in candidates] == [
        "attachment-1",
        "inline:2",
    ]
    assert all("private body" not in repr(candidate) for candidate in candidates)
    assert adapter.download(candidates[0], maximum=1024) == b"statement-one"
    assert adapter.download(candidates[1], maximum=1024) == b"a,b\n1,2"


def test_atomic_store_source_and_content_dedup(tmp_path):
    store = GmailStatementStore(tmp_path / "db.sqlite", tmp_path / "storage")
    store.ensure_schema()
    adapter = GmailReadonlyAdapter(
        Transport(message_payload()),
        trusted_query="has:attachment",
        batch_size=10,
    )
    first_candidate = adapter.attachment_candidates("message-1")[0]
    first = store.store(
        workspace=workspace(),
        connection_id="connection",
        candidate=first_candidate,
        content=b"same content",
        policy=policy(),
    )
    assert first.status == "stored"
    assert first.local_original_path is not None
    assert first.local_metadata_path is not None
    metadata = json.loads(open(first.local_metadata_path, encoding="utf-8").read())
    assert metadata["parse_status"] == "deferred"
    assert "private body" not in json.dumps(metadata)

    source_duplicate = store.store(
        workspace=workspace(),
        connection_id="connection",
        candidate=first_candidate,
        content=b"same content",
        policy=policy(),
    )
    assert source_duplicate.status == "duplicate_source"

    inline_candidate = adapter.attachment_candidates("message-1")[1]
    content_duplicate = store.store(
        workspace=workspace(),
        connection_id="connection",
        candidate=inline_candidate,
        content=b"same content",
        policy=policy(),
    )
    assert content_duplicate.status == "duplicate_content"
    assert content_duplicate.duplicate_of_import_id == first.import_id
    assert content_duplicate.local_original_path == first.local_original_path
    with sqlite3.connect(tmp_path / "db.sqlite") as connection:
        rows = connection.execute(
            "SELECT collection_status, parse_status, COUNT(*) "
            "FROM gmail_statement_imports GROUP BY collection_status, parse_status"
        ).fetchall()
    assert rows == [("stored", "deferred", 2)]

class ReauthAdapter:
    def list_message_ids(self):
        return ("message-1",)

    def attachment_candidates(self, message_id):
        raise GmailReadonlyNeedsReauth("gmail_needs_reauth")


def test_needs_reauth_is_not_swallowed_by_per_message_isolation(tmp_path):
    collector = GmailStatementCollector(
        adapter=ReauthAdapter(),
        store=GmailStatementStore(tmp_path / "db.sqlite", tmp_path / "storage"),
        resolve_workspace=lambda workspace_id: workspace(),
        workspace_id="workspace-zevs",
        connection_id="connection",
        policy=policy(),
    )

    with pytest.raises(GmailReadonlyNeedsReauth, match="gmail_needs_reauth"):
        collector.run_once()

def test_crash_after_atomic_promote_recovers_same_import_without_rewrite(tmp_path):
    store = GmailStatementStore(tmp_path / "db.sqlite", tmp_path / "storage")
    adapter = GmailReadonlyAdapter(
        Transport(message_payload()), trusted_query="has:attachment", batch_size=10
    )
    candidate = adapter.attachment_candidates("message-1")[0]
    first = store.store(
        workspace=workspace(),
        connection_id="connection",
        candidate=candidate,
        content=b"same content",
        policy=policy(),
    )
    original = first.local_original_path
    with sqlite3.connect(tmp_path / "db.sqlite") as connection:
        connection.execute(
            "UPDATE gmail_statement_imports SET collection_status='downloading' "
            "WHERE import_id=?",
            (first.import_id,),
        )
        connection.commit()

    recovered = store.store(
        workspace=workspace(),
        connection_id="connection",
        candidate=candidate,
        content=b"same content",
        policy=policy(),
    )

    assert recovered.import_id == first.import_id
    assert recovered.status == "stored"
    assert recovered.local_original_path == original
    with sqlite3.connect(tmp_path / "db.sqlite") as connection:
        status, attempts = connection.execute(
            "SELECT collection_status, attempt_count FROM gmail_statement_imports "
            "WHERE import_id=?",
            (first.import_id,),
        ).fetchone()
    assert (status, attempts) == ("stored", 2)
