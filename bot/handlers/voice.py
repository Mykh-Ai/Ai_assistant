import logging

from aiogram import Bot, F, Router
from aiogram.types import Message

from bot.config import Config
from bot.services.llm_invoice_parser import parse_invoice_draft
from bot.services.speech_to_text import transcribe_audio

router = Router(name='voice')
logger = logging.getLogger(__name__)


def _format_preview(recognized_text: str, draft: dict) -> str:
    def val(v: object) -> str:
        return str(v) if v is not None else '—'

    def pair(a: object, b: object) -> str:
        if a is not None and b is not None:
            return f'{a} {b}'
        if a is not None:
            return str(a)
        if b is not None:
            return str(b)
        return '—'

    due = f"{draft['due_days']} днів" if draft['due_days'] is not None else '—'

    return (
        f'🎙 <b>Розпізнаний текст:</b>\n'
        f'{recognized_text}\n\n'
        f'📋 <b>Ось що я зрозумів:</b>\n'
        f'• Контрагент: {val(draft["customer_name"])}\n'
        f'• Позиція: {val(draft["item_name_raw"])}\n'
        f'• Кількість: {pair(draft["quantity"], draft["unit"])}\n'
        f'• Сума: {pair(draft["amount"], draft["currency"])}\n'
        f'• Дата виставлення: {val(draft["issue_date"])}\n'
        f'• Сплатність: {due}'
    )


@router.message(F.voice)
async def handle_voice(message: Message, bot: Bot, config: Config) -> None:
    if not config.openai_api_key:
        await message.answer(
            'Бот не налаштовано: відсутній OPENAI_API_KEY.\n'
            'Зверніться до адміністратора.'
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
            await message.answer('Не вдалося розпізнати голосове повідомлення. Спробуйте ще раз.')
            return

        if not recognized_text.strip():
            await message.answer('Не вдалося розпізнати зміст голосового повідомлення. Спробуйте ще раз.')
            return

        try:
            draft = await parse_invoice_draft(
                recognized_text, config.openai_api_key, config.openai_llm_model
            )
        except Exception:
            logger.exception('LLM parsing failed')
            await message.answer('Не вдалося розібрати фактуру. Спробуйте ще раз.')
            return

        await message.answer(_format_preview(recognized_text, draft))

    finally:
        voice_path.unlink(missing_ok=True)
