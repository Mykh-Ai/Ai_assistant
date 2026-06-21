from __future__ import annotations

from pathlib import Path

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.config import Config
from bot.handlers.accounting_document_intake import process_staged_accounting_document
from bot.handlers.contacts import _start_add_contact_from_source
from bot.services.decision_resolver import (
    resolve_attachment_document_type_choice,
    resolve_attachment_route_choice,
    resolve_yes_no,
)
from bot.services.officeflow_attachment_lmm import OfficeFlowAttachmentLmmError, classify_officeflow_attachment
from bot.services.officeflow_attachment_models import (
    DOCUMENT_TYPE_CONTACT_SOURCE,
    DOCUMENT_TYPE_CONTRACT,
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    DOCUMENT_TYPE_UNKNOWN,
    OfficeFlowAttachment,
    OfficeFlowAttachmentClassification,
)
from bot.services.officeflow_attachment_storage import (
    OfficeFlowAttachmentStorageError,
    cleanup_staged_attachment,
    stage_message_attachment,
)
from bot.services.supplier_service import SupplierService
from bot.services.temp_intake_session import build_intake_session_metadata, ensure_intake_session_active


router = Router(name='officeflow_attachment_router')

_STATE_ATTACHMENT_PATH = 'officeflow_attachment_staged_path'
_STATE_ATTACHMENT_METADATA = 'officeflow_attachment_metadata'
_STATE_CLASSIFICATION = 'officeflow_attachment_classification'
_STATE_EXTRACTED_PDF_TEXT = 'officeflow_attachment_extracted_pdf_text'
_OFFICEFLOW_ATTACHMENT_RECOVERY_HINT = 'Ak nechcete pokračovať, napíšte „zrušiť“.'
_YES_BUTTON = '✅ Áno'
_NO_BUTTON = '❌ Nie'


def _with_officeflow_attachment_recovery_hint(text: str) -> str:
    return f'{text}\n\n{_OFFICEFLOW_ATTACHMENT_RECOVERY_HINT}'


class OfficeFlowAttachmentRouterStates(StatesGroup):
    accounting_proposal = State()
    route_choice = State()
    unknown_clarification = State()


def _yes_no_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=_YES_BUTTON), KeyboardButton(text=_NO_BUTTON)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder='Vyberte možnosť',
    )


def _remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


