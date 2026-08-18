from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


INVOICE_EDIT_CALLBACK_PREFIX = 'invoice_edit:'
INVOICE_EDIT_ITEM_TARGET_PREFIX = 'item_target:'
INVOICE_EDIT_BACK = 'back'
INVOICE_EDIT_CANCEL = 'cancel'

_INVOICE_EDIT_ACTION_TOKENS = {
    'invoice_level',
    'item_level',
    'edit_invoice_number',
    'edit_invoice_issue_date',
    'edit_invoice_delivery_date',
    'edit_invoice_due_date',
    'edit_invoice_date',
    'replace_service',
    'replace_main_description',
    'add_item_details',
    'clear_item_details',
    'edit_item_quantity',
    'edit_item_unit_price',
    'edit_item_total_amount',
    INVOICE_EDIT_BACK,
    INVOICE_EDIT_CANCEL,
}


def invoice_edit_callback_data(token: str) -> str:
    return f'{INVOICE_EDIT_CALLBACK_PREFIX}{token}'


def parse_invoice_edit_callback_data(data: str | None) -> str | None:
    if not data or not data.startswith(INVOICE_EDIT_CALLBACK_PREFIX):
        return None
    token = data[len(INVOICE_EDIT_CALLBACK_PREFIX) :]
    if token in _INVOICE_EDIT_ACTION_TOKENS:
        return token
    if token.startswith(INVOICE_EDIT_ITEM_TARGET_PREFIX):
        raw_index = token[len(INVOICE_EDIT_ITEM_TARGET_PREFIX) :]
        if raw_index.isdigit() and 1 <= int(raw_index) <= 99:
            return token
    return None


def invoice_edit_main_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Číslo faktúry',
                    callback_data=invoice_edit_callback_data('edit_invoice_number'),
                ),
                InlineKeyboardButton(
                    text='Položka faktúry',
                    callback_data=invoice_edit_callback_data('item_level'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Dátum vystavenia',
                    callback_data=invoice_edit_callback_data('edit_invoice_issue_date'),
                ),
                InlineKeyboardButton(
                    text='Dátum dodania',
                    callback_data=invoice_edit_callback_data('edit_invoice_delivery_date'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Dátum splatnosti',
                    callback_data=invoice_edit_callback_data('edit_invoice_due_date'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Zrušiť úpravu',
                    callback_data=invoice_edit_callback_data(INVOICE_EDIT_CANCEL),
                ),
            ],
        ]
    )


def invoice_edit_invoice_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Číslo faktúry',
                    callback_data=invoice_edit_callback_data('edit_invoice_number'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Dátum vystavenia',
                    callback_data=invoice_edit_callback_data('edit_invoice_issue_date'),
                ),
                InlineKeyboardButton(
                    text='Dátum dodania',
                    callback_data=invoice_edit_callback_data('edit_invoice_delivery_date'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Dátum splatnosti',
                    callback_data=invoice_edit_callback_data('edit_invoice_due_date'),
                ),
            ],
            _back_cancel_row(),
        ]
    )


def invoice_edit_item_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Zmeniť službu',
                    callback_data=invoice_edit_callback_data('replace_service'),
                ),
                InlineKeyboardButton(
                    text='Nový opis',
                    callback_data=invoice_edit_callback_data('replace_main_description'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Pridať detaily',
                    callback_data=invoice_edit_callback_data('add_item_details'),
                ),
                InlineKeyboardButton(
                    text='Vymazať detaily',
                    callback_data=invoice_edit_callback_data('clear_item_details'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Množstvo',
                    callback_data=invoice_edit_callback_data('edit_item_quantity'),
                ),
                InlineKeyboardButton(
                    text='Cena za m.j.',
                    callback_data=invoice_edit_callback_data('edit_item_unit_price'),
                ),
            ],
            [
                InlineKeyboardButton(
                    text='Suma položky',
                    callback_data=invoice_edit_callback_data('edit_item_total_amount'),
                ),
            ],
            _back_cancel_row(),
        ]
    )


def invoice_edit_item_target_keyboard(item_labels: list[str]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for index, label in enumerate(item_labels, start=1):
        compact_label = ' '.join(label.split()).strip() or f'Položka {index}'
        if len(compact_label) > 36:
            compact_label = f'{compact_label[:33].rstrip()}...'
        rows.append(
            [
                InlineKeyboardButton(
                    text=f'{index}. {compact_label}',
                    callback_data=invoice_edit_callback_data(
                        f'{INVOICE_EDIT_ITEM_TARGET_PREFIX}{index}'
                    ),
                )
            ]
        )
    rows.append(_back_cancel_row())
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _back_cancel_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text='Späť',
            callback_data=invoice_edit_callback_data(INVOICE_EDIT_BACK),
        ),
        InlineKeyboardButton(
            text='Zrušiť',
            callback_data=invoice_edit_callback_data(INVOICE_EDIT_CANCEL),
        ),
    ]
