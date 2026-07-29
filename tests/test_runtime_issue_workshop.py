from __future__ import annotations

from datetime import UTC, datetime
import json

import pytest

from bot.services.runtime_issue_workshop import (
    RuntimeIssueWorkshopError,
    bootstrap_workshop,
)


NOW = datetime(2026, 7, 29, tzinfo=UTC)


def test_absent_directory_creates_exact_empty_seed_and_repeats_idempotently(tmp_path):
    directory = tmp_path / 'workshop'
    first = bootstrap_workshop(directory, now=NOW)
    queue_path = directory / 'AUTOREPAIR_QUEUE.json'
    log_path = directory / 'AUTOREPAIR_LOG.md'
    before = (queue_path.read_bytes(), log_path.read_bytes())
    second = bootstrap_workshop(directory, now=NOW.replace(day=30))
    assert first == second
    assert (queue_path.read_bytes(), log_path.read_bytes()) == before
    queue = json.loads(queue_path.read_text())
    assert queue['schema_version'] == 'autorepair-workshop-v1'
    assert queue['workshop_branch'] == 'maintenance/runtime-issue-workshop'
    assert queue['source_issues'] == []
    assert queue['findings'] == []


def test_valid_nonempty_workshop_is_preserved(tmp_path):
    directory = tmp_path / 'workshop'
    bootstrap_workshop(directory, now=NOW)
    queue_path = directory / 'AUTOREPAIR_QUEUE.json'
    queue = json.loads(queue_path.read_text())
    queue['source_issues'].append({'issue_id': 'IR-verified'})
    queue_path.write_text(json.dumps(queue))
    log_path = directory / 'AUTOREPAIR_LOG.md'
    log_path.write_text(log_path.read_text() + '\nVerified receipt.\n')
    before = (queue_path.read_bytes(), log_path.read_bytes())
    bootstrap_workshop(directory, now=NOW)
    assert (queue_path.read_bytes(), log_path.read_bytes()) == before


@pytest.mark.parametrize('target', ['queue', 'log'])
def test_incompatible_file_fails_closed_without_overwrite(tmp_path, target):
    directory = tmp_path / 'workshop'
    bootstrap_workshop(directory, now=NOW)
    path = directory / (
        'AUTOREPAIR_QUEUE.json' if target == 'queue' else 'AUTOREPAIR_LOG.md'
    )
    path.write_text('incompatible')
    before = path.read_bytes()
    with pytest.raises(RuntimeIssueWorkshopError):
        bootstrap_workshop(directory, now=NOW)
    assert path.read_bytes() == before
