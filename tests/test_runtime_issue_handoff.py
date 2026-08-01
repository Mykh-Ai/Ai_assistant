from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
import hashlib
import json
import sqlite3

import pytest

from bot.services import db
from bot.services.db import init_db
from bot.services.runtime_issue import RuntimeIssueCaptureInput, RuntimeIssueService
from bot.services.runtime_issue_handoff import (
    RuntimeIssueHandoffConflict,
    RuntimeIssueHandoffInvalid,
    RuntimeIssueHandoffService,
    canonical_manifest_digest,
)


NOW = datetime(2026, 7, 29, 8, 0, tzinfo=UTC)


def _capture(db_path, *, update_id: int, description: str = 'Unicode chyba žltý účet') -> str:
    result = RuntimeIssueService(db_path).capture(
        RuntimeIssueCaptureInput(
            description=description,
            actor_telegram_id=100,
            telegram_update_id=update_id,
            telegram_message_id=update_id + 1000,
            telegram_chat_id=200,
            workspace_id=None,
            workspace_resolution_reason='no_active_workspace',
            source_channel='text',
            active_fsm_state=None,
            active_fsm_data={},
            reported_build_sha=None,
            build_sha_status='unavailable',
        )
    )
    return result.record.issue_id


def _service(db_path, *, now=NOW, tokens=None):
    token_values = iter(tokens or ['A' * 43, 'B' * 43, 'C' * 43])
    handoff_ids = iter(
        [
            'RH-20260729-ABCDEF123456',
            'RH-20260729-ABCDEF123457',
            'RH-20260729-ABCDEF123458',
        ]
    )
    return RuntimeIssueHandoffService(
        db_path,
        clock=lambda: now,
        token_factory=lambda: next(token_values),
        handoff_id_factory=lambda _: next(handoff_ids),
    )


def test_additive_idempotent_schema_and_unknown_optional_column(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            'ALTER TABLE runtime_issue_handoffs ADD COLUMN future_note TEXT'
        )
        connection.commit()
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        db.validate_runtime_issue_handoff_schema(connection)
        assert 'future_note' in {
            row[1] for row in connection.execute(
                "PRAGMA table_info('runtime_issue_handoffs')"
            )
        }


@pytest.mark.parametrize(
    'schema',
    [
        db.RUNTIME_ISSUE_HANDOFF_SCHEMA.replace('issue_id TEXT NOT NULL UNIQUE,', ''),
        db.RUNTIME_ISSUE_HANDOFF_SCHEMA.replace(
            'attempt_count INTEGER NOT NULL', 'attempt_count TEXT NOT NULL'
        ),
        db.RUNTIME_ISSUE_HANDOFF_SCHEMA.replace(
            'CHECK (attempt_count > 0)', 'CHECK (attempt_count >= 0)'
        ),
    ],
)
def test_incompatible_owned_schema_fails_closed(tmp_path, schema):
    db_path = tmp_path / 'db.sqlite'
    with sqlite3.connect(db_path) as connection:
        connection.execute(schema)
        connection.execute(
            'CREATE INDEX IF NOT EXISTS idx_runtime_issue_handoffs_status_lease_until '
            'ON runtime_issue_handoffs (status, lease_until)'
        )
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info('runtime_issue_handoffs')"
            )
        }
        if 'issue_id' in columns:
            connection.execute(
                'CREATE INDEX IF NOT EXISTS idx_runtime_issue_handoffs_issue_status '
                'ON runtime_issue_handoffs (issue_id, status)'
            )
        with pytest.raises(RuntimeError):
            db.validate_runtime_issue_handoff_schema(connection)


@pytest.mark.parametrize(
    'schema',
    [
        db.RUNTIME_ISSUE_HANDOFF_SCHEMA.replace(
            'schema_version INTEGER NOT NULL DEFAULT 1',
            'schema_version INTEGER NOT NULL DEFAULT 2',
        ),
        db.RUNTIME_ISSUE_HANDOFF_SCHEMA.replace(
            'issue_id TEXT NOT NULL UNIQUE,',
            'issue_id TEXT NOT NULL,',
        ),
    ],
)
def test_incompatible_default_or_unique_constraint_fails_closed(tmp_path, schema):
    db_path = tmp_path / 'db.sqlite'
    with sqlite3.connect(db_path) as connection:
        connection.execute(schema)
        connection.execute(
            'CREATE INDEX idx_runtime_issue_handoffs_status_lease_until '
            'ON runtime_issue_handoffs (status, lease_until)'
        )
        connection.execute(
            'CREATE INDEX idx_runtime_issue_handoffs_issue_status '
            'ON runtime_issue_handoffs (issue_id, status)'
        )
        with pytest.raises(RuntimeError):
            db.validate_runtime_issue_handoff_schema(connection)


