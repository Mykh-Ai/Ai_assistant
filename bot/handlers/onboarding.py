from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.validation import (
    validate_days_due,
    validate_dic,
    validate_email,
    validate_iban,
    validate_ic_dph,
    validate_ico,
)

router = Router(name='onboarding')


class OnboardingStates(StatesGroup):
    name = State()
    ico = State()
    dic = State()
    ic_dph = State()
    address = State()
    iban = State()
    swift = State()
    email = State()
    smtp_host = State()
    smtp_user = State()
    smtp_pass = State()
    days_due = State()
    confirm = State()


def _summary(data: dict[str, str]) -> str:
    return (
        '<b>Prehľad profilu dodávateľa</b>\n\n'
        f'• Názov: {data["name"]}\n'
        f'• ICO: {data["ico"]}\n'
        f'• DIC: {data["dic"]}\n'
        f'• IC DPH: {data["ic_dph"] or "-"}\n'
        f'• Adresa: {data["address"]}\n'
        f'• IBAN: {data["iban"]}\n'
        f'• SWIFT: {data["swift"]}\n'
        f'• Email: {data["email"]}\n'
        f'• SMTP host: {data["smtp_host"]}\n'
        f'• SMTP user: {data["smtp_user"]}\n'
        '• SMTP heslo: ********\n'
        f'• Splatnosť: {data["days_due"]} dní\n\n'
        'Napíšte <b>ano</b> pre potvrdenie alebo <b>nie</b> pre zrušenie.'
    )


@router.message(Command('onboarding', 'supplier'))
async def cmd_onboarding(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    service = SupplierService(config.db_path)
    existing = service.get_by_telegram_id(message.from_user.id)

    if existing:
        await message.answer(
            'Profil dodávateľa už existuje.\n'
            f'Aktuálny profil: {existing.name} ({existing.ico}).\n'
            'Onboarding teraz prejdeme znova kvôli aktualizácii.'
        )
    else:
        await message.answer('Spúšťam onboarding dodávateľa.')

    await state.clear()
    await state.set_state(OnboardingStates.name)
    await message.answer('1/12 Zadajte názov firmy / obchodné meno:')


@router.message(OnboardingStates.name)
async def onboarding_name(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Názov nemôže byť prázdny. Skúste znova:')
        return
    await state.update_data(name=value)
    await state.set_state(OnboardingStates.ico)
    await message.answer('2/12 Zadajte ICO (8 číslic):')


@router.message(OnboardingStates.ico)
async def onboarding_ico(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer('Neplatné ICO. Formát: 8 číslic. Skúste znova:')
        return
    await state.update_data(ico=value)
    await state.set_state(OnboardingStates.dic)
    await message.answer('3/12 Zadajte DIC (10 číslic):')


@router.message(OnboardingStates.dic)
async def onboarding_dic(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer('Neplatné DIC. Formát: 10 číslic. Skúste znova:')
        return
    await state.update_data(dic=value)
    await state.set_state(OnboardingStates.ic_dph)
    await message.answer('4/12 Zadajte IC DPH (alebo "-", ak ho nemáte):')


@router.message(OnboardingStates.ic_dph)
async def onboarding_ic_dph(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if value == '-':
        await state.update_data(ic_dph='')
    else:
        if not validate_ic_dph(value):
            await message.answer('Neplatné IC DPH. Príklad: SK1234567890. Skúste znova:')
            return
        await state.update_data(ic_dph=value.upper().replace(' ', ''))

    await state.set_state(OnboardingStates.address)
    await message.answer('5/12 Zadajte adresu:')


@router.message(OnboardingStates.address)
async def onboarding_address(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Adresa nemôže byť prázdna. Skúste znova:')
        return
    await state.update_data(address=value)
    await state.set_state(OnboardingStates.iban)
    await message.answer('6/12 Zadajte IBAN:')


@router.message(OnboardingStates.iban)
async def onboarding_iban(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_iban(value):
        await message.answer('Neplatný IBAN. Skúste znova:')
        return
    await state.update_data(iban=value.upper().replace(' ', ''))
    await state.set_state(OnboardingStates.swift)
    await message.answer('7/12 Zadajte SWIFT/BIC:')


@router.message(OnboardingStates.swift)
async def onboarding_swift(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SWIFT/BIC nemôže byť prázdny. Skúste znova:')
        return
    await state.update_data(swift=value.upper())
    await state.set_state(OnboardingStates.email)
    await message.answer('8/12 Zadajte email:')


@router.message(OnboardingStates.email)
async def onboarding_email(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_email(value):
        await message.answer('Neplatný email. Skúste znova:')
        return
    await state.update_data(email=value)
    await state.set_state(OnboardingStates.smtp_host)
    await message.answer('9/12 Zadajte SMTP host:')


@router.message(OnboardingStates.smtp_host)
async def onboarding_smtp_host(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SMTP host nemôže byť prázdny. Skúste znova:')
        return
    await state.update_data(smtp_host=value)
    await state.set_state(OnboardingStates.smtp_user)
    await message.answer('10/12 Zadajte SMTP user:')


@router.message(OnboardingStates.smtp_user)
async def onboarding_smtp_user(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SMTP user nemôže byť prázdny. Skúste znova:')
        return
    await state.update_data(smtp_user=value)
    await state.set_state(OnboardingStates.smtp_pass)
    await message.answer('11/12 Zadajte SMTP heslo:')


@router.message(OnboardingStates.smtp_pass)
async def onboarding_smtp_pass(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SMTP heslo nemôže byť prázdne. Skúste znova:')
        return
    await state.update_data(smtp_pass=value)
    await state.set_state(OnboardingStates.days_due)
    await message.answer('12/12 Zadajte štandardnú splatnosť v dňoch (celé číslo > 0):')


@router.message(OnboardingStates.days_due)
async def onboarding_days_due(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_days_due(value):
        await message.answer('Neplatná hodnota. Zadajte celé číslo > 0:')
        return
    await state.update_data(days_due=value)
    data = await state.get_data()
    await state.set_state(OnboardingStates.confirm)
    await message.answer(_summary(data))


@router.message(OnboardingStates.confirm)
async def onboarding_confirm(
    message: Message,
    state: FSMContext,
    config: Config,
) -> None:
    answer = (message.text or '').strip().lower()
    if answer not in {'ano', 'nie'}:
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'nie':
        await state.clear()
        await message.answer('Onboarding bol zrušený. Pre nový pokus spustite /supplier.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    service = SupplierService(config.db_path)
    service.create_or_replace(
        SupplierProfile(
            telegram_id=message.from_user.id,
            name=data['name'],
            ico=data['ico'],
            dic=data['dic'],
            ic_dph=data['ic_dph'] or None,
            address=data['address'],
            iban=data['iban'],
            swift=data['swift'],
            email=data['email'],
            smtp_host=data['smtp_host'],
            smtp_user=data['smtp_user'],
            smtp_pass=data['smtp_pass'],
            days_due=int(data['days_due']),
        )
    )

    await state.clear()
    await message.answer('Profil dodávateľa bol uložený.')
