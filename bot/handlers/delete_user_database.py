from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.authorization import UNAUTHORIZED_MESSAGE, is_authorized_telegram_user
from bot.services.user_data_deletion import UserDataDeletionService


router = Router(name='delete_user_database')

DELETE_USER_DATABASE_INTENT = 'delete_user_database'
EXACT_DELETE_DATABASE_CONFIRMATION = 'vymazať databázu'
VOICE_EXACT_CONFIRMATION_MESSAGE = (
    'Pre bezpečnosť napíšte potvrdenie presne textom: vymazať databázu.'
)
DELETE_USER_DATABASE_WARNING = (
    'Ak vymažete databázu, natrvalo odstránite svoje pracovné údaje vo FakturaBot '
    'a stratíte prístup k botu.\n\n'
    'Nové pripojenie bude možné iba po opätovnom schválení administrátorom.\n\n'
    'Pre potvrdenie napíšte presne:\n'
    f'{EXACT_DELETE_DATABASE_CONFIRMATION}'
)
DELETE_USER_DATABASE_DONE_MESSAGE = (
    'Databáza bola vymazaná a prístup k FakturaBot bol odstránený.\n\n'
    'Ak budete chcieť FakturaBot používať znova, pošlite /start a počkajte na nové '
    'schválenie administrátorom.'
)
DELETE_USER_DATABASE_PARTIAL_FILES_MESSAGE = (
    'Databáza bola vymazaná a prístup k FakturaBot bol odstránený.\n\n'
    'Niektoré lokálne súbory sa nepodarilo odstrániť automaticky. Administrátor ich musí skontrolovať.'
)


class DeleteUserDatabaseStates(StatesGroup):
    waiting_exact_confirmation = State()


@router.message(Command('vymazat_databazu'))
async def cmd_vymazat_databazu(message: Message, state: FSMContext, config: Config) -> None:
    await start_delete_user_database_flow(message=message, state=state, config=config)


async def start_delete_user_database_flow(*, message: Message, state: FSMContext, config: Config) -> None:
    telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return
    if not is_authorized_telegram_user(config, telegram_id):
        await message.answer(UNAUTHORIZED_MESSAGE)
        return

    await state.set_state(DeleteUserDatabaseStates.waiting_exact_confirmation)
    await message.answer(DELETE_USER_DATABASE_WARNING)


@router.message(DeleteUserDatabaseStates.waiting_exact_confirmation)
async def confirm_delete_user_database(message: Message, state: FSMContext, config: Config) -> None:
    telegram_id = getattr(getattr(message, 'from_user', None), 'id', None)
    if telegram_id is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    if (message.text or '').strip() != EXACT_DELETE_DATABASE_CONFIRMATION:
        await message.answer(
            'Potvrdenie nesúhlasí. Pre vymazanie databázy napíšte presne:\n'
            f'{EXACT_DELETE_DATABASE_CONFIRMATION}'
        )
        return

    result = UserDataDeletionService(config.db_path, config.storage_dir).delete_user_database(telegram_id=telegram_id)
    await state.clear()
    if result.filesystem_errors:
        await message.answer(DELETE_USER_DATABASE_PARTIAL_FILES_MESSAGE)
        return
    await message.answer(DELETE_USER_DATABASE_DONE_MESSAGE)
