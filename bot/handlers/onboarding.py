from __future__ import annotations

from datetime import date

from aiogram import Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.config import Config
from bot.services.decision_resolver import resolve_yes_no
from bot.services.invoice_service import InvoiceService
from bot.services.supplier_service import SupplierProfile, SupplierService
from bot.services.validation import (
    validate_days_due,
    validate_dic,
    validate_email,
    validate_iban,
    validate_ic_dph,
    validate_ico,
    validate_invoice_number_for_year,
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
    first_invoice_number = State()
    days_due = State()
    confirm = State()


def _summary(data: dict[str, object]) -> str:
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
        f'• Prvé číslo faktúry od bota ({data["invoice_number_issue_year"]}): {data["first_invoice_number"]}\n'
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
    await message.answer('1/10 Zadajte názov firmy / obchodné meno:')


@router.message(OnboardingStates.name)
async def onboarding_name(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Názov nemôže byť prázdny. Skúste znova:')
        return
    await state.update_data(name=value)
    await state.set_state(OnboardingStates.ico)
    await message.answer('2/10 Zadajte ICO (8 číslic):')


@router.message(OnboardingStates.ico)
async def onboarding_ico(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer('Neplatné ICO. Formát: 8 číslic. Skúste znova:')
        return
    await state.update_data(ico=value)
    await state.set_state(OnboardingStates.dic)
    await message.answer('3/10 Zadajte DIC (10 číslic):')


@router.message(OnboardingStates.dic)
async def onboarding_dic(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer('Neplatné DIC. Formát: 10 číslic. Skúste znova:')
        return
    await state.update_data(dic=value)
    await state.set_state(OnboardingStates.ic_dph)
    await message.answer('4/10 Zadajte IC DPH (alebo "-", ak ho nemáte):')


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
    await message.answer('5/10 Zadajte adresu:')


@router.message(OnboardingStates.address)
async def onboarding_address(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Adresa nemôže byť prázdna. Skúste znova:')
        return
    await state.update_data(address=value)
    await state.set_state(OnboardingStates.iban)
    await message.answer('6/10 Zadajte IBAN:')


@router.message(OnboardingStates.iban)
async def onboarding_iban(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_iban(value):
        await message.answer('Neplatný IBAN. Skúste znova:')
        return
    await state.update_data(iban=value.upper().replace(' ', ''))
    await state.set_state(OnboardingStates.swift)
    await message.answer('7/10 Zadajte SWIFT/BIC:')


@router.message(OnboardingStates.swift)
async def onboarding_swift(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SWIFT/BIC nemôže byť prázdny. Skúste znova:')
        return
    await state.update_data(swift=value.upper())
    await state.set_state(OnboardingStates.email)
    await message.answer('8/10 Zadajte email:')


@router.message(OnboardingStates.email)
async def onboarding_email(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_email(value):
        await message.answer('Neplatný email. Skúste znova:')
        return
    issue_year = date.today().year
    await state.update_data(email=value, invoice_number_issue_year=issue_year)
    await state.set_state(OnboardingStates.first_invoice_number)
    await message.answer(
        f'9/10 Zadajte prvé číslo faktúry, ktoré má FakturaBot vytvoriť v roku {issue_year}.\n'
        'Ak ste už vystavili faktúry mimo bota, zadajte ďalšie voľné číslo.\n'
        f'Príklad: ak posledná faktúra bola {issue_year}0024, zadajte {issue_year}0025.\n'
        f'Ak ešte nemáte žiadne faktúry, zadajte {issue_year}0001.'
    )


@router.message(OnboardingStates.first_invoice_number)
async def onboarding_first_invoice_number(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    data = await state.get_data()
    issue_year = int(data.get('invoice_number_issue_year') or date.today().year)
    if not validate_invoice_number_for_year(value, issue_year):
        await message.answer(
            f'Neplatné číslo faktúry. Zadajte číslo vo formáte {issue_year}NNNN, '
            f'napríklad {issue_year}0001:'
        )
        return
    await state.update_data(first_invoice_number=value)
    await state.set_state(OnboardingStates.days_due)
    await message.answer('10/10 Zadajte štandardnú splatnosť v dňoch (celé číslo > 0):')


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
    answer = await resolve_yes_no(
        context_name='onboarding_confirm',
        user_input_text=(message.text or ''),
        api_key=config.openai_api_key,
        model=config.openai_llm_model,
    )
    if answer == 'unknown':
        await message.answer('Napíšte ano alebo nie.')
        return

    if answer == 'no':
        await state.clear()
        await message.answer('Onboarding bol zrušený. Pre nový pokus spustite /supplier.')
        return

    if message.from_user is None:
        await message.answer('Nepodarilo sa identifikovať používateľa.')
        return

    data = await state.get_data()
    service = SupplierService(config.db_path)
    invoice_service = InvoiceService(config.db_path)
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
            smtp_host=None,
            smtp_user=None,
            smtp_pass=None,
            days_due=int(data['days_due']),
        )
    )
    invoice_service.set_first_invoice_number(
        supplier_telegram_id=message.from_user.id,
        issue_year=int(data['invoice_number_issue_year']),
        first_invoice_number=str(data['first_invoice_number']),
    )

    await state.clear()
    await message.answer('Profil dodávateľa bol uložený.')
