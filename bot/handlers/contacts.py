from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.contact_service import ContactProfile, ContactService
from bot.services.supplier_service import SupplierService
from bot.services.validation import validate_dic, validate_email, validate_ic_dph, validate_ico

router = Router(name='contacts')


class ContactStates(StatesGroup):
    name = State()
    ico = State()
    dic = State()
    ic_dph = State()
    address = State()
    email = State()
    contact_person = State()
    confirm = State()


def _summary(data: dict[str, str]) -> str:
    duplicate_note = ''
    if data.get('existing_match') == '1':
        duplicate_note = (
            '\n\nUpozornenie: kontakt s týmto presným názvom už existuje v profile dodávateľa. '
            'Potvrdením odpoveďou ano tento kontakt prepíšete.'
        )

    return (
        'Prehľad kontaktu\n\n'
        f'Názov: {data["name"]}\n'
        f'ICO: {data["ico"]}\n'
        f'DIC: {data["dic"]}\n'
        f'IC DPH: {data["ic_dph"] or "-"}\n'
        f'Adresa: {data["address"]}\n'
        f'Email: {data["email"]}\n'
        f'Kontaktná osoba: {data["contact_person"] or "-"}'
        f'{duplicate_note}\n\n'
        'Napíšte ano pre uloženie alebo nie pre zrušenie.'
    )


@router.message(Command('contact', 'contact_add'))
async def cmd_contact(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    supplier_service = SupplierService(config.db_path)
    if supplier_service.get_by_telegram_id(message.from_user.id) is None:
        await message.answer('Profil dodávateľa neexistuje. Najprv spustite /supplier a potom pridajte kontakt.')
        return

    existing_state = await state.get_state()
    if existing_state is not None:
        await message.answer('Flow kontaktu bol reštartovaný. Predchádzajúci draft bol zahodený.')

    await state.clear()
    await state.set_state(ContactStates.name)
    await message.answer('1/7 Zadajte názov firmy odberateľa:')


@router.message(ContactStates.name)
async def contact_name(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    value = (message.text or '').strip()
    if not value:
        await message.answer('Názov nemôže byť prázdny. Skúste znova:')
        return

    service = ContactService(config.db_path)
    existing = service.get_by_name(message.from_user.id, value)
    if existing is not None:
        await message.answer(
            'Kontakt s týmto presným názvom už existuje. '
            'Pokračujte a po potvrdení sa prepíše.'
        )

    await state.update_data(name=value, existing_match='1' if existing is not None else '0')
    await state.set_state(ContactStates.ico)
    await message.answer('2/7 Zadajte ICO (8 číslic):')


@router.message(ContactStates.ico)
async def contact_ico(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer('Neplatné ICO. Formát: 8 číslic. Skúste znova:')
        return
    await state.update_data(ico=value)
    await state.set_state(ContactStates.dic)
    await message.answer('3/7 Zadajte DIC (10 číslic):')


@router.message(ContactStates.dic)
async def contact_dic(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer('Neplatné DIC. Formát: 10 číslic. Skúste znova:')
        return
    await state.update_data(dic=value)
    await state.set_state(ContactStates.ic_dph)
    await message.answer('4/7 Zadajte IC DPH (voliteľné, pošlite "-"):')


@router.message(ContactStates.ic_dph)
async def contact_ic_dph(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if value == '-':
        await state.update_data(ic_dph='')
    else:
        if not validate_ic_dph(value):
            await message.answer('Neplatné IC DPH. Príklad: SK1234567890. Skúste znova:')
            return
        await state.update_data(ic_dph=value.upper().replace(' ', ''))

    await state.set_state(ContactStates.address)
    await message.answer('5/7 Zadajte adresu:')


@router.message(ContactStates.address)
async def contact_address(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Adresa nemôže byť prázdna. Skúste znova:')
        return
    await state.update_data(address=value)
    await state.set_state(ContactStates.email)
    await message.answer('6/7 Zadajte email:')


@router.message(ContactStates.email)
async def contact_email(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_email(value):
        await message.answer('Neplatný email. Skúste znova:')
        return
    await state.update_data(email=value)
    await state.set_state(ContactStates.contact_person)
    await message.answer('7/7 Zadajte kontaktnú osobu (voliteľné, pošlite "-"):')


@router.message(ContactStates.contact_person)
async def contact_person(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    await state.update_data(contact_person='' if value == '-' else value)

    data = await state.get_data()
    await state.set_state(ContactStates.confirm)
    await message.answer(_summary(data))


@router.message(ContactStates.confirm)
async def contact_confirm(message: Message, state: FSMContext, config: Config) -> None:
    answer = (message.text or '').strip().lower()
    if answer not in {'ano', 'nie'}:
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'nie':
        await state.clear()
        await message.answer('Vytvorenie kontaktu bolo zrušené. Pre nový pokus spustite /contact.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    service = ContactService(config.db_path)
    service.create_or_replace(
        ContactProfile(
            supplier_telegram_id=message.from_user.id,
            name=data['name'],
            ico=data['ico'],
            dic=data['dic'],
            ic_dph=data['ic_dph'] or None,
            address=data['address'],
            email=data['email'],
            contact_person=data['contact_person'] or None,
            source_type='manual',
            source_note=None,
            contract_path=None,
        )
    )

    await state.clear()
    await message.answer('Kontakt bol uložený.')
