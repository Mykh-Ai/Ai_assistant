from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any
from uuid import uuid4

from bot.services.db import init_db

APPLY_CONFIRMATION = 'APPLY_MULTI_WORKSPACE_V1'
ROLLBACK_CONFIRMATION = 'ROLLBACK_MULTI_WORKSPACE_V1'
MANIFEST_VERSION = 1
_FOUNDATION_TABLES = {'workspace', 'workspace_membership', 'active_workspace_selection'}
_WORKSPACE_OWNED_TABLES = {
    'supplier', 'contact', 'confirmed_semantic_alias', 'invoice',
    'invoice_number_settings', 'invoice_followup_state', 'customization_requests',
    'work_time_days', 'work_time_settings', 'work_time_events', 'archive_jobs',
    'accounting_document_archive_state',
}


class MigrationApplyError(RuntimeError):
    pass


def assess_public_profile_switch_readiness(
    connection: sqlite3.Connection,
    *,
    blocker_count: int,
) -> dict[str, Any]:
    """Derive profile-switch readiness from persisted schema and ownership."""
    tables = _table_names(connection)
    missing_required_tables = sorted(_WORKSPACE_OWNED_TABLES - tables)
    missing_workspace_columns = sorted(
        table
        for table in _WORKSPACE_OWNED_TABLES & tables
        if 'workspace_id' not in _column_names(connection, table)
    )
    null_workspace_rows: dict[str, int] = {}
    for table in sorted(_WORKSPACE_OWNED_TABLES & tables):
        if table in missing_workspace_columns:
            continue
        count = int(
            connection.execute(
                f'SELECT COUNT(*) FROM "{table}" '
                "WHERE workspace_id IS NULL OR trim(workspace_id) = ''"
            ).fetchone()[0]
        )
        if count:
            null_workspace_rows[table] = count

    missing_foundation_tables = sorted(_FOUNDATION_TABLES - tables)
    foundation_schema_errors: dict[str, list[str]] = {}
    required_foundation_columns = {
        'supplier': {'workspace_id', 'telegram_id'},
        'workspace': {'workspace_id'},
        'workspace_membership': {
            'workspace_id',
            'telegram_id',
            'status',
        },
        'active_workspace_selection': {'workspace_id', 'telegram_id'},
    }
    for table, required_columns in required_foundation_columns.items():
        if table not in tables:
            foundation_schema_errors[table] = sorted(required_columns)
            continue
        missing = required_columns - set(_column_names(connection, table))
        if missing:
            foundation_schema_errors[table] = sorted(missing)

    foundation_counts = {
        table: (
            int(connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            if table in tables
            else 0
        )
        for table in sorted(_FOUNDATION_TABLES)
    }
    foundation_issues: dict[str, int] = {}
    if not foundation_schema_errors:
        checks = {
            'supplier_workspace_missing': (
                'SELECT COUNT(*) FROM supplier s '
                'LEFT JOIN workspace w ON w.workspace_id = s.workspace_id '
                "WHERE s.workspace_id IS NULL OR trim(s.workspace_id) = '' "
                'OR w.workspace_id IS NULL'
            ),
            'supplier_membership_missing': (
                'SELECT COUNT(*) FROM supplier s '
                'LEFT JOIN workspace_membership m '
                'ON m.workspace_id = s.workspace_id '
                'AND m.telegram_id = s.telegram_id '
                'WHERE m.workspace_id IS NULL'
            ),
            'membership_workspace_missing': (
                'SELECT COUNT(*) FROM workspace_membership m '
                'LEFT JOIN workspace w ON w.workspace_id = m.workspace_id '
                'WHERE w.workspace_id IS NULL'
            ),
            'active_selection_membership_invalid': (
                'SELECT COUNT(*) FROM active_workspace_selection s '
                'LEFT JOIN workspace_membership m '
                'ON m.workspace_id = s.workspace_id '
                'AND m.telegram_id = s.telegram_id '
                "AND m.status = 'active' "
                'LEFT JOIN workspace w ON w.workspace_id = s.workspace_id '
                "AND w.status = 'active' WHERE m.workspace_id IS NULL OR w.workspace_id IS NULL"
            ),
        }
        for issue, query in checks.items():
            count = int(connection.execute(query).fetchone()[0])
            if count:
                foundation_issues[issue] = count

        if 'authorized_users' in tables:
            unavailable_count = int(
                connection.execute(
                    'SELECT COUNT(*) FROM supplier s '
                    'JOIN authorized_users a ON a.telegram_id = s.telegram_id '
                    "AND a.status = 'active' "
                    'LEFT JOIN workspace w ON w.workspace_id = s.workspace_id '
                    "AND w.status = 'active' "
                    'LEFT JOIN workspace_membership m '
                    'ON m.workspace_id = s.workspace_id '
                    'AND m.telegram_id = s.telegram_id '
                    "AND m.status = 'active' "
                    'WHERE w.workspace_id IS NULL OR m.workspace_id IS NULL'
                ).fetchone()[0]
            )
            if unavailable_count:
                foundation_issues['active_authorized_workspace_unavailable'] = (
                    unavailable_count
                )
            missing_selection_count = int(
                connection.execute(
                    'SELECT COUNT(*) FROM ('
                    'SELECT DISTINCT m.telegram_id FROM workspace_membership m '
                    'JOIN authorized_users a ON a.telegram_id = m.telegram_id '
                    "WHERE m.status = 'active' AND a.status = 'active' "
                    'EXCEPT '
                    'SELECT s.telegram_id FROM active_workspace_selection s '
                    'JOIN workspace_membership selected '
                    'ON selected.workspace_id = s.workspace_id '
                    'AND selected.telegram_id = s.telegram_id '
                    "WHERE selected.status = 'active'"
                    ')'
                ).fetchone()[0]
            )
            if missing_selection_count:
                foundation_issues['active_authorized_selection_missing'] = (
                    missing_selection_count
                )

    foundation_valid = not (
        missing_foundation_tables
        or foundation_schema_errors
        or foundation_issues
    )
    readiness_blockers: list[str] = []
    if missing_required_tables:
        readiness_blockers.append('required_business_tables_missing')
    if missing_workspace_columns:
        readiness_blockers.append('required_workspace_columns_missing')
    if null_workspace_rows:
        readiness_blockers.append('workspace_ownership_not_backfilled')
    if blocker_count:
        readiness_blockers.append('migration_blockers_present')
    if not foundation_valid:
        readiness_blockers.append('workspace_foundation_invalid')

    ready = not readiness_blockers
    return {
        'public_profile_switch_ready': ready,
        'reason': 'ready' if ready else 'workspace_readiness_checks_failed',
        'readiness_blockers': readiness_blockers,
        'missing_required_tables': missing_required_tables,
        'missing_workspace_columns': missing_workspace_columns,
        'null_workspace_rows': null_workspace_rows,
        'blocker_count': blocker_count,
        'foundation_valid': foundation_valid,
        'foundation_counts': foundation_counts,
        'missing_foundation_tables': missing_foundation_tables,
        'foundation_schema_errors': foundation_schema_errors,
        'foundation_issues': foundation_issues,
    }


@dataclass(frozen=True)
class _WorkspaceCandidate:
    workspace_id: str
    telegram_id: int
    supplier_id: int
    display_name: str
    storage_key: str
    membership_status: str


@dataclass(frozen=True)
class _MigrationPlan:
    fingerprint: str
    candidates: tuple[_WorkspaceCandidate, ...]
    blockers: tuple[dict[str, Any], ...]
    table_row_counts: dict[str, int]
    ownership_counts: dict[str, int]
    migration_required: bool = True

    def public_report(self) -> dict[str, Any]:
        blocker_counts: dict[str, int] = {}
        for blocker in self.blockers:
            code = str(blocker['code'])
            blocker_counts[code] = blocker_counts.get(code, 0) + int(blocker.get('count', 1))
        return {
            'database_fingerprint': self.fingerprint,
            'workspace_candidate_count': len(self.candidates),
            'ownership_counts': dict(sorted(self.ownership_counts.items())),
            'blocker_count': sum(blocker_counts.values()),
            'blockers': dict(sorted(blocker_counts.items())),
            'migration_required': self.migration_required,
            'apply_available': self.migration_required and not blocker_counts,
            'requires_expected_fingerprint': True,
            'requires_backup_directory': True,
            'requires_service_stopped_confirmation': True,
            'storage_writes_planned': False,
            'invoice_pdf_paths_preserved': True,
            'accounting_paths_preserved': True,
        }


class LegacyMultiWorkspaceMigrationPlanner:
    def __init__(self, *, db_path: Path, storage_root: Path) -> None:
        self._db_path = db_path.resolve()
        self._storage_root = storage_root.resolve()

    def plan(self) -> _MigrationPlan:
        if not self._db_path.is_file():
            raise MigrationApplyError('database_not_found')
        connection = sqlite3.connect(f'{self._db_path.as_uri()}?mode=ro', uri=True)
        connection.row_factory = sqlite3.Row
        try:
            return self.plan_connection(connection)
        finally:
            connection.close()

    def plan_connection(self, connection: sqlite3.Connection) -> _MigrationPlan:
        tables = _table_names(connection)
        blockers: list[dict[str, Any]] = []
        if 'supplier' not in tables:
            blockers.append({'code': 'supplier_table_missing', 'count': 1})
            return _MigrationPlan(
                _logical_fingerprint(connection), (), tuple(blockers),
                _table_counts(connection), {},
            )
        supplier_columns = _column_names(connection, 'supplier')
        workspace_expr = 'workspace_id' if 'workspace_id' in supplier_columns else 'NULL AS workspace_id'
        suppliers = connection.execute(
            f'SELECT id, telegram_id, name, {workspace_expr} FROM supplier ORDER BY id'
        ).fetchall()
        if not suppliers:
            blockers.append({'code': 'no_supplier_profiles_to_migrate', 'count': 1})
        telegram_counts: dict[int, int] = {}
        for row in suppliers:
            key = int(row['telegram_id'])
            telegram_counts[key] = telegram_counts.get(key, 0) + 1
        ambiguous = sum(
            1 for row in suppliers
            if row['workspace_id'] is None and telegram_counts[int(row['telegram_id'])] > 1
        )
        if ambiguous:
            blockers.append({'code': 'multiple_legacy_suppliers_for_actor', 'count': ambiguous})

        existing = _existing_workspaces(connection)
        storage_keys, storage_blockers = self._resolve_storage_keys(suppliers, existing)
        blockers.extend(storage_blockers)
        candidates: list[_WorkspaceCandidate] = []
        by_telegram: dict[int, _WorkspaceCandidate] = {}
        by_supplier: dict[int, _WorkspaceCandidate] = {}
        for row in suppliers:
            telegram_id = int(row['telegram_id'])
            supplier_id = int(row['id'])
            existing_id = str(row['workspace_id']).strip() if row['workspace_id'] else None
            workspace_id = existing_id or _workspace_id_for_telegram(telegram_id)
            candidate = _WorkspaceCandidate(
                workspace_id=workspace_id,
                telegram_id=telegram_id,
                supplier_id=supplier_id,
                display_name=str(row['name']).strip() or 'Business profile',
                storage_key=storage_keys.get(supplier_id, f'telegram-{telegram_id}'),
                membership_status=_membership_status(connection, telegram_id),
            )
            old = existing.get(workspace_id)
            if old is not None and old['storage_key'] != candidate.storage_key:
                blockers.append({'code': 'workspace_identity_collision', 'count': 1})
            candidates.append(candidate)
            by_supplier[supplier_id] = candidate
            if telegram_counts[telegram_id] == 1:
                by_telegram[telegram_id] = candidate
        _add_duplicate_blocker(blockers, 'duplicate_target_storage_key', [row.storage_key for row in candidates])
        _add_duplicate_blocker(blockers, 'duplicate_target_workspace_id', [row.workspace_id for row in candidates])

        ownership_counts: dict[str, int] = {}
        for table, owner_column in (
            ('contact', 'supplier_telegram_id'), ('invoice', 'supplier_telegram_id'),
            ('invoice_number_settings', 'supplier_telegram_id'), ('work_time_days', 'telegram_id'),
            ('work_time_settings', 'telegram_id'), ('archive_jobs', 'telegram_id'),
            ('accounting_document_archive_state', 'telegram_id'),
        ):
            _validate_direct_owner(
                connection, tables, table, owner_column, by_telegram, blockers, ownership_counts
            )
        _validate_relations(
            connection, tables, by_telegram, by_supplier, blockers, ownership_counts
        )
        migration_required = not _is_already_migrated(
            connection,
            suppliers=suppliers,
            supplier_columns=supplier_columns,
        )
        return _MigrationPlan(
            fingerprint=_logical_fingerprint(connection),
            candidates=tuple(candidates),
            blockers=tuple(blockers),
            table_row_counts=_table_counts(connection),
            ownership_counts=ownership_counts,
            migration_required=migration_required,
        )

    def _resolve_storage_keys(
        self,
        suppliers: list[sqlite3.Row],
        existing: dict[str, dict[str, str]],
    ) -> tuple[dict[int, str], list[dict[str, Any]]]:
        assignments: dict[int, str] = {}
        root = self._storage_root / 'workspaces'
        names = sorted(path.name for path in root.iterdir() if path.is_dir()) if root.is_dir() else []
        unassigned_dirs = set(names)
        pending: list[sqlite3.Row] = []
        for row in suppliers:
            supplier_id = int(row['id'])
            workspace_id = str(row['workspace_id']).strip() if row['workspace_id'] else None
            if workspace_id and workspace_id in existing:
                key = existing[workspace_id]['storage_key']
            else:
                key = f'telegram-{int(row["telegram_id"])}'
                if key not in unassigned_dirs:
                    pending.append(row)
                    continue
            assignments[supplier_id] = key
            unassigned_dirs.discard(key)
        if len(pending) == 1 and len(unassigned_dirs) == 1:
            assignments[int(pending.pop()['id'])] = unassigned_dirs.pop()
        for row in pending:
            assignments[int(row['id'])] = f'telegram-{int(row["telegram_id"])}'
        blockers = []
        if unassigned_dirs:
            blockers.append({'code': 'unassigned_accounting_workspace_directories', 'count': len(unassigned_dirs)})
        return assignments, blockers

def _validate_direct_owner(
    connection: sqlite3.Connection,
    tables: set[str],
    table: str,
    owner_column: str,
    by_telegram: dict[int, _WorkspaceCandidate],
    blockers: list[dict[str, Any]],
    ownership_counts: dict[str, int],
) -> None:
    if table not in tables or owner_column not in _column_names(connection, table):
        return
    rows = connection.execute(f'SELECT {owner_column} FROM {table}').fetchall()
    ownership_counts[table] = len(rows)
    missing = sum(
        1 for row in rows
        if row[owner_column] is None or int(row[owner_column]) not in by_telegram
    )
    if missing:
        blockers.append({'code': f'{table}_owner_missing', 'count': missing})


def _validate_relations(
    connection: sqlite3.Connection,
    tables: set[str],
    by_telegram: dict[int, _WorkspaceCandidate],
    by_supplier: dict[int, _WorkspaceCandidate],
    blockers: list[dict[str, Any]],
    ownership_counts: dict[str, int],
) -> None:
    if {'invoice', 'contact'} <= tables:
        rows = connection.execute(
            'SELECT i.id FROM invoice i LEFT JOIN contact c ON c.id = i.contact_id '
            'WHERE c.id IS NULL OR c.supplier_telegram_id != i.supplier_telegram_id'
        ).fetchall()
        if rows:
            blockers.append({'code': 'invoice_contact_owner_mismatch', 'count': len(rows)})
    if {'invoice_followup_state', 'invoice'} <= tables:
        rows = connection.execute(
            'SELECT f.invoice_id FROM invoice_followup_state f '
            'LEFT JOIN invoice i ON i.id = f.invoice_id '
            'WHERE i.id IS NULL OR i.supplier_telegram_id != f.supplier_telegram_id'
        ).fetchall()
        if rows:
            blockers.append({'code': 'invoice_followup_owner_mismatch', 'count': len(rows)})
    if 'supplier_service_alias' in tables:
        rows = connection.execute('SELECT supplier_id FROM supplier_service_alias').fetchall()
        ownership_counts['supplier_service_alias'] = len(rows)
        missing = sum(1 for row in rows if int(row['supplier_id']) not in by_supplier)
        if missing:
            blockers.append({'code': 'supplier_service_alias_owner_missing', 'count': missing})
    if 'confirmed_semantic_alias' in tables:
        rows = connection.execute(
            'SELECT supplier_telegram_id, domain, target_type, target_id '
            'FROM confirmed_semantic_alias'
        ).fetchall()
        ownership_counts['confirmed_semantic_alias'] = len(rows)
        missing = 0
        for row in rows:
            telegram_id = int(row['supplier_telegram_id'])
            if telegram_id not in by_telegram:
                missing += 1
                continue
            if str(row['domain']) == 'contact' or str(row['target_type']) == 'contact':
                contact = connection.execute(
                    'SELECT supplier_telegram_id FROM contact WHERE id = ?',
                    (int(row['target_id']),),
                ).fetchone()
                if contact is None or int(contact[0]) != telegram_id:
                    missing += 1
        if missing:
            blockers.append({'code': 'confirmed_alias_target_mismatch', 'count': missing})
    if 'work_time_events' in tables:
        rows = connection.execute(
            'SELECT work_time_day_id, telegram_id FROM work_time_events'
        ).fetchall()
        ownership_counts['work_time_events'] = len(rows)
        missing = 0
        for row in rows:
            owner = int(row['telegram_id']) if row['telegram_id'] is not None else None
            if row['work_time_day_id'] is not None and 'work_time_days' in tables:
                day = connection.execute(
                    'SELECT telegram_id FROM work_time_days WHERE id = ?',
                    (int(row['work_time_day_id']),),
                ).fetchone()
                if day is not None:
                    owner = int(day[0])
            if owner is None or owner not in by_telegram:
                missing += 1
        if missing:
            blockers.append({'code': 'work_time_event_owner_missing', 'count': missing})
    if 'customization_requests' in tables:
        columns = _column_names(connection, 'customization_requests')
        supplier_expr = (
            'supplier_telegram_id'
            if 'supplier_telegram_id' in columns
            else 'NULL AS supplier_telegram_id'
        )
        rows = connection.execute(
            f'SELECT telegram_id, {supplier_expr} FROM customization_requests'
        ).fetchall()
        ownership_counts['customization_requests'] = len(rows)
        missing = 0
        for row in rows:
            owner = row['supplier_telegram_id'] or row['telegram_id']
            if owner is None or int(owner) not in by_telegram:
                missing += 1
        if missing:
            blockers.append({'code': 'customization_request_owner_missing', 'count': missing})


class MultiWorkspaceMigrationManager:
    def __init__(self, *, db_path: Path, storage_root: Path) -> None:
        self._db_path = db_path.resolve()
        self._storage_root = storage_root.resolve()
        self._planner = LegacyMultiWorkspaceMigrationPlanner(
            db_path=self._db_path,
            storage_root=self._storage_root,
        )

    def dry_run(self) -> dict[str, Any]:
        return {
            'mode': 'dry-run',
            'writes_performed': False,
            'plan': self._planner.plan().public_report(),
        }

    def apply(
        self,
        *,
        expected_fingerprint: str,
        backup_dir: Path,
        confirmation: str,
        service_stopped: bool,
    ) -> dict[str, Any]:
        if confirmation != APPLY_CONFIRMATION:
            raise MigrationApplyError('apply_confirmation_required')
        if not service_stopped:
            raise MigrationApplyError('service_stopped_confirmation_required')
        plan = self._planner.plan()
        if plan.fingerprint != expected_fingerprint:
            raise MigrationApplyError('database_fingerprint_changed')
        if plan.blockers:
            raise MigrationApplyError('migration_blockers_present')
        if not plan.migration_required:
            raise MigrationApplyError('database_already_migrated')
        self._verify_exclusive_fingerprint(expected_fingerprint)

        backup_root = self._create_backup(backup_dir=backup_dir, plan=plan)
        snapshot_path = backup_root / 'database.sqlite3'
        target_path = backup_root / 'target.sqlite3'
        self._build_target(source_path=snapshot_path, target_path=target_path, plan=plan)
        post_report = self._post_apply_report(target_path, plan)
        if not post_report['ready']:
            raise MigrationApplyError('post_apply_audit_failed')
        if self._planner.plan().fingerprint != expected_fingerprint:
            raise MigrationApplyError('database_changed_after_backup')
        self._verify_exclusive_fingerprint(expected_fingerprint)
        manifest_path = backup_root / 'manifest.json'
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('storage_inventory') != self._current_storage_inventory():
            raise MigrationApplyError('source_storage_changed_after_backup')
        manifest.update(
            status='swap_in_progress',
            expected_post_apply_fingerprint=post_report['database_fingerprint'],
            post_apply_audit=post_report,
        )
        _write_json(manifest_path, manifest)
        self._quarantine_sidecars(backup_root)
        _atomic_database_replace(target_path, self._db_path)
        post_fingerprint = _fingerprint_path(self._db_path)
        if post_fingerprint != post_report['database_fingerprint']:
            try:
                _atomic_database_replace(snapshot_path, self._db_path)
                restored_fingerprint = _fingerprint_path(self._db_path)
                if restored_fingerprint != expected_fingerprint:
                    raise MigrationApplyError('emergency_restore_fingerprint_mismatch')
            except Exception as exc:
                manifest.update(
                    status='apply_failed_restore_failed',
                    failed_at=_utc_now(),
                )
                _write_json(manifest_path, manifest)
                raise MigrationApplyError('post_swap_emergency_restore_failed') from exc
            manifest.update(
                status='apply_failed_rolled_back',
                failed_at=_utc_now(),
            )
            _write_json(manifest_path, manifest)
            raise MigrationApplyError('post_swap_fingerprint_mismatch_rolled_back')

        manifest.update(
            status='applied',
            post_apply_fingerprint=post_fingerprint,
            post_apply_audit=post_report,
        )
        _write_json(manifest_path, manifest)
        return {
            'mode': 'apply',
            'writes_performed': True,
            'backup_id': backup_root.name,
            'manifest_path': str(manifest_path),
            'pre_apply_fingerprint': expected_fingerprint,
            'post_apply_fingerprint': post_fingerprint,
            'post_apply_audit': post_report,
            'rollback_available': True,
        }

    def rollback(
        self,
        *,
        manifest_path: Path,
        expected_current_fingerprint: str,
        confirmation: str,
        service_stopped: bool,
    ) -> dict[str, Any]:
        if confirmation != ROLLBACK_CONFIRMATION:
            raise MigrationApplyError('rollback_confirmation_required')
        if not service_stopped:
            raise MigrationApplyError('service_stopped_confirmation_required')
        manifest_path = manifest_path.resolve()
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        if manifest.get('manifest_version') != MANIFEST_VERSION:
            raise MigrationApplyError('unsupported_backup_manifest')
        if manifest.get('status') != 'applied':
            raise MigrationApplyError('backup_manifest_not_applied')
        if manifest.get('database_path') != str(self._db_path):
            raise MigrationApplyError('rollback_manifest_database_path_mismatch')
        if manifest.get('storage_root') != str(self._storage_root):
            raise MigrationApplyError('rollback_manifest_storage_root_mismatch')
        if manifest.get('storage_inventory') != self._current_storage_inventory():
            raise MigrationApplyError('rollback_storage_inventory_changed')
        current = _fingerprint_path(self._db_path)
        if current != expected_current_fingerprint:
            raise MigrationApplyError('rollback_current_fingerprint_changed')
        if manifest.get('post_apply_fingerprint') != current:
            raise MigrationApplyError('rollback_manifest_does_not_match_current_database')
        self._verify_exclusive_fingerprint(current)
        backup_path = manifest_path.parent / 'database.sqlite3'
        if _file_sha256(backup_path) != manifest.get('backup_sha256'):
            raise MigrationApplyError('backup_hash_mismatch')
        if _integrity_check(backup_path) != 'ok':
            raise MigrationApplyError('backup_integrity_check_failed')
        restore_path = manifest_path.parent / f'rollback-restore-{uuid4().hex}.sqlite3'
        shutil.copy2(backup_path, restore_path)
        self._quarantine_sidecars(manifest_path.parent, prefix='rollback')
        _atomic_database_replace(restore_path, self._db_path)
        restored = _fingerprint_path(self._db_path)
        if restored != manifest.get('pre_apply_fingerprint'):
            raise MigrationApplyError('rollback_fingerprint_mismatch')
        manifest.update(status='rolled_back', rolled_back_at=_utc_now())
        _write_json(manifest_path, manifest)
        return {
            'mode': 'rollback',
            'writes_performed': True,
            'restored_fingerprint': restored,
            'integrity_check': _integrity_check(self._db_path),
        }

    def _create_backup(self, *, backup_dir: Path, plan: _MigrationPlan) -> Path:
        backup_dir = backup_dir.resolve()
        self._validate_backup_destination(backup_dir)
        backup_dir.mkdir(parents=True, exist_ok=True)
        self._require_backup_capacity(backup_dir)
        backup_id = datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ') + '-' + uuid4().hex[:8]
        backup_root = backup_dir / backup_id
        backup_root.mkdir()
        backup_path = backup_root / 'database.sqlite3'
        source = sqlite3.connect(self._db_path)
        destination = sqlite3.connect(backup_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()
        if _integrity_check(backup_path) != 'ok':
            raise MigrationApplyError('backup_integrity_check_failed')
        if _fingerprint_path(backup_path) != plan.fingerprint:
            raise MigrationApplyError('backup_fingerprint_mismatch')
        raw_dir = backup_root / 'raw'
        raw_dir.mkdir()
        shutil.copy2(self._db_path, raw_dir / self._db_path.name)
        for suffix in ('-wal', '-shm'):
            sidecar = Path(str(self._db_path) + suffix)
            if sidecar.exists():
                shutil.copy2(sidecar, raw_dir / sidecar.name)
        storage_backup = backup_root / 'storage'
        storage_backup.mkdir()
        storage_inventory: dict[str, dict[str, Any]] = {}
        for name in ('invoices', 'workspaces'):
            source_dir = self._storage_root / name
            source_inventory = _directory_inventory(source_dir)
            storage_inventory[name] = source_inventory
            if source_dir.is_dir():
                copied_dir = storage_backup / name
                shutil.copytree(source_dir, copied_dir)
                if _directory_inventory(copied_dir) != source_inventory:
                    raise MigrationApplyError('backup_storage_verification_failed')
                if _directory_inventory(source_dir) != source_inventory:
                    raise MigrationApplyError('source_storage_changed_during_backup')
        _write_json(
            backup_root / 'manifest.json',
            {
                'manifest_version': MANIFEST_VERSION,
                'status': 'backup_complete',
                'created_at': _utc_now(),
                'database_path': str(self._db_path),
                'storage_root': str(self._storage_root),
                'pre_apply_fingerprint': plan.fingerprint,
                'backup_sha256': _file_sha256(backup_path),
                'backup_integrity_check': 'ok',
                'storage_writes_planned': False,
                'storage_inventory': storage_inventory,
                'workspace_candidate_count': len(plan.candidates),
                'table_row_counts': plan.table_row_counts,
            },
        )
        return backup_root

    def _validate_backup_destination(self, backup_dir: Path) -> None:
        for name in ('invoices', 'workspaces'):
            source = (self._storage_root / name).resolve()
            if backup_dir == source or source in backup_dir.parents:
                raise MigrationApplyError('backup_directory_inside_source_tree')

    def _require_backup_capacity(self, backup_dir: Path) -> None:
        storage_bytes = sum(
            _directory_inventory(self._storage_root / name)['total_bytes']
            for name in ('invoices', 'workspaces')
        )
        required = self._db_path.stat().st_size * 4 + storage_bytes
        probe = backup_dir.parent if backup_dir.parent.exists() else self._db_path.parent
        if shutil.disk_usage(probe).free < int(required * 1.1):
            raise MigrationApplyError('insufficient_backup_disk_space')

    def _current_storage_inventory(self) -> dict[str, dict[str, Any]]:
        return {
            name: _directory_inventory(self._storage_root / name)
            for name in ('invoices', 'workspaces')
        }

    def _verify_exclusive_fingerprint(self, expected_fingerprint: str) -> None:
        connection = sqlite3.connect(self._db_path, timeout=0, isolation_level=None)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute('BEGIN EXCLUSIVE')
            current = _logical_fingerprint(connection)
            connection.execute('ROLLBACK')
        except sqlite3.OperationalError as exc:
            try:
                connection.execute('ROLLBACK')
            except sqlite3.Error:
                pass
            raise MigrationApplyError('database_exclusive_lock_unavailable') from exc
        finally:
            connection.close()
        if current != expected_fingerprint:
            raise MigrationApplyError('database_fingerprint_changed_under_lock')

    def _build_target(
        self,
        *,
        source_path: Path,
        target_path: Path,
        plan: _MigrationPlan,
    ) -> None:
        if target_path.exists():
            target_path.unlink()
        init_db(target_path)
        source = sqlite3.connect(source_path)
        target = sqlite3.connect(target_path)
        source.row_factory = sqlite3.Row
        target.row_factory = sqlite3.Row
        try:
            target.execute('PRAGMA foreign_keys = OFF')
            target.execute('BEGIN IMMEDIATE')
            canonical_tables = _table_names(target)
            for table in sorted(_table_names(source)):
                self._copy_table(source, target, table, plan)
            self._write_foundation(target, plan)
            self._copy_unknown_schema_objects(
                source,
                target,
                canonical_tables=canonical_tables,
            )
            target.commit()
        except Exception:
            target.rollback()
            raise
        finally:
            target.close()
            source.close()

    @staticmethod
    def _copy_unknown_schema_objects(
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        *,
        canonical_tables: set[str],
    ) -> None:
        rows = source.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type IN ('index', 'trigger') AND sql IS NOT NULL "
            "ORDER BY CASE type WHEN 'index' THEN 0 ELSE 1 END, name"
        ).fetchall()
        for row in rows:
            if str(row['tbl_name']) in canonical_tables:
                continue
            existing = target.execute(
                'SELECT 1 FROM sqlite_master WHERE type = ? AND name = ?',
                (row['type'], row['name']),
            ).fetchone()
            if existing is None:
                target.execute(str(row['sql']))
    def _copy_table(
        self,
        source: sqlite3.Connection,
        target: sqlite3.Connection,
        table: str,
        plan: _MigrationPlan,
    ) -> None:
        if table not in _table_names(target):
            schema = source.execute(
                "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
                (table,),
            ).fetchone()
            if schema is None or not schema[0]:
                return
            target.execute(str(schema[0]))
        source_columns = _column_names(source, table)
        target_columns = _column_names(target, table)
        source_info = {
            str(row['name']): row
            for row in source.execute(f'PRAGMA table_info("{table}")').fetchall()
        }
        for column in source_columns:
            if column not in target_columns:
                column_type = str(source_info[column]['type'] or 'BLOB')
                target.execute(
                    f'ALTER TABLE "{table}" ADD COLUMN "{column}" {column_type}'
                )
        target_columns = _column_names(target, table)
        by_telegram = {item.telegram_id: item for item in plan.candidates}
        by_supplier = {item.supplier_id: item for item in plan.candidates}
        invoice_owner = _id_owner_map(source, 'invoice', 'supplier_telegram_id')
        day_owner = _id_owner_map(source, 'work_time_days', 'telegram_id')
        for row in source.execute(f'SELECT * FROM "{table}"').fetchall():
            payload = {
                column: row[column]
                for column in source_columns
                if column in target_columns
            }
            if 'workspace_id' in target_columns and table in _WORKSPACE_OWNED_TABLES:
                owner = self._row_owner(
                    table, row, source_columns, by_telegram, by_supplier,
                    invoice_owner, day_owner,
                )
                if owner is None:
                    raise MigrationApplyError(f'{table}_owner_resolution_failed')
                payload['workspace_id'] = owner.workspace_id
            columns = [column for column in target_columns if column in payload]
            quoted = ', '.join(f'"{column}"' for column in columns)
            placeholders = ', '.join('?' for _ in columns)
            target.execute(
                f'INSERT INTO "{table}" ({quoted}) VALUES ({placeholders})',
                [payload[column] for column in columns],
            )

    @staticmethod
    def _row_owner(
        table: str,
        row: sqlite3.Row,
        source_columns: list[str],
        by_telegram: dict[int, _WorkspaceCandidate],
        by_supplier: dict[int, _WorkspaceCandidate],
        invoice_owner: dict[int, int],
        day_owner: dict[int, int],
    ) -> _WorkspaceCandidate | None:
        if table == 'supplier':
            return by_supplier.get(int(row['id']))
        if table in {'contact', 'invoice', 'invoice_number_settings', 'confirmed_semantic_alias'}:
            return by_telegram.get(int(row['supplier_telegram_id']))
        if table == 'invoice_followup_state':
            owner = invoice_owner.get(int(row['invoice_id']))
            return by_telegram.get(owner) if owner is not None else None
        if table in {
            'work_time_days', 'work_time_settings', 'archive_jobs',
            'accounting_document_archive_state',
        }:
            return by_telegram.get(int(row['telegram_id']))
        if table == 'work_time_events':
            owner = None
            if row['work_time_day_id'] is not None:
                owner = day_owner.get(int(row['work_time_day_id']))
            if owner is None and 'telegram_id' in source_columns and row['telegram_id'] is not None:
                owner = int(row['telegram_id'])
            return by_telegram.get(owner) if owner is not None else None
        if table == 'customization_requests':
            value = (
                row['supplier_telegram_id']
                if 'supplier_telegram_id' in source_columns
                and row['supplier_telegram_id'] is not None
                else row['telegram_id']
            )
            return by_telegram.get(int(value))
        return None

    @staticmethod
    def _write_foundation(
        target: sqlite3.Connection,
        plan: _MigrationPlan,
    ) -> None:
        for row in plan.candidates:
            target.execute(
                'INSERT INTO workspace '
                '(workspace_id, display_name, storage_key, drive_folder_name, status, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                'ON CONFLICT(workspace_id) DO UPDATE SET '
                'display_name=excluded.display_name, storage_key=excluded.storage_key, '
                'drive_folder_name=excluded.drive_folder_name, status=excluded.status, '
                'updated_at=CURRENT_TIMESTAMP',
                (row.workspace_id, row.display_name, row.storage_key, row.display_name, 'active'),
            )
            target.execute(
                'INSERT INTO workspace_membership '
                '(workspace_id, telegram_id, role, status, created_at, updated_at) '
                'VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) '
                'ON CONFLICT(workspace_id, telegram_id) DO UPDATE SET '
                'role=excluded.role, status=excluded.status, updated_at=CURRENT_TIMESTAMP',
                (row.workspace_id, row.telegram_id, 'owner', row.membership_status),
            )
            if row.membership_status == 'active':
                target.execute(
                    'INSERT INTO active_workspace_selection '
                    '(telegram_id, workspace_id, updated_at) '
                    'VALUES (?, ?, CURRENT_TIMESTAMP) '
                    'ON CONFLICT(telegram_id) DO NOTHING',
                    (row.telegram_id, row.workspace_id),
                )

    def _post_apply_report(
        self,
        target_path: Path,
        plan: _MigrationPlan,
    ) -> dict[str, Any]:
        connection = sqlite3.connect(target_path)
        connection.row_factory = sqlite3.Row
        try:
            integrity = str(connection.execute('PRAGMA integrity_check').fetchone()[0])
            counts = _table_counts(connection)
            mismatches = {
                table: {'before': before, 'after': counts.get(table, 0)}
                for table, before in plan.table_row_counts.items()
                if table not in _FOUNDATION_TABLES and counts.get(table, 0) != before
            }
            post_plan = LegacyMultiWorkspaceMigrationPlanner(
                db_path=target_path,
                storage_root=self._storage_root,
            ).plan()
            readiness = assess_public_profile_switch_readiness(
                connection,
                blocker_count=len(post_plan.blockers),
            )
            ready = (
                integrity == 'ok'
                and not mismatches
                and readiness['public_profile_switch_ready']
            )
            return {
                **readiness,
                'ready': ready,
                'public_profile_switch_ready': ready,
                'reason': 'ready' if ready else 'post_apply_audit_failed',
                'integrity_check': integrity,
                'database_fingerprint': _logical_fingerprint(connection),
                'count_mismatches': mismatches,
                'workspace_count': int(connection.execute(
                    'SELECT COUNT(*) FROM workspace'
                ).fetchone()[0]),
                'membership_count': int(connection.execute(
                    'SELECT COUNT(*) FROM workspace_membership'
                ).fetchone()[0]),
            }
        finally:
            connection.close()

    def _quarantine_sidecars(
        self,
        backup_root: Path,
        *,
        prefix: str = 'apply',
    ) -> None:
        target_dir = backup_root / f'{prefix}-sidecars'
        for suffix in ('-wal', '-shm'):
            sidecar = Path(str(self._db_path) + suffix)
            if sidecar.exists():
                target_dir.mkdir(exist_ok=True)
                shutil.move(str(sidecar), target_dir / sidecar.name)

def _is_already_migrated(
    connection: sqlite3.Connection,
    *,
    suppliers: list[sqlite3.Row],
    supplier_columns: list[str],
) -> bool:
    if not suppliers or 'workspace_id' not in supplier_columns:
        return False
    if any(
        row['workspace_id'] is None or not str(row['workspace_id']).strip()
        for row in suppliers
    ):
        return False
    tables = _table_names(connection)
    if not {'workspace', 'workspace_membership', 'active_workspace_selection'} <= tables:
        return False
    for row in suppliers:
        workspace_id = str(row['workspace_id']).strip()
        telegram_id = int(row['telegram_id'])
        if connection.execute(
            'SELECT 1 FROM workspace WHERE workspace_id = ?',
            (workspace_id,),
        ).fetchone() is None:
            return False
        if connection.execute(
            'SELECT 1 FROM workspace_membership '
            'WHERE workspace_id = ? AND telegram_id = ?',
            (workspace_id, telegram_id),
        ).fetchone() is None:
            return False
    return True

def _workspace_id_for_telegram(telegram_id: int) -> str:
    digest = sha256(
        f'fakturabot-workspace-v1:{telegram_id}'.encode('utf-8')
    ).hexdigest()
    return f'ws_{digest[:24]}'


def _membership_status(
    connection: sqlite3.Connection,
    telegram_id: int,
) -> str:
    if 'authorized_users' not in _table_names(connection):
        return 'inactive'
    row = connection.execute(
        'SELECT status FROM authorized_users WHERE telegram_id = ?',
        (telegram_id,),
    ).fetchone()
    return 'active' if row is not None and str(row[0]) == 'active' else 'inactive'


def _existing_workspaces(
    connection: sqlite3.Connection,
) -> dict[str, dict[str, str]]:
    if 'workspace' not in _table_names(connection):
        return {}
    return {
        str(row['workspace_id']): {
            'storage_key': str(row['storage_key']),
            'display_name': str(row['display_name']),
        }
        for row in connection.execute(
            'SELECT workspace_id, storage_key, display_name FROM workspace'
        ).fetchall()
    }


def _add_duplicate_blocker(
    blockers: list[dict[str, Any]],
    code: str,
    values: list[str],
) -> None:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    duplicate_count = sum(count - 1 for count in counts.values() if count > 1)
    if duplicate_count:
        blockers.append({'code': code, 'count': duplicate_count})


def _table_names(connection: sqlite3.Connection) -> set[str]:
    return {
        str(row[0])
        for row in connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }


def _column_names(
    connection: sqlite3.Connection,
    table: str,
) -> list[str]:
    escaped = table.replace('"', '""')
    return [
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{escaped}")'
        ).fetchall()
    ]


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    return {
        table: int(connection.execute(
            f'SELECT COUNT(*) FROM "{table}"'
        ).fetchone()[0])
        for table in sorted(_table_names(connection))
    }


