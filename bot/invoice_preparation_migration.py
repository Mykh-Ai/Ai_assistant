"""Explicit, additive SQLite migration for invoice preparation."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

from bot.services.db import (
    CONTACT_EXPECTED_COLUMNS, CONTACT_LEGACY_EXPECTED_COLUMN_NAMES,
    INVOICE_EXPECTED_COLUMNS, INVOICE_LEGACY_EXPECTED_COLUMN_NAMES,
)


_TARGETS = (
    ('contact', 'default_hourly_rate_eur', {frozenset(CONTACT_EXPECTED_COLUMNS), frozenset(CONTACT_LEGACY_EXPECTED_COLUMN_NAMES)}),
    ('invoice', 'calculation_bundle_json', {frozenset(INVOICE_EXPECTED_COLUMNS), frozenset(INVOICE_LEGACY_EXPECTED_COLUMN_NAMES)}),
)


def _read_only(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f'{db_path.resolve().as_uri()}?mode=ro', uri=True)
    connection.execute('PRAGMA query_only = ON')
    return connection


def _fingerprint(connection: sqlite3.Connection) -> str:
    digest = sha256()
    for record in connection.iterdump():
        digest.update(record.encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def _inspect(connection: sqlite3.Connection) -> dict:
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('SQLite integrity check failed')
    pending = []
    counts = {}
    for table, column, accepted in _TARGETS:
        columns = {row[1]: row for row in connection.execute(f'PRAGMA table_info({table})')}
        if frozenset(columns.keys() - {column}) not in accepted:
            raise ValueError(f'Unsupported schema for {table}')
        if column in columns:
            if columns[column][2].upper() != 'TEXT' or columns[column][3] or columns[column][4] is not None:
                raise ValueError(f'Expected nullable TEXT with no default: {table}.{column}')
        else:
            pending.append(f'{table}.{column}')
        counts[table] = connection.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]
    return {'pending': pending, 'row_counts': counts, 'fingerprint': _fingerprint(connection)}


def audit(db_path: Path) -> dict:
    with closing(_read_only(db_path)) as connection:
        connection.execute('BEGIN')
        return _inspect(connection)


def apply(db_path: Path, *, expected_fingerprint: str, backup_path: Path) -> dict:
    if not db_path.is_file() or backup_path.exists():
        raise ValueError('A real database and an unused backup path are required')
    if backup_path.resolve() == db_path.resolve():
        raise ValueError('Backup path must differ from database')
    with closing(sqlite3.connect(db_path, timeout=0)) as writer:
        writer.execute('BEGIN IMMEDIATE')
        current = _inspect(writer)
        if current['fingerprint'] != expected_fingerprint:
            raise ValueError('Database changed since dry-run')
        if not current['pending']:
            return current
        with closing(_read_only(db_path)) as reader, closing(sqlite3.connect(backup_path)) as backup:
            reader.backup(backup)
            if _inspect(backup) != current:
                raise ValueError('Backup does not match the approved database')
        for table, column, _ in _TARGETS:
            if f'{table}.{column}' in current['pending']:
                writer.execute(f'ALTER TABLE {table} ADD COLUMN {column} TEXT')
        expanded = _inspect(writer)
        if expanded['pending'] or expanded['row_counts'] != current['row_counts']:
            raise ValueError('Expanded schema verification failed')
        writer.commit()
        return expanded


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('audit', 'dry-run', 'apply'))
    parser.add_argument('--db-path', required=True, type=Path)
    parser.add_argument('--backup-path', type=Path)
    parser.add_argument('--expected-fingerprint')
    parser.add_argument('--service-stopped', action='store_true')
    args = parser.parse_args()
    if args.mode == 'apply':
        if not (args.backup_path and args.expected_fingerprint and args.service_stopped):
            parser.error('apply requires --backup-path, --expected-fingerprint and --service-stopped')
        result = apply(args.db_path, expected_fingerprint=args.expected_fingerprint, backup_path=args.backup_path)
    else:
        result = audit(args.db_path)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
