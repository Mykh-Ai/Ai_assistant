from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
import sqlite3
from urllib.parse import quote


CLEANUP_ACTION_KEEP = 'keep'
CLEANUP_ACTION_WOULD_DELETE = 'would_delete'
CLEANUP_ACTION_EXCLUDE = 'exclude'

CLEANUP_REASON_KEEP_LATEST_5 = 'keep_latest_5'
CLEANUP_REASON_WOULD_DELETE_UPLOADED_BEYOND_LATEST_5 = 'would_delete_uploaded_beyond_latest_5'
CLEANUP_REASON_EXCLUDE_NOT_UPLOADED = 'exclude_not_uploaded'
CLEANUP_REASON_EXCLUDE_MISSING_DRIVE_FILE_ID = 'exclude_missing_drive_file_id'
CLEANUP_REASON_EXCLUDE_MISSING_UPLOADED_AT = 'exclude_missing_uploaded_at'
CLEANUP_REASON_EXCLUDE_INVALID_PATH = 'exclude_invalid_path'
CLEANUP_REASON_EXCLUDE_METADATA_PATH = 'exclude_metadata_path'
CLEANUP_REASON_EXCLUDE_INVOICE_PATH = 'exclude_invoice_path'
CLEANUP_REASON_EXCLUDE_TEMP_OR_UPLOAD_PATH = 'exclude_temp_or_upload_path'
CLEANUP_REASON_EXCLUDE_FILE_MISSING = 'exclude_file_missing'
CLEANUP_REASON_EXCLUDE_UNKNOWN_DOCUMENT_TYPE = 'exclude_unknown_document_type'

_ARCHIVE_STATUS_UPLOADED = 'uploaded'
_DOCUMENT_TYPE_TO_FOLDER = {
    'receipt': 'receipts',
    'incoming_invoice': 'incoming_invoices',
}
_EXCLUDED_ROOTS = {'contracts', 'uploads', 'temp'}


@dataclass(frozen=True)
class AccountingOriginalCleanupDryRunItem:
    workspace_id: str
    document_id: str
    document_type: str
    local_file_path: str
    metadata_path: str | None
    archive_status: str
    drive_file_id: str | None
    uploaded_at: str | None
    group_key: tuple[str, str]
    rank_in_group: int | None
    action: str
    reason: str


@dataclass(frozen=True)
class AccountingOriginalCleanupDryRunResult:
    scanned_count: int
    keep_count: int
    would_delete_count: int
    excluded_count: int
    items: tuple[AccountingOriginalCleanupDryRunItem, ...]


@dataclass(frozen=True)
class _EligibleOriginal:
    row: sqlite3.Row
    uploaded_at: datetime
    local_file_path: str
    group_key: tuple[str, str]


class AccountingOriginalCleanupService:
    def __init__(self, db_path: Path, storage_dir: Path) -> None:
        self._db_path = db_path
        self._storage_dir = storage_dir

    def dry_run(self) -> AccountingOriginalCleanupDryRunResult:
        rows = self._read_archive_state_rows()
        excluded: list[AccountingOriginalCleanupDryRunItem] = []
        eligible_by_group: dict[tuple[str, str], list[_EligibleOriginal]] = {}

        for row in rows:
            eligible, excluded_item = self._classify_before_grouping(row)
            if excluded_item is not None:
                excluded.append(excluded_item)
                continue
            if eligible is not None:
                eligible_by_group.setdefault(eligible.group_key, []).append(eligible)

        grouped_items: list[AccountingOriginalCleanupDryRunItem] = []
        for group_key, candidates in sorted(eligible_by_group.items()):
            candidates.sort(
                key=lambda item: (
                    item.uploaded_at,
                    str(item.row['document_id']),
                    item.local_file_path,
                ),
                reverse=True,
            )
            for index, candidate in enumerate(candidates, start=1):
                if index <= 5:
                    action = CLEANUP_ACTION_KEEP
                    reason = CLEANUP_REASON_KEEP_LATEST_5
                else:
                    action = CLEANUP_ACTION_WOULD_DELETE
                    reason = CLEANUP_REASON_WOULD_DELETE_UPLOADED_BEYOND_LATEST_5
                grouped_items.append(
                    _item_from_row(
                        candidate.row,
                        group_key=group_key,
                        rank_in_group=index,
                        action=action,
                        reason=reason,
                    )
                )

        items = tuple(excluded + grouped_items)
        keep_count = sum(1 for item in items if item.action == CLEANUP_ACTION_KEEP)
        would_delete_count = sum(1 for item in items if item.action == CLEANUP_ACTION_WOULD_DELETE)
        excluded_count = sum(1 for item in items if item.action == CLEANUP_ACTION_EXCLUDE)
        return AccountingOriginalCleanupDryRunResult(
            scanned_count=len(rows),
            keep_count=keep_count,
            would_delete_count=would_delete_count,
            excluded_count=excluded_count,
            items=items,
        )

    def _read_archive_state_rows(self) -> list[sqlite3.Row]:
        if not self._db_path.exists():
            return []
        db_uri = f"file:{quote(self._db_path.resolve().as_posix(), safe='/:')}?mode=ro"
        try:
            with sqlite3.connect(db_uri, uri=True) as connection:
                connection.row_factory = sqlite3.Row
                return list(
                    connection.execute(
                        (
                            'SELECT document_id, workspace_id, telegram_id, document_type, '
                            'metadata_path, local_file_path, archive_status, latest_job_id, '
                            'drive_file_id, drive_folder_id, uploaded_at, last_error_code, '
                            'created_at, updated_at '
                            'FROM accounting_document_archive_state '
                            'ORDER BY workspace_id ASC, document_type ASC, document_id ASC'
                        )
                    ).fetchall()
                )
        except sqlite3.OperationalError:
            return []

    def _classify_before_grouping(
        self,
        row: sqlite3.Row,
    ) -> tuple[_EligibleOriginal | None, AccountingOriginalCleanupDryRunItem | None]:
        group_key = (str(row['workspace_id']), str(row['document_type']))
        if row['archive_status'] != _ARCHIVE_STATUS_UPLOADED:
            return None, _excluded_item(row, group_key, CLEANUP_REASON_EXCLUDE_NOT_UPLOADED)
        if str(row['drive_file_id'] or '').strip() == '':
            return None, _excluded_item(row, group_key, CLEANUP_REASON_EXCLUDE_MISSING_DRIVE_FILE_ID)

        uploaded_at = _parse_uploaded_at(row['uploaded_at'])
        if uploaded_at is None:
            return None, _excluded_item(row, group_key, CLEANUP_REASON_EXCLUDE_MISSING_UPLOADED_AT)

        path_result = _validate_original_path(
            storage_dir=self._storage_dir,
            workspace_id=str(row['workspace_id']),
            document_type=str(row['document_type']),
            local_file_path=str(row['local_file_path']),
        )
        if path_result.reason is not None:
            return None, _excluded_item(row, group_key, path_result.reason)
        if path_result.resolved_path is None or not path_result.resolved_path.is_file():
            return None, _excluded_item(row, group_key, CLEANUP_REASON_EXCLUDE_FILE_MISSING)

        return (
            _EligibleOriginal(
                row=row,
                uploaded_at=uploaded_at,
                local_file_path=str(path_result.resolved_path),
                group_key=group_key,
            ),
            None,
        )


