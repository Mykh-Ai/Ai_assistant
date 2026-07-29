from __future__ import annotations

from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.services.invoice_drive_archive_service import InvoiceDriveArchiveService
from bot.services.invoice_followup_service import (
    InvoiceFollowupService,
    OverdueInvoiceReminder,
)
from bot.services.invoice_service import InvoiceService
from bot.services.db import managed_connection
from bot.services.workspace_context import (
    WorkspaceContextError,
    WorkspaceContextService,
)
from bot.services.workspace_invoice_followup_service import (
    WorkspaceInvoiceFollowupService,
    WorkspaceOverdueInvoiceReminder,
)
from bot.services.workspace_invoice_service import WorkspaceInvoiceService


router = Router(name='invoice_followup')
logger = logging.getLogger(__name__)

INVOICE_FOLLOWUP_CALLBACK_PREFIX = 'invoice_followup:'
INVOICE_FOLLOWUP_DECISION_MARK_PAID = 'mark_paid'
INVOICE_FOLLOWUP_DECISION_REMIND_LATER = 'remind_later'
INVOICE_FOLLOWUP_DECISION_MUTE = 'mute'

_STALE_OR_FORBIDDEN_CALLBACK = 'Tato pripomienka uz nie je dostupna pre vas ucet.'
_INVOICE_FOLLOWUP_CALLBACK_TTL_SECONDS = 24 * 60 * 60
_CALLBACK_CLOCK_SKEW_SECONDS = 60


@router.callback_query(F.data.startswith(INVOICE_FOLLOWUP_CALLBACK_PREFIX))
async def invoice_followup_callback(callback: CallbackQuery, config: Config) -> None:
    parsed = _parse_followup_callback(callback.data)
    supplier_telegram_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if parsed is None or supplier_telegram_id is None:
        await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)
        return

    decision, invoice_id, issued_at = parsed
    if _is_followup_callback_expired(issued_at):
        await _clear_callback_keyboard(callback)
        await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)
        return
    workspace_id = _invoice_workspace_id(config.db_path, invoice_id)
    if workspace_id is not None:
        await _handle_workspace_followup_callback(
            callback=callback,
            config=config,
            supplier_telegram_id=supplier_telegram_id,
            workspace_id=workspace_id,
            decision=decision,
            invoice_id=invoice_id,
        )
        return
    service = InvoiceFollowupService(config.db_path)
    try:
        if decision == INVOICE_FOLLOWUP_DECISION_MARK_PAID:
            state = service.mark_paid(
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
            invoice = InvoiceService(config.db_path).get_invoice_for_supplier_by_id(
                supplier_telegram_id=supplier_telegram_id,
                invoice_id=invoice_id,
            )
            if invoice is None:
                raise ValueError('invoice_not_found_for_supplier')
            stub = InvoiceDriveArchiveService(config).request_after_paid(invoice=invoice)
            await _clear_callback_keyboard(callback)
            await _answer_callback_message(
                callback,
                'Fakturu som oznacil ako zaplatenu.\n\n' + stub.user_message,
            )
            await callback.answer()
            return

        if decision == INVOICE_FOLLOWUP_DECISION_REMIND_LATER:
            state = service.remind_later(
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
            suffix = f'\nDalsia pripomienka najskor: {state.remind_after}.' if state.remind_after else ''
            await _clear_callback_keyboard(callback)
            await _answer_callback_message(callback, 'Dobre, pripomeniem neskor.' + suffix)
            await callback.answer()
            return

        if decision == INVOICE_FOLLOWUP_DECISION_MUTE:
            service.mute(
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
            await _clear_callback_keyboard(callback)
            await _answer_callback_message(callback, 'Dobre, tuto fakturu uz nebudem pripominat.')
            await callback.answer()
            return
    except ValueError:
        await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)
        return

    await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)


async def _handle_workspace_followup_callback(
    *,
    callback: CallbackQuery,
    config: Config,
    supplier_telegram_id: int,
    workspace_id: str,
    decision: str,
    invoice_id: int,
) -> None:
    try:
        context = WorkspaceContextService(config.db_path).require_membership(
            supplier_telegram_id,
            workspace_id,
        )
        service = WorkspaceInvoiceFollowupService(config.db_path)
        if decision == INVOICE_FOLLOWUP_DECISION_MARK_PAID:
            service.mark_paid(context, invoice_id=invoice_id)
            invoice = WorkspaceInvoiceService(config.db_path).get_by_id(context, invoice_id)
            if invoice is None:
                raise ValueError('invoice_not_found_for_workspace')
            stub = InvoiceDriveArchiveService(config).request_after_paid_for_workspace(
                context,
                invoice=invoice,
            )
            await _clear_callback_keyboard(callback)
            await _answer_callback_message(
                callback,
                'Fakturu som oznacil ako zaplatenu.\n\n' + stub.user_message,
            )
            await callback.answer()
            return
        if decision == INVOICE_FOLLOWUP_DECISION_REMIND_LATER:
            state = service.remind_later(context, invoice_id=invoice_id)
            suffix = (
                f'\nDalsia pripomienka najskor: {state.remind_after}.'
                if state.remind_after
                else ''
            )
            await _clear_callback_keyboard(callback)
            await _answer_callback_message(callback, 'Dobre, pripomeniem neskor.' + suffix)
            await callback.answer()
            return
        if decision == INVOICE_FOLLOWUP_DECISION_MUTE:
            service.mute(context, invoice_id=invoice_id)
            await _clear_callback_keyboard(callback)
            await _answer_callback_message(
                callback,
                'Dobre, tuto fakturu uz nebudem pripominat.',
            )
            await callback.answer()
            return
    except (ValueError, WorkspaceContextError):
        await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)
        return
    await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)


