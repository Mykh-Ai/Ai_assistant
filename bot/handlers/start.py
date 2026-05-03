from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.config import Config
from bot.services.supplier_service import SupplierService

router = Router(name='start')

APPROVED_ACCESS_NEXT_STEP_MESSAGE = (
    'Váš prístup k FakturaBot bol schválený.\n\n'
    'FakturaBot je pripravený na nastavenie profilu dodávateľa.\n'
    'Keď budete pripravený zadať registračné údaje dodávateľa, spustite /supplier.\n\n'
    'Bez profilu dodávateľa ešte nie je možné vytvárať faktúry.'
)

READY_WITH_SUPPLIER_MESSAGE = (
    'FakturaBot je pripravený.\n\n'
    'Profil dodávateľa je nastavený. Môžete vytvárať faktúry hlasom alebo textom.'
)


@router.message(CommandStart())
async def cmd_start(message: Message, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None:
        await message.answer(APPROVED_ACCESS_NEXT_STEP_MESSAGE)
        return

    await message.answer(READY_WITH_SUPPLIER_MESSAGE)

