from __future__ import annotations

from datetime import UTC, datetime
import sqlite3
import subprocess

import pytest

from bot.services.db import init_db
from bot.services.runtime_issue import RuntimeIssueCaptureInput, RuntimeIssueService
from bot.services.runtime_issue_evidence import (
    MAX_EXCERPT,
    MAX_RAW_BYTES,
    MAX_RAW_LINES,
    FixedDockerLogSource,
    RecordedEvidenceLine,
    RuntimeIssueEvidenceInvalid,
    RuntimeIssueEvidenceService,
)
from bot.services.runtime_issue_handoff import RuntimeIssueHandoffService


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
    handoff_service.claim(
        handoff_id=manifest['handoff_id'],
        raw_token=manifest['lease_token'],
        manifest_digest=manifest['manifest_digest'],
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


def test_fixed_docker_source_collects_stderr_only_python_logs():
    line = '2026-07-29T08:00:00Z provider timeout update_id=123'

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout='', stderr=f'{line}\n')

    records = FixedDockerLogSource(runner=runner).read(start=NOW, end=NOW)
    assert records == [
        RecordedEvidenceLine(NOW, 'provider timeout update_id=123')
    ]


def test_fixed_docker_source_merges_streams_in_deterministic_timestamp_order():
    stdout = (
        '2026-07-29T08:00:02Z docker stdout later\n'
        '2026-07-29T08:00:01Z docker stdout same-time\n'
    )
    stderr = (
        '2026-07-29T08:00:00Z python stderr first\n'
        '2026-07-29T08:00:01Z python stderr same-time\n'
    )

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=stderr)

    records = FixedDockerLogSource(runner=runner).read(start=NOW, end=NOW)
    assert [record.text for record in records] == [
        'python stderr first',
        'docker stdout same-time',
        'python stderr same-time',
        'docker stdout later',
    ]


def test_fixed_docker_source_applies_one_combined_input_boundary():
    stdout = ''.join(
        f'2026-07-29T08:00:00Z docker stdout {index}\n'
        for index in range(MAX_RAW_LINES)
    )
    stderr = ''.join(
        f'2026-07-29T08:00:01Z python stderr {index}\n'
        for index in range(MAX_RAW_LINES)
    )

    def runner(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 0, stdout=stdout, stderr=stderr)

    records = FixedDockerLogSource(runner=runner).read(start=NOW, end=NOW)
    assert len(records) == MAX_RAW_LINES
    assert sum(
        len(
            f'{record.timestamp.isoformat()} {record.text}'.encode(
                'utf-8', errors='replace'
            )
        ) + 1
        for record in records
    ) <= MAX_RAW_BYTES

    large = 'x' * (MAX_RAW_BYTES // 2)

    def byte_runner(argv, **kwargs):
        return subprocess.CompletedProcess(
            argv,
            0,
            stdout=f'2026-07-29T08:00:00Z docker {large}\n',
            stderr=f'2026-07-29T08:00:01Z python {large}\n',
        )

    byte_bounded = FixedDockerLogSource(runner=byte_runner).read(
        start=NOW,
        end=NOW,
    )
    assert len(byte_bounded) == 1


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


@pytest.mark.parametrize(
    'line',
    [
        'provider timeout update_id=9123',
        'provider timeout update_id=1234',
        'provider timeout update_id=123abc',
        'provider timeout duration=123',
        'provider timeout HTTP 123',
        'provider timeout actor_telegram_id=999 update_id=123',
        'provider timeout workspace_id=OTHER update_id=123',
    ],
)
def test_numeric_correlation_rejects_substrings_unlabeled_values_and_other_tenant(
    tmp_path,
    line,
):
    db_path, issue_id, handoff_id = _acknowledged(
        tmp_path,
        workspace_id='WORKSPACE-1',
    )
    result = RuntimeIssueEvidenceService(
        db_path,
        source=FakeSource([RecordedEvidenceLine(NOW, line)]),
    ).collect(issue_id=issue_id, handoff_id=handoff_id)
    provider = next(
        category
        for category in result['categories']
        if category['category'] == 'provider'
    )
    assert provider == {
        'category': 'provider',
        'status': 'unavailable',
        'items': [],
    }


@pytest.mark.parametrize(
    'line',
    [
        'provider timeout update_id=123 message_id=999',
        'provider timeout update_id=999 message_id=456',
        'provider timeout update_id=123 update_id=999',
        'provider timeout message_id=456 message_id=888',
        'docker handler error update_id=999 customer_data=private',
        'docker customer_data=private',
        'container request handler failed',
        'health customer payload leaked',
    ],
)
def test_conflicting_identities_and_non_allowlisted_docker_facts_are_rejected(
    tmp_path,
    line,
):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path)
    result = RuntimeIssueEvidenceService(
        db_path,
        source=FakeSource([RecordedEvidenceLine(NOW, line)]),
    ).collect(issue_id=issue_id, handoff_id=handoff_id)
    assert all(category['status'] == 'unavailable' for category in result['categories'])


def test_global_docker_allowlist_and_correlated_tenant_docker_fact_are_preserved(
    tmp_path,
):
    db_path, issue_id, handoff_id = _acknowledged(tmp_path)
    result = RuntimeIssueEvidenceService(
        db_path,
        source=FakeSource(
            [
                RecordedEvidenceLine(NOW, 'docker container health restart'),
                RecordedEvidenceLine(
                    NOW,
                    'docker handler error update_id=123 customer_data=private',
                ),
            ]
        ),
    ).collect(issue_id=issue_id, handoff_id=handoff_id)
    docker = next(
        category
        for category in result['categories']
        if category['category'] == 'docker'
    )
    assert docker['status'] == 'available'
    assert len(docker['items']) == 2
    assert docker['items'][0]['correlation_ids'] == []
    assert docker['items'][1]['correlation_ids'] == ['update:123']
