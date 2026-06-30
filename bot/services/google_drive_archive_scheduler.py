from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from bot.config import Config
from bot.services.archive_worker import (
    ARCHIVE_WORKER_NOOP,
    ArchiveLocalRetentionPolicy,
    ArchiveUploadProvider,
    ArchiveWorker,
    ArchiveWorkerResult,
)
from bot.services.google_drive_service_account_client import (
    GoogleDriveServiceAccountArchiveProvider,
    GoogleDriveServiceAccountClientConfig,
)


logger = logging.getLogger(__name__)


class _UnsetProvider:
    pass


_UNSET = _UnsetProvider()


@dataclass(frozen=True)
class GoogleDriveArchiveRunResult:
    processed_jobs: int
    last_status: str
    last_error_code: str | None = None


def build_google_drive_archive_provider(config: Config) -> ArchiveUploadProvider | None:
    if not config.google_drive_enabled:
        return None
    if config.google_drive_mode != "service_account":
        return None
    return GoogleDriveServiceAccountArchiveProvider(
        GoogleDriveServiceAccountClientConfig(
            service_account_json_path=config.google_drive_service_account_json_path,
            root_folder_id=config.google_drive_root_folder_id,
            root_folder_name=config.google_drive_root_folder_name,
        )
    )


def retention_policy_from_config(config: Config) -> ArchiveLocalRetentionPolicy:
    return ArchiveLocalRetentionPolicy(
        delete_receipt_original_after_upload=(
            config.google_drive_delete_local_receipt_original_after_upload
        ),
        delete_incoming_invoice_original_after_upload=(
            config.google_drive_delete_local_incoming_invoice_original_after_upload
        ),
    )


def process_google_drive_archive_once(
    *,
    config: Config,
    provider: ArchiveUploadProvider | None | object = _UNSET,
    now: datetime | None = None,
) -> ArchiveWorkerResult:
    if not config.google_drive_enabled:
        return ArchiveWorkerResult(status=ARCHIVE_WORKER_NOOP)
    resolved_provider = build_google_drive_archive_provider(config) if provider is _UNSET else provider
    if resolved_provider is None:
        return ArchiveWorkerResult(status=ARCHIVE_WORKER_NOOP)
    return ArchiveWorker(
        config.db_path,
        resolved_provider,
        retention_policy=retention_policy_from_config(config),
    ).process_one(now=now)


async def run_google_drive_archive_scheduler(*, config: Config) -> None:
    if not config.google_drive_enabled:
        logger.info("Google Drive archive scheduler disabled by configuration")
        return

    interval = config.google_drive_archive_worker_interval_seconds
    batch_size = config.google_drive_archive_worker_batch_size
    logger.info(
        "Google Drive archive scheduler started mode=%s interval_seconds=%s batch_size=%s",
        config.google_drive_mode,
        interval,
        batch_size,
    )
    while True:
        try:
            result = run_google_drive_archive_batch(config=config, batch_size=batch_size)
            if result.processed_jobs or result.last_error_code:
                logger.info(
                    "Google Drive archive scheduler tick processed_jobs=%s last_status=%s last_error_code=%s",
                    result.processed_jobs,
                    result.last_status,
                    result.last_error_code,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Google Drive archive scheduler tick failed")

        await asyncio.sleep(interval)


def run_google_drive_archive_batch(*, config: Config, batch_size: int) -> GoogleDriveArchiveRunResult:
    processed = 0
    last_status = ARCHIVE_WORKER_NOOP
    last_error_code = None
    provider = build_google_drive_archive_provider(config)
    for _ in range(max(0, batch_size)):
        result = process_google_drive_archive_once(config=config, provider=provider)
        last_status = result.status
        last_error_code = result.error_code
        if result.status == ARCHIVE_WORKER_NOOP:
            break
        processed += 1
    return GoogleDriveArchiveRunResult(
        processed_jobs=processed,
        last_status=last_status,
        last_error_code=last_error_code,
    )
