import logging
import json
from uuid import uuid4

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.handlers.contacts import ContactStates, process_contact_intake_confirm, process_contact_missing_fields
from bot.handlers.invoice import (
    InvoiceStates,
    process_invoice_postpdf_decision,
    process_invoice_preview_confirmation,
    process_invoice_service_clarification,
    process_invoice_slot_clarification,
    process_invoice_text,
)
from bot.handlers.supplier import ServiceAliasStates
from bot.services.speech_to_text import transcribe_audio

router = Router(name='voice')
logger = logging.getLogger(__name__)


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot, config: Config, state: FSMContext) -> None:
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

        current_state = await state.get_state()
        if current_state == InvoiceStates.waiting_confirm.state:
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
        elif current_state == InvoiceStates.waiting_pdf_decision.state:
            await process_invoice_postpdf_decision(
                message=message,
                state=state,
                config=config,
                decision_text=recognized_text,
            )
        elif current_state == InvoiceStates.waiting_edit_item_target.state:
            await message.answer('V tomto kroku zadajte číslo položky textom (napr. 1).')
        elif current_state == InvoiceStates.waiting_edit_operation.state:
            await message.answer('V tomto kroku zadajte voľbu úpravy textom.')
        elif current_state == InvoiceStates.waiting_edit_service_value.state:
            await message.answer('Napíšte nový názov služby textom.')
        elif current_state == InvoiceStates.waiting_edit_description_value.state:
            await message.answer(
                'Pre finálny opis položky použite textový vstup. '
                'Napíšte opis textom alebo `vymaž opis`.'
            )
        elif current_state == ContactStates.intake_missing.state:
            await process_contact_missing_fields(
                message=message,
                state=state,
                user_text=recognized_text,
            )
        elif current_state == ContactStates.intake_confirm.state:
            await process_contact_intake_confirm(
                message=message,
                state=state,
                config=config,
                answer_text=recognized_text,
            )
        elif current_state == ContactStates.name_hint.state:
            await message.answer('V tomto kroku zadajte názov firmy textom.')
        elif current_state == ContactStates.source_after_name.state:
            await message.answer('V tomto kroku pošlite zmluvu/PDF alebo zadajte IČO textom.')
        elif current_state == ServiceAliasStates.waiting_short_name.state:
            await message.answer('Napíšte krátky názov položky textom.')
        elif current_state == ServiceAliasStates.waiting_display_name.state:
            await message.answer('Napíšte plný názov služby textom.')
        else:
            await process_invoice_text(
                message=message,
                state=state,
                config=config,
                invoice_text=recognized_text,
                request_id=request_id,
            )

    finally:
        voice_path.unlink(missing_ok=True)