@router.message(StateFilter(None), F.photo | F.document)
async def officeflow_idle_attachment(message: Message, state: FSMContext, config: Config, bot: Bot) -> None:
    if message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return
    attachment = await stage_message_attachment(
        message=message,
        bot=bot,
        storage_dir=config.storage_dir,
        supplier_telegram_id=message.from_user.id,
    )
    if attachment is None:
        await message.answer('Tento typ prílohy zatiaľ nepodporujem. Pošlite, prosím, fotku alebo PDF.')
        return

    try:
        classification = await classify_officeflow_attachment(
            attachment=attachment,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    except (OfficeFlowAttachmentLmmError, ValueError, OSError):
        _cleanup_attachment_quietly(config.storage_dir, attachment.staged_path)
        await state.clear()
        await message.answer('Prílohu sa nepodarilo bezpečne zaradiť. Skúste ju poslať ešte raz.')
        return

    await _store_attachment_state(state=state, attachment=attachment, classification=classification)
    await _ask_for_document_type_route(message=message, state=state, document_type=classification.document_type)


@router.message(OfficeFlowAttachmentRouterStates.accounting_proposal)
async def officeflow_accounting_proposal(message: Message, state: FSMContext, config: Config) -> None:
    await handle_officeflow_accounting_proposal_text(
        message=message,
        state=state,
        config=config,
        answer_text=message.text or '',
    )


async def handle_officeflow_accounting_proposal_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    answer_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return

    decision = await resolve_yes_no(
        context_name='idle_attachment_accounting_proposal',
        user_input_text=answer_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer(
            _with_officeflow_attachment_recovery_hint('Prosím, odpovedzte áno alebo nie.'),
            reply_markup=_yes_no_reply_keyboard(),
        )
        return

    if decision == 'no':
        await _cleanup_state_attachment(config=config, state=state)
        await state.clear()
        await message.answer('Spracovanie prílohy bolo zrušené.', reply_markup=_remove_keyboard())
        return

    data = await state.get_data()
    staged_path_value = data.get(_STATE_ATTACHMENT_PATH)
    metadata = data.get(_STATE_ATTACHMENT_METADATA)
    classification = data.get(_STATE_CLASSIFICATION)
    if not isinstance(staged_path_value, str) or not isinstance(metadata, dict):
        await state.clear()
        await message.answer('Návrh prílohy už nie je dostupný. Pošlite dokument znova.', reply_markup=_remove_keyboard())
        return

    document_type_hint = classification.get('document_type') if isinstance(classification, dict) else None
    await process_staged_accounting_document(
        message=message,
        state=state,
        config=config,
        staged_path=Path(staged_path_value),
        attachment_metadata={key: str(value) for key, value in metadata.items() if value is not None},
        document_type_hint=document_type_hint if isinstance(document_type_hint, str) else None,
    )
    _cleanup_attachment_quietly(config.storage_dir, Path(staged_path_value))


@router.message(OfficeFlowAttachmentRouterStates.route_choice)
async def officeflow_route_choice(message: Message, state: FSMContext, config: Config) -> None:
    await handle_officeflow_route_choice_text(
        message=message,
        state=state,
        config=config,
        answer_text=message.text or '',
    )


async def handle_officeflow_route_choice_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    answer_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return

    decision = await resolve_attachment_route_choice(
        context_name='idle_attachment_route_choice',
        user_input_text=answer_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer(
            _with_officeflow_attachment_recovery_hint(
                'Prosím, vyberte: vytvoriť kontakt, uložiť zmluvu alebo zrušiť.'
            )
        )
        return

    if decision == 'cancel':
        await _cleanup_state_attachment(config=config, state=state)
        await state.clear()
        await message.answer('Spracovanie prílohy bolo zrušené.', reply_markup=_remove_keyboard())
        return

    if decision == 'save_contract':
        await message.answer(
            'Samostatné uloženie zmluvy zatiaľ nie je dostupné. '
            'Môžem z dokumentu vytvoriť kontakt alebo spracovanie zrušiť.'
        )
        return

    await _start_contact_from_staged_attachment(message=message, state=state, config=config)


@router.message(OfficeFlowAttachmentRouterStates.unknown_clarification)
async def officeflow_unknown_clarification(message: Message, state: FSMContext, config: Config) -> None:
    await handle_officeflow_unknown_clarification_text(
        message=message,
        state=state,
        config=config,
        answer_text=message.text or '',
    )


async def handle_officeflow_unknown_clarification_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    answer_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return

    decision = await resolve_attachment_document_type_choice(
        context_name='idle_attachment_document_type_choice',
        user_input_text=answer_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer(
            _with_officeflow_attachment_recovery_hint(
                'Prosím, napíšte: bloček, prijatá faktúra, zmluva alebo zrušiť.'
            )
        )
        return
    if decision == 'cancel':
        await _cleanup_state_attachment(config=config, state=state)
        await state.clear()
        await message.answer('Spracovanie prílohy bolo zrušené.', reply_markup=_remove_keyboard())
        return

    await _ask_for_document_type_route(message=message, state=state, document_type=decision)


async def _ask_for_document_type_route(*, message: Message, state: FSMContext, document_type: str) -> None:
    if document_type in {DOCUMENT_TYPE_RECEIPT, DOCUMENT_TYPE_INCOMING_INVOICE}:
        await state.set_state(OfficeFlowAttachmentRouterStates.accounting_proposal)
        await message.answer(
            'Vyzerá to ako bloček/prijatá faktúra. '
            'Chcete ju spracovať ako výdavkový doklad?\n'
            'Vyberte možnosť:',
            reply_markup=_yes_no_reply_keyboard(),
        )
        return

    if document_type in {DOCUMENT_TYPE_CONTRACT, DOCUMENT_TYPE_CONTACT_SOURCE}:
        await state.set_state(OfficeFlowAttachmentRouterStates.route_choice)
        await message.answer(
            'Vyzerá to ako zmluva alebo podklad ku kontaktu. '
            'Chcete z dokumentu vytvoriť kontakt, uložiť zmluvu alebo zrušiť?'
        )
        return

    if document_type == DOCUMENT_TYPE_UNKNOWN:
        await state.set_state(OfficeFlowAttachmentRouterStates.unknown_clarification)
        await message.answer(
            'Dokument sa nepodarilo jednoznačne zaradiť. '
            'Je to bloček, prijatá faktúra alebo zmluva?'
        )
        return

    await state.set_state(OfficeFlowAttachmentRouterStates.unknown_clarification)
    await message.answer(
        'Dokument sa nepodarilo jednoznačne zaradiť. '
        'Je to bloček, prijatá faktúra alebo zmluva?'
    )


async def _start_contact_from_staged_attachment(*, message: Message, state: FSMContext, config: Config) -> None:
    data = await state.get_data()
    staged_path_value = data.get(_STATE_ATTACHMENT_PATH)
    if message.from_user is None:
        if isinstance(staged_path_value, str):
            _cleanup_attachment_quietly(config.storage_dir, Path(staged_path_value))
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        if isinstance(staged_path_value, str):
            _cleanup_attachment_quietly(config.storage_dir, Path(staged_path_value))
        await state.clear()
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /moj_profil.')
        return

    metadata = data.get(_STATE_ATTACHMENT_METADATA)
    extracted_pdf_text = data.get(_STATE_EXTRACTED_PDF_TEXT)
    classification = data.get(_STATE_CLASSIFICATION)
    caption = metadata.get('caption') if isinstance(metadata, dict) else None
    reason = classification.get('reason') if isinstance(classification, dict) else None
    source_text = '\n'.join(str(part) for part in [caption, reason] if part)

    await _start_add_contact_from_source(
        message=message,
        state=state,
        config=config,
        source_text=source_text or 'idle attachment contact source',
        document_text=extracted_pdf_text if isinstance(extracted_pdf_text, str) else None,
        contract_path=None,
    )
    if isinstance(staged_path_value, str):
        _cleanup_attachment_quietly(config.storage_dir, Path(staged_path_value))


async def _store_attachment_state(
    *,
    state: FSMContext,
    attachment: OfficeFlowAttachment,
    classification: OfficeFlowAttachmentClassification,
) -> None:
    await state.update_data(
        **{
            _STATE_ATTACHMENT_PATH: str(attachment.staged_path),
            _STATE_ATTACHMENT_METADATA: {
                'file_id': attachment.file_id,
                'file_unique_id': attachment.file_unique_id,
                'input_type': attachment.input_type,
                'original_filename': attachment.original_filename,
                'mime_type': attachment.mime_type,
                'extension': attachment.extension,
                'caption': attachment.caption,
            },
            _STATE_CLASSIFICATION: {
                'document_type': classification.document_type,
                'confidence': classification.confidence,
                'reason': classification.reason,
            },
            _STATE_EXTRACTED_PDF_TEXT: attachment.extracted_pdf_text,
            **build_intake_session_metadata(
                temp_paths=[attachment.staged_path],
                cleanup_kind='officeflow_attachment',
            ),
        }
    )


async def _cleanup_state_attachment(*, config: Config, state: FSMContext) -> None:
    data = await state.get_data()
    staged_path_value = data.get(_STATE_ATTACHMENT_PATH)
    if isinstance(staged_path_value, str):
        _cleanup_attachment_quietly(config.storage_dir, Path(staged_path_value))


def _cleanup_attachment_quietly(storage_dir: Path, staged_path: Path) -> None:
    try:
        cleanup_staged_attachment(storage_dir=storage_dir, staged_path=staged_path)
    except (OfficeFlowAttachmentStorageError, OSError):
        pass
