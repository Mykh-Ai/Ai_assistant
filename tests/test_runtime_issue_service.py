from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from bot.services import db
from bot.services.db import RUNTIME_ISSUE_SCHEMA, init_db
from bot.services.runtime_issue import (
    RuntimeIssueCaptureInput,
    RuntimeIssueService,
    RuntimeIssueUnsafeInput,
    sanitize_runtime_issue,
)


def _payload(
    *,
    description: str = 'Po potvrdení faktúry sa nezobrazila výsledná správa.',
    actor: int = 101,
    update: int = 501,
    message: int = 301,
    chat: int = 201,
    workspace: str | None = None,
    source: str = 'text',
    fsm_data: dict[str, object] | None = None,
) -> RuntimeIssueCaptureInput:
    return RuntimeIssueCaptureInput(
        description=description,
        actor_telegram_id=actor,
        telegram_update_id=update,
        telegram_message_id=message,
        telegram_chat_id=chat,
        workspace_id=workspace,
        workspace_resolution_reason=(
            'active_workspace' if workspace is not None else 'no_active_workspace'
        ),
        source_channel=source,
        active_fsm_state='InvoiceStates:waiting_input',
        active_fsm_data=fsm_data or {},
        reported_build_sha=None,
        build_sha_status='unavailable',
    )


def _service(tmp_path: Path) -> tuple[RuntimeIssueService, Path]:
    db_path = tmp_path / 'runtime-issue.db'
    init_db(db_path)
    return RuntimeIssueService(db_path), db_path


def test_insert_duplicate_and_distinct_delivery_have_stable_ids(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)

    first = service.capture(_payload())
    duplicate = service.capture(_payload())
    second_delivery = service.capture(_payload(update=502, message=302))

    assert first.duplicate is False
    assert first.record.issue_id.startswith('IR-')
    assert duplicate.duplicate is True
    assert duplicate.record.issue_id == first.record.issue_id
    assert second_delivery.duplicate is False
    assert second_delivery.record.issue_id != first.record.issue_id
    assert first.record.intake_status == 'new'
    assert first.record.schema_version == 1


def test_nullable_workspace_and_actor_workspace_isolation(tmp_path: Path) -> None:
    service, _ = _service(tmp_path)
    without_workspace = service.capture(_payload())
    with_workspace = service.capture(
        _payload(actor=102, update=601, message=401, workspace='workspace-b')
    )

    assert without_workspace.record.workspace_id is None
    assert without_workspace.record.workspace_resolution_reason == 'no_active_workspace'
    assert (
        service.get_for_actor(
            issue_id=with_workspace.record.issue_id,
            actor_telegram_id=101,
            workspace_id='workspace-b',
        )
        is None
    )
    assert (
        service.get_for_actor(
            issue_id=with_workspace.record.issue_id,
            actor_telegram_id=102,
            workspace_id='workspace-a',
        )
        is None
    )
    assert (
        service.get_for_actor(
            issue_id=with_workspace.record.issue_id,
            actor_telegram_id=102,
            workspace_id='workspace-b',
        )
        == with_workspace.record
    )


def test_sanitizer_redacts_secrets_paths_and_derives_title_after_redaction() -> None:
    sanitized = sanitize_runtime_issue(
        description=(
            'token=very-secret-value spadol handler pri /root/private/app.env\n'
            'Authorization: Bearer abc.def.ghi a password="hunter two" zostala v správe'
        ),
        active_fsm_data={
            'invoice_draft': {'customer': 'Sensitive Company'},
            'unrelated_record': {'iban': 'SK00 PRIVATE'},
        },
    )

    assert 'very-secret-value' not in sanitized.description
    assert 'abc.def.ghi' not in sanitized.description
    assert 'hunter two' not in sanitized.description
    assert '/root/private/app.env' not in sanitized.description
    assert sanitized.short_title in sanitized.description
    assert len(sanitized.short_title) <= 120
    assert sanitized.fsm_context_summary['present_contexts'] == ['invoice_draft_present']
    serialized = json.dumps(sanitized.fsm_context_summary)
    assert 'Sensitive Company' not in serialized
    assert 'SK00 PRIVATE' not in serialized
    assert set(sanitized.privacy_metadata['redaction_categories']) == {
        'authorization_header',
        'private_path',
        'secret_assignment',
    }


