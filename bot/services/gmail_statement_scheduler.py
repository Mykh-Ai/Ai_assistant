from __future__ import annotations

import asyncio
import logging
import html
from datetime import UTC, datetime, timedelta

from aiogram import Bot

from bot.config import Config
from bot.services.db import managed_connection
from bot.services.google_integration_service import (
    GoogleIntegrationError,
    ensure_google_integration_schema,
)
from bot.services.accounting_document_archive_service import (
    AccountingDocumentArchiveService,
)
from bot.services.gmail_readonly_adapter import GmailReadonlyAdapter, GmailReadonlyNeedsReauth
from bot.services.gmail_statement_collector import (
    GmailStatementCollector,
    GmailStatementPolicy,
    GmailStatementStore,
)
from bot.services.google_api_gmail_transport import GoogleAPIGmailReadonlyTransport
from bot.services.gmail_statement_archive_path import (
    DOCUMENT_TYPE_BANK_STATEMENT_ORIGINAL,
)
from bot.services.gmail_statement_period import STATEMENT_PERIOD_DETECTED
from bot.services.google_gmail_config import (
    load_google_gmail_config,
    load_statement_pdf_open_password,
)
from bot.services.google_gmail_runtime import GoogleGmailRuntimeService
from bot.services.token_crypto import FernetTokenCryptoProvider
from bot.services.workspace_context import WorkspaceContextService


logger = logging.getLogger(__name__)


async def run_gmail_statement_scheduler(*, bot: Bot, config: Config) -> None:
    gmail = load_google_gmail_config()
    if not gmail.enabled:
        return
    while True:
        try:
            tick = await asyncio.to_thread(_run_tick, config)
            if tick is not None:
                outcome, result, workspace = tick
                if outcome == "needs_reauth":
                    if await asyncio.to_thread(
                        _reauth_notification_due,
                        config.db_path,
                        workspace.workspace_id,
                        gmail.notification_cooldown_seconds,
                    ):
                        try:
                            await bot.send_message(
                                workspace.actor_telegram_id,
                                "Pripojenie Gmail vyžaduje nové overenie. "
                                "Správca môže použiť /gmail_connect. "
                                "Uložené výpisy zostali zachované.",
                            )
                        except Exception:
                            logger.exception(
                                "gmail_reauth_notification_failed workspace_id=%s",
                                workspace.workspace_id,
                            )
                        else:
                            await asyncio.to_thread(
                                _mark_reauth_notified,
                                config.db_path,
                                workspace.workspace_id,
                            )
                else:
                    store = GmailStatementStore(config.db_path, config.storage_dir)
                    for imported in result.new_imports:
                        try:
                            await bot.send_message(
                                workspace.actor_telegram_id,
                                _notification_text(imported),
                            )
                        except Exception:
                            logger.exception(
                                "gmail_statement_notification_failed import_id=%s",
                                imported.import_id,
                            )
                        else:
                            store.mark_notified(imported.import_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "gmail_statement_scheduler_tick_failed error_code=gmail_tick_failed"
            )
        await asyncio.sleep(gmail.check_interval_seconds)


