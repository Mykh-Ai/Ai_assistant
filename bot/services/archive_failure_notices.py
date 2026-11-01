"""Durable, tenant-scoped archive failure delivery; no FSM/keyboard ownership."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha256
import html
import logging
import os
from pathlib import Path
import sqlite3
from uuid import uuid4

from bot.services.db import managed_connection
from bot.services.archive_delivery import _contained, ArchiveDeliveryError
from bot.services.workspace_context import WorkspaceContextService, WorkspaceContextError

logger = logging.getLogger(__name__)
SCHEMA = """
CREATE TABLE IF NOT EXISTS archive_failure_notices (
 event_key TEXT PRIMARY KEY, job_id TEXT, document_id TEXT NOT NULL,
 workspace_id TEXT NOT NULL, recipient_telegram_id INTEGER NOT NULL,
 failure_kind TEXT NOT NULL, safe_error_code TEXT NOT NULL,
 safe_display_name TEXT NOT NULL, local_file_path TEXT NOT NULL,
 upload_attempts INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
 status TEXT NOT NULL, delivery_attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt_at TEXT, locked_by TEXT, lease_until TEXT, sent_at TEXT,
 telegram_message_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
"""
SAFE_CODES = frozenset('''archive_failed archive_enqueue_failed archive_disabled
password_required password_invalid password_secret_unavailable pdf_unreadable
signed_pdf_requires_review statement_period_invalid statement_period_mismatch
period_ambiguous text_unavailable not_pdf archive_routes_invalid
archive_folder_forbidden archive_folder_mismatch archive_folder_ambiguous
archive_folder_listing_incomplete archive_id_unavailable archive_remote_mismatch
archive_upload_unconfirmed archive_source_unsafe archive_source_changed
archive_source_too_large archive_payload_changed archive_payload_missing
archive_workspace_mismatch archive_context_missing archive_context_mismatch
archive_context_invalid archive_pdf_verification_failed local_file_missing archive_storage_root_required archive_routed_provider_unsupported
upload_transient_failed upload_permanent_failed upload_unexpected_failed
provider_unavailable google_drive_not_configured archive_authority_revoked'''.split())


def utc(now=None):
    value = now or datetime.now(UTC)
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def configured_cutoff() -> str | None:
    raw = os.getenv('GOOGLE_DRIVE_FAILURE_NOTICE_CUTOFF', '').strip()
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(raw)
        if value.tzinfo is None:
            raise ValueError
        return value.astimezone(UTC).isoformat()
    except ValueError:
        raise ValueError('archive_notice_cutoff_invalid') from None


class ArchiveFailureNoticeStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    def _prepare(self, connection, cutoff):
        connection.execute(SCHEMA)
        # Persist the activation boundary. Changing env must never silently replay history.
        values = ('archive-notices:activation', None, '', '', 0, 'activation', 'archive_failed', '', '',
                  0, 0, 'activation', cutoff, cutoff)
        connection.execute('INSERT OR IGNORE INTO archive_failure_notices (event_key,job_id,document_id,workspace_id,recipient_telegram_id,failure_kind,safe_error_code,safe_display_name,local_file_path,upload_attempts,max_attempts,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', values)
        stored = connection.execute("SELECT created_at FROM archive_failure_notices WHERE event_key='archive-notices:activation'").fetchone()
        if stored[0] != cutoff:
            raise ValueError('archive_notice_cutoff_changed')

    def enqueue(self, *, workspace_id: str, recipient: int, document_id: str, error_code: str,
                local_file_path: str, job_id: str | None = None, attempts: int = 0,
                max_attempts: int = 5, now=None) -> bool:
        cutoff = configured_cutoff()
        timestamp = utc(now).isoformat()
        if cutoff is None or timestamp < cutoff:
            return False
        code = error_code if error_code in SAFE_CODES else 'archive_failed'
        kind = 'archive_failed' if job_id else 'archive_prequeue_failed'
        # One terminal/review event per business source; no raw exceptions or names in keys.
        ref = job_id or workspace_id + ':' + document_id
        key = sha256((kind + ':' + ref).encode()).hexdigest()
        name = Path(local_file_path).name[:160]
        name = ''.join(c for c in name if ord(c) >= 32 and ord(c) != 127) or 'dokument'
        with managed_connection(self.db_path) as connection:
            self._prepare(connection, cutoff)
            connection.execute('INSERT OR IGNORE INTO archive_failure_notices (event_key,job_id,document_id,workspace_id,recipient_telegram_id,failure_kind,safe_error_code,safe_display_name,local_file_path,upload_attempts,max_attempts,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                               (key,job_id,document_id,workspace_id,recipient,kind,code,name,local_file_path,
                                attempts,max_attempts,'pending',timestamp,timestamp))
            connection.commit()
        return True

    def reconcile(self, *, now=None) -> None:
        cutoff = configured_cutoff()
        if cutoff is None:
            return
        with managed_connection(self.db_path) as connection:
            self._prepare(connection, cutoff)
            connection.commit()
            connection.row_factory = sqlite3.Row
            # authoritative jobs, never Gmail's enqueue-era archive_status summary.
            rows = connection.execute("SELECT * FROM archive_jobs WHERE provider='google_drive' AND status='failed' AND updated_at>=?", (cutoff,)).fetchall()
        for row in rows:
            self.enqueue(workspace_id=row['workspace_id'], recipient=row['telegram_id'],
                         document_id=row['document_id'], error_code=row['error_code'] or 'archive_failed',
                         local_file_path=row['local_file_path'], job_id=row['job_id'],
                         attempts=row['attempts'], max_attempts=row['max_attempts'], now=now)

        with managed_connection(self.db_path) as connection:
            has_imports = connection.execute("SELECT 1 FROM sqlite_master WHERE name='gmail_statement_imports'").fetchone()
            connection.row_factory = sqlite3.Row
            imports = connection.execute(
                "SELECT import_id,workspace_id,local_original_path,last_error_code FROM gmail_statement_imports "
                "WHERE collection_status='stored' AND archive_status IN ('period_review_required','archive_failed') AND updated_at>=?",
                (cutoff,)).fetchall() if has_imports else []
        for imported in imports:
            try:
                owner = WorkspaceContextService(self.db_path).resolve_for_background_workspace(imported['workspace_id'])
            except WorkspaceContextError:
                continue
            code = imported['last_error_code'] or 'archive_enqueue_failed'
            if code.startswith('gmail_statement_period_'):
                code = code[len('gmail_statement_period_'):]
            self.enqueue(workspace_id=owner.workspace_id,recipient=owner.actor_telegram_id,
                         document_id=imported['import_id'],error_code=code,
                         local_file_path=imported['local_original_path'] or '',now=now)

    def claim(self, *, now=None):
        cutoff = configured_cutoff()
        if cutoff is None:
            return None
        current = utc(now)
        token = uuid4().hex
        with managed_connection(self.db_path) as connection:
            self._prepare(connection, cutoff)
            connection.commit()
            connection.row_factory = sqlite3.Row
            connection.execute('BEGIN IMMEDIATE')
            row = connection.execute("SELECT * FROM archive_failure_notices WHERE status='pending' OR (status='retry_wait' AND next_attempt_at<=?) OR (status='sending' AND lease_until<=?) ORDER BY created_at LIMIT 1", (current.isoformat(),current.isoformat())).fetchone()
            if row is None:
                return None
            connection.execute("UPDATE archive_failure_notices SET status='sending',locked_by=?,lease_until=?,updated_at=? WHERE event_key=?", (token,(current+timedelta(minutes=5)).isoformat(),current.isoformat(),row['event_key']))
            connection.commit()
            result = dict(row)
            result['locked_by'] = token
            return result

    def complete(self, notice, *, status: str, message_id=None, retry_seconds=300, now=None):
        if status not in {'sent','retry_wait','delivery_blocked'}:
            raise ValueError('archive_notice_status_invalid')
        current = utc(now)
        with managed_connection(self.db_path) as connection:
            connection.execute('UPDATE archive_failure_notices SET status=?,delivery_attempts=delivery_attempts+1,next_attempt_at=?,sent_at=?,telegram_message_id=?,locked_by=NULL,lease_until=NULL,updated_at=? WHERE event_key=? AND status=\'sending\' AND locked_by=?',
                               (status,(current+timedelta(seconds=max(1,retry_seconds))).isoformat() if status=='retry_wait' else None,
                                current.isoformat() if status=='sent' else None,str(message_id) if message_id is not None else None,
                                current.isoformat(),notice['event_key'],notice['locked_by']))
            connection.commit()


def notice_text(notice, *, source_present: bool) -> str:
    name = html.escape(notice['safe_display_name'], quote=False)
    if notice['safe_error_code'] in {'archive_upload_unconfirmed','upload_transient_failed','upload_unexpected_failed'}:
        line = f'Uloženie dokumentu „{name}“ na Google Drive sa nepodarilo potvrdiť.'
    else:
        line = f'Dokument „{name}“ sa nepodarilo uložiť na Google Drive.'
    if notice['upload_attempts'] >= notice['max_attempts'] > 0:
        line += f" Počet neúspešných pokusov: {notice['upload_attempts']}."
    line += '\nLokálny originál zostal zachovaný.' if source_present else '\nLokálny originál nie je dostupný; je potrebná kontrola správcom.'
    return line + '\nObráťte sa na správcu. Dôvod: ' + notice['safe_error_code'] + '. Referencia: ' + notice['event_key'][:12] + '.'


async def deliver_failure_notices(*, bot, db_path: Path, storage_dir: Path, limit=20, now=None):
    store = ArchiveFailureNoticeStore(db_path)
    store.reconcile(now=now)
    for _ in range(limit):
        notice = store.claim(now=now)
        if notice is None:
            break
        try:
            context = WorkspaceContextService(db_path).require_membership(notice['recipient_telegram_id'],notice['workspace_id'])
            source = Path(notice['local_file_path'])
            root = storage_dir.resolve() / 'workspaces' / context.storage_key
            # Outgoing invoice failures also use this common outbox, with their own storage owner.
            if notice['job_id']:
                with managed_connection(db_path) as connection:
                    row = connection.execute('SELECT document_type,local_file_path,workspace_id,telegram_id FROM archive_jobs WHERE job_id=?',(notice['job_id'],)).fetchone()
                if not row or row[1:] != (notice['local_file_path'],notice['workspace_id'],notice['recipient_telegram_id']):
                    raise WorkspaceContextError('archive_notice_authority_invalid')
                if row[0] == 'invoice_pdf':
                    from bot.services.workspace_invoice_service import WorkspaceInvoiceService
                    from bot.services.workspace_invoice_pdf_storage import WorkspaceInvoicePdfStorageService
                    try:
                        invoice_id = int(notice['document_id'])
                    except ValueError:
                        raise WorkspaceContextError('archive_notice_authority_invalid') from None
                    invoice = WorkspaceInvoiceService(db_path).get_by_id(context, invoice_id=invoice_id)
                    if invoice is None or invoice.pdf_path != notice['local_file_path']:
                        raise WorkspaceContextError('archive_notice_authority_invalid')
                    owner = WorkspaceInvoicePdfStorageService(db_path, storage_dir)
                    root = storage_dir.resolve() / 'invoices' / context.storage_key
                    legacy = storage_dir.resolve() / 'invoices' / str(invoice.supplier_telegram_id)
                    if source.parent == legacy and owner._legacy_actor_path_is_unambiguous(context, invoice):
                        root = legacy
                    if source.name != invoice.invoice_number + '.pdf':
                        raise WorkspaceContextError('archive_notice_authority_invalid')
            if not notice['job_id']:
                # A missing Gmail source pointer is recoverable only through its
                # persisted, scoped import; membership alone is not document authority.
                with managed_connection(db_path) as connection:
                    has_imports = connection.execute("SELECT 1 FROM sqlite_master WHERE name='gmail_statement_imports'").fetchone()
                    imported = connection.execute(
                        "SELECT local_original_path FROM gmail_statement_imports WHERE import_id=? AND workspace_id=? AND collection_status='stored'",
                        (notice['document_id'],notice['workspace_id'])).fetchone() if has_imports else None
                if imported is not None:
                    owner = WorkspaceContextService(db_path).resolve_for_background_workspace(notice['workspace_id'])
                    if owner.actor_telegram_id != notice['recipient_telegram_id']:
                        raise WorkspaceContextError('archive_notice_authority_invalid')
                    if notice['local_file_path'] and imported[0] != notice['local_file_path']:
                        raise WorkspaceContextError('archive_notice_authority_invalid')
                    if not notice['local_file_path'] and imported[0]:
                        source = Path(imported[0])
                elif not notice['local_file_path']:
                    raise WorkspaceContextError('archive_notice_authority_invalid')
            if notice['local_file_path'] or source.is_absolute():
                _contained(source,root)
                source_present = source.is_file() and os.access(source,os.R_OK)
            else:
                source_present = False
        except (WorkspaceContextError, ArchiveDeliveryError):
            store.complete(notice,status='delivery_blocked',now=now)
            logger.warning('archive_notice_blocked ref=%s',notice['event_key'][:12])
            continue
        except Exception:
            store.complete(notice,status='retry_wait',now=now)
            logger.warning('archive_notice_authority_check_unavailable ref=%s',notice['event_key'][:12])
            continue
        try:
            # No reply_markup and no FSM reference: never alter another active flow.
            sent = await bot.send_message(notice['recipient_telegram_id'],notice_text(notice,source_present=source_present))
        except Exception as exc:
            blocked = type(exc).__name__ in {'TelegramForbiddenError','TelegramBadRequest'}
            retry = getattr(exc,'retry_after',300)
            store.complete(notice,status='delivery_blocked' if blocked else 'retry_wait',
                           retry_seconds=retry if isinstance(retry,(int,float)) else 300,now=now)
            logger.warning('archive_notice_delivery_failed ref=%s',notice['event_key'][:12])
        else:
            store.complete(notice,status='sent',message_id=getattr(sent,'message_id',None),now=now)
