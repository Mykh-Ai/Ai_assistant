from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.services.accounting_document_models import DOCUMENT_TYPE_INCOMING_INVOICE, DOCUMENT_TYPE_RECEIPT
from bot.services.accounting_document_archive_service import (
    ARCHIVE_STATUS_ABANDONED,
    ARCHIVE_STATUS_FAILED,
    ARCHIVE_STATUS_PENDING,
    ARCHIVE_STATUS_RETRY_WAIT,
    ARCHIVE_STATUS_UPLOADED,
    ARCHIVE_STATUS_UPLOADING,
    AccountingDocumentArchiveService,
)
from bot.services.accounting_document_registry import AccountingDocumentSummary, list_recent_accounting_documents
from bot.services.accounting_document_storage import WORKSPACE_KEY, workspace_key_for_supplier


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


@router.message(Command('blocky', 'blocek'))
async def cmd_blocky(message: Message, config: Config, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await _send_recent_accounting_documents(message=message, config=config)


@router.message(
    lambda message: _normalize_alias(message.text or '') in _RECENT_ACCOUNTING_DOCUMENT_ALIASES,
)
async def recent_accounting_documents_alias(message: Message, config: Config, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    await _send_recent_accounting_documents(message=message, config=config)


async def _send_recent_accounting_documents(*, message: Message, config: Config) -> None:
    if hasattr(message, 'from_user') and message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return
    supplier_telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    if supplier_telegram_id is None:
        workspace_key = WORKSPACE_KEY
        summaries = list_recent_accounting_documents(storage_dir=config.storage_dir, limit=5)
    else:
        workspace_key = workspace_key_for_supplier(supplier_telegram_id)
        summaries = list_recent_accounting_documents(
            storage_dir=config.storage_dir,
            workspace_key=workspace_key,
            limit=5,
        )
    if not summaries:
        await message.answer('Zatiaľ nemáte uložené žiadne bločky ani prijaté doklady.')
        return

    archive_service = AccountingDocumentArchiveService(config.db_path)
    lines = ['Posledné bločky a prijaté doklady:']
    for index, summary in enumerate(summaries, start=1):
        archive_status = _archive_status_for_summary(
            archive_service=archive_service,
            workspace_key=workspace_key,
            summary=summary,
        )
        lines.extend(_format_summary(index, summary, archive_status=archive_status))
    await message.answer('\n'.join(lines))


def _format_summary(index: int, summary: AccountingDocumentSummary, *, archive_status: str = 'not_configured') -> list[str]:
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
        f'   {_archive_status_label(archive_status)}',
    ]


def _archive_status_for_summary(
    *,
    archive_service: AccountingDocumentArchiveService,
    workspace_key: str,
    summary: AccountingDocumentSummary,
) -> str:
    document_id = Path(summary.metadata_path).stem
    if not document_id:
        return 'not_configured'
    state = archive_service.get_state_read_only(
        workspace_id=workspace_key,
        document_id=document_id,
    )
    if state is None:
        return 'not_configured'
    return state.archive_status


def _archive_status_label(status: str) -> str:
    labels = {
        'not_configured': 'Archív: Google Drive archív zatiaľ nie je pripojený',
        ARCHIVE_STATUS_PENDING: 'Archív: čaká na spracovanie',
        ARCHIVE_STATUS_UPLOADING: 'Archív: spracúva sa',
        ARCHIVE_STATUS_UPLOADED: 'Archív: pripravené v archíve / nahraté podľa evidencie',
        ARCHIVE_STATUS_RETRY_WAIT: 'Archív: čaká na opakovanie',
        ARCHIVE_STATUS_FAILED: 'Archív: zlyhalo',
        ARCHIVE_STATUS_ABANDONED: 'Archív: zastavené',
    }
    return labels.get(status, labels['not_configured'])


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
