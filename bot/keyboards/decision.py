from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


DECISION_CALLBACK_PREFIX = 'decision:'
DECISION_YES = 'yes'
DECISION_NO = 'no'
DECISION_APPROVE = 'approve'
DECISION_EDIT = 'edit'
DECISION_CANCEL = 'cancel'
DECISION_CLOSE_DAY = 'close_day'
DECISION_FILL_TIME = 'fill_time'
DECISION_SKIP_DAY = 'skip_day'
DECISION_FILL = 'fill'
DECISION_SKIP = 'skip'


def decision_callback_data(token: str) -> str:
    return f'{DECISION_CALLBACK_PREFIX}{token}'


def work_time_open_conflict_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='Uzavriet den', callback_data=decision_callback_data(DECISION_CLOSE_DAY)),
                InlineKeyboardButton(text='Doplnit cas', callback_data=decision_callback_data(DECISION_FILL_TIME)),
            ],
            [
                InlineKeyboardButton(text='Preskocit', callback_data=decision_callback_data(DECISION_SKIP_DAY)),
                InlineKeyboardButton(text='Zrusit', callback_data=decision_callback_data(DECISION_CANCEL)),
            ],
        ]
    )


def work_time_missing_days_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='Doplnit', callback_data=decision_callback_data(DECISION_FILL)),
                InlineKeyboardButton(text='Preskocit', callback_data=decision_callback_data(DECISION_SKIP)),
                InlineKeyboardButton(text='Zrusit', callback_data=decision_callback_data(DECISION_CANCEL)),
            ]
        ]
    )


def approve_edit_cancel_keyboard(
    *,
    approve_label: str = 'Schváliť',
    edit_label: str = 'Upraviť',
    cancel_label: str = 'Zrušiť',
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=approve_label, callback_data=decision_callback_data(DECISION_APPROVE)),
                InlineKeyboardButton(text=edit_label, callback_data=decision_callback_data(DECISION_EDIT)),
                InlineKeyboardButton(text=cancel_label, callback_data=decision_callback_data(DECISION_CANCEL)),
            ]
        ]
    )


def yes_no_keyboard(*, yes_label: str = 'Áno', no_label: str = 'Nie') -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=yes_label, callback_data=decision_callback_data(DECISION_YES)),
                InlineKeyboardButton(text=no_label, callback_data=decision_callback_data(DECISION_NO)),
            ]
        ]
    )


def save_cancel_keyboard(*, save_label: str = 'Uložiť', cancel_label: str = 'Zrušiť') -> InlineKeyboardMarkup:
    return yes_no_keyboard(yes_label=save_label, no_label=cancel_label)


def delete_cancel_keyboard(*, delete_label: str = 'Vymazať', cancel_label: str = 'Zrušiť') -> InlineKeyboardMarkup:
    return yes_no_keyboard(yes_label=delete_label, no_label=cancel_label)


async def answer_with_decision_keyboard(message, text: str, reply_markup: InlineKeyboardMarkup) -> None:
    try:
        await message.answer(text, reply_markup=reply_markup)
    except TypeError as exc:
        if 'reply_markup' not in str(exc) and 'unexpected keyword' not in str(exc):
            raise
        await message.answer(text)
