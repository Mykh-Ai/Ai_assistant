from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
from typing import Callable
from uuid import uuid4

from bot.services.db import managed_connection
from bot.services.gmail_readonly_adapter import (
    GmailAttachmentCandidate,
    GmailReadonlyAdapter,
    GmailReadonlyError,
    GmailReadonlyNeedsReauth,
)
from bot.services.gmail_statement_period import (
    GmailStatementPeriodResult,
    STATEMENT_PERIOD_NOT_PDF,
    detect_gmail_statement_period,
)
from bot.services.workspace_context import WorkspaceContext


GMAIL_STATEMENT_IMPORT_SCHEMA = """
CREATE TABLE IF NOT EXISTS gmail_statement_imports (
    import_id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    connection_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    gmail_message_id TEXT NOT NULL,
    gmail_thread_id TEXT,
    source_attachment_key TEXT NOT NULL,
    gmail_attachment_id TEXT,
    mime_part_id TEXT,
    sender TEXT,
    subject TEXT,
    gmail_internal_date TEXT,
    original_filename TEXT NOT NULL,
    safe_display_filename TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    size_bytes INTEGER,
    sha256 TEXT,
    local_original_path TEXT,
    local_metadata_path TEXT,
    collection_status TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    statement_period_status TEXT NOT NULL DEFAULT 'not_checked',
    statement_period_start TEXT,
    statement_period_end TEXT,
    statement_period_year INTEGER,
    statement_period_month INTEGER,
    statement_period_source TEXT,
    statement_period_error_code TEXT,
    duplicate_of_import_id TEXT,
    archive_status TEXT NOT NULL,
    archive_job_id TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    claim_token TEXT,
    claim_expires_at TEXT,
    last_error_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    stored_at TEXT,
    notified_at TEXT,
    UNIQUE(workspace_id, gmail_message_id, source_attachment_key)
);
CREATE INDEX IF NOT EXISTS ix_gmail_statement_content_dedup
ON gmail_statement_imports(workspace_id, sha256, collection_status);
"""


class GmailStatementCollectorError(RuntimeError):
    pass


@dataclass(frozen=True)
class GmailStatementPolicy:
    maximum_bytes: int
    allowed_mime_types: frozenset[str]
    allowed_extensions: frozenset[str]


@dataclass(frozen=True)
class GmailStatementImportResult:
    import_id: str
    status: str
    duplicate_of_import_id: str | None = None
    local_original_path: str | None = None
    local_metadata_path: str | None = None
    safe_display_filename: str | None = None
    size_bytes: int | None = None
    statement_period_status: str = "not_checked"
    statement_period_start: str | None = None
    statement_period_end: str | None = None
    statement_period_year: int | None = None
    statement_period_month: int | None = None
    statement_period_source: str | None = None
    statement_period_error_code: str | None = None


@dataclass(frozen=True)
class GmailCollectorRunResult:
    messages_seen: int
    candidates_seen: int
    stored: int
    duplicate_source: int
    duplicate_content: int
    rejected: int
    failed: int
    new_imports: tuple[GmailStatementImportResult, ...] = ()


def ensure_gmail_statement_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(GMAIL_STATEMENT_IMPORT_SCHEMA)
    columns = {
        str(row[1])
        for row in connection.execute("PRAGMA table_info(gmail_statement_imports)")
    }
    additions = {
        "statement_period_status": "TEXT NOT NULL DEFAULT 'not_checked'",
        "statement_period_start": "TEXT",
        "statement_period_end": "TEXT",
        "statement_period_year": "INTEGER",
        "statement_period_month": "INTEGER",
        "statement_period_source": "TEXT",
        "statement_period_error_code": "TEXT",
    }
    for name, definition in additions.items():
        if name not in columns:
            connection.execute(
                f"ALTER TABLE gmail_statement_imports ADD COLUMN {name} {definition}"
            )


