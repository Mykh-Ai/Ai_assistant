from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from typing import Any

from bot.config import Config
from bot.handlers.invoice_followup import (
    format_overdue_invoice_notification,
    invoice_followup_keyboard,
)
from bot.services.authorization import is_authorized_telegram_user
from bot.services.invoice_followup_service import InvoiceFollowupService
from bot.services.workspace_context import (
    WorkspaceContextError,
    WorkspaceContextService,
)
from bot.services.workspace_invoice_followup_service import (
    WorkspaceInvoiceFollowupSchemaRequired,
    WorkspaceInvoiceFollowupService,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InvoiceFollowupRunResult:
    eligible_suppliers: int
    notified_suppliers: int
    reminders_sent: int
    skipped_unauthorized_suppliers: int
    failed_sends: int


async def send_due_invoice_followups_once(
    *,
    bot: Any,
    config: Config,
    now: datetime | None = None,
) -> InvoiceFollowupRunResult:
    run_now = (now or datetime.now()).replace(microsecond=0)
    legacy_service = InvoiceFollowupService(config.db_path)
    workspace_service = WorkspaceInvoiceFollowupService(config.db_path)
    context_service = WorkspaceContextService(config.db_path)
    supplier_ids = legacy_service.list_supplier_telegram_ids_with_due_invoices(
        today=run_now.date(),
        now=run_now,
    )
    try:
        workspace_ids = workspace_service.list_workspace_ids_with_due_invoices(
            today=run_now.date(),
            now=run_now,
        )
    except WorkspaceInvoiceFollowupSchemaRequired:
        workspace_ids = []

    eligible_actor_ids = set(supplier_ids)
    notified_suppliers: set[int] = set()
    reminders_sent = 0
    skipped_unauthorized = 0
    failed_sends = 0
    next_reminder_after = run_now + timedelta(
        hours=config.invoice_followup_notification_cooldown_hours
    )

    for supplier_id in supplier_ids:
        if not is_authorized_telegram_user(config, supplier_id):
            skipped_unauthorized += 1
            continue
        reminders = legacy_service.list_due_invoices_for_supplier(
            supplier_telegram_id=supplier_id,
            today=run_now.date(),
            now=run_now,
        )
        for reminder in reminders:
            try:
                await bot.send_message(
                    reminder.supplier_telegram_id,
                    format_overdue_invoice_notification(reminder),
                    reply_markup=invoice_followup_keyboard(reminder.invoice_id),
                )
            except Exception:
                failed_sends += 1
                logger.exception(
                    'Failed to send invoice follow-up reminder '
                    'invoice_id=%s supplier_telegram_id=%s',
                    reminder.invoice_id,
                    reminder.supplier_telegram_id,
                )
                continue
            legacy_service.record_reminder_sent(
                invoice_id=reminder.invoice_id,
                supplier_telegram_id=reminder.supplier_telegram_id,
                now=run_now,
                next_reminder_after=next_reminder_after,
            )
            notified_suppliers.add(reminder.supplier_telegram_id)
            reminders_sent += 1

    for workspace_id in workspace_ids:
        try:
            context = context_service.resolve_for_background_workspace(workspace_id)
        except WorkspaceContextError:
            skipped_unauthorized += 1
            logger.warning(
                'Skipping invoice follow-up workspace without active owner membership '
                'workspace_id=%s',
                workspace_id,
            )
            continue
        eligible_actor_ids.add(context.actor_telegram_id)
        reminders = workspace_service.list_due_invoices(
            context,
            today=run_now.date(),
            now=run_now,
        )
        for reminder in reminders:
            try:
                await bot.send_message(
                    context.actor_telegram_id,
                    format_overdue_invoice_notification(
                        reminder,
                        workspace_name=context.workspace_display_name,
                    ),
                    reply_markup=invoice_followup_keyboard(reminder.invoice_id),
                )
            except Exception:
                failed_sends += 1
                logger.exception(
                    'Failed to send workspace invoice follow-up reminder '
                    'invoice_id=%s workspace_id=%s',
                    reminder.invoice_id,
                    workspace_id,
                )
                continue
            workspace_service.record_reminder_sent(
                context,
                invoice_id=reminder.invoice_id,
                now=run_now,
                next_reminder_after=next_reminder_after,
            )
            notified_suppliers.add(context.actor_telegram_id)
            reminders_sent += 1

    return InvoiceFollowupRunResult(
        eligible_suppliers=len(eligible_actor_ids),
        notified_suppliers=len(notified_suppliers),
        reminders_sent=reminders_sent,
        skipped_unauthorized_suppliers=skipped_unauthorized,
        failed_sends=failed_sends,
    )

async def run_invoice_followup_scheduler(*, bot: Any, config: Config) -> None:
    if not config.invoice_followup_scheduler_enabled:
        logger.info('Invoice follow-up scheduler disabled by configuration')
        return

    interval = config.invoice_followup_check_interval_seconds
    logger.info('Invoice follow-up scheduler started interval_seconds=%s', interval)
    while True:
        try:
            result = await send_due_invoice_followups_once(bot=bot, config=config)
            if result.reminders_sent or result.failed_sends or result.skipped_unauthorized_suppliers:
                logger.info(
                    'Invoice follow-up scheduler tick eligible_suppliers=%s notified_suppliers=%s '
                    'reminders_sent=%s skipped_unauthorized_suppliers=%s failed_sends=%s',
                    result.eligible_suppliers,
                    result.notified_suppliers,
                    result.reminders_sent,
                    result.skipped_unauthorized_suppliers,
                    result.failed_sends,
                )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception('Invoice follow-up scheduler tick failed')

        await asyncio.sleep(interval)
