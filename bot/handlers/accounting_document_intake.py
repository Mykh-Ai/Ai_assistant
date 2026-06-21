from __future__ import annotations

from dataclasses import replace
import hashlib
import logging
from pathlib import Path
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup, ReplyKeyboardRemove

from bot.config import Config
from bot.services.accounting_document_duplicates import DuplicateMatch, find_duplicate_accounting_document
from bot.services.accounting_document_categories import (
    AccountingDocumentCategory,
    AccountingDocumentCategoryError,
    allowed_categories_payload,
    create_workspace_category,
    find_similar_category,
    get_category_by_id,
    list_active_categories,
    normalize_category_label,
)
from bot.services.accounting_document_lmm import (
    AccountingDocumentLmmError,
    AccountingDocumentLmmInput,
    classify_accounting_document,
    extract_accounting_document_metadata,
)
from bot.services.accounting_document_models import (
    DOCUMENT_TYPE_INCOMING_INVOICE,
    DOCUMENT_TYPE_RECEIPT,
    AccountingDocumentCandidate,
    AccountingDocumentCategoryCandidate,
    AccountingDocumentConfirmedCategory,
    AccountingDocumentLineItemCandidate,
    AccountingDocumentQuality,
    AccountingDocumentSource,
    AccountingDocumentSuggestedCategory,
    candidate_to_metadata_dict,
)
from bot.services.accounting_document_storage import (
    AccountingDocumentSaveResult,
    AccountingDocumentStorageError,
    WORKSPACE_KEY,
    cleanup_temp_staging_path,
    save_confirmed_accounting_document,
    stage_original_file,
    temp_staging_dir,
    workspace_key_for_supplier,
)
from bot.services.accounting_document_archive_service import AccountingDocumentArchiveService
from bot.services.accounting_document_validation import validate_accounting_document_candidate
from bot.services.decision_resolver import (
    resolve_accounting_document_category_preview_decision,
    resolve_accounting_document_category_selection,
    resolve_accounting_document_category_similar_decision,
    resolve_accounting_document_category_unknown_decision,
    resolve_yes_no,
)
from bot.services.temp_intake_session import build_intake_session_metadata, ensure_intake_session_active


router = Router()
logger = logging.getLogger(__name__)

_DECISION_CONTEXT = 'accounting_document_category_preview_decision'
_UNKNOWN_CATEGORY_CONTEXT = 'accounting_document_category_unknown_decision'
_CATEGORY_CREATE_CONFIRM_CONTEXT = 'accounting_document_category_create_confirm'
_CATEGORY_SELECTION_CONTEXT = 'accounting_document_category_selection'
_CATEGORY_SIMILAR_CONTEXT = 'accounting_document_category_similar_decision'
_STATE_CANDIDATE_KEY = 'accounting_document_candidate'
_STATE_TEMP_ORIGINAL_KEY = 'accounting_document_temp_original_path'
_STATE_FILE_UNIQUE_ID_KEY = 'accounting_document_file_unique_id'
_STATE_EXTENSION_KEY = 'accounting_document_extension'
_STATE_DUPLICATE_MATCH_KEY = 'accounting_document_duplicate_match'
_STATE_SELECTED_LINE_ITEM_INDEX_KEY = 'accounting_document_selected_line_item_index'
_STATE_CATEGORY_TARGET_KEY = 'accounting_document_category_target'
_STATE_PENDING_CATEGORY_LABEL_KEY = 'accounting_document_pending_category_label'
_STATE_SIMILAR_CATEGORY_ID_KEY = 'accounting_document_similar_category_id'
_ACCOUNTING_INTAKE_RECOVERY_HINT = 'Ak chcete spracovanie dokumentu zrušiť, napíšte „zrušiť“.'
_CATEGORY_BUTTON_LIMIT = 20

_PREVIEW_SAVE_WITH_CATEGORY = '✅ Uložiť s kategóriou'
_PREVIEW_CHANGE_CATEGORY = '✏️ Zmeniť kategóriu'
_PREVIEW_CHANGE_LINE_ITEM_CATEGORY = '✏️ Zmeniť kategóriu položky'
_PREVIEW_SAVE_WITHOUT_CATEGORY = '📎 Uložiť bez kategórie'
_CANCEL_BUTTON = '❌ Zrušiť'
_YES_BUTTON = '✅ Áno'
_NO_BUTTON = '❌ Nie'
_DUPLICATE_ADD_OTHER = '➕ Pridať iný bloček'
_DUPLICATE_SAVE_ANYWAY = '⚠️ Uložiť aj tak'
_DUPLICATE_MENU = '🏠 /menu'
_UNKNOWN_CHOOSE_EXISTING = '📂 Vybrať existujúcu kategóriu'
_UNKNOWN_CREATE_NEW = '➕ Vytvoriť novú kategóriu'
_UNKNOWN_SAVE_AS_REVIEW = '📎 Uložiť ako Na kontrolu'
_SIMILAR_USE_EXISTING = '✅ Použiť existujúcu'
_SIMILAR_CREATE_ANYWAY = '➕ Vytvoriť novú aj tak'
_BACK_BUTTON = '↩️ Späť'


def _with_accounting_intake_recovery_hint(text: str) -> str:
    return f'{text}\n\n{_ACCOUNTING_INTAKE_RECOVERY_HINT}'


def _reply_keyboard(rows: list[list[str]]) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=label) for label in row] for row in rows],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def _remove_keyboard() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove(remove_keyboard=True)


def _yes_no_reply_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard([[_YES_BUTTON, _NO_BUTTON]])


def _duplicate_warning_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard([[_DUPLICATE_ADD_OTHER], [_DUPLICATE_SAVE_ANYWAY], [_DUPLICATE_MENU]])


def _preview_decision_keyboard(candidate: AccountingDocumentCandidate) -> ReplyKeyboardMarkup:
    rows = [
        [_PREVIEW_SAVE_WITH_CATEGORY],
        [_PREVIEW_CHANGE_CATEGORY],
    ]
    if candidate.line_items:
        rows.append([_PREVIEW_CHANGE_LINE_ITEM_CATEGORY])
    rows.extend([[_PREVIEW_SAVE_WITHOUT_CATEGORY], [_CANCEL_BUTTON]])
    return _reply_keyboard(rows)


def _unknown_category_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(
        [
            [_UNKNOWN_CHOOSE_EXISTING],
            [_UNKNOWN_CREATE_NEW],
            [_UNKNOWN_SAVE_AS_REVIEW],
            [_CANCEL_BUTTON],
        ]
    )


