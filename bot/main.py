import logging
import asyncio
from contextlib import suppress

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import load_config
from bot.handlers import routers
from bot.services.active_fsm_guard import ActiveFsmMessageMiddleware
from bot.services.authorization import TelegramUserAuthorizationMiddleware
from bot.services.db import init_db
from bot.services.google_drive_archive_scheduler import run_google_drive_archive_scheduler
from bot.services.google_gmail_config import load_google_gmail_config
from bot.services.gmail_statement_scheduler import run_gmail_statement_scheduler
from bot.services.google_integration_callback_runner import run_google_integration_callback
from bot.services.invoice_followup_scheduler import run_invoice_followup_scheduler
from bot.services.contact_registry_monitor import (
    run_contact_registry_monitor_scheduler,
)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    config = load_config()
    gmail_config = load_google_gmail_config()
    init_db(config.db_path)

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()
    dp.message.outer_middleware(TelegramUserAuthorizationMiddleware())
    dp.message.outer_middleware(ActiveFsmMessageMiddleware())
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
    contact_registry_monitor_task = asyncio.create_task(
        run_contact_registry_monitor_scheduler(bot=bot, config=config),
        name='contact_registry_monitor_scheduler',
    )
    background_tasks = [
        invoice_followup_task,
        google_drive_archive_task,
        contact_registry_monitor_task,
    ]
    if gmail_config.enabled:
        background_tasks.append(asyncio.create_task(
            run_gmail_statement_scheduler(bot=bot, config=config),
            name='gmail_statement_scheduler',
        ))
    if gmail_config.enabled and gmail_config.callback_enabled:
        background_tasks.append(asyncio.create_task(
            run_google_integration_callback(
                bot=bot, config=config, gmail=gmail_config
            ),
            name='google_integration_callback',
        ))
    try:
        await dp.start_polling(bot, config=config)
    finally:
        for task in background_tasks:
            task.cancel()
        for task in background_tasks:
            with suppress(asyncio.CancelledError):
                await task


if __name__ == '__main__':
    asyncio.run(main())
