from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.service_alias_service import ServiceAliasService
from bot.services.supplier_service import SupplierService
from bot.services.workspace_context import WorkspaceContextError, WorkspaceContextService

router = Router(name='supplier_service_alias')

_SERVICE_ALIAS_WORKSPACE_ID_KEY = 'service_alias_workspace_id'

SERVICE_ALIAS_RECOVERY_HINT = 'Ak nechcete pridať službu, napíšte „zrušiť“.'


class ServiceAliasStates(StatesGroup):
    waiting_short_name = State()
    waiting_display_name = State()


def _is_case_variant_command(text: str, command: str) -> bool:
    stripped = text.strip()
    if not stripped.startswith('/'):
        return False
    raw_token = stripped.split(maxsplit=1)[0].split('@', 1)[0]
    return raw_token != command and raw_token.lower() == command


def _mappings_preview(mappings: list[tuple[str, str]]) -> str:
    if not mappings:
        return 'Zatiaľ nemáte žiadne názvy služieb.'

    lines = ['<b>Aktuálne názvy služieb:</b>']
    for service_short_name, service_display_name in mappings:
        lines.append(f'• <code>{service_short_name}</code> → {service_display_name}')
    return '\n'.join(lines)


def _supplier_for_workspace_flow(
    *,
    config: Config,
    telegram_id: int,
    workspace_id: str | None = None,
):
    if workspace_id:
        context = WorkspaceContextService(config.db_path).require_membership(
            telegram_id,
            workspace_id,
        )
        return SupplierService(config.db_path).get_by_workspace_id(context.workspace_id), context
    try:
        context = WorkspaceContextService(config.db_path).resolve_for_user(telegram_id)
    except WorkspaceContextError as workspace_error:
        try:
            supplier = SupplierService(config.db_path).get_by_telegram_id(telegram_id)
        except RuntimeError:
            raise workspace_error
        if supplier is None or supplier.workspace_id is None:
            return supplier, None
        raise workspace_error
    return SupplierService(config.db_path).get_by_workspace_id(context.workspace_id), context

async def start_add_service_alias_intake(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    try:
        supplier, context = _supplier_for_workspace_flow(
            config=config,
            telegram_id=message.from_user.id,
        )
    except WorkspaceContextError:
        await message.answer('Vyberte aktívny business profil cez /profily.')
        return
    if supplier is None or supplier.id is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /moj_profil.')
        return

    alias_service = ServiceAliasService(config.db_path)
    mappings = alias_service.list_mappings(supplier.id)

    await state.clear()
    await state.update_data(
        **{_SERVICE_ALIAS_WORKSPACE_ID_KEY: context.workspace_id if context is not None else ''}
    )
    await state.set_state(ServiceAliasStates.waiting_short_name)
    await message.answer(
        _mappings_preview([(entry.service_short_name, entry.service_display_name) for entry in mappings])
        + '\n\n'
        'Pridanie názvu služby (krok 1/2): napíšte krátky názov služby.\n'
        'Príklad: <code>opravy</code>'
    )


@router.message(Command('service', 'alias', 'sluzbu'))
async def cmd_service(message: Message, state: FSMContext, config: Config) -> None:
    await start_add_service_alias_intake(message=message, state=state, config=config)


@router.message(lambda message: _is_case_variant_command(message.text or '', '/sluzbu'))
async def cmd_sluzbu_case_alias(message: Message, state: FSMContext, config: Config) -> None:
    await start_add_service_alias_intake(message=message, state=state, config=config)


@router.message(ServiceAliasStates.waiting_short_name)
async def service_short_name_input(message: Message, state: FSMContext) -> None:
    service_short_name = (message.text or '').strip()
    if not service_short_name:
        await message.answer(
            'Krátky názov služby nemôže byť prázdny. Skúste znova:\n\n'
            f'{SERVICE_ALIAS_RECOVERY_HINT}'
        )
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
        await message.answer(
            'Plný názov služby nemôže byť prázdny. Skúste znova:\n\n'
            f'{SERVICE_ALIAS_RECOVERY_HINT}'
        )
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        await state.clear()
        return

    data = await state.get_data()
    service_short_name = (data.get('service_short_name') or '').strip()
    if not service_short_name:
        await message.answer('Krátky názov služby sa stratil zo stavu. Spustite /sluzbu znova.')
        await state.clear()
        return

    workspace_id = str(data.get(_SERVICE_ALIAS_WORKSPACE_ID_KEY) or '').strip() or None
    try:
        supplier, _context = _supplier_for_workspace_flow(
            config=config,
            telegram_id=message.from_user.id,
            workspace_id=workspace_id,
        )
    except WorkspaceContextError:
        await message.answer('Business profil tejto služby už nie je dostupný.')
        await state.clear()
        return
    if supplier is None or supplier.id is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /moj_profil.')
        await state.clear()
        return

    alias_service = ServiceAliasService(config.db_path)
    alias_service.create_mapping(supplier.id, service_short_name, service_display_name)
    mappings = alias_service.list_mappings(supplier.id)

    await state.clear()
    await message.answer(
        'Názov služby bol uložený.\n\n'
        + _mappings_preview([(entry.service_short_name, entry.service_display_name) for entry in mappings])
        + '\n\nPre ďalší názov služby spustite /sluzbu.'
    )
