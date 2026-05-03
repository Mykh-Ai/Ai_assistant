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
    'Profil dodávateľa je nastavený.\n\n'
    'Teraz si môžete pripraviť fakturáciu:\n'
    '1. Nastavte krátky názov služby cez /alias.\n'
    '   Môžete začať aj hlasom alebo textom: „dodaj novú službu“.\n'
    '   Potom napíšte krátky názov, napríklad „opravy“, a plný názov pre faktúru/PDF, napríklad '
    '„Opravy vyhradených zariadení elektrických“.\n'
    '2. Pridajte odberateľa cez /contact.\n'
    '   Môžete to spustiť aj hlasom alebo textom: „dodaj nový kontakt“.\n'
    '3. Potom vytvorte faktúru cez /invoice alebo ju jednoducho nadiktujte.'
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

