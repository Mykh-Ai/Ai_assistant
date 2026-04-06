from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierService

router = Router(name='supplier_service_alias')


class ServiceAliasStates(StatesGroup):
    waiting_alias = State()
    waiting_canonical = State()


def _mappings_preview(mappings: list[tuple[str, str]]) -> str:
    if not mappings:
        return 'Zatiaľ nemáte žiadne aliasy služieb.'

    lines = ['<b>Aktuálne aliasy služieb:</b>']
    for alias, canonical in mappings:
        lines.append(f'• <code>{alias}</code> → {canonical}')
    return '\n'.join(lines)


@router.message(Command('service'))
async def cmd_service(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None or supplier.id is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        return

    alias_service = ServiceAliasService(config.db_path)
    mappings = alias_service.list_mappings(supplier.id)

    await state.clear()
    await state.set_state(ServiceAliasStates.waiting_alias)
    await message.answer(
        _mappings_preview([(entry.alias, entry.canonical_title) for entry in mappings])
        + '\n\n'
        'Pridanie aliasu (krok 1/2): napíšte krátky alias služby.\n'
        'Príklad: <code>opravy</code>'
    )


@router.message(ServiceAliasStates.waiting_alias)
async def service_alias_input(message: Message, state: FSMContext) -> None:
    alias = (message.text or '').strip()
    if not alias:
        await message.answer('Alias nemôže byť prázdny. Skúste znova:')
        return

    await state.update_data(service_alias=alias)
    await state.set_state(ServiceAliasStates.waiting_canonical)
    await message.answer(
        'Krok 2/2: napíšte plný canonical názov služby, '
        'ktorý sa má použiť vo faktúre/PDF.'
    )


@router.message(ServiceAliasStates.waiting_canonical)
async def service_canonical_input(message: Message, state: FSMContext, config: Config) -> None:
    canonical_title = (message.text or '').strip()
    if not canonical_title:
        await message.answer('Canonical názov nemôže byť prázdny. Skúste znova:')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        await state.clear()
        return

    data = await state.get_data()
    alias = (data.get('service_alias') or '').strip()
    if not alias:
        await message.answer('Alias sa stratil zo stavu. Spustite /service znova.')
        await state.clear()
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None or supplier.id is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        await state.clear()
        return

    alias_service = ServiceAliasService(config.db_path)
    alias_service.create_mapping(supplier.id, alias, canonical_title)
    mappings = alias_service.list_mappings(supplier.id)

    await state.clear()
    await message.answer(
        'Alias služby bol uložený.\n\n'
        + _mappings_preview([(entry.alias, entry.canonical_title) for entry in mappings])
        + '\n\nPre ďalší alias spustite /service.'
    )
