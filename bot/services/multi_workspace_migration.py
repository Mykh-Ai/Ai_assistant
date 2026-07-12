from __future__ import annotations

from collections import Counter
from pathlib import Path, PureWindowsPath
import re
import sqlite3
from typing import Any


TENANT_COLUMNS = ('workspace_id', 'supplier_telegram_id', 'telegram_id')
FOUNDATION_TABLES = ('workspace', 'workspace_membership', 'active_workspace_selection')
BUSINESS_TABLES = (
    'supplier',
    'contact',
    'supplier_service_alias',
    'confirmed_semantic_alias',
    'invoice',
    'invoice_item',
    'invoice_number_settings',
    'invoice_followup_state',
    'customization_requests',
    'work_time_days',
    'work_time_settings',
    'work_time_events',
    'archive_jobs',
    'accounting_document_archive_state',
)
WORKSPACE_COLUMN_REQUIRED = tuple(
    table for table in BUSINESS_TABLES if table != 'invoice_item'
)


class MigrationAuditError(RuntimeError):
    pass


class MultiWorkspaceMigrationAuditor:
    """Read-only inventory and migration planning for the workspace rollout."""

    def __init__(self, *, db_path: Path, storage_root: Path) -> None:
        self._db_path = db_path.resolve()
        self._storage_root = storage_root.resolve()

    def audit(self) -> dict[str, Any]:
        with self._read_only_connection() as connection:
            tables = self._table_names(connection)
            tenant_refs = self._tenant_refs(connection, tables)
            table_reports = {
                table: self._table_report(connection, table, tenant_refs)
                for table in tables
            }
            indexes = {
                table: self._index_report(connection, table)
                for table in tables
                if table in BUSINESS_TABLES or table in FOUNDATION_TABLES
            }
            invoice_paths = self._invoice_path_report(connection, tables)

        missing_workspace_columns = [
            table
            for table in WORKSPACE_COLUMN_REQUIRED
            if table in table_reports
            and 'workspace_id' not in table_reports[table]['columns']
        ]
        foundation_counts = {
            table: table_reports.get(table, {}).get('row_count', 0)
            for table in FOUNDATION_TABLES
        }
        return {
            'mode': 'audit',
            'database': {
                'exists': True,
                'table_count': len(tables),
                'journal_writes': False,
            },
            'tables': table_reports,
            'indexes': indexes,
            'invoice_pdf_paths': invoice_paths,
            'accounting_storage': self._accounting_storage_report(),
            'foundation_counts': foundation_counts,
            'migration_state': {
                'missing_workspace_columns': missing_workspace_columns,
                'public_profile_switch_ready': False,
                'reason': 'runtime_target_ready_but_persisted_data_apply_gate_closed',
            },
            'privacy': {
                'tenant_ids_redacted': True,
                'paths_listed': False,
                'secrets_read': False,
            },
        }

    def dry_run(self) -> dict[str, Any]:
        audit = self.audit()
        tables = audit['tables']
        tenant_refs = sorted(
            {
                tenant_ref
                for table in tables.values()
                for groups in table['tenant_groups'].values()
                for tenant_ref in groups
                if tenant_ref != 'none'
            }
        )
        schema_changes: list[dict[str, Any]] = []
        for table in WORKSPACE_COLUMN_REQUIRED:
            table_report = tables.get(table)
            if table_report is None:
                continue
            if 'workspace_id' not in table_report['columns']:
                schema_changes.append(
                    {
                        'table': table,
                        'operation': 'add_and_backfill_workspace_id',
                        'row_count': table_report['row_count'],
                    }
                )

        audit['mode'] = 'dry-run'
        audit['plan'] = {
            'writes_performed': False,
            'workspace_candidates': [
                {
                    'tenant_ref': tenant_ref,
                    'workspace_id': f'planned_{tenant_ref}',
                    'storage_key': 'preserve_or_assign_after_path_audit',
                    'membership_role': 'owner',
                    'active_selection': True,
                }
                for tenant_ref in tenant_refs
            ],
            'schema_changes': schema_changes,
            'uniqueness_rebuilds': [
                'supplier: UNIQUE(workspace_id)',
                'invoice: UNIQUE(workspace_id, invoice_number)',
                'invoice_number_settings: UNIQUE(workspace_id, issue_year)',
                'work_time_days: UNIQUE(workspace_id, work_date)',
            ],
            'preserve_invoice_pdf_paths': True,
            'move_existing_invoice_pdfs': False,
            'ambiguous_or_orphan_rows': 'must_be_zero_or_explicitly_resolved_before_apply',
            'apply_available': False,
            'apply_block_reason': 'backup_rollback_and_full_domain_apply_not_approved_or_implemented',
        }
        return audit

    def _read_only_connection(self) -> sqlite3.Connection:
        if not self._db_path.is_file():
            raise MigrationAuditError('database_not_found')
        connection = sqlite3.connect(f'{self._db_path.as_uri()}?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        return connection

    @staticmethod
    def _table_names(connection: sqlite3.Connection) -> list[str]:
        rows = connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
        ).fetchall()
        return [str(row['name']) for row in rows]

    def _tenant_refs(
        self,
        connection: sqlite3.Connection,
        tables: list[str],
    ) -> dict[str, str]:
        values: set[str] = set()
        for table in tables:
            columns = self._column_names(connection, table)
            for column in TENANT_COLUMNS:
                if column not in columns:
                    continue
                rows = connection.execute(
                    f'SELECT DISTINCT "{column}" AS tenant_value FROM "{table}" '
                    f'WHERE "{column}" IS NOT NULL'
                ).fetchall()
                values.update(str(row['tenant_value']) for row in rows)
        return {
            value: f'tenant_{index}'
            for index, value in enumerate(sorted(values), 1)
        }

    def _table_report(
        self,
        connection: sqlite3.Connection,
        table: str,
        tenant_refs: dict[str, str],
    ) -> dict[str, Any]:
        columns = self._column_names(connection, table)
        row_count = int(
            connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        )
        tenant_groups: dict[str, dict[str, int]] = {}
        for column in TENANT_COLUMNS:
            if column not in columns:
                continue
            rows = connection.execute(
                f'SELECT "{column}" AS tenant_value, COUNT(*) AS row_count '
                f'FROM "{table}" GROUP BY "{column}"'
            ).fetchall()
            tenant_groups[column] = {
                (
                    tenant_refs.get(str(row['tenant_value']), 'none')
                    if row['tenant_value'] is not None
                    else 'none'
                ): int(row['row_count'])
                for row in rows
            }
        return {
            'row_count': row_count,
            'columns': columns,
            'tenant_groups': tenant_groups,
        }

    @staticmethod
    def _column_names(connection: sqlite3.Connection, table: str) -> list[str]:
        escaped = table.replace('"', '""')
        return [
            str(row['name'])
            for row in connection.execute(
                f'PRAGMA table_info("{escaped}")'
            ).fetchall()
        ]

    @staticmethod
    def _index_report(
        connection: sqlite3.Connection,
        table: str,
    ) -> list[dict[str, Any]]:
        escaped = table.replace('"', '""')
        reports: list[dict[str, Any]] = []
        for row in connection.execute(
            f'PRAGMA index_list("{escaped}")'
        ).fetchall():
            name = str(row['name'])
            index_escaped = name.replace('"', '""')
            columns = [
                str(info['name'])
                for info in connection.execute(
                    f'PRAGMA index_info("{index_escaped}")'
                ).fetchall()
            ]
            reports.append(
                {'name': name, 'unique': bool(row['unique']), 'columns': columns}
            )
        return reports

    def _invoice_path_report(
        self,
        connection: sqlite3.Connection,
        tables: list[str],
    ) -> dict[str, int]:
        if (
            'invoice' not in tables
            or 'pdf_path' not in self._column_names(connection, 'invoice')
        ):
            return {}
        counts: Counter[str] = Counter()
        rows = connection.execute('SELECT pdf_path FROM invoice').fetchall()
        for row in rows:
            counts[self._classify_invoice_path(row['pdf_path'])] += 1
        return dict(sorted(counts.items()))

    def _classify_invoice_path(self, value: Any) -> str:
        if value is None or not str(value).strip():
            return 'empty'
        text = str(value).strip()
        if re.match(r'^[A-Za-z]:[\/]', text) or PureWindowsPath(text).drive:
            return 'windows_absolute'
        path = Path(text)
        resolved = path if path.is_absolute() else (self._storage_root.parent / path)
        normalized = text.replace(chr(92), '/')
        if resolved.exists():
            return (
                'existing_tenant_path'
                if '/invoices/' in normalized and normalized.count('/') >= 3
                else 'existing_other'
            )
        if re.search(r'/invoices/[^/]+.pdf$', normalized):
            return 'missing_flat_legacy'
        if '/invoices/' in normalized:
            return 'missing_tenant_or_nested'
        return 'missing_other'

    def _accounting_storage_report(self) -> dict[str, Any]:
        workspaces_root = self._storage_root / 'workspaces'
        if not workspaces_root.is_dir():
            return {
                'workspace_directory_count': 0,
                'key_classes': {},
                'metadata_files': 0,
                'original_files': 0,
            }
        key_classes: Counter[str] = Counter()
        metadata_files = 0
        original_files = 0
        directories = [
            path for path in workspaces_root.iterdir() if path.is_dir()
        ]
        for directory in directories:
            name = directory.name
            if name == 'mykhailo-szco':
                key_classes['legacy_named'] += 1
            elif name.startswith('telegram-'):
                key_classes['telegram_derived'] += 1
            else:
                key_classes['other'] += 1
            metadata_files += sum(
                1 for _ in directory.rglob('metadata/*.json')
            )
            original_files += sum(
                1
                for path in directory.rglob('originals/*')
                if path.is_file()
            )
        return {
            'workspace_directory_count': len(directories),
            'key_classes': dict(sorted(key_classes.items())),
            'metadata_files': metadata_files,
            'original_files': original_files,
        }