def _similar_category_keyboard() -> ReplyKeyboardMarkup:
    return _reply_keyboard(
        [
            [_SIMILAR_USE_EXISTING],
            [_SIMILAR_CREATE_ANYWAY],
            [_BACK_BUTTON],
        ]
    )


def _category_selection_keyboard(allowed: list[dict[str, Any]]) -> ReplyKeyboardMarkup:
    visible = [
        str(item.get('label_sk') or item.get('category_id') or '').strip()
        for item in allowed
        if item.get('category_id')
    ]
    visible = [label for label in visible if label]
    if len(visible) > _CATEGORY_BUTTON_LIMIT:
        return _reply_keyboard([[_BACK_BUTTON]])
    rows = [[label] for label in visible]
    rows.append([_BACK_BUTTON])
    return _reply_keyboard(rows)


def _message_supplier_telegram_id(message: Message) -> int | None:
    return getattr(getattr(message, 'from_user', None), 'id', None)


class AccountingDocumentIntakeStates(StatesGroup):
    waiting_upload = State()
    waiting_duplicate_decision = State()
    waiting_preview_decision = State()
    waiting_unknown_category_decision = State()
    waiting_document_category_selection = State()
    waiting_line_item_selection = State()
    waiting_line_item_category_selection = State()
    waiting_new_category_label = State()
    waiting_new_category_confirm = State()
    waiting_similar_category_decision = State()


@router.message(Command('doklad', 'expense', 'intake', 'add_blocek', 'dodat_blocek'))
async def cmd_accounting_document_intake(message: Message, state: FSMContext) -> None:
    if hasattr(message, 'from_user') and message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.', reply_markup=_remove_keyboard())
        return
    await state.clear()
    await state.set_state(AccountingDocumentIntakeStates.waiting_upload)
    await message.answer(
        'Pošlite fotku alebo PDF bločka / prijatej faktúry.\n'
        'Spracujem ju ako návrh a pred uložením si vyžiadam potvrdenie.'
    )


