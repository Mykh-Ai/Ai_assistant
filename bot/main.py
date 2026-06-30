import logging
import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_config
from bot.handlers import routers
from bot.services.authorization import TelegramUserAuthorizationMiddleware
from bot.services.db import init_db
from bot.services.google_drive_archive_scheduler import run_google_drive_archive_scheduler
from bot.services.invoice_followup_scheduler import run_invoice_followup_scheduler


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    config = load_config()
    init_db(config.db_path)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(TelegramUserAuthorizationMiddleware())
    dp.callback_query.outer_middleware(TelegramUserAuthorizationMiddleware())

    for router in routers:
        dp.include_router(router)

    logging.info('FakturaBot starting')
    invoice_followup_task = asyncio.create_task(
        run_invoice_followup_scheduler(bot=bot, config=config),
        name='invoice_followup_scheduler',
    )
    google_drive_archive_task = asyncio.create_task(
        run_google_drive_archive_scheduler(config=config),
        name='google_drive_archive_scheduler',
    )
    try:
        await dp.start_polling(bot, config=config)
    finally:
        for task in (invoice_followup_task, google_drive_archive_task):
            task.cancel()
        for task in (invoice_followup_task, google_drive_archive_task):
            with suppress(asyncio.CancelledError):
                await task


if __name__ == '__main__':
    asyncio.run(main())
