from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from bot.services.db import init_db


def _replace_contact_with_pre_iban_schema(db_path: Path, *, legacy: bool = False) -> None:
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='contact'"
        ).fetchone()[0]
        schema = schema.replace('    iban TEXT,\n', '')
        if legacy:
            schema = schema.replace('    workspace_id TEXT,\n', '')
            schema = schema.replace(
                'UNIQUE(workspace_id, name)',
                'UNIQUE(supplier_telegram_id, name)',
            )
        connection.execute('DROP TABLE contact')
        connection.execute(schema)
        columns = (
            'supplier_telegram_id, name, ico, dic, ic_dph, address, email, '
            'contact_person, source_type, source_note, contract_path'
        )
        values = (77, 'Preserved s.r.o.', '87654321', '0987654321', None,
                  'Hlavná 1, Bratislava', 'old@example.test', 'Eva',
                  'manual', 'before migration', 'storage/contracts/old.pdf')
        if legacy:
            cursor = connection.execute(
                f'INSERT INTO contact ({columns}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                values,
            )
        else:
            cursor = connection.execute(
                f'INSERT INTO contact (workspace_id, {columns}) '
                'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                ('ws_one', *values),
            )
        contact_id = int(cursor.lastrowid)
        connection.execute(
            'INSERT INTO invoice '
            '(workspace_id, supplier_telegram_id, contact_id, invoice_number, '
            'issue_date, delivery_date, due_date, due_days, total_amount, currency, status) '
            'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            ('ws_one' if not legacy else None, 77, contact_id, '2026-001',
             '2026-07-17', '2026-07-17', '2026-07-31', 14, 10.0, 'EUR', 'draft'),
        )
        connection.commit()


def test_fresh_contact_schema_contains_nullable_iban(tmp_path: Path) -> None:
    db_path = tmp_path / 'fresh.db'
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        columns = {row[1]: row for row in connection.execute('PRAGMA table_info(contact)')}
    assert 'iban' in columns
    assert columns['iban'][3] == 0


@pytest.mark.parametrize('legacy', [False, True])
def test_pre_iban_schema_is_migrated_in_place_and_idempotently(
    tmp_path: Path,
    legacy: bool,
) -> None:
    db_path = tmp_path / f'pre_iban_{legacy}.db'
    _replace_contact_with_pre_iban_schema(db_path, legacy=legacy)

    init_db(db_path)
    init_db(db_path)

    with sqlite3.connect(db_path) as connection:
        columns = [row[1] for row in connection.execute('PRAGMA table_info(contact)')]
        contact = connection.execute(
            'SELECT id, name, email, contact_person, contract_path, iban FROM contact'
        ).fetchone()
        invoice_contact_id = connection.execute(
            'SELECT contact_id FROM invoice WHERE invoice_number = ?', ('2026-001',)
        ).fetchone()[0]
    assert columns.count('iban') == 1
    assert contact == (1, 'Preserved s.r.o.', 'old@example.test', 'Eva',
                       'storage/contracts/old.pdf', None)
    assert invoice_contact_id == contact[0]


def test_incompatible_contact_schema_still_fails_closed(tmp_path: Path) -> None:
    db_path = tmp_path / 'incompatible.db'
    init_db(db_path)
    with sqlite3.connect(db_path) as connection:
        connection.execute('ALTER TABLE contact ADD COLUMN unexpected TEXT')
        connection.commit()

    with pytest.raises(RuntimeError, match='Incompatible local schema for table contact'):
        init_db(db_path)