class GmailStatementStore:
    def __init__(self, db_path: Path, storage_root: Path) -> None:
        self._db_path = db_path
        self._storage_root = storage_root.resolve()

    def ensure_schema(self) -> None:
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.commit()

    def source_exists(
        self, *, workspace_id: str, message_id: str, source_attachment_key: str
    ) -> bool:
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            row = connection.execute(
                "SELECT collection_status FROM gmail_statement_imports "
                "WHERE workspace_id=? AND gmail_message_id=? "
                "AND source_attachment_key=?",
                (workspace_id, message_id, source_attachment_key),
            ).fetchone()
        return row is not None and str(row[0]) == "stored"

    def mark_archive_enqueued(
        self, import_id: str, archive_job_id: str, *, now: datetime | None = None
    ) -> None:
        timestamp = _utc_now(now).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.execute(
                "UPDATE gmail_statement_imports SET archive_status='archive_pending', "
                "archive_job_id=?, updated_at=? WHERE import_id=? "
                "AND collection_status='stored'",
                (archive_job_id, timestamp, import_id),
            )
            connection.commit()

    def mark_archive_failed(
        self, import_id: str, error_code: str, *, now: datetime | None = None
    ) -> None:
        timestamp = _utc_now(now).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.execute(
                "UPDATE gmail_statement_imports SET archive_status='archive_failed', "
                "last_error_code=?, updated_at=? WHERE import_id=? "
                "AND collection_status='stored'",
                (error_code[:128], timestamp, import_id),
            )
            connection.commit()

    def mark_archive_withheld(
        self, import_id: str, error_code: str, *, now: datetime | None = None
    ) -> None:
        timestamp = _utc_now(now).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.execute(
                "UPDATE gmail_statement_imports "
                "SET archive_status='period_review_required', last_error_code=?, "
                "updated_at=? WHERE import_id=? AND collection_status='stored'",
                (error_code[:128], timestamp, import_id),
            )
            connection.commit()

    def mark_notified(self, import_id: str, *, now: datetime | None = None) -> None:
        timestamp = _utc_now(now).isoformat()
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.execute(
                "UPDATE gmail_statement_imports SET notified_at=?, updated_at=? "
                "WHERE import_id=? AND collection_status='stored'",
                (timestamp, timestamp, import_id),
            )
            connection.commit()

    def store(
        self,
        *,
        workspace: WorkspaceContext,
        connection_id: str,
        candidate: GmailAttachmentCandidate,
        content: bytes,
        policy: GmailStatementPolicy,
        statement_period: GmailStatementPeriodResult | None = None,
        now: datetime | None = None,
    ) -> GmailStatementImportResult:
        # Commit any additive legacy-schema upgrade before the explicit storage
        # transaction begins; ALTER TABLE must never be left implicit here.
        self.ensure_schema()
        _validate_workspace(workspace)
        connection_id = _required(connection_id, "connection_id", 128)
        safe_name, extension = _validate_attachment(candidate, content, policy)
        timestamp = _utc_now(now)
        period = statement_period or GmailStatementPeriodResult(
            status="not_checked", error_code="not_checked"
        )
        import_id = str(uuid4())
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.row_factory = sqlite3.Row
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT import_id, collection_status, duplicate_of_import_id,
                       local_original_path, local_metadata_path,
                       safe_display_filename, size_bytes,
                       statement_period_status, statement_period_start,
                       statement_period_end, statement_period_year,
                       statement_period_month, statement_period_source,
                       statement_period_error_code
                FROM gmail_statement_imports
                WHERE workspace_id=? AND gmail_message_id=?
                      AND source_attachment_key=?
                """,
                (
                    workspace.workspace_id,
                    candidate.message_id,
                    candidate.source_attachment_key,
                ),
            ).fetchone()
            if existing is not None and str(existing["collection_status"]) == "stored":
                connection.rollback()
                return GmailStatementImportResult(
                    import_id=str(existing["import_id"]),
                    status="duplicate_source",
                    duplicate_of_import_id=existing["duplicate_of_import_id"],
                    local_original_path=existing["local_original_path"],
                    local_metadata_path=existing["local_metadata_path"],
                    safe_display_filename=existing["safe_display_filename"],
                    size_bytes=existing["size_bytes"],
                    statement_period_status=str(existing["statement_period_status"]),
                    statement_period_start=existing["statement_period_start"],
                    statement_period_end=existing["statement_period_end"],
                    statement_period_year=existing["statement_period_year"],
                    statement_period_month=existing["statement_period_month"],
                    statement_period_source=existing["statement_period_source"],
                    statement_period_error_code=existing[
                        "statement_period_error_code"
                    ],
                )
            if existing is not None:
                import_id = str(existing["import_id"])
                connection.execute(
                    "UPDATE gmail_statement_imports SET collection_status='downloading', "
                    "attempt_count=attempt_count+1, next_attempt_at=NULL, "
                    "last_error_code=NULL, updated_at=? WHERE import_id=?",
                    (timestamp.isoformat(), import_id),
                )
                connection.commit()
            else:
                connection.execute(
                """
                INSERT INTO gmail_statement_imports
                (import_id, workspace_id, connection_id, source_type,
                 gmail_message_id, gmail_thread_id, source_attachment_key,
                 gmail_attachment_id, mime_part_id, sender, subject,
                 gmail_internal_date, original_filename, safe_display_filename,
                 mime_type, collection_status, parse_status, archive_status,
                 attempt_count, created_at, updated_at)
                VALUES (?, ?, ?, 'gmail', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        'downloading', 'deferred', 'not_configured', 1, ?, ?)
                """,
                (
                    import_id,
                    workspace.workspace_id,
                    connection_id,
                    candidate.message_id,
                    candidate.thread_id,
                    candidate.source_attachment_key,
                    candidate.gmail_attachment_id,
                    candidate.mime_part_id,
                    candidate.sender,
                    candidate.subject,
                    candidate.internal_date,
                    candidate.filename,
                    safe_name,
                    candidate.mime_type,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                ),
                )
                connection.commit()

        digest = hashlib.sha256(content).hexdigest()
        with managed_connection(self._db_path) as connection:
            ensure_gmail_statement_schema(connection)
            connection.row_factory = sqlite3.Row
            duplicate = connection.execute(
                """
                SELECT import_id, local_original_path
                FROM gmail_statement_imports
                WHERE workspace_id=? AND sha256=? AND collection_status='stored'
                ORDER BY stored_at, import_id LIMIT 1
                """,
                (workspace.workspace_id, digest),
            ).fetchone()
        try:
            if duplicate is not None:
                metadata_path = self._write_duplicate_metadata(
                    workspace=workspace,
                    import_id=import_id,
                    candidate=candidate,
                    digest=digest,
                    size=len(content),
                    canonical_import_id=str(duplicate["import_id"]),
                    canonical_path=str(duplicate["local_original_path"]),
                    timestamp=timestamp,
                    statement_period=period,
                )
                original_path = str(duplicate["local_original_path"])
                status = "duplicate_content"
                duplicate_id = str(duplicate["import_id"])
            else:
                original_path, metadata_path = self._write_original_atomically(
                    workspace=workspace,
                    import_id=import_id,
                    extension=extension,
                    candidate=candidate,
                    content=content,
                    digest=digest,
                    timestamp=timestamp,
                    statement_period=period,
                )
                status = "stored"
                duplicate_id = None
        except Exception:
            self._mark_failed(import_id, "gmail_storage_failed")
            raise

        with managed_connection(self._db_path) as connection:
            connection.execute(
                """
                UPDATE gmail_statement_imports
                SET size_bytes=?, sha256=?, local_original_path=?,
                    local_metadata_path=?, collection_status='stored',
                    duplicate_of_import_id=?, updated_at=?, stored_at=?,
                    statement_period_status=?, statement_period_start=?,
                    statement_period_end=?, statement_period_year=?,
                    statement_period_month=?, statement_period_source=?,
                    statement_period_error_code=?, last_error_code=NULL
                WHERE import_id=? AND collection_status='downloading'
                """,
                (
                    len(content),
                    digest,
                    original_path,
                    metadata_path,
                    duplicate_id,
                    timestamp.isoformat(),
                    timestamp.isoformat(),
                    period.status,
                    _date_iso(period.start_date),
                    _date_iso(period.end_date),
                    period.period_year,
                    period.period_month,
                    period.source,
                    period.error_code,
                    import_id,
                ),
            )
            connection.commit()
        return GmailStatementImportResult(
            import_id=import_id,
            status=status,
            duplicate_of_import_id=duplicate_id,
            local_original_path=original_path,
            local_metadata_path=metadata_path,
            safe_display_filename=safe_name,
            size_bytes=len(content),
            statement_period_status=period.status,
            statement_period_start=_date_iso(period.start_date),
            statement_period_end=_date_iso(period.end_date),
            statement_period_year=period.period_year,
            statement_period_month=period.period_month,
            statement_period_source=period.source,
            statement_period_error_code=period.error_code,
        )

    def _write_original_atomically(
        self,
        *,
        workspace: WorkspaceContext,
        import_id: str,
        extension: str,
        candidate: GmailAttachmentCandidate,
        content: bytes,
        digest: str,
        timestamp: datetime,
        statement_period: GmailStatementPeriodResult,
    ) -> tuple[str, str]:
        month_root = self._month_root(workspace, timestamp)
        final_dir = month_root / import_id
        temp_dir = month_root / f".tmp-{import_id}"
        month_root.mkdir(parents=True, exist_ok=True)
        self._assert_contained(month_root)
        if final_dir.exists():
            final_original = final_dir / f"original{extension}"
            final_metadata = final_dir / "metadata.json"
            if (
                final_original.is_file()
                and final_metadata.is_file()
                and _sha256_file(final_original) == digest
            ):
                return str(final_original), str(final_metadata)
            raise GmailStatementCollectorError("gmail_import_path_conflict")
        if temp_dir.exists():
            self._assert_contained(temp_dir)
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        try:
            original = temp_dir / f"original{extension}"
            with original.open("xb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            metadata = temp_dir / "metadata.json"
            model = _metadata_model(
                workspace,
                import_id,
                candidate,
                digest,
                len(content),
                timestamp,
                statement_period=statement_period,
            )
            _write_json(metadata, model)
            temp_dir.replace(final_dir)
            final_original = final_dir / original.name
            final_metadata = final_dir / metadata.name
            if not final_original.is_file() or not final_metadata.is_file():
                raise GmailStatementCollectorError("gmail_storage_verification_failed")
            return str(final_original), str(final_metadata)
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise

    def _write_duplicate_metadata(
        self,
        *,
        workspace: WorkspaceContext,
        import_id: str,
        candidate: GmailAttachmentCandidate,
        digest: str,
        size: int,
        canonical_import_id: str,
        canonical_path: str,
        timestamp: datetime,
        statement_period: GmailStatementPeriodResult,
    ) -> str:
        canonical = Path(canonical_path).resolve()
        self._assert_contained(canonical)
        if not canonical.is_file():
            raise GmailStatementCollectorError("gmail_duplicate_original_missing")
        month_root = self._month_root(workspace, timestamp)
        final_dir = month_root / import_id
        temp_dir = month_root / f".tmp-{import_id}"
        month_root.mkdir(parents=True, exist_ok=True)
        self._assert_contained(month_root)
        if final_dir.exists():
            existing_metadata = final_dir / "metadata.json"
            if existing_metadata.is_file():
                return str(existing_metadata)
            raise GmailStatementCollectorError("gmail_import_path_conflict")
        if temp_dir.exists():
            self._assert_contained(temp_dir)
            shutil.rmtree(temp_dir)
        temp_dir.mkdir()
        try:
            model = _metadata_model(
                workspace,
                import_id,
                candidate,
                digest,
                size,
                timestamp,
                statement_period=statement_period,
                duplicate_of_import_id=canonical_import_id,
                canonical_original_path=canonical_path,
            )
            metadata = temp_dir / "metadata.json"
            _write_json(metadata, model)
            temp_dir.replace(final_dir)
            final_metadata = final_dir / "metadata.json"
            if not final_metadata.is_file():
                raise GmailStatementCollectorError("gmail_storage_verification_failed")
            return str(final_metadata)
        except Exception:
            if temp_dir.exists():
                shutil.rmtree(temp_dir)
            raise

    def _month_root(
        self, workspace: WorkspaceContext, timestamp: datetime
    ) -> Path:
        root = (
            self._storage_root
            / "workspaces"
            / workspace.storage_key
            / "bank_statement_imports"
            / "gmail"
            / f"{timestamp.year:04d}"
            / f"{timestamp.month:02d}"
        )
        self._assert_contained(root)
        return root

    def _assert_contained(self, path: Path) -> None:
        try:
            path.resolve().relative_to(self._storage_root)
        except ValueError:
            raise GmailStatementCollectorError("gmail_storage_escape") from None
        current = path
        while current != self._storage_root and current.exists():
            if current.is_symlink():
                raise GmailStatementCollectorError("gmail_storage_symlink")
            current = current.parent

    def _mark_failed(self, import_id: str, error_code: str) -> None:
        with managed_connection(self._db_path) as connection:
            connection.execute(
                """
                UPDATE gmail_statement_imports SET collection_status='failed',
                last_error_code=?, updated_at=? WHERE import_id=?
                """,
                (error_code, datetime.now(UTC).isoformat(), import_id),
            )
            connection.commit()


class GmailStatementCollector:
    def __init__(
        self,
        *,
        adapter: GmailReadonlyAdapter,
        store: GmailStatementStore,
        resolve_workspace: Callable[[str], WorkspaceContext],
        workspace_id: str,
        connection_id: str,
        policy: GmailStatementPolicy,
        pdf_open_password: str | None = None,
    ) -> None:
        self._adapter = adapter
        self._store = store
        self._resolve_workspace = resolve_workspace
        self._workspace_id = _required(workspace_id, "workspace_id", 128)
        self._connection_id = _required(connection_id, "connection_id", 128)
        self._policy = policy
        self._pdf_open_password = pdf_open_password
        self._running = False

    def run_once(self) -> GmailCollectorRunResult:
        if self._running:
            raise GmailStatementCollectorError("gmail_collector_overlap")
        self._running = True
        counts = {
            "messages_seen": 0,
            "candidates_seen": 0,
            "stored": 0,
            "duplicate_source": 0,
            "duplicate_content": 0,
            "rejected": 0,
            "failed": 0,
        }
        new_imports: list[GmailStatementImportResult] = []
        try:
            workspace = self._resolve_workspace(self._workspace_id)
            if workspace.workspace_id != self._workspace_id:
                raise GmailStatementCollectorError("gmail_workspace_mismatch")
            message_ids = self._adapter.list_message_ids()
            counts["messages_seen"] = len(message_ids)
            for message_id in message_ids:
                try:
                    candidates = self._adapter.attachment_candidates(message_id)
                except GmailReadonlyNeedsReauth:
                    raise
                except GmailReadonlyError:
                    counts["failed"] += 1
                    continue
                counts["candidates_seen"] += len(candidates)
                for candidate in candidates:
                    try:
                        if self._store.source_exists(
                            workspace_id=workspace.workspace_id,
                            message_id=candidate.message_id,
                            source_attachment_key=candidate.source_attachment_key,
                        ):
                            counts["duplicate_source"] += 1
                            continue
                        if not _candidate_allowed(candidate, self._policy):
                            counts["rejected"] += 1
                            continue
                        content = self._adapter.download(
                            candidate, maximum=self._policy.maximum_bytes
                        )
                        if Path(candidate.filename).suffix.lower() == ".pdf":
                            statement_period = detect_gmail_statement_period(
                                content, open_password=self._pdf_open_password
                            )
                        else:
                            statement_period = GmailStatementPeriodResult(
                                status=STATEMENT_PERIOD_NOT_PDF,
                                error_code=STATEMENT_PERIOD_NOT_PDF,
                            )
                        result = self._store.store(
                            workspace=workspace,
                            connection_id=self._connection_id,
                            candidate=candidate,
                            content=content,
                            policy=self._policy,
                            statement_period=statement_period,
                        )
                        counts[result.status] += 1
                        if result.status == "stored":
                            new_imports.append(result)
                    except GmailReadonlyNeedsReauth:
                        raise
                    except (GmailReadonlyError, GmailStatementCollectorError):
                        counts["failed"] += 1
            return GmailCollectorRunResult(**counts, new_imports=tuple(new_imports))
        finally:
            self._running = False


def _validate_attachment(
    candidate: GmailAttachmentCandidate,
    content: bytes,
    policy: GmailStatementPolicy,
) -> tuple[str, str]:
    if not content:
        raise GmailStatementCollectorError("gmail_attachment_empty")
    if len(content) > policy.maximum_bytes:
        raise GmailStatementCollectorError("gmail_attachment_too_large")
    if not _candidate_allowed(candidate, policy):
        raise GmailStatementCollectorError("gmail_attachment_unsupported")
    name = candidate.filename.replace("\\", "/").split("/")[-1].strip()
    if (
        not name
        or len(name) > 255
        or any(ord(c) < 32 for c in name)
        or name in {".", ".."}
    ):
        raise GmailStatementCollectorError("gmail_filename_invalid")
    extension = Path(name).suffix.lower()
    if (
        candidate.mime_type.lower() == "application/octet-stream"
        and (extension != ".pdf" or not content.startswith(b"%PDF-"))
    ):
        raise GmailStatementCollectorError("gmail_attachment_signature_invalid")
    safe = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    if not safe:
        safe = f"statement{extension}"
    return safe[:255], extension


def _candidate_allowed(
    candidate: GmailAttachmentCandidate, policy: GmailStatementPolicy
) -> bool:
    extension = Path(candidate.filename.replace("\\", "/").split("/")[-1]).suffix.lower()
    return (
        candidate.mime_type.lower() in policy.allowed_mime_types
        and extension in policy.allowed_extensions
    )


def _validate_workspace(workspace: WorkspaceContext) -> None:
    _required(workspace.workspace_id, "workspace_id", 128)
    storage_key = _required(workspace.storage_key, "workspace_storage_key", 128)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", storage_key):
        raise GmailStatementCollectorError("gmail_workspace_storage_key_invalid")


def _metadata_model(
    workspace: WorkspaceContext,
    import_id: str,
    candidate: GmailAttachmentCandidate,
    digest: str,
    size: int,
    timestamp: datetime,
    *,
    statement_period: GmailStatementPeriodResult,
    duplicate_of_import_id: str | None = None,
    canonical_original_path: str | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "import_id": import_id,
        "workspace_id": workspace.workspace_id,
        "workspace_storage_key": workspace.storage_key,
        "source_type": "gmail",
        "gmail_message_id": candidate.message_id,
        "gmail_thread_id": candidate.thread_id,
        "source_attachment_key": candidate.source_attachment_key,
        "sender": candidate.sender,
        "subject": candidate.subject,
        "gmail_internal_date": candidate.internal_date,
        "original_filename": candidate.filename,
        "mime_type": candidate.mime_type,
        "size_bytes": size,
        "sha256": digest,
        "collection_status": "stored",
        "parse_status": "deferred",
        "statement_period_status": statement_period.status,
        "statement_period_start": _date_iso(statement_period.start_date),
        "statement_period_end": _date_iso(statement_period.end_date),
        "statement_period_year": statement_period.period_year,
        "statement_period_month": statement_period.period_month,
        "statement_period_source": statement_period.source,
        "statement_period_error_code": statement_period.error_code,
        "archive_status": "not_configured",
        "duplicate_of_import_id": duplicate_of_import_id,
        "canonical_original_path": canonical_original_path,
        "stored_at": timestamp.isoformat(),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    data = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode(
        "utf-8"
    )
    with temporary.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def _date_iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _required(value: object, field: str, maximum: int = 4096) -> str:
    text = str(value).strip() if value is not None else ""
    if not text or len(text) > maximum or any(c in text for c in "\r\n\x00"):
        raise GmailStatementCollectorError(f"{field}_invalid")
    return text


def _utc_now(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