def _run_tick(config: Config):
    gmail = load_google_gmail_config()
    pdf_open_password = load_statement_pdf_open_password(gmail)
    workspace_id = gmail.target_workspace_id or ""
    workspace_service = WorkspaceContextService(config.db_path)
    workspace = workspace_service.resolve_for_background_workspace(workspace_id)
    crypto = FernetTokenCryptoProvider(
        secret=gmail.token_crypto_secret, key_id="google-integration-fernet-v1"
    )
    runtime = GoogleGmailRuntimeService(config.db_path, crypto)
    try:
        grant = runtime.load_active_grant(workspace.workspace_id)
    except GoogleIntegrationError as exc:
        if str(exc) == "gmail_binding_inactive":
            return None
        raise
    transport = GoogleAPIGmailReadonlyTransport(
        access_token=grant.access_token,
        refresh_token=grant.refresh_token,
        client_id=gmail.client_id or "",
        client_secret=gmail.client_secret or "",
        scopes=grant.scopes,
    )
    tick_started = datetime.now(UTC)
    trusted_query = _bounded_query(
        gmail.statement_query or "",
        last_successful=runtime.last_successful_check(workspace.workspace_id),
        initial_lookback_days=gmail.initial_lookback_days,
        overlap_hours=gmail.overlap_hours,
        now=tick_started,
    )
    adapter = GmailReadonlyAdapter(
        transport,
        trusted_query=trusted_query,
        batch_size=gmail.batch_size,
    )
    collector = GmailStatementCollector(
        adapter=adapter,
        store=GmailStatementStore(config.db_path, config.storage_dir),
        resolve_workspace=workspace_service.resolve_for_background_workspace,
        workspace_id=workspace.workspace_id,
        connection_id=grant.connection_id,
        policy=GmailStatementPolicy(
            maximum_bytes=gmail.max_attachment_bytes,
            allowed_mime_types=gmail.allowed_mime_types,
            allowed_extensions=gmail.allowed_extensions,
        ),
        pdf_open_password=pdf_open_password,
    )
    try:
        result = collector.run_once()
    except GmailReadonlyNeedsReauth:
        runtime.mark_needs_reauth(workspace.workspace_id)
        logger.warning(
            "gmail_statement_scheduler_needs_reauth workspace_id=%s",
            workspace.workspace_id,
        )
        return "needs_reauth", None, workspace
    if config.google_drive_enabled:
        store = GmailStatementStore(config.db_path, config.storage_dir)
        archive = AccountingDocumentArchiveService(config.db_path)
        for imported in result.new_imports:
            if (
                imported.statement_period_status != STATEMENT_PERIOD_DETECTED
                or imported.statement_period_year is None
                or imported.statement_period_month is None
            ):
                store.mark_archive_withheld(
                    imported.import_id,
                    "gmail_statement_period_"
                    + imported.statement_period_status[:96],
                )
                logger.warning(
                    "gmail_statement_archive_withheld import_id=%s period_status=%s",
                    imported.import_id,
                    imported.statement_period_status,
                )
                continue
            if not imported.local_original_path or not imported.local_metadata_path:
                store.mark_archive_failed(imported.import_id, "gmail_archive_path_missing")
                continue
            try:
                enqueued = archive.enqueue_confirmed_document(
                    workspace_id=workspace.workspace_id,
                    telegram_id=workspace.actor_telegram_id,
                    document_id=imported.import_id,
                    document_type=DOCUMENT_TYPE_BANK_STATEMENT_ORIGINAL,
                    local_file_path=imported.local_original_path,
                    metadata_path=imported.local_metadata_path,
                    workspace_storage_key=workspace.storage_key,
                    workspace_drive_folder_name=workspace.drive_folder_name,
                    statement_period_year=imported.statement_period_year,
                    statement_period_month=imported.statement_period_month,
                )
            except Exception:
                store.mark_archive_failed(imported.import_id, "gmail_archive_enqueue_failed")
                logger.warning(
                    "gmail_statement_archive_enqueue_failed import_id=%s",
                    imported.import_id,
                )
            else:
                store.mark_archive_enqueued(imported.import_id, enqueued.job.job_id)
    runtime.mark_check_succeeded(workspace.workspace_id, tick_started.isoformat())
    logger.info(
        "gmail_statement_scheduler_tick_complete messages=%s stored=%s "
        "duplicate_source=%s duplicate_content=%s rejected=%s failed=%s",
        result.messages_seen,
        result.stored,
        result.duplicate_source,
        result.duplicate_content,
        result.rejected,
        result.failed,
    )
    return "complete", result, workspace


def _notification_text(imported) -> str:
    filename = html.escape(
        imported.safe_display_filename or "bankový výpis", quote=False
    )
    size = imported.size_bytes or 0
    if imported.statement_period_status == STATEMENT_PERIOD_DETECTED:
        period_line = (
            "Obdobie archívu: "
            f"{imported.statement_period_year:04d}-"
            f"{imported.statement_period_month:02d}.\n"
        )
    else:
        period_line = (
            "Obdobie sa nepodarilo bezpečne určiť; archivácia na Drive "
            "bola pozastavená na kontrolu.\n"
        )
    return (
        "Nový bankový výpis bol bezpečne uložený.\n"
        f"Súbor: {filename}\n"
        f"Veľkosť: {size} B\n"
        f"{period_line}"
        "Spracovanie obsahu: odložené; výpis ešte nebol parsovaný ani spárovaný."
    )


def _bounded_query(
    base_query: str,
    *,
    last_successful: str | None,
    initial_lookback_days: int,
    overlap_hours: int,
    now: datetime,
) -> str:
    start = now - timedelta(days=initial_lookback_days)
    if last_successful:
        try:
            parsed = datetime.fromisoformat(last_successful)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            start = parsed.astimezone(UTC) - timedelta(hours=overlap_hours)
        except ValueError:
            start = now - timedelta(days=initial_lookback_days)
    epoch_seconds = int(start.timestamp())
    return f"({base_query.strip()}) after:{epoch_seconds}"

def _reauth_notification_due(
    db_path,
    workspace_id: str,
    cooldown_seconds: int,
    *,
    now: datetime | None = None,
) -> bool:
    current = now or datetime.now(UTC)
    with managed_connection(db_path) as connection:
        ensure_google_integration_schema(connection)
        row = connection.execute(
            "SELECT last_notified_at FROM google_integration_notification_state "
            "WHERE workspace_id=? AND service='gmail' "
            "AND notification_type='needs_reauth'",
            (workspace_id,),
        ).fetchone()
    if row is None:
        return True
    try:
        last = datetime.fromisoformat(str(row[0]))
        if last.tzinfo is None:
            last = last.replace(tzinfo=UTC)
    except ValueError:
        return True
    return (current - last.astimezone(UTC)).total_seconds() >= cooldown_seconds


def _mark_reauth_notified(
    db_path, workspace_id: str, *, now: datetime | None = None
) -> None:
    timestamp = (now or datetime.now(UTC)).isoformat()
    with managed_connection(db_path) as connection:
        ensure_google_integration_schema(connection)
        connection.execute(
            "INSERT INTO google_integration_notification_state "
            "(workspace_id, service, notification_type, last_notified_at) "
            "VALUES (?, 'gmail', 'needs_reauth', ?) "
            "ON CONFLICT(workspace_id, service, notification_type) DO UPDATE SET "
            "last_notified_at=excluded.last_notified_at",
            (workspace_id, timestamp),
        )
        connection.commit()
