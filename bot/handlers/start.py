from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.config import Config
from bot.services.contact_service import ContactService
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierService

router = Router(name='start')

APPROVED_ACCESS_NEXT_STEP_MESSAGE = (
    'Váš prístup k FakturaBot bol schválený.\n\n'
    'Vaša pracovná databáza vo FakturaBot je pripravená.\n'
    'Kedykoľvek ju môžete úplne vymazať príkazom /vymazat_databazu '
    'alebo hlasom, napríklad: „Chcem vymazať moju databázu“.\n\n'
    'Ste pripravený pokračovať? Stlačte /start.'
)

READY_WITH_SUPPLIER_MESSAGE = (
    'FakturaBot je pripravený.\n\n'
    'Profil dodávateľa je nastavený.\n\n'
    'Ďalší krok: vytvorte si prvú službu cez /sluzbu.'
)

APPROVED_WITHOUT_SUPPLIER_MESSAGE = (
    'Ďalší krok: vytvorte si profil dodávateľa cez /moj_profil.'
)

READY_WITH_SERVICE_MESSAGE = (
    'FakturaBot je pripravený.\n\n'
    'Profil a prvá služba sú nastavené.\n\n'
    'Ďalší krok: pridajte prvého odberateľa cez /contact.'
)

ADVANCED_START_MESSAGE = (
    'FakturaBot je pripravený.\n\n'
    'Čo chcete urobiť?\n\n'
    '• /invoice — vytvoriť faktúru\n'
    '• Zobraziť faktúru — napíšte alebo povedzte: "zobraz faktúru 04"\n'
    '• Upraviť faktúru — napíšte alebo povedzte: "uprav faktúru 04"\n'
    '• /add_blocek — dodať bloček\n'
    '• /blocek — posledné bločky\n'
    '• /upravit_profil — upraviť profil\n'
    '• /moj_profil — zobraziť profil'
)

MENU_MESSAGE = (
    'Všetky používateľské možnosti:\n\n'
    'Faktúry:\n'
    '• /invoice — vytvoriť faktúru\n'
    '• Zobraziť faktúru — napíšte alebo povedzte: "zobraz faktúru 04"\n'
    '• Upraviť faktúru — napíšte alebo povedzte: "uprav faktúru 04"\n'
    '• Vymazať faktúru — napíšte alebo povedzte: "vymaž faktúru 04"\n\n'
    'Nastavenia:\n'
    '• /sluzbu — pridať službu\n'
    '• /contact — pridať odberateľa\n'
    '• /moj_profil — zobraziť profil\n'
    '• /upravit_profil — upraviť profil\n\n'
    'Bločky a doklady:\n'
    '• /add_blocek — dodať bloček\n'
    '• /blocek — posledné bločky\n\n'
    'Dáta a prístup:\n'
    '• /vymazat_databazu — vymazať moje dáta a odobrať prístup k botu'
)


def build_start_status_message(config: Config, telegram_id: int) -> str:
    supplier = SupplierService(config.db_path).get_by_telegram_id(telegram_id)
    if supplier is None:
        return APPROVED_WITHOUT_SUPPLIER_MESSAGE

    if supplier.id is None or not ServiceAliasService(config.db_path).list_mappings(supplier.id):
        return READY_WITH_SUPPLIER_MESSAGE

    if not ContactService(config.db_path).get_all_by_supplier(telegram_id):
        return READY_WITH_SERVICE_MESSAGE

    return ADVANCED_START_MESSAGE


@router.message(CommandStart())
async def cmd_start(message: Message, config: Config, state: FSMContext | None = None) -> None:
    if state is not None:
        await state.clear()
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    await message.answer(build_start_status_message(config, message.from_user.id))


@router.message(lambda message: _command_token(message.text or '') == '/menu')
async def cmd_menu(message: Message, config: Config, state: FSMContext | None = None) -> None:
    _ = config
    if state is not None:
        await state.clear()
    await message.answer(MENU_MESSAGE)


@router.message(lambda message: _is_case_variant_command(message.text or '', '/start'))
async def cmd_start_case_alias(message: Message, config: Config, state: FSMContext | None = None) -> None:
    await cmd_start(message, config, state)


def _command_token(text: str) -> str:
    if not text.strip().startswith('/'):
        return ''
    return text.strip().split(maxsplit=1)[0].split('@', 1)[0].lower()


def _is_case_variant_command(text: str, command: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith('/'):
        return False
    raw_token = stripped.split(maxsplit=1)[0].split('@', 1)[0]
    return raw_token != command and raw_token.lower() == command