@dataclass(frozen=True)
class _PathValidationResult:
    resolved_path: Path | None
    reason: str | None


def _validate_original_path(
    *,
    storage_dir: Path,
    workspace_id: str,
    document_type: str,
    local_file_path: str,
) -> _PathValidationResult:
    expected_folder = _DOCUMENT_TYPE_TO_FOLDER.get(document_type)
    if expected_folder is None:
        return _PathValidationResult(None, CLEANUP_REASON_EXCLUDE_UNKNOWN_DOCUMENT_TYPE)

    raw_path = Path(local_file_path)
    if not raw_path.parts or any(part == '..' for part in raw_path.parts):
        return _PathValidationResult(None, CLEANUP_REASON_EXCLUDE_INVALID_PATH)

    storage_root = storage_dir.resolve()
    resolved_path = raw_path.resolve()
    try:
        relative = resolved_path.relative_to(storage_root)
    except ValueError:
        return _PathValidationResult(None, CLEANUP_REASON_EXCLUDE_INVALID_PATH)

    parts = relative.parts
    if not parts:
        return _PathValidationResult(None, CLEANUP_REASON_EXCLUDE_INVALID_PATH)
    if parts[0] == 'invoices':
        return _PathValidationResult(resolved_path, CLEANUP_REASON_EXCLUDE_INVOICE_PATH)
    if parts[0] in _EXCLUDED_ROOTS or 'accounting_intake' in parts:
        return _PathValidationResult(resolved_path, CLEANUP_REASON_EXCLUDE_TEMP_OR_UPLOAD_PATH)
    if 'metadata' in parts or resolved_path.suffix.lower() == '.json':
        return _PathValidationResult(resolved_path, CLEANUP_REASON_EXCLUDE_METADATA_PATH)
    if len(parts) != 9:
        return _PathValidationResult(resolved_path, CLEANUP_REASON_EXCLUDE_INVALID_PATH)
    if (
        parts[0] != 'workspaces'
        or parts[1] != workspace_id
        or parts[2] != 'years'
        or not (parts[3].isdigit() and len(parts[3]) == 4)
        or parts[4] != 'expenses'
        or not (parts[5].isdigit() and len(parts[5]) == 2)
        or parts[6] != expected_folder
        or parts[7] != 'originals'
        or not parts[8]
    ):
        return _PathValidationResult(resolved_path, CLEANUP_REASON_EXCLUDE_INVALID_PATH)
    return _PathValidationResult(resolved_path, None)


def _parse_uploaded_at(value: str | None) -> datetime | None:
    text = (value or '').strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace('Z', '+00:00'))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _excluded_item(
    row: sqlite3.Row,
    group_key: tuple[str, str],
    reason: str,
) -> AccountingOriginalCleanupDryRunItem:
    return _item_from_row(
        row,
        group_key=group_key,
        rank_in_group=None,
        action=CLEANUP_ACTION_EXCLUDE,
        reason=reason,
    )


def _item_from_row(
    row: sqlite3.Row,
    *,
    group_key: tuple[str, str],
    rank_in_group: int | None,
    action: str,
    reason: str,
) -> AccountingOriginalCleanupDryRunItem:
    return AccountingOriginalCleanupDryRunItem(
        workspace_id=str(row['workspace_id']),
        document_id=str(row['document_id']),
        document_type=str(row['document_type']),
        local_file_path=str(row['local_file_path']),
        metadata_path=row['metadata_path'],
        archive_status=str(row['archive_status']),
        drive_file_id=row['drive_file_id'],
        uploaded_at=row['uploaded_at'],
        group_key=group_key,
        rank_in_group=rank_in_group,
        action=action,
        reason=reason,
    )