def _id_owner_map(
    connection: sqlite3.Connection,
    table: str,
    owner_column: str,
) -> dict[int, int]:
    if table not in _table_names(connection):
        return {}
    if owner_column not in _column_names(connection, table):
        return {}
    return {
        int(row['id']): int(row[owner_column])
        for row in connection.execute(
            f'SELECT id, {owner_column} FROM {table}'
        ).fetchall()
    }


def _logical_fingerprint(connection: sqlite3.Connection) -> str:
    digest = sha256()
    for table in sorted(_table_names(connection)):
        schema = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
        digest.update(table.encode('utf-8'))
        digest.update(str(schema[0] if schema else '').encode('utf-8'))
        columns = _column_names(connection, table)
        order_clause = ', '.join(f'"{column}"' for column in columns)
        rows = connection.execute(
            f'SELECT * FROM "{table}" ORDER BY {order_clause}'
        ).fetchall()
        for row in rows:
            values = [
                row[column] if isinstance(row, sqlite3.Row) else row[index]
                for index, column in enumerate(columns)
            ]
            digest.update(_stable_json(values).encode('utf-8'))
    return digest.hexdigest()


def _fingerprint_path(path: Path) -> str:
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        return _logical_fingerprint(connection)
    finally:
        connection.close()


def _stable_json(values: list[Any]) -> str:
    normalized = []
    for value in values:
        if isinstance(value, bytes):
            normalized.append({
                'blob_sha256': sha256(value).hexdigest(),
                'size': len(value),
            })
        else:
            normalized.append(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _integrity_check(path: Path) -> str:
    connection = sqlite3.connect(path)
    try:
        return str(connection.execute('PRAGMA integrity_check').fetchone()[0])
    finally:
        connection.close()


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _directory_inventory(path: Path) -> dict[str, Any]:
    digest = sha256()
    if not path.is_dir():
        return {
            'file_count': 0,
            'total_bytes': 0,
            'content_sha256': digest.hexdigest(),
        }
    files = sorted(
        (item for item in path.rglob('*') if item.is_file()),
        key=lambda item: item.relative_to(path).as_posix(),
    )
    total_bytes = 0
    for item in files:
        relative = item.relative_to(path).as_posix()
        size = item.stat().st_size
        total_bytes += size
        digest.update(relative.encode('utf-8'))
        digest.update(str(size).encode('ascii'))
        digest.update(_file_sha256(item).encode('ascii'))
    return {
        'file_count': len(files),
        'total_bytes': total_bytes,
        'content_sha256': digest.hexdigest(),
    }


def _atomic_database_replace(source: Path, destination: Path) -> None:
    staged = destination.parent / f'.{destination.name}.{uuid4().hex}.tmp'
    shutil.copy2(source, staged)
    try:
        with staged.open('r+b') as handle:
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(staged, destination)
    finally:
        staged.unlink(missing_ok=True)

def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
        encoding='utf-8',
    )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()