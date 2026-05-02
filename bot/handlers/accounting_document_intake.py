from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.accounting_document_duplicates import DuplicateMatch, find_duplicate_accounting_document
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
    AccountingDocumentQuality,
    AccountingDocumentSource,
    candidate_to_metadata_dict,
)
from bot.services.accounting_document_storage import (
    AccountingDocumentStorageError,
    cleanup_temp_staging_path,
    save_confirmed_accounting_document,
    stage_original_file,
    temp_staging_dir,
    workspace_key_for_supplier,
)
from bot.services.accounting_document_validation import validate_accounting_document_candidate
from bot.services.decision_resolver import resolve_approve_edit_cancel, resolve_yes_no
from bot.services.temp_intake_session import build_intake_session_metadata, ensure_intake_session_active


router = Router()

_DECISION_CONTEXT = 'accounting_document_intake_preview'
_STATE_CANDIDATE_KEY = 'accounting_document_candidate'
_STATE_TEMP_ORIGINAL_KEY = 'accounting_document_temp_original_path'
_STATE_FILE_UNIQUE_ID_KEY = 'accounting_document_file_unique_id'
_STATE_EXTENSION_KEY = 'accounting_document_extension'
_STATE_DUPLICATE_MATCH_KEY = 'accounting_document_duplicate_match'


def _message_supplier_telegram_id(message: Message) -> int | None:
    return getattr(getattr(message, 'from_user', None), 'id', None)


class AccountingDocumentIntakeStates(StatesGroup):
    waiting_upload = State()
    waiting_duplicate_decision = State()
    waiting_preview_decision = State()


@router.message(Command('doklad', 'expense', 'intake'))
async def cmd_accounting_document_intake(message: Message, state: FSMContext) -> None:
    if hasattr(message, 'from_user') and message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
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
        await message.answer('Pošlite, prosím, fotku alebo PDF bločka / prijatej faktúry.')
        return

    if hasattr(message, 'from_user') and message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.')
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
        await message.answer('Nepodarilo sa identifikovať používateľa.')
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
    await message.answer('Pošlite, prosím, fotku alebo PDF bločka / prijatej faktúry.')


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
        await message.answer('Prosím, odpovedzte áno alebo nie.')
        return

    data = await state.get_data()
    source_path_value = data.get(_STATE_TEMP_ORIGINAL_KEY)
    if decision == 'no':
        if isinstance(source_path_value, str):
            _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
        await state.clear()
        await message.answer('Spracovanie dokladu bolo zrušené.')
        return

    candidate = _candidate_from_state_payload(data.get(_STATE_CANDIDATE_KEY) if isinstance(data.get(_STATE_CANDIDATE_KEY), dict) else {})
    if not isinstance(source_path_value, str):
        await state.clear()
        await message.answer('Návrh dokladu už nie je dostupný. Spustite /doklad znova.')
        return

    await state.update_data(
        **build_intake_session_metadata(
            temp_paths=[Path(source_path_value)],
            cleanup_kind='accounting_document_preview',
        )
    )
    await state.set_state(AccountingDocumentIntakeStates.waiting_preview_decision)
    await message.answer(_format_accounting_document_preview(candidate))


async def handle_accounting_document_preview_decision_text(
    *,
    message: Message,
    state: FSMContext,
    config: Config,
    decision_text: str,
) -> None:
    if not await ensure_intake_session_active(message=message, state=state, storage_dir=config.storage_dir):
        return

    decision = await resolve_approve_edit_cancel(
        context_name=_DECISION_CONTEXT,
        user_input_text=decision_text,
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )

    if decision == 'unknown':
        await message.answer('Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.')
        return

    if decision == 'edit':
        await message.answer(
            'Úprava výdavkového dokladu zatiaľ nie je dostupná. '
            'Môžete ho schváliť alebo zrušiť.'
        )
        return

    if decision == 'cancel':
        state_data = await state.get_data()
        source_path_value = state_data.get(_STATE_TEMP_ORIGINAL_KEY)
        if isinstance(source_path_value, str):
            _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
        await state.clear()
        await message.answer('Spracovanie dokladu bolo zrušené.')
        return

    state_data = await state.get_data()
    candidate_payload = state_data.get(_STATE_CANDIDATE_KEY)
    source_path_value = state_data.get(_STATE_TEMP_ORIGINAL_KEY)
    file_unique_id = state_data.get(_STATE_FILE_UNIQUE_ID_KEY)
    extension = state_data.get(_STATE_EXTENSION_KEY)
    if not isinstance(candidate_payload, dict) or not isinstance(source_path_value, str) or not isinstance(file_unique_id, str):
        await state.clear()
        await message.answer('Návrh dokladu už nie je dostupný. Spustite /doklad znova.')
        return

    if hasattr(message, 'from_user') and message.from_user is None:
        await state.clear()
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier_telegram_id = _message_supplier_telegram_id(message)
    try:
        result = save_confirmed_accounting_document(
            storage_dir=config.storage_dir,
            source_path=Path(source_path_value),
            candidate=_candidate_from_state_payload(candidate_payload),
            file_unique_id=file_unique_id,
            extension=extension if isinstance(extension, str) else None,
            supplier_telegram_id=supplier_telegram_id,
        )
    except (AccountingDocumentStorageError, OSError, ValueError):
        await message.answer('Doklad sa nepodarilo uložiť. Skúste /doklad znova.')
        return

    _cleanup_temp_quietly(config.storage_dir, Path(source_path_value))
    await state.clear()
    await message.answer(f'Doklad bol uložený.\nMetadata: {result.metadata_path}')


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
        await message.answer('Nepodarilo sa identifikovať používateľa.')
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
        await message.answer(_format_duplicate_warning(duplicate))
        return

    await state.update_data(**state_payload)
    await state.set_state(AccountingDocumentIntakeStates.waiting_preview_decision)
    await message.answer(_format_accounting_document_preview(candidate))


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


def _format_accounting_document_preview(candidate: AccountingDocumentCandidate) -> str:
    document_type_label = _document_type_label(candidate.document_type)
    date_value = candidate.issue_date or 'nezistené'
    amount_value = candidate.total_amount if candidate.total_amount is not None else 'nezistené'
    currency_value = candidate.currency or ''
    payment_value = candidate.payment_method or 'nezistené'
    purchase_subject_value = candidate.purchase_subject or 'nezistené'

    return (
        'Náhľad dokladu\n'
        f'Typ: {document_type_label}\n'
        f'Dodávateľ: {candidate.vendor_name or "nezistené"}\n'
        f'Dátum: {date_value}\n'
        f'Suma: {amount_value} {currency_value}'.rstrip()
        + '\n'
        f'Platba: {payment_value}\n'
        f'Predmet nákupu: {purchase_subject_value}\n\n'
        'Schváliť, upraviť alebo zrušiť?'
    )


def _format_duplicate_warning(match: DuplicateMatch) -> str:
    document_type_label = _document_type_label(match.document_type).lower()
    amount = match.total_amount.replace('.', ',')
    purchase_subject = match.purchase_subject or 'nezistené'
    vendor = match.vendor_name or 'nezistené'
    return (
        'Podobný doklad už existuje:\n\n'
        f'Typ: {document_type_label}\n'
        f'Dodávateľ: {vendor}\n'
        f'Dátum: {match.issue_date}\n'
        f'Suma: {amount} {match.currency}\n'
        f'Predmet nákupu: {purchase_subject}\n\n'
        'Chcete nový doklad aj napriek tomu spracovať?\n'
        'Odpovedzte: áno / nie.'
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