def test_missing_or_incompatible_owned_index_fails_closed(tmp_path):
    for mode in ('missing', 'wrong_shape'):
        db_path = tmp_path / f'{mode}.sqlite'
        init_db(db_path)
        with sqlite3.connect(db_path) as connection:
            connection.execute('DROP INDEX idx_runtime_issue_handoffs_issue_status')
            if mode == 'wrong_shape':
                connection.execute(
                    'CREATE INDEX idx_runtime_issue_handoffs_issue_status '
                    'ON runtime_issue_handoffs (status, issue_id)'
                )
            with pytest.raises(RuntimeError):
                db.validate_runtime_issue_handoff_schema(connection)


def test_bootstrap_preserves_existing_schema_rows_and_identifiers(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    with sqlite3.connect(db_path) as connection:
        connection.execute('CREATE TABLE sentinel (id TEXT PRIMARY KEY, value TEXT)')
        connection.execute("INSERT INTO sentinel VALUES ('S-1', 'unchanged')")
        before = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'sentinel'"
        ).fetchone()[0]
        connection.commit()
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        after = connection.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'sentinel'"
        ).fetchone()[0]
        assert after == before
        assert connection.execute('SELECT id, value FROM sentinel').fetchall() == [
            ('S-1', 'unchanged')
        ]


def test_bootstrap_preserves_all_preexisting_objects_and_rows(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    issue_id = _capture(db_path, update_id=9)
    with sqlite3.connect(db_path) as connection:
        connection.execute('DROP TABLE runtime_issue_handoffs')
        connection.execute(
            'CREATE TABLE migration_sentinel (id TEXT PRIMARY KEY, value TEXT NOT NULL)'
        )
        connection.execute(
            'CREATE INDEX idx_migration_sentinel_value ON migration_sentinel (value)'
        )
        connection.execute(
            'CREATE TRIGGER trg_migration_sentinel_no_delete '
            'BEFORE DELETE ON migration_sentinel BEGIN SELECT RAISE(ABORT, "preserved"); END'
        )
        connection.execute(
            "INSERT INTO migration_sentinel (id, value) VALUES ('S-1', 'unchanged')"
        )
        connection.commit()
        before_objects = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' ORDER BY type, name"
        ).fetchall()
        table_names = [
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            )
        ]
        before_rows = {
            name: connection.execute(
                f'SELECT * FROM "{name}" ORDER BY rowid'
            ).fetchall()
            for name in table_names
        }
    with sqlite3.connect(db_path) as connection:
        db._bootstrap_runtime_issue_handoff_table(connection)
        connection.commit()
        after_objects = connection.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_%' "
            "AND tbl_name != 'runtime_issue_handoffs' "
            "ORDER BY type, name"
        ).fetchall()
        after_rows = {
            name: connection.execute(
                f'SELECT * FROM "{name}" ORDER BY rowid'
            ).fetchall()
            for name in table_names
        }
        assert after_objects == before_objects
        assert after_rows == before_rows
        assert connection.execute(
            'SELECT issue_id FROM runtime_issues WHERE issue_id = ?',
            (issue_id,),
        ).fetchone() == (issue_id,)


def test_take_next_oldest_first_limit_empty_and_no_stage1_mutation(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    newer = _capture(db_path, update_id=2, description='Druhé hlásenie je novšie')
    older = _capture(db_path, update_id=1, description='Prvé hlásenie je staršie')
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE runtime_issues SET reported_at = '2026-07-29T07:00:00+00:00' "
            'WHERE issue_id = ?',
            (older,),
        )
        before = connection.execute(
            'SELECT * FROM runtime_issues ORDER BY issue_id'
        ).fetchall()
        connection.commit()
    service = _service(db_path, tokens=['A' * 43, 'B' * 43])
    result = service.take_next(limit=2)
    assert [item['issue']['issue_id'] for item in result] == [older, newer]
    assert service.take_next(limit=1) == []
    with sqlite3.connect(db_path) as connection:
        after = connection.execute(
            'SELECT * FROM runtime_issues ORDER BY issue_id'
        ).fetchall()
    assert after == before


