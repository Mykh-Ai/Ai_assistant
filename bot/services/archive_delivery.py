"""Validated, immutable routing and private payloads for configured archives.

No Google/Telegram/AI dependencies. Original document identity never changes.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import md5, sha256
from io import BytesIO
import json
import mimetypes
import os
from pathlib import Path
import re
import sqlite3
from typing import Any
from uuid import uuid4

from bot.services.db import managed_connection
from bot.services.accounting_document_archive_path import validate_confirmed_accounting_document_path
from bot.services.gmail_statement_archive_path import validate_gmail_statement_archive_paths
from bot.services.workspace_context import WorkspaceContextService


class ArchiveDeliveryError(ValueError):
    """Only bounded codes may cross into persisted/user-facing errors."""
    def __init__(self, code: str, *, permanent: bool = True) -> None:
        super().__init__(code)
        self.code = code
        self.permanent = permanent


DELIVERY_SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_delivery_context (
 job_id TEXT PRIMARY KEY, workspace_id TEXT NOT NULL, route_revision TEXT NOT NULL,
 company_root_folder_id TEXT NOT NULL, archive_year INTEGER NOT NULL,
 archive_month INTEGER NOT NULL, annual_folder_template TEXT NOT NULL,
 document_folder_name TEXT NOT NULL, relative_suffix TEXT NOT NULL,
 payload_mode TEXT NOT NULL, output_filename TEXT NOT NULL,
 source_sha256 TEXT NOT NULL, workspace_root TEXT NOT NULL,
 resolved_target_folder_id TEXT, payload_path TEXT, payload_sha256 TEXT,
 payload_md5 TEXT, payload_size INTEGER, payload_mime_type TEXT,
 reserved_drive_file_id TEXT, created_at TEXT NOT NULL
);
"""


def ensure_delivery_schema(connection: sqlite3.Connection) -> None:
    connection.execute(DELIVERY_SCHEMA)


@dataclass(frozen=True)
class ArchiveRoute:
    workspace_id: str
    document_type: str
    route_revision: str
    company_root_folder_id: str
    annual_folder_template: str
    document_folder_name: str
    relative_suffix_mode: str
    payload_mode: str


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ArchiveDeliveryError('archive_routes_invalid')
        value[key] = item
    return value


def configured_route(workspace_id: str, document_type: str) -> ArchiveRoute | None:
    if document_type not in {'receipt', 'bank_statement_original'}:
        return None
    name = os.getenv('GOOGLE_DRIVE_DOCUMENT_ROUTES_FILE', '').strip()
    if not name:
        return None
    path = Path(name)
    try:
        if not path.is_absolute() or path.is_symlink() or not path.is_file() or path.stat().st_size > 65536:
            raise ArchiveDeliveryError('archive_routes_invalid')
        raw = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_unique_object)
        if not isinstance(raw, dict) or set(raw) != {'schema_version', 'routes'} or type(raw['schema_version']) is not int or raw['schema_version'] != 1:
            raise ArchiveDeliveryError('archive_routes_invalid')
        if not isinstance(raw['routes'], list) or len(raw['routes']) > 200:
            raise ArchiveDeliveryError('archive_routes_invalid')
        routes = {}
        required = set(ArchiveRoute.__dataclass_fields__)
        for item in raw['routes']:
            if not isinstance(item, dict) or set(item) - {'existing_year_anchors'} != required:
                raise ArchiveDeliveryError('archive_routes_invalid')
            values = {k: item[k] for k in required}
            if any(not isinstance(v, str) or not v or len(v) > 256 or any(ord(c) < 32 for c in v) for v in values.values()):
                raise ArchiveDeliveryError('archive_routes_invalid')
            route = ArchiveRoute(**values)
            expected = {'receipt': ('blocky', 'year_month', 'original'),
                        'bank_statement_original': ('Vypisy', 'none', 'pdf_without_password')}
            if route.document_type not in expected or (route.document_folder_name, route.relative_suffix_mode, route.payload_mode) != expected[route.document_type]:
                raise ArchiveDeliveryError('archive_routes_invalid')
            if route.annual_folder_template != 'Zevs_{YYYY}' or not re.fullmatch(r'[A-Za-z0-9_-]+', route.company_root_folder_id):
                raise ArchiveDeliveryError('archive_routes_invalid')
            if not re.fullmatch(r'[A-Za-z0-9._-]+', route.route_revision):
                raise ArchiveDeliveryError('archive_routes_invalid')
            key = (route.workspace_id, route.document_type)
            if key in routes:
                raise ArchiveDeliveryError('archive_routes_invalid')
            routes[key] = route
        return routes.get((workspace_id, document_type))
    except ArchiveDeliveryError:
        raise
    except (OSError, ValueError, TypeError, KeyError):
        raise ArchiveDeliveryError('archive_routes_invalid') from None


