from __future__ import annotations

from datetime import UTC, datetime
import sqlite3

import pytest

from bot.services.db import init_db
from bot.services.runtime_issue import RuntimeIssueCaptureInput, RuntimeIssueService
from bot.services.runtime_issue_evidence import (
    MAX_EXCERPT,
    RecordedEvidenceLine,
    RuntimeIssueEvidenceInvalid,
    RuntimeIssueEvidenceService,
)
from bot.services.runtime_issue_handoff import RuntimeIssueHandoffService, WORKSHOP_BRANCH


NOW = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)


class FakeSource:
    def __init__(self, lines=(), error=None):
        self.lines = list(lines)
        self.error = error
        self.calls = []

    def read(self, *, start, end):
        self.calls.append((start, end))
        if self.error:
            raise self.error
        return self.lines


def _acknowledged(tmp_path, *, workspace_id=None):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    issue = RuntimeIssueService(db_path).capture(
        RuntimeIssueCaptureInput(
            description='Provider vrátil chybu pri spracovaní dokladu',
            actor_telegram_id=1,
            telegram_update_id=123,
            telegram_message_id=456,
            telegram_chat_id=2,
            workspace_id=workspace_id,
            workspace_resolution_reason=(
                'active_workspace' if workspace_id else 'no_active_workspace'
            ),
            source_channel='voice',
            active_fsm_state=None,
            active_fsm_data={},
            reported_build_sha=None,
            build_sha_status='unavailable',
        )
    ).record
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'UPDATE runtime_issues SET reported_at = ? WHERE issue_id = ?',
            (NOW.isoformat(), issue.issue_id),
        )
        connection.commit()
    handoff_service = RuntimeIssueHandoffService(
        db_path,
        clock=lambda: NOW,
        token_factory=lambda: 'A' * 43,
        handoff_id_factory=lambda now: 'RH-20260729-ABCDEF123456',
    )
    manifest = handoff_service.take_next(limit=1)[0]
    handoff_service.acknowledge(
        handoff_id=manifest['handoff_id'],
        raw_token=manifest['lease_token'],
        manifest_digest=manifest['manifest_digest'],
        workshop_branch=WORKSHOP_BRANCH,
        workshop_commit_sha='a' * 40,
        verifier=lambda branch, commit: True,
    )
    return db_path, issue.issue_id, manifest['handoff_id']


def test_collects_correlated_categories_and_global_docker_fact(tmp_path):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path)
    source = FakeSource(
        [
            RecordedEvidenceLine(NOW, 'STT update=123 transcript error token=secret'),
            RecordedEvidenceLine(NOW, 'provider timeout message=456 /root/private/file'),
            RecordedEvidenceLine(NOW, 'network connection timeout update=123'),
            RecordedEvidenceLine(NOW, 'docker container health restart'),
            RecordedEvidenceLine(NOW, 'provider timeout for unrelated tenant'),
        ]
    )
    result = RuntimeIssueEvidenceService(db_path, source=source).collect(
        issue_id=issue_id,
        handoff_id=handoff_id,
    )
    categories = {item['category']: item for item in result['categories']}
    assert all(categories[name]['status'] == 'available' for name in categories)
    assert len(categories['provider']['items']) == 1
    combined = str(result)
    assert 'secret' not in combined
    assert '/root/private/file' not in combined
    assert source.calls[0][1] - source.calls[0][0] == __import__('datetime').timedelta(
        minutes=30
    )


def test_missing_evidence_is_truthful_and_null_workspace_is_valid(tmp_path):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path, workspace_id=None)
    result = RuntimeIssueEvidenceService(db_path, source=FakeSource()).collect(
        issue_id=issue_id,
        handoff_id=handoff_id,
    )
    assert {category['status'] for category in result['categories']} == {'unavailable'}


def test_source_error_is_bounded(tmp_path):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path)
    result = RuntimeIssueEvidenceService(
        db_path, source=FakeSource(error=TimeoutError('private details'))
    ).collect(issue_id=issue_id, handoff_id=handoff_id)
    assert {category['status'] for category in result['categories']} == {'source_error'}
    assert 'private details' not in str(result)


def test_unacknowledged_and_cross_issue_fail_closed(tmp_path):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path)
    with pytest.raises(RuntimeIssueEvidenceInvalid):
        RuntimeIssueEvidenceService(db_path, source=FakeSource()).collect(
            issue_id='IR-20260729-FFFFFFFFFFFF',
            handoff_id=handoff_id,
        )
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE runtime_issue_handoffs SET status = 'leased' WHERE handoff_id = ?",
            (handoff_id,),
        )
        connection.commit()
    with pytest.raises(RuntimeIssueEvidenceInvalid):
        RuntimeIssueEvidenceService(db_path, source=FakeSource()).collect(
            issue_id=issue_id,
            handoff_id=handoff_id,
        )


def test_excerpt_item_and_input_limits(tmp_path):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path)
    lines = [
        RecordedEvidenceLine(NOW, f'provider timeout update=123 {"x" * 800}')
        for _ in range(600)
    ]
    result = RuntimeIssueEvidenceService(db_path, source=FakeSource(lines)).collect(
        issue_id=issue_id,
        handoff_id=handoff_id,
    )
    items = [item for category in result['categories'] for item in category['items']]
    assert len(items) == 20
    assert all(len(item['sanitized_excerpt']) <= MAX_EXCERPT for item in items)
