import logging
import json
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.handlers.accounting_document_intake import (
    AccountingDocumentIntakeStates,
    handle_accounting_document_category_selection_text,
    handle_accounting_document_duplicate_decision_text,
    handle_accounting_document_line_item_selection_text,
    handle_accounting_document_new_category_confirm_text,
    handle_accounting_document_preview_decision_text,
    handle_accounting_document_similar_category_decision_text,
    handle_accounting_document_unknown_category_decision_text,
)
from bot.handlers.access_admin import (
    CustomizationRequestAdminResponseStates,
    customization_request_response_preview_decision,
)
from bot.handlers.contacts import ContactStates, contact_confirm, process_contact_intake_confirm
from bot.handlers.delete_user_database import DeleteUserDatabaseStates, VOICE_EXACT_CONFIRMATION_MESSAGE
from bot.handlers.invoice import (
    CustomizationRequestStates,
    InvoiceStates,
    customization_request_preview_decision,
    invoice_delete_existing_invoice_confirm,
    invoice_mark_existing_invoice_paid_confirm,
    invoice_edit_invoice_action,
    invoice_edit_invoice_date_value,
    invoice_edit_item_action,
    invoice_edit_item_target,
    invoice_edit_scope,
    invoice_edit_service_value,
    process_invoice_customer_alias_confirm,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    process_invoice_service_clarification,
    process_invoice_slot_clarification,
    process_invoice_text,
)
from bot.handlers.onboarding import (
    OnboardingStates,
    SupplierProfileEditStates,
    onboarding_confirm,
    supplier_profile_edit_confirm,
    supplier_profile_edit_field,
)
from bot.handlers.officeflow_attachment_router import (
    OfficeFlowAttachmentRouterStates,
    handle_officeflow_accounting_proposal_text,
    handle_officeflow_route_choice_text,
    handle_officeflow_unknown_clarification_text,
)
from bot.handlers.state_control import cancel_current_state
from bot.handlers.work_time import (
    WorkTimeStates,
    work_time_close_input,
    work_time_close_preview_confirm,
    work_time_manual_range_confirm,
    work_time_manual_range_input,
    work_time_missing_days_choice,
    work_time_open_day_conflict_choice,
)
from bot.handlers.supplier import ServiceAliasStates
from bot.services.decision_resolver import is_global_cancel_text, resolve_global_cancel
from bot.services.speech_to_text import transcribe_audio

router = Router(name='voice')
logger = logging.getLogger(__name__)


