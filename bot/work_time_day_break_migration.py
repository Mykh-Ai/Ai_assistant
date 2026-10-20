"""Explicit additive migration; runtime startup deliberately never invokes it."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sqlite3
from uuid import uuid4


_COLUMN = 'lunch_break_minutes_override'
_TABLES = ('work_time_days', 'work_time_events', 'work_time_settings')


def _readonly(path: Path):
    connection = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    connection.execute('PRAGMA query_only=ON')
    return connection


def _business_snapshot(connection):
    result = {}
    for table in _TABLES:
        columns = [row[1] for row in connection.execute(f'PRAGMA table_info({table})') if row[1] != _COLUMN]
        if not columns:
            raise RuntimeError('work_time_tables_missing')
        quoted = ','.join(f'"{column}"' for column in columns)
        rows = connection.execute(f'SELECT {quoted} FROM {table}').fetchall()
        result[table] = (columns, sorted(rows, key=repr))
    return result


def _audit(connection):
    business = _business_snapshot(connection)
    schema = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    fingerprint = hashlib.sha256(json.dumps([schema, business], sort_keys=True).encode()).hexdigest()
    ready = _COLUMN in [row[1] for row in connection.execute('PRAGMA table_info(work_time_days)')]
    mode_counts = dict(connection.execute('SELECT COALESCE(close_input_mode,\'legacy\'),COUNT(*) FROM work_time_days GROUP BY close_input_mode'))
    invalid_clocks = connection.execute("SELECT COUNT(*) FROM work_time_days WHERE start_time IS NOT NULL AND end_time IS NOT NULL AND end_time < start_time").fetchone()[0]
    opaque_net = connection.execute('SELECT COUNT(*) FROM work_time_days WHERE net_work_minutes_override IS NOT NULL').fetchone()[0]
    return {'fingerprint': fingerprint, 'schema_ready': ready, 'migration_required': not ready,
            'writes_performed': False, 'row_counts': {k: len(v[1]) for k,v in business.items()},
            'input_modes': mode_counts, 'reversed_clock_rows': invalid_clocks,
            'fixed_net_rows': opaque_net, 'business_digest': hashlib.sha256(json.dumps(business, sort_keys=True).encode()).hexdigest(),
            'integrity': connection.execute('PRAGMA integrity_check').fetchone()[0]}


def audit_day_break_schema(path: Path):
    with closing(_readonly(path)) as connection:
        return _audit(connection)


def apply_day_break_schema(path: Path, *, expected_fingerprint: str, backup_dir: Path, service_stopped: bool = False):
    """Caller must obtain operational approval and freeze writers first."""
    if not service_stopped:
        raise RuntimeError('migration_writer_freeze_confirmation_required')
    with closing(sqlite3.connect(path.resolve().as_uri() + '?mode=rw', uri=True)) as connection, connection:
        connection.execute('BEGIN IMMEDIATE')
        before = _audit(connection)
        if before['fingerprint'] != expected_fingerprint or before['integrity'] != 'ok':
            raise RuntimeError('migration_baseline_changed')
        if before['schema_ready']:
            raise RuntimeError('day_break_schema_already_ready')
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f'day-break-{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}.sqlite'
        with closing(_readonly(path)) as source, closing(sqlite3.connect(backup)) as destination:
            source.backup(destination)
        if audit_day_break_schema(backup)['fingerprint'] != expected_fingerprint:
            raise RuntimeError('migration_backup_verification_failed')
        connection.execute(f'ALTER TABLE work_time_days ADD COLUMN {_COLUMN} INTEGER CHECK ({_COLUMN} BETWEEN 0 AND 180)')
        after = _audit(connection)
        if after['business_digest'] != before['business_digest'] or after['integrity'] != 'ok':
            raise RuntimeError('migration_changed_business_rows')
        connection.commit()
        return {**after, 'writes_performed': True, 'backup_path': str(backup)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('audit', 'dry-run', 'apply'))
    parser.add_argument('--db-path', required=True, type=Path)
    parser.add_argument('--expected-fingerprint')
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--service-stopped', action='store_true')
    args = parser.parse_args()
    if args.mode == 'apply':
        if not args.expected_fingerprint or not args.backup_dir or not args.service_stopped:
            parser.error('apply requires --expected-fingerprint, --backup-dir and --service-stopped after approved dry-run')
        result = apply_day_break_schema(args.db_path, expected_fingerprint=args.expected_fingerprint,
                                       backup_dir=args.backup_dir, service_stopped=args.service_stopped)
    else:
        result = audit_day_break_schema(args.db_path)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