@router.message(AccountingDocumentIntakeStates.waiting_upload, F.photo | F.document)
async def accounting_document_upload(message: Message, state: FSMContext, config: Config, bot: Bot) -> None:
    if await state.get_state() != AccountingDocumentIntakeStates.waiting_upload.state:
        return

    attachment = _extract_supported_attachment(message)
    if attachment is None:
        await message.answer(
            _with_accounting_intake_recovery_hint(
                'Pošlite, prosím, fotku alebo PDF bločka / prijatej faktúry.'
            )
        )
        return

    if hasattr(message, 'from_user') and message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.', reply_markup=_remove_keyboard())
        return

    supplier_telegram_id = _message_supplier_telegram_id(message)
    file_unique_id = attachment['file_unique_id']
    staged_path = (
        temp_staging_dir(config.storage_dir, file_unique_id, supplier_telegram_id)
        / f'original{attachment["extension"]}'
    )
    staged_path.parent.mkdir(parents=True, exist_ok=True)

    telegram_file = await bot.get_file(attachment['file_id'])
    await bot.download_file(telegram_file.file_path, destination=staged_path)
    file_bytes = staged_path.read_bytes()

    document_input = AccountingDocumentLmmInput(
        input_type=attachment['input_type'],
        original_filename=attachment['original_filename'],
        mime_type=attachment['mime_type'],
        file_bytes=file_bytes,
    )
    try:
        classification = await classify_accounting_document(
            document_input=document_input,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
        if classification.document_type == 'unknown':
            _cleanup_temp_quietly(config.storage_dir, staged_path)
            await message.answer('Doklad sa nepodarilo rozpoznať. Skúste poslať čitateľnejšiu fotku alebo PDF.')
            return
        candidate = await extract_accounting_document_metadata(
            document_input=document_input,
            document_type_hint=classification.document_type,
            allowed_categories=allowed_categories_payload(
                storage_dir=config.storage_dir,
                supplier_telegram_id=supplier_telegram_id,
            ),
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    except AccountingDocumentLmmError:
        _cleanup_temp_quietly(config.storage_dir, staged_path)
        await message.answer('Doklad sa nepodarilo spracovať. Skúste ho poslať ešte raz v lepšej kvalite.')
        return
    except ValueError:
        _cleanup_temp_quietly(config.storage_dir, staged_path)
        await message.answer('Doklad sa nepodarilo bezpečne prečítať. Skúste ho poslať ešte raz.')
        return

    candidate = _with_upload_source(candidate, attachment)
    if candidate.quality.readability == 'poor':
        _cleanup_temp_quietly(config.storage_dir, staged_path)
        await message.answer('Doklad je príliš rozmazaný alebo nečitateľný. Skúste poslať ostrejšiu fotku alebo PDF.')
        return

    validation = validate_accounting_document_candidate(candidate)
    if not validation.can_save:
        _cleanup_temp_quietly(config.storage_dir, staged_path)
        await message.answer(_format_validation_failure(validation.errors))
        return

    await _store_preview_or_duplicate_state(
        message=message,
        state=state,
        config=config,
        candidate=candidate,
        staged_path=staged_path,
        file_unique_id=file_unique_id,
        extension=attachment['extension'],
    )


async def process_staged_accounting_document(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    staged_path: Path,
    attachment_metadata: dict[str, str],
    document_type_hint: str | None = None,
) -> None:
    if hasattr(message, 'from_user') and message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.', reply_markup=_remove_keyboard())
        return

    supplier_telegram_id = _message_supplier_telegram_id(message)
    file_unique_id = attachment_metadata.get('file_unique_id')
    accounting_staged_path = stage_original_file(
        storage_dir=config.storage_dir,
        source_path=staged_path,
        file_unique_id=file_unique_id,
        supplier_telegram_id=supplier_telegram_id,
    )
    await _process_accounting_document_from_staged_original(
        message=message,
        state=state,
        config=config,
        staged_path=accounting_staged_path,
        attachment_metadata=attachment_metadata,
        document_type_hint=document_type_hint,
        failure_state=None,
    )


@router.message(AccountingDocumentIntakeStates.waiting_upload)
async def accounting_document_waiting_upload(message: Message) -> None:
    await message.answer(
        _with_accounting_intake_recovery_hint('Pošlite, prosím, fotku alebo PDF bločka / prijatej faktúry.')
    )


@router.message(AccountingDocumentIntakeStates.waiting_preview_decision)
async def accounting_document_preview_decision(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_preview_decision_text(
        message=message,
        state=state,
        config=config,
        decision_text=message.text or '',
    )


@router.message(AccountingDocumentIntakeStates.waiting_duplicate_decision)
async def accounting_document_duplicate_decision(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_duplicate_decision_text(
        message=message,
        state=state,
        config=config,
        decision_text=message.text or '',
    )


@router.message(AccountingDocumentIntakeStates.waiting_unknown_category_decision)
async def accounting_document_unknown_category_decision(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_unknown_category_decision_text(
        message=message,
        state=state,
        config=config,
        decision_text=message.text or '',
    )


@router.message(AccountingDocumentIntakeStates.waiting_document_category_selection)
async def accounting_document_category_selection(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_category_selection_text(
        message=message,
        state=state,
        config=config,
        selection_text=message.text or '',
        target='document',
    )


@router.message(AccountingDocumentIntakeStates.waiting_line_item_selection)
async def accounting_document_line_item_selection(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_line_item_selection_text(
        message=message,
        state=state,
        config=config,
        selection_text=message.text or '',
    )


@router.message(AccountingDocumentIntakeStates.waiting_line_item_category_selection)
async def accounting_document_line_item_category_selection(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_category_selection_text(
        message=message,
        state=state,
        config=config,
        selection_text=message.text or '',
        target='line_item',
    )


@router.message(AccountingDocumentIntakeStates.waiting_new_category_label)
async def accounting_document_new_category_label(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_new_category_label_text(
        message=message,
        state=state,
        config=config,
        label_text=message.text or '',
    )


@router.message(AccountingDocumentIntakeStates.waiting_new_category_confirm)
async def accounting_document_new_category_confirm(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_new_category_confirm_text(
        message=message,
        state=state,
        config=config,
        decision_text=message.text or '',
    )


@router.message(AccountingDocumentIntakeStates.waiting_similar_category_decision)
async def accounting_document_similar_category_decision(message: Message, state: FSMContext, config: Config) -> None:
    await handle_accounting_document_similar_category_decision_text(
        message=message,
        state=state,
        config=config,
        decision_text=message.text or '',
    )


async def handle_accounting_document_duplicate_decision_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return

    decision = await resolve_yes_no(
        context_name='accounting_document_duplicate_save_decision',
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer(_with_accounting_intake_recovery_hint('Prosím, odpovedzte áno alebo nie.'), reply_markup=_yes_no_reply_keyboard())
        return

    data = await state.get_data()
    source_path_value = data.get(_STATE_TEMP_ORIGINAL_KEY)
    if decision == 'no':
        if isinstance(source_path_value, str):
            _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
        await state.clear()
        await message.answer('Spracovanie dokladu bolo zrušené.', reply_markup=_remove_keyboard())
        return

    candidate = _candidate_from_state_payload(data.get(_STATE_CANDIDATE_KEY) if isinstance(data.get(_STATE_CANDIDATE_KEY), dict) else {})
    if not isinstance(source_path_value, str):
        await state.clear()
        await message.answer('Návrh dokladu už nie je dostupný. Spustite /doklad znova.', reply_markup=_remove_keyboard())
        return

    await state.update_data(
        **build_intake_session_metadata(
            temp_paths=[Path(source_path_value)],
            cleanup_kind='accounting_document_preview',
        )
    )
    await _send_category_entry_or_preview(message=message, state=state, candidate=candidate)


async def handle_accounting_document_preview_decision_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return

    decision = await resolve_accounting_document_category_preview_decision(
        context_name=_DECISION_CONTEXT,
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )

    if decision == 'unknown':
        await message.answer(
            _with_accounting_intake_recovery_hint(
                'Prosím, vyberte: uložiť s kategóriou, zmeniť kategóriu, uložiť bez kategórie alebo zrušiť.'
            )
        )
        return

    if decision == 'change_document_category':
        await _ask_document_category_selection(message=message, state=state, config=config)
        return

    if decision == 'change_line_item_category':
        await _ask_line_item_selection(message=message, state=state)
        return

    if decision == 'save_without_category':
        await _save_accounting_document_from_state(
            message=message,
            state=state,
            config=config,
            confirm_categories=False,
        )
        return

    if decision == 'cancel':
        state_data = await state.get_data()
        source_path_value = state_data.get(_STATE_TEMP_ORIGINAL_KEY)
        if isinstance(source_path_value, str):
            _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
        await state.clear()
        await message.answer('Spracovanie dokladu bolo zrušené.', reply_markup=_remove_keyboard())
        return

    await _save_accounting_document_from_state(
        message=message,
        state=state,
        config=config,
        confirm_categories=True,
    )


async def handle_accounting_document_unknown_category_decision_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return
    decision = await resolve_accounting_document_category_unknown_decision(
        context_name=_UNKNOWN_CATEGORY_CONTEXT,
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer(
            _unknown_category_message(_candidate_from_state_payload((await state.get_data()).get(_STATE_CANDIDATE_KEY, {}))),
            reply_markup=_unknown_category_keyboard(),
        )
        return
    if decision == 'cancel':
        await _cancel_accounting_document_preview(message=message, state=state, config=config)
        return
    if decision == 'choose_existing_category':
        await _ask_document_category_selection(message=message, state=state, config=config)
        return
    if decision == 'create_new_category':
        await _ask_new_category_label(message=message, state=state, target='document')
        return
    if decision == 'save_as_unknown_review':
        await _apply_category_to_state(message=message, state=state, config=config, category_id='unknown_review', target='document')
        return


async def handle_accounting_document_category_selection_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    selection_text: str,
    target: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return
    allowed = _allowed_categories_for_message(message=message, config=config)
    decision = await resolve_accounting_document_category_selection(
        context_name=_CATEGORY_SELECTION_CONTEXT,
        user_input_text=selection_text,
        allowed_categories=allowed,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'cancel':
        await _return_to_preview(message=message, state=state)
        return
    if decision == 'unknown':
        await message.answer(_format_category_selection_prompt(allowed), reply_markup=_category_selection_keyboard(allowed))
        return
    await _apply_category_to_state(message=message, state=state, config=config, category_id=decision, target=target)


async def handle_accounting_document_line_item_selection_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    selection_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return
    candidate = _candidate_from_state_payload((await state.get_data()).get(_STATE_CANDIDATE_KEY, {}))
    index = _parse_line_item_selection(selection_text, len(candidate.line_items))
    if index is None:
        await message.answer(_format_line_item_selection_prompt(candidate))
        return
    await state.update_data(**{_STATE_SELECTED_LINE_ITEM_INDEX_KEY: index, _STATE_CATEGORY_TARGET_KEY: 'line_item'})
    await state.set_state(AccountingDocumentIntakeStates.waiting_line_item_category_selection)
    allowed = _allowed_categories_for_message(message=message, config=config)
    await message.answer(_format_category_selection_prompt(allowed), reply_markup=_category_selection_keyboard(allowed))


async def handle_accounting_document_new_category_label_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    label_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return
    try:
        label = normalize_category_label(label_text)
    except AccountingDocumentCategoryError:
        await message.answer('Zadajte krátky názov kategórie textom, bez prázdneho alebo príliš dlhého názvu.')
        return
    supplier_telegram_id = _message_supplier_telegram_id(message)
    similar = find_similar_category(
        storage_dir=config.storage_dir,
        label=label,
        supplier_telegram_id=supplier_telegram_id,
        include_inactive=True,
    )
    await state.update_data(**{_STATE_PENDING_CATEGORY_LABEL_KEY: label})
    if similar is not None:
        await state.update_data(**{_STATE_SIMILAR_CATEGORY_ID_KEY: similar.category_id})
        await state.set_state(AccountingDocumentIntakeStates.waiting_similar_category_decision)
        await message.answer(
            f'Podobná kategória už existuje: {similar.display_label}.\n'
            'Chcete použiť túto kategóriu?\n\n'
            'Odpovedzte: použiť existujúcu, vytvoriť novú aj tak, alebo späť.',
            reply_markup=_similar_category_keyboard(),
        )
        return
    await state.set_state(AccountingDocumentIntakeStates.waiting_new_category_confirm)
    await message.answer(
        f'Vytvoriť novú kategóriu „{label}“?\n\nOdpovedzte: áno / nie.',
        reply_markup=_yes_no_reply_keyboard(),
    )


async def handle_accounting_document_new_category_confirm_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return
    decision = await resolve_yes_no(
        context_name=_CATEGORY_CREATE_CONFIRM_CONTEXT,
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if decision == 'unknown':
        await message.answer('Prosím, odpovedzte áno alebo nie.', reply_markup=_yes_no_reply_keyboard())
        return
    if decision == 'no':
        await _return_to_preview(message=message, state=state)
        return
    data = await state.get_data()
    label = _optional_str(data.get(_STATE_PENDING_CATEGORY_LABEL_KEY))
    if label is None:
        await _return_to_preview(message=message, state=state)
        return
    category = create_workspace_category(
        storage_dir=config.storage_dir,
        label=label,
        supplier_telegram_id=_message_supplier_telegram_id(message),
    )
    await _apply_category_to_state(message=message, state=state, config=config, category_id=category.category_id, target=_category_target(data))


async def handle_accounting_document_similar_category_decision_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return
    decision = await resolve_accounting_document_category_similar_decision(
        context_name=_CATEGORY_SIMILAR_CONTEXT,
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    data = await state.get_data()
    if decision == 'unknown':
        await message.answer('Odpovedzte: použiť existujúcu, vytvoriť novú aj tak, alebo späť.', reply_markup=_similar_category_keyboard())
        return
    if decision == 'back':
        await _return_to_preview(message=message, state=state)
        return
    if decision == 'use_existing_category':
        similar_id = _optional_str(data.get(_STATE_SIMILAR_CATEGORY_ID_KEY))
        if similar_id is None:
            await _return_to_preview(message=message, state=state)
            return
        await _apply_category_to_state(message=message, state=state, config=config, category_id=similar_id, target=_category_target(data))
        return
    label = _optional_str(data.get(_STATE_PENDING_CATEGORY_LABEL_KEY))
    if label is None:
        await _return_to_preview(message=message, state=state)
        return
    category = create_workspace_category(
        storage_dir=config.storage_dir,
        label=label,
        supplier_telegram_id=_message_supplier_telegram_id(message),
        allow_similar=True,
    )
    await _apply_category_to_state(message=message, state=state, config=config, category_id=category.category_id, target=_category_target(data))


async def _send_category_entry_or_preview(
    *,
    message: Message,
    state: FSMContext,
    candidate: AccountingDocumentCandidate,
) -> None:
    if _candidate_needs_unknown_category_decision(candidate):
        await state.set_state(AccountingDocumentIntakeStates.waiting_unknown_category_decision)
        await message.answer(_unknown_category_message(candidate), reply_markup=_unknown_category_keyboard())
        return
    await state.set_state(AccountingDocumentIntakeStates.waiting_preview_decision)
    await message.answer(_format_accounting_document_preview(candidate), reply_markup=_preview_decision_keyboard(candidate))


async def _ask_document_category_selection(*, message: Message, state: FSMContext, config: Config) -> None:
    await state.update_data(**{_STATE_CATEGORY_TARGET_KEY: 'document'})
    await state.set_state(AccountingDocumentIntakeStates.waiting_document_category_selection)
    allowed = _allowed_categories_for_message(message=message, config=config)
    await message.answer(_format_category_selection_prompt(allowed), reply_markup=_category_selection_keyboard(allowed))


async def _ask_line_item_selection(*, message: Message, state: FSMContext) -> None:
    candidate = _candidate_from_state_payload((await state.get_data()).get(_STATE_CANDIDATE_KEY, {}))
    if not candidate.line_items:
        await message.answer('Na doklade nie sú rozpoznané samostatné položky. Môžete zmeniť hlavnú kategóriu.', reply_markup=_preview_decision_keyboard(candidate))
        return
    await state.set_state(AccountingDocumentIntakeStates.waiting_line_item_selection)
    await message.answer(_format_line_item_selection_prompt(candidate))


async def _ask_new_category_label(*, message: Message, state: FSMContext, target: str) -> None:
    await state.update_data(**{_STATE_CATEGORY_TARGET_KEY: target})
    await state.set_state(AccountingDocumentIntakeStates.waiting_new_category_label)
    candidate = _candidate_from_state_payload((await state.get_data()).get(_STATE_CANDIDATE_KEY, {}))
    suggestions = _format_suggested_labels(candidate)
    await message.answer(
        f'{suggestions}\nZadajte názov novej kategórie textom.'.strip(),
        reply_markup=_remove_keyboard(),
    )


async def _apply_category_to_state(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    category_id: str,
    target: str,
) -> None:
    data = await state.get_data()
    candidate = _candidate_from_state_payload(data.get(_STATE_CANDIDATE_KEY, {}))
    category = get_category_by_id(
        storage_dir=config.storage_dir,
        category_id=category_id,
        supplier_telegram_id=_message_supplier_telegram_id(message),
        include_inactive=True,
    )
    if category is None:
        await message.answer('Kategória už nie je dostupná. Vyberte inú kategóriu.')
        return
    updated = _apply_category(candidate, category=category, target=target, state_data=data)
    await state.update_data(**{_STATE_CANDIDATE_KEY: candidate_to_metadata_dict(updated)})
    await state.set_state(AccountingDocumentIntakeStates.waiting_preview_decision)
    await message.answer(_format_accounting_document_preview(updated), reply_markup=_preview_decision_keyboard(updated))


async def _return_to_preview(*, message: Message, state: FSMContext) -> None:
    candidate = _candidate_from_state_payload((await state.get_data()).get(_STATE_CANDIDATE_KEY, {}))
    await state.set_state(AccountingDocumentIntakeStates.waiting_preview_decision)
    await message.answer(_format_accounting_document_preview(candidate), reply_markup=_preview_decision_keyboard(candidate))


async def _cancel_accounting_document_preview(*, message: Message, state: FSMContext, config: Config) -> None:
    state_data = await state.get_data()
    source_path_value = state_data.get(_STATE_TEMP_ORIGINAL_KEY)
    if isinstance(source_path_value, str):
        _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
    await state.clear()
    await message.answer('Spracovanie dokladu bolo zrušené.', reply_markup=_remove_keyboard())


async def _save_accounting_document_from_state(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    confirm_categories: bool,
) -> None:
    state_data = await state.get_data()
    candidate_payload = state_data.get(_STATE_CANDIDATE_KEY)
    source_path_value = state_data.get(_STATE_TEMP_ORIGINAL_KEY)
    file_unique_id = state_data.get(_STATE_FILE_UNIQUE_ID_KEY)
    extension = state_data.get(_STATE_EXTENSION_KEY)
    if not isinstance(candidate_payload, dict) or not isinstance(source_path_value, str) or not isinstance(file_unique_id, str):
        await state.clear()
        await message.answer('Návrh dokladu už nie je dostupný. Spustite /doklad znova.', reply_markup=_remove_keyboard())
        return

    if hasattr(message, 'from_user') and message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.', reply_markup=_remove_keyboard())
        return

    supplier_telegram_id = _message_supplier_telegram_id(message)
    candidate = _candidate_from_state_payload(candidate_payload)
    candidate = (
        _confirm_candidate_categories(candidate, config=config, supplier_telegram_id=supplier_telegram_id)
        if confirm_categories
        else _without_categories(candidate)
    )
    try:
        result = save_confirmed_accounting_document(
            storage_dir=config.storage_dir,
            source_path=Path(source_path_value),
            candidate=candidate,
            file_unique_id=file_unique_id,
            extension=extension if isinstance(extension, str) else None,
            supplier_telegram_id=supplier_telegram_id,
        )
    except (AccountingDocumentStorageError, OSError, ValueError):
        await message.answer('Doklad sa nepodarilo uložiť. Skúste /doklad znova.', reply_markup=_remove_keyboard())
        return

    _enqueue_archive_after_confirmed_save(
        db_path=config.db_path,
        result=result,
        candidate=candidate,
        supplier_telegram_id=supplier_telegram_id,
    )
    _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
    await state.clear()
    await message.answer(_format_post_save_next_steps(), reply_markup=_remove_keyboard())


def _format_post_save_next_steps() -> str:
    return (
        'Doklad bol uložený.\n\n'
        'Ďalšie kroky:\n'
        '➕ /add_blocek — pridať ďalší bloček\n'
        '📄 /blocek — zobraziť posledné doklady\n'
        '🏠 /menu — hlavné menu / hotovo'
    )


def _extract_supported_attachment(message: Message) -> dict[str, str] | None:
    if message.photo:
        photo = message.photo[-1]
        return {
            'file_id': photo.file_id,
            'file_unique_id': getattr(photo, 'file_unique_id', None) or photo.file_id,
            'extension': '.jpg',
            'input_type': 'photo',
            'original_filename': 'photo.jpg',
            'mime_type': 'image/jpeg',
        }

    document = message.document
    if document is None:
        return None

    file_name = document.file_name or 'document.pdf'
    mime_type = document.mime_type or ''
    suffix = Path(file_name).suffix.lower()
    if suffix != '.pdf' and mime_type != 'application/pdf':
        return None

    return {
        'file_id': document.file_id,
        'file_unique_id': getattr(document, 'file_unique_id', None) or document.file_id,
        'extension': '.pdf',
        'input_type': 'pdf',
        'original_filename': file_name,
        'mime_type': mime_type or 'application/pdf',
    }


async def _process_accounting_document_from_staged_original(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    staged_path: Path,
    attachment_metadata: dict[str, str],
    document_type_hint: str | None = None,
    failure_state: State | None = None,
) -> None:
    file_unique_id = attachment_metadata['file_unique_id']
    file_bytes = staged_path.read_bytes()
    document_input = AccountingDocumentLmmInput(
        input_type=attachment_metadata['input_type'],
        original_filename=attachment_metadata['original_filename'],
        mime_type=attachment_metadata['mime_type'],
        file_bytes=file_bytes,
    )
    try:
        resolved_document_type = document_type_hint
        if resolved_document_type is None:
            classification = await classify_accounting_document(
                document_input=document_input,
                api_key=config.openai_api_key,
                model=config.openai_llm_model,
            )
            resolved_document_type = classification.document_type
        if resolved_document_type == 'unknown':
            await _handle_accounting_processing_failure(
                message=message,
                state=state,
                config=config,
                staged_path=staged_path,
                failure_state=failure_state,
                text='Doklad sa nepodarilo rozpoznať. Skúste poslať čitateľnejšiu fotku alebo PDF.',
            )
            return
        candidate = await extract_accounting_document_metadata(
            document_input=document_input,
            document_type_hint=resolved_document_type,
            allowed_categories=allowed_categories_payload(
                storage_dir=config.storage_dir,
                supplier_telegram_id=_message_supplier_telegram_id(message),
            ),
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    except AccountingDocumentLmmError:
        await _handle_accounting_processing_failure(
            message=message,
            state=state,
            config=config,
            staged_path=staged_path,
            failure_state=failure_state,
            text='Doklad sa nepodarilo spracovať. Skúste ho poslať ešte raz v lepšej kvalite.',
        )
        return
    except ValueError:
        await _handle_accounting_processing_failure(
            message=message,
            state=state,
            config=config,
            staged_path=staged_path,
            failure_state=failure_state,
            text='Doklad sa nepodarilo bezpečne prečítať. Skúste ho poslať ešte raz.',
        )
        return

    candidate = _with_upload_source(candidate, attachment_metadata)
    if candidate.quality.readability == 'poor':
        await _handle_accounting_processing_failure(
            message=message,
            state=state,
            config=config,
            staged_path=staged_path,
            failure_state=failure_state,
            text='Doklad je príliš rozmazaný alebo nečitateľný. Skúste poslať ostrejšiu fotku alebo PDF.',
        )
        return

    validation = validate_accounting_document_candidate(candidate)
    if not validation.can_save:
        await _handle_accounting_processing_failure(
            message=message,
            state=state,
            config=config,
            staged_path=staged_path,
            failure_state=failure_state,
            text=_format_validation_failure(validation.errors),
        )
        return

    await _store_preview_or_duplicate_state(
        message=message,
        state=state,
        config=config,
        candidate=candidate,
        staged_path=staged_path,
        file_unique_id=file_unique_id,
        extension=attachment_metadata['extension'],
    )


async def _store_preview_or_duplicate_state(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    candidate: AccountingDocumentCandidate,
    staged_path: Path,
    file_unique_id: str,
    extension: str,
) -> None:
    state_payload = {
        _STATE_CANDIDATE_KEY: candidate_to_metadata_dict(candidate),
        _STATE_TEMP_ORIGINAL_KEY: str(staged_path),
        _STATE_FILE_UNIQUE_ID_KEY: file_unique_id,
        _STATE_EXTENSION_KEY: extension,
        **build_intake_session_metadata(
            temp_paths=[staged_path],
            cleanup_kind='accounting_document_preview',
        ),
    }
    if hasattr(message, 'from_user') and message.from_user is None:
        _cleanup_temp_quietly(config.storage_dir, staged_path)
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.', reply_markup=_remove_keyboard())
        return

    supplier_telegram_id = _message_supplier_telegram_id(message)
    if supplier_telegram_id is None:
        duplicate = find_duplicate_accounting_document(storage_dir=config.storage_dir, candidate=candidate)
    else:
        duplicate = find_duplicate_accounting_document(
            storage_dir=config.storage_dir,
            candidate=candidate,
            workspace_key=workspace_key_for_supplier(supplier_telegram_id),
        )
    if duplicate is not None:
        state_payload[_STATE_DUPLICATE_MATCH_KEY] = duplicate.to_dict()
        await state.update_data(**state_payload)
        await state.set_state(AccountingDocumentIntakeStates.waiting_duplicate_decision)
        await message.answer(_format_duplicate_warning(duplicate), reply_markup=_duplicate_warning_keyboard())
        return

    await state.update_data(**state_payload)
    await _send_category_entry_or_preview(message=message, state=state, candidate=candidate)


async def _handle_accounting_processing_failure(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    staged_path: Path,
    failure_state: State | None,
    text: str,
) -> None:
    _cleanup_temp_quietly(config.storage_dir, staged_path)
    if failure_state is None:
        await state.clear()
        await message.answer(text, reply_markup=_remove_keyboard())
    else:
        await state.set_state(failure_state)
        await message.answer(text)


def _with_upload_source(candidate: AccountingDocumentCandidate, attachment: dict[str, str]) -> AccountingDocumentCandidate:
    return replace(
        candidate,
        source=AccountingDocumentSource(
            input_type=attachment['input_type'],
            original_filename=candidate.source.original_filename or attachment['original_filename'],
            file_unique_id=attachment['file_unique_id'],
            upload_date=candidate.source.upload_date,
        ),
    )


def _enqueue_archive_after_confirmed_save(
    *,
    db_path: Path,
    result: AccountingDocumentSaveResult,
    candidate: AccountingDocumentCandidate,
    supplier_telegram_id: int | None,
) -> None:
    workspace_id = (
        workspace_key_for_supplier(supplier_telegram_id)
        if supplier_telegram_id is not None
        else WORKSPACE_KEY
    )
    try:
        AccountingDocumentArchiveService(db_path).enqueue_confirmed_document(
            workspace_id=workspace_id,
            telegram_id=supplier_telegram_id or 0,
            document_id=result.metadata_path.stem,
            document_type=candidate.document_type,
            local_file_path=result.original_path,
            metadata_path=result.metadata_path,
        )
    except Exception:
        logger.warning(
            'archive_enqueue_failed workspace_ref=%s document_ref=%s error_category=%s',
            _safe_log_ref(workspace_id),
            _safe_log_ref(result.metadata_path.stem),
            'archive_enqueue_failed',
        )


def _safe_log_ref(value: object, *, length: int = 12) -> str:
    text = str(value).strip()
    if not text:
        return 'missing'
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:length]


def _allowed_categories_for_message(*, message: Message, config: Config) -> list[dict[str, Any]]:
    return allowed_categories_payload(
        storage_dir=config.storage_dir,
        supplier_telegram_id=_message_supplier_telegram_id(message),
    )


def _candidate_needs_unknown_category_decision(candidate: AccountingDocumentCandidate) -> bool:
    category_candidate = candidate.document_category_candidate
    return (
        candidate.category is None
        and category_candidate is not None
        and category_candidate.category_id == 'unknown_review'
    )


def _unknown_category_message(candidate: AccountingDocumentCandidate) -> str:
    suggestions = _format_suggested_labels(candidate)
    return (
        'Kategóriu sa nepodarilo jednoznačne určiť.\n\n'
        'Najprv skúste vybrať existujúcu kategóriu.\n'
        'Ak vhodná kategória neexistuje, môžete vytvoriť novú.\n\n'
        f'{suggestions}'
        'Odpovedzte jednou z možností:\n'
        '- vybrať existujúcu kategóriu\n'
        '- vytvoriť novú kategóriu\n'
        '- uložiť ako Na kontrolu\n'
        '- zrušiť'
    )


def _format_suggested_labels(candidate: AccountingDocumentCandidate) -> str:
    labels = [suggestion.label_sk for suggestion in candidate.suggested_new_categories[:3]]
    if not labels:
        return ''
    rendered = '\n'.join(f'- {label}' for label in labels)
    return f'Možné nové názvy, ak v zozname nič vhodné nenájdete:\n{rendered}\n\n'


def _format_category_selection_prompt(allowed: list[dict[str, Any]]) -> str:
    rendered = '\n'.join(
        f'- {item["category_id"]}: {item.get("label_sk") or item["category_id"]}'
        for item in allowed
        if item.get('category_id')
    )
    return (
        'Vyberte kategóriu z existujúceho zoznamu.\n\n'
        f'{rendered}\n\n'
        'Napíšte category_id alebo názov kategórie. Ak sa chcete vrátiť, napíšte zrušiť.'
    )


def _format_line_item_selection_prompt(candidate: AccountingDocumentCandidate) -> str:
    if not candidate.line_items:
        return 'Na doklade nie sú rozpoznané samostatné položky.'
    rendered = '\n'.join(
        f'{index + 1}. {item.description or "položka"}'
        for index, item in enumerate(candidate.line_items)
    )
    return f'Vyberte položku, ktorej chcete zmeniť kategóriu:\n\n{rendered}'


def _parse_line_item_selection(value: str, item_count: int) -> int | None:
    try:
        index = int(str(value).strip()) - 1
    except ValueError:
        return None
    if 0 <= index < item_count:
        return index
    return None


def _category_target(state_data: dict[str, Any]) -> str:
    target = _optional_str(state_data.get(_STATE_CATEGORY_TARGET_KEY))
    return target if target in {'document', 'line_item'} else 'document'


def _apply_category(
    candidate: AccountingDocumentCandidate,
    *,
    category: AccountingDocumentCategory,
    target: str,
    state_data: dict[str, Any],
) -> AccountingDocumentCandidate:
    confirmed = _confirmed_category_from_category(category, candidate.document_category_candidate)
    if target == 'line_item':
        index_value = state_data.get(_STATE_SELECTED_LINE_ITEM_INDEX_KEY)
        try:
            index = int(index_value)
        except (TypeError, ValueError):
            index = -1
        if 0 <= index < len(candidate.line_items):
            line_items = list(candidate.line_items)
            item = line_items[index]
            item_confirmed = _confirmed_category_from_category(category, item.category_candidate)
            line_items[index] = replace(item, category=item_confirmed)
            return replace(candidate, line_items=line_items)
    return replace(candidate, category=confirmed)


def _confirmed_category_from_category(
    category: AccountingDocumentCategory,
    candidate: AccountingDocumentCategoryCandidate | None,
) -> AccountingDocumentConfirmedCategory:
    return AccountingDocumentConfirmedCategory(
        category_id=category.category_id,
        label_snapshot=category.display_label,
        source='user_confirmed',
        candidate_source='lmm' if candidate is not None else 'user_selected',
        confidence=candidate.confidence if candidate is not None else None,
        review_required=category.review_required or (candidate.review_required if candidate is not None else False),
    )


def _confirm_candidate_categories(
    candidate: AccountingDocumentCandidate,
    *,
    config: Config,
    supplier_telegram_id: int | None,
) -> AccountingDocumentCandidate:
    confirmed_document = candidate.category
    if confirmed_document is None and candidate.document_category_candidate and candidate.document_category_candidate.category_id:
        category = get_category_by_id(
            storage_dir=config.storage_dir,
            category_id=candidate.document_category_candidate.category_id,
            supplier_telegram_id=supplier_telegram_id,
        )
        if category is not None:
            confirmed_document = _confirmed_category_from_category(category, candidate.document_category_candidate)

    line_items: list[AccountingDocumentLineItemCandidate] = []
    for item in candidate.line_items:
        confirmed = item.category
        if confirmed is None and item.category_candidate and item.category_candidate.category_id:
            category = get_category_by_id(
                storage_dir=config.storage_dir,
                category_id=item.category_candidate.category_id,
                supplier_telegram_id=supplier_telegram_id,
            )
            if category is not None:
                confirmed = _confirmed_category_from_category(category, item.category_candidate)
        line_items.append(replace(item, category=confirmed))
    return replace(candidate, category=confirmed_document, line_items=line_items)


def _without_categories(candidate: AccountingDocumentCandidate) -> AccountingDocumentCandidate:
    line_items = [
        replace(
            item,
            category=None,
            category_candidate=None,
            suggested_new_categories=[],
        )
        for item in candidate.line_items
    ]
    return replace(
        candidate,
        category=None,
        document_category_candidate=None,
        suggested_new_categories=[],
        line_items=line_items,
    )


def _format_accounting_document_preview(candidate: AccountingDocumentCandidate) -> str:
    document_type_label = _document_type_label(candidate.document_type)
    date_value = candidate.issue_date or 'nezistené'
    amount_value = candidate.total_amount if candidate.total_amount is not None else 'nezistené'
    currency_value = candidate.currency or ''
    payment_value = candidate.payment_method or 'nezistené'
    purchase_subject_value = candidate.purchase_subject or 'nezistené'
    category_label = _candidate_category_label(candidate)
    line_items_block = _format_preview_line_items(candidate)

    return (
        'Náhľad dokladu\n'
        f'Typ: {document_type_label}\n'
        f'Dodávateľ: {candidate.vendor_name or "nezistené"}\n'
        f'Dátum: {date_value}\n'
        f'Suma: {amount_value} {currency_value}'.rstrip()
        + '\n'
        f'Platba: {payment_value}\n'
        f'Predmet nákupu: {purchase_subject_value}\n'
        f'{line_items_block}'
        f'Navrhovaná kategória: {category_label}\n\n'
        'Vyberte ďalší krok:\n'
        '- uložiť s kategóriou\n'
        '- zmeniť kategóriu\n'
        '- zmeniť kategóriu položky\n'
        '- uložiť bez kategórie\n'
        '- zrušiť'
    )


def _candidate_category_label(candidate: AccountingDocumentCandidate) -> str:
    if candidate.category is not None:
        return candidate.category.label_snapshot
    if candidate.document_category_candidate and candidate.document_category_candidate.category_id:
        return candidate.document_category_candidate.category_id
    return 'nezistená'


def _format_preview_line_items(candidate: AccountingDocumentCandidate) -> str:
    if not candidate.line_items:
        return ''
    rendered: list[str] = ['\nPoložky:']
    for index, item in enumerate(candidate.line_items, start=1):
        category_label = 'bez kategórie'
        if item.category is not None:
            category_label = item.category.label_snapshot
        elif item.category_candidate and item.category_candidate.category_id:
            category_label = item.category_candidate.category_id
        rendered.append(f'{index}. {item.description or "položka"} — {category_label}')
    return '\n'.join(rendered) + '\n\n'


def _format_duplicate_warning(match: DuplicateMatch) -> str:
    document_type_label = _document_type_label(match.document_type).lower()
    amount = match.total_amount.replace('.', ',')
    purchase_subject = match.purchase_subject or 'nezistené'
    vendor = match.vendor_name or 'nezistené'
    return (
        'POZOR! Tento doklad už je uložený!!!!\n\n'
        f'Typ: {document_type_label}\n'
        f'Dodávateľ: {vendor}\n'
        f'Dátum: {match.issue_date}\n'
        f'Suma: {amount} {match.currency}\n'
        f'Predmet nákupu: {purchase_subject}\n\n'
        'Ak je to ten istý bloček, nepridávajte ho znova.\n'
        'Vyberte: pridať iný bloček, uložiť aj tak alebo /menu.'
    )


def _format_validation_failure(errors: list[str]) -> str:
    details = ', '.join(errors) if errors else 'neznáma chyba'
    return (
        'Doklad sa nepodarilo pripraviť na uloženie. '
        f'Chýbajú alebo sú neplatné polia: {details}. '
        'Skúste poslať čitateľnejší doklad.'
    )


def _document_type_label(document_type: str) -> str:
    if document_type == DOCUMENT_TYPE_RECEIPT:
        return 'Bloček'
    if document_type == DOCUMENT_TYPE_INCOMING_INVOICE:
        return 'Prijatá faktúra'
    return 'Neznáme'


def _candidate_from_state_payload(payload: dict[str, Any]) -> AccountingDocumentCandidate:
    source = payload.get('source') if isinstance(payload.get('source'), dict) else {}
    business = payload.get('business') if isinstance(payload.get('business'), dict) else {}
    quality = payload.get('quality') if isinstance(payload.get('quality'), dict) else {}
    line_items_payload = payload.get('line_items') if isinstance(payload.get('line_items'), list) else []
    return AccountingDocumentCandidate(
        document_type=str(payload.get('document_type') or ''),
        vendor_name=_optional_str(business.get('vendor_name')),
        vendor_ico=_optional_str(business.get('vendor_ico')),
        document_number=_optional_str(business.get('document_number')),
        issue_date=_optional_str(business.get('issue_date')),
        tax_date=_optional_str(business.get('tax_date')),
        due_date=_optional_str(business.get('due_date')),
        total_amount=business.get('total_amount'),
        currency=_optional_str(business.get('currency')),
        vat_amount=business.get('vat_amount'),
        iban=_optional_str(business.get('iban')),
        variable_symbol=_optional_str(business.get('variable_symbol')),
        payment_method=_optional_str(business.get('payment_method')),
        purchase_subject=_optional_str(business.get('purchase_subject'))
        or _optional_str(business.get('category_candidate')),
        document_category_candidate=_category_candidate_from_payload(payload.get('document_category_candidate')),
        suggested_new_categories=_suggested_categories_from_payload(payload.get('suggested_new_categories')),
        line_items=[_line_item_from_payload(item) for item in line_items_payload if isinstance(item, dict)],
        category=_confirmed_category_from_payload(payload.get('category')),
        source=AccountingDocumentSource(
            input_type=str(source.get('input_type') or 'unknown'),
            original_filename=_optional_str(source.get('original_filename')),
            file_unique_id=_optional_str(source.get('file_unique_id')),
            upload_date=_optional_str(source.get('upload_date')),
        ),
        quality=AccountingDocumentQuality(
            readability=str(quality.get('readability') or 'unknown'),
            missing_fields=_string_list(quality.get('missing_fields')),
            warnings=_string_list(quality.get('warnings')),
        ),
    )


def _category_candidate_from_payload(value: Any) -> AccountingDocumentCategoryCandidate | None:
    if not isinstance(value, dict):
        return None
    return AccountingDocumentCategoryCandidate(
        category_id=_optional_str(value.get('category_id')),
        confidence=_optional_str(value.get('confidence')) or 'low',
        review_required=bool(value.get('review_required', False)),
        reason=_optional_str(value.get('reason')),
    )


def _suggested_categories_from_payload(value: Any) -> list[AccountingDocumentSuggestedCategory]:
    if not isinstance(value, list):
        return []
    suggestions: list[AccountingDocumentSuggestedCategory] = []
    for item in value[:3]:
        if not isinstance(item, dict):
            continue
        label = _optional_str(item.get('label_sk'))
        if label:
            suggestions.append(AccountingDocumentSuggestedCategory(label_sk=label, reason=_optional_str(item.get('reason'))))
    return suggestions


def _confirmed_category_from_payload(value: Any) -> AccountingDocumentConfirmedCategory | None:
    if not isinstance(value, dict):
        return None
    category_id = _optional_str(value.get('category_id'))
    label_snapshot = _optional_str(value.get('label_snapshot'))
    if category_id is None or label_snapshot is None:
        return None
    return AccountingDocumentConfirmedCategory(
        category_id=category_id,
        label_snapshot=label_snapshot,
        source=_optional_str(value.get('source')) or 'user_confirmed',
        candidate_source=_optional_str(value.get('candidate_source')),
        confidence=_optional_str(value.get('confidence')),
        review_required=bool(value.get('review_required', False)),
    )


def _line_item_from_payload(value: dict[str, Any]) -> AccountingDocumentLineItemCandidate:
    return AccountingDocumentLineItemCandidate(
        description=_optional_str(value.get('description')),
        amount=value.get('amount'),
        currency=_optional_str(value.get('currency')),
        vat_amount=value.get('vat_amount'),
        category_candidate=_category_candidate_from_payload(value.get('category_candidate')),
        suggested_new_categories=_suggested_categories_from_payload(value.get('suggested_new_categories')),
        category=_confirmed_category_from_payload(value.get('category')),
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _cleanup_temp_quietly(storage_dir: Path, staged_path: Path) -> None:
    try:
        cleanup_temp_staging_path(storage_dir=storage_dir, staged_path=staged_path)
    except (AccountingDocumentStorageError, OSError):
        pass