def _invoice_workspace_id(db_path: Path, invoice_id: int) -> str | None:
    with managed_connection(db_path) as connection:
        columns = {row[1] for row in connection.execute('PRAGMA table_info(invoice)')}
        if 'workspace_id' not in columns:
            return None
        row = connection.execute(
            'SELECT workspace_id FROM invoice WHERE id = ?',
            (invoice_id,),
        ).fetchone()
    if row is None or row[0] is None:
        return None
    return str(row[0])



def format_overdue_invoice_notification(
    reminder: OverdueInvoiceReminder | WorkspaceOverdueInvoiceReminder,
    *,
    workspace_name: str | None = None,
) -> str:
    newline = chr(10)
    workspace_line = f'Profil: {workspace_name}{newline}' if workspace_name else ''
    return (
        f'Fakture {reminder.invoice_number} uplynula splatnost.{newline}{newline}'
        f'{workspace_line}'
        f'Odberatel: {reminder.customer_name}{newline}'
        f'Suma: {_format_amount(reminder.total_amount)} {reminder.currency}{newline}'
        f'Splatnost: {reminder.due_date}{newline}{newline}'
        'Co chcete urobit?'
    )

def invoice_followup_keyboard(invoice_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Oznacit ako zaplatenu',
                    callback_data=_callback_data(INVOICE_FOLLOWUP_DECISION_MARK_PAID, invoice_id),
                )
            ],
            [
                InlineKeyboardButton(
                    text='Pripomenut neskor',
                    callback_data=_callback_data(INVOICE_FOLLOWUP_DECISION_REMIND_LATER, invoice_id),
                ),
                InlineKeyboardButton(
                    text='Viac nepripominat',
                    callback_data=_callback_data(INVOICE_FOLLOWUP_DECISION_MUTE, invoice_id),
                ),
            ],
        ]
    )


def _callback_data(decision: str, invoice_id: int, *, now: datetime | None = None) -> str:
    issued_at = int(_utc_now(now).timestamp())
    return f'{INVOICE_FOLLOWUP_CALLBACK_PREFIX}{decision}:{invoice_id}:{issued_at}'


def _parse_followup_callback(data: str | None) -> tuple[str, int, datetime | None] | None:
    if not data or not data.startswith(INVOICE_FOLLOWUP_CALLBACK_PREFIX):
        return None
    payload = data[len(INVOICE_FOLLOWUP_CALLBACK_PREFIX) :]
    parts = payload.split(':')
    if len(parts) not in {2, 3}:
        return None
    decision, invoice_id_text = parts[0], parts[1]
    if decision not in {
        INVOICE_FOLLOWUP_DECISION_MARK_PAID,
        INVOICE_FOLLOWUP_DECISION_REMIND_LATER,
        INVOICE_FOLLOWUP_DECISION_MUTE,
    }:
        return None
    try:
        invoice_id = int(invoice_id_text)
    except ValueError:
        return None
    if invoice_id <= 0:
        return None
    if len(parts) == 2:
        return decision, invoice_id, None
    try:
        issued_at = datetime.fromtimestamp(int(parts[2]), tz=UTC)
    except (ValueError, OSError, OverflowError):
        return None
    return decision, invoice_id, issued_at


def _is_followup_callback_expired(issued_at: datetime | None, *, now: datetime | None = None) -> bool:
    if issued_at is None:
        return True
    current = _utc_now(now)
    if issued_at > current + timedelta(seconds=_CALLBACK_CLOCK_SKEW_SECONDS):
        return True
    return current - issued_at >= timedelta(seconds=_INVOICE_FOLLOWUP_CALLBACK_TTL_SECONDS)


def _utc_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(UTC)
    if now.tzinfo is None:
        return now.replace(tzinfo=UTC)
    return now.astimezone(UTC)

def _format_amount(value: float) -> str:
    return f'{value:.2f}'.replace('.', ',')


async def _answer_callback_message(callback: CallbackQuery, text: str) -> None:
    source_message = callback.message
    if source_message is not None and hasattr(source_message, 'answer'):
        await source_message.answer(text)
        return
    await callback.answer(text, show_alert=True)


async def _clear_callback_keyboard(callback: CallbackQuery) -> None:
    source_message = callback.message
    if source_message is None or not hasattr(source_message, 'edit_reply_markup'):
        return
    try:
        await source_message.edit_reply_markup(reply_markup=None)
    except Exception:
        logger.exception('Failed to clear invoice follow-up inline keyboard')