def test_sanitizer_bounds_size_and_rejects_unsafe_input_without_row(tmp_path: Path) -> None:
    service, db_path = _service(tmp_path)
    bounded = service.capture(_payload(description='Pozorovaný problém: ' + ('x' * 3000)))
    assert len(bounded.record.description) == 2000
    assert bounded.record.privacy_metadata['description_truncated'] is True

    with pytest.raises(RuntimeIssueUnsafeInput):
        service.capture(
            _payload(
                update=502,
                message=302,
                description='AAA=one\nBBB=two\nCCC=three\nbot prestal odpovedať',
            )
        )
    with sqlite3.connect(db_path) as connection:
        count = connection.execute(
            'SELECT count(*) FROM runtime_issues'
        ).fetchone()[0]
    assert count == 1


def test_transaction_rolls_back_on_insert_failure(tmp_path: Path) -> None:
    service, db_path = _service(tmp_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            "CREATE TRIGGER reject_runtime_issue BEFORE INSERT ON runtime_issues "
            "BEGIN SELECT RAISE(ABORT, 'forced'); END"
        )
    with pytest.raises(sqlite3.IntegrityError):
        service.capture(_payload())
    with sqlite3.connect(db_path) as connection:
        assert connection.execute(
            'SELECT count(*) FROM runtime_issues'
        ).fetchone()[0] == 0


def test_repeated_bootstrap_and_unknown_optional_column_are_compatible(tmp_path: Path) -> None:
    db_path = tmp_path / 'optional.db'
    schema = RUNTIME_ISSUE_SCHEMA.replace(
        '\n);',
        ',\n    future_optional_note TEXT\n);',
    )
    with sqlite3.connect(db_path) as connection:
        connection.execute(schema)
        connection.commit()

    with sqlite3.connect(db_path) as connection:
        db._bootstrap_runtime_issue_table(connection)
        connection.commit()
    init_db(db_path)
    result = RuntimeIssueService(db_path).capture(_payload())
    assert result.record.issue_id.startswith('IR-')


@pytest.mark.parametrize(
    'schema',
    [
        RUNTIME_ISSUE_SCHEMA.replace(
            '    description TEXT NOT NULL CHECK (length(description) BETWEEN 10 AND 2000),\n',
            '',
        ),
        RUNTIME_ISSUE_SCHEMA.replace(
            '    telegram_update_id INTEGER NOT NULL,',
            '    telegram_update_id TEXT NOT NULL,',
        ),
        RUNTIME_ISSUE_SCHEMA.replace(
            "CHECK (intake_status = 'new')",
            "CHECK (intake_status IN ('new', 'claimed'))",
        ),
    ],
)
def test_incompatible_required_schema_fails_safely(tmp_path: Path, schema: str) -> None:
    db_path = tmp_path / 'incompatible.db'
    with sqlite3.connect(db_path) as connection:
        connection.execute(schema)
        connection.commit()
    with pytest.raises(RuntimeError, match='Incompatible local schema'):
        init_db(db_path)


def _database_snapshot(
    connection: sqlite3.Connection,
) -> tuple[list[tuple], dict[str, list[tuple]]]:
    schema = connection.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' AND tbl_name != 'runtime_issues' "
        "ORDER BY type, name"
    ).fetchall()
    table_names = [
        str(row[1])
        for row in schema
        if row[0] == 'table'
    ]
    data: dict[str, list[tuple]] = {}
    for table_name in table_names:
        columns = [
            str(row[1])
            for row in connection.execute(
                f'PRAGMA table_info("{table_name}")'
            ).fetchall()
        ]
        quoted_columns = ', '.join(f'"{column}"' for column in columns)
        data[table_name] = connection.execute(
            f'SELECT {quoted_columns} FROM "{table_name}" ORDER BY rowid'
        ).fetchall()
    return schema, data


def test_additive_bootstrap_preserves_all_existing_business_tables_and_rows(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / 'pre-issue.db'
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute('DROP TABLE runtime_issues')
        connection.execute(
            "INSERT INTO authorized_users "
            "(telegram_id, role, status, created_at, approved_by) "
            "VALUES (777, 'user', 'active', '2026-07-28T00:00:00+00:00', 1)"
        )
        connection.commit()
        before = _database_snapshot(connection)

    with sqlite3.connect(db_path) as connection:
        db._bootstrap_runtime_issue_table(connection)
        connection.commit()

    with sqlite3.connect(db_path) as connection:
        after = _database_snapshot(connection)
        issue_table_count = connection.execute(
            "SELECT count(*) FROM sqlite_master "
            "WHERE type = 'table' AND name = 'runtime_issues'"
        ).fetchone()[0]

    assert after == before
    assert issue_table_count == 1


def test_runtime_issue_sql_uses_named_columns_and_row_mapping() -> None:
    source = Path('bot/services/runtime_issue.py').read_text(encoding='utf-8')
    assert 'SELECT *' not in source.upper()
    assert 'sqlite3.Row' in source
    assert "row['issue_id']" in source
