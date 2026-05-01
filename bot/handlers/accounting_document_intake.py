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
    save_confirmed_accounting_document,
    temp_staging_dir,
)
from bot.services.accounting_document_validation import validate_accounting_document_candidate
from bot.services.decision_resolver import resolve_approve_edit_cancel


router = Router()

_DECISION_CONTEXT = 'accounting_document_intake_preview'
_STATE_CANDIDATE_KEY = 'accounting_document_candidate'
_STATE_TEMP_ORIGINAL_KEY = 'accounting_document_temp_original_path'
_STATE_FILE_UNIQUE_ID_KEY = 'accounting_document_file_unique_id'
_STATE_EXTENSION_KEY = 'accounting_document_extension'


class AccountingDocumentIntakeStates(StatesGroup):
    waiting_upload = State()
    waiting_preview_decision = State()


@router.message(Command('doklad', 'expense', 'intake'))
async def cmd_accounting_document_intake(message: Message, state: FSMContext) -> None:
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

    file_unique_id = attachment['file_unique_id']
    staged_path = temp_staging_dir(config.storage_dir, file_unique_id) / f'original{attachment["extension"]}'
    staged_path.parent.mkdir(parents=True, exist_ok=True)

    telegram_file = await bot.get_file(attachment['file_id'])
    await bot.download_file(telegram_file.file_path, destination=staged_path)

    document_input = AccountingDocumentLmmInput(
        input_type=attachment['input_type'],
        original_filename=attachment['original_filename'],
        mime_type=attachment['mime_type'],
    )
    try:
        classification = await classify_accounting_document(
            document_input=document_input,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
        candidate = await extract_accounting_document_metadata(
            document_input=document_input,
            document_type_hint=classification.document_type,
            api_key=config.openai_api_key,
            model=config.openai_llm_model,
        )
    except AccountingDocumentLmmError:
        await message.answer('Doklad sa nepodarilo spracovať. Skúste ho poslať ešte raz v lepšej kvalite.')
        return
    except ValueError:
        await message.answer('Doklad sa nepodarilo bezpečne prečítať. Skúste ho poslať ešte raz.')
        return

    candidate = _with_upload_source(candidate, attachment)
    validation = validate_accounting_document_candidate(candidate)
    if not validation.can_save:
        await message.answer(_format_validation_failure(validation.errors))
        return

    await state.update_data(
        **{
            _STATE_CANDIDATE_KEY: candidate_to_metadata_dict(candidate),
            _STATE_TEMP_ORIGINAL_KEY: str(staged_path),
            _STATE_FILE_UNIQUE_ID_KEY: file_unique_id,
            _STATE_EXTENSION_KEY: attachment['extension'],
        }
    )
    await state.set_state(AccountingDocumentIntakeStates.waiting_preview_decision)
    await message.answer(_format_accounting_document_preview(candidate))


@router.message(AccountingDocumentIntakeStates.waiting_upload)
async def accounting_document_waiting_upload(message: Message) -> None:
    await message.answer('Pošlite, prosím, fotku alebo PDF bločka / prijatej faktúry.')


@router.message(AccountingDocumentIntakeStates.waiting_preview_decision)
async def accounting_document_preview_decision(message: Message, state: FSMContext, config: Config) -> None:
    decision = await resolve_approve_edit_cancel(
        context_name=_DECISION_CONTEXT,
        user_input_text=message.text or '',
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )

    if decision == 'unknown':
        await message.answer('Prosím, odpovedzte: schváliť, upraviť alebo zrušiť.')
        return

    if decision == 'edit':
        await message.answer(
            'Úprava polí zatiaľ nie je v tomto kroku implementovaná. '
            'Napíšte schváliť alebo zrušiť.'
        )
        return

    if decision == 'cancel':
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

    try:
        result = save_confirmed_accounting_document(
            storage_dir=config.storage_dir,
            source_path=Path(source_path_value),
            candidate=_candidate_from_state_payload(candidate_payload),
            file_unique_id=file_unique_id,
            extension=extension if isinstance(extension, str) else None,
        )
    except (AccountingDocumentStorageError, OSError, ValueError):
        await message.answer('Doklad sa nepodarilo uložiť. Skúste /doklad znova.')
        return

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

    return (
        'Náhľad dokladu\n'
        f'Typ: {document_type_label}\n'
        f'Dodávateľ: {candidate.vendor_name or "nezistené"}\n'
        f'Dátum: {date_value}\n'
        f'Suma: {amount_value} {currency_value}'.rstrip()
        + '\n'
        f'Platba: {payment_value}\n'
        'Kategória: nezaradené\n\n'
        'Schváliť, upraviť alebo zrušiť?'
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
        category_candidate=_optional_str(business.get('category_candidate')),
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
