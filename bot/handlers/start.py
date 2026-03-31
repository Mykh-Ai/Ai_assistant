from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

router = Router(name='start')


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        'FakturaBot skeleton is running.\n\n'
        'Available now: basic startup, config, SQLite bootstrap, and /start.\n'
        'Next phases: onboarding, voice-to-draft, invoices.'
    )
