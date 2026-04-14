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
    waiting_short_name = State()
    waiting_display_name = State()


def _mappings_preview(mappings: list[tuple[str, str]]) -> str:
    if not mappings:
        return 'Zatiaľ nemáte žiadne názvy služieb.'

    lines = ['<b>Aktuálne názvy služieb:</b>']
    for service_short_name, service_display_name in mappings:
        lines.append(f'• <code>{service_short_name}</code> → {service_display_name}')
    return '\n'.join(lines)


async def start_add_service_alias_intake(message: Message, state: FSMContext, config: Config) -> None:
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
    await state.set_state(ServiceAliasStates.waiting_short_name)
    await message.answer(
        _mappings_preview([(entry.service_short_name, entry.service_display_name) for entry in mappings])
        + '\n\n'
        'Pridanie názvu služby (krok 1/2): napíšte krátky názov služby.\n'
        'Príklad: <code>opravy</code>'
    )


@router.message(Command('service'))
async def cmd_service(message: Message, state: FSMContext, config: Config) -> None:
    await start_add_service_alias_intake(message=message, state=state, config=config)


@router.message(ServiceAliasStates.waiting_short_name)
async def service_short_name_input(message: Message, state: FSMContext) -> None:
    service_short_name = (message.text or '').strip()
    if not service_short_name:
        await message.answer('Krátky názov služby nemôže byť prázdny. Skúste znova:')
        return

    await state.update_data(service_short_name=service_short_name)
    await state.set_state(ServiceAliasStates.waiting_display_name)
    await message.answer(
        'Krok 2/2: napíšte plný názov služby, '
        'ktorý sa má použiť vo faktúre/PDF.'
    )


@router.message(ServiceAliasStates.waiting_display_name)
async def service_display_name_input(message: Message, state: FSMContext, config: Config) -> None:
    service_display_name = (message.text or '').strip()
    if not service_display_name:
        await message.answer('Plný názov služby nemôže byť prázdny. Skúste znova:')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        await state.clear()
        return

    data = await state.get_data()
    service_short_name = (data.get('service_short_name') or '').strip()
    if not service_short_name:
        await message.answer('Krátky názov služby sa stratil zo stavu. Spustite /service znova.')
        await state.clear()
        return

    supplier = SupplierService(config.db_path).get_by_telegram_id(message.from_user.id)
    if supplier is None or supplier.id is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier.')
        await state.clear()
        return

    alias_service = ServiceAliasService(config.db_path)
    alias_service.create_mapping(supplier.id, service_short_name, service_display_name)
    mappings = alias_service.list_mappings(supplier.id)

    await state.clear()
    await message.answer(
        'Názov služby bol uložený.\n\n'
        + _mappings_preview([(entry.service_short_name, entry.service_display_name) for entry in mappings])
        + '\n\nPre ďalší názov služby spustite /service.'
    )