@pytest.mark.parametrize('limit', [0, 4, -1])
def test_limit_is_hard_bounded(tmp_path, limit):
    init_db(tmp_path / 'db.sqlite')
    with pytest.raises(RuntimeIssueHandoffInvalid):
        _service(tmp_path / 'db.sqlite').take_next(limit=limit)


def test_concurrent_workers_do_not_lease_same_issue(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    issue_id = _capture(db_path, update_id=1)

    def take(token):
        return _service(db_path, tokens=[token]).take_next(limit=1)

    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(take, ['A' * 43, 'B' * 43]))
    leased = [item for batch in batches for item in batch]
    assert len(leased) == 1
    assert leased[0]['issue']['issue_id'] == issue_id


def test_redelivery_stable_receipt_new_token_and_old_token_cannot_claim(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    _capture(db_path, update_id=1)
    first = _service(db_path, tokens=['A' * 43]).take_next(limit=1)[0]
    retry_service = _service(
        db_path,
        now=NOW + timedelta(minutes=61),
        tokens=['B' * 43],
    )
    second = retry_service.take_next(limit=1)[0]
    assert second['handoff_id'] == first['handoff_id']
    assert second['manifest_digest'] == first['manifest_digest']
    assert second['lease_token'] != first['lease_token']
    with pytest.raises(RuntimeIssueHandoffConflict, match='handoff_token_mismatch'):
        retry_service.claim(
            handoff_id=second['handoff_id'],
            raw_token=first['lease_token'],
            manifest_digest=second['manifest_digest'],
        )
    result = retry_service.claim(
        handoff_id=second['handoff_id'],
        raw_token=second['lease_token'],
        manifest_digest=second['manifest_digest'],
    )
    assert result.status == 'acknowledged'


def test_claim_reuses_existing_columns_without_github_and_is_idempotent(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    _capture(db_path, update_id=1)
    service = _service(db_path)
    item = service.take_next(limit=1)[0]
    result = service.claim(
        handoff_id=item['handoff_id'],
        raw_token=item['lease_token'],
        manifest_digest=item['manifest_digest'],
    )
    repeated = service.claim(
        handoff_id=item['handoff_id'],
        raw_token=item['lease_token'],
        manifest_digest=item['manifest_digest'],
    )
    assert result.status == 'acknowledged'
    assert result.idempotent is False
    assert repeated.idempotent is True
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            'SELECT status, workshop_branch, workshop_commit_sha, acknowledged_at '
            'FROM runtime_issue_handoffs'
        ).fetchone()
    assert row[0] == 'acknowledged'
    assert row[1] is None
    assert row[2] is None
    assert row[3] == NOW.isoformat()
    assert service.take_next(limit=1) == []


@pytest.mark.parametrize(
    ('field', 'value', 'error'),
    [
        ('handoff_id', 'invalid', 'handoff_id_invalid'),
        ('manifest_digest', 'invalid', 'manifest_digest_invalid'),
        ('raw_token', 'B' * 43, 'handoff_token_mismatch'),
        ('manifest_digest', 'sha256:' + 'b' * 64, 'handoff_digest_mismatch'),
    ],
)
def test_claim_rejections_do_not_mutate_handoff(tmp_path, field, value, error):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    _capture(db_path, update_id=1)
    service = _service(db_path)
    item = service.take_next(limit=1)[0]
    values = {
        'handoff_id': item['handoff_id'],
        'raw_token': item['lease_token'],
        'manifest_digest': item['manifest_digest'],
    }
    values[field] = value
    with sqlite3.connect(db_path) as connection:
        before = connection.execute(
            'SELECT * FROM runtime_issue_handoffs'
        ).fetchone()
    with pytest.raises((RuntimeIssueHandoffInvalid, RuntimeIssueHandoffConflict), match=error):
        service.claim(**values)
    with sqlite3.connect(db_path) as connection:
        after = connection.execute(
            'SELECT * FROM runtime_issue_handoffs'
        ).fetchone()
    assert after == before


def test_expired_lease_cannot_be_claimed_until_redelivery(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    _capture(db_path, update_id=1)
    item = _service(db_path).take_next(limit=1)[0]
    expired = _service(db_path, now=NOW + timedelta(minutes=61))
    with pytest.raises(RuntimeIssueHandoffConflict, match='handoff_lease_expired'):
        expired.claim(
            handoff_id=item['handoff_id'],
            raw_token=item['lease_token'],
            manifest_digest=item['manifest_digest'],
        )


def test_legacy_acknowledged_row_is_preserved_as_terminal_delivery_fact(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    _capture(db_path, update_id=1)
    service = _service(db_path)
    item = service.take_next(limit=1)[0]
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE runtime_issue_handoffs SET status = 'acknowledged', "
            'workshop_branch = ?, workshop_commit_sha = ?, acknowledged_at = ?',
            ('maintenance/runtime-issue-workshop', 'a' * 40, NOW.isoformat()),
        )
        connection.commit()
    result = service.claim(
        handoff_id=item['handoff_id'],
        raw_token=item['lease_token'],
        manifest_digest=item['manifest_digest'],
    )
    assert result.idempotent is True
    assert service.take_next(limit=1) == []


def test_conflicting_repeat_and_reserved_reconciled_unreachable(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    _capture(db_path, update_id=1)
    service = _service(db_path)
    item = service.take_next(limit=1)[0]
    service.claim(
        handoff_id=item['handoff_id'],
        raw_token=item['lease_token'],
        manifest_digest=item['manifest_digest'],
    )
    with pytest.raises(RuntimeIssueHandoffConflict, match='handoff_claim_conflict'):
        service.claim(
            handoff_id=item['handoff_id'],
            raw_token='B' * 43,
            manifest_digest=item['manifest_digest'],
        )

    other_db = tmp_path / 'other.sqlite'
    init_db(other_db)
    _capture(other_db, update_id=2)
    other = _service(other_db)
    leased = other.take_next(limit=1)[0]
    with sqlite3.connect(other_db) as connection:
        connection.execute(
            "UPDATE runtime_issue_handoffs SET status = 'reconciled'"
        )
        connection.commit()
    with pytest.raises(RuntimeIssueHandoffConflict, match='handoff_not_live'):
        other.claim(
            handoff_id=leased['handoff_id'],
            raw_token=leased['lease_token'],
            manifest_digest=leased['manifest_digest'],
        )
    assert other.take_next(limit=1) == []


def test_fsm_status_null_active_and_read_failed(tmp_path):
    db_path = tmp_path / 'db.sqlite'
    init_db(db_path)
    null_issue = _capture(db_path, update_id=1)
    active_issue = _capture(db_path, update_id=2)
    broken_issue = _capture(db_path, update_id=3)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "UPDATE runtime_issues SET active_fsm_state = 'Invoice:waiting', "
            "active_fsm_context_summary_json = '{}' WHERE issue_id = ?",
            (active_issue,),
        )
        connection.execute(
            "UPDATE runtime_issues SET active_fsm_context_summary_json = '{broken' "
            'WHERE issue_id = ?',
            (broken_issue,),
        )
        connection.commit()
    service = RuntimeIssueHandoffService(
        db_path,
        clock=lambda: NOW,
        token_factory=iter(['A' * 43, 'B' * 43, 'C' * 43]).__next__,
        handoff_id_factory=lambda now: (
            f'RH-20260729-{secrets.pop()}'
        ),
    )
    secrets = {'AAAAAAAAAAAA', 'BBBBBBBBBBBB', 'CCCCCCCCCCCC'}
    rows = service.take_next(limit=3)
    statuses = {
        item['issue']['issue_id']: item['issue']['fsm_context_status']
        for item in rows
    }
    assert statuses[null_issue] == 'not_active'
    assert statuses[active_issue] == 'active'
    assert statuses[broken_issue] == 'read_failed'


def test_canonical_digest_contract():
    first = {'z': 'žltý', 'a': {'b': 2, 'a': 1}}
    reordered = {'a': {'a': 1, 'b': 2}, 'z': 'žltý'}
    digest = canonical_manifest_digest(first)
    assert digest == canonical_manifest_digest(reordered)
    assert digest.startswith('sha256:') and len(digest) == 71
    durable = {
        'schema_version': 'runtime-issue-handoff-v1',
        'handoff_id': 'RH-20260729-ABCDEF123456',
        'issue': {'description': 'žltý účet'},
    }
    with_delivery = dict(durable, lease_token='secret', attempt_count=2)
    assert canonical_manifest_digest(durable) != canonical_manifest_digest(with_delivery)
    assert canonical_manifest_digest(durable) != canonical_manifest_digest(
        {**durable, 'issue': {'description': 'iný účet'}}
    )
    expected = hashlib.sha256(
        json.dumps(
            durable,
            sort_keys=True,
            separators=(',', ':'),
            ensure_ascii=False,
        ).encode('utf-8')
    ).hexdigest()
    assert canonical_manifest_digest(durable) == f'sha256:{expected}'
