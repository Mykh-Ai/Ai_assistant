from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup

from bot.config import Config
from bot.services.google_drive_archive_stub import GoogleDriveArchiveStubService
from bot.services.invoice_followup_service import (
    InvoiceFollowupService,
    OverdueInvoiceReminder,
)


router = Router(name='invoice_followup')

INVOICE_FOLLOWUP_CALLBACK_PREFIX = 'invoice_followup:'
INVOICE_FOLLOWUP_DECISION_MARK_PAID = 'mark_paid'
INVOICE_FOLLOWUP_DECISION_REMIND_LATER = 'remind_later'
INVOICE_FOLLOWUP_DECISION_MUTE = 'mute'

_STALE_OR_FORBIDDEN_CALLBACK = 'Tato pripomienka uz nie je dostupna pre vas ucet.'


@router.callback_query(F.data.startswith(INVOICE_FOLLOWUP_CALLBACK_PREFIX))
async def invoice_followup_callback(callback: CallbackQuery, config: Config) -> None:
    parsed = _parse_followup_callback(callback.data)
    supplier_telegram_id = getattr(getattr(callback, 'from_user', None), 'id', None)
    if parsed is None or supplier_telegram_id is None:
        await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)
        return

    decision, invoice_id = parsed
    service = InvoiceFollowupService(config.db_path)
    try:
        if decision == INVOICE_FOLLOWUP_DECISION_MARK_PAID:
            state = service.mark_paid(
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
            stub = GoogleDriveArchiveStubService(config.db_path).request_invoice_archive_stub(
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
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
            await _answer_callback_message(callback, 'Dobre, pripomeniem neskor.' + suffix)
            await callback.answer()
            return

        if decision == INVOICE_FOLLOWUP_DECISION_MUTE:
            service.mute(
                invoice_id=invoice_id,
                supplier_telegram_id=supplier_telegram_id,
            )
            await _answer_callback_message(callback, 'Dobre, tuto fakturu uz nebudem pripominat.')
            await callback.answer()
            return
    except ValueError:
        await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)
        return

    await callback.answer(_STALE_OR_FORBIDDEN_CALLBACK, show_alert=True)


def format_overdue_invoice_notification(reminder: OverdueInvoiceReminder) -> str:
    return (
        f'Fakture {reminder.invoice_number} uplynula splatnost.\n\n'
        f'Odberatel: {reminder.customer_name}\n'
        f'Suma: {_format_amount(reminder.total_amount)} {reminder.currency}\n'
        f'Splatnost: {reminder.due_date}\n\n'
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


def _callback_data(decision: str, invoice_id: int) -> str:
    return f'{INVOICE_FOLLOWUP_CALLBACK_PREFIX}{decision}:{invoice_id}'


def _parse_followup_callback(data: str | None) -> tuple[str, int] | None:
    if not data or not data.startswith(INVOICE_FOLLOWUP_CALLBACK_PREFIX):
        return None
    payload = data[len(INVOICE_FOLLOWUP_CALLBACK_PREFIX) :]
    decision, separator, invoice_id_text = payload.partition(':')
    if not separator or decision not in {
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
    return decision, invoice_id


def _format_amount(value: float) -> str:
    return f'{value:.2f}'.replace('.', ',')


async def _answer_callback_message(callback: CallbackQuery, text: str) -> None:
    source_message = callback.message
    if source_message is not None and hasattr(source_message, 'answer'):
        await source_message.answer(text)
        return
    await callback.answer(text, show_alert=True)
