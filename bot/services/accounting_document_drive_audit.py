from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path
import sqlite3
from urllib.parse import quote

from bot.services.accounting_document_archive_path import (
    AccountingDocumentArchivePathError,
    derive_accounting_document_drive_target_path,
    normalize_relative_drive_target_path,
)


_ACTIVE_STATUSES = ('pending', 'uploading', 'retry_wait')
_ACCOUNTING_DOCUMENT_TYPES = ('receipt', 'incoming_invoice')


@dataclass(frozen=True)
class AccountingDocumentDriveAuditReport:
    database_sha256_before: str
    database_sha256_after: str
    database_unchanged: bool
    active_accounting_jobs: int
    valid_target_jobs: int
    blocker_count: int
    blocker_categories: dict[str, int]
    deployment_ready: bool
    writes_performed: bool = False

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def audit_accounting_document_drive_targets(
    db_path: Path,
) -> AccountingDocumentDriveAuditReport:
    if not db_path.is_file():
        raise FileNotFoundError(db_path)

    fingerprint_before = _file_sha256(db_path)
    db_uri = f"file:{quote(db_path.resolve().as_posix(), safe='/:')}?mode=ro"
    blockers: Counter[str] = Counter()
    valid_targets = 0

    with sqlite3.connect(db_uri, uri=True) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only = ON')
        rows = connection.execute(
            (
                'SELECT j.document_type, j.local_file_path, j.metadata_path, '
                'j.target_folder_path, w.storage_key, w.drive_folder_name '
                'FROM archive_jobs AS j '
                'LEFT JOIN workspace AS w ON w.workspace_id = j.workspace_id '
                'WHERE j.status IN (?, ?, ?) AND j.document_type IN (?, ?)'
            ),
            (*_ACTIVE_STATUSES, *_ACCOUNTING_DOCUMENT_TYPES),
        ).fetchall()

    for row in rows:
        if row['storage_key'] is None or row['drive_folder_name'] is None:
            blockers['workspace_context_missing'] += 1
            continue
        if row['target_folder_path'] is None or not str(row['target_folder_path']).strip():
            blockers['target_folder_path_missing'] += 1
            continue
        try:
            expected_target = derive_accounting_document_drive_target_path(
                local_file_path=row['local_file_path'],
                metadata_path=row['metadata_path'],
                workspace_storage_key=row['storage_key'],
                workspace_drive_folder_name=row['drive_folder_name'],
                document_type=row['document_type'],
            )
            actual_target = normalize_relative_drive_target_path(row['target_folder_path'])
        except AccountingDocumentArchivePathError:
            blockers['unsafe_or_inconsistent_path'] += 1
            continue
        if actual_target != expected_target:
            blockers['target_folder_path_mismatch'] += 1
            continue
        valid_targets += 1

    fingerprint_after = _file_sha256(db_path)
    blocker_count = sum(blockers.values())
    return AccountingDocumentDriveAuditReport(
        database_sha256_before=fingerprint_before,
        database_sha256_after=fingerprint_after,
        database_unchanged=fingerprint_before == fingerprint_after,
        active_accounting_jobs=len(rows),
        valid_target_jobs=valid_targets,
        blocker_count=blocker_count,
        blocker_categories=dict(sorted(blockers.items())),
        deployment_ready=blocker_count == 0 and fingerprint_before == fingerprint_after,
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
