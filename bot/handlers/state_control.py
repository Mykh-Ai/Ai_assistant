from __future__ import annotations

from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.handlers.accounting_document_intake import AccountingDocumentIntakeStates
from bot.handlers.contacts import ContactStates
from bot.handlers.delete_user_database import DeleteUserDatabaseStates
from bot.handlers.invoice import InvoiceStates, process_invoice_postpdf_decision
from bot.handlers.officeflow_attachment_router import OfficeFlowAttachmentRouterStates
from bot.handlers.onboarding import OnboardingStates, SupplierProfileEditStates
from bot.handlers.supplier import ServiceAliasStates
from bot.services.accounting_document_storage import (
    AccountingDocumentStorageError,
    cleanup_temp_staging_path,
)
from bot.services.decision_resolver import is_global_cancel_text
from bot.services.officeflow_attachment_storage import (
    OfficeFlowAttachmentStorageError,
    cleanup_staged_attachment,
)


router = Router(name='state_control')

IDLE_CANCEL_MESSAGE = 'Nie je rozpracovaná žiadna akcia. Bot je v režime čakania.'
STATE_CANCELLED_MESSAGE = 'Rozpracovaná akcia bola zrušená. Bot je v režime čakania.'
PERSISTED_EDIT_CANCELLED_MESSAGE = 'Úprava faktúry bola ukončená. Faktúra zostala uložená.'


@router.message(Command('cancel'))
async def cmd_cancel(message: Message, state: FSMContext, config: Config) -> None:
    await cancel_current_state(message=message, state=state, config=config)


@router.message(lambda message: is_global_cancel_text(message.text or ''))
async def cancel_alias(message: Message, state: FSMContext, config: Config) -> None:
    _ = config
    await cancel_current_state(message=message, state=state, config=config)


async def cancel_current_state(*, message: Message, state: FSMContext, config: Config) -> None:
    current_state = await state.get_state()
    if current_state is None:
        await state.clear()
        await message.answer(IDLE_CANCEL_MESSAGE)
        return

    data = await state.get_data()

    if current_state == InvoiceStates.waiting_pdf_decision.state and data.get('edit_stage') != 'persisted':
        await process_invoice_postpdf_decision(
            message=message,
            state=state,
            config=config,
            decision_text='zrušiť',
        )
        return

    if current_state == InvoiceStates.waiting_pdf_decision.state and data.get('edit_stage') == 'persisted':
        await state.clear()
        await message.answer(PERSISTED_EDIT_CANCELLED_MESSAGE)
        return

    if _is_accounting_intake_state(current_state):
        _cleanup_accounting_temp(config=config, data=data)

    if _is_officeflow_attachment_state(current_state):
        _cleanup_officeflow_temp(config=config, data=data)

    await state.clear()
    await message.answer(STATE_CANCELLED_MESSAGE)


def _is_accounting_intake_state(current_state: str | None) -> bool:
    state_values = {
        AccountingDocumentIntakeStates.waiting_upload.state,
        AccountingDocumentIntakeStates.waiting_duplicate_decision.state,
        AccountingDocumentIntakeStates.waiting_preview_decision.state,
    }
    return current_state in state_values


def _is_officeflow_attachment_state(current_state: str | None) -> bool:
    state_values = {
        OfficeFlowAttachmentRouterStates.accounting_proposal.state,
        OfficeFlowAttachmentRouterStates.route_choice.state,
        OfficeFlowAttachmentRouterStates.unknown_clarification.state,
    }
    return current_state in state_values


def _cleanup_accounting_temp(*, config: Config, data: dict) -> None:
    source_path = data.get('accounting_document_temp_original_path')
    if not isinstance(source_path, str):
        return
    try:
        cleanup_temp_staging_path(storage_dir=config.storage_dir, staged_path=Path(source_path))
    except (AccountingDocumentStorageError, OSError):
        pass


def _cleanup_officeflow_temp(*, config: Config, data: dict) -> None:
    source_path = data.get('officeflow_attachment_staged_path')
    if not isinstance(source_path, str):
        return
    try:
        cleanup_staged_attachment(storage_dir=config.storage_dir, staged_path=Path(source_path))
    except (OfficeFlowAttachmentStorageError, OSError):
        pass


_STATE_TYPES_REFERENCED_FOR_AUDIT = (
    ContactStates,
    DeleteUserDatabaseStates,
    InvoiceStates,
    OnboardingStates,
    ServiceAliasStates,
    SupplierProfileEditStates,
)
