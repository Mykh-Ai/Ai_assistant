from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name='start')


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        'FakturaBot je spustený.\n\n'
        'Aktuálne je pripravený základ aplikácie, konfigurácia, SQLite bootstrap a príkaz /start.\n'
        'Ďalšie fázy: onboarding, voice-to-draft a faktúry.'
    )