def _inject_recognized_text(message: Message, recognized_text: str):
    async def _noop_answer_document(*args, **kwargs) -> None:
        return None

    return type(
        'VoiceTextMessage',
        (),
        {
            'text': recognized_text,
            'answer': message.answer,
            'answer_document': getattr(message, 'answer_document', _noop_answer_document),
            'from_user': getattr(message, 'from_user', None),
        },
    )()


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot, config: Config, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state == DeleteUserDatabaseStates.waiting_exact_confirmation.state:
        await message.answer(VOICE_EXACT_CONFIRMATION_MESSAGE)
        return

    if not config.openai_api_key:
        await message.answer(
            'Bot nie je nakonfigurovaný: chýba OPENAI_API_KEY.\n'
            'Obráťte sa na administrátora.'
        )
        return

    assert message.voice is not None

    uploads_dir = config.storage_dir / 'uploads'
    voice_path = uploads_dir / f'{message.voice.file_id}.ogg'

    try:
        file = await bot.get_file(message.voice.file_id)
        await bot.download_file(file.file_path, destination=voice_path)

        try:
            request_id = str(uuid4())
            recognized_text = await transcribe_audio(
                voice_path, config.openai_api_key, config.openai_stt_model
            )
            if config.debug_invoice_transparency:
                logger.info(
                    json.dumps(
                        {
                            'event': 'invoice_stt_result',
                            'request_id': request_id,
                            'telegram_update_id': getattr(message, 'update_id', None),
                            'telegram_message_id': getattr(message, 'message_id', None),
                            'stt_text': recognized_text,
                        },
                        ensure_ascii=False,
                    )
                )
        except Exception:
            logger.exception('STT failed')
            await message.answer('Nepodarilo sa rozpoznať hlasovú správu. Skúste znova.')
            return

        if not recognized_text.strip():
            await message.answer('Nepodarilo sa rozpoznať obsah hlasovej správy. Skúste znova.')
            return

        if current_state is not None:
            if is_global_cancel_text(recognized_text):
                await cancel_current_state(message=message, state=state, config=config)
                return
            cancel_decision = await resolve_global_cancel(
                context_name='global_state_cancel',
                user_input_text=recognized_text,
                api_key=config.openai_api_key,
                model=config.openai_llm_model,
            )
            if cancel_decision == 'cancel':
                await cancel_current_state(message=message, state=state, config=config)
                return

        text_message = _inject_recognized_text(message, recognized_text)
        if current_state == InvoiceStates.waiting_input.state:
            await process_invoice_text(
                message=message,
                state=state,
                config=config,
                invoice_text=recognized_text,
                request_id=request_id,
                input_channel='voice',
            )
        elif current_state == InvoiceStates.waiting_confirm.state:
            if config.debug_invoice_transparency:
                logger.info(
                    json.dumps(
                        {
                            'event': 'confirm_voice_routing',
                            'request_id': request_id,
                            'current_state': current_state,
                            'recognized_text': recognized_text,
                            'telegram_message_id': getattr(message, 'message_id', None),
                        },
                        ensure_ascii=False,
                    )
                )
            await process_invoice_preview_confirmation(
                message=message,
                state=state,
                config=config,
                confirmation_text=recognized_text,
            )
        elif current_state == InvoiceStates.waiting_service_clarification.state:
            await process_invoice_service_clarification(
                message=message,
                state=state,
                config=config,
                clarification_text=recognized_text,
            )
        elif current_state == InvoiceStates.waiting_slot_clarification.state:
            await process_invoice_slot_clarification(
                message=message,
                state=state,
                config=config,
                clarification_text=recognized_text,
            )
        elif current_state == InvoiceStates.waiting_customer_alias_confirm.state:
            await process_invoice_customer_alias_confirm(
                message=text_message,
                state=state,
                config=config,
                answer_text=recognized_text,
            )
        elif current_state == InvoiceStates.waiting_pdf_decision.state:
            if config.debug_invoice_transparency:
                logger.info(
                    json.dumps(
                        {
                            'event': 'approval_voice_routing',
                            'request_id': request_id,
                            'current_state': current_state,
                            'recognized_text': recognized_text,
                            'telegram_message_id': getattr(message, 'message_id', None),
                        },
                        ensure_ascii=False,
                    )
                )
            await process_invoice_postpdf_decision(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == InvoiceStates.waiting_delete_existing_invoice_confirm.state:
            await invoice_delete_existing_invoice_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_mark_existing_invoice_paid_confirm.state:
            await invoice_mark_existing_invoice_paid_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_scope.state:
            await invoice_edit_scope(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_invoice_action.state:
            await invoice_edit_invoice_action(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_item_target.state:
            await invoice_edit_item_target(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_item_action.state:
            await invoice_edit_item_action(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_service_value.state:
            await invoice_edit_service_value(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_invoice_number_value.state:
            await message.answer('Číslo faktúry prosím zadajte textom vo formáte RRRRNNNN.')
        elif current_state == InvoiceStates.waiting_edit_invoice_date_value.state:
            await invoice_edit_invoice_date_value(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == InvoiceStates.waiting_edit_description_value.state:
            await message.answer(
                'Pre finálny opis položky použite textový vstup. '
                'Napíšte opis textom alebo `vymaž opis`.'
            )
        elif current_state == ContactStates.intake_missing.state:
            await message.answer('V tomto kroku prosím doplňte chýbajúci údaj textom.')
        elif current_state == ContactStates.intake_confirm.state:
            await process_contact_intake_confirm(
                message=message,
                state=state,
                config=config,
                answer_text=recognized_text,
            )
        elif current_state == ContactStates.confirm.state:
            await contact_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == OnboardingStates.confirm.state:
            await onboarding_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == SupplierProfileEditStates.field.state:
            await supplier_profile_edit_field(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == SupplierProfileEditStates.confirm.state:
            await supplier_profile_edit_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == OfficeFlowAttachmentRouterStates.accounting_proposal.state:
            await handle_officeflow_accounting_proposal_text(
                message=message,
                state=state,
                config=config,
                answer_text=recognized_text,
            )
        elif current_state == OfficeFlowAttachmentRouterStates.route_choice.state:
            await handle_officeflow_route_choice_text(
                message=message,
                state=state,
                config=config,
                answer_text=recognized_text,
            )
        elif current_state == OfficeFlowAttachmentRouterStates.unknown_clarification.state:
            await handle_officeflow_unknown_clarification_text(
                message=message,
                state=state,
                config=config,
                answer_text=recognized_text,
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_preview_decision.state:
            await handle_accounting_document_preview_decision_text(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_duplicate_decision.state:
            await handle_accounting_document_duplicate_decision_text(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_unknown_category_decision.state:
            await handle_accounting_document_unknown_category_decision_text(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_document_category_selection.state:
            await handle_accounting_document_category_selection_text(
                message=message,
                state=state,
                config=config,
                selection_text=recognized_text,
                target='document',
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_line_item_selection.state:
            await handle_accounting_document_line_item_selection_text(
                message=message,
                state=state,
                config=config,
                selection_text=recognized_text,
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_line_item_category_selection.state:
            await handle_accounting_document_category_selection_text(
                message=message,
                state=state,
                config=config,
                selection_text=recognized_text,
                target='line_item',
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_new_category_label.state:
            await message.answer('Názov novej kategórie prosím napíšte textom.')
        elif current_state == AccountingDocumentIntakeStates.waiting_new_category_confirm.state:
            await handle_accounting_document_new_category_confirm_text(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == AccountingDocumentIntakeStates.waiting_similar_category_decision.state:
            await handle_accounting_document_similar_category_decision_text(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == WorkTimeStates.waiting_manual_range_input.state:
            await work_time_manual_range_input(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == WorkTimeStates.waiting_manual_range_confirm.state:
            await work_time_manual_range_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == WorkTimeStates.waiting_close_input.state:
            await work_time_close_input(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == WorkTimeStates.waiting_close_preview_confirm.state:
            await work_time_close_preview_confirm(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == WorkTimeStates.waiting_open_day_conflict_choice.state:
            await work_time_open_day_conflict_choice(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == WorkTimeStates.waiting_missing_days_choice.state:
            await work_time_missing_days_choice(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == CustomizationRequestStates.waiting_preview_decision.state:
            await customization_request_preview_decision(
                message=text_message,
                state=state,
                config=config,
            )
        elif current_state == CustomizationRequestStates.waiting_edit_text.state:
            await message.answer('Upraven\u00fd n\u00e1zov alebo zhrnutie po\u017eiadavky pros\u00edm nap\u00ed\u0161te textom.')
        elif current_state == CustomizationRequestAdminResponseStates.waiting_response_text.state:
            await message.answer('Odpove\u010f pre pou\u017e\u00edvate\u013ea pros\u00edm nap\u00ed\u0161te textom.')
        elif current_state == CustomizationRequestAdminResponseStates.waiting_response_preview_decision.state:
            await customization_request_response_preview_decision(
                message=text_message,
                state=state,
                config=config,
                bot=bot,
            )
        elif _is_officeflow_attachment_state(current_state):
            await message.answer('Hlasovu odpoved v tomto kroku zatial neviem spracovat. Odpovedzte, prosim, textom.')
        elif current_state == ContactStates.name_hint.state:
            await message.answer('V tomto kroku zadajte názov firmy textom.')
        elif current_state == ContactStates.source_after_name.state:
            await message.answer('V tomto kroku pošlite zmluvu/PDF alebo zadajte IČO textom.')
        elif current_state == ServiceAliasStates.waiting_short_name.state:
            await message.answer('Napíšte krátky názov položky textom.')
        elif current_state == ServiceAliasStates.waiting_display_name.state:
            await message.answer('Napíšte plný názov služby textom.')
        elif current_state is not None:
            await message.answer('V tomto kroku prosím zadajte hodnotu textom.')
        else:
            await process_invoice_text(
                message=message,
                state=state,
                config=config,
                invoice_text=recognized_text,
                request_id=request_id,
                input_channel='voice',
            )

    finally:
        voice_path.unlink(missing_ok=True)


def _is_officeflow_attachment_state(current_state: str | None) -> bool:
    return bool(current_state and current_state.startswith(f'{OfficeFlowAttachmentRouterStates.__name__}:'))
