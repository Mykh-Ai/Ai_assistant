import logging

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.handlers.invoice import process_invoice_text
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
            recognized_text = await transcribe_audio(
                voice_path, config.openai_api_key, config.openai_stt_model
            )
        except Exception:
            logger.exception('STT failed')
            await message.answer('Nepodarilo sa rozpoznať hlasovú správu. Skúste znova.')
            return

        if not recognized_text.strip():
            await message.answer('Nepodarilo sa rozpoznať obsah hlasovej správy. Skúste znova.')
            return

        await process_invoice_text(
            message=message,
            state=state,
            config=config,
            invoice_text=recognized_text,
        )

    finally:
        voice_path.unlink(missing_ok=True)