def workspace_source_root(path: Path, storage_key: str) -> Path:
    if not path.is_absolute():
        raise ArchiveDeliveryError('archive_source_unsafe')
    parts = path.parts
    matches = [i for i in range(len(parts) - 1) if parts[i] == 'workspaces' and parts[i+1] == storage_key]
    if len(matches) != 1:
        raise ArchiveDeliveryError('archive_source_unsafe')
    root = Path(*parts[:matches[0]+2])
    _contained(path, root)
    return root


def _contained(path: Path, root: Path) -> None:
    if not path.is_absolute() or any(p in {'.', '..'} for p in path.parts):
        raise ArchiveDeliveryError('archive_source_unsafe')
    try:
        path.relative_to(root)
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ArchiveDeliveryError('archive_source_unsafe') from None
    cursor = path
    while True:
        if cursor.is_symlink():
            raise ArchiveDeliveryError('archive_source_unsafe')
        if cursor == cursor.parent:
            break
        cursor = cursor.parent


def read_source(path: Path, root: Path) -> bytes:
    _contained(path, root)
    try:
        if not path.is_file():
            raise ArchiveDeliveryError('local_file_missing')
        if path.stat().st_size > 100 * 1024 * 1024:
            raise ArchiveDeliveryError('archive_source_too_large')
        return path.read_bytes()
    except OSError:
        raise ArchiveDeliveryError('local_file_missing') from None


def make_snapshot(*, db_path: Path, workspace_id: str, telegram_id: int,
                  document_type: str, local_file_path: str, metadata_path: str | None,
                  storage_key: str | None, statement_year: int | None,
                  statement_month: int | None, storage_dir: Path | None) -> dict[str, Any] | None:
    route = configured_route(workspace_id, document_type)
    if route is None:
        return None
    context = WorkspaceContextService(db_path).require_membership(telegram_id, workspace_id)
    if storage_key != context.storage_key:
        raise ArchiveDeliveryError('archive_workspace_mismatch')
    source = Path(local_file_path)
    if storage_dir is None:
        raise ArchiveDeliveryError('archive_storage_root_required')
    root = storage_dir.resolve() / 'workspaces' / context.storage_key
    if workspace_source_root(source, context.storage_key) != root:
        raise ArchiveDeliveryError('archive_source_unsafe')
    if metadata_path:
        _contained(Path(metadata_path), root)
    if document_type == 'receipt':
        period = validate_confirmed_accounting_document_path(
            source, workspace_storage_key=context.storage_key, document_type='receipt',
            expected_leaf='originals', field_name='local_file_path')
        year, month = int(period.year), int(period.month)
        filename = source.name
    else:
        validate_gmail_statement_archive_paths(local_file_path=source, metadata_path=metadata_path,
                                              workspace_storage_key=context.storage_key)
        if type(statement_year) is not int or type(statement_month) is not int:
            raise ArchiveDeliveryError('statement_period_invalid')
        year, month = statement_year, statement_month
        ref = sha256(source.parent.name.encode()).hexdigest()[:12]
        filename = f'ZEVS_Tatra_{year:04d}-{month:02d}_{ref}.pdf'
    if not 1 <= year <= 9999 or not 1 <= month <= 12:
        raise ArchiveDeliveryError('statement_period_invalid')
    if any(ord(c) < 32 for c in filename) or filename in {'.', '..'}:
        raise ArchiveDeliveryError('archive_filename_invalid')
    original = read_source(source, root)
    return dict(workspace_id=workspace_id, route_revision=route.route_revision,
                company_root_folder_id=route.company_root_folder_id, archive_year=year,
                archive_month=month, annual_folder_template=route.annual_folder_template,
                document_folder_name=route.document_folder_name,
                relative_suffix=f'{year:04d}-{month:02d}' if route.relative_suffix_mode == 'year_month' else '',
                payload_mode=route.payload_mode, output_filename=filename,
                source_sha256=sha256(original).hexdigest(), workspace_root=str(root))


class ArchiveDeliveryStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get(self, job_id: str) -> dict[str, Any] | None:
        if not self.db_path.is_file():
            return None
        with managed_connection(self.db_path) as connection:
            # Legacy installations can read existing jobs without a new-schema write.
            if not connection.execute("SELECT 1 FROM sqlite_master WHERE name='archive_delivery_context'").fetchone():
                return None
            connection.row_factory = sqlite3.Row
            row = connection.execute('SELECT * FROM archive_delivery_context WHERE job_id=?', (job_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def insert(connection: sqlite3.Connection, job_id: str, snapshot: dict[str, Any], timestamp: str) -> None:
        values = dict(snapshot, job_id=job_id, created_at=timestamp)
        columns = tuple(values)
        connection.execute(f"INSERT INTO archive_delivery_context ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})", tuple(values.values()))

    def set_once(self, job_id: str, **values) -> dict[str, Any]:
        allowed = {'payload_path', 'payload_sha256', 'payload_md5', 'payload_size', 'payload_mime_type',
                   'resolved_target_folder_id', 'reserved_drive_file_id'}
        if not values or not set(values) <= allowed:
            raise ArchiveDeliveryError('archive_context_invalid')
        with managed_connection(self.db_path) as connection:
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute('SELECT * FROM archive_delivery_context WHERE job_id=?', (job_id,)).fetchone()
            if row is None:
                raise ArchiveDeliveryError('archive_context_missing')
            for k, v in values.items():
                if row[k] is not None and row[k] != v:
                    raise ArchiveDeliveryError('archive_context_mismatch')
            connection.execute('UPDATE archive_delivery_context SET '+','.join(f'{k}=?' for k in values)+' WHERE job_id=?', (*values.values(), job_id))
            connection.commit()
        return self.get(job_id)

    def reserve_file(self, job_id: str, proposed_id: str) -> str:
        with managed_connection(self.db_path) as connection:
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('UPDATE archive_delivery_context SET reserved_drive_file_id=? WHERE job_id=? AND reserved_drive_file_id IS NULL', (proposed_id, job_id))
            row = connection.execute('SELECT reserved_drive_file_id FROM archive_delivery_context WHERE job_id=?', (job_id,)).fetchone()
            connection.commit()
            if not row or not row[0]:
                raise ArchiveDeliveryError('archive_context_missing')
            return str(row[0])


def _unsigned_pdf(content: bytes, password: str | None) -> bytes:
    from pypdf import PdfReader, PdfWriter
    try:
        reader = PdfReader(BytesIO(content), strict=False)
        encrypted = reader.is_encrypted
        if encrypted and (password is None or not reader.decrypt(password)):
            raise ArchiveDeliveryError('password_required' if password is None else 'password_invalid')
        # /SigFlags covers document-level signature intent; scan all form fields too.
        root = reader.trailer['/Root']
        form = root.get('/AcroForm')
        form = form.get_object() if form else {}
        if form.get('/SigFlags') or any(v.get('/FT') == '/Sig' or v.get('/V', {}).get('/Type') == '/Sig'
                                      for v in (reader.get_fields() or {}).values()):
            raise ArchiveDeliveryError('signed_pdf_requires_review')
        if not encrypted:
            return content
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        output = BytesIO()
        writer.write(output)
        result = output.getvalue()
        check = PdfReader(BytesIO(result))
        if check.is_encrypted or len(check.pages) != len(reader.pages):
            raise ArchiveDeliveryError('archive_pdf_verification_failed')
        for before, after in zip(reader.pages, check.pages):
            if (before.extract_text() or '') != (after.extract_text() or '') or list(before.mediabox) != list(after.mediabox):
                raise ArchiveDeliveryError('archive_pdf_verification_failed')
        return result
    except ArchiveDeliveryError:
        raise
    except Exception:
        raise ArchiveDeliveryError('pdf_unreadable') from None


def prepare_payload(store: ArchiveDeliveryStore, job, *, storage_dir: Path | None, password_loader=None) -> Path:
    context = store.get(job.job_id)
    if not context or context['workspace_id'] != job.workspace_id:
        raise ArchiveDeliveryError('archive_workspace_mismatch')
    membership = WorkspaceContextService(store.db_path).require_membership(job.telegram_id, job.workspace_id)
    if storage_dir is None:
        raise ArchiveDeliveryError('archive_storage_root_required')
    root = storage_dir.resolve() / 'workspaces' / membership.storage_key
    if context['workspace_root'] != str(root):
        raise ArchiveDeliveryError('archive_workspace_mismatch')
    if root.name != membership.storage_key or workspace_source_root(Path(job.local_file_path), membership.storage_key) != root:
        raise ArchiveDeliveryError('archive_workspace_mismatch')
    source = read_source(Path(job.local_file_path), root)
    if sha256(source).hexdigest() != context['source_sha256']:
        raise ArchiveDeliveryError('archive_source_changed')
    if context['payload_path']:
        payload = Path(context['payload_path'])
        content = read_source(payload, root)
        if sha256(content).hexdigest() != context['payload_sha256'] or len(content) != context['payload_size']:
            raise ArchiveDeliveryError('archive_payload_changed')
        return payload
    if context['reserved_drive_file_id']:
        raise ArchiveDeliveryError('archive_payload_missing')
    if context['payload_mode'] == 'pdf_without_password':
        try:
            content = _unsigned_pdf(source, None)
        except ArchiveDeliveryError as error:
            if error.code != 'password_required':
                raise
            try:
                if password_loader is None:
                    from bot.services.google_gmail_config import load_google_gmail_config, load_statement_pdf_open_password
                    password_loader = lambda: load_statement_pdf_open_password(load_google_gmail_config())
                password = password_loader()
            except Exception:
                raise ArchiveDeliveryError('password_secret_unavailable') from None
            content = _unsigned_pdf(source, password)
        # Reuse existing period detector; never reassign a frozen year/month.
        from bot.services.gmail_statement_period import detect_gmail_statement_period
        period = detect_gmail_statement_period(content)
        if (period.period_year, period.period_month) != (context['archive_year'], context['archive_month']):
            raise ArchiveDeliveryError('statement_period_mismatch')
        directory = root / 'archive_payloads' / job.job_id
        _contained(directory, root)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(directory.parent, 0o700)
        os.chmod(directory, 0o700)
        payload = directory / 'statement.pdf'
        _contained(payload, root)
        temporary = directory / ('.tmp-' + uuid4().hex)
        try:
            descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(descriptor, 'wb') as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, payload)
        finally:
            temporary.unlink(missing_ok=True)
        mime = 'application/pdf'
    else:
        payload, content = Path(job.local_file_path), source
        mime = mimetypes.guess_type(payload.name)[0] or 'application/octet-stream'
    store.set_once(job.job_id, payload_path=str(payload), payload_sha256=sha256(content).hexdigest(),
                   payload_md5=md5(content).hexdigest(), payload_size=len(content), payload_mime_type=mime)
    return payload


def cleanup_payload(store: ArchiveDeliveryStore, job, *, storage_dir: Path | None) -> None:
    context = store.get(job.job_id)
    if not context or context['payload_mode'] != 'pdf_without_password':
        return
    if job.status not in {'uploaded', 'failed'} or job.lease_until is not None:
        raise ArchiveDeliveryError('archive_payload_unsafe')
    if storage_dir is None:
        raise ArchiveDeliveryError('archive_storage_root_required')
    root = Path(context['workspace_root'])
    if root.parent != storage_dir.resolve() / 'workspaces':
        raise ArchiveDeliveryError('archive_payload_unsafe')
    expected = root / 'archive_payloads' / job.job_id / 'statement.pdf'
    if context['payload_path'] and Path(context['payload_path']) != expected:
        raise ArchiveDeliveryError('archive_payload_unsafe')
    _contained(expected, root)
    expected.unlink(missing_ok=True)
    if expected.parent.is_dir():
        for temporary in expected.parent.iterdir():
            if re.fullmatch(r'\.tmp-[a-f0-9]{32}', temporary.name):
                _contained(temporary, root)
                if temporary.is_file():
                    temporary.unlink()
