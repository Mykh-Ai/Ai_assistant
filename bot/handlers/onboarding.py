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
        '📋 <b>Підсумок профілю постачальника</b>\n\n'
        f'• Name: {data["name"]}\n'
        f'• ICO: {data["ico"]}\n'
        f'• DIC: {data["dic"]}\n'
        f'• IC DPH: {data["ic_dph"] or "—"}\n'
        f'• Address: {data["address"]}\n'
        f'• IBAN: {data["iban"]}\n'
        f'• SWIFT: {data["swift"]}\n'
        f'• Email: {data["email"]}\n'
        f'• SMTP host: {data["smtp_host"]}\n'
        f'• SMTP user: {data["smtp_user"]}\n'
        '• SMTP pass: ********\n'
        f'• Days due: {data["days_due"]}\n\n'
        'Напишіть <b>yes</b> для підтвердження або <b>no</b> для скасування.'
    )


@router.message(Command('onboarding', 'supplier'))
async def cmd_onboarding(message: Message, state: FSMContext, config: Config) -> None:
    if message.from_user is None:
        await message.answer('Не вдалося визначити користувача.')
        return

    service = SupplierService(config.db_path)
    existing = service.get_by_telegram_id(message.from_user.id)

    if existing:
        await message.answer(
            'Профіль постачальника вже існує.\n'
            f'Поточний профіль: {existing.name} ({existing.ico}).\n'
            'Пройдемо onboarding повторно для оновлення.'
        )
    else:
        await message.answer('Починаємо onboarding постачальника.')

    await state.clear()
    await state.set_state(OnboardingStates.name)
    await message.answer('1/12 Введіть імʼя / obchodné meno:')


@router.message(OnboardingStates.name)
async def onboarding_name(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Імʼя не може бути порожнім. Спробуйте ще раз:')
        return
    await state.update_data(name=value)
    await state.set_state(OnboardingStates.ico)
    await message.answer('2/12 Введіть IČO (8 цифр):')


@router.message(OnboardingStates.ico)
async def onboarding_ico(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_ico(value):
        await message.answer('Некоректний IČO. Формат: 8 цифр. Спробуйте ще раз:')
        return
    await state.update_data(ico=value)
    await state.set_state(OnboardingStates.dic)
    await message.answer('3/12 Введіть DIČ (10 цифр):')


@router.message(OnboardingStates.dic)
async def onboarding_dic(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_dic(value):
        await message.answer('Некоректний DIČ. Формат: 10 цифр. Спробуйте ще раз:')
        return
    await state.update_data(dic=value)
    await state.set_state(OnboardingStates.ic_dph)
    await message.answer('4/12 Введіть IČ DPH (або "-" якщо немає):')


@router.message(OnboardingStates.ic_dph)
async def onboarding_ic_dph(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if value in {'-', '—'}:
        await state.update_data(ic_dph='')
    else:
        if not validate_ic_dph(value):
            await message.answer('Некоректний IČ DPH. Приклад: SK1234567890. Спробуйте ще раз:')
            return
        await state.update_data(ic_dph=value.upper().replace(' ', ''))

    await state.set_state(OnboardingStates.address)
    await message.answer('5/12 Введіть адресу:')


@router.message(OnboardingStates.address)
async def onboarding_address(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('Адреса не може бути порожньою. Спробуйте ще раз:')
        return
    await state.update_data(address=value)
    await state.set_state(OnboardingStates.iban)
    await message.answer('6/12 Введіть IBAN:')


@router.message(OnboardingStates.iban)
async def onboarding_iban(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_iban(value):
        await message.answer('Некоректний IBAN. Спробуйте ще раз:')
        return
    await state.update_data(iban=value.upper().replace(' ', ''))
    await state.set_state(OnboardingStates.swift)
    await message.answer('7/12 Введіть SWIFT/BIC:')


@router.message(OnboardingStates.swift)
async def onboarding_swift(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SWIFT/BIC не може бути порожнім. Спробуйте ще раз:')
        return
    await state.update_data(swift=value.upper())
    await state.set_state(OnboardingStates.email)
    await message.answer('8/12 Введіть email:')


@router.message(OnboardingStates.email)
async def onboarding_email(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_email(value):
        await message.answer('Некоректний email. Спробуйте ще раз:')
        return
    await state.update_data(email=value)
    await state.set_state(OnboardingStates.smtp_host)
    await message.answer('9/12 Введіть SMTP host:')


@router.message(OnboardingStates.smtp_host)
async def onboarding_smtp_host(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SMTP host не може бути порожнім. Спробуйте ще раз:')
        return
    await state.update_data(smtp_host=value)
    await state.set_state(OnboardingStates.smtp_user)
    await message.answer('10/12 Введіть SMTP user:')


@router.message(OnboardingStates.smtp_user)
async def onboarding_smtp_user(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SMTP user не може бути порожнім. Спробуйте ще раз:')
        return
    await state.update_data(smtp_user=value)
    await state.set_state(OnboardingStates.smtp_pass)
    await message.answer('11/12 Введіть SMTP pass:')


@router.message(OnboardingStates.smtp_pass)
async def onboarding_smtp_pass(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not value:
        await message.answer('SMTP pass не може бути порожнім. Спробуйте ще раз:')
        return
    await state.update_data(smtp_pass=value)
    await state.set_state(OnboardingStates.days_due)
    await message.answer('12/12 Введіть стандартну splatnosť у днях (ціле число > 0):')


@router.message(OnboardingStates.days_due)
async def onboarding_days_due(message: Message, state: FSMContext) -> None:
    value = (message.text or '').strip()
    if not validate_days_due(value):
        await message.answer('Некоректне значення. Введіть ціле число > 0:')
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
    if answer not in {'yes', 'no'}:
        await message.answer('Введіть yes або no.')
        return

    if answer == 'no':
        await state.clear()
        await message.answer('Onboarding скасовано. Запустіть /supplier для повтору.')
        return

    if message.from_user is None:
        await message.answer('Не вдалося визначити користувача.')
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
    await message.answer('✅ Профіль постачальника збережено.')
