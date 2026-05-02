from __future__ import annotations

import re
import unicodedata

from aiogram import Router
from aiogram.filters import Command, StateFilter
from aiogram.types import Message

from bot.config import Config
from bot.services.accounting_document_models import DOCUMENT_TYPE_INCOMING_INVOICE, DOCUMENT_TYPE_RECEIPT
from bot.services.accounting_document_registry import AccountingDocumentSummary, list_recent_accounting_documents


router = Router()


_RECENT_ACCOUNTING_DOCUMENT_ALIASES = {
    'posledne blocky',
    'moje blocky',
    'ukaz posledne blocky',
    'poslednych 5 blockov',
    'posledne vydavky',
    'покажи останні чеки',
    'покажи 5 останніх чеків',
    'останні блочки',
    'последние чеки',
    'последние блочки',
}


@router.message(StateFilter(None), Command('blocky'))
async def cmd_blocky(message: Message, config: Config) -> None:
    await _send_recent_accounting_documents(message=message, config=config)


@router.message(
    StateFilter(None),
    lambda message: _normalize_alias(message.text or '') in _RECENT_ACCOUNTING_DOCUMENT_ALIASES,
)
async def recent_accounting_documents_alias(message: Message, config: Config) -> None:
    await _send_recent_accounting_documents(message=message, config=config)


async def _send_recent_accounting_documents(*, message: Message, config: Config) -> None:
    summaries = list_recent_accounting_documents(storage_dir=config.storage_dir, limit=5)
    if not summaries:
        await message.answer('Zatiaľ nemáte uložené žiadne bločky ani prijaté doklady.')
        return

    lines = ['Posledné bločky a prijaté doklady:']
    for index, summary in enumerate(summaries, start=1):
        lines.extend(_format_summary(index, summary))
    await message.answer('\n'.join(lines))


def _format_summary(index: int, summary: AccountingDocumentSummary) -> list[str]:
    issue_date = _display(summary.issue_date)
    vendor = _display(summary.vendor_name)
    amount = _format_amount(summary.total_amount, summary.currency)
    purchase_subject = _display(summary.purchase_subject)
    document_type = _document_type_label(summary.document_type)
    return [
        '',
        f'{index}. {issue_date} — {vendor} — {amount}',
        f'   Predmet nákupu: {purchase_subject}',
        f'   Typ: {document_type}',
    ]


def _format_amount(total_amount: str | None, currency: str | None) -> str:
    amount = _display(total_amount).replace('.', ',')
    if amount == 'nezistené':
        return amount
    currency_value = (currency or '').strip().upper()
    if not currency_value:
        return amount
    return f'{amount} {currency_value}'


def _document_type_label(document_type: str) -> str:
    if document_type == DOCUMENT_TYPE_RECEIPT:
        return 'bloček'
    if document_type == DOCUMENT_TYPE_INCOMING_INVOICE:
        return 'prijatá faktúra'
    return 'doklad'


def _display(value: str | None) -> str:
    text = (value or '').strip()
    return text or 'nezistené'


def _normalize_alias(value: str) -> str:
    text = value.strip().lower()
    normalized = unicodedata.normalize('NFKD', text)
    without_diacritics = ''.join(ch for ch in normalized if not unicodedata.combining(ch))
    compact = re.sub(r'\s+', ' ', without_diacritics).strip()
    return compact